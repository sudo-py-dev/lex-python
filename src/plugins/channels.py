from __future__ import annotations

import asyncio
import contextlib
import os
import random
import tempfile
from typing import TYPE_CHECKING

from pyrogram import Client, filters
from pyrogram.types import InputMediaPhoto, Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.plugins.admin_panel.repository import get_chat_settings
from src.utils.media import apply_watermark, parse_watermark_config

if TYPE_CHECKING:
    from src.db.models import ChatSettings


class ChannelsPlugin(Plugin):
    """
    Plugin to handle channel administration and automation with flood protection.

    Provides features like automated reactions, watermarking images, and appending
    signatures to channel posts. Processes all messages through a sequential worker
    to prevent Telegram's FloodWait errors.
    """

    name: str = "channels"
    priority: int = 100

    def __init__(self):
        super().__init__()
        self.queue: asyncio.Queue[Message] = asyncio.Queue()
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(1)
        self._worker_task: asyncio.Task | None = None

    async def setup(self, client: Client, ctx) -> None:
        """Starts the background sequential processor task."""
        self._worker_task = asyncio.create_task(self._worker(client))

    async def teardown(self) -> None:
        """Safely shuts down the background worker task."""
        if self._worker_task:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task

    async def _worker(self, client: Client) -> None:
        """
        Background worker that processes channel posts sequentially.
        Ensures that resource-intensive operations and API calls are throttled.
        """
        while True:
            try:
                message = await self.queue.get()
                async with self.semaphore:
                    await self._process_message(client, message)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                from loguru import logger

                logger.error(f"Error in channel worker: {e}")
                await asyncio.sleep(1)

    async def _process_message(self, client: Client, message: Message) -> None:
        """
        Core automation entry point for a single channel message.
        Dispatches tasks for reactions and content enhancements.
        """
        ctx = get_context()
        settings: ChatSettings | None = await get_chat_settings(ctx, message.chat.id)

        if not settings:
            return

        # 1. Automated Reactions
        await self._handle_reactions(settings, message)

        # 2. Preparation for Content Updates
        is_caption_host = await self._is_caption_host(message)
        is_media = bool(
            message.photo
            or message.video
            or message.document
            or message.animation
            or message.audio
            or message.voice
            or message.video_note
        )

        # Calculate proposed signature update
        target_content = self._calculate_target_content(
            settings, message, is_media, is_caption_host
        )

        # 3. Dispatched Task Selection (Ensure only one edit occurs)
        wm_cfg = parse_watermark_config(settings.watermarkText)
        wm_text = wm_cfg.get("text", "")
        if wm_cfg.get("type") == "username" and wm_text and not wm_text.startswith("@"):
            wm_text = f"@{wm_text.lstrip('@')}"

        if is_media and message.photo and settings.watermarkEnabled and wm_text:
            # Photos get watermarked (and signature is passed through if applicable)
            # IMPORTANT: In an album, ONLY edit the caption host to avoid accidental caption loss.
            if message.media_group_id and not is_caption_host:
                return

            await self._handle_watermarking(
                settings,
                message,
                target_content or message.caption,
                wm_text=wm_text,
                wm_color=wm_cfg.get("color", "white"),
                wm_style=wm_cfg.get("style", "shadow"),
            )
        elif target_content is not None:
            # Other content gets only signature update
            await self._handle_signature(message, target_content, is_media)

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

        with contextlib.suppress(Exception):
            await message.react(target_reaction)

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

        try:
            if is_media:
                await message.edit_caption(
                    caption=new_content, caption_entities=entities, parse_mode=None
                )
            else:
                await message.edit_text(text=new_content, entities=entities, parse_mode=None)
        except Exception as e:
            from loguru import logger

            logger.error(f"Error adding signature to message {message.id}: {e}")

    async def _handle_watermarking(
        self,
        settings: ChatSettings,
        message: Message,
        final_caption: str | None,
        wm_text: str,
        wm_color: str,
        wm_style: str,
    ) -> None:
        """
        Downloads the image, applies the watermark and the final caption, then updates the post.
        """
        from loguru import logger

        with tempfile.TemporaryDirectory() as temp_dir:
            photo_path = await message.download(file_name=os.path.join(temp_dir, "input.jpg"))
            output_path = os.path.join(temp_dir, "output.jpg")

            if not photo_path or not apply_watermark(
                photo_path, wm_text, output_path, color=wm_color, style=wm_style
            ):
                return

            try:
                await message.edit_media(
                    media=InputMediaPhoto(
                        media=output_path,
                        caption=final_caption,
                        caption_entities=message.caption_entities,
                        parse_mode=None,
                    )
                )
            except Exception as e:
                logger.error(f"Error watermarking message {message.id}: {e}")


# Define an instance of the plugin to store state
channels_plugin = ChannelsPlugin()


@bot.on_message(filters.channel & ~filters.forwarded & ~filters.service & ~filters.via_bot)
async def channel_post_handler(client: Client, message: Message) -> None:
    """EntryPoint for channel posts: push to queue for sequential processing."""
    await channels_plugin.queue.put(message)
    await message.continue_propagation()


register(channels_plugin)
