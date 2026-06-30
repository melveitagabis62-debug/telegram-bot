from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.ext import MessageHandler, filters

from tradingview_ta import TA_Handler, Interval
import logging
import os
import datetime

TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [6351041498]

# ===== SETTINGS =====
MIN_CONFIDENCE = 70

# ===== ENTRY TIMING =====
def get_entry_decision(timeframe):
    now = datetime.datetime.utcnow()

    if timeframe == "1m":
        total = 60
        passed = now.second
    elif timeframe == "5m":
        total = 300
        passed = (now.minute % 5) * 60 + now.second
    else:
        total = 900
        passed = (now.minute % 15) * 60 + now.second

    remaining = total - passed

    if remaining > total * 0.6:
        return "⏳ WAIT", remaining
    elif remaining > total * 0.2:
        return "⚠️ PREPARE", remaining
    else:
        return "🚀 ENTER NOW", remaining

# ===== SESSION =====
def session_ok():
    hour = datetime.datetime.utcnow().hour
    return 7 <= hour <= 22

# ===== PAIRS =====
PAIRS = [
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD",
    "EURJPY","GBPJPY"
]

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Start Trading", callback_data="forex")]
    ])

def forex_menu():
    keyboard, row = [], []
    for i, pair in enumerate(PAIRS, 1):
        row.append(InlineKeyboardButton(pair[:3]+"/"+pair[3:], callback_data=pair))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def timeframe_menu(pair):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1m", callback_data=f"{pair}_1m"),
         InlineKeyboardButton("5m", callback_data=f"{pair}_5m")]
    ])

def get_analysis(symbol, interval):
    handler = TA_Handler(
        symbol=symbol,
        screener="forex",
        exchange="FX_IDC",
        interval=interval
    )
    return handler.get_analysis()

# ===== SIGNAL ENGINE (UPGRADED) =====
def generate_signal(pair, timeframe):
    try:
        if not session_ok():
            return "⛔ Trade London / NY session only"

        interval_map = {
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES
        }

        analysis = get_analysis(pair, interval_map[timeframe])
        analysis_htf = get_analysis(pair, Interval.INTERVAL_5_MINUTES)

        price = analysis.indicators["close"]
        ema = analysis.indicators["EMA50"]
        rsi = analysis.indicators["RSI"]
        rsi_prev = analysis.indicators.get("RSI[1]", rsi)

        macd = analysis.indicators.get("MACD.macd", 0)
        macd_signal = analysis.indicators.get("MACD.signal", 0)

        # ===== TREND =====
        trend = "UP" if price > ema else "DOWN"

        htf_price = analysis_htf.indicators["close"]
        htf_ema = analysis_htf.indicators["EMA50"]
        htf_trend = "UP" if htf_price > htf_ema else "DOWN"

        if trend != htf_trend:
            return "⛔ MTF Conflict"

        confidence = 0

        # ===== CONDITIONS =====
        if trend == "UP":
            if 53 < rsi < 65:
                confidence += 25
            if rsi > rsi_prev:
                confidence += 15
            if macd > macd_signal:
                confidence += 25
            if price > ema:
                confidence += 20

            signal = "BUY"
        else:
            if 35 < rsi < 47:
                confidence += 25
            if rsi < rsi_prev:
                confidence += 15
            if macd < macd_signal:
                confidence += 25
            if price < ema:
                confidence += 20

            signal = "SELL"

        # ===== FILTER =====
        if confidence < MIN_CONFIDENCE:
            return "⏳ No strong setup"

        decision, seconds = get_entry_decision(timeframe)

        # ===== FINAL MESSAGE =====
        return f"""
💱 {pair}
⏱ {timeframe} (MT4 Manual Mode)

🔥 {signal} SIGNAL

📊 Confidence: {confidence}%

📍 Decision: {decision}
⏳ Time to candle: {seconds}s

🎯 How to execute (MT4):
1. Open {pair}
2. Wait for signal timing
3. Tap {'BUY' if signal=='BUY' else 'SELL'}

⚠️ Skip if candle spikes fast
"""

    except Exception as e:
        print(e)
        return "❌ Error"

# ===== TELEGRAM =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Not authorized")
        return
    await update.message.reply_text("🚀 MT4 SNIPER BOT READY", reply_markup=main_menu())

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "forex":
        await query.edit_message_text("Select Pair:", reply_markup=forex_menu())

    elif data in PAIRS:
        await query.edit_message_text(f"Select TF {data}", reply_markup=timeframe_menu(data))

    elif "_" in data:
        pair, tf = data.split("_")
        result = generate_signal(pair, tf)
        await query.edit_message_text(result)

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
