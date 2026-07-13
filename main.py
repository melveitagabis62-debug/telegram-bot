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

def get_entry_timing(timeframe):
    now = datetime.datetime.utcnow()
    if timeframe == "5s":
        total_seconds = 5
        seconds_passed = now.second % 5
    elif timeframe == "15s":
        total_seconds = 15
        seconds_passed = now.second % 15
    elif timeframe == "30s":
        total_seconds = 30
        seconds_passed = now.second % 30
    elif timeframe == "1m":
        total_seconds = 60
        seconds_passed = now.second
    else:  # 5m
        total_seconds = 300
        seconds_passed = (now.minute % 5) * 60 + now.second

    remaining = total_seconds - seconds_passed
    if remaining > total_seconds * 0.6:
        return f"⏳ WAIT ({remaining}s)"
    elif remaining > total_seconds * 0.25:
        return f"⚠️ PREPARE ({remaining}s)"
    else:
        return f"🔥 ENTER NOW ({remaining}s)"

async def session_notifier(context: ContextTypes.DEFAULT_TYPE):
    for user_id in ALLOWED_USERS:
        await context.bot.send_message(chat_id=user_id, text="🚀 Sigma AI SNIPER Active\nOTC + Forex + Crypto")

def result_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ WIN", callback_data="result_win"),
         InlineKeyboardButton("❌ LOSS", callback_data="result_loss")]
    ])

# === PAIRS ===
PAIRS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD","EURJPY","GBPJPY","AUDJPY"]
CRYPTO_PAIRS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]

# Expanded OTC Currency Pairs
OTC_PAIRS = [
    "EURUSD_OTC", "GBPUSD_OTC", "USDJPY_OTC", "AUDUSD_OTC", "USDCAD_OTC",
    "VOLATILITY75", "VOLATILITY100", "VOLATILITY50",
    "BOOM500", "BOOM1000", "CRASH500", "CRASH1000",
    "JUMP10", "JUMP25", "JUMP50", "JUMP75", "RANGEBREAK"
]

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Forex", callback_data="forex")],
        [InlineKeyboardButton("💰 Crypto", callback_data="crypto")],
        [InlineKeyboardButton("⚡ OTC", callback_data="otc")]
    ])

def forex_menu():
    keyboard, row = [], []
    for i, pair in enumerate(PAIRS, 1):
        row.append(InlineKeyboardButton(pair[:3]+"/"+pair[3:], callback_data=pair))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def crypto_menu():
    keyboard, row = [], []
    for i, pair in enumerate(CRYPTO_PAIRS, 1):
        row.append(InlineKeyboardButton(pair.replace("USDT","/USDT"), callback_data=f"crypto_{pair}"))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def otc_menu():
    keyboard, row = [], []
    for i, pair in enumerate(OTC_PAIRS, 1):
        row.append(InlineKeyboardButton(pair, callback_data=f"otc_{pair}"))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def otc_timeframe_menu(pair):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("5s", callback_data=f"{pair}_5s"), InlineKeyboardButton("15s", callback_data=f"{pair}_15s")],
        [InlineKeyboardButton("30s", callback_data=f"{pair}_30s"), InlineKeyboardButton("1m", callback_data=f"{pair}_1m")],
        [InlineKeyboardButton("5m", callback_data=f"{pair}_5m")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_otc")]
    ])

def get_analysis(symbol, interval):
    is_otc = any(x in symbol for x in ["OTC", "VOLATILITY", "BOOM", "CRASH", "JUMP"])
    handler = TA_Handler(
        symbol=symbol,
        screener="forex" if is_otc else ("crypto" if "USDT" in symbol else "forex"),
        exchange="OANDA" if is_otc else ("BINANCE" if "USDT" in symbol else "FX_IDC"),
        interval=interval
    )
    return handler.get_analysis()

