import logging
import requests
import pandas as pd

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===== CONFIG =====
import os

TOKEN = os.getenv("BOT_TOKEN")

PAIR = "EURUSD"
TIMEFRAME = "5m"

# ===== LOGGING =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ===== FETCH DATA (FREE API) =====
def get_candles():
    url = f"https://api.binance.com/api/v3/klines?symbol={PAIR}&interval={TIMEFRAME}&limit=50"
    
    response = requests.get(url)
    data = response.json()

    # ✅ FIX: check bad response
    if not isinstance(data, list):
        print("API error:", data)
        return None

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "close_time","qav","trades","tbav","tqav","ignore"
    ])

    if df.empty:
        return None

    df["close"] = df["close"].astype(float)

    return df

# ===== INDICATORS =====
def calculate_indicators(df):
    df["EMA50"] = df["close"].ewm(span=50).mean()
    df["EMA200"] = df["close"].ewm(span=200).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    return df

# ===== SIGNAL LOGIC =====
def generate_signal():
    df = get_candles()

    # ✅ FIX 1: check if df is empty
    if df is None or df.empty:
        print("No data from API")
        return "NO DATA"

    df = calculate_indicators(df)

    # ✅ FIX 2: safe check before iloc
    if len(df) == 0:
        return "NO DATA"

    last = df.iloc[-1]

    trend = "UP" if last["EMA50"] > last["EMA200"] else "DOWN"
    rsi = last["RSI"]

    if trend == "UP" and rsi < 35:
        return "BUY"
    if trend == "DOWN" and rsi > 65:
        return "SELL"

    return "HOLD"

# ===== TELEGRAM COMMAND =====
async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = generate_signal()

    await update.message.reply_text(
        f"📊 Pair: {PAIR}\n"
        f"⏱ Timeframe: {TIMEFRAME}\n\n"
        f"📢 Signal: {result}"
    )

# ===== START BOT =====
def main():
    async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = generate_signal()

    await update.message.reply_text(
        f"📊 Pair: {PAIR}\n"
        f"⏱ Timeframe: {TIMEFRAME}\n\n"
        f"📢 Signal: {result}"
    )
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", signal))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()

from telegram.ext import CommandHandler, ContextTypes

# ===== TELEGRAM COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is working!")

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = generate_signal()
    await update.message.reply_text(f"Signal: {result}")

# ===== APP =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("signal", signal))

print("Bot started...")
app.run_polling()
