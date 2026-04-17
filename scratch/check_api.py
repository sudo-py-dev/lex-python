import asyncio

from hebcal_api import ShabbatRequest


async def main():
    try:
        req = ShabbatRequest(geonameid=281184)  # Jerusalem
        print("Model fields:", req.model_fields.keys())
    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    asyncio.run(main())
