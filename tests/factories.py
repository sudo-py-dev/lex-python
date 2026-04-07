import uuid
from datetime import UTC, datetime

import factory

from src.db.models import (
    ActionLog,
    AIChatContext,
    AISettings,
    AllowedChannel,
    Approval,
    Blacklist,
    BlockedEntity,
    BlockedLanguage,
    ChannelProtect,
    ChatCleaner,
    DisabledCommand,
    FedAdmin,
    FedBan,
    FedChat,
    Federation,
    FedSubscription,
    Filter,
    GlobalBan,
    ChatNightLock,
    ChatRules,
    ChatSettings,
    Note,
    Reminder,
    ReportSetting,
    ScheduledMessage,
    SlowmodeSetting,
    SudoUser,
    TimedAction,
    UserConnection,
    UserWarn,
)


class SudoUserFactory(factory.Factory):
    class Meta:
        model = SudoUser

    userId = factory.Sequence(lambda n: 1000 + n)
    addedBy = 99999
    createdAt = factory.LazyFunction(lambda: datetime.now(UTC))


class UserConnectionFactory(factory.Factory):
    class Meta:
        model = UserConnection

    userId = factory.Sequence(lambda n: 2000 + n)
    activeChatId = factory.Sequence(lambda n: -100 - n)


class ActionLogFactory(factory.Factory):
    class Meta:
        model = ActionLog

    chatId = factory.Sequence(lambda n: -100 - n)
    actorId = factory.Sequence(lambda n: 3000 + n)
    targetId = factory.Sequence(lambda n: 4000 + n)
    action = "ban"
    reason = "test reason"
    createdAt = factory.LazyFunction(lambda: datetime.now(UTC))


class TimedActionFactory(factory.Factory):
    class Meta:
        model = TimedAction

    chatId = factory.Sequence(lambda n: -100 - n)
    userId = factory.Sequence(lambda n: 5000 + n)
    action = "mute"
    expiresAt = factory.LazyFunction(lambda: datetime.now(UTC))


class ChatSettingsFactory(factory.Factory):
    class Meta:
        model = ChatSettings

    id = factory.Sequence(lambda n: -100 - n)
    floodThreshold = 5
    floodWindow = 10
    floodAction = "mute"
    raidEnabled = False
    language = "en"
    isActive = True


class ChatRulesFactory(factory.Factory):
    class Meta:
        model = ChatRules

    chatId = factory.Sequence(lambda n: -100 - n)
    content = "Test rules"
    privateMode = False


class ChatCleanerFactory(factory.Factory):
    class Meta:
        model = ChatCleaner

    chatId = factory.Sequence(lambda n: -100 - n)
    cleanDeleted = False
    cleanFake = False
    cleanInactiveDays = 0


class ChatNightLockFactory(factory.Factory):
    class Meta:
        model = ChatNightLock

    chatId = factory.Sequence(lambda n: -100 - n)
    isEnabled = False
    startTime = "23:00"
    endTime = "07:00"


class AllowedChannelFactory(factory.Factory):
    class Meta:
        model = AllowedChannel

    chatId = factory.Sequence(lambda n: -100 - n)
    channelId = factory.Sequence(lambda n: 6000 + n)


class DisabledCommandFactory(factory.Factory):
    class Meta:
        model = DisabledCommand

    chatId = factory.Sequence(lambda n: -100 - n)
    command = "testcmd"


class BlacklistFactory(factory.Factory):
    class Meta:
        model = Blacklist

    chatId = factory.Sequence(lambda n: -100 - n)
    pattern = "spam.*"
    isRegex = True
    action = "delete"


class BlockedEntityFactory(factory.Factory):
    class Meta:
        model = BlockedEntity

    chatId = factory.Sequence(lambda n: -100 - n)
    entityType = "url"
    action = "delete"


class BlockedLanguageFactory(factory.Factory):
    class Meta:
        model = BlockedLanguage

    chatId = factory.Sequence(lambda n: -100 - n)
    langCode = "fa"
    action = "delete"


