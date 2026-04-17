import asyncio
from datetime import datetime

from src.utils.hebcal import get_shabbat_events, is_shabbat_now


async def live_test():
    cities = [
        "Asia/Jerusalem",
        "America/New_York",
        "Europe/London",
        "Europe/Paris",
        "Asia/Tokyo",
        "Australia/Sydney",
        "UTC",
    ]

    print(f"--- Live Test: {datetime.now()} (UTC) ---")
    print(f"{'Timezone':<20} | {'Start':<25} | {'End':<25} | {'Active?':<8}")
    print("-" * 88)

    for tzid in cities:
        try:
            start, end, h_flag = await get_shabbat_events(tzid)
            active = await is_shabbat_now(tzid)

            s_str = start.strftime("%Y-%m-%d %H:%M %Z") if start else "N/A"
            e_str = end.strftime("%Y-%m-%d %H:%M %Z") if end else "N/A"
            h_str = " (Holiday)" if h_flag else ""

            print(f"{tzid:<20} | {s_str:<25} | {e_str:<25} | {str(active) + h_str:<8}")
        except Exception as e:
            print(f"{tzid:<20} | ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(live_test())
