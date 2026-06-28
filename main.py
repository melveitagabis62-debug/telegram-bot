from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.ext import MessageHandler, filters

from tradingview_ta import TA_Handler, Interval
import logging
import os
import datetime

TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [6351041498]

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

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Forex", callback_data="forex")],
        [InlineKeyboardButton("💰 Crypto", callback_data="crypto")]
    ]
    return InlineKeyboardMarkup(keyboard)

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

def generate_signal(pair, timeframe):
    try:
        interval_map = {
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }

        # SESSION FILTER
        hour = datetime.datetime.utcnow().hour

        # London + New York sessions only
        if not (7 <= hour <= 16 or 13 <= hour <= 22):
            return "⛔ Avoid Asian session (low quality market)"

        analysis = get_analysis(pair, interval_map[timeframe])

        rsi = analysis.indicators["RSI"]
        ema50 = analysis.indicators["EMA50"]
        price = analysis.indicators["close"]
        open_price = analysis.indicators["open"]
        high = analysis.indicators["high"]
        low = analysis.indicators["low"]

        # TREND FUNCTION
        def get_trend(tf):
            a = get_analysis(pair, interval_map[tf])
            return "UP" if a.indicators["close"] > a.indicators["EMA50"] else "DOWN"

        trend_1m = get_trend("1m")
        trend_5m = get_trend("5m")
        trend_15m = get_trend("15m")

        if not (trend_1m == trend_5m == trend_15m):
            return "⛔ No Trade (timeframes not aligned)"

        # TREND STRENGTH FILTER
        trend_strength = abs(price - ema50) / price
        if trend_strength < 0.001:
            return "⛔ Weak trend"

        # VOLATILITY FILTER
        range_size = (high - low) / price
        if range_size < 0.001:
            return "⛔ Low volatility"

        # NO TRADE ZONE
        if 40 < rsi < 60:
            return "⛔ Consolidation zone"

        # SUPPORT / RESISTANCE
        near_support = abs(price - low) / price < 0.0015
        near_resistance = abs(price - high) / price < 0.0015

        # SMC BIAS
        smc_bias = "NEUTRAL"
        if price > high:
            smc_bias = "BULLISH"
        elif price < low:
            smc_bias = "BEARISH"

        signal = "HOLD"

        if (rsi < 30 and near_support) or smc_bias == "BULLISH":
            signal = "BUY"
        elif (rsi > 70 and near_resistance) or smc_bias == "BEARISH":
            signal = "SELL"
        elif trend_1m == "UP":
            signal = "BUY"
        elif trend_1m == "DOWN":
            signal = "SELL"

        # CANDLE CONFIRMATION
        bullish_candle = price > open_price
        bearish_candle = price < open_price

        if signal == "BUY" and not bullish_candle:
            return "⏳ Waiting bullish confirmation"
        if signal == "SELL" and not bearish_candle:
            return "⏳ Waiting bearish confirmation"

        # ENTRY TIMING
        if abs(price - ema50) / price > 0.002:
            return "⏳ Wait for EMA50 retest"

        # CONFIDENCE SCORE
        confidence = 0
        if trend_1m == trend_5m == trend_15m:
            confidence += 2
        if smc_bias != "NEUTRAL":
            confidence += 2
        if near_support or near_resistance:
            confidence += 1
        if rsi < 30 or rsi > 70:
            confidence += 1

        result = "🟡 HOLD"
        if signal == "BUY":
            result = f"🟢 BUY @ {round(price,5)}"
        elif signal == "SELL":
            result = f"🔴 SELL @ {round(price,5)}"

        return f"""
📊 **Sigma AI PRO MAX**

💱 Pair: {pair}
⏱ TF: {timeframe}

📈 {result}
🔥 Confidence: {confidence}/6

📊 RSI: {round(rsi,2)}
📊 Trend: {trend_1m}/{trend_5m}/{trend_15m}
🧠 Bias: {smc_bias}
"""

    except Exception as e:
        print(e)
        return "❌ Error"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Not authorized")
        return
    await update.message.reply_text("🚀 Bot Started", reply_markup=main_menu())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower() in ["start bot", "🚀 start bot"]:
        await start(update, context)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "forex":
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
        await query.edit_message_text(result, parse_mode="Markdown")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
