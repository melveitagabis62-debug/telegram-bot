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
        interval_map = {
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }

        expiration_map = {
            "1m": "1-2 min",
            "5m": "3-5 min",
            "15m": "10-15 min"
        }

        interval = interval_map.get(timeframe)
        expiration = expiration_map.get(timeframe)

        analysis = get_analysis(pair, interval)

        rsi = analysis.indicators["RSI"]
        macd = analysis.indicators["MACD.macd"]
        ema = analysis.indicators["EMA20"]
        close = analysis.indicators["close"]

        # SIGNAL LOGIC
        if rsi < 30 and macd > 0:
            signal = "BUY"
        elif rsi > 70 and macd < 0:
            signal = "SELL"
        elif ema < close:
            signal = "BUY"
        else:
            signal = "SELL"

        # SAFE ENTRY
        if signal == "BUY":
            safe_entry = close * 0.995
        else:
            safe_entry = close * 1.005

def generate_signal(pair, timeframe, signal, safe_entry, expiration):
    return f"""
📊 Sigma AI Trade

💱 Pair: {pair}
⏱ Timeframe: {timeframe}

📈 Signal: {signal}
🎯 Safe Entry: {round(safe_entry, 5)}
⏳ Expiration: {expiration}

⚡ Powered by TradingView
"""


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
                     
    elif data in ["1m", "5m", "15m"]:
        
        await query.message.reply_text(f"⏱ Timeframe selected: {data}")
    
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
