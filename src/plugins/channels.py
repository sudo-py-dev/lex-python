from __future__ import annotations

import asyncio
import contextlib
import errno
import os
import random
import tempfile
from dataclasses import dataclass
from typing import TYPE_CHECKING
from collections.abc import Awaitable, Callable

from PIL import Image, UnidentifiedImageError
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InputMediaPhoto, Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.plugins.admin_panel.repository import get_chat_settings
from src.utils.media import apply_watermark, parse_watermark_config
from src.utils.rate_limit import TokenBucketLimiter

if TYPE_CHECKING:
    from src.db.models import ChatSettings


@dataclass(slots=True)
class WatermarkOptions:
    text: str
    color: str
    style: str
    location: str


@dataclass(slots=True)
class ChannelContentPlan:
    is_media: bool
    is_caption_host: bool
    target_content: str | None


class ChannelsPlugin(Plugin):
    """
    Plugin to handle channel administration and automation with flood protection.

    Provides features like automated reactions, watermarking images, and appending
    signatures to channel posts. Processes all messages through a sequential worker
    to prevent Telegram's FloodWait errors.
    """

    name: str = "channels"
    priority: int = 100
    ALBUM_DEBOUNCE_SECONDS: int = 10
    ALBUM_MAX_PHOTOS_TO_EDIT: int = 10
    METHOD_EDIT: str = "edit"
    METHOD_REACT: str = "react"

    def __init__(self):
        super().__init__()
        self.queue: asyncio.Queue[Message] = asyncio.Queue()
        self._processing_lock: asyncio.Semaphore = asyncio.Semaphore(1)
        self._worker_task: asyncio.Task | None = None
        self._album_jobs: dict[str, asyncio.Task] = {}
        self._global_mutation_limiter = TokenBucketLimiter(rate=8.0, burst=8.0)
        self._chat_mutation_limiter = TokenBucketLimiter(rate=0.45, burst=2.0)
        self._edit_method_limiter = TokenBucketLimiter(rate=0.4, burst=1.0)
        self._react_method_limiter = TokenBucketLimiter(rate=1.0, burst=1.0)

    async def setup(self, client: Client, ctx) -> None:
        """Starts the background sequential processor task."""
        self._worker_task = asyncio.create_task(self._worker(client))

    async def teardown(self) -> None:
        """Safely shuts down the background worker task."""
        if self._worker_task:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
        for task in list(self._album_jobs.values()):
            task.cancel()
        self._album_jobs.clear()

    async def _worker(self, client: Client) -> None:
        """
        Background worker that processes channel posts sequentially.
        Ensures that resource-intensive operations and API calls are throttled.
        """
        while True:
            message: Message | None = None
            try:
                message = await self.queue.get()
                async with self._processing_lock:
                    await self._process_message(client, message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                from loguru import logger

                logger.error(f"Error in channel worker: {e}")
                await asyncio.sleep(1)
            finally:
                if message is not None:
                    self.queue.task_done()

    async def _process_message(self, client: Client, message: Message) -> None:
        """
        Core automation entry point for a single channel message.
        Dispatches tasks for reactions and content enhancements.
        """
        ctx = get_context()
        settings: ChatSettings | None = await get_chat_settings(ctx, message.chat.id)
        if not settings:
            return

        await self._handle_reactions(settings, message)

        plan = await self._build_content_plan(settings, message)
        wm = self._get_watermark_options(settings)

        if plan.is_media and message.photo and settings.watermarkEnabled and wm.text:
            if message.media_group_id:
                self._schedule_album_job(message)
                return

            await self._handle_watermarking(
                message,
                plan.target_content or message.caption,
                wm,
            )
            return

        if plan.target_content is not None:
            await self._handle_signature(message, plan.target_content, plan.is_media)

    def _schedule_album_job(self, message: Message) -> None:
        media_group_id = message.media_group_id
        if not media_group_id or media_group_id in self._album_jobs:
            return
        self._album_jobs[media_group_id] = asyncio.create_task(
            self._process_album_after_debounce(media_group_id, message)
        )

    async def _process_album_after_debounce(
        self, media_group_id: str, anchor_message: Message
    ) -> None:
        try:
            # Debounce until Telegram has delivered the full album.
            await asyncio.sleep(self.ALBUM_DEBOUNCE_SECONDS)
            ctx = get_context()
            settings: ChatSettings | None = await get_chat_settings(ctx, anchor_message.chat.id)
            if not settings:
                return
            wm = self._get_watermark_options(settings)
            if not (settings.watermarkEnabled and wm.text):
                return
            with contextlib.suppress(Exception):
                group = await anchor_message.get_media_group()
                if not group:
                    return

                async with self._processing_lock:
                    trigger = min(group, key=lambda m: m.id)
                    caption_host = next((m for m in group if m.caption), None) or trigger
                    final_caption = self._calculate_target_content(
                        settings, caption_host, is_media=True, is_caption_host=True
                    ) or caption_host.caption

                    photo_items = self._select_album_photos(group, caption_host)
                    if not photo_items:
                        return

                    for item in photo_items:
                        item_caption = final_caption if item.id == caption_host.id else None
                        await self._handle_watermarking(
                            item,
                            item_caption,
                            wm,
                        )
                        await asyncio.sleep(self._get_album_edit_interval(len(photo_items)))
        finally:
            self._album_jobs.pop(media_group_id, None)

    def _select_album_photos(self, group: list[Message], caption_host: Message) -> list[Message]:
        """Apply album quota while keeping caption host image in the edited set."""
        photo_items = [m for m in group if m.photo]
        if not photo_items:
            return []
        selected = photo_items[: self.ALBUM_MAX_PHOTOS_TO_EDIT]
        if caption_host.photo and caption_host not in selected and selected:
            selected[-1] = caption_host
        return selected

    def _get_album_edit_interval(self, total_items: int) -> float:
        """Adaptive edit interval based on album size."""
        return min(4.0, 1.8 + (total_items * 0.25))

    def _get_watermark_options(self, settings: ChatSettings) -> WatermarkOptions:
        cfg = parse_watermark_config(settings.watermarkText)
        text = cfg.get("text", "")
        if cfg.get("type") == "username" and text and not text.startswith("@"):
            text = f"@{text.lstrip('@')}"
        return WatermarkOptions(
            text=text,
            color=cfg.get("color", "white"),
            style=cfg.get("style", "shadow"),
            location=cfg.get("location", "bottom_right"),
        )

    async def _build_content_plan(
        self, settings: ChatSettings, message: Message
    ) -> ChannelContentPlan:
        """Build once, then route message through watermark/signature handlers."""
        is_media = bool(
            message.photo
            or message.video
            or message.document
            or message.animation
            or message.audio
            or message.voice
            or message.video_note
        )
        is_caption_host = await self._is_caption_host(message)
        target_content = self._calculate_target_content(
            settings, message, is_media, is_caption_host
        )
        return ChannelContentPlan(
            is_media=is_media, is_caption_host=is_caption_host, target_content=target_content
        )

    def _calculate_target_content(
        self, settings: ChatSettings, message: Message, is_media: bool, is_caption_host: bool
    ) -> str | None:
        """
        Calculates the new text/caption for the message including the signature.
        Returns None if no update is required.
        """
        if not (settings.signatureEnabled and settings.signatureText and is_caption_host):
            return None

        current = (message.caption or "") if is_media else (message.text or "")
        limit = 1024 if is_media else 4096
        sig = f"\n\n{settings.signatureText}"

        # Only apply if not already present and fits limit
        if sig not in current and len(current) + len(sig) <= limit:
            return f"{current}{sig}"

        return None

    async def _handle_reactions(self, settings: ChatSettings, message: Message) -> None:
        """
        Applies exactly one reaction based on the reactionMode (fixed vs random).

        Args:
            settings: The chat settings containing reaction configuration.
            message: The Pyrogram message to react to.
        """
        if not settings.reactionsEnabled or not settings.reactions:
            return

        reactions = settings.reactions.split()
        if not reactions:
            return

        # Telegram limits bots to ONE reaction per message - Mode 'all' defaults to first emoji
        target_reaction = (
            reactions[0] if settings.reactionMode == "all" else random.choice(reactions)
        )

        async def do_react() -> None:
            await message.react(target_reaction)

        with contextlib.suppress(Exception):
            await self._run_with_retry(message.chat.id, self.METHOD_REACT, do_react)

    async def _is_caption_host(self, message: Message) -> bool:
        """
        In a media group (album), only one message should typically carry the caption.
        This method identifies if the current message is that host.
        """
        if not message.media_group_id:
            return True

        try:
            group = await message.get_media_group()
            host_message = next((m for m in group if m.caption), None)
            if not host_message:
                host_message = min(group, key=lambda m: m.id)
            return message.id == host_message.id
        except Exception:
            return True

    async def _handle_signature(self, message: Message, new_content: str, is_media: bool) -> None:
        """
        Applies the pre-calculated signature to the message text or caption.
        """
        entities = message.caption_entities if is_media else message.entities

        async def do_edit() -> None:
            if is_media:
                await message.edit_caption(
                    caption=new_content, caption_entities=entities, parse_mode=None
                )
            else:
                await message.edit_text(text=new_content, entities=entities, parse_mode=None)

        try:
            await self._run_with_retry(message.chat.id, self.METHOD_EDIT, do_edit)
        except Exception as e:
            from loguru import logger

            logger.error(f"Error adding signature to message {message.id}: {e}")

    async def _handle_watermarking(
        self,
        message: Message,
        final_caption: str | None,
        wm: WatermarkOptions,
    ) -> None:
        """
        Downloads the image, applies the watermark and the final caption, then updates the post.
        """
        from loguru import logger

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "input.jpg")
            output_path = os.path.join(temp_dir, "output.jpg")
            try:
                photo_path = await message.download(file_name=input_path)
            except OSError as e:
                if e.errno == errno.ENOSPC:
                    logger.error(
                        f"Storage full while downloading image for message {message.id}; skipping watermark."
                    )
                    return
                logger.error(f"OS error downloading image for message {message.id}: {e}")
                return
            except Exception as e:
                logger.error(f"Error downloading image for message {message.id}: {e}")
                return

            if not photo_path:
                return
            if not self._is_real_image(photo_path):
                logger.error(f"Downloaded file is not a valid image for message {message.id}")
                return

            if not apply_watermark(
                photo_path,
                wm.text,
                output_path,
                color=wm.color,
                style=wm.style,
                location=wm.location,
            ):
                return

            if not self._is_real_image(output_path):
                logger.error(f"Watermark output is not a valid image for message {message.id}")
                return

            async def do_edit_media() -> None:
                await message.edit_media(
                    media=InputMediaPhoto(
                        media=output_path,
                        caption=final_caption,
                        caption_entities=message.caption_entities,
                        parse_mode=None,
                    )
                )

            try:
                await self._run_with_retry(message.chat.id, self.METHOD_EDIT, do_edit_media)
            except OSError as e:
                if e.errno == errno.ENOSPC:
                    logger.error(
                        f"Storage full while editing media for message {message.id}; skipping update."
                    )
                    return
                logger.error(f"OS error watermarking message {message.id}: {e}")
            except Exception as e:
                logger.error(f"Error watermarking message {message.id}: {e}")

    async def _throttle_operation(self, chat_id: int, method: str) -> None:
        chat_key = str(chat_id)
        await self._global_mutation_limiter.wait("global")
        await self._chat_mutation_limiter.wait(chat_key)
        if method == self.METHOD_EDIT:
            await self._edit_method_limiter.wait(chat_key)
        elif method == self.METHOD_REACT:
            await self._react_method_limiter.wait(chat_key)

    async def _on_floodwait(self, chat_id: int, method: str, seconds: float) -> None:
        chat_key = str(chat_id)
        # Feed wait signal back to all relevant limiters to avoid retry storms.
        await self._global_mutation_limiter.penalize("global", seconds)
        await self._chat_mutation_limiter.penalize(chat_key, seconds)
        if method == self.METHOD_EDIT:
            await self._edit_method_limiter.penalize(chat_key, seconds)
        elif method == self.METHOD_REACT:
            await self._react_method_limiter.penalize(chat_key, seconds)

    async def _run_with_retry(
        self, chat_id: int, method: str, op: Callable[[], Awaitable[None]]
    ) -> None:
        """Throttle operation, retry once on FloodWait."""
        await self._throttle_operation(chat_id, method)
        try:
            await op()
        except FloodWait as e:
            await self._on_floodwait(chat_id, method, float(e.value))
            await asyncio.sleep(float(e.value) + 0.2)
            await self._throttle_operation(chat_id, method)
            await op()

    def _is_real_image(self, path: str) -> bool:
        """Validate file exists and can be decoded as an image."""
        if not os.path.exists(path):
            return False
        try:
            with Image.open(path) as img:
                img.verify()
            with Image.open(path):
                pass
            return True
        except (UnidentifiedImageError, OSError, ValueError):
            return False


# Define an instance of the plugin to store state
channels_plugin = ChannelsPlugin()


@bot.on_message(filters.channel & ~filters.forwarded & ~filters.service & ~filters.via_bot)
async def channel_post_handler(client: Client, message: Message) -> None:
    """EntryPoint for channel posts: push to queue for sequential processing."""
    await channels_plugin.queue.put(message)
    await message.continue_propagation()


register(channels_plugin)
