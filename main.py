import logging
import requests
import os

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TOKEN")

# FAST DATA SOURCE (Binance)
PAIR_MAP = {
    "EURUSD": "EURUSDT",
    "GBPUSD": "GBPUSDT",
    "USDJPY": "BTCUSDT"  # fallback (JPY not available)
}

TIMEFRAMES = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m"
}

user_state = {}

logging.basicConfig(level=logging.INFO)

# ===== GET CANDLES =====
def get_candles(symbol, interval):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=50"
    data = requests.get(url).json()

    candles = []
    for c in data:
        candles.append({
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4])
        })
    return candles

# ===== PATTERN DETECTION =====
def detect_pattern(c):
    c1 = c[-1]
    c2 = c[-2]
    c3 = c[-3]

    def body(x): return abs(x["close"] - x["open"])

    # ENGULFING
    if c2["close"] < c2["open"] and c1["close"] > c1["open"]:
        if c1["close"] > c2["open"] and c1["open"] < c2["close"]:
            return "BUY 📈", "Bullish Engulfing"

    if c2["close"] > c2["open"] and c1["close"] < c1["open"]:
        if c1["close"] < c2["open"] and c1["open"] > c2["close"]:
            return "SELL 📉", "Bearish Engulfing"

    # HAMMER
    if body(c1) < (c1["high"] - c1["low"]) * 0.3 and (c1["close"] - c1["low"]) > body(c1) * 2:
        return "BUY 📈", "Hammer"

    # SHOOTING STAR
    if body(c1) < (c1["high"] - c1["low"]) * 0.3 and (c1["high"] - c1["close"]) > body(c1) * 2:
        return "SELL 📉", "Shooting Star"

    # MORNING STAR
    if c3["close"] < c3["open"] and body(c2) < body(c3) and c1["close"] > c1["open"]:
        return "BUY 📈", "Morning Star"

    # EVENING STAR
    if c3["close"] > c3["open"] and body(c2) < body(c3) and c1["close"] < c1["open"]:
        return "SELL 📉", "Evening Star"

    # DOJI
    if body(c1) < (c1["high"] - c1["low"]) * 0.1:
        return "WAIT ⏸", "Doji"

    return "WAIT ⏸", "No clear pattern"

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[p] for p in PAIR_MAP.keys()]
    await update.message.reply_text(
        "Select Pair:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ===== HANDLE =====
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.message.chat_id

    # STEP 1
    if text in PAIR_MAP:
        user_state[uid] = {"pair": text}
        keyboard = [[t] for t in TIMEFRAMES.keys()]
        await update.message.reply_text(
            f"{text} selected.\nChoose timeframe:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # STEP 2
    if text in TIMEFRAMES:
        pair = user_state[uid]["pair"]
        symbol = PAIR_MAP[pair]
        tf = TIMEFRAMES[text]

        candles = get_candles(symbol, tf)

        signal, pattern = detect_pattern(candles)

        await update.message.reply_text(
            f"📊 {pair} ({symbol})\n⏱ {text}\n\n🔥 Signal: {signal}\n🧠 Pattern: {pattern}"
        )

# ===== RUN =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, handle))

app.run_polling()
