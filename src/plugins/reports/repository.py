from src.core.context import AppContext
from src.db.models import ReportSetting


async def set_report_enabled(ctx: AppContext, chat_id: int, enabled: bool) -> ReportSetting:
    async with ctx.db() as session:
        obj = await session.get(ReportSetting, chat_id)
        if obj:
            obj.enabled = enabled
            session.add(obj)
        else:
            obj = ReportSetting(chatId=chat_id, enabled=enabled)
            session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj


async def is_report_enabled(ctx: AppContext, chat_id: int) -> bool:
    async with ctx.db() as session:
        setting = await session.get(ReportSetting, chat_id)
        return setting.enabled if setting else True
