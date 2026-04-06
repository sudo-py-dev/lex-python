import pytest
from sqlalchemy import select

from src.db.models import AIChatContext, AISettings
from tests.factories import AIChatContextFactory, AISettingsFactory, GroupSettingsFactory


@pytest.mark.asyncio
async def test_aisettings_creation(db_session):
    # GroupSettings must exist for AISettings as it uses its ID as PK and FK
    gs = GroupSettingsFactory.build(id=-100)
    db_session.add(gs)
    await db_session.flush()

    ai_settings = AISettingsFactory.build(chatId=-100, provider="gemini")
    db_session.add(ai_settings)
    await db_session.flush()

    result = await db_session.execute(select(AISettings).where(AISettings.chatId == -100))
    fetched = result.scalar_one()
    assert fetched.provider == "gemini"


@pytest.mark.asyncio
async def test_aichatcontext_creation(db_session):
    gs = GroupSettingsFactory.build(id=-200)
    db_session.add(gs)
    await db_session.flush()

    ctx = AIChatContextFactory.build(chatId=-200, text="how are you?")
    db_session.add(ctx)
    await db_session.flush()

    result = await db_session.execute(select(AIChatContext).where(AIChatContext.chatId == -200))
    fetched = result.scalar_one()
    assert fetched.text == "how are you?"
