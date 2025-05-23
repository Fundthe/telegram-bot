import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters, CallbackQueryHandler
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
LOAN_DEP_AMOUNT, LOAN_DEP_PRICE, LOAN_BORROW_AMOUNT, LOAN_BORROW_PRICE, \
LOAN_LTV, LOAN_BORROW_FACTOR, IL_INPUT = range(14)

user_data_temp = {}

def calculate_simple(rate, hours):
    periods = 8760 / hours  # часов в году
    return rate * periods

def calculate_looping_table(tokens, ltv, supply_rate, borrow_rate):
    rounds = []
    deposit = tokens
    total_borrow = 0

    for i in range(1, 11):
        borrow = deposit * ltv
        total_borrow += borrow
        deposit += borrow
        net_apy = (deposit * supply_rate - total_borrow * borrow_rate) / tokens
        rounds.append({
            'round': i,
            'deposit': deposit,
            'borrow': borrow,
            'total_borrow': total_borrow,
            'apy': net_apy
        })

    return rounds
    
def back_to_menu_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В начало", callback_data="back")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Ставка финансирования", callback_data="rate"),
         InlineKeyboardButton("🔁 Лупинг", callback_data="looping")],
        [InlineKeyboardButton("💳 Кредитование", callback_data="loan"),
         InlineKeyboardButton("📉 Impermanent Loss", callback_data="il")]
    ])
    if update.message:
        await update.message.reply_markdown_v2("*📋Главное меню калькулятора*", reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.message.edit_text("📋 Главное меню\n\n🔽 Выбери один из вариантов:", reply_markup=keyboard)
    return CHOOSING

async def get_il_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip().replace(',', '.')
    user_state = user_data_temp.setdefault(chat_id, {})

    try:
        if 'token1' not in user_state:
            user_state['token1'] = text.upper()
            await update.message.reply_text(f"💰 Введи цену {user_state['token1']} при входе в пул:")
            return IL_INPUT

        elif 'p1_initial' not in user_state:
            user_state['p1_initial'] = float(text)
            await update.message.reply_text(f"📉 Введи текущую цену {user_state['token1']}:")
            return IL_INPUT

        elif 'p1_now' not in user_state:
            user_state['p1_now'] = float(text)
            await update.message.reply_text("🔠 Введи название второй монеты:")
            return IL_INPUT

        elif 'token2' not in user_state:
            user_state['token2'] = text.upper()
            await update.message.reply_text(f"💰 Введи цену {user_state['token2']} при входе в пул:")
            return IL_INPUT

        elif 'p2_initial' not in user_state:
            user_state['p2_initial'] = float(text)
            await update.message.reply_text(f"📉 Введи текущую цену {user_state['token2']}:")
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

            response = (
                "📉 Impermanent Loss\n"
                "```\n"
                f"{user_state['token1']}: {p1_initial} → {p1_now}\n"
                f"{user_state['token2']}: {p2_initial} → {p2_now}\n"
                f"IL: {abs(il) * 100:.2f}%\n"
                "```"
            )

            await update.message.reply_text(response)
            return await start(update, context)

        else:
            user_data_temp[chat_id] = {}
            await update.message.reply_text("❌ Что-то пошло не так. Начнём заново. Введи название первой монеты:")
            return IL_INPUT

    except Exception:
        await update.message.reply_text("❌ Введи корректное число или название токена.")
        return IL_INPUT

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
            "*📈 Расчёт фандинга*\n"
            "```\n"
            f"{'Ставка финансирования:':<22} {rate}%\n"
            f"{'Начисляется каждые:':<22} {hours} ч\n"
            f"{'APR:':<22} {simple:.2f}%\n"
            "```"
        )

        await update.message.reply_markdown_v2(response)
        return await start(update, context)

    except Exception:
        await update.message.reply_text("❌ Что-то пошло не так. Попробуй ещё раз.")
        return RATE
        
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

        response = "🔁 *Лупинг (10 кругов)*\n"
        response += "```\n"
        response += "Круг |   Депозит  |   Заём   |   Долг   |   APY\n"
        response += "-----|------------|----------|----------|--------\n"

        for r in rounds:
            response += f"{r['round']:>4} | {r['deposit']:>10.2f} | {r['borrow']:>8.2f} | {r['total_borrow']:>8.2f} | {r['apy']:>6.2f}%\n"

        response += "```"

        await update.message.reply_text(response, parse_mode='Markdown')
        
        return await start(update, context)

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
        return LOOP_BORROW
        
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
                    "💳 *Кредитование*\n"
                    "```\n"
                    f"Health Factor:         {hf:.2f}\n"
                    f"Risk Factor:           {rf:.1%}\n"
                    f"Ликв. цена депозита:   ${liquidation_price_dep:.4f}\n"
                    f"Ликв. цена займа:      ${liquidation_price_borrow:.4f}\n"
                    "```\n"
                )

                await update.message.reply_text(response, parse_mode='Markdown')
                return await start(update, context)

            except:
                await update.message.reply_text("❌ Что-то пошло не так.")
                return LOAN_BORROW_FACTOR

