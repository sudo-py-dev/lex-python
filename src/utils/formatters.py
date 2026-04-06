import re
from typing import Any, TypedDict

from pyrogram.enums import ButtonStyle
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    ReplyParameters,
    User,
)


class ParsedMessage(TypedDict):
    text: str
    reply_markup: InlineKeyboardMarkup | None
    link_preview_options: LinkPreviewOptions
    disable_notification: bool
    protect_content: bool
    has_media_spoiler: bool


class TelegramFormatter:
    """Centralized utility for formatting bot messages, replacing fillings and extracting keyboards."""

    @staticmethod
    def parse_message(
        text: str,
        user: User | None = None,
        chat_id: int = 0,
        chat_title: str = "",
        bot_username: str = "",
    ) -> ParsedMessage:
        if not text:
            return ParsedMessage(
                text="",
                reply_markup=None,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
                disable_notification=False,
                protect_content=False,
                has_media_spoiler=False,
            )

        kwargs: ParsedMessage = {
            "text": text,
            "reply_markup": None,
            "link_preview_options": LinkPreviewOptions(is_disabled=True),  # off by default
            "disable_notification": False,
            "protect_content": False,
            "has_media_spoiler": False,
        }

        # 1. Handle special modifiers
        kwargs["text"] = kwargs["text"].replace("{nonotif}", "")
        if "{nonotif}" in text:
            kwargs["disable_notification"] = True

        kwargs["text"] = kwargs["text"].replace("{protect}", "")
        if "{protect}" in text:
            kwargs["protect_content"] = True

        kwargs["text"] = kwargs["text"].replace("{mediaspoiler}", "")
        if "{mediaspoiler}" in text:
            kwargs["has_media_spoiler"] = True

        kwargs["text"] = kwargs["text"].replace("{preview}", "")
        kwargs["text"] = kwargs["text"].replace("{preview:top}", "")
        if "{preview:top}" in text:
            kwargs["link_preview_options"] = LinkPreviewOptions(
                is_disabled=False, show_above_text=True
            )
        elif "{preview}" in text:
            kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=False)

        # 2. Handle Fillings
        if user:
            kwargs["text"] = (
                kwargs["text"]
                .replace("{first}", user.first_name)
                .replace("{first_name}", user.first_name)
                .replace("{name}", user.first_name)
                .replace("{last}", user.last_name or "")
                .replace("{last_name}", user.last_name or "")
                .replace("{fullname}", f"{user.first_name} {user.last_name or ''}".strip())
                .replace("{username}", f"@{user.username}" if user.username else user.first_name)
                .replace("{mention}", user.mention)
                .replace("{id}", str(user.id))
            )

        kwargs["text"] = (
            kwargs["text"]
            .replace("{chat}", chat_title)
            .replace("{chatname}", chat_title)
            .replace("{chat_name}", chat_title)
        )

        buttons: list[tuple[str, str, bool]] = []

        # Parse {rules} and {rules:same}
        if "{rules:same}" in kwargs["text"]:
            kwargs["text"] = kwargs["text"].replace("{rules:same}", "")
            buttons.append(
                ("Rules", f"https://t.me/{bot_username}?start=rules_{chat_id}", True, None)
            )
        elif "{rules}" in kwargs["text"]:
            kwargs["text"] = kwargs["text"].replace("{rules}", "")
            buttons.append(
                ("Rules", f"https://t.me/{bot_username}?start=rules_{chat_id}", False, None)
            )

        # 3. Parse Buttons via Regex
        # Matches [Text](buttonurl://link) or [Text](buttonurl#style://link:same)
        # Styles: primary, danger, success (maps to ButtonStyle enum)
        # Note buttons: [Text](buttonurl://#note_name:same)
        # Group 1: Text
        # Group 2: Optional style (primary|danger|success)
        # Group 3: URL (including #note_name optionally)
        # Group 4: Optional :same
        _style_map = {
            "primary": ButtonStyle.PRIMARY,
            "danger": ButtonStyle.DANGER,
            "success": ButtonStyle.SUCCESS,
        }
        btn_pattern = re.compile(
            r"\[([^\]]+)\]\(buttonurl(?:#(primary|danger|success))?:\/\/([^\)]+?)(?::(same))?\)"
        )

        for match in btn_pattern.finditer(kwargs["text"]):
            btn_text = match.group(1)
            btn_style_str = match.group(2)  # may be None
            btn_url = match.group(3)
            is_same = bool(match.group(4))
            btn_style = _style_map.get(btn_style_str) if btn_style_str else None

            # Handle deep link to note (includes chat_id so bot knows which chat to look up)
            if btn_url.startswith("#"):
                note_name = btn_url[1:]
                btn_url = f"https://t.me/{bot_username}?start=note_{chat_id}_{note_name}"
            # Ensure proper URL formatting
            elif (
                not btn_url.startswith("http://")
                and not btn_url.startswith("https://")
                and not btn_url.startswith("t.me")
            ):
                btn_url = f"http://{btn_url}"

            buttons.append((btn_text, btn_url, is_same, btn_style))

        # Remove matched buttons from text
        kwargs["text"] = btn_pattern.sub("", kwargs["text"]).strip()

        # Build Keyboard
        if buttons:
            keyboard = []
            for text_lbl, url, same, style in buttons:
                btn = InlineKeyboardButton(text_lbl, url=url, style=style)
                if same and keyboard:
                    keyboard[-1].append(btn)
                else:
                    keyboard.append([btn])
            kwargs["reply_markup"] = InlineKeyboardMarkup(keyboard)

        return kwargs

    @staticmethod
    async def send_parsed(
        client, chat_id: int, parsed: ParsedMessage, reply_to_message_id: int | None = None
    ) -> Any:
        reply_params = (
            ReplyParameters(message_id=reply_to_message_id) if reply_to_message_id else None
        )
        return await client.send_message(
            chat_id=chat_id,
            text=parsed["text"],
            reply_markup=parsed["reply_markup"],
            link_preview_options=parsed["link_preview_options"],
            disable_notification=parsed["disable_notification"],
            protect_content=parsed["protect_content"],
            reply_parameters=reply_params,
        )

    @staticmethod
    async def send_media_parsed(
        client,
        chat_id: int,
        response_type: str,
        file_id: str,
        parsed: ParsedMessage,
        reply_to_message_id: int | None = None,
    ) -> Any:
        """Send a media filter response (photo, video, document, etc) with caption + buttons."""
        reply_params = (
            ReplyParameters(message_id=reply_to_message_id) if reply_to_message_id else None
        )
        # Caption comes from parsed["text"]; buttons from parsed["reply_markup"]
        common = dict(
            chat_id=chat_id,
            caption=parsed["text"] or None,
            reply_markup=parsed["reply_markup"],
            disable_notification=parsed["disable_notification"],
            protect_content=parsed["protect_content"],
            reply_parameters=reply_params,
        )
        _DISPATCH: dict[str, Any] = {
            "photo": client.send_photo,
            "video": client.send_video,
            "document": client.send_document,
            "audio": client.send_audio,
            "voice": client.send_voice,
            "animation": client.send_animation,
            "sticker": client.send_sticker,
            "video_note": client.send_video_note,
        }
        sender = _DISPATCH.get(response_type)
        if sender is None:
            # Fall back to plain message if type is unknown
            return await TelegramFormatter.send_parsed(client, chat_id, parsed, reply_to_message_id)

        # Stickers and video notes do NOT support captions
        if response_type in ("sticker", "video_note"):
            common.pop("caption", None)

        return await sender(file_id, **common)
