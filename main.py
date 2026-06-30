from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from tradingview_ta import TA_Handler, Interval
import datetime
import os

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [6351041498]

# ================= TRACKING =================
WIN = 0
LOSS = 0
MARTINGALE_STEP = 0
MARTINGALE_ENABLED = True

def get_trade_amount(base=1):
    if not MARTINGALE_ENABLED:
        return base
    return base * (2 ** MARTINGALE_STEP)

def reset_martingale():
    global MARTINGALE_STEP
    MARTINGALE_STEP = 0

def increase_martingale():
    global MARTINGALE_STEP
    MARTINGALE_STEP += 1

# ================= PAIRS =================
PAIRS = [
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF",
    "EURJPY","GBPJPY"
]

# ================= ANALYSIS =================
def get_analysis(symbol, interval):
    handler = TA_Handler(
        symbol=symbol,
        screener="forex",
        exchange="FX_IDC",
        interval=interval
    )
    return handler.get_analysis()

# ================= CANDLE LOGIC =================
def detect_engulfing(open_p, close_p, prev_open, prev_close):
    return (close_p > open_p and prev_close < prev_open) or \
           (close_p < open_p and prev_close > prev_open)

def rejection_wick(open_p, close_p, high, low):
    body = abs(close_p - open_p)
    upper_wick = high - max(open_p, close_p)
    lower_wick = min(open_p, close_p) - low
    return upper_wick > body * 2 or lower_wick > body * 2

# ================= SIGNAL ENGINE =================
def generate_signal(pair):
    try:
        # TRADE SESSION FILTER
        hour = datetime.datetime.utcnow().hour
        if not (7 <= hour <= 22):
            return None

        # MULTI TF
        tf1 = get_analysis(pair, Interval.INTERVAL_1_MINUTE)
        tf5 = get_analysis(pair, Interval.INTERVAL_5_MINUTES)
        tf15 = get_analysis(pair, Interval.INTERVAL_15_MINUTES)

        price = tf1.indicators["close"]

        rsi1 = tf1.indicators["RSI"]
        ema1 = tf1.indicators["EMA50"]
        ema5 = tf5.indicators["EMA50"]
        ema15 = tf15.indicators["EMA50"]

        high = tf1.indicators["high"]
        low = tf1.indicators["low"]
        open_price = tf1.indicators["open"]

        # TREND ALIGNMENT
        trend1 = "UP" if price > ema1 else "DOWN"
        trend5 = "UP" if price > ema5 else "DOWN"
        trend15 = "UP" if price > ema15 else "DOWN"

        if not (trend1 == trend5 == trend15):
            return None

        trend = trend1

        # VOLATILITY FILTER
        if (high - low) / price < 0.0008:
            return None

        # RSI FILTER
        if trend == "UP" and rsi1 < 50:
            return None
        if trend == "DOWN" and rsi1 > 50:
            return None

        # SUPPORT / RESISTANCE
        support = low
        resistance = high

        near_support = abs(price - support) / price < 0.0015
        near_resistance = abs(price - resistance) / price < 0.0015

        # CANDLE CONFIRMATION
        engulf = detect_engulfing(open_price, price, open_price, price)
        wick = rejection_wick(open_price, price, high, low)

        signal = None

        if trend == "UP" and near_support and (engulf or wick):
            signal = "BUY"

        elif trend == "DOWN" and near_resistance and (engulf or wick):
            signal = "SELL"

        if not signal:
            return None

        confidence = 4
        if engulf: confidence += 1
        if wick: confidence += 1

        direction = "🟢 BUY" if signal == "BUY" else "🔴 SELL"
        amount = get_trade_amount()

        return f"""
🚀 AUTO SNIPER SIGNAL

💱 Pair: {pair}
📊 Direction: {direction}
🔥 Confidence: {confidence}/6

⏱ Entry: 1m
📈 Confirm: 5m + 15m
⏳ Expiration: 2-5 min

💰 Amount: {amount}
📉 Martingale: {MARTINGALE_STEP}
"""

    except:
        return None

# ================= AUTO SIGNAL LOOP =================
async def auto_signal(context: ContextTypes.DEFAULT_TYPE):
    for pair in PAIRS:
        signal = generate_signal(pair)

        if signal:
            for user_id in ALLOWED_USERS:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=signal
                )

# ================= START COMMAND =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Not authorized")
        return
    await update.message.reply_text("🚀 AUTO BOT ACTIVATED")

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

# RUN AUTO EVERY 60s
app.job_queue.run_repeating(auto_signal, interval=60, first=10)

app.run_polling()