class UserWarnFactory(factory.Factory):
    class Meta:
        model = UserWarn

    chatId = factory.Sequence(lambda n: -100 - n)
    userId = factory.Sequence(lambda n: 7000 + n)
    reason = "Test warn"
    actorId = 99999


class GlobalBanFactory(factory.Factory):
    class Meta:
        model = GlobalBan

    userId = factory.Sequence(lambda n: 8000 + n)
    reason = "Global spammer"
    bannedBy = 99999


class ChannelProtectFactory(factory.Factory):
    class Meta:
        model = ChannelProtect

    chatId = factory.Sequence(lambda n: -100 - n)
    antiChannel = True
    antiAnon = False


class SlowmodeSettingFactory(factory.Factory):
    class Meta:
        model = SlowmodeSetting

    chatId = factory.Sequence(lambda n: -100 - n)
    interval = 10


class ReportSettingFactory(factory.Factory):
    class Meta:
        model = ReportSetting

    chatId = factory.Sequence(lambda n: -100 - n)
    enabled = True


class ApprovalFactory(factory.Factory):
    class Meta:
        model = Approval

    chatId = factory.Sequence(lambda n: -100 - n)
    userId = factory.Sequence(lambda n: 9000 + n)
    grantedBy = 99999


class FilterFactory(factory.Factory):
    class Meta:
        model = Filter

    chatId = factory.Sequence(lambda n: -100 - n)
    keyword = "test"
    responseData = "test response"


class NoteFactory(factory.Factory):
    class Meta:
        model = Note

    chatId = factory.Sequence(lambda n: -100 - n)
    name = "testnote"
    content = "test content"


class ReminderFactory(factory.Factory):
    class Meta:
        model = Reminder

    chatId = factory.Sequence(lambda n: -100 - n)
    text = "remind me"
    sendTime = "12:00"


class ScheduledMessageFactory(factory.Factory):
    class Meta:
        model = ScheduledMessage

    chatId = factory.Sequence(lambda n: -100 - n)
    content = "scheduled"
    jobId = factory.Sequence(lambda n: f"job_{n}")
    createdBy = 99999


class AISettingsFactory(factory.Factory):
    class Meta:
        model = AISettings

    chatId = factory.Sequence(lambda n: -100 - n)
    provider = "openai"
    isEnabled = True


class AIChatContextFactory(factory.Factory):
    class Meta:
        model = AIChatContext

    chatId = factory.Sequence(lambda n: -100 - n)
    messageId = factory.Sequence(lambda n: 1000 + n)
    userId = factory.Sequence(lambda n: 2000 + n)
    text = "hello"


class FederationFactory(factory.Factory):
    class Meta:
        model = Federation

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name = "Test Fed"
    ownerId = 99999


class FedChatFactory(factory.Factory):
    class Meta:
        model = FedChat

    fedId = factory.SubFactory(FederationFactory)
    chatId = factory.Sequence(lambda n: -100 - n)


class FedAdminFactory(factory.Factory):
    class Meta:
        model = FedAdmin

    fedId = factory.SubFactory(FederationFactory)
    userId = factory.Sequence(lambda n: 3000 + n)


class FedBanFactory(factory.Factory):
    class Meta:
        model = FedBan

    fedId = factory.SubFactory(FederationFactory)
    userId = factory.Sequence(lambda n: 4000 + n)
    reason = "Fed ban reason"
    bannedBy = 99999


class FedSubscriptionFactory(factory.Factory):
    class Meta:
        model = FedSubscription

    subscriberId = factory.SubFactory(FederationFactory)
    publisherId = factory.SubFactory(FederationFactory)


class ChannelSettingsFactory(factory.Factory):
    class Meta:
        model = ChatSettings

    id = factory.Sequence(lambda n: -200 - n)
    reactionsEnabled = False
    reactions = "👍 ❤️ 🔥"
    reactionMode = "all"
    watermarkEnabled = False
    watermarkText = None
    signatureEnabled = False
    signatureText = None
