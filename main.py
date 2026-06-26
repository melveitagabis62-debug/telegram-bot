from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from tradingview_ta import TA_Handler, Interval
import asyncio
import time
import os

TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [6351041498]  # replace with your Telegram ID

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
        [InlineKeyboardButton("📊 Forex", callback_data="forex")],
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

# ================= ANALYSIS =================

def get_analysis(symbol, interval):
    handler = TA_Handler(
        symbol=symbol,
        screener="forex",
        exchange="FX_IDC",
        interval=interval
    )
    return handler.get_analysis()

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

        distance_from_ema = abs(price - ema50) / price

        signal = "HOLD"
        warning = ""
        entry_price = None

        # ❌ Avoid bad market
        if distance_from_ema > 0.0028:
            warning = "⚠️ Market too strong / volatile → Skip"

        # ✅ Strategy
        if rsi < 32 and price >= ema50 * 0.993:
            signal = "BUY"
            entry_price = round(max(price, ema50 * 0.997), 5)

        elif rsi > 68 and price <= ema50 * 1.007:
            signal = "SELL"
            entry_price = round(min(price, ema50 * 1.003), 5)

        else:
            signal = "HOLD"
            warning = "⚠️ Market not good → Don't Trade"

        if signal == "BUY":
            signal_display = "🟢 BUY / CALL"
            entry_text = f"📍 Enter CALL at {entry_price}\n→ Next candle entry"
        elif signal == "SELL":
            signal_display = "🔴 SELL / PUT"
            entry_text = f"📍 Enter PUT at {entry_price}\n→ Next candle entry"
        else:
            signal_display = "🟡 HOLD"
            entry_text = "⛔ No trade"

        return f"""
📊 Sigma AI Signal

💱 {pair}
⏱ {timeframe}

📈 {signal_display}

{entry_text}

{warning}

RSI: {round(rsi,2)}
EMA50: {round(ema50,5)}
Price: {round(price,5)}
"""

    except Exception as e:
        print("ERROR:", e)
        return "❌ Failed to fetch data."

# ================= AUTO DETECT =================

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

        distance_from_ema = abs(price - ema50) / price

        if distance_from_ema > 0.003:
            return False

        if (rsi < 32 and price >= ema50 * 0.995) or \
           (rsi > 68 and price <= ema50 * 1.005):
            return True

        return False

    except:
        return False

# ================= AUTO SIGNAL LOOP =================

last_sent = {}

async def auto_signal_loop(app):
    await asyncio.sleep(10)

    while True:
        print("🔄 Scanning market...")

        for pair in PAIRS:
            if True:

                now = time.time()

                if pair in last_sent and now - last_sent[pair] < 300:
                    continue

                last_sent[pair] = now

                message = f"""
🚨 MARKET ALERT

💱 {pair} is GOOD for trading now!

📊 Clean setup detected (RSI + EMA)

⚡ Get signal now!

⏱ Timeframe: 1m
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
        await update.message.reply_text(
            "🚀 Sigma AI Bot Ready",
            reply_markup=main_menu()
        )


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

    asyncio.create_task(auto_signal_loop(app))

    await app.run_polling()

asyncio.run(main())
