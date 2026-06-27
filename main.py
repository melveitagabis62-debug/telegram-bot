from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from tradingview_ta import TA_Handler, Interval
import logging

import os

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

# 🔥 OTC PAIRS
OTC_PAIRS = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC",
    "AUDUSD-OTC", "USDCAD-OTC", "USDCHF-OTC",
    "NZDUSD-OTC"
]

# ================= MENU =================

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Forex", callback_data="forex")],
        [InlineKeyboardButton("🟣 OTC Market", callback_data="otc")],
        [InlineKeyboardButton("💰 Crypto", callback_data="crypto")]
    ]
    return InlineKeyboardMarkup(keyboard)


def forex_menu():
    keyboard = []
    row = []

    for i, pair in enumerate(PAIRS, 1):
        display = pair[:3] + "/" + pair[3:]
        row.append(InlineKeyboardButton(display, callback_data=pair))

        if i % 2 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
    return InlineKeyboardMarkup(keyboard)


def otc_menu():
    keyboard = []
    row = []

    for i, pair in enumerate(OTC_PAIRS, 1):
        clean = pair.replace("-OTC", "")
        display = clean[:3] + "/" + clean[3:]

        row.append(
            InlineKeyboardButton(display + " (OTC)", callback_data=pair)
        )

        if i % 2 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
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
    handler = TA_Handler(
        symbol=symbol,
        screener="forex",
        exchange="FX_IDC",
        interval=interval
    )
    return handler.get_analysis()


def generate_signal(pair, timeframe):
    try:
        # 🔥 OTC DETECTION
        is_otc = False
        if "-OTC" in pair:
            is_otc = True
            pair = pair.replace("-OTC", "")

        interval_map = {
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }

        analysis = get_analysis(pair, interval_map[timeframe])

        rsi = analysis.indicators["RSI"]
        ema50 = analysis.indicators["EMA50"]
        price = analysis.indicators["close"]
        high = analysis.indicators.get("high", price)
        low = analysis.indicators.get("low", price)

        # 🔥 NEW (candle data for OTC accuracy)
        open_price = analysis.indicators.get("open", price)

        signal = "HOLD"
        warning = ""
        entry_price = None

        # 🔥 EMA DISTANCE FILTER
        distance_from_ema = abs(price - ema50) / price
        if distance_from_ema > 0.0028:
            warning = "⚠️ Strong trend or volatile market → HIGH RISK"

        # 🔥 OTC FAKE BREAKOUT FILTER
        if is_otc:
            wick_size = abs(high - low)
            body_size = abs(price - open_price)

            if wick_size > body_size * 3:
                return "⛔ OTC: Fake spike detected → Skip trade"

        # ================= STRATEGY =================

        if (rsi < (25 if is_otc else 32)) and price >= ema50 * 0.993:

            # 🔥 OTC candle confirmation
            if is_otc and price < open_price:
                return "⛔ OTC: Waiting for bullish confirmation candle"

            signal = "BUY"
            entry_price = round(max(price, ema50 * 0.997), 5)

        elif (rsi > (75 if is_otc else 68)) and price <= ema50 * 1.007:

            # 🔥 OTC candle confirmation
            if is_otc and price > open_price:
                return "⛔ OTC: Waiting for bearish confirmation candle"

            signal = "SELL"
            entry_price = round(min(price, ema50 * 1.003), 5)

        else:
            if is_otc:
                return "⛔ OTC: Market too choppy → No trade"
            signal = "HOLD"
            warning = "⚠️ Market is not good → Don't Trade"

        # ================= DISPLAY =================

        if signal == "BUY":
            signal_display = "🟢 BUY / CALL"
            entry_text = f"📍 Enter **CALL** at **{entry_price}**\n   → Or wait for next candle open"
        elif signal == "SELL":
            signal_display = "🔴 SELL / PUT"
            entry_text = f"📍 Enter **PUT** at **{entry_price}**\n   → Or wait for next candle open"
        else:
            signal_display = "🟡 HOLD"
            entry_text = "⛔ Do not trade right now"

        mode = "🟣 OTC MODE" if is_otc else "🌐 LIVE FOREX"

        return f"""
📊 **Sigma AI - Pocket Option Signal**
{mode}

💱 Pair: **{pair}**
⏱ Timeframe: **{timeframe}**

📈 **Signal**: **{signal_display}**

{entry_text}

{warning}

🧠 **Strategy**: Mean Reversion (RSI + EMA50)

📊 **Indicators**:
• RSI: `{round(rsi, 2)}`
• EMA50: `{round(ema50, 5)}`
• Current Price: `{round(price, 5)}`

⚡ **Tip for Pocket Option**:
• Use **Next Candle** entry
• Best for 1-5 minute expiration
• Avoid news!
"""

    except Exception as e:
        print("ERROR:", e)
        return "❌ Failed to fetch data. Please try again."

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
        "👋 Welcome! Click below to start:",
        reply_markup=reply_markup
    )


async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ALLOWED_USERS:
        return

    if update.message.text == "🚀 Start Bot":
        await update.message.reply_text(
            "🚀 Welcome to Sigma AI Bot",
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

    elif data == "otc":
        await query.edit_message_text("Select OTC Pair:", reply_markup=otc_menu())

    elif data in PAIRS or data in OTC_PAIRS:
        await query.edit_message_text("Select Timeframe:", reply_markup=timeframe_menu(data))

    elif "_" in data:
        pair, tf = data.split("_")
        result = generate_signal(pair, tf)
        await query.edit_message_text(result)

    elif data == "back_main":
        await query.edit_message_text(
            "🚀 Welcome to Sigma AI Bot",
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