# === FOREX / CRYPTO SIGNAL (Original Logic) ===
def generate_signal(pair, timeframe):
    try:
        interval_map = {"1m": Interval.INTERVAL_1_MINUTE, "5m": Interval.INTERVAL_5_MINUTES, "15m": Interval.INTERVAL_15_MINUTES}
        analysis = get_analysis(pair, interval_map.get(timeframe, Interval.INTERVAL_1_MINUTE))
        current = analysis.indicators
        price = current["close"]
        rsi = current.get("RSI", 50)
        ema50 = current.get("EMA50", 0)
        trend = "UP" if price > ema50 else "DOWN"

        if trend == "UP" and 38 < rsi < 65:
            return f"📊 **Forex/Crypto**\n🟢 BUY @ {round(price,5)}"
        elif trend == "DOWN" and 35 < rsi < 62:
            return f"📊 **Forex/Crypto**\n🔴 SELL @ {round(price,5)}"
        return "⏳ Waiting for setup"
    except:
        return "❌ Error"

# === OTC SPECIAL SIGNAL LOGIC ===
def generate_otc_signal(pair, timeframe):
    try:
        tf_map = {
            "5s": Interval.INTERVAL_5_SECONDS,
            "15s": Interval.INTERVAL_15_SECONDS,
            "30s": Interval.INTERVAL_30_SECONDS,
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES
        }
        analysis = get_analysis(pair, tf_map[timeframe])
        current = analysis.indicators

        price = current["close"]
        rsi = current.get("RSI", 50)
        ema20 = current.get("EMA20", price)
        high = current["high"]
        low = current["low"]

        momentum = price - ema20
        spike = (high - low) / price > 0.0025

        if momentum > 0 and rsi < 70 and spike:
            result = f"🔥 **OTC SNIPER** \n🟢 BUY @ {round(price,5)}"
        elif momentum < 0 and rsi > 30 and spike:
            result = f"🔥 **OTC SNIPER** \n🔴 SELL @ {round(price,5)}"
        else:
            return "⏳ Waiting for OTC spike"

        return f"""
📊 **Sigma AI OTC SNIPER**

💱 Pair: {pair}
⏱ TF: {timeframe}

{result}

⚡ High Volatility Mode
💰 Amount: {get_trade_amount()}
📉 Martingale: {MARTINGALE_STEP}
"""
    except:
        return "❌ OTC Data error"

# === BUTTON HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Not authorized")
        return
    await update.message.reply_text("🚀 Sigma AI SNIPER Started!\nForex + Crypto + OTC", reply_markup=main_menu())

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global WIN, LOSS
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "result_win":
        WIN += 1
        reset_martingale()
        await query.edit_message_text(f"✅ WIN\nWins: {WIN}\nLosses: {LOSS}")
    elif data == "result_loss":
        LOSS += 1
        increase_martingale()
        await query.edit_message_text(f"❌ LOSS\nWins: {WIN}\nLosses: {LOSS}\nMartingale: {MARTINGALE_STEP}")

    elif data == "forex":
        await query.edit_message_text("Choose Forex:", reply_markup=forex_menu())
    elif data == "crypto":
        await query.edit_message_text("Choose Crypto:", reply_markup=crypto_menu())
    elif data == "otc":
        await query.edit_message_text("Choose OTC Pair:", reply_markup=otc_menu())
    elif data == "back_main":
        await query.edit_message_text("Main Menu:", reply_markup=main_menu())
    elif data == "back_otc":
        await query.edit_message_text("Choose OTC Pair:", reply_markup=otc_menu())

    elif data in PAIRS:
        await query.edit_message_text(f"Select TF {data}", reply_markup=timeframe_menu(data))
    elif data.startswith("crypto_"):
        pair = data.replace("crypto_", "")
        await query.edit_message_text(f"Select TF {pair}", reply_markup=timeframe_menu(pair))
    elif data.startswith("otc_"):
        pair = data.replace("otc_", "")
        await query.edit_message_text(f"Select TF for {pair}", reply_markup=otc_timeframe_menu(pair))

    elif "_" in data:
        if data.startswith("otc_") or any(otc in data for otc in OTC_PAIRS):
            pair, tf = data.split("_", 1)
            if any(otc in pair for otc in ["OTC", "VOLATILITY", "BOOM", "CRASH", "JUMP"]):
                result = generate_otc_signal(pair, tf)
            else:
                result = generate_signal(pair, tf)
        else:
            pair, tf = data.split("_", 1)
            result = generate_signal(pair, tf)
        await query.edit_message_text(result, parse_mode="Markdown", reply_markup=result_buttons())

app = ApplicationBuilder().token(TOKEN).build()
app.job_queue.run_repeating(session_notifier, interval=300, first=10)

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
