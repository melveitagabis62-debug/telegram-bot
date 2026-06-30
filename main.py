from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from tradingview_ta import TA_Handler, Interval
import datetime
import os

TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [6351041498]

# === TRACKING SYSTEM ===
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

# === ENTRY TIMING ===
def get_entry_timing(timeframe):
    now = datetime.datetime.utcnow()

    if timeframe == "5m":
        total_seconds = 300
        seconds_passed = (now.minute % 5) * 60 + now.second
    elif timeframe == "15m":
        total_seconds = 900
        seconds_passed = (now.minute % 15) * 60 + now.second

    remaining = total_seconds - seconds_passed

    if remaining > total_seconds * 0.5:
        return f"⏳ WAIT ({remaining}s)"
    else:
        return f"🚀 ENTRY ({remaining}s)"

# === SESSION FILTER ===
def get_trading_session():
    hour = datetime.datetime.utcnow().hour

    if 7 <= hour < 13:
        return "London"
    elif 13 <= hour < 17:
        return "Overlap"
    elif 17 <= hour < 22:
        return "NewYork"
    return None

# === PAIRS ===
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "GBPJPY", "EURGBP", "XAUUSD"]

TIMEFRAMES = ["5m", "15m"]  # HIGH ACCURACY MODE

LAST_SIGNAL = {}

# === ANALYSIS ===
def get_analysis(symbol, interval):
    handler = TA_Handler(
        symbol=symbol,
        screener="forex",
        exchange="FX_IDC",
        interval=interval
    )
    return handler.get_analysis()

# === SIGNAL LOGIC (UPGRADED ACCURACY) ===
def generate_signal(pair, tf):
    try:
        if not get_trading_session():
            return None

        interval_map = {
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }

        analysis = get_analysis(pair, interval_map[tf])

        rsi = analysis.indicators["RSI"]
        ema50 = analysis.indicators["EMA50"]
        price = analysis.indicators["close"]
        macd = analysis.indicators.get("MACD.macd", 0)
        macd_signal = analysis.indicators.get("MACD.signal", 0)

        trend = "UP" if price > ema50 else "DOWN"

        # STRONGER FILTERS
        distance = abs(price - ema50)
        strong_trend = distance > price * 0.0007

        macd_power = abs(macd - macd_signal)
        strong_macd = macd_power > 0.00007

        # === IMPROVED SIGNAL LOGIC ===

rsi_prev = analysis.indicators.get("RSI[1]", rsi)
rsi_up = rsi > rsi_prev
rsi_down = rsi < rsi_prev

pullback_buy = price <= ema50 * 1.001
pullback_sell = price >= ema50 * 0.999

macd_confirm_buy = macd > macd_signal and macd > 0
macd_confirm_sell = macd < macd_signal and macd < 0

if trend == "UP":
    if (
        52 < rsi < 65
        and rsi_up
        and macd_confirm_buy
        and strong_trend
        and pullback_buy
    ):
        signal = "🔥 STRONG BUY"
    else:
        return None

else:
    if (
        35 < rsi < 48
        and rsi_down
        and macd_confirm_sell
        and strong_trend
        and pullback_sell
    ):
        signal = "🔥 STRONG SELL"
    else:
        return None
    

        timing = get_entry_timing(tf)
        amount = get_trade_amount()

        expiration = "5-10 min" if tf == "5m" else "15-30 min"

        return f"""
📊 AUTO SNIPER MODE (HIGH ACCURACY)

💱 {pair}
⏱ TF: {tf}

{signal}
{timing}

💰 Amount: {amount}
📉 Martingale: {MARTINGALE_STEP}

⏳ Expiration: {expiration}

📊 RSI: {round(rsi,2)}
📊 Trend: {trend}
📊 MACD: {'Bullish' if macd > macd_signal else 'Bearish'}
📊 Strength: {'Strong' if strong_trend else 'Weak'}
"""

    except:
        return None

# === AUTO LOOP ===
async def auto_signal_loop(context: ContextTypes.DEFAULT_TYPE):
    global LAST_SIGNAL

    for pair in PAIRS:
        for tf in TIMEFRAMES:
            key = f"{pair}_{tf}"

            signal = generate_signal(pair, tf)

            if signal:
                if LAST_SIGNAL.get(key) == signal:
                    continue

                LAST_SIGNAL[key] = signal

                for user in ALLOWED_USERS:
                    await context.bot.send_message(chat_id=user, text=signal)

# === START ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Not authorized")
        return

    await update.message.reply_text(
        "🤖 AUTO BOT RUNNING (5m & 15m High Accuracy)\nNo manual clicking needed."
    )

# === APP ===
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

# AUTO SCAN EVERY 60s
app.job_queue.run_repeating(auto_signal_loop, interval=60, first=10)

app.run_polling()
        
