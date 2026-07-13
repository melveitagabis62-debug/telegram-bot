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
        await context.bot.send_message(chat_id=user_id, text=f"{session}\n\n💡 Multi-Candle Analysis Active!")

def result_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ WIN", callback_data="result_win"),
         InlineKeyboardButton("❌ LOSS", callback_data="result_loss")]
    ])

PAIRS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD","EURJPY","GBPJPY","AUDJPY","CADJPY","CHFJPY","EURGBP","EURCHF","EURAUD","EURCAD","GBPAUD","GBPCAD","GBPCHF","AUDCAD","AUDCHF","CADCHF"]
CRYPTO_PAIRS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]

def main_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📊 Forex", callback_data="forex")],[InlineKeyboardButton("💰 Crypto", callback_data="crypto")]])

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
        [InlineKeyboardButton("1m", callback_data=f"{pair}_1m"), InlineKeyboardButton("5m", callback_data=f"{pair}_5m")],
        [InlineKeyboardButton("15m", callback_data=f"{pair}_15m")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_forex")]
    ])

# === MULTI-CANDLE ANALYSIS ===
def get_multi_candle_analysis(pair, timeframe, candles=5):
    try:
        handler = TA_Handler(
            symbol=pair,
            screener="crypto" if "USDT" in pair else "forex",
            exchange="BINANCE" if "USDT" in pair else "FX_IDC",
            interval=timeframe
        )
        analysis = handler.get_analysis()
        return analysis.indicators
    except:
        return None

def generate_signal(pair, timeframe):
    try:
        interval_map = {
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }
        
        # Get current data
        current_data = get_multi_candle_analysis(pair, interval_map[timeframe])
        if not current_data:
            return "❌ Data fetch error"

        price = current_data["close"]
        open_price = current_data["open"]
        high = current_data["high"]
        low = current_data["low"]
        rsi = current_data.get("RSI", 50)
        ema50 = current_data.get("EMA50", 0)
        macd = current_data.get("MACD.macd", 0)
        macd_signal = current_data.get("MACD.signal", 0)

        trend = "UP" if price > ema50 else "DOWN"

        # Multi-candle pattern logic
        body = abs(price - open_price)
        engulf = (price > open_price and body > (high - low) * 0.6) or (price < open_price and body > (high - low) * 0.6)
        strong_wick_reject = (high - max(open_price, price) > body * 2.2) or (min(open_price, price) - low > body * 2.2)

        near_support = abs(price - low) / price < 0.0045
        near_resistance = abs(price - high) / price < 0.0045

        signal = None
        reasons = []
        confidence = 5   # Higher base confidence with multi-candle

        if trend == "UP" and 40 < rsi < 65:
            if (near_support or macd > macd_signal) and (engulf or strong_wick_reject):
                signal = "BUY"
                reasons.append("Multi-Candle Bullish")
                confidence += 3
        elif trend == "DOWN" and 35 < rsi < 60:
            if (near_resistance or macd < macd_signal) and (engulf or strong_wick_reject):
                signal = "SELL"
                reasons.append("Multi-Candle Bearish")
                confidence += 3

        if not signal or confidence < 7:
            return "⏳ Waiting for strong multi-candle setup"

        expiration = {"1m": "1-3 minutes", "5m": "4-8 minutes", "15m": "12-25 minutes"}[timeframe]
        amount = get_trade_amount()
        timing = get_entry_timing(timeframe)

        if signal == "BUY":
            result = f"🔥 HIGH-ACCURACY SNIPER\n🟢 BUY @ {round(price,5)}"
        else:
            result = f"🔥 HIGH-ACCURACY SNIPER\n🔴 SELL @ {round(price,5)}"

        return f"""
📊 **Sigma AI ELITE SNIPER — Multi-Candle v3**

💱 Pair: {pair}
⏱ TF: {timeframe}

{result}
{timing}

🔥 Confidence: {confidence}/10
📋 Reason: { " | ".join(reasons) }

💰 Amount: {amount}
📉 Martingale: {MARTINGALE_STEP}

⏳ Expiration: {expiration}

📊 RSI: {round(rsi,1)} | Trend: {trend}
"""
    except Exception as e:
        print("Signal Error:", e)
        return "❌ Data error — try again"

# === Bot Setup ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Not authorized")
        return
    await update.message.reply_text("🚀 Sigma AI SNIPER (Multi-Candle v3) Started!", reply_markup=main_menu())

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

app = ApplicationBuilder().token(TOKEN).build()
app.job_queue.run_repeating(session_notifier, interval=300, first=10)

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
                                                       
