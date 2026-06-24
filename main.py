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
        [InlineKeyboardButton("GBP/JPY", callback_data="GBPJPY")]
    ]
    return InlineKeyboardMarkup(keyboard)


def timeframe_menu(pair):
    keyboard = [
        [InlineKeyboardButton("1m", callback_data=f"{pair}_1m"),
         InlineKeyboardButton("5m", callback_data=f"{pair}_5m")],
        [InlineKeyboardButton("15m", callback_data=f"{pair}_15m")]
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
        ema = analysis.indicators["EMA20"]

        signal = "HOLD"

        # 🔥 Improved logic
        if rsi < 30 and macd > 0:
            signal = "BUY"
        elif rsi > 70 and macd < 0:
            signal = "SELL"
        elif ema < analysis.indicators["close"]:
            signal = "BUY"
        else:
            signal = "SELL"

        return f"""
📊 Sigma AI Trade

💱 Pair: {pair}
⏱ Timeframe: {timeframe}

📈 Signal: {signal}

🧠 Indicators:
RSI: {round(rsi,2)}
MACD: {round(macd,2)}
EMA20: {round(ema,2)}

⚡ Powered by TradingView
"""

    except Exception as e:
        print("ERROR:", e)
        return "❌ Failed to fetch data"

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    "EURCHF", "AUDJPY", "GBPCHF"
                 ]:
        await query.edit_message_text("Select Timeframe:", reply_markup=timeframe_menu(data))

    elif "_" in data:
        pair, tf = data.split("_")

        result = generate_signal(pair, tf)

        await query.edit_message_text(result)


# ================= RUN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))

print("Bot running...")
app.run_polling()
