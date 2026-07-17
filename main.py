from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.ext import MessageHandler, filters

from tradingview_ta import TA_Handler, Interval
import os
import datetime

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

    if timeframe == "1m":
        total = 60
        passed = now.second
    elif timeframe == "5m":
        total = 300
        passed = (now.minute % 5) * 60 + now.second
    else:
        total = 900
        passed = (now.minute % 15) * 60 + now.second

    remain = total - passed

    if remain > total * 0.55:
        return f"⏳ WAIT ({remain}s)"
    elif remain > total * 0.25:
        return f"⚠️ PREPARE ({remain}s)"
    else:
        return f"🔥 ENTER NOW ({remain}s)"

# === SESSION ===
async def session_notifier(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.utcnow()
    h = now.hour

    if 7 <= h < 13:
        msg = "🇬🇧 London Session"
    elif 13 <= h < 17:
        msg = "🔥 London-NY Overlap (BEST)"
    elif 17 <= h < 22:
        msg = "🇺🇸 New York Session"
    else:
        return

    for uid in ALLOWED_USERS:
        await context.bot.send_message(uid, f"{msg}\n\n💡 Alligator RSI Sniper Active")

# === UI ===
def result_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ WIN", callback_data="result_win"),
         InlineKeyboardButton("❌ LOSS", callback_data="result_loss")]
    ])

PAIRS = ["EURUSD"]
CRYPTO_PAIRS = ["BTCUSDT"]

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Forex", callback_data="forex")],
        [InlineKeyboardButton("💰 Crypto", callback_data="crypto")]
    ])

def forex_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("EUR/USD", callback_data="EURUSD")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
    ])

def crypto_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("BTC/USDT", callback_data="crypto_BTCUSDT")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
    ])

def timeframe_menu(pair):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1m", callback_data=f"{pair}_1m"),
         InlineKeyboardButton("5m", callback_data=f"{pair}_5m")],
        [InlineKeyboardButton("15m", callback_data=f"{pair}_15m")]
    ])

# === TA ===
INTERVAL_MAP = {
    "1m": Interval.INTERVAL_1_MINUTE,
    "5m": Interval.INTERVAL_5_MINUTES,
    "15m": Interval.INTERVAL_15_MINUTES
}

def get_analysis(pair, tf):
    try:
        return TA_Handler(
            symbol=pair,
            screener="crypto" if "USDT" in pair else "forex",
            exchange="BINANCE" if "USDT" in pair else "FX_IDC",
            interval=tf
        ).get_analysis()
    except:
        return None

# === SIGNAL ENGINE ===
def generate_signal(pair, timeframe):
    try:
        analysis = get_analysis(pair, INTERVAL_MAP[timeframe])
        if not analysis:
            return "❌ Data error"

        ind = analysis.indicators

        price = ind.get("close")
        open_p = ind.get("open")
        high = ind.get("high")
        low = ind.get("low")

        if None in (price, open_p, high, low):
            return "❌ Missing data"

        # === INDICATORS ===
        rsi = ind.get("RSI", 50)
        jaw = ind.get("Alligator.Jaw")
        teeth = ind.get("Alligator.Teeth")
        lips = ind.get("Alligator.Lips")

        if None in (jaw, teeth, lips):
            return "❌ Alligator missing"

        # === TREND ===
        uptrend = lips > teeth > jaw and price > lips
        downtrend = lips < teeth < jaw and price < lips

        # === PULLBACK (IMPORTANT) ===
        near_alligator = abs(price - lips) / price < 0.0015

        # === CANDLE ===
        body = abs(price - open_p)
        range_ = max(high - low, 1e-9)

        bullish = price > open_p
        bearish = price < open_p

        body_ratio = body / range_

        upper_wick = high - max(price, open_p)
        lower_wick = min(price, open_p) - low

        strong_body = body_ratio > 0.5
        engulf = body_ratio > 0.6
        reject_buy = lower_wick > body * 1.5
        reject_sell = upper_wick > body * 1.5

        signal = None
        reasons = []

        # === BUY ===
        if uptrend and rsi > 50 and near_alligator:
            if bullish and (strong_body or engulf or reject_buy):
                signal = "BUY"
                reasons = ["Alligator UP", "RSI > 50", "Pullback entry", "Bullish candle"]

        # === SELL ===
        elif downtrend and rsi < 50 and near_alligator:
            if bearish and (strong_body or engulf or reject_sell):
                signal = "SELL"
                reasons = ["Alligator DOWN", "RSI < 50", "Pullback entry", "Bearish candle"]

        if not signal:
            return "⏳ No clean setup (waiting pullback)"

        timing = get_entry_timing(timeframe)
        amount = get_trade_amount()

        expiration = {
            "1m": "1-3 min",
            "5m": "5-10 min",
            "15m": "15-30 min"
        }[timeframe]

        arrow = "🟢 BUY" if signal == "BUY" else "🔴 SELL"

        return f"""
🔥 **Alligator RSI SNIPER**

💱 {pair}
⏱ TF: {timeframe}

{arrow} @ {round(price,5)}
{timing}

📊 RSI: {round(rsi,1)}

🧠 Reason:
- {" | ".join(reasons)}

💰 Amount: {amount}
📉 Martingale: {MARTINGALE_STEP}

⏳ Exp: {expiration}
"""

    except Exception as e:
        print(e)
        return "❌ Signal error"

# === BOT ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Not allowed")
        return
    await update.message.reply_text("🚀 Alligator RSI Sniper Bot", reply_markup=main_menu())

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global WIN, LOSS

    q = update.callback_query
    await q.answer()
    d = q.data

    if d == "result_win":
        WIN += 1
        reset_martingale()
        await q.edit_message_text(f"✅ WIN\n{WIN}-{LOSS}")

    elif d == "result_loss":
        LOSS += 1
        increase_martingale()
        await q.edit_message_text(f"❌ LOSS\n{WIN}-{LOSS}\nMG {MARTINGALE_STEP}")

    elif d == "forex":
        await q.edit_message_text("Choose:", reply_markup=forex_menu())

    elif d == "crypto":
        await q.edit_message_text("Choose:", reply_markup=crypto_menu())

    elif d == "back_main":
        await q.edit_message_text("Menu:", reply_markup=main_menu())

    elif d in PAIRS:
        await q.edit_message_text(f"TF for {d}", reply_markup=timeframe_menu(d))

    elif d.startswith("crypto_"):
        pair = d.replace("crypto_", "")
        await q.edit_message_text(f"TF for {pair}", reply_markup=timeframe_menu(pair))

    elif "_" in d:
        pair, tf = d.split("_")
        res = generate_signal(pair, tf)
        await q.edit_message_text(res, parse_mode="Markdown", reply_markup=result_buttons())

# === RUN ===
app = ApplicationBuilder().token(TOKEN).build()

app.job_queue.run_repeating(session_notifier, interval=1200, first=10)

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_buttons))

app.run_polling()
