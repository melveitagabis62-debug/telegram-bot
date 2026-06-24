import pandas as pd
import pandas_ta as ta
import yfinance as yf
import asyncio
import os
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

# 🔐 Use Railway environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

MANUAL_MODE = True
ACTIVE_CHATS = set()

# =============================
# 🔍 MARKET SESSION FILTER
# =============================
def is_trading_session():
    now = datetime.utcnow().hour
    return 7 <= now <= 20


# =============================
# 📊 SUPPORT / RESISTANCE
# =============================
def get_sr_levels(data):
    recent = data.tail(50)
    support = recent["Low"].min()
    resistance = recent["High"].max()
    return support, resistance


# =============================
# 🧠 ANALYSIS ENGINE
# =============================
def analyze_pair(symbol):
    try:
        m15 = yf.download(symbol, interval="15m", period="5d", progress=False)
        h1 = yf.download(symbol, interval="1h", period="10d", progress=False)

        if len(m15) < 100 or len(h1) < 100:
            return None

        m15["EMA20"] = ta.ema(m15["Close"], length=20)
        m15["EMA50"] = ta.ema(m15["Close"], length=50)
        m15["RSI"] = ta.rsi(m15["Close"], length=14)

        h1["EMA50"] = ta.ema(h1["Close"], length=50)
        h1["EMA200"] = ta.ema(h1["Close"], length=200)

        latest = m15.iloc[-1]
        prev = m15.iloc[-2]
        h1_latest = h1.iloc[-1]

        trend = None
        if h1_latest["EMA50"] > h1_latest["EMA200"]:
            trend = "BULL"
        elif h1_latest["EMA50"] < h1_latest["EMA200"]:
            trend = "BEAR"

        bullish_cross = prev["EMA20"] < prev["EMA50"] and latest["EMA20"] > latest["EMA50"]
        bearish_cross = prev["EMA20"] > prev["EMA50"] and latest["EMA20"] < latest["EMA50"]

        support, resistance = get_sr_levels(m15)
        price = latest["Close"]

        near_support = abs(price - support) / price < 0.002
        near_resistance = abs(price - resistance) / price < 0.002

        score = 0
        direction = None

        if trend == "BULL":
            score += 1
        if bullish_cross:
            score += 1
        if latest["RSI"] > 55:
            score += 1
        if near_support:
            score += 1

        if score >= 3:
            direction = "CALL"

        score_put = 0

        if trend == "BEAR":
            score_put += 1
        if bearish_cross:
            score_put += 1
        if latest["RSI"] < 45:
            score_put += 1
        if near_resistance:
            score_put += 1

        if score_put >= 3:
            direction = "PUT"
            score = score_put

        if direction is None:
            return None

        confidence = "LOW"
        if score == 3:
            confidence = "MEDIUM"
        elif score >= 4:
            confidence = "HIGH"

        return {
            "direction": direction,
            "confidence": confidence,
            "price": round(price, 5)
        }

    except Exception:
        return None


# =============================
# 📤 FORMAT MESSAGE
# =============================
def format_signal(pair, data):
    return (
        f"📊 {pair}\n"
        f"Direction: {data['direction']}\n"
        f"Confidence: {data['confidence']}\n"
        f"Entry: {data['price']}\n"
        f"Expiry: 15 min\n"
        f"---------------------\n"
    )


# =============================
# 🤖 AUTO SIGNAL LOOP
# =============================
async def send_signals(context: ContextTypes.DEFAULT_TYPE):
    global MANUAL_MODE

    if MANUAL_MODE:
        return

    if not is_trading_session():
        return

    pairs = {
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "JPY=X"
    }

    msg = "🤖 AUTO SIGNALS\n\n"

    for pair, ticker in pairs.items():
        result = await asyncio.to_thread(analyze_pair, ticker)

        if result:
            msg += format_signal(pair, result)

    if msg.strip() == "🤖 AUTO SIGNALS":
        return

    for chat_id in ACTIVE_CHATS:
        await context.bot.send_message(chat_id=chat_id, text=msg)


# =============================
# 📩 COMMANDS
# =============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ACTIVE_CHATS.add(chat_id)
    await update.message.reply_text("✅ Bot Activated")


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pairs = {
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "JPY=X"
    }

    msg = "📊 MANUAL SIGNALS\n\n"

    for pair, ticker in pairs.items():
        result = await asyncio.to_thread(analyze_pair, ticker)

        if result:
            msg += format_signal(pair, result)

    await update.message.reply_text(msg)


async def manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MANUAL_MODE
    MANUAL_MODE = True
    await update.message.reply_text("🛑 Manual Mode")


async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MANUAL_MODE
    MANUAL_MODE = False
    await update.message.reply_text("🤖 Auto Mode Enabled")


# =============================
# 🚀 RUN BOT
# =============================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("signal", signal))
app.add_handler(CommandHandler("manual", manual))
app.add_handler(CommandHandler("auto", auto))

app.job_queue.run_repeating(send_signals, interval=300, first=10)

app.run_polling()
