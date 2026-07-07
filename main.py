import logging
import requests
import pandas as pd

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from config import TELEGRAM_TOKEN, API_URL
from strategy import generate_signal

logging.basicConfig(level=logging.INFO)

user_settings = {}

# ================= DATA FETCH =================
def get_market_data(symbol="BTCUSDT", interval="1m", limit=50):
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    res = requests.get(API_URL, params=params)
    data = res.json()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "close_time","qav","trades","tbbav","tbqav","ignore"
    ])

    df = df.astype(float)
    return df

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id

    user_settings[user_id] = {
        "step": "pair"
    }

    keyboard = [
        ["EURUSDT", "GBPUSDT"],
        ["BTCUSDT"]
    ]

    await update.message.reply_text(
        "📊 Select Pair:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.chat_id

    if user_id not in user_settings:
        user_settings[user_id] = {
            "step": "pair"
        }

    step = user_settings[user_id]["step"]

    # ================= STEP 1: SELECT PAIR =================
    if step == "pair":
        user_settings[user_id]["pair"] = text
        user_settings[user_id]["step"] = "timeframe"

        keyboard = [["1m", "5m", "15m"]]

        await update.message.reply_text(
            "⏱ Select Timeframe:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # ================= STEP 2: SELECT TIMEFRAME =================
    elif step == "timeframe":
        user_settings[user_id]["timeframe"] = text
        user_settings[user_id]["step"] = "done"

        await update.message.reply_text("🔍 Analyzing market...")

        pair = user_settings[user_id]["pair"]
        tf = user_settings[user_id]["timeframe"]

        try:
            df = get_market_data(pair, tf)
            signal, support, resistance = generate_signal(df)

            if signal:
                await update.message.reply_text(
                    f"🚨 SIGNAL: {signal}\n"
                    f"Pair: {pair}\n"
                    f"TF: {tf}\n"
                    f"Support: {support:.5f}\n"
                    f"Resistance: {resistance:.5f}"
                )
            else:
                await update.message.reply_text(
                    f"❌ No Signal\n"
                    f"Support: {support:.5f}\n"
                    f"Resistance: {resistance:.5f}"
                )

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

        # RESET FLOW
        user_settings[user_id] = {
            "step": "pair"
        }

        keyboard = [
            ["EURUSDT", "GBPUSDT"],
            ["BTCUSDT"]
        ]

        await update.message.reply_text(
            "📊 Select Pair:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )


# ================= RUN =================
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
