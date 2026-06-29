from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from tradingview_ta import TA_Handler, Interval
import asyncio
import time
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

# ================= MENU =================

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Forex", callback_data="forex")],
        [InlineKeyboardButton("💰 Crypto", callback_data="crypto")]
    ])

def forex_menu():
    keyboard, row = [], []

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
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1m", callback_data=f"{pair}_1m"),
         InlineKeyboardButton("5m", callback_data=f"{pair}_5m")],
        [InlineKeyboardButton("15m", callback_data=f"{pair}_15m")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_forex")]
    ])

# ================= ANALYSIS =================

def get_analysis(symbol, interval):
    handler = TA_Handler(
        symbol=symbol,
        screener="forex",
        exchange="FX_IDC",
        interval=interval
    )
    return handler.get_analysis()

def get_support_resistance(analysis):
    try:
        high = analysis.indicators.get("high")
        low = analysis.indicators.get("low")
        return low, high
    except:
        return None, None

# ================= SIGNAL =================

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

        support, resistance = get_support_resistance(analysis)
        distance_from_ema = abs(price - ema50) / price

        signal = "HOLD"
        entry_price = None
        reason = ""

        # ❌ Smart no-trade filter
        if distance_from_ema > 0.003:
            reason = "Strong trend / risky"
        elif 45 < rsi < 55:
            reason = "Weak RSI (sideways)"
        elif support and resistance:
            mid = (support + resistance) / 2
            if abs(price - mid) / price < 0.0015:
                reason = "Middle zone (no edge)"

        # ✅ Buy near support
        if support and price <= support * 1.002 and rsi < 35:
            signal = "BUY"
            entry_price = price

        # ✅ Sell near resistance
        elif resistance and price >= resistance * 0.998 and rsi > 65:
            signal = "SELL"
            entry_price = price

        # DISPLAY
        if signal == "BUY":
            text = "🟢 BUY / CALL"
        elif signal == "SELL":
            text = "🔴 SELL / PUT"
        else:
            text = "🟡 NO TRADE"

        return f"""
📊 Sigma AI Signal

💱 {pair}
⏱ {timeframe}

📈 {text}

📍 Entry: {entry_price if entry_price else "Wait"}

📊 Support: {round(support,5) if support else "-"}
📊 Resistance: {round(resistance,5) if resistance else "-"}

⚠️ {reason if reason else "Valid setup"}

RSI: {round(rsi,2)}
EMA50: {round(ema50,5)}
Price: {round(price,5)}
"""

    except Exception as e:
        print("ERROR:", e)
        return "❌ Failed to fetch data."

# ================= SMART DETECTOR =================

def is_good_chart(pair, timeframe):
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

        support, resistance = get_support_resistance(analysis)
        distance_from_ema = abs(price - ema50) / price

        if distance_from_ema > 0.003:
            return False

        if 45 < rsi < 55:
            return False

        if support and resistance:
            mid = (support + resistance) / 2
            if abs(price - mid) / price < 0.0015:
                return False

        if support and price <= support * 1.002 and rsi < 35:
            return True

        if resistance and price >= resistance * 0.998 and rsi > 65:
            return True

        return False

    except:
        return False

# ================= TIMER =================

def get_candle_time_left(timeframe):
    now = datetime.datetime.utcnow()

    if timeframe == "1m":
        return 60 - now.second
    elif timeframe == "5m":
        return (5*60) - (now.minute % 5)*60 - now.second
    elif timeframe == "15m":
        return (15*60) - (now.minute % 15)*60 - now.second
    return 60

# ================= AUTO LOOP =================

last_sent = {}

async def auto_signal_loop(app):
    await asyncio.sleep(10)

    while True:
        print("🔄 Scanning market...")

        for pair in PAIRS:
            if is_good_chart(pair, "1m"):

                now = time.time()
                if pair in last_sent and now - last_sent[pair] < 300:
                    continue

                last_sent[pair] = now

                time_left = get_candle_time_left("1m")

                message = f"""
🚨 SMART SIGNAL ALERT

💱 {pair}

📊 Clean setup detected
📍 Near Support/Resistance

⏰ Wait {time_left}s for next candle

⚡ Then get signal immediately!

🎯 Pocket Option Ready
"""

                for user_id in ALLOWED_USERS:
                    await app.bot.send_message(chat_id=user_id, text=message)

                await asyncio.sleep(3)

        await asyncio.sleep(60)

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Access Denied")
        return

    keyboard = [["🚀 Start Bot"]]
    await update.message.reply_text(
        "👋 Welcome!",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        return

    if update.message.text == "🚀 Start Bot":
        await update.message.reply_text("🚀 Sigma AI Bot Ready", reply_markup=main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.from_user.id not in ALLOWED_USERS:
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
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT, start_button))

async def main():
    print("Bot running...")
    asyncio.create_task(auto_signal_loop())
    await app.run_polling()

    if __name__ == "__main__":
    
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
