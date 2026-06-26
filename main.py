from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from tradingview_ta import TA_Handler, Interval
import logging

import os

TOKEN = os.getenv("TOKEN")

# ================= MENU =================

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Forex", callback_data="forex")],
        [InlineKeyboardButton("💰 Crypto", callback_data="crypto")]
    ]
    return InlineKeyboardMarkup(keyboard)


def forex_menu():
    keyboard = [
        [InlineKeyboardButton("EUR/USD", callback_data="EURUSD")],
        [InlineKeyboardButton("GBP/USD", callback_data="GBPUSD")],
        [InlineKeyboardButton("USD/JPY", callback_data="USDJPY")],
        # 🔥 ADD THESE
        [InlineKeyboardButton("AUD/USD", callback_data="AUDUSD")],
        [InlineKeyboardButton("USD/CAD", callback_data="USDCAD")],
        [InlineKeyboardButton("USD/CHF", callback_data="USDCHF")],
        [InlineKeyboardButton("NZD/USD", callback_data="NZDUSD")],
        [InlineKeyboardButton("EUR/JPY", callback_data="EURJPY")],
        [InlineKeyboardButton("GBP/JPY", callback_data="GBPJPY")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
    ]
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
    keyboard = [["🚀 Start Bot"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "👋 Welcome! Click below to start:",
        reply_markup=reply_markup
    )
async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🚀 Start Bot":
        await update.message.reply_text(
            "🚀 Welcome to Sigma AI Bot",
            reply_markup=main_menu()
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "forex":
        await query.edit_message_text("Select Pair:", reply_markup=forex_menu())

    elif data in ["EURUSD", "GBPUSD", "USDJPY", "USDCHF",
    "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY",
    "EURCHF", "AUDJPY", "GBPCHF"]:
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

# ================= RUN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT, start_button))

print("Bot running...")
app.run_polling()
