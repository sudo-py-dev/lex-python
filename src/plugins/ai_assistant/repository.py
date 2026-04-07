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
            settings = await session.get(AISettings, chat_id)
            if not settings:
                settings = AISettings(chatId=chat_id)
                session.add(settings)

            for key, value in kwargs.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)

            await session.commit()
            await session.refresh(settings)
            return settings

    @staticmethod
    async def add_message(
        ctx: AppContext, chat_id: int, message_id: int, user_id: int, user_name: str, text: str
    ) -> None:
        async with ctx.db() as session:
            new_msg = AIChatContext(
                chatId=chat_id,
                messageId=message_id,
                userId=user_id,
                userName=user_name,
                text=text,
                timestamp=datetime.now(UTC),
            )
            session.add(new_msg)

            stmt = (
                select(AIChatContext)
                .where(AIChatContext.chatId == chat_id)
                .order_by(AIChatContext.timestamp.desc())
                .offset(50)
            )
            result = await session.execute(stmt)
            to_delete = result.scalars().all()
            for msg in to_delete:
                await session.delete(msg)

            await session.commit()

    @staticmethod
    async def get_context(ctx: AppContext, chat_id: int, bot_id: int) -> list[dict[str, str]]:
        async with ctx.db() as session:
            stmt = (
                select(AIChatContext)
                .where(AIChatContext.chatId == chat_id)
                .order_by(AIChatContext.timestamp.desc())
                .limit(AIRepository._CONTEXT_DB_LIMIT)
            )
            result = await session.execute(stmt)
            msgs = result.scalars().all()

            ai_messages = []
            budget = AIRepository._CONTEXT_TOTAL_CHAR_BUDGET
            current_chars = 0

            for m in msgs:
                role = "assistant" if m.userId == bot_id else "user"
                content = m.text if role == "assistant" else f"[{m.userName}]: {m.text}"
                msg_max = (
                    AIRepository._CONTEXT_ASSISTANT_MSG_MAX_CHARS
                    if role == "assistant"
                    else AIRepository._CONTEXT_USER_MSG_MAX_CHARS
                )
                if len(content) > msg_max:
                    content = content[:msg_max] + "..."

                if current_chars + len(content) > budget:
                    remaining = budget - current_chars
                    if remaining > 100:
                        content = content[:remaining] + "..."
                        ai_messages.append({"role": role, "content": content})
                    break

                ai_messages.append({"role": role, "content": content})
                current_chars += len(content)

            return ai_messages[::-1]

    @staticmethod
    async def clear_context(ctx: AppContext, chat_id: int) -> None:
        async with ctx.db() as session:
            stmt = delete(AIChatContext).where(AIChatContext.chatId == chat_id)
            await session.execute(stmt)
            await session.commit()
