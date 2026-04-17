import asyncio
import re
import time
from collections import defaultdict

from loguru import logger
from pyrogram import Client, filters
from pyrogram.enums import ChatAction, ParseMode
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.utils.decorators import safe_handler
from src.utils.formatters import TelegramFormatter
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input

from .repository import AIRepository
from .service import AIService
from .telegram_markdown import render_pyrogram_html

# Per-chat locks to prevent concurrent AI requests from hitting rate limits
ai_locks = defaultdict(asyncio.Lock)


def _compact_history(msgs, max_m, max_c):
    if not msgs:
        return []
    out, total = [], 0
    for m in reversed(msgs[-max_m:]):
        content = str(m.get("content", ""))
        if not content:
            continue
        if total + len(content) > max_c:
            if (rem := max_c - total) <= 80:
                break
            content = content[-rem:]
        out.append({"role": m.get("role", "user"), "content": content})
        if (total := total + len(content)) >= max_c:
            break
    return out[::-1]


def _is_request_too_large_error(err):
    e = str(err).lower()
    return any(x in e for x in ("request_too_large", "413", "entity too large"))


def _trim_text(v, max_c):
    return v.strip()[-max_c:] if v and len(v.strip()) > max_c else (v.strip() if v else v)


@bot.on_message(filters.group & ~filters.service & ~filters.bot, group=100)
@safe_handler
async def ai_message_handler(client: Client, message: Message):
    cid = message.chat.id
    uid = message.from_user.id if message.from_user else 0
    text = message.text or message.caption
    if not client.me or not text or text.startswith("/"):
        return

    ctx = get_context()
    await AIRepository.add_message(
        ctx,
        cid,
        message.id,
        uid,
        message.from_user.first_name if message.from_user else "Unknown",
        text,
    )
    s = await AIRepository.get_settings(ctx, cid)
    if not s or not s.isAssistantEnabled or not s.apiKey:
        return

    me_tag = f"@{client.me.username}".lower()
    if not (
        me_tag in text.lower()
        or (
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.id == client.me.id
        )
    ):
        return

    from .prompts import BASE_PROMPT, OPERATIONAL_RULES

    pvd = (s.provider or "openai").lower()
    lim = {"m": 12, "c": 5000} if pvd == "groq" else {"m": 24, "c": 12000}

    try:
        async with ai_locks[cid]:
            # Mandatory delay to prevent hitting provider rate limits (e.g. Groq)
            await asyncio.sleep(2.0)

            await client.send_chat_action(cid, ChatAction.TYPING)
            sys_p = (s.systemPrompt or BASE_PROMPT).format(
                bot_name=client.me.first_name, bot_username=client.me.username
            )
        sys_p = f"IDENTITY: You are @{client.me.username} ({client.me.first_name})\n\n{sys_p}"
        if s.systemPrompt:
            sys_p += OPERATIONAL_RULES

        async def _call(m_l, c_l):
            hist = _compact_history(
                await AIRepository.get_context(ctx, cid, client.me.id), m_l, c_l
            )
            st = time.time()
            res = await AIService.call_ai(
                s.provider,
                s.apiKey,
                s.modelId or "gpt-3.5-turbo",
                _trim_text(sys_p, 3200),
                _trim_text(s.customInstruction, 900),
                hist,
            )
            return res, time.time() - st

        try:
            resp, dur = await _call(lim["m"], lim["c"])
        except Exception as e:
            if not _is_request_too_large_error(e):
                raise
            resp, dur = await _call(8, 3000)

        if resp:
            full = resp.strip()
            sent = await TelegramFormatter.send_safe(
                client,
                cid,
                render_pyrogram_html(full),
                reply_to_message_id=message.id,
                parse_mode=ParseMode.HTML,
            )
            if sent:
                await AIRepository.add_message(
                    ctx, cid, sent[0].id, client.me.id, client.me.first_name, full
                )
    except Exception as e:
        logger.debug(f"AI Fail {cid}: {e}")
        err = await at(cid, "ai.error_prefix", error=str(e))
        if "rate_limit" in str(e).lower():
            w = (
                re.search(r"in ([\d\.]+)s", str(e)).group(1)
                if re.search(r"in ([\d\.]+)s", str(e))
                else await at(cid, "ai.few")
            )
            err = (await at(cid, "ai.rate_limit", seconds=f"{await at(cid, 'ai.latency_fmt_short', duration=w)}"))
        elif _is_request_too_large_error(e):
            await AIRepository.clear_context(ctx, cid)
            err = await at(cid, "ai.error_entity_too_large")
        import contextlib

        with contextlib.suppress(Exception):
            await message.reply_text(err)


AI_FIELDS = ["aiApiKey", "aiModelId", "aiSystemPrompt", "aiInstruction"]


@bot.on_message(filters.private & is_waiting_for_input(AI_FIELDS), group=-50)
@safe_handler
async def ai_settings_handler(client: Client, message: Message):
    st = message.input_state
    cid, fld, uid = st["chat_id"], st["field"], message.from_user.id
    ctx, val = get_context(), (message.text or "").strip()
    if not val:
        return await message.reply(await at(uid, "panel.input_invalid_string"))

    mapping = {
        "aiApiKey": "apiKey",
        "aiModelId": "modelId",
        "aiSystemPrompt": "systemPrompt",
        "aiInstruction": "customInstruction",
    }
    await AIRepository.update_settings(ctx, cid, **{mapping.get(fld, fld): val})

    from src.plugins.admin_panel.handlers.ai_kbs import ai_menu_kb

    kb = await ai_menu_kb(cid, user_id=uid)
    s = await AIRepository.get_settings(ctx, cid)
    is_e, pvd, mod = (
        (s.isAssistantEnabled if s else False),
        (s.provider if s else "openai").upper(),
        (s.modelId if s else "N/A") or "N/A",
    )
    ake = "****" if (s and s.apiKey) else await at(uid, "panel.not_set")

    txt = await at(
        uid,
        "panel.ai_text",
        status=await at(uid, f"panel.status_{'enabled' if is_e else 'disabled'}"),
        provider=pvd,
        model=mod,
        api_key=ake,
    )
    ok = await at(uid, "panel.input_success")
    if fld == "aiModelId":
        ok = await at(uid, "panel.ai_model_set", model=mod)
    await finalize_input_capture(
        client, message, uid, st["prompt_msg_id"], txt, kb, success_text=ok
    )
