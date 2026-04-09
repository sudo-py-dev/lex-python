from src.config import TECH_STACK, config
from src.utils.i18n import at


async def get_about_text(chat_id: int | None) -> str:
    """
    Generate the standardized 'About' text for the bot.

    Args:
        chat_id (int | None): The chat ID for localization.

    Returns:
        str: The formatted about text including tech stack and version.
    """
    labels = {
        "engine": await at(chat_id, "misc.tech_engine"),
        "database": await at(chat_id, "misc.tech_database"),
        "framework": await at(chat_id, "misc.tech_framework"),
        "performance": await at(chat_id, "misc.tech_performance"),
    }
    tech_stack = "\n".join(
        [
            f"• **{label}**: {value}"
            for key, label in labels.items()
            if (value := TECH_STACK.get(key))
        ]
    )
    return await at(
        chat_id,
        "misc.about_text",
        version=config.VERSION,
        dev_name=config.DEV_NAME,
        dev_url=config.DEV_URL,
        repo_url=config.GITHUB_URL,
        tech_stack=tech_stack,
    )
