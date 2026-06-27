from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from tradingview_ta import TA_Handler, Interval
import logging
import os

TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [6351041498]  # replace with your Telegram ID

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

# 🔥 NEW: CRYPTO PAIRS (INCLUDING BITCOIN)
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


# 🔥 NEW: CRYPTO MENU
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

# 🔥 UPDATED: SUPPORT FOREX + CRYPTO
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

        signal = "HOLD"
        warning = ""
        entry_price = None
        direction = ""

        distance_from_ema = abs(price - ema50) / price
        if distance_from_ema > 0.0028:
            warning = "⚠️ Strong trend or volatile market → HIGH RISK"

        if rsi < 32 and price >= ema50 * 0.993:
            signal = "BUY"
            direction = "CALL"
            entry_price = round(max(price, ema50 * 0.997), 5)

        elif rsi > 68 and price <= ema50 * 1.007:
            signal = "SELL"
            direction = "PUT"
            entry_price = round(min(price, ema50 * 1.003), 5)

        else:
            signal = "HOLD"
            warning = "⚠️ Market is not good → Don't Trade"

        if signal == "BUY":
            signal_display = f"🟢 BUY / CALL"
            entry_text = f"📍 Enter **CALL** at **{entry_price}**\n→ Or wait next candle"
        elif signal == "SELL":
            signal_display = f"🔴 SELL / PUT"
            entry_text = f"📍 Enter **PUT** at **{entry_price}**\n→ Or wait next candle"
        else:
            signal_display = "🟡 HOLD"
            entry_text = "⛔ Do not trade"

        return f"""
📊 **Sigma AI Signal**

💱 Pair: **{pair}**
⏱ Timeframe: **{timeframe}**

📈 Signal: **{signal_display}**

{entry_text}

{warning}

📊 RSI: `{round(rsi, 2)}`
📊 EMA50: `{round(ema50, 5)}`
📊 Price: `{round(price, 5)}`
"""

    except Exception as e:
        print("ERROR:", e)
        return "❌ Failed to fetch data."

# ================= HANDLERS =================

from telegram import ReplyKeyboardMarkup
from telegram.ext import MessageHandler, filters

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Access Denied")
        return

    keyboard = [["🚀 Start Bot"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "👋 Welcome! Click below:",
        reply_markup=reply_markup
    )


async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ALLOWED_USERS:
        return

    if update.message.text == "🚀 Start Bot":
        await update.message.reply_text(
            "🚀 Sigma AI Bot",
            reply_markup=main_menu()
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if user_id not in ALLOWED_USERS:
        await query.answer("⛔ Access Denied", show_alert=True)
        return

    await query.answer()
    data = query.data

    if data == "forex":
        await query.edit_message_text("Select Pair:", reply_markup=forex_menu())

    elif data == "crypto":
        await query.edit_message_text("Select Crypto:", reply_markup=crypto_menu())

    elif data in PAIRS:
        await query.edit_message_text("Select Timeframe:", reply_markup=timeframe_menu(data))

    elif data.startswith("crypto_"):
        pair = data.replace("crypto_", "")
        await query.edit_message_text(
            "Select Timeframe:",
            reply_markup=timeframe_menu(pair)
        )

    elif "_" in data:
        pair, tf = data.split("_")
        result = generate_signal(pair, tf)
        await query.edit_message_text(result)

    elif data == "back_main":
        await query.edit_message_text(
            "🚀 Sigma AI Bot",
            reply_markup=main_menu()
        )

    elif data == "back_forex":
        await query.edit_message_text(
            "Select Pair:",
            reply_markup=forex_menu()
        )

# ================= RUN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT, start_button))

print("Bot running...")
app.run_polling()
