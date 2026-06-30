from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.ext import MessageHandler, filters

from tradingview_ta import TA_Handler, Interval
import os
import datetime

TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [6351041498]

# ===== TRACKING =====
WIN = 0
LOSS = 0
MARTINGALE_STEP = 0
MARTINGALE_ENABLED = True
LAST_SIGNAL = {}

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

# ===== ENTRY TIMING =====
def get_entry_timing(timeframe):
    now = datetime.datetime.utcnow()

    if timeframe == "5m":
        total_seconds = 300
        seconds_passed = (now.minute % 5) * 60 + now.second

    elif timeframe == "15m":
        total_seconds = 900
        seconds_passed = (now.minute % 15) * 60 + now.second

    remaining = total_seconds - seconds_passed

    if remaining > total_seconds * 0.6:
        return f"⏳ WAIT ({remaining}s)"
    elif remaining > total_seconds * 0.2:
        return f"⚠️ PREPARE ({remaining}s)"
    else:
        return f"🔥 ENTER NOW ({remaining}s)"

# ===== SESSION =====
def get_trading_session():
    hour = datetime.datetime.utcnow().hour
    if 7 <= hour < 13:
        return "🇬🇧 London"
    elif 13 <= hour < 17:
        return "🔥 Overlap"
    elif 17 <= hour < 22:
        return "🇺🇸 New York"
    return None

# ===== ANALYSIS =====
def get_analysis(symbol, interval):
    handler = TA_Handler(
        symbol=symbol,
        screener="forex",
        exchange="FX_IDC",
        interval=interval
    )
    return handler.get_analysis()

# ===== HYBRID SNIPER =====
def generate_signal(pair, timeframe):
    try:
        interval_map = {
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }

        hour = datetime.datetime.utcnow().hour
        if not (7 <= hour <= 22):
            return "⛔ Session closed"

        analysis = get_analysis(pair, interval_map[timeframe])
        higher_tf = "15m"
        analysis_htf = get_analysis(pair, interval_map[higher_tf])

        rsi = analysis.indicators["RSI"]
        ema50 = analysis.indicators["EMA50"]
        price = analysis.indicators["close"]
        open_price = analysis.indicators["open"]
        high = analysis.indicators["high"]
        low = analysis.indicators["low"]

        prev_open = analysis.indicators.get("open[1]", open_price)
        prev_close = analysis.indicators.get("close[1]", price)

        trend = "UP" if price > ema50 else "DOWN"
        htf_trend = "UP" if analysis_htf.indicators["close"] > analysis_htf.indicators["EMA50"] else "DOWN"

        if trend != htf_trend:
            return "⛔ MTF conflict"

        # CHOPPY FILTER
        if (high - low)/price < 0.0008 and abs(price - ema50)/price < 0.0005 and 45 < rsi < 55:
            return "⛔ Choppy"

        # FAKE BREAKOUT
        if (high - low) > abs(price - open_price) * 2:
            return "⛔ Fake breakout"

        # S/R ZONE
        near_resistance = price >= high * 0.9985
        near_support = price <= low * 1.0015

        # PRICE ACTION
        engulf = (
            (price > open_price and prev_close < prev_open and price > prev_open) or
            (price < open_price and prev_close > prev_open and price < prev_open)
        )

        body = abs(price - open_price)
        upper_wick = high - max(open_price, price)
        lower_wick = min(open_price, price) - low

        wick_reject = upper_wick > body * 2 or lower_wick > body * 2

        rsi_up = rsi > analysis.indicators.get("RSI[1]", rsi)
        rsi_down = rsi < analysis.indicators.get("RSI[1]", rsi)

        signal = None
        strength = ""

        if trend == "UP" and near_support:
            if engulf and wick_reject and rsi_up:
                signal = "BUY"
                strength = "🔥 STRONG BUY"
            elif (engulf or wick_reject) and rsi_up:
                signal = "BUY"
                strength = "⚡ QUICK BUY"

        elif trend == "DOWN" and near_resistance:
            if engulf and wick_reject and rsi_down:
                signal = "SELL"
                strength = "🔥 STRONG SELL"
            elif (engulf or wick_reject) and rsi_down:
                signal = "SELL"
                strength = "⚡ QUICK SELL"

        if not signal:
            return "⏳ No setup"

        expiration = "5-10 min" if timeframe == "5m" else "15-30 min"
        amount = get_trade_amount()
        timing = get_entry_timing(timeframe)

        action = f"🟢 BUY @ {round(price,5)}" if signal == "BUY" else f"🔴 SELL @ {round(price,5)}"

        return f"""
📊 HYBRID SNIPER AUTO

💱 {pair} | {timeframe}
{strength}
{action}
{timing}

🎯 Trend: {trend} (HTF: {htf_trend})
📊 RSI: {round(rsi,2)}

💰 Amount: {amount}
📉 Martingale: {MARTINGALE_STEP}

⏳ Exp: {expiration}
"""

    except:
        return "❌ Error"

# ===== AUTO SIGNAL =====
PAIRS = [
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD",
    "EURJPY","GBPJPY","AUDJPY"
]

async def auto_signal(context: ContextTypes.DEFAULT_TYPE):
    global LAST_SIGNAL

    for pair in PAIRS:
        for tf in ["5m", "15m"]:

            result = generate_signal(pair, tf)

            if any(x in result for x in ["⛔", "⏳"]):
                continue

            key = f"{pair}_{tf}"
            if LAST_SIGNAL.get(key) == result:
                continue

            LAST_SIGNAL[key] = result

            for user in ALLOWED_USERS:
                await context.bot.send_message(chat_id=user, text=result)

# ===== BUTTONS =====
def result_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ WIN", callback_data="result_win"),
            InlineKeyboardButton("❌ LOSS", callback_data="result_loss")
        ]
    ])

# ===== TELEGRAM =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 AUTO SNIPER RUNNING...")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global WIN, LOSS

    query = update.callback_query
    await query.answer()

    if query.data == "result_win":
        WIN += 1
        reset_martingale()
    elif query.data == "result_loss":
        LOSS += 1
        increase_martingale()

    await query.edit_message_text(f"Wins: {WIN} | Loss: {LOSS}")

app = ApplicationBuilder().token(TOKEN).build()

# 🔥 AUTO MODE EVERY 60 SEC
app.job_queue.run_repeating(auto_signal, interval=120, first=10)

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_buttons))

app.run_polling()
