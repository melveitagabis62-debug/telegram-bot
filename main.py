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

# === ENTRY TIMING SYSTEM ===
def get_entry_timing(timeframe):
    now = datetime.datetime.utcnow()

    if timeframe == "1m":
        total_seconds = 60
        seconds_passed = now.second

    elif timeframe == "5m":
        total_seconds = 300
        seconds_passed = (now.minute % 5) * 60 + now.second

    elif timeframe == "15m":
        total_seconds = 900
        seconds_passed = (now.minute % 15) * 60 + now.second

    remaining = total_seconds - seconds_passed

    if remaining > total_seconds * 0.6:
        return f"⏳ WAIT ({remaining}s left in candle)"
    elif remaining > total_seconds * 0.2:
        return f"⚠️ PREPARE ({remaining}s)"
    else:
        return f"🚀 Perfect Timing ({remaining}s to new candle)"

# === SESSION DETECTION ===
def get_trading_session():
    now = datetime.datetime.utcnow()
    hour = now.hour

    if 7 <= hour < 13:
        return "🇬🇧 London Session OPEN"
    elif 13 <= hour < 17:
        return "🔥 London-New York OVERLAP (BEST TIME)"
    elif 17 <= hour < 22:
        return "🇺🇸 New York Session OPEN"
    else:
        return None

# === AUTO SESSION NOTIFIER ===
async def session_notifier(context: ContextTypes.DEFAULT_TYPE):
    session = get_trading_session()

    if session:
        for user_id in ALLOWED_USERS:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"{session}\n\n💡 Market is active — spam mode ON!"
            )

# === RESULT BUTTONS ===
def result_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ WIN", callback_data="result_win"),
            InlineKeyboardButton("❌ LOSS", callback_data="result_loss")
        ]
    ])

PAIRS = [
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD",
    "EURJPY","GBPJPY","AUDJPY","CADJPY","CHFJPY",
    "EURGBP","EURCHF","EURAUD","EURCAD",
    "GBPAUD","GBPCAD","GBPCHF",
    "AUDCAD","AUDCHF","CADCHF"
]

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

# === IMPROVED SIGNAL GENERATION (BALANCED MODE) ===

def generate_signal(pair, timeframe):
    try:
        interval_map = {
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }

        hour = datetime.datetime.utcnow().hour
        if not (7 <= hour <= 22):
            return "⛔ Trade only London/New York session"

        analysis = get_analysis(pair, interval_map[timeframe])

        rsi = analysis.indicators["RSI"]
        ema50 = analysis.indicators["EMA50"]
        price = analysis.indicators["close"]
        macd = analysis.indicators.get("MACD.macd", 0)
        macd_signal = analysis.indicators.get("MACD.signal", 0)

        trend = "UP" if price > ema50 else "DOWN"

        # 🔥 Momentum Strength
        distance = abs(price - ema50)
        strength_threshold = price * 0.0007
        strong_momentum = distance > strength_threshold

        # 🔥 MACD Strength
        macd_strength = abs(macd - macd_signal)
        strong_macd = macd_strength > 0.00006

        # 🔥 NEW: TREND QUALITY FILTER
        ema_trend_strength = distance / price
        clean_trend = ema_trend_strength > 0.0004

        # 🔥 NEW: ENTRY POSITION (avoid late entries)
        entry_ok = distance < (price * 0.002)

        if trend == "UP":
            if (52 < rsi < 63 and macd > macd_signal 
                and strong_momentum and strong_macd 
                and clean_trend and entry_ok):
                
                result = f"🔥 STRONG BUY\n🟢 BUY @ {round(price,5)}"

            elif (50 < rsi < 66 and macd > macd_signal 
                  and strong_macd and clean_trend):
                
                result = f"⚡ QUICK BUY\n🟢 BUY @ {round(price,5)}"
            else:
                return "⏳ No clean setup"

        else:
            if (37 < rsi < 48 and macd < macd_signal 
                and strong_momentum and strong_macd 
                and clean_trend and entry_ok):
                
                result = f"🔥 STRONG SELL\n🔴 SELL @ {round(price,5)}"

            elif (34 < rsi < 50 and macd < macd_signal 
                  and strong_macd and clean_trend):
                
                result = f"⚡ QUICK SELL\n🔴 SELL @ {round(price,5)}"
            else:
                return "⏳ No clean setup"

        expiration = {
            "1m": "2-3 minutes",
            "5m": "5-10 minutes",
            "15m": "15-30 minutes"
        }[timeframe]

        amount = get_trade_amount()
        timing = get_entry_timing(timeframe)

        return f"""
📊 Sigma AI SMART MODE v5

💱 Pair: {pair}
⏱ TF: {timeframe}

{result}
{timing}

🎯 Mode: HIGH ACCURACY (Filtered)

💰 Amount: {amount}
📉 Martingale: {MARTINGALE_STEP}

⏳ Expiration: {expiration}

📊 RSI: {round(rsi,2)}
📊 Trend: {trend}
📊 MACD: {'Bullish' if macd > macd_signal else 'Bearish'}
📊 Momentum: {'Strong' if strong_momentum else 'Weak'}
📊 Trend Quality: {'Clean' if clean_trend else 'Choppy'}
"""

    except Exception as e:
        print(e)
        return "❌ Error"
        
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Not authorized")
        return
    await update.message.reply_text("🚀 Bot Started (BALANCED MODE)", reply_markup=main_menu())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower() in ["start bot", "🚀 start bot"]:
        await start(update, context)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global WIN, LOSS

    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "result_win":
        WIN += 1
        reset_martingale()
        await query.edit_message_text(f"✅ WIN\n\nWins: {WIN}\nLoss: {LOSS}")

    elif data == "result_loss":
        LOSS += 1
        increase_martingale()
        await query.edit_message_text(f"❌ LOSS\n\nWins: {WIN}\nLoss: {LOSS}\nMartingale: {MARTINGALE_STEP}")

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
        pair, tf = data.split("_")
        result = generate_signal(pair, tf)
        await query.edit_message_text(result, parse_mode="Markdown", reply_markup=result_buttons())

app = ApplicationBuilder().token(TOKEN).build()

app.job_queue.run_repeating(session_notifier, interval=300, first=10)

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
