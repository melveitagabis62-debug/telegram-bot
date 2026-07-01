from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from tradingview_ta import TA_Handler, Interval
import datetime
import os
import logging
import asyncio

# === CONFIG ===
TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [int(uid) for uid in os.getenv("ALLOWED_USERS", "6351041498").split(",")]
BASE_AMOUNT = float(os.getenv("BASE_AMOUNT", 1.0))
MARTINGALE_ENABLED = os.getenv("MARTINGALE_ENABLED", "True").lower() == "true"

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === TRACKING ===
WIN = 0
LOSS = 0
MARTINGALE_STEP = 0

def get_trade_amount(base=BASE_AMOUNT):
    if not MARTINGALE_ENABLED:
        return base
    return base * (2 ** MARTINGALE_STEP)

def reset_martingale():
    global MARTINGALE_STEP
    MARTINGALE_STEP = 0
    logger.info("Martingale reset")

def increase_martingale():
    global MARTINGALE_STEP
    MARTINGALE_STEP += 1
    logger.info(f"Martingale step increased to {MARTINGALE_STEP}")

# === TIMING & SESSION ===
def get_entry_timing(timeframe):
    now = datetime.datetime.utcnow()
    if timeframe == "5m":
        total = 300
        passed = (now.minute % 5) * 60 + now.second
    elif timeframe == "15m":
        total = 900
        passed = (now.minute % 15) * 60 + now.second
    else:
        return "⏳ N/A"
    remaining = total - passed
    return f"🚀 ENTRY ({remaining}s)" if remaining <= total * 0.5 else f"⏳ WAIT ({remaining}s)"

def is_trading_session():
    hour = datetime.datetime.utcnow().hour
    return 7 <= hour <= 22

# === PAIRS & TIMEFRAMES ===
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "GBPJPY", "EURGBP", "XAUUSD"]
TIMEFRAMES = ["5m", "15m"]

LAST_SIGNAL = {}
BOT_RUNNING = True

# === ANALYSIS ===
def get_analysis(symbol, interval):
    handler = TA_Handler(
        symbol=symbol,
        screener="forex",
        exchange="FX_IDC",
        interval=interval
    )
    return handler.get_analysis()

# === SIGNAL GENERATOR (Improved) ===
def generate_signal(pair, timeframe):
    try:
        if not is_trading_session():
            return None  # Skip silently outside session

        interval_map = {
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }

        analysis = get_analysis(pair, interval_map[timeframe])

        rsi = analysis.indicators["RSI"]
        ema50 = analysis.indicators["EMA50"]
        price = analysis.indicators["close"]
        macd = analysis.indicators.get("MACD.macd", 0)
        macd_signal = analysis.indicators.get("MACD.signal", 0)

        trend = "UP" if price > ema50 else "DOWN"

        # Filters (kept similar but cleaned)
        distance = abs(price - ema50)
        strong_momentum = distance > price * 0.0008
        strong_macd = abs(macd - macd_signal) > 0.00008
        macd_aligned = (macd > 0 and trend == "UP") or (macd < 0 and trend == "DOWN")
        clean_trend = (distance / price) > 0.0005
        entry_ok = distance < (price * 0.0016)
        rsi_prev = analysis.indicators.get("RSI[1]", rsi)
        rsi_up = rsi > rsi_prev
        rsi_down = rsi < rsi_prev
        pullback_ok = distance < (price * 0.0011)
        stable_market = abs(price - analysis.indicators.get("close[1]", price)) < (price * 0.0015)

        result = None
        if trend == "UP":
            if (53 < rsi < 61 and rsi_up and macd > macd_signal and strong_macd and
                macd_aligned and strong_momentum and clean_trend and entry_ok and
                pullback_ok and stable_market):
                result = f"🔥 STRONG BUY\n🟢 BUY @ {round(price,5)}"
            elif (50 < rsi < 64 and rsi_up and macd > macd_signal and strong_macd and
                  macd_aligned and clean_trend and stable_market):
                result = f"⚡ QUICK BUY\n🟢 BUY @ {round(price,5)}"
        else:
            if (39 < rsi < 47 and rsi_down and macd < macd_signal and strong_macd and
                macd_aligned and strong_momentum and clean_trend and entry_ok and
                pullback_ok and stable_market):
                result = f"🔥 STRONG SELL\n🔴 SELL @ {round(price,5)}"
            elif (36 < rsi < 50 and rsi_down and macd < macd_signal and strong_macd and
                  macd_aligned and clean_trend and stable_market):
                result = f"⚡ QUICK SELL\n🔴 SELL @ {round(price,5)}"

        if not result:
            return None

        timing = get_entry_timing(timeframe)
        amount = get_trade_amount()

        return f"""
📊 **Sigma AI v8 - Fully Automated**

💱 Pair: {pair} | ⏱ TF: {timeframe}
{result}
{timing}

🎯 ULTRA FILTERED • High Accuracy
💰 Amount: {amount:.2f} | 📉 Martingale: {MARTINGALE_STEP}

⏳ Exp: {timeframe == "5m" and "5-10 min" or "15-30 min"}
RSI: {round(rsi,2)} | Trend: {trend} | Stability: {'Stable' if stable_market else 'Volatile'}
"""

    except Exception as e:
        logger.error(f"Error generating signal for {pair} {timeframe}: {e}")
        return None

# === AUTO LOOP ===
async def auto_signal_loop(context: ContextTypes.DEFAULT_TYPE):
    global BOT_RUNNING
    if not BOT_RUNNING:
        return

    for pair in PAIRS:
        for tf in TIMEFRAMES:
            key = f"{pair}_{tf}"
            signal = generate_signal(pair, tf)

            if signal and LAST_SIGNAL.get(key) != signal:
                LAST_SIGNAL[key] = signal
                for user in ALLOWED_USERS:
                    try:
                        await context.bot.send_message(chat_id=user, text=signal, parse_mode='Markdown')
                    except Exception as e:
                        logger.error(f"Failed to send to {user}: {e}")

# === COMMANDS ===
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Not authorized")
        return
    global BOT_RUNNING
    BOT_RUNNING = True
    await update.message.reply_text("✅ **Bot Started** - Fully automated signals running (every 60s)")

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        return
    global BOT_RUNNING
    BOT_RUNNING = False
    await update.message.reply_text("⏹️ **Bot Stopped**")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        return
    status = "🟢 Running" if BOT_RUNNING else "🔴 Stopped"
    await update.message.reply_text(
        f"**Sigma AI Status**\n"
        f"Status: {status}\n"
        f"Martingale Step: {MARTINGALE_STEP}\n"
        f"Base Amount: {BASE_AMOUNT}\n"
        f"Pairs: {len(PAIRS)} | TFs: {TIMEFRAMES}"
    )

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        return
    reset_martingale()
    await update.message.reply_text("✅ Martingale Reset")

# === MAIN ===
if __name__ == "__main__":
    if not TOKEN:
        logger.error("TOKEN environment variable not set!")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))

    # Start auto loop immediately
    app.job_queue.run_repeating(auto_signal_loop, interval=60, first=5)

    logger.info("Sigma AI Fully Automated Bot Starting...")
    app.run_polling()
