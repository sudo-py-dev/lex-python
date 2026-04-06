import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.db.models import (
    Approval,
    Blacklist,
    BlockedEntity,
    BlockedLanguage,
    ChannelProtect,
    GlobalBan,
    ReportSetting,
    SlowmodeSetting,
    UserWarn,
)
from tests.factories import (
    ApprovalFactory,
    BlacklistFactory,
    BlockedEntityFactory,
    BlockedLanguageFactory,
    ChannelProtectFactory,
    GlobalBanFactory,
    GroupSettingsFactory,
    ReportSettingFactory,
    SlowmodeSettingFactory,
    UserWarnFactory,
)


@pytest.mark.asyncio
async def test_blacklist_creation(db_session):
    gs = GroupSettingsFactory.build(id=-100)
    db_session.add(gs)
    await db_session.flush()

    bl = BlacklistFactory.build(chatId=-100, pattern="badword")
    db_session.add(bl)
    await db_session.flush()

    result = await db_session.execute(select(Blacklist).where(Blacklist.chatId == -100))
    fetched = result.scalar_one()
    assert fetched.pattern == "badword"
    assert fetched.chatId == -100


@pytest.mark.asyncio
async def test_blacklist_fk_violation(db_session):
    bl = BlacklistFactory.build(chatId=999)  # Group id 999 doesn't exist
    db_session.add(bl)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_blockedentity_creation(db_session):
    gs = GroupSettingsFactory.build(id=-200)
    db_session.add(gs)
    await db_session.flush()

    be = BlockedEntityFactory.build(chatId=-200, entityType="url")
    db_session.add(be)
    await db_session.flush()

    result = await db_session.execute(select(BlockedEntity).where(BlockedEntity.chatId == -200))
    fetched = result.scalar_one()
    assert fetched.entityType == "url"


@pytest.mark.asyncio
async def test_blockedlanguage_creation(db_session):
    gs = GroupSettingsFactory.build(id=-300)
    db_session.add(gs)
    await db_session.flush()

    bl = BlockedLanguageFactory.build(chatId=-300, langCode="fa")
    db_session.add(bl)
    await db_session.flush()

    result = await db_session.execute(select(BlockedLanguage).where(BlockedLanguage.chatId == -300))
    fetched = result.scalar_one()
    assert fetched.langCode == "fa"


@pytest.mark.asyncio
async def test_userwarn_creation(db_session):
    gs = GroupSettingsFactory.build(id=-400)
    db_session.add(gs)
    await db_session.flush()

    warn = UserWarnFactory.build(chatId=-400, userId=123, reason="toxic")
    db_session.add(warn)
    await db_session.flush()

    result = await db_session.execute(select(UserWarn).where(UserWarn.chatId == -400))
    fetched = result.scalar_one()
    assert fetched.userId == 123
    assert fetched.reason == "toxic"


@pytest.mark.asyncio
async def test_userwarn_fk_violation(db_session):
    warn = UserWarnFactory.build(chatId=999)  # Group id 999 doesn't exist
    db_session.add(warn)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_globalban_creation(db_session):
    gb = GlobalBanFactory.build(userId=999, reason="spammer")
    db_session.add(gb)
    await db_session.flush()

    result = await db_session.execute(select(GlobalBan).where(GlobalBan.userId == 999))
    fetched = result.scalar_one()
    assert fetched.reason == "spammer"


@pytest.mark.asyncio
async def test_globalban_unique_violation(db_session):
    gb1 = GlobalBanFactory.build(userId=100)
    db_session.add(gb1)
    await db_session.flush()

    gb2 = GlobalBanFactory.build(userId=100)
    db_session.add(gb2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_channelprotect_creation(db_session):
    cp = ChannelProtectFactory.build(chatId=-500, antiChannel=True)
    db_session.add(cp)
    await db_session.flush()

    result = await db_session.execute(select(ChannelProtect).where(ChannelProtect.chatId == -500))
    fetched = result.scalar_one()
    assert fetched.antiChannel is True


@pytest.mark.asyncio
async def test_slowmodesetting_creation(db_session):
    sm = SlowmodeSettingFactory.build(chatId=-700, interval=30)
    db_session.add(sm)
    await db_session.flush()

    result = await db_session.execute(select(SlowmodeSetting).where(SlowmodeSetting.chatId == -700))
    fetched = result.scalar_one()
    assert fetched.interval == 30


@pytest.mark.asyncio
async def test_reportsetting_creation(db_session):
    rs = ReportSettingFactory.build(chatId=-800, enabled=False)
    db_session.add(rs)
    await db_session.flush()

    result = await db_session.execute(select(ReportSetting).where(ReportSetting.chatId == -800))
    fetched = result.scalar_one()
    assert fetched.enabled is False


@pytest.mark.asyncio
async def test_approval_creation(db_session):
    app = ApprovalFactory.build(chatId=-900, userId=111)
    db_session.add(app)
    await db_session.flush()

    result = await db_session.execute(select(Approval).where(Approval.chatId == -900))
    fetched = result.scalar_one()
    assert fetched.userId == 111
