
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

load_dotenv()

# Этапы диалога
RATE, HOURS = range(2)

# Временное хранилище для значений
user_data_temp = {}

def calculate_simple(rate, hours, days=365):
    periods_per_day = 24 / hours
    return rate * periods_per_day * days

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💬 Напиши процент ставки финансирования (например: 0.5)")
    return RATE

async def get_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rate = float(update.message.text.replace(',', '.'))
        user_data_temp[update.effective_chat.id] = {'rate': rate}
        await update.message.reply_text("🕒 А теперь напиши, как часто начисляется ставка (в часах, например: 4)")
        return HOURS
    except:
        await update.message.reply_text("⚠️ Введи число, например: 0.5")
        return RATE

async def get_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hours = int(update.message.text)
        chat_id = update.effective_chat.id
        rate = user_data_temp.get(chat_id, {}).get('rate')

        if rate is None:
            await update.message.reply_text("⚠️ Что-то пошло не так. Напиши /start, чтобы начать заново.")
            return ConversationHandler.END

        simple = calculate_simple(rate, hours)
        response = (
            f"📊 Процент за период: {rate}%\n"
            f"⏱ Период: каждые {hours} ч\n"
            f"🧮 Простой % в год: {simple:.2f}%"
        )
        await update.message.reply_text(response)
        return ConversationHandler.END
    except:
        await update.message.reply_text("⚠️ Введи количество часов числом, например: 4")
        return HOURS

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Диалог прерван. Напиши /start, чтобы начать заново.")
    return ConversationHandler.END

app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("start", start),
        MessageHandler(filters.TEXT & ~filters.COMMAND, start)
    ],
,
    states={
        RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rate)],
        HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_hours)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

app.add_handler(conv_handler)
app.run_polling()
