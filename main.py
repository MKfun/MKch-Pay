import os
import logging
import traceback
from collections import defaultdict
from typing import DefaultDict, Dict
from dotenv import load_dotenv
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    PreCheckoutQueryHandler,
    CallbackContext
)
from config import ITEMS, MESSAGES
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Исправлено: massage -> message
    level=logging.INFO
)

logger = logging.getLogger(__name__)
STATS: Dict[str, DefaultDict[str, int]] = {
    'purchases': defaultdict(int)
}

async def start(update: Update, context: CallbackContext) -> None:
    keyboard = []
    for item_id, item in ITEMS.items():
        keyboard.append([InlineKeyboardButton(
            f"{item['name']} - {item['price']} ⭐",
            callback_data=item_id
        )])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        MESSAGES['welcome'],
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        MESSAGES['help'],
        parse_mode='MarkdownV2',
        disable_web_page_preview=True
    )

async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
    try:
        await query.answer()
        item_id = query.data
        item = ITEMS[item_id]
        if not isinstance(query.message, Message):
            return

        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=item['name'],
            description=item['description'],
            payload=item_id,
            provider_token="",  # Не забудьте добавить реальный токен платежной системы!
            currency="XTR",
            prices=[LabeledPrice(item['name'], int(item['price']))],
            start_parameter="start_parameter"
        )
    except Exception as e:
        logger.error(f"Ошибка в button_handler: {str(e)}")
        if query and query.message and isinstance(query.message, Message):
            await query.message.reply_text(
                "Извините, что-то пошло не так при обработке вашего запроса."
            )

async def precheckout_callback(update: Update, context: CallbackContext) -> None:
    query = update.pre_checkout_query
    if query.invoice_payload in ITEMS:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Что-то пошло не так ...")

async def successful_payment_callback(update: Update, context: CallbackContext) -> None:
    payment = update.message.successful_payment
    item_id = payment.invoice_payload
    item = ITEMS[item_id]
    user_id = update.effective_user.id

    STATS['purchases'][str(user_id)] += 1

    logger.info(
        f"Успешная покупка от {user_id} "
        f"С товаром {item_id} (charge_id: {payment.telegram_payment_charge_id})"
    )

    # Исправленная секция: правильное форматирование и закрытие скобок
    await update.message.reply_text(
        f"Спасибо за покупку! 🎉\n\n"
        f"`{item['secret']}`",
        parse_mode='Markdown'
    )

async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(f"Update {update} caused error {context.error}")


def main() -> None:
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
        application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

        # Add error handler
        application.add_error_handler(error_handler)

        # Start the bot
        logger.info("Бот стартанул")
        application.run_polling()

    except Exception as e:
        logger.error(f"Ошибка старта бота: {str(e)}")


if __name__ == '__main__':
    main()