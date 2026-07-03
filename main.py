from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

import requests
import os
from datetime import datetime

TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [6351041498]

PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
    "USDCAD", "USDCHF", "NZDUSD"
]

SYMBOL = [
    "BTCUSDT",
]
INTERVAL = "5m"
LIMIT = 100

# ================= MENU =================

def main_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📊 Forex", callback_data="forex")]])

def forex_menu():
    keyboard = []
    row = []

    for i, pair in enumerate(PAIRS, 1):
        display = pair[:3] + "/" + pair[3:]
        row.append(InlineKeyboardButton(display, callback_data=pair))

        if i % 2 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def timeframe_menu(pair):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1m", callback_data=f"{pair}_1m"),
         InlineKeyboardButton("5m", callback_data=f"{pair}_5m")],
        [InlineKeyboardButton("15m", callback_data=f"{pair}_15m")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_forex")]
    ])

# ================= MARKET DATA =================

def get_ohlc(symbol, interval="5m", limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}

    data = requests.get(url, params=params).json()

    candles = []
    for c in data:
        candles.append({
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4])
        })
    return candles

# ================= SMC LOGIC =================

def get_snr_zones(candles):
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    return min(lows[-20:]), max(highs[-20:])

def detect_liquidity_sweep(candles, support, resistance):
    prev = candles[-2]
    last = candles[-1]

    sweep_down = prev["low"] < support and last["close"] > support
    sweep_up = prev["high"] > resistance and last["close"] < resistance

    return sweep_down, sweep_up

def detect_bos(candles):
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    return highs[-1] > highs[-2], lows[-1] < lows[-2]

def get_order_block(candles):
    for c in candles[-6:]:
        body = abs(c["close"] - c["open"])
        rng = c["high"] - c["low"]
        if body > rng * 0.6:
            return c["low"], c["high"]
    return None, None

def detect_fvg(candles):
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        if c1["high"] < c3["low"]:
            return ("bullish", c1["high"], c3["low"])
        if c1["low"] > c3["high"]:
            return ("bearish", c3["high"], c1["low"])
    return None

def is_kill_zone():
    hour = datetime.utcnow().hour
    return (7 <= hour <= 10) or (13 <= hour <= 16)

# ================= SIGNAL =================

def generate_signal(pair, timeframe):
    try:
        symbol = pair + "T"

        tf_map = {"1m": "1m", "5m": "5m", "15m": "15m"}
        candles = get_ohlc(symbol, tf_map[timeframe], 100)

        price = candles[-1]["close"]

        support, resistance = get_snr_zones(candles)
        sweep_down, sweep_up = detect_liquidity_sweep(candles, support, resistance)
        bos_up, bos_down = detect_bos(candles)
        ob_low, ob_high = get_order_block(candles)
        fvg = detect_fvg(candles)

        signal = "HOLD"
        confidence = 0

        # 🔥 BUY
        if sweep_down and bos_up and is_kill_zone():
            if ob_low and ob_high and ob_low <= price <= ob_high:
                signal = "BUY"
                confidence = 92

        # 🔥 SELL
        elif sweep_up and bos_down and is_kill_zone():
            if ob_low and ob_high and ob_low <= price <= ob_high:
                signal = "SELL"
                confidence = 92

        # 🔥 FVG boost
        if fvg:
            fvg_type, low, high = fvg
            if signal == "BUY" and fvg_type == "bullish" and low <= price <= high:
                confidence += 5
            if signal == "SELL" and fvg_type == "bearish" and low <= price <= high:
                confidence += 5

        if signal == "HOLD":
            return "🟡 HOLD (No smart money setup)"

        return f"""
📊 ULTRA SMC SIGNAL: {signal}
💰 Price: {price}
🔥 Confidence: {confidence}%
📍 Support: {support}
📍 Resistance: {resistance}
"""

    except Exception as e:
        return f"Error: {str(e)}"

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Access Denied")
        return

    keyboard = [["🚀 Start Bot"]]
    await update.message.reply_text("Click below:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🚀 Start Bot":
        await update.message.reply_text("🚀 ULTRA SMC BOT", reply_markup=main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
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
        await query.edit_message_text("🚀 ULTRA SMC BOT", reply_markup=main_menu())

    elif data == "back_forex":
        await query.edit_message_text("Select Pair:", reply_markup=forex_menu())

# ================= RUN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, start_button))
app.add_handler(CallbackQueryHandler(button_handler))

print("🔥 ULTRA SMC BOT RUNNING...")
app.run_polling()
