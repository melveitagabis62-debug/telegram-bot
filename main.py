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
    "EURUSD",
    "GBPUSD",
    "EURGBP",
    "GBPJPY",
    "USDJPY",
    "AUDCAD",
    "USDCAD"
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
        ind = analysis.indicators

        # === PRICE DATA ===
        o = ind["open"]
        h = ind["high"]
        l = ind["low"]
        c = ind["close"]
        body = abs(c - o)
        candle_range = h - l if h > l else 0.00001
        upper_shadow = h - max(o, c)
        lower_shadow = min(o, c) - l

        # === INDICATORS ===
        rsi = ind["RSI"]
        ema50 = ind["EMA50"]
        macd = ind.get("MACD.macd", 0)
        macd_signal = ind.get("MACD.signal", 0)
        trend = "UP" if c > ema50 else "DOWN"

        # === CANDLESTICK ANALYSIS ===
        is_bullish_candle = c > o
        body_ratio = body / candle_range
        lower_shadow_ratio = lower_shadow / candle_range
        upper_shadow_ratio = upper_shadow / candle_range

        candle_signal = None

        # Strong patterns
        if body_ratio > 0.65 and is_bullish_candle and lower_shadow_ratio < 0.2:
            candle_signal = "STRONG_BULLISH"
        elif body_ratio > 0.65 and not is_bullish_candle and upper_shadow_ratio < 0.2:
            candle_signal = "STRONG_BEARISH"
        elif lower_shadow_ratio > 2.0 and body_ratio < 0.3:   # Hammer / Inverted Hammer
            candle_signal = "BULLISH_REVERSAL" if trend == "DOWN" else "BULLISH_CONT"
        elif upper_shadow_ratio > 2.0 and body_ratio < 0.3:
            candle_signal = "BEARISH_REVERSAL" if trend == "UP" else "BEARISH_CONT"

        # === HYBRID SIGNAL LOGIC ===
        result = None

        if candle_signal in ["STRONG_BULLISH", "BULLISH_REVERSAL", "BULLISH_CONT"]:
            if 40 < rsi < 68 and c > ema50 and macd > macd_signal:
                result = f"🔥 HYBRID STRONG BUY\n🟢 BUY @ {round(c,5)}"

        elif candle_signal in ["STRONG_BEARISH", "BEARISH_REVERSAL", "BEARISH_CONT"]:
            if 32 < rsi < 60 and c < ema50 and macd < macd_signal:
                result = f"🔥 HYBRID STRONG SELL\n🔴 SELL @ {round(c,5)}"

        if not result:
            # Fallback to lighter signals to maintain frequency
            if 48 < rsi < 65 and macd > macd_signal and c > ema50 and body_ratio > 0.4:
                result = f"⚡ QUICK BUY\n🟢 BUY @ {round(c,5)}"
            elif 35 < rsi < 52 and macd < macd_signal and c < ema50 and body_ratio > 0.4:
                result = f"⚡ QUICK SELL\n🔴 SELL @ {round(c,5)}"
            else:
                return "⏳ No clean hybrid setup"

        expiration = {"1m": "2-3 minutes", "5m": "5-10 minutes", "15m": "15-30 minutes"}[timeframe]
        timing = get_entry_timing(timeframe)
        amount = get_trade_amount()

        return f"""
📊 Sigma AI HYBRID MODE v4

💱 Pair: {pair}
⏱ TF: {timeframe}

{result}

{timing}

🎯 Mode: Hybrid (Candle + Indicators) - Balanced Frequency

💰 Amount: {amount}
📉 Martingale: {MARTINGALE_STEP}

⏳ Expiration: {expiration}

📊 RSI: {round(rsi,2)} | Trend: {trend}
📊 Candle: {'Strong Body' if body_ratio > 0.6 else 'With Shadow'}
        """

    except Exception as e:
        print(e)
        return "❌ Error generating signal"

               
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

    
