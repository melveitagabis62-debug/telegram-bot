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


# ================= SIGNAL ENGINE =================

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
        ema200 = analysis.indicators.get("EMA200", ema50)
        price = analysis.indicators["close"]
        high = analysis.indicators.get("high", price)
        low = analysis.indicators.get("low", price)

        # 🔥 Higher timeframe (15m)
        htf = get_analysis(pair, Interval.INTERVAL_15_MINUTES)
        htf_rsi = htf.indicators["RSI"]

        signal = "HOLD"
        warning = ""
        entry_price = None

        # ================= TREND =================
        if ema50 > ema200:
            trend = "UPTREND"
        elif ema50 < ema200:
            trend = "DOWNTREND"
        else:
            trend = "SIDEWAYS"

        # ================= NO TRADE =================
        if 45 < rsi < 55:
            return f"""
🟡 NO TRADE

💱 {pair} | {timeframe}
⚠️ Market is sideways

📊 RSI: {round(rsi,2)}
"""

        # ================= SIGNAL =================
        if rsi < 32 and price >= ema50 * 0.993:
            signal = "BUY"
            entry_price = round(max(price, ema50 * 0.997), 5)

        elif rsi > 68 and price <= ema50 * 1.007:
            signal = "SELL"
            entry_price = round(min(price, ema50 * 1.003), 5)

        else:
            signal = "HOLD"
            warning = "⚠️ Weak setup"

        # ================= TREND FILTER =================
        if signal == "BUY" and trend == "DOWNTREND":
            signal = "HOLD"
            warning += "\n⚠️ Against downtrend"

        if signal == "SELL" and trend == "UPTREND":
            signal = "HOLD"
            warning += "\n⚠️ Against uptrend"

        # ================= SUPPORT/RESISTANCE =================
        if signal == "BUY" and price > high * 0.995:
            signal = "HOLD"
            warning += "\n⚠️ Near resistance"

        if signal == "SELL" and price < low * 1.005:
            signal = "HOLD"
            warning += "\n⚠️ Near support"

        # ================= HTF CONFIRM =================
        if signal == "BUY" and htf_rsi < 50:
            signal = "HOLD"
            warning += "\n⚠️ HTF bearish"

        if signal == "SELL" and htf_rsi > 50:
            signal = "HOLD"
            warning += "\n⚠️ HTF bullish"

        # ================= CONFIDENCE =================
        confidence = 50

        if signal == "BUY":
            if rsi < 25:
                confidence += 25
            if abs(price - ema50) < price * 0.002:
                confidence += 15

        if signal == "SELL":
            if rsi > 75:
                confidence += 25
            if abs(price - ema50) < price * 0.002:
                confidence += 15

        confidence = min(confidence, 95)

        # ================= TIMER =================
        seconds = int(time.time()) % 60
        countdown = 60 - seconds

        # ================= DISPLAY =================
        if signal == "BUY":
            signal_text = "🟢 BUY / CALL"
            entry = f"📍 Entry: {entry_price} or next candle"
        elif signal == "SELL":
            signal_text = "🔴 SELL / PUT"
            entry = f"📍 Entry: {entry_price} or next candle"
        else:
            signal_text = "🟡 HOLD"
            entry = "⛔ No trade"

        return f"""
📊 **Sigma AI PRO Signal**

💱 Pair: **{pair}**
⏱ Timeframe: **{timeframe}**

📈 Signal: **{signal_text}**
🔥 Confidence: **{confidence}%**

{entry}

📊 Trend: **{trend}**
⏳ Next Candle: **{countdown}s**

{warning}

📊 Indicators:
• RSI: {round(rsi,2)}
• EMA50: {round(ema50,5)}
• EMA200: {round(ema200,5)}
• Price: {round(price,5)}
"""

    except Exception as e:
        print("ERROR:", e)
        return "❌ Failed to fetch data."

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
