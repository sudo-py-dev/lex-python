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

from src.utils.text import smart_split


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

        res: ParsedMessage = {
            "text": text,
            "reply_markup": None,
            "link_preview_options": LinkPreviewOptions(is_disabled=True),
            "disable_notification": False,
            "protect_content": False,
            "has_media_spoiler": False,
        }

        tags = {
            "{nonotif}": "disable_notification",
            "{protect}": "protect_content",
            "{mediaspoiler}": "has_media_spoiler",
        }
        for tag, key in tags.items():
            if tag in res["text"]:
                res[key] = True
                res["text"] = res["text"].replace(tag, "")

        if "{preview:top}" in res["text"]:
            res["link_preview_options"], res["text"] = (
                LinkPreviewOptions(is_disabled=False, show_above_text=True),
                res["text"].replace("{preview:top}", ""),
            )
        elif "{preview}" in res["text"]:
            res["link_preview_options"], res["text"] = (
                LinkPreviewOptions(is_disabled=False),
                res["text"].replace("{preview}", ""),
            )

        if user:
            replaces = {
                "{first}": user.first_name,
                "{first_name}": user.first_name,
                "{name}": user.first_name,
                "{last}": user.last_name or "",
                "{last_name}": user.last_name or "",
                "{fullname}": f"{user.first_name} {user.last_name or ''}".strip(),
                "{username}": f"@{user.username}" if user.username else user.first_name,
                "{mention}": user.mention,
                "{id}": str(user.id),
            }
            for k, v in replaces.items():
                res["text"] = res["text"].replace(k, v)

        for tag in ("{chat}", "{chatname}", "{chat_name}"):
            res["text"] = res["text"].replace(tag, chat_title)

        btns: list[tuple] = []
        if "{rules:same}" in res["text"]:
            res["text"] = res["text"].replace("{rules:same}", "")
            btns.append(("Rules", f"https://t.me/{bot_username}?start=rules_{chat_id}", True, None))
        elif "{rules}" in res["text"]:
            res["text"] = res["text"].replace("{rules}", "")
            btns.append(
                ("Rules", f"https://t.me/{bot_username}?start=rules_{chat_id}", False, None)
            )

        style_map = {
            "primary": ButtonStyle.PRIMARY,
            "danger": ButtonStyle.DANGER,
            "success": ButtonStyle.SUCCESS,
        }
        btn_re = re.compile(
            r"\[([^\]]+)\]\(buttonurl(?:#(primary|danger|success))?:\/\/([^\)]+?)(?::(same))?\)"
        )

        for m in btn_re.finditer(res["text"]):
            lbl, style_str, url, same = m.groups()
            style = style_map.get(style_str) if style_str else None
            if url.startswith("#"):
                url = f"https://t.me/{bot_username}?start=note_{chat_id}_{url[1:]}"
            elif not any(url.startswith(x) for x in ("http://", "https://", "t.me")):
                url = f"http://{url}"
            btns.append((lbl, url, bool(same), style))

        res["text"] = btn_re.sub("", res["text"]).strip()
        if btns:
            kb = []
            for lbl, url, same, style in btns:
                btn = InlineKeyboardButton(lbl, url=url, style=style)
                if same and kb:
                    kb[-1].append(btn)
                else:
                    kb.append([btn])
            res["reply_markup"] = InlineKeyboardMarkup(kb)

        return res

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
        reply_params = (
            ReplyParameters(message_id=reply_to_message_id) if reply_to_message_id else None
        )
        common = dict(
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
            return await TelegramFormatter.send_parsed(client, chat_id, parsed, reply_to_message_id)

        if response_type in ("sticker", "video_note"):
            common.pop("caption", None)

        return await sender(chat_id, file_id, **common)

    @staticmethod
    async def send_safe(
        client,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
        parse_mode: Any = "html",
        **kwargs,
    ) -> list[Any]:
        """
        Sends text safely, splitting it if it exceeds Telegram limits.
        """
        chunks = smart_split(text)
        sent_messages = []
        reply_params = (
            ReplyParameters(message_id=reply_to_message_id) if reply_to_message_id else None
        )

        for i, chunk in enumerate(chunks):
            # Only the first message is a reply to the original
            params = reply_params if i == 0 else None
            msg = await client.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode=parse_mode,
                reply_parameters=params,
                **kwargs,
            )
            sent_messages.append(msg)
        return sent_messages
