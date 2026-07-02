from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.ext import MessageHandler, filters

from tradingview_ta import TA_Handler, Interval
import logging
import os

TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [6351041498]

# ================= PAIRS =================

PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
    "USDCAD", "USDCHF", "NZDUSD",
    "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY",
    "EURGBP", "EURCHF", "EURAUD", "EURCAD",
    "GBPAUD", "GBPCAD", "GBPCHF",
    "AUDCAD", "AUDCHF",
    "CADCHF"
]

CRYPTO_PAIRS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT"
]

# ================= MENU =================

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Forex", callback_data="forex")],
        [InlineKeyboardButton("💰 Crypto", callback_data="crypto")]
    ]
    return InlineKeyboardMarkup(keyboard)


def forex_menu():
    keyboard = []
    row = []

    for i, pair in enumerate(PAIRS, 1):
        display = pair[:3] + "/" + pair[3:]

        row.append(
            InlineKeyboardButton(display, callback_data=pair)
        )

        if i % 2 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data="back_main")
    ])

    return InlineKeyboardMarkup(keyboard)


def crypto_menu():
    keyboard = []
    row = []

    for i, pair in enumerate(CRYPTO_PAIRS, 1):
        display = pair.replace("USDT", "/USDT")

        row.append(
            InlineKeyboardButton(display, callback_data=f"crypto_{pair}")
        )

        if i % 2 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data="back_main")
    ])

    return InlineKeyboardMarkup(keyboard)


