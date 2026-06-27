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


# 🔥🔥 UPDATED LOGIC HERE (REVERSAL + TREND)
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


        # ================= PRO STRATEGY =================

        is_crypto = "USDT" in pair

        # 🔥 NO-TRADE ZONE (sideways killer)
        if 45 <= rsi <= 55:
        
            return f"""
📊 **Sigma AI Signal**

💱 Pair: **{pair}**
⏱ Timeframe: **{timeframe}**

🟡 HOLD

⛔ No-trade zone (sideways market)

📊 RSI: `{round(rsi, 2)}`
"""

# 🔥 FAKE BREAKOUT FILTER
distance_from_ema = abs(price - ema50) / price

        if distance_from_ema > (0.004 if is_crypto else 0.003):
        return f"""
📊 **Sigma AI Signal**

💱 Pair: **{pair}**
⏱ Timeframe: **{timeframe}**

⚠️ FAKE BREAKOUT RISK

⛔ Price too far from EMA → likely reversal trap

📊 RSI: `{round(rsi, 2)}`
"""

# 🔥 RSI MOMENTUM (candle confirmation)
rsi_strength = abs(rsi - 50)

# ================= SIGNAL LOGIC =================

        # 🔥 REVERSAL (VERY STRONG)
        if rsi <= (28 if is_crypto else 30):
        signal = "BUY"
        direction = "CALL"
        entry_price = round(price, 5)

        elif rsi >= (72 if is_crypto else 70):
        signal = "SELL"
        direction = "PUT"
        entry_price = round(price, 5)

        # 🔥 TREND + MOMENTUM CONFIRMATION
        elif price > ema50 and rsi > (55 if is_crypto else 52) and rsi_strength > 5:
        signal = "BUY"
        direction = "CALL"
        entry_price = round(price, 5)

        elif price < ema50 and rsi < (45 if is_crypto else 48) and rsi_strength > 5:
        signal = "SELL"
        direction = "PUT"
        entry_price = round(price, 5)

        # 🔥 OTHERWISE
    else:
        signal = "HOLD"
        warning = "⚠️ Weak structure → Skip trade"
        # ================= DISPLAY =================

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

    # MAIN MENU
    if data == "forex":
        await query.edit_message_text("📊 Choose Forex Pair:", reply_markup=forex_menu())

    elif data == "crypto":
        await query.edit_message_text("💰 Choose Crypto Pair:", reply_markup=crypto_menu())

    elif data == "back_main":
        await query.edit_message_text("🏠 Main Menu:", reply_markup=main_menu())

    elif data == "back_forex":
        await query.edit_message_text("📊 Choose Forex Pair:", reply_markup=forex_menu())

    # PAIR SELECTED → SHOW TIMEFRAME
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

    # FINAL SIGNAL
    elif "_" in data:
        pair, timeframe = data.split("_")

        result = generate_signal(pair, timeframe)

        await query.edit_message_text(result, parse_mode="Markdown")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling(
)
