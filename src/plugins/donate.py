import contextlib

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from src.config import config
from src.core.bot import bot
from src.core.plugin import Plugin, register
from src.utils.decorators import safe_handler
from src.utils.i18n import at


class DonatePlugin(Plugin):
    """Plugin for handling donations via Telegram Stars and external links."""

    name = "donate"
    priority = 250

    async def setup(self, client: Client, ctx) -> None:
        pass


async def get_donate_kb(chat_id: int) -> InlineKeyboardMarkup:
    """Generate the main donation keyboard with Stars and external links."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(chat_id, "donate.stars_btn"), callback_data="donate:stars"
                )
            ],
            [InlineKeyboardButton(await at(chat_id, "donate.bmc_btn"), url=config.SUPPORT_URL)],
            [
                InlineKeyboardButton(
                    await at(chat_id, "donate.github_btn"), url=config.GITHUB_SPONSORS_URL
                )
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "donate.back_btn"), callback_data="help:start"
                )
            ],
        ]
    )


@bot.on_message(filters.command(["donate", "support"]))
@safe_handler
async def donate_handler(client: Client, message: Message) -> None:
    """Display the main donation menu."""
    chat_id = message.chat.id
    await message.reply(
        await at(chat_id, "donate.text", bot_name=config.BOT_NAME),
        reply_markup=await get_donate_kb(chat_id),
    )


@bot.on_callback_query(filters.regex(r"^donate:"))
@safe_handler
async def donate_callback_handler(client: Client, callback_query: CallbackQuery) -> None:
    """Handle donation menu navigation and Stars payment flow."""
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id

    if data == "donate:main":
        with contextlib.suppress(Exception):
            await callback_query.message.edit_text(
                await at(chat_id, "donate.text", bot_name=config.BOT_NAME),
                reply_markup=await get_donate_kb(chat_id),
            )

    elif data == "donate:stars":
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        await at(chat_id, "donate.stars_amount", amount=50),
                        callback_data="donate:pay:50",
                    ),
                    InlineKeyboardButton(
                        await at(chat_id, "donate.stars_amount", amount=250),
                        callback_data="donate:pay:250",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        await at(chat_id, "donate.stars_amount", amount=500),
                        callback_data="donate:pay:500",
                    )
                ],
                [
                    InlineKeyboardButton(
                        await at(chat_id, "donate.back_btn"), callback_data="donate:main"
                    )
                ],
            ]
        )
        with contextlib.suppress(Exception):
            await callback_query.message.edit_text(
                await at(chat_id, "donate.stars_select_text"),
                reply_markup=kb,
            )

    elif data.startswith("donate:pay:"):
        amount = int(data.split(":")[-1])
        title = await at(chat_id, "donate.invoice_title", bot_name=config.BOT_NAME)
        description = await at(chat_id, "donate.invoice_desc", amount=amount)

        try:
            await client.send_invoice(
                chat_id=user_id,
                title=title,
                description=description,
                payload=f"donate_{amount}",
                currency="XTR",
                prices=[LabeledPrice(label="Support", amount=amount)],
                start_parameter="donate",
            )
            await callback_query.answer()
        except Exception as e:
            await callback_query.answer(f"Error: {str(e)}", show_alert=True)


@bot.on_pre_checkout_query()
@safe_handler
async def pre_checkout_handler(client: Client, query: PreCheckoutQuery) -> None:
    """Approve checkout queries for Telegram Stars."""
    await query.answer(ok=True)


@bot.on_message(filters.successful_payment)
@safe_handler
async def successful_payment_handler(client: Client, message: Message) -> None:
    """Handle successful donation payments and notify admin."""
    payment = message.successful_payment
    amount = payment.total_amount
    currency = payment.currency

    await message.reply(
        await at(message.chat.id, "donate.thanks", amount=amount, currency=currency)
    )

    if config.OWNER_ID:
        with contextlib.suppress(Exception):
            admin_msg = await at(
                config.OWNER_ID,
                "donate.admin_notify",
                mention=message.from_user.mention,
                amount=amount,
                currency=currency,
                payload=payment.invoice_payload,
            )
            await client.send_message(config.OWNER_ID, admin_msg)


register(DonatePlugin())