def timeframe_menu(pair):
    keyboard = [
        [InlineKeyboardButton("1m", callback_data=f"{pair}_1m"),
         InlineKeyboardButton("5m", callback_data=f"{pair}_5m")],
        [InlineKeyboardButton("15m", callback_data=f"{pair}_15m")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_forex")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ================= SIGNAL =================

def get_analysis(symbol, interval):
    if "USDT" in symbol:
        handler = TA_Handler(
            symbol=symbol,
            screener="crypto",
            exchange="BINANCE",
            interval=interval
        )
    else:
        handler = TA_Handler(
            symbol=symbol,
            screener="forex",
            exchange="FX_IDC",
            interval=interval
        )

    analysis = handler.get_analysis()
    return analysis


# 🔥🔥 HIGH FREQUENCY STRATEGY v2 - HIGHER ACCURACY
def generate_signal(pair, timeframe):
    try:
        interval_map = {
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }

        analysis = get_analysis(pair, interval_map[timeframe])

        # Core indicators
        rsi = analysis.indicators.get("RSI", 50)
        ema50 = analysis.indicators.get("EMA50", 0)
        price = analysis.indicators.get("close", 0)
        high = analysis.indicators.get("high", 0)
        low = analysis.indicators.get("low", 0)
        
        # Additional indicators for better confluence
        macd = analysis.indicators.get("MACD.macd", 0)
        macd_signal = analysis.indicators.get("MACD.signal", 0)
        stoch_k = analysis.indicators.get("Stoch.K", 50)
        adx = analysis.indicators.get("ADX", 20)  # Trend strength
        bb_upper = analysis.indicators.get("BB.upper", price * 1.02)
        bb_lower = analysis.indicators.get("BB.lower", price * 0.98)

        signal = "HOLD"
        confidence = 0
        warning = ""
        entry_price = round(price, 5)

        # ================= MULTI TIMEFRAME CONFLUENCE (STRICTER) =================
        def get_trend(tf):
            a = get_analysis(pair, interval_map[tf])
            close_tf = a.indicators.get("close", 0)
            ema_tf = a.indicators.get("EMA50", 0)
            return "UP" if close_tf > ema_tf else "DOWN"

        trend_1m = get_trend("1m")
        trend_5m = get_trend("5m")
        trend_15m = get_trend("15m")

        # Require at least 2/3 timeframes aligned (better than before)
        up_trends = sum([trend_1m == "UP", trend_5m == "UP", trend_15m == "UP"])
        down_trends = 3 - up_trends
        mtf_aligned = max(up_trends, down_trends) >= 2

        # ================= MOMENTUM & OSCILLATORS =================
        macd_bullish = macd > macd_signal
        macd_bearish = macd < macd_signal
        stoch_oversold = stoch_k < 30
        stoch_overbought = stoch_k > 70

        # ================= VOLATILITY FILTER (Avoid chop) =================
        atr = analysis.indicators.get("ATR", 0.0005)  # Rough fallback
        volatility = (high - low) / price
        is_volatile_enough = volatility > 0.0005  # Filter very tight ranges

        # ================= CONFLUENCE-BASED SIGNAL LOGIC =================
        if mtf_aligned and is_volatile_enough:
            if (rsi < 45 and stoch_oversold and macd_bullish and 
                trend_1m == "UP" and price < bb_upper * 0.995):  # Near lower band or support
                signal = "BUY"
                confidence = 75 + (int(adx > 25) * 15)  # ADX bonus for strong trend
            
            elif (rsi > 55 and stoch_overbought and macd_bearish and 
                  trend_1m == "DOWN" and price > bb_lower * 1.005):
                signal = "SELL"
                confidence = 75 + (int(adx > 25) * 15)

        # Fallback with higher threshold (less frequent but higher quality)
        elif trend_1m == trend_5m == "UP" and rsi < 50 and macd_bullish:
            signal = "BUY"
            confidence = 60
        elif trend_1m == trend_5m == "DOWN" and rsi > 50 and macd_bearish:
            signal = "SELL"
            confidence = 60

        # ================= RETEST / PULLBACK FILTER =================
        distance_to_ema = abs(price - ema50) / price
        if signal != "HOLD" and distance_to_ema > 0.0035:
            warning = "⚠️ Wait for EMA50 retest"

        # ================= FINAL OUTPUT =================
        direction = "CALL" if signal == "BUY" else "PUT" if signal == "SELL" else ""
        result = f"🟢 BUY @ {entry_price}" if signal == "BUY" else \
                 f"🔴 SELL @ {entry_price}" if signal == "SELL" else "🟡 HOLD"

        # Confidence badge
        conf_badge = f" | **{confidence}%**" if confidence > 0 else ""

        # Logging
        try:
            with open("trades.txt", "a") as f:
                f.write(f"{pair} | {timeframe} | {signal} | {price} | conf:{confidence}\n")
        except:
            pass

        alignment = f"{trend_1m}/{trend_5m}/{trend_15m}"

        return f"""
📊 **Sigma AI Signal v2 (HIGH ACCURACY)**

💱 Pair: **{pair}**
⏱ Timeframe: **{timeframe}**

📈 {result}{conf_badge} {warning}

📊 RSI: {round(rsi,2)} | Stoch: {round(stoch_k,1)}
📊 MACD: {"Bullish" if macd_bullish else "Bearish"}
📊 ADX: {round(adx,1)} (Trend Strength)
📊 Trend: {alignment}
"""

    except Exception as e:
        print("ERROR:", e)
        return "❌ Failed to fetch data. Try again."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Not authorized")
        return

    await update.message.reply_text(
        "🚀 Sigma Bot Started\n\nChoose market:",
        reply_markup=main_menu()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    if text in ["start bot", "🚀 start bot"]:
        await start(update, context)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "forex":
        await query.edit_message_text("📊 Choose Forex Pair:", reply_markup=forex_menu())

    elif data == "crypto":
        await query.edit_message_text("💰 Choose Crypto Pair:", reply_markup=crypto_menu())

    elif data == "back_main":
        await query.edit_message_text("🏠 Main Menu:", reply_markup=main_menu())

    elif data == "back_forex":
        await query.edit_message_text("📊 Choose Forex Pair:", reply_markup=forex_menu())

    elif data in PAIRS:
        await query.edit_message_text(
            f"⏱ Select timeframe for {data}",
            reply_markup=timeframe_menu(data)
        )

    elif data.startswith("crypto_"):
        pair = data.replace("crypto_", "")
        await query.edit_message_text(
            f"⏱ Select timeframe for {pair}",
            reply_markup=timeframe_menu(pair)
        )

    elif "_" in data:
        pair, timeframe = data.split("_")
        result = generate_signal(pair, timeframe)
        await query.edit_message_text(result, parse_mode="Markdown")


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


app.run_polling()
        