async def get_il_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip().replace(',', '.')
    user_state = user_data_temp.setdefault(chat_id, {})

    try:
        # Шаг 1: название первой монеты
        if 'token1' not in user_state:
            user_state['token1'] = text.upper()
            await update.message.reply_text(f"💰 Введи цену {user_state['token1']} при входе в пул:")
            return IL_INPUT

        # Шаг 2: цена первой монеты при входе
        elif 'p1_initial' not in user_state:
            user_state['p1_initial'] = float(text)
            await update.message.reply_text(f"📉 Введи текущую цену {user_state['token1']}:")
            return IL_INPUT

        # Шаг 3: текущая цена первой монеты
        elif 'p1_now' not in user_state:
            user_state['p1_now'] = float(text)
            await update.message.reply_text("🔠 Введи название второй монеты:")
            return IL_INPUT

        # Шаг 4: название второй монеты
        elif 'token2' not in user_state:
            user_state['token2'] = text.upper()
            await update.message.reply_text(f"💰 Введи цену {user_state['token2']} при входе в пул:")
            return IL_INPUT

        # Шаг 5: цена второй монеты при входе
        elif 'p2_initial' not in user_state:
            user_state['p2_initial'] = float(text)
            await update.message.reply_text(f"📉 Введи текущую цену {user_state['token2']}:")
            return IL_INPUT

        # Шаг 6: текущая цена второй монеты
        elif 'p2_now' not in user_state:
            user_state['p2_now'] = float(text)

            # Расчёт
            p1_initial = user_state['p1_initial']
            p1_now = user_state['p1_now']
            p2_initial = user_state['p2_initial']
            p2_now = user_state['p2_now']

            r1 = p1_now / p1_initial
            r2 = p2_now / p2_initial
            k = r1 / r2
            il = (2 * (k ** 0.5) / (1 + k)) - 1

            response = (
                "📉 *Impermanent Loss*\n"
                "```\n"
                f"{'Монета':<10}│{'Вход':>10}│{'Выход':>10}\n"
                f"{'-'*10}│{'-'*10}│{'-'*10}\n"
                f"{user_state['token1']:<10}│{p1_initial:>10.2f}│{p1_now:>10.2f}\n"
                f"{user_state['token2']:<10}│{p2_initial:>10.2f}│{p2_now:>10.2f}\n"
                f"{'-'*33}\n"
                f"{'Impermanent Loss':<10} → → →{abs(il) * 100:>10.2f}%\n"
                "```"
            )
            await update.message.reply_markdown_v2(response)
            user_data_temp[chat_id] = {}
            return await start(update, context)

            await update.message.reply_text(response)
            return await start(update, context)

        else:
            user_data_temp[chat_id] = {}
            await update.message.reply_text("❌ Что-то пошло не так. Начнём заново. Введи название первой монеты:")
            return IL_INPUT

    except Exception:
        await update.message.reply_text("❌ Введи корректное число или название токена.")
        return IL_INPUT

from telegram.ext import CallbackQueryHandler

async def choose_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back":
        return await start(update, context)

    choice = query.data

    if choice == "rate":
        await query.edit_message_text(
            "💬 Введи процент ставки (например: 0.5):",
            reply_markup=back_to_menu_button()
        )
        return RATE

    elif choice == "looping":
        await query.edit_message_text(
            "🔢 Введи количество токенов:",
            reply_markup=back_to_menu_button()
        )
        return LOOP_TOKENS

    elif choice == "loan":
        await query.edit_message_text(
            "💰 Введи количество токенов в депозите:",
            reply_markup=back_to_menu_button()
        )
        return LOAN_DEP_AMOUNT

    elif choice == "il":
        await query.edit_message_text(
            "🔠 Введи название первой монеты:",
            reply_markup=back_to_menu_button()
        )
        user_data_temp[query.from_user.id] = {}  # <-- исправлено!
        return IL_INPUT

    else:
        await query.edit_message_text("❌ Неизвестная команда. Попробуй ещё раз.")
        return CHOOSING
        
# --- Хендлер состояний ---
conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(choose_option)],
        states={
            CHOOSING: [CallbackQueryHandler(choose_option)],
            RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_rate),
                CallbackQueryHandler(choose_option, pattern="^back$")
            ],
            HOURS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_hours),
                CallbackQueryHandler(choose_option, pattern="^back$")
            ],
            LOOP_TOKENS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_loop_tokens),
                CallbackQueryHandler(choose_option, pattern="^back$")
            ],
            LOOP_LTV: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_loop_ltv),
                CallbackQueryHandler(choose_option, pattern="^back$")
            ],
            LOOP_SUPPLY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_loop_supply),
                CallbackQueryHandler(choose_option, pattern="^back$")
            ],
            LOOP_BORROW: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_loop_borrow),
                CallbackQueryHandler(choose_option, pattern="^back$")
            ],
            LOAN_DEP_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_loan_dep_amount),
                CallbackQueryHandler(choose_option, pattern="^back$")
            ],
            LOAN_DEP_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_loan_dep_price),
                CallbackQueryHandler(choose_option, pattern="^back$")
            ],
            LOAN_BORROW_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_loan_borrow_amount),
                CallbackQueryHandler(choose_option, pattern="^back$")
            ],
            LOAN_BORROW_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_loan_borrow_price),
                CallbackQueryHandler(choose_option, pattern="^back$")
            ],
            LOAN_LTV: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_loan_ltv),
                CallbackQueryHandler(choose_option, pattern="^back$")
            ],
            LOAN_BORROW_FACTOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_loan_borrow_factor),
                CallbackQueryHandler(choose_option, pattern="^back$")
            ],
            IL_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_il_input),
                CallbackQueryHandler(choose_option, pattern="^back$")
            ],
        },
        fallbacks=[]
    )

    # --- Запуск ---
if __name__ == "__main__":
        keep_alive()
        app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

        app.add_handler(conv_handler)
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))

        app.run_polling()

        app.add_handler(conv_handler)
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))

        app.run_polling()
