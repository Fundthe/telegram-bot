import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from flask import Flask
from threading import Thread

# --- Keep Alive ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "I'm alive!"

def run():
    app_web.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Telegram bot ---
load_dotenv()

CHOOSING, RATE, HOURS, LOOP_TOKENS, LOOP_LTV, LOOP_SUPPLY, LOOP_BORROW, \
LOAN_DEP_AMOUNT, LOAN_DEP_PRICE, LOAN_BORROW_AMOUNT, LOAN_BORROW_PRICE, LOAN_LTV, LOAN_BORROW_FACTOR, IL_INPUT = range(14)
user_data_temp = {}

def calculate_simple(rate, hours, days=365):
    periods_per_day = 24 / hours
    return rate * periods_per_day * days

def calculate_looping_table(tokens, ltv, supply_rate, borrow_rate, loops=10):
    supply_rate /= 100
    borrow_rate /= 100
    ltv = float(ltv)

    results = []
    deposit = tokens
    total_borrow = 0

    for i in range(1, loops + 1):
        borrow = tokens * (ltv ** i)
        total_borrow += borrow
        deposit += borrow

        supply_income = deposit * supply_rate
        borrow_cost = total_borrow * borrow_rate
        apy = ((supply_income - borrow_cost) / tokens) * 100

        results.append({
            'round': i,
            'deposit': round(deposit, 2),
            'borrow': round(borrow, 2),
            'total_borrow': round(total_borrow, 2),
            'apy': round(apy, 2)
        })
    return results

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["📈 Ставка финансирования"], ["🔁 Лупинг"], ["💳 Кредитование"], ["📉 IL"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Что хочешь рассчитать?", reply_markup=reply_markup)
    return CHOOSING

async def choose_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if "Ставка финансирования" in choice:
        await update.message.reply_text("💬 Введи процент ставки (например: 0.5)")
        return RATE
    elif "Лупинг" in choice:
        await update.message.reply_text("🔢 Введи количество токенов:")
        return LOOP_TOKENS
    elif "Кредитование" in choice:
        await update.message.reply_text("💰 Введи количество токенов в депозите:")
        return LOAN_DEP_AMOUNT
    elif "IL" in choice:
        await update.message.reply_text("📉 Введи цену первого токена при входе в пул:")
        user_data_temp[update.effective_chat.id] = {}
        return IL_INPUT
    else:
        await update.message.reply_text("❌ Пожалуйста, выбери одну из опций.")
        return CHOOSING

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
            f"✅ Расчёт готов! \n"
            f"📈 Процент за период: {rate}% \n"
            f"⏱ Начисляется каждые: {hours} ч \n"
            f"📅 Простой % в год: {simple:.2f}% \n"
            f"⬇️ Выбери следующую функцию:"
        )
        await update.message.reply_text(response)
        return await start(update, context)
    except Exception:
        await update.message.reply_text("❌ Что-то пошло не так. Попробуй ещё раз.")
        return RATE

# Лупинг — шаги ввода
async def get_loop_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tokens = float(update.message.text.strip())
        user_data_temp[update.effective_chat.id] = {'tokens': tokens}
        await update.message.reply_text("📊 Введи LTV (в %):")
        return LOOP_LTV
    except ValueError:
        await update.message.reply_text("❌ Введи число. Пример: 10")
        return LOOP_TOKENS

async def get_loop_ltv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ltv = float(update.message.text.strip().replace('%', '')) / 100
        user_data_temp[update.effective_chat.id]['ltv'] = ltv
        await update.message.reply_text("📈 Введи процент по депозиту (в %):")
        return LOOP_SUPPLY
    except ValueError:
        await update.message.reply_text("❌ Введи число. Пример: 70")
        return LOOP_LTV

async def get_loop_supply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        supply = float(update.message.text.strip().replace('%', ''))
        user_data_temp[update.effective_chat.id]['supply'] = supply
        await update.message.reply_text("💸 Введи процент по займу (в %):")
        return LOOP_BORROW
    except ValueError:
        await update.message.reply_text("❌ Введи число. Пример: 15")
        return LOOP_SUPPLY

async def get_loop_borrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        borrow = float(update.message.text.strip().replace('%', ''))
        data = user_data_temp[update.effective_chat.id]

        rounds = calculate_looping_table(
            tokens=data['tokens'],
            ltv=data['ltv'],
            supply_rate=data['supply'],
            borrow_rate=borrow
        )

        response = "✅ Расчёт по лупингу (10 кругов):\n\n"
        response += "```\n"
        response += "Круг |   Депозит  |   Заём   |   Долг   |   APY\n"
        response += "-----|------------|----------|----------|--------\n"

        for r in rounds:
            response += f"{r['round']:>4} | {r['deposit']:>10.2f} | {r['borrow']:>8.2f} | {r['total_borrow']:>8.2f} | {r['apy']:>6.2f}%\n"

        response += "```\n"
        response += "\n⬇️ Выбери следующую функцию:"
        await update.message.reply_text(response)
        return await start(update, context)

    except Exception:
        await update.message.reply_text("❌ Что-то пошло не так. Попробуй ещё раз.")
        return LOOP_BORROW

