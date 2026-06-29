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
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD",
    "EURJPY","GBPJPY","AUDJPY","CADJPY","CHFJPY",
    "EURGBP","EURCHF","EURAUD","EURCAD",
    "GBPAUD","GBPCAD","GBPCHF",
    "AUDCAD","AUDCHF","CADCHF"
]

# ================= ELITE SETTINGS =================
COOLDOWN = 180
last_signal_time = {}
sent_pre_signal = {}

# ================= MENU =================

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Forex", callback_data="forex")]
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

# ================= ELITE FILTERS =================

def trend_direction(price, ema50, ema200):
    if ema50 > ema200 and price > ema50:
        return "BUY"
    elif ema50 < ema200 and price < ema50:
        return "SELL"
    return None

def candlestick_signal(open_, close, high, low):
    body = abs(close - open_)
    wick = high - low

    if body > wick * 0.5:
        return True
    if wick > body * 2:
        return True
    return False

def is_near_zone(price, support, resistance):
    if support and abs(price - support) / price < 0.002:
        return True
    if resistance and abs(price - resistance) / price < 0.002:
        return True
    return False

def should_send(pair):
    now = time.time()
    if pair not in last_signal_time:
        return True
    return now - last_signal_time[pair] > COOLDOWN

# ================= SIGNAL =================

def generate_signal(pair, timeframe):
    try:
        interval_map = {
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }

        analysis = get_analysis(pair, interval_map[timeframe])

        price = analysis.indicators["close"]
        ema50 = analysis.indicators.get("EMA50", price)
        ema200 = analysis.indicators.get("EMA200", price)
        rsi = analysis.indicators.get("RSI", 50)

        support = analysis.indicators.get("low")
        resistance = analysis.indicators.get("high")

        open_ = analysis.indicators.get("open", price)
        high = analysis.indicators.get("high", price)
        low = analysis.indicators.get("low", price)

        direction = trend_direction(price, ema50, ema200)

        if not direction:
            return None

        if not is_near_zone(price, support, resistance):
            return None

        if not candlestick_signal(open_, price, high, low):
            return None

        return {
            "pair": pair,
            "direction": direction,
            "price": price,
            "rsi": rsi,
            "ema50": ema50,
            "ema200": ema200,
            "support": support,
            "resistance": resistance
        }

    except Exception as e:
        print("ERROR:", e)
        return None

# ================= AUTO LOOP (ELITE) =================

async def auto_signal_loop(app):
    await asyncio.sleep(10)

    while True:
        for pair in PAIRS:
            data = generate_signal(pair, "1m")

            if not data:
                continue

            # PRE SIGNAL
            if pair not in sent_pre_signal:
                msg = f"""
📡 PRE-SIGNAL

💱 {pair}
Bias: {data['direction']}

Prepare for next candle
"""
                for user_id in ALLOWED_USERS:
                    await app.bot.send_message(chat_id=user_id, text=msg)

                sent_pre_signal[pair] = True
                continue

            # ENTRY SIGNAL
            if should_send(pair):
                msg = f"""
🎯 ENTRY SIGNAL

💱 {pair}
Direction: {data['direction']}
Entry: Next candle open

RSI: {round(data['rsi'],2)}
"""
                for user_id in ALLOWED_USERS:
                    await app.bot.send_message(chat_id=user_id, text=msg)

                last_signal_time[pair] = time.time()
                sent_pre_signal[pair] = False

            await asyncio.sleep(2)

        await asyncio.sleep(30)

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Access Denied")
        return

    keyboard = [["🚀 Start Bot"]]
    await update.message.reply_text("👋 Welcome!", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        return

    if update.message.text == "🚀 Start Bot":
        await update.message.reply_text("🚀 Sniper Bot Ready", reply_markup=main_menu())

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

        if not result:
            await query.edit_message_text("🟡 No high-quality setup. Wait...")
            return

        await query.edit_message_text(f"""
🎯 MANUAL SIGNAL

💱 {pair}
Direction: {result['direction']}
Entry: Next candle open
""")

    elif data == "back_main":
        await query.edit_message_text("🚀 Sniper Bot", reply_markup=main_menu())

    elif data == "back_forex":
        await query.edit_message_text("Select Pair:", reply_markup=forex_menu())

# ================= RUN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT, start_button))

async def post_init(app):
    asyncio.create_task(auto_signal_loop(app))

app.post_init = post_init

print("🔥 ELITE Sniper Bot Running...")
app.run_polling()
