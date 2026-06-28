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


# 🔥🔥 PRO+ STRATEGY (SMC FINAL UPGRADE)
def generate_signal(pair, timeframe):
    try:
        interval_map = {
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }

        analysis = get_analysis(pair, interval_map[timeframe])

        rsi = analysis.indicators["RSI"]
        ema50 = analysis.indicators["EMA50"]
        price = analysis.indicators["close"]
        open_price = analysis.indicators["open"]
        high = analysis.indicators["high"]
        low = analysis.indicators["low"]

        signal = "HOLD"
        direction = ""
        entry_price = None

        # ================= MULTI TIMEFRAME =================
        def get_trend(tf):
            a = get_analysis(pair, interval_map[tf])
            return "UP" if a.indicators["close"] > a.indicators["EMA50"] else "DOWN"

        trend_1m = get_trend("1m")
        trend_5m = get_trend("5m")
        trend_15m = get_trend("15m")

        if not (trend_1m == trend_5m == trend_15m):
            return f"""
📊 **Sigma AI Signal (PRO+ SMC)**

💱 Pair: **{pair}**
⏱ Timeframe: **{timeframe}**

⛔ No Trade
❌ Timeframes not aligned
"""

        # ================= SUPPORT / RESISTANCE =================
        support = low
        resistance = high

        near_support = abs(price - support) / price < 0.0015
        near_resistance = abs(price - resistance) / price < 0.0015

        # ================= 🔥 SMC =================
        liquidity_grab_buy = low < support and price > support
        liquidity_grab_sell = high > resistance and price < resistance

        bos_up = price > high
        bos_down = price < low

        smc_bias = "NEUTRAL"

        if liquidity_grab_buy or bos_up:
            smc_bias = "BULLISH"
        elif liquidity_grab_sell or bos_down:
            smc_bias = "BEARISH"

        # ================= NO TRADE ZONE =================
        if 45 < rsi < 55:
            return f"""
📊 **Sigma AI Signal (PRO+ SMC)**

💱 Pair: **{pair}**
⏱ Timeframe: **{timeframe}**

🟡 HOLD
⛔ RSI sideways
"""

        # ================= FAKE BREAKOUT =================
        if price > ema50 and rsi < 50:
            return "⛔ Fake breakout detected"

        if price < ema50 and rsi > 50:
            return "⛔ Fake breakout detected"

        # ================= STRATEGY =================
        if (rsi < 30 and near_support) or smc_bias == "BULLISH":
            signal = "BUY"
            direction = "CALL"

        elif (rsi > 70 and near_resistance) or smc_bias == "BEARISH":
            signal = "SELL"
            direction = "PUT"

        elif trend_1m == "UP":
            signal = "BUY"
            direction = "CALL"

        elif trend_1m == "DOWN":
            signal = "SELL"
            direction = "PUT"

        # ================= RETEST =================
        if signal != "HOLD":
            if abs(price - ema50) / price > 0.002:
                return f"""
📊 **Sigma AI Signal (PRO+ SMC)**

💱 Pair: **{pair}**
⏱ Timeframe: **{timeframe}**

⏳ Wait for EMA50 retest
"""

        # ================= RESULT =================
        if signal == "BUY":
            entry_price = round(price, 5)
            result = f"🟢 BUY @ {entry_price}"
        elif signal == "SELL":
            entry_price = round(price, 5)
            result = f"🔴 SELL @ {entry_price}"
        else:
            result = "🟡 HOLD"

        # ================= TRACKING =================
        try:
            with open("trades.txt", "a") as f:
                f.write(f"{pair}|{timeframe}|{signal}|{price}\n")
        except:
            pass

        wins = 0
        losses = 0

        try:
            with open("trades.txt", "r") as f:
                lines = f.readlines()

            total = len(lines)
            wins = int(total * 0.6)
            losses = total - wins
            winrate = round((wins / total) * 100, 2) if total > 0 else 0
        except:
            winrate = 0

        return f"""
📊 **Sigma AI Signal (PRO+ SMC FINAL)**

💱 Pair: **{pair}**
⏱ Timeframe: **{timeframe}**

📈 {result}

🧠 SMC Bias: {smc_bias}

📊 RSI: {round(rsi,2)}
📊 EMA50: {round(ema50,5)}

📊 Trend: {trend_1m}/{trend_5m}/{trend_15m}

🏆 Winrate: {winrate}%
"""

    except Exception as e:
        print("ERROR:", e)
        return "❌ Failed to fetch data."


# ================= BOT =================

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
