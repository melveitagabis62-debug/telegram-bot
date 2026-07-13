from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.ext import MessageHandler, filters

from tradingview_ta import TA_Handler, Interval
import logging
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
        total_seconds = 60
        seconds_passed = now.second
    elif timeframe == "5m":
        total_seconds = 300
        seconds_passed = (now.minute % 5) * 60 + now.second
    else:
        total_seconds = 900
        seconds_passed = (now.minute % 15) * 60 + now.second

    remaining = total_seconds - seconds_passed
    if remaining > total_seconds * 0.55:
        return f"⏳ WAIT ({remaining}s left)"
    elif remaining > total_seconds * 0.25:
        return f"⚠️ PREPARE ({remaining}s)"
    else:
        return f"🔥 ENTER NOW ({remaining}s)"

# === SESSION NOTIFIER ===
async def session_notifier(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.utcnow()
    hour = now.hour
    if 7 <= hour < 13:
        session = "🇬🇧 London Session OPEN"
    elif 13 <= hour < 17:
        session = "🔥 London-New York OVERLAP (BEST TIME)"
    elif 17 <= hour < 22:
        session = "🇺🇸 New York Session OPEN"
    else:
        return
    for user_id in ALLOWED_USERS:
        await context.bot.send_message(chat_id=user_id, text=f"{session}\n\n💡 High-Accuracy signals active!")

# === RESULT BUTTONS ===
def result_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ WIN", callback_data="result_win"),
         InlineKeyboardButton("❌ LOSS", callback_data="result_loss")]
    ])

PAIRS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD","EURJPY","GBPJPY","AUDJPY","CADJPY","CHFJPY","EURGBP","EURCHF","EURAUD","EURCAD","GBPAUD","GBPCAD","GBPCHF","AUDCAD","AUDCHF","CADCHF"]
CRYPTO_PAIRS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Forex", callback_data="forex")],
        [InlineKeyboardButton("💰 Crypto", callback_data="crypto")]
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

def timeframe_menu(pair):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1m", callback_data=f"{pair}_1m"),
         InlineKeyboardButton("5m", callback_data=f"{pair}_5m")],
        [InlineKeyboardButton("15m", callback_data=f"{pair}_15m")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_forex")]
    ])

def get_analysis(symbol, interval):
    handler = TA_Handler(
        symbol=symbol,
        screener="crypto" if "USDT" in symbol else "forex",
        exchange="BINANCE" if "USDT" in symbol else "FX_IDC",
        interval=interval
    )
    return handler.get_analysis()

# === MAIN SIGNAL FUNCTION (Improved with better candle awareness) ===
def generate_signal(pair, timeframe):
    try:
        interval_map = {
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }
        
        analysis = get_analysis(pair, interval_map[timeframe])
        current = analysis.indicators

        rsi = current.get("RSI", 50)
        ema50 = current.get("EMA50", 0)
        macd = current.get("MACD.macd", 0)
        macd_signal = current.get("MACD.signal", 0)
        
        price = current["close"]
        open_price = current["open"]
        high = current["high"]
        low = current["low"]

        trend = "UP" if price > ema50 else "DOWN"

        # Better pattern detection (uses current candle + approximation of previous)
        body = abs(price - open_price)
        engulf = (price > open_price and price > open_price * 1.001) or (price < open_price and price < open_price * 0.999)  # Strong body
        wick_reject = (high - max(open_price, price) > body * 2.0) or (min(open_price, price) - low > body * 2.0)

        near_support = abs(price - low) / price < 0.005
        near_resistance = abs(price - high) / price < 0.005

        signal = None
        reasons = []
        confidence = 4

        if trend == "UP" and 38 < rsi < 65:
            if (near_support or macd > macd_signal) and (engulf or wick_reject):
                signal = "BUY"
                reasons.append("Bullish Confluence")
                confidence += 3
        elif trend == "DOWN" and 35 < rsi < 62:
            if (near_resistance or macd < macd_signal) and (engulf or wick_reject):
                signal = "SELL"
                reasons.append("Bearish Confluence")
                confidence += 3

        if not signal or confidence < 7:
            return "⏳ Waiting for high-probability sniper setup"

        expiration = {"1m": "1-3 minutes", "5m": "4-8 minutes", "15m": "12-25 minutes"}[timeframe]
        amount = get_trade_amount()
        timing = get_entry_timing(timeframe)
        reason_str = " | ".join(reasons)

        if signal == "BUY":
            result = f"🔥 HIGH-ACCURACY SNIPER\n🟢 BUY @ {round(price,5)}"
        else:
            result = f"🔥 HIGH-ACCURACY SNIPER\n🔴 SELL @ {round(price,5)}"

        return f"""
📊 **Sigma AI ELITE SNIPER — Balanced Max v2**

💱 Pair: {pair}
⏱ TF: {timeframe}

{result}
{timing}

🔥 Confidence: {confidence}/9
📋 Reason: {reason_str}

💰 Amount: {amount}
📉 Martingale: {MARTINGALE_STEP}

⏳ Expiration: {expiration}

📊 RSI: {round(rsi,1)} | Trend: {trend}
"""
    except Exception as e:
        print("Signal Error:", e)
        return "❌ Data error — try again"

# === Bot Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Not authorized")
        return
    await update.message.reply_text("🚀 Sigma AI SNIPER (Balanced Max v2) Started!", reply_markup=main_menu())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower() in ["start", "start bot", "🚀 start bot"]:
        await start(update, context)

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
    elif data == "back_main":
        await query.edit_message_text("Main Menu:", reply_markup=main_menu())
    elif data == "back_forex":
        await query.edit_message_text("Choose Forex:", reply_markup=forex_menu())
    elif data in PAIRS:
        await query.edit_message_text(f"Select TF {data}", reply_markup=timeframe_menu(data))
    elif data.startswith("crypto_"):
        pair = data.replace("crypto_", "")
        await query.edit_message_text(f"Select TF {pair}", reply_markup=timeframe_menu(pair))
    elif "_" in data:
        pair, tf = data.split("_", 1)
        result = generate_signal(pair, tf)
        await query.edit_message_text(result, parse_mode="Markdown", reply_markup=result_buttons())

# === RUN BOT ===
app = ApplicationBuilder().token(TOKEN).build()
app.job_queue.run_repeating(session_notifier, interval=300, first=10)

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
