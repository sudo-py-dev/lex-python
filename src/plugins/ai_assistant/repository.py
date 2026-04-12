from datetime import UTC, datetime

from sqlalchemy import delete, select

from src.core.context import AppContext
from src.db.models.ai import AIChatContext, AISettings


class AIRepository:
    _CONTEXT_DB_LIMIT = 40
    _CONTEXT_TOTAL_CHAR_BUDGET = 9000
    _CONTEXT_USER_MSG_MAX_CHARS = 900
    _CONTEXT_ASSISTANT_MSG_MAX_CHARS = 1200

    @staticmethod
    async def get_settings(ctx: AppContext, chat_id: int) -> AISettings | None:
        async with ctx.db() as session:
            return await session.get(AISettings, chat_id)

    @staticmethod
    async def update_settings(ctx: AppContext, chat_id: int, **kwargs) -> AISettings:
        async with ctx.db() as session:
            s = await session.get(AISettings, chat_id)
            if not s:
                s = AISettings(chatId=chat_id)
                session.add(s)
            for k, v in kwargs.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            await session.commit()
            await session.refresh(s)
            return s

    @staticmethod
    async def add_message(
        ctx: AppContext, chat_id: int, msg_id: int, user_id: int, name: str, text: str
    ) -> None:
        async with ctx.db() as session:
            session.add(
                AIChatContext(
                    chatId=chat_id,
                    messageId=msg_id,
                    userId=user_id,
                    userName=name,
                    text=text,
                    timestamp=datetime.now(UTC),
                )
            )
            # Keep history under limit via subquery delete
            subq = (
                select(AIChatContext.id)
                .where(AIChatContext.chatId == chat_id)
                .order_by(AIChatContext.timestamp.desc())
                .offset(50)
                .scalar_subquery()
            )
            await session.execute(delete(AIChatContext).where(AIChatContext.id.in_(subq)))
            await session.commit()

    @staticmethod
    async def get_context(ctx: AppContext, chat_id: int, bot_id: int) -> list[dict[str, str]]:
        async with ctx.db() as session:
            res = await session.execute(
                select(AIChatContext)
                .where(AIChatContext.chatId == chat_id)
                .order_by(AIChatContext.timestamp.desc())
                .limit(AIRepository._CONTEXT_DB_LIMIT)
            )
            msgs = res.scalars().all()

            ctx_list, cur_chars = [], 0
            for m in msgs:
                role = "assistant" if m.userId == bot_id else "user"
                txt = m.text if role == "assistant" else f"[{m.userName}]: {m.text}"
                limit = (
                    AIRepository._CONTEXT_ASSISTANT_MSG_MAX_CHARS
                    if role == "assistant"
                    else AIRepository._CONTEXT_USER_MSG_MAX_CHARS
                )

                if len(txt) > limit:
                    txt = txt[:limit] + "..."
                if cur_chars + len(txt) > AIRepository._CONTEXT_TOTAL_CHAR_BUDGET:
                    rem = AIRepository._CONTEXT_TOTAL_CHAR_BUDGET - cur_chars
                    if rem > 100:
                        ctx_list.append({"role": role, "content": txt[:rem] + "..."})
                    break

                ctx_list.append({"role": role, "content": txt})
                cur_chars += len(txt)
            return ctx_list[::-1]

    @staticmethod
    async def clear_context(ctx: AppContext, chat_id: int) -> None:
        async with ctx.db() as session:
            await session.execute(delete(AIChatContext).where(AIChatContext.chatId == chat_id))
            await session.commit()
