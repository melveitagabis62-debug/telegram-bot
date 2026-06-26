from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from tradingview_ta import TA_Handler, Interval
import logging

import os

TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [6351041498]  # replace with your Telegram ID

# 🔥 ADD THIS RIGHT HERE
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
        display = pair[:3] + "/" + pair[3:]  # EURUSD → EUR/USD

        row.append(
            InlineKeyboardButton(display, callback_data=pair)
        )

        if i % 2 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data="back")
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
        high = analysis.indicators.get("high", price)
        low = analysis.indicators.get("low", price)

        signal = "HOLD"
        warning = ""
        entry_price = None
        direction = ""

        # Strong trend filter (avoid choppy or trending markets)
        distance_from_ema = abs(price - ema50) / price
        if distance_from_ema > 0.0028:  
            warning = "⚠️ Strong trend or volatile market → HIGH RISK"

        # ================= STRATEGY LOGIC (Mean Reversion) =================
        if rsi < 32 and price >= ema50 * 0.993:           # Strong oversold + near EMA
            signal = "BUY"
            direction = "CALL"
            entry_price = round(max(price, ema50 * 0.997), 5)   # Enter near EMA

        elif rsi > 68 and price <= ema50 * 1.007:         # Strong overbought + near EMA
            signal = "SELL"
            direction = "PUT"
            entry_price = round(min(price, ema50 * 1.003), 5)

        else:
            signal = "HOLD"
            warning = "⚠️ Market is not good → Don't Trade"

        # ================= DISPLAY =================
        if signal == "BUY":
            signal_display = f"🟢 BUY / CALL"
            entry_text = f"📍 Enter **CALL** at **{entry_price}**\n" \
                        f"   → Or wait for next candle open"
        elif signal == "SELL":
            signal_display = f"🔴 SELL / PUT"
            entry_text = f"📍 Enter **PUT** at **{entry_price}**\n" \
                        f"   → Or wait for next candle open"
        else:
            signal_display = "🟡 HOLD"
            entry_text = "⛔ Do not trade right now"

        return f"""
📊 **Sigma AI - Pocket Option Signal**

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
• Use **Next Candle** entry to avoid repaints
• Best for 1-5 minute expirations
• Avoid news times!
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
    user_id = update.effective_user.id  # 👈 ADD THIS

    # 🔒 BLOCK UNAUTHORIZED USERS
    if user_id not in ALLOWED_USERS:
        return

    if update.message.text == "🚀 Start Bot":
        await update.message.reply_text(
            "🚀 Welcome to Sigma AI Bot",
            reply_markup=main_menu()
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id   # 👈 ADD THIS

    # 🔒 BLOCK UNAUTHORIZED USERS
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
            
