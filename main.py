from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from tradingview_ta import TA_Handler, Interval
import logging

import os

TOKEN = os.getenv("TOKEN")

# ================= MENU =================

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Forex", callback_data="forex")],
        [InlineKeyboardButton("💰 Crypto", callback_data="crypto")]
    ]
    return InlineKeyboardMarkup(keyboard)


def forex_menu():
    keyboard = [
        [InlineKeyboardButton("EUR/USD", callback_data="EURUSD")],
        [InlineKeyboardButton("GBP/USD", callback_data="GBPUSD")],
        [InlineKeyboardButton("USD/JPY", callback_data="USDJPY")],
        # 🔥 ADD THESE
        [InlineKeyboardButton("AUD/USD", callback_data="AUDUSD")],
        [InlineKeyboardButton("USD/CAD", callback_data="USDCAD")],
        [InlineKeyboardButton("USD/CHF", callback_data="USDCHF")],
        [InlineKeyboardButton("NZD/USD", callback_data="NZDUSD")],
        [InlineKeyboardButton("EUR/JPY", callback_data="EURJPY")],
        [InlineKeyboardButton("EUR/AUD", callback_data="EURAUD")],
        [InlineKeyboardButton("GBP/JPY", callback_data="GBPJPY")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
    ]
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
        symbol=pair.replace("/", ""),
        screener="forex",
        exchange="OANDA",
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

        import time
            time.sleep(1)
        
        analysis = get_analysis(pair, interval_map[timeframe])

        rsi = analysis.indicators["RSI"]
        macd = analysis.indicators["MACD.macd"]
        macd_signal = analysis.indicators["MACD.signal"]
        ema20 = analysis.indicators["EMA20"]
        ema50 = analysis.indicators["EMA50"]
        adx = analysis.indicators["ADX"]
        price = analysis.indicators["close"]

        buy_conditions = 0
        sell_conditions = 0
        
          # === MARKET QUALITY FILTER ===
        is_trending = adx > 20
        is_sideways = abs(ema20 - ema50) < 0.1
        rsi_safe_buy = rsi < 70
        rsi_safe_sell = rsi > 30
         
          # 🚫 Avoid weak trends
        if adx < 20:
            return "🟡 HOLD (Weak Trend)"

          # RSI Momentum
        if 30 < rsi < 60:
            buy_conditions += 1
        elif 40 < rsi < 70:
            sell_conditions += 1

        # MACD crossover
        if macd > macd_signal:
            buy_conditions += 1
        else:
            sell_conditions += 1

        # Trend confirmation
        if price > ema20 and price > ema50:
            buy_conditions += 1
        elif price < ema20 and price < ema50:
            sell_conditions += 1

         # Multi-timeframe confirmation
        higher_tf = get_analysis(pair, Interval.INTERVAL_5_MINUTES)
        htf_price = higher_tf.indicators["close"]
        htf_ema = higher_tf.indicators["EMA20"]

        if price > ema20 and htf_price > htf_ema:
            buy_conditions += 1
        elif price < ema20 and htf_price < htf_ema:
            sell_conditions += 1

        # === FINAL DECISION WITH FILTER ===
        if buy_conditions >= 2 and is_trending and not is_sideways and rsi_safe_buy:
            signal = "BUY"
            warning = "✅ Strong Trend - Safe to BUY"

        elif sell_conditions >= 2 and is_trending and not is_sideways and rsi_safe_sell:
            signal = "SELL"
            warning = "✅ Strong Trend - Safe to SELL"

        elif not is_trending:
            signal = "HOLD"
            warning = "⚠️ Weak Trend (ADX too low) - Avoid Trading"

        elif is_sideways:
            signal = "HOLD"
            warning = "⚠️ Sideways Market - No Trade Zone"

        else:
            signal = "HOLD"
            warning = "⚠️ Unclear Setup - Stay Out"

        return f"""
📊 Sigma AI Trade

💱 Pair: {pair}
⏱ Timeframe: {timeframe}

📈 Signal: {signal_display}

🧠 Indicators:
EMA20: {round(ema20,2)}
EMA50: {round(ema50,2)}
ADX: {round(adx,2)}

⚠️ Status: {warning}

⚡ Powered by TradingView
"""

    except Exception as e:
        print("ERROR:", e)
        return "❌ Failed to fetch data"

# ================= HANDLERS =================

from telegram import ReplyKeyboardMarkup

from telegram.ext import MessageHandler, filters

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🚀 Start Bot"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "👋 Welcome! Click below to start:",
        reply_markup=reply_markup
    )
async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🚀 Start Bot":
        await update.message.reply_text(
            "🚀 Welcome to Sigma AI Bot",
            reply_markup=main_menu()
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "forex":
        await query.edit_message_text("Select Pair:", reply_markup=forex_menu())

    elif data in ["EURUSD", "GBPUSD", "USDJPY", "USDCHF",
    "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY",
    "EURCHF", "AUDJPY", "GBPCHF", "EURAUD"]:
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
