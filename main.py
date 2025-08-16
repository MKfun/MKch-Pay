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
    CallbackContext,
    ConversationHandler
)
from config import ITEMS, MESSAGES
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)
STATS: Dict[str, DefaultDict[str, int]] = {
    'purchases': defaultdict(int)
}

# Состояния разговора
WAITING_AMOUNT = 1

async def start(update: Update, context: CallbackContext) -> None:
    keyboard = []
    for item_id, item in ITEMS.items():
        keyboard.append([InlineKeyboardButton(
            f"{item['name']}",
            callback_data=item_id
        )])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_photo(
        photo=MESSAGES['welcome_photo_url'],
        caption=MESSAGES['welcome'],
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        MESSAGES['help'],
        parse_mode='MarkdownV2',
        disable_web_page_preview=True
    )

async def button_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    if not query or not query.message:
        return ConversationHandler.END
    try:
        await query.answer()
        item_id = query.data
        item = ITEMS[item_id]
        
        if not isinstance(query.message, Message):
            return ConversationHandler.END

        # Для PASSCODE запрашиваем сумму
        if item_id == 'PASSCODE':
            context.user_data['selected_item'] = item_id
            await query.message.reply_text(MESSAGES['enter_amount'])
            return WAITING_AMOUNT
        else:
            # Для других товаров (если будут) используем фиксированную цену
            await context.bot.send_invoice(
                chat_id=query.message.chat_id,
                title=item['name'],
                description=item['description'],
                payload=item_id,
                provider_token="",  # Ваш реальный токен
                currency="XTR",
                prices=[LabeledPrice(item['name'], int(item['price']))],
                start_parameter="start_parameter"
            )
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка в button_handler: {str(e)}")
        if query and query.message and isinstance(query.message, Message):
            await query.message.reply_text("Извините, что-то пошло не так при обработке вашего запроса.")
        return ConversationHandler.END

async def handle_amount(update: Update, context: CallbackContext) -> int:
    try:
        amount = int(update.message.text)
        if amount < MESSAGES['min_amount']:
            await update.message.reply_text(MESSAGES['invalid_amount'])
            return WAITING_AMOUNT
        
        item_id = context.user_data.get('selected_item')
        if not item_id:
            await update.message.reply_text("Ошибка: товар не выбран")
            return ConversationHandler.END
        
        item = ITEMS[item_id]
        
        await context.bot.send_invoice(
            chat_id=update.message.chat_id,
            title=f"{item['name']} ({amount} ⭐)",
            description=item['description'],
            payload=item_id,
            provider_token="",  # Ваш реальный токен
            currency="XTR",
            prices=[LabeledPrice(item['name'], amount)],
            start_parameter="start_parameter"
        )
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(MESSAGES['invalid_amount'])
        return WAITING_AMOUNT

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
        f"Товар: {item_id}, Сумма: {payment.total_amount} ⭐"
    )

    await update.message.reply_text(
        f"Спасибо за покупку! 🎉\n\n"
        f"`{item['secret']}`",
        parse_mode='Markdown'
    )

async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(f"Update {update} caused error {context.error}")

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END

def main() -> None:
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        # Добавляем обработчик диалога
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(button_handler)],
            states={
                WAITING_AMOUNT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)
                ],
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(conv_handler)
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