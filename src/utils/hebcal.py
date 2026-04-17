from datetime import datetime
from zoneinfo import ZoneInfo

from hebcal_api import ShabbatRequest, fetch_shabbat_async
from hebcal_api.utils.types import EventType


async def get_shabbat_events(
    tzid: str,
) -> tuple[datetime | None, datetime | None, bool]:
    """
    Fetches the Shabbat/Holiday entrance and exit times relevant to the current time.
    Returns (start_time, end_time, is_holiday).
    """
    try:
        city = tzid.split("/")[-1].replace("_", " ") if "/" in tzid else tzid
        request = ShabbatRequest(city=city, tzid=tzid, c="on", s="on")
        response = await fetch_shabbat_async(request)
    except Exception:
        # Fallback to Jerusalem if the provided city/timezone is invalid
        try:
            tzid = "Asia/Jerusalem"
            request = ShabbatRequest(city="Jerusalem", tzid=tzid, c="on", s="on")
            response = await fetch_shabbat_async(request)
        except Exception:
            return None, None, False

    target_tz = ZoneInfo(tzid)
    now = datetime.now(target_tz)

    start_time: datetime | None = None
    end_time: datetime | None = None
    is_holiday = False

    for item in response.items:
        if item.type == EventType.HAVDALAH and item.date > now:
            end_time = item.date
            break

    if not end_time:
        return None, None, False

    for item in response.items:
        if item.type == EventType.CANDLES and item.date < end_time:
            start_time = item.date
            if item.holiday and item.holiday.yomtov:
                is_holiday = True

    return start_time, end_time, is_holiday


async def is_shabbat_now(tzid: str) -> bool:
    """Checks if it is currently Shabbat or a Holiday in the given timezone."""
    start, end, _ = await get_shabbat_events(tzid)
    if not start or not end:
        return False

    try:
        target_tz = ZoneInfo(tzid)
    except Exception:
        # Fallback to Jerusalem if tzid is invalid
        target_tz = ZoneInfo("Asia/Jerusalem")

    now = datetime.now(target_tz)
    return start <= now <= end
