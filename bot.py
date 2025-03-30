
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
    await update.message.reply_text(
        "👋 Привет!\n"
        "Я помогу тебе рассчитать простой годовой процент по ставке финансирования.\n\n"
        "💬 Напиши процент ставки (например: 0.5)"
    )
    return RATE

async def get_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rate = float(update.message.text.strip().replace('%', ''))
        user_data_temp[update.effective_chat.id] = {'rate': rate}
        await update.message.reply_text("⏱ Теперь напиши, раз в сколько часов начисляется процент (например: 4)")
        return HOURS
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введи число. Например: 0.5")
        return RATE

async def get_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hours = float(update.message.text.strip().replace('ч', '').replace(' ', ''))
        rate = user_data_temp[update.effective_chat.id]['rate']
        simple = calculate_simple(rate, hours)
        response = (
            f"✅ Расчёт готов!\n\n"
            f"📈 Процент за период: {rate}%\n"
            f"⏱ Начисляется каждые: {hours} ч\n"
            f"📅 Простой % в год: {simple:.2f}%\n\n"
            f"🔁 Напиши новые данные, если хочешь рассчитать заново."
        )
        await update.message.reply_text(response)
        await update.message.reply_text("💬 Напиши процент ставки финансирования (например: 0.5)")
        return RATE
    except Exception:
        await update.message.reply_text("❌ Что-то пошло не так. Попробуй ещё раз.")
        return RATE

if __name__ == "__main__":
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, start)
        ],
        states={
            RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rate)],
            HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_hours)]
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv_handler)
    app.run_polling()
