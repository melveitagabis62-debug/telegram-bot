from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from tradingview_ta import TA_Handler, Interval
import os
import time

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

# ================= MENU =================

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Forex", callback_data="forex")]
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

    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])

    return InlineKeyboardMarkup(keyboard)


def timeframe_menu(pair):
    keyboard = [
        [InlineKeyboardButton("1m", callback_data=f"{pair}_1m"),
         InlineKeyboardButton("5m", callback_data=f"{pair}_5m")],
        [InlineKeyboardButton("15m", callback_data=f"{pair}_15m")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_forex")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ================= ANALYSIS =================

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
        from datetime import datetime

        interval_map = {
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }

        analysis = get_analysis(pair, interval_map[timeframe])

        rsi = analysis.indicators["RSI"]
        ema50 = analysis.indicators["EMA50"]
        ema200 = analysis.indicators.get("EMA200", ema50)
        price = analysis.indicators["close"]
        high = analysis.indicators.get("high", price)
        low = analysis.indicators.get("low", price)

        # 🔥 Higher timeframe
        htf = get_analysis(pair, Interval.INTERVAL_15_MINUTES)
        htf_rsi = htf.indicators["RSI"]

        signal = "HOLD"
        warning = ""
        entry_price = None
        confidence = 0

        # ================= TREND =================
        if ema50 > ema200:
            trend = "UPTREND"
        elif ema50 < ema200:
            trend = "DOWNTREND"
        else:
            trend = "SIDEWAYS"

        # ================= NO TRADE ZONE =================
        if 45 < rsi < 55:
            return "🟡 HOLD\n⚠️ Market is ranging"

        # ================= BUY =================
        if trend == "UPTREND" and rsi < 35 and htf_rsi < 40:
            signal = "BUY"
            entry_price = price
            confidence = 80

        # ================= SELL =================
        elif trend == "DOWNTREND" and rsi > 65 and htf_rsi > 60:
            signal = "SELL"
            entry_price = price
            confidence = 80

        # ================= EXTRA FILTERS =================
        if signal != "HOLD":
            if abs(price - high) < 0.0003:
                warning = "⚠️ Near resistance"
                confidence -= 10

            if abs(price - low) < 0.0003:
                warning = "⚠️ Near support"
                confidence -= 10

            if trend == "UPTREND" and htf_rsi > 70:
                warning = "⚠️ HTF overbought"
                confidence -= 15

            if trend == "DOWNTREND" and htf_rsi < 30:
                warning = "⚠️ HTF oversold"
                confidence -= 15

        # ================= TIME =================
        now = datetime.utcnow()
        seconds = now.second
        remaining = 60 - seconds

        # ================= RESULT =================
        if signal == "HOLD":
            return f"""
🟡 HOLD
📊 Trend: {trend}
⏳ Next Candle: {remaining}s
"""

        return f"""
📊 SIGNAL: {signal}
💰 Entry: {entry_price}
🔥 Confidence: {confidence}%
📊 Trend: {trend}
⏳ Next Candle: {remaining}s
{warning}
"""

    except Exception as e:
        return f"Error: {str(e)}"


# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Access Denied")
        return

    keyboard = [["🚀 Start Bot"]]
    await update.message.reply_text("Click below:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))


async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        return

    if update.message.text == "🚀 Start Bot":
        await update.message.reply_text("🚀 Sigma AI Bot", reply_markup=main_menu())


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

    elif data in PAIRS:
        await query.edit_message_text("Select Timeframe:", reply_markup=timeframe_menu(data))

    elif "_" in data:
        pair, tf = data.split("_")
        result = generate_signal(pair, tf)
        await query.edit_message_text(result)

    elif data == "back_main":
        await query.edit_message_text("🚀 Sigma AI Bot", reply_markup=main_menu())

    elif data == "back_forex":
        await query.edit_message_text("Select Pair:", reply_markup=forex_menu())

# ================= RUN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, start_button))
app.add_handler(CallbackQueryHandler(button_handler))

print("Bot running...")
app.run_polling()
        
