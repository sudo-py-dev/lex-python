from pyrogram import Client

from src.config import config

bot: Client = Client(
    name="group_manager",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workdir="sessions",
)
