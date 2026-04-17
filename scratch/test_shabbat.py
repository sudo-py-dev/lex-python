import asyncio

from hebcal_api import ShabbatRequest, fetch_shabbat_async


async def main():
    # Test for Jerusalem
    req = ShabbatRequest(tzid="Asia/Jerusalem")
    res = await fetch_shabbat_async(req)

    print(f"Location: {res.location.city if res.location else 'Unknown'}")
    for item in res.items:
        print(f"Event: {item.title} | Category: {item.category} | Date: {item.date}")


if __name__ == "__main__":
    asyncio.run(main())
