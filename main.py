import logging
import requests
import pandas as pd

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===== CONFIG =====
TOKEN = "YOUR_BOT_TOKEN_HERE"

PAIR = "EURUSD"
TIMEFRAME = "5m"

# ===== LOGGING =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ===== FETCH DATA (FREE API) =====
def get_candles():
    url = f"https://api.binance.com/api/v3/klines?symbol=EURUSDT&interval=5m&limit=100"
    data = requests.get(url).json()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "close_time","qav","trades","tbav","tqav","ignore"
    ])

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
    df = calculate_indicators(df)

    last = df.iloc[-1]

    trend = "UP" if last["EMA50"] > last["EMA200"] else "DOWN"
    rsi = last["RSI"]

    if trend == "UP" and rsi < 35:
        return "BUY"
    elif trend == "DOWN" and rsi > 65:
        return "SELL"
    else:
        return "WAIT"

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
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("signal", signal))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
