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


# 🔥🔥 HIGH FREQUENCY STRATEGY (UPGRADED)
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
        warning = ""
        entry_price = None
        direction = ""

        # ================= MULTI TIMEFRAME (RELAXED) =================
        def get_trend(tf):
            a = get_analysis(pair, interval_map[tf])
            if a.indicators["close"] > a.indicators["EMA50"]:
                return "UP"
            else:
                return "DOWN"

        trend_1m = get_trend("1m")
        trend_5m = get_trend("5m")
        trend_15m = get_trend("15m")

        # Relaxed: only require 1m and 5m alignment for higher frequency
        if not (trend_1m == trend_5m):
            # Still show trend but don't block
            pass

        # ================= SUPPORT / RESISTANCE =================
        support = low
        resistance = high

        near_support = abs(price - support) / price < 0.003  # Wider zone
        near_resistance = abs(price - resistance) / price < 0.003

        # ================= NO TRADE ZONE (RELAXED) =================
        if 48 < rsi < 52:  # Narrower sideways zone
            pass  # No hard HOLD

        # ================= HIGH FREQUENCY STRATEGY =================
        # More aggressive RSI thresholds + trend bias
        if rsi < 40 and (near_support or trend_1m == "UP"):
            signal = "BUY"
            direction = "CALL"

        elif rsi > 60 and (near_resistance or trend_1m == "DOWN"):
            signal = "SELL"
            direction = "PUT"

        elif trend_1m == "UP":
            signal = "BUY"
            direction = "CALL"

        elif trend_1m == "DOWN":
            signal = "SELL"
            direction = "PUT"

        # ================= RETEST ENTRY (RELAXED) =================
        if signal != "HOLD":
            if abs(price - ema50) / price > 0.005:  # Wider tolerance
                # Still suggest but don't block signal
                warning = "⚠️ Consider retest to EMA50"

        # ================= FINAL =================
        if signal == "BUY":
            entry_price = round(price, 5)
            result = f"🟢 BUY @ {entry_price}"

        elif signal == "SELL":
            entry_price = round(price, 5)
            result = f"🔴 SELL @ {entry_price}"

        else:
            result = "🟡 HOLD"

        # ================= LOGGING =================
        try:
            with open("trades.txt", "a") as f:
                f.write(f"{pair} | {timeframe} | {signal} | {price}\n")
        except:
            pass

        alignment = f"{trend_1m} / {trend_5m} / {trend_15m}"

        return f"""
📊 **Sigma AI Signal (HIGH FREQ)**

💱 Pair: **{pair}**
⏱ Timeframe: **{timeframe}**

📈 {result} {warning}

📊 RSI: {round(rsi,2)}
📊 EMA50: {round(ema50,5)}

📊 Trend: {alignment}
"""

    except Exception as e:
        print("ERROR:", e)
        return "❌ Failed to fetch data."


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
app.add_handler(MessageHandler(filters.TEXT & \~filters.COMMAND, handle_text))

app.run_polling()
