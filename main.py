from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from tradingview_ta import TA_Handler, Interval
import logging

import os

TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [6351041498]  # replace with your Telegram ID

# 🔥 ADD THIS RIGHT HERE
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
    "USDCAD", "USDCHF", "NZDUSD",
    "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY",
    "EURGBP", "EURCHF", "EURAUD", "EURCAD",
    "GBPAUD", "GBPCAD", "GBPCHF",
    "AUDCAD", "AUDCHF",
    "CADCHF"
]

AUTO_TIMEFRAME = "1m"   # you can change to 5m
SCAN_INTERVAL = 60      # seconds

last_signals = {}  # prevent spam

# ================= MENU =================

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Forex", callback_data="forex")],
        [InlineKeyboardButton("💰 Crypto", callback_data="crypto")]
    ]
    return InlineKeyboardMarkup(keyboard)


def forex_menu():
    keyboard = []
    row = []

    for i, pair in enumerate(PAIRS, 1):
        display = pair[:3] + "/" + pair[3:]  # EURUSD → EUR/USD

        row.append(
            InlineKeyboardButton(display, callback_data=pair)
        )

        if i % 2 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data="back")
    ])

    return InlineKeyboardMarkup(keyboard)


def timeframe_menu(pair):
    keyboard = [
        [InlineKeyboardButton("1m", callback_data=f"{pair}_1m"),
         InlineKeyboardButton("5m", callback_data=f"{pair}_5m")],
        [InlineKeyboardButton("15m", callback_data=f"{pair}_15m")],
        
        [InlineKeyboardButton("⬅️ Back", callback_data="back_forex")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ================= SIGNAL =================

def get_analysis(symbol, interval):
    handler = TA_Handler(
        symbol=symbol,
        screener="forex",
        exchange="FX_IDC",
        interval=interval
    )

    analysis = handler.get_analysis()
    return analysis


def generate_signal(pair, timeframe):
    try:
        interval_map = {
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }

        analysis = get_analysis(pair, interval_map[timeframe])

        rsi = analysis.indicators["RSI"]
        macd = analysis.indicators["MACD.macd"]
        ema50 = analysis.indicators["EMA50"]
        price = analysis.indicators["close"]
        

        # ================= STRATEGY LOGIC =================

        signal = "HOLD"
        warning = ""

        # 🔥 Detect strong trend (avoid trading)
        if abs(price - ema50) > (price * 0.002):  # far from EMA = strong trend
            warning = "⚠️ Strong trend detected → DO NOT TRADE"

        # 🟢 BUY (mean reversion)
        elif rsi < 30 and price >= ema50 * 0.995:
            signal = "BUY"

        # 🔴 SELL (mean reversion)
        elif rsi > 70 and price <= ema50 * 1.005:
            signal = "SELL"

        else:
            signal = "HOLD"
            warning = "⚠️ No clean setup → WAIT"

        # ================= DISPLAY =================

        if signal == "BUY":
            signal_display = "🟢 BUY (CALL)"
        elif signal == "SELL":
            signal_display = "🔴 SELL (PUT)"
        else:
            signal_display = "🟡 HOLD"

        return f"""
📊 Sigma AI Smart Signal

💱 Pair: {pair}
⏱ Timeframe: {timeframe}

📈 Signal: {signal_display}

{warning}

🧠 Strategy:
• Mean Reversion (No Chase)
• RSI + EMA50 Filter

📊 Indicators:
RSI: {round(rsi,2)}
EMA50: {round(ema50,2)}
Price: {round(price,5)}

⛔ Avoid trading during strong trends!
"""

    except Exception as e:
        print("ERROR:", e)
        return "❌ Failed to fetch data"

# ================= HANDLERS =================

from telegram import ReplyKeyboardMarkup

from telegram.ext import MessageHandler, filters

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Access Denied")
        return

    keyboard = [["🚀 Start Bot"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "👋 Welcome! Click below to start:",
        reply_markup=reply_markup
    )
async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id  # 👈 ADD THIS

    # 🔒 BLOCK UNAUTHORIZED USERS
    if user_id not in ALLOWED_USERS:
        return

    if update.message.text == "🚀 Start Bot":
        await update.message.reply_text(
            "🚀 Welcome to Sigma AI Bot",
            reply_markup=main_menu()
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id   # 👈 ADD THIS

    # 🔒 BLOCK UNAUTHORIZED USERS
    if user_id not in ALLOWED_USERS:
        await query.answer("⛔ Access Denied", show_alert=True)
        return

    # ✅ FIXED TIMEFRAME
    TIMEFRAME_MAP = {
        "1m": "1minute",
        "5m": "5minute",
        "15m": "15minute"
    }

    timeframe = TIMEFRAME_MAP.get(query.data, "1minute")

    pair = "EURUSD"  # or your selected pair

    try:
        result = generate_signal(pair, timeframe)
        await query.message.reply_text(result)

    except Exception as e:
        print("ERROR:", e)
        await query.message.reply_text("❌ Failed to fetch data")

    await query.answer()

    data = query.data

    if data == "forex":
        await query.edit_message_text("Select Pair:", reply_markup=forex_menu())

    elif data in PAIRS:
        await query.edit_message_text("Select Timeframe:", reply_markup=timeframe_menu(data))

    elif "_" in data:
        pair, tf = data.split("_")

        result = generate_signal(pair, tf)

        await query.edit_message_text(result)

    elif data == "back_main":
        await query.edit_message_text(
        "🚀 Welcome to Sigma AI Bot",
        reply_markup=main_menu()
    )

    elif data == "back_forex":
        await query.edit_message_text(
        "Select Pair:",
        reply_markup=forex_menu()
    )

async def auto_signal(context: ContextTypes.DEFAULT_TYPE):
    for pair in PAIRS:
        try:  # ✅ INDENTED

            result = generate_signal(pair, AUTO_TIMEFRAME)

            # 🔥 Only send BUY or SELL
            if "BUY" in result or "SELL" in result:

                # 🚫 prevent duplicate spam
                if last_signals.get(pair) == result:
                    continue

                last_signals[pair] = result

                # 📩 send to your Telegram
                await context.bot.send_message(
                    chat_id=ALLOWED_USERS[0],
                    text=f"🚨 AUTO SIGNAL\n\n{result}"
                )

        except Exception as e:  # ✅ same level as try
            print("AUTO ERROR:", e)

# ================= RUN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT, start_button))

print("Bot running...")
app.job_queue.run_repeating(auto_signal, interval=SCAN_INTERVAL, first=10)
app.run_polling()
