"""
Google Safe Browsing URL scanner for phishing and malware detection.
"""

from urllib.parse import urlparse

import httpx
from loguru import logger

from src.utils.i18n import t


async def is_url_malicious(urls: list[str], api_key: str, lang: str = "en") -> str | None:
    """
    Check if URLs are malicious using Google Safe Browsing API.
    Returns the localized threat type if found, else None.
    """
    if not urls or not isinstance(urls, list):
        return None

    exclude_tg_urls = ("t.me", "telegram.me", "telegram.dog", "telegra.ph")
    filtered_urls = [
        {"url": url}
        for url in urls
        if urlparse(url).netloc.lower() not in exclude_tg_urls
        and urlparse(url).scheme in ("http", "https")
    ]

    if not filtered_urls:
        return None

    endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}"
    payload = {
        "client": {"clientId": "lex-tg", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": [
                "MALWARE",
                "SOCIAL_ENGINEERING",
                "UNWANTED_SOFTWARE",
                "POTENTIALLY_HARMFUL_APPLICATION",
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": filtered_urls,
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(endpoint, json=payload, timeout=10.0)
            if response.status_code != 200:
                logger.error(f"Safe Browsing API error: {response.status_code} - {response.text}")
                return None

            result = response.json()
            if result.get("matches"):
                match = result["matches"][0]
                threat_type = match.get("threatType")
                return t(lang, f"threat_types.{threat_type}")

            return None

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Request failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in URL scanner: {e}")

    return None