# Кредитование — шаги ввода
async def get_loan_dep_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        user_data_temp[update.effective_chat.id] = {'dep_amount': amount}
        await update.message.reply_text("💵 Введи цену токена депозита:")
        return LOAN_DEP_PRICE
    except:
        await update.message.reply_text("❌ Введи число.")
        return LOAN_DEP_AMOUNT

async def get_loan_dep_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip())
        user_data_temp[update.effective_chat.id]['dep_price'] = price
        await update.message.reply_text("💸 Введи количество токенов в займе:")
        return LOAN_BORROW_AMOUNT
    except:
        await update.message.reply_text("❌ Введи число.")
        return LOAN_DEP_PRICE

async def get_loan_borrow_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        user_data_temp[update.effective_chat.id]['borrow_amount'] = amount
        await update.message.reply_text("💲 Введи цену токена займа:")
        return LOAN_BORROW_PRICE
    except:
        await update.message.reply_text("❌ Введи число.")
        return LOAN_BORROW_AMOUNT

async def get_loan_borrow_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip())
        user_data_temp[update.effective_chat.id]['borrow_price'] = price
        await update.message.reply_text("📊 Введи LTV (например: 0.8):")
        return LOAN_LTV
    except:
        await update.message.reply_text("❌ Введи число.")
        return LOAN_BORROW_PRICE

async def get_loan_ltv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ltv_input = float(update.message.text.strip().replace('%', ''))
        if ltv_input > 1:
            ltv_input /= 100  # Преобразуем 70% -> 0.7
        user_data_temp[update.effective_chat.id]['ltv'] = ltv_input
        await update.message.reply_text("🧮 Введи borrow factor (например: 1):")
        return LOAN_BORROW_FACTOR
    except:
        await update.message.reply_text("❌ Введи число.")
        return LOAN_LTV

async def get_loan_borrow_factor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        factor = float(update.message.text.strip())
        data = user_data_temp[update.effective_chat.id]
        dep_value = data['dep_amount'] * data['dep_price']
        borrow_value = data['borrow_amount'] * data['borrow_price']

        hf = (data['ltv'] * dep_value) / (borrow_value * factor)
        rf = 1 / hf if hf != 0 else 0
        liquidation_price_dep = data['dep_price'] / hf if hf != 0 else 0
        liquidation_price_borrow = data['borrow_price'] / hf if hf != 0 else 0

        response = (
            f"✅ Результаты расчёта: \n"
            f"🟢 Health Factor: {hf:.2f} \n"
            f"⚠️ Risk Factor: {rf:.1%} \n"
            f"💣 Ликв. цена депозита: ${liquidation_price_dep:.4f} \n"
            f"💣 Ликв. цена займа: ${liquidation_price_borrow:.4f} \n"
            f"⬇️ Выбери следующую функцию:"
        )

        await update.message.reply_text(response)
        return await start(update, context)
    except:
        await update.message.reply_text("❌ Что-то пошло не так.")
        return LOAN_BORROW_FACTOR

# IL — impermanent loss
async def get_il_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip().replace(',', '.')

    try:
        user_state = user_data_temp.setdefault(chat_id, {})

        if 'p1_initial' not in user_state:
            user_state['p1_initial'] = float(text)
            await update.message.reply_text("🔁 Введи текущую цену первого токена:")
            return IL_INPUT

        elif 'p1_now' not in user_state:
            user_state['p1_now'] = float(text)
            await update.message.reply_text("🟠 Введи цену второго токена при входе в пул:")
            return IL_INPUT

        elif 'p2_initial' not in user_state:
            user_state['p2_initial'] = float(text)
            await update.message.reply_text("🟡 Введи текущую цену второго токена:")
            return IL_INPUT

        elif 'p2_now' not in user_state:
            user_state['p2_now'] = float(text)

            p1_initial = user_state['p1_initial']
            p1_now = user_state['p1_now']
            p2_initial = user_state['p2_initial']
            p2_now = user_state['p2_now']

            r1 = p1_now / p1_initial
            r2 = p2_now / p2_initial
            k = r1 / r2
            il = (2 * (k ** 0.5) / (1 + k)) - 1

            await update.message.reply_text(f"📉 Impermanent Loss (2 токена): {abs(il) * 100:.2f}%")
            return await start(update, context)

        else:
            user_data_temp[chat_id] = {}
            await update.message.reply_text("❌ Что-то пошло не так. Начнём заново. Введи цену первого токена при входе в пул:")
            return IL_INPUT

    except Exception:
        await update.message.reply_text("❌ Введи корректное число, например: 1200")
        return IL_INPUT

if __name__ == "__main__":
    keep_alive()
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, choose_option)
        ],
        states={
            CHOOSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_option)],
            RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rate)],
            HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_hours)],
            LOOP_TOKENS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_loop_tokens)],
            LOOP_LTV: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_loop_ltv)],
            LOOP_SUPPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_loop_supply)],
            LOOP_BORROW: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_loop_borrow)],
            LOAN_DEP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_loan_dep_amount)],
            LOAN_DEP_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_loan_dep_price)],
            LOAN_BORROW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_loan_borrow_amount)],
            LOAN_BORROW_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_loan_borrow_price)],
            LOAN_LTV: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_loan_ltv)],
            LOAN_BORROW_FACTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_loan_borrow_factor)],
            IL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_il_input)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv_handler)
    app.run_polling()
