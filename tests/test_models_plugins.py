import pytest
from sqlalchemy import select

from src.db.models import Filter, Note, Reminder, ScheduledMessage
from tests.factories import (
    FilterFactory,
    GroupSettingsFactory,
    NoteFactory,
    ReminderFactory,
    ScheduledMessageFactory,
)


@pytest.mark.asyncio
async def test_filter_creation(db_session):
    gs = GroupSettingsFactory.build(id=-100)
    db_session.add(gs)
    await db_session.flush()
    
    f = FilterFactory.build(chatId=-100, keyword="hello", responseData="hi there")
    db_session.add(f)
    await db_session.flush()
    
    result = await db_session.execute(select(Filter).where(Filter.chatId == -100))
    fetched = result.scalar_one()
    assert fetched.keyword == "hello"

@pytest.mark.asyncio
async def test_note_creation(db_session):
    gs = GroupSettingsFactory.build(id=-200)
    db_session.add(gs)
    await db_session.flush()
    
    n = NoteFactory.build(chatId=-200, name="rules", content="follow them")
    db_session.add(n)
    await db_session.flush()
    
    result = await db_session.execute(select(Note).where(Note.chatId == -200))
    fetched = result.scalar_one()
    assert fetched.name == "rules"

@pytest.mark.asyncio
async def test_reminder_creation(db_session):
    gs = GroupSettingsFactory.build(id=-300)
    db_session.add(gs)
    await db_session.flush()
    
    r = ReminderFactory.build(chatId=-300, text="clean up", sendTime="08:00")
    db_session.add(r)
    await db_session.flush()
    
    result = await db_session.execute(select(Reminder).where(Reminder.chatId == -300))
    fetched = result.scalar_one()
    assert fetched.text == "clean up"

@pytest.mark.asyncio
async def test_scheduledmessage_creation(db_session):
    # ScheduledMessage does not have a FK to GroupSettings in its definition
    sm = ScheduledMessageFactory.build(chatId=-400, content="scheduled hi")
    db_session.add(sm)
    await db_session.flush()
    
    result = await db_session.execute(select(ScheduledMessage).where(ScheduledMessage.chatId == -400))
    fetched = result.scalar_one()
    assert fetched.content == "scheduled hi"
