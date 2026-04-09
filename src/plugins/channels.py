from __future__ import annotations

import asyncio
import contextlib
import errno
import json
import os
import random
import tempfile
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger
from PIL import Image, UnidentifiedImageError
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InputMediaPhoto, InputMediaVideo, Message

from src.config import config
from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.chats import (
    get_chat_settings,
)
from src.utils.decorators import safe_handler
from src.utils.input import (
    finalize_input_capture,
    is_waiting_for_input,
)
from src.utils.media import (
    apply_video_watermark,
    apply_watermark,
    parse_watermark_config,
)
from src.utils.rate_limit import TokenBucketLimiter

if TYPE_CHECKING:
    from src.db.models import ChatSettings


@dataclass(slots=True)
class WatermarkOptions:
    text: str
    color: str
    style: str
    image_enabled: bool
    video_enabled: bool
    video_quality: str
    video_motion: str


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
            logger.debug(
                f"[channels] No settings found for chat={message.chat.id}, skipping message={message.id}"
            )
            return

        await self._handle_reactions(settings, message)

        plan = await self._build_content_plan(settings, message)
        wm = self._get_watermark_options(settings)
        logger.debug(
            "[channels] message={} chat={} media={} photo={} video={} wm_enabled={} wm_text={} video_wm={} "
            "video_quality={} video_motion={} signature_enabled={}",
            message.id,
            message.chat.id,
            plan.is_media,
            bool(message.photo),
            bool(message.video),
            wm.image_enabled,
            bool(wm.text),
            wm.video_enabled,
            wm.video_quality,
            wm.video_motion,
            settings.signatureEnabled,
        )

        if plan.is_media and message.photo and wm.image_enabled and wm.text:
            logger.debug(f"[channels] Applying image watermark for message={message.id}")
            if message.media_group_id:
                logger.debug(
                    f"[channels] Deferring image watermark to album worker for media_group={message.media_group_id}"
                )
                self._schedule_album_job(message)
                return

            await self._handle_watermarking(
                message,
                plan.target_content or message.caption,
                wm,
            )
            return

        if (
            plan.is_media
            and message.video
            and wm.video_enabled
            and wm.text
            and config.ENABLE_VIDEO_WATERMARK
        ):
            logger.debug(
                f"[channels] Applying video watermark for message={message.id} quality={wm.video_quality}"
            )
            await self._handle_video_watermarking(
                message,
                plan.target_content or message.caption,
                wm,
            )
            return
        if plan.is_media and message.video and wm.video_enabled and wm.text:
            logger.debug(
                "[channels] Video watermark skipped for message={} (channel_video={}, developer_video={})",
                message.id,
                wm.video_enabled,
                config.ENABLE_VIDEO_WATERMARK,
            )

        if plan.target_content is not None:
            logger.debug(f"[channels] Applying signature update for message={message.id}")
            await self._handle_signature(message, plan.target_content, plan.is_media)

    def _schedule_album_job(self, message: Message) -> None:
        media_group_id = message.media_group_id
        if not media_group_id or media_group_id in self._album_jobs:
            return
        logger.debug(f"[channels] Scheduling album watermark job media_group={media_group_id}")
        self._album_jobs[media_group_id] = asyncio.create_task(
            self._process_album_after_debounce(media_group_id, message)
        )

    async def _process_album_after_debounce(
        self, media_group_id: str, anchor_message: Message
    ) -> None:
        try:
            await asyncio.sleep(self.ALBUM_DEBOUNCE_SECONDS)
            ctx = get_context()
            settings: ChatSettings | None = await get_chat_settings(ctx, anchor_message.chat.id)
            if not settings:
                return
            wm = self._get_watermark_options(settings)
            if not ((wm.image_enabled or wm.video_enabled) and wm.text):
                logger.debug(
                    f"[channels] Album watermark skipped media_group={media_group_id} "
                    f"(image_enabled={wm.image_enabled}, video_enabled={wm.video_enabled}, has_text={bool(wm.text)})"
                )
                return
            with contextlib.suppress(Exception):
                group = await anchor_message.get_media_group()
                if not group:
                    return

                async with self._processing_lock:
                    trigger = min(group, key=lambda m: m.id)
                    caption_host = next((m for m in group if m.caption), None) or trigger
                    final_caption = (
                        self._calculate_target_content(
                            settings, caption_host, is_media=True, is_caption_host=True
                        )
                        or caption_host.caption
                    )

                    photo_items = self._select_album_photos(group, caption_host)
                    if not photo_items:
                        return
                    logger.debug(
                        f"[channels] Album watermark media_group={media_group_id} photos_to_edit={len(photo_items)}"
                    )

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
        return WatermarkOptions(
            text=cfg.text,
            color=cfg.color,
            style=cfg.style,
            image_enabled=cfg.image_enabled,
            video_enabled=cfg.video_enabled,
            video_quality=cfg.video_quality,
            video_motion=cfg.video_motion,
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
        logger.debug(f"[channels] Start image watermark pipeline message={message.id}")
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = self._safe_temp_media_path(temp_dir, "img_input", ".jpg")
            output_path = self._safe_temp_media_path(temp_dir, "img_output", ".jpg")
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
            ):
                logger.debug(
                    f"[channels] Image watermark renderer returned false message={message.id}"
                )
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
                logger.debug(f"[channels] Image watermark edit success message={message.id}")
            except OSError as e:
                if e.errno == errno.ENOSPC:
                    logger.error(
                        f"Storage full while editing media for message {message.id}; skipping update."
                    )
                    return
                logger.error(f"OS error watermarking message {message.id}: {e}")
            except Exception as e:
                logger.error(f"Error watermarking message {message.id}: {e}")

    async def _handle_video_watermarking(
        self,
        message: Message,
        final_caption: str | None,
        wm: WatermarkOptions,
    ) -> None:
        logger.debug(
            f"[channels] Start video watermark pipeline message={message.id} "
            f"quality={wm.video_quality} motion={wm.video_motion}"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = self._safe_temp_media_path(temp_dir, "video_input", ".mp4")
            output_path = self._safe_temp_media_path(temp_dir, "video_output", ".mp4")
            # Developer-side hard limit to protect low-resource servers.
            max_size_bytes = max(1, int(config.VIDEO_WATERMARK_MAX_SIZE_MB)) * 1024 * 1024
            source_size = int(getattr(message.video, "file_size", 0) or 0)
            if source_size > max_size_bytes:
                logger.debug(
                    "[channels] Skip video watermark (over size limit) message={} size={} limit={}",
                    message.id,
                    self._human_size(source_size),
                    self._human_size(max_size_bytes),
                )
                return
            try:
                video_path = await message.download(file_name=input_path)
            except OSError as e:
                if e.errno == errno.ENOSPC:
                    logger.error(
                        f"Storage full while downloading video for message {message.id}; skipping watermark."
                    )
                    return
                logger.error(f"OS error downloading video for message {message.id}: {e}")
                return
            except Exception as e:
                logger.error(f"Error downloading video for message {message.id}: {e}")
                return

            if not video_path or not os.path.exists(video_path):
                return

            if not apply_video_watermark(
                video_path,
                wm.text,
                output_path,
                color=wm.color,
                style=wm.style,
                quality=wm.video_quality,
                motion=wm.video_motion,
            ):
                logger.debug(
                    f"[channels] Video watermark renderer returned false message={message.id}"
                )
                return

            with contextlib.suppress(OSError):
                input_size = os.path.getsize(video_path)
                output_size = os.path.getsize(output_path)
                delta = output_size - input_size
                sign = "+" if delta > 0 else "-"
                delta_abs = abs(delta)
                ratio = (delta / input_size * 100.0) if input_size > 0 else 0.0
                logger.debug(
                    "[channels] Video size change message={} quality={} motion={} input={} output={} delta={}{} ({:+.2f}%)",
                    message.id,
                    wm.video_quality,
                    wm.video_motion,
                    self._human_size(input_size),
                    self._human_size(output_size),
                    sign,
                    self._human_size(delta_abs),
                    ratio,
                )

            async def do_edit_media() -> None:
                await message.edit_media(
                    media=InputMediaVideo(
                        media=output_path,
                        caption=final_caption,
                        caption_entities=message.caption_entities,
                        parse_mode=None,
                    )
                )

            try:
                await self._run_with_retry(message.chat.id, self.METHOD_EDIT, do_edit_media)
                logger.debug(f"[channels] Video watermark edit success message={message.id}")
            except OSError as e:
                if e.errno == errno.ENOSPC:
                    logger.error(
                        f"Storage full while editing video for message {message.id}; skipping update."
                    )
                    return
                logger.error(f"OS error video watermarking message {message.id}: {e}")
            except Exception as e:
                logger.error(f"Error video watermarking message {message.id}: {e}")

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

    def _safe_temp_media_path(self, temp_dir: str, stem: str, ext: str) -> str:
        """
        Build a bot-controlled temp path and ensure it stays inside temp_dir.
        Prevents any path/name influence from untrusted sources.
        """
        safe_name = f"lex_{stem}_{uuid.uuid4().hex}{ext}"
        candidate = os.path.realpath(os.path.join(temp_dir, safe_name))
        temp_root = os.path.realpath(temp_dir)
        if os.path.commonpath([candidate, temp_root]) != temp_root:
            raise ValueError("Unsafe temp media path generated")
        return candidate

    def _human_size(self, size_bytes: int) -> str:
        """Format byte size using human-readable binary units."""
        units = ("B", "KB", "MB", "GB", "TB")
        size = float(max(0, size_bytes))
        unit_idx = 0
        while size >= 1024.0 and unit_idx < len(units) - 1:
            size /= 1024.0
            unit_idx += 1
        return f"{size:.2f} {units[unit_idx]}"


channels_plugin = ChannelsPlugin()


@bot.on_message(filters.channel & ~filters.forwarded & ~filters.service & ~filters.via_bot, group=-100)
async def channel_post_handler(client: Client, message: Message) -> None:
    """EntryPoint for channel posts: push to queue for sequential processing."""
    await channels_plugin.queue.put(message)
    await message.continue_propagation()


@bot.on_message(filters.channel & filters.service, group=-100)
async def channel_service_handler(client: Client, message: Message) -> None:
    """Delete channel service messages based on service cleaner settings."""
    ctx = get_context()
    settings: ChatSettings | None = await get_chat_settings(ctx, message.chat.id)
    if not settings:
        await message.continue_propagation()
        return

    should_delete = False
    if settings.cleanAllServices:
        should_delete = True
    else:
        try:
            enabled_types = set(json.loads(settings.cleanServiceTypes or "[]"))
        except (json.JSONDecodeError, TypeError):
            enabled_types = set()
        service_type = getattr(message, "service", None)
        if service_type and hasattr(service_type, "name"):
            should_delete = service_type.name in enabled_types

    if should_delete:
        with contextlib.suppress(Exception):
            await message.delete()

    await message.continue_propagation()


# --- Admin Panel Input Handlers ---


@bot.on_message(
    filters.private & is_waiting_for_input(["reactions", "watermarkText", "signatureText"]),
    group=-50,
)
@safe_handler
async def channel_content_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    channel_id = state["chat_id"]
    field = state["field"]
    user_id = message.from_user.id
    ctx = get_context()
    value = message.text or ""

    from src.db.repositories.chats import update_chat_setting
    from src.plugins.admin_panel.handlers.keyboards import channel_settings_kb, channel_watermark_kb

    if field == "reactions":
        import emoji

        emojis = [c for c in str(value) if emoji.is_emoji(c)] or [
            word for word in str(value).split() if any(emoji.is_emoji(c) for c in word)
        ]
        await update_chat_setting(
            ctx, channel_id, "reactions", " ".join(emojis) if emojis else "👍"
        )
    elif field == "watermarkText":
        from src.utils.watermark import (
            build_watermark_config,
            parse_watermark_config,
        )

        s = await get_chat_settings(ctx, channel_id)
        cfg = parse_watermark_config(s.watermarkText)
        cfg.text = str(value).strip()
        await update_chat_setting(
            ctx,
            channel_id,
            "watermarkText",
            build_watermark_config(
                cfg.text,
                color=cfg.color,
                style=cfg.style,
                image_enabled=cfg.image_enabled,
                video_enabled=cfg.video_enabled,
                video_quality=cfg.video_quality,
                video_motion=cfg.video_motion,
            ),
        )
    elif field == "signatureText":
        await update_chat_setting(ctx, channel_id, "signatureText", str(value))

    from src.utils.i18n import at

    s = await get_chat_settings(ctx, channel_id)
    title = s.title or f"Channel {channel_id}"

    if field == "watermarkText":
        from src.utils.watermark import (
            build_watermark_config,
            parse_watermark_config,
        )

        cfg = parse_watermark_config(s.watermarkText)
        main_text = await at(
            user_id,
            "panel.channel_watermark_text",
            image_status=await at(
                user_id, "panel.status_enabled" if cfg.image_enabled else "panel.status_disabled"
            ),
            text=cfg.text or "-",
            color=await at(user_id, f"panel.wm_color_{cfg.color}"),
            style=await at(user_id, f"panel.wm_style_{cfg.style}"),
            video_status=await at(
                user_id, "panel.status_enabled" if cfg.video_enabled else "panel.status_disabled"
            ),
            video_quality=await at(user_id, f"panel.wm_quality_{cfg.video_quality}"),
            video_motion=await at(user_id, f"panel.wm_motion_{cfg.video_motion}"),
            video_available=await at(
                user_id,
                "panel.wm_video_available_yes"
                if config.ENABLE_VIDEO_WATERMARK
                else "panel.wm_video_available_no",
            ),
            video_limit_note=(
                await at(
                    user_id, "panel.wm_video_limit_note", size_mb=config.VIDEO_WATERMARK_MAX_SIZE_MB
                )
                if config.ENABLE_VIDEO_WATERMARK
                else ""
            ),
        )
        kb = await channel_watermark_kb(ctx, channel_id, user_id)
    else:
        status = await at(user_id, "panel.status_enabled" if s.enabled else "panel.status_disabled")
        main_text = await at(
            user_id,
            "panel.channel_settings_text",
            title=title,
            id=channel_id,
            status=status,
            reactions=s.reactions or "👍",
            signature=s.signatureText or await at(user_id, "panel.not_set"),
            sign_pos=s.signaturePosition.upper(),
        )
        kb = await channel_settings_kb(ctx, channel_id, user_id)

    await finalize_input_capture(
        client, message, user_id, state["prompt_msg_id"], main_text, kb, success_text=None
    )


register(ChannelsPlugin())
