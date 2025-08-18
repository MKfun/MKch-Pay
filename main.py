import os
import logging
import json
from collections import defaultdict
from typing import DefaultDict, Dict, List, Optional
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
from config import ITEMS, MESSAGES, SETTINGS

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Статистика
STATS: Dict[str, DefaultDict[str, int]] = {'purchases': defaultdict(int)}
ADMINS: List[int] = SETTINGS['ADMINS']
AUTO_DELIVERY: bool = SETTINGS['AUTO_DELIVERY']

# Состояния
WAITING_AMOUNT = 1

def save_settings():
    settings = {
        'ADMINS': ADMINS,
        'PASSCODE_MIN_PRICE': ITEMS['PASSCODE']['min_price'],
        'AUTO_DELIVERY': AUTO_DELIVERY
    }
    with open('settings.json', 'w') as f:
        json.dump(settings, f, indent=2)

def get_code() -> Optional[str]:
    try:
        if not os.path.exists('PASSCODE_codes.txt'):
            return None
            
        with open('PASSCODE_codes.txt', 'r') as f:
            codes = f.read().splitlines()
        
        if not codes:
            return None
            
        code = codes[0]
        with open('PASSCODE_codes.txt', 'w') as f:
            f.write('\n'.join(codes[1:]))
        
        return code
    except Exception as e:
        logger.error(f"Ошибка получения кода: {e}")
        return None

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

async def admin_command(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(MESSAGES['admin_only'])
        return
    await update.message.reply_text(MESSAGES['admin_help'], parse_mode='Markdown')

async def set_price(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(MESSAGES['admin_only'])
        return
    
    try:
        new_price = int(context.args[0])
        # Минимальная цена теперь от 1 звезды
        if new_price < 1:
            await update.message.reply_text(MESSAGES['min_price_error'])
            return
            
        ITEMS['PASSCODE']['min_price'] = new_price
        save_settings()
        await update.message.reply_text(MESSAGES['price_updated'].format(new_price))
    except:
        await update.message.reply_text(MESSAGES['invalid_command'])

async def toggle_auto_delivery(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(MESSAGES['admin_only'])
        return
    
    try:
        state = context.args[0].lower()
        global AUTO_DELIVERY
        
        if state == 'on':
            AUTO_DELIVERY = True
            status = "включена"
        elif state == 'off':
            AUTO_DELIVERY = False
            status = "выключена"
        else:
            raise ValueError()
            
        save_settings()
        await update.message.reply_text(MESSAGES['delivery_status'].format(status))
    except:
        await update.message.reply_text(MESSAGES['invalid_command'])

async def add_admin(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(MESSAGES['admin_only'])
        return
    
    try:
        new_admin = int(context.args[0])
        if new_admin in ADMINS:
            await update.message.reply_text("⚠️ Админ уже существует")
            return
            
        ADMINS.append(new_admin)
        save_settings()
        await update.message.reply_text(MESSAGES['admin_added'].format(new_admin))
    except:
        await update.message.reply_text(MESSAGES['invalid_command'])

async def remove_admin(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(MESSAGES['admin_only'])
        return
    
    try:
        admin_id = int(context.args[0])
        if admin_id not in ADMINS:
            await update.message.reply_text("⚠️ Админ не найден")
            return
            
        ADMINS.remove(admin_id)
        save_settings()
        await update.message.reply_text(MESSAGES['admin_removed'].format(admin_id))
    except:
        await update.message.reply_text(MESSAGES['invalid_command'])

async def list_admins(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(MESSAGES['admin_only'])
        return
    
    if not ADMINS:
        await update.message.reply_text(MESSAGES['no_admins'])
        return
        
    await update.message.reply_text(
        MESSAGES['admin_list'].format('\n'.join(str(admin) for admin in ADMINS))
    )

async def show_stats(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(MESSAGES['admin_only'])
        return
    
    total_sales = sum(STATS['purchases'].values())
    unique_buyers = len(STATS['purchases'])
    await update.message.reply_text(MESSAGES['stats'].format(total_sales, unique_buyers))

async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [[InlineKeyboardButton(item['name'], callback_data=item_id)] 
                for item_id, item in ITEMS.items()]
    await update.message.reply_photo(
        photo=MESSAGES['welcome_photo_url'],
        caption=MESSAGES['welcome'],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(MESSAGES['help'], parse_mode='MarkdownV2')

async def button_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    try:
        await query.answer()
        item_id = query.data
        
        if item_id == 'PASSCODE':
            context.user_data['selected_item'] = item_id
            await query.message.reply_text(MESSAGES['enter_amount'])
            return WAITING_AMOUNT
        else:
            item = ITEMS[item_id]
            await context.bot.send_invoice(
                chat_id=query.message.chat_id,
                title=item['name'],
                description=item['description'],
                payload=item_id,
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(item['name'], int(item['price']))],
                start_parameter="start_parameter"
            )
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка в button_handler: {e}")
        await query.message.reply_text("Ошибка обработки запроса")
        return ConversationHandler.END

async def handle_amount(update: Update, context: CallbackContext) -> int:
    try:
        amount = int(update.message.text)
        min_price = ITEMS['PASSCODE']['min_price']
        if amount < min_price:
            await update.message.reply_text(MESSAGES['invalid_amount'])
            return WAITING_AMOUNT
        
        item_id = context.user_data.get('selected_item', 'PASSCODE')
        item = ITEMS[item_id]
        
        await context.bot.send_invoice(
            chat_id=update.message.chat_id,
            title=f"{item['name']} ({amount} ⭐)",
            description=item['description'],
            payload=item_id,
            provider_token="",
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
    await query.answer(ok=(query.invoice_payload in ITEMS))

async def successful_payment_callback(update: Update, context: CallbackContext) -> None:
    payment = update.message.successful_payment
    item_id = payment.invoice_payload
    user_id = update.effective_user.id

    STATS['purchases'][str(user_id)] += 1
    logger.info(f"Покупка: {user_id}, Товар: {item_id}, Сумма: {payment.total_amount} ⭐")

    # Автовыдача работает независимо от цены
    if item_id == 'PASSCODE' and AUTO_DELIVERY:
        code = get_code() or MESSAGES['no_codes']
    else:
        code = ITEMS[item_id]['secret']

    await update.message.reply_text(f"Спасибо за покупку! 🎉\n\n`{code}`", parse_mode='Markdown')

async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(f"Ошибка: {context.error}")

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Админ-команды
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("setprice", set_price))
    application.add_handler(CommandHandler("autodelivery", toggle_auto_delivery))
    application.add_handler(CommandHandler("addadmin", add_admin))
    application.add_handler(CommandHandler("removeadmin", remove_admin))
    application.add_handler(CommandHandler("listadmins", list_admins))
    application.add_handler(CommandHandler("stats", show_stats))

    # Основные обработчики
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={
            WAITING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    application.add_error_handler(error_handler)

    logger.info("Бот запущен")
    application.run_polling()

if __name__ == '__main__':
    main()