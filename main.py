import time
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from tradingview_ta import TA_Handler, Interval
from telegram import Bot

# ================= CONFIG =================
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("6351041498")

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
TIMEFRAME = Interval.INTERVAL_1_MINUTE

# =============== SETTINGS =================
RSI_PERIOD = 14
EMA_PERIOD = 50

SIGNAL_COOLDOWN = 300  # seconds (5 mins)

last_signal_time = {}

# =============== FUNCTIONS =================

def get_analysis(symbol):
    handler = TA_Handler(
        symbol=symbol,
        screener="forex",
        exchange="FX_IDC",
        interval=TIMEFRAME
    )
    return handler.get_analysis()

def calculate_indicators(df):
    df["ema"] = EMAIndicator(df["close"], EMA_PERIOD).ema_indicator()
    df["rsi"] = RSIIndicator(df["close"], RSI_PERIOD).rsi()
    return df

def detect_signal(symbol):
    try:
        analysis = get_analysis(symbol)
        indicators = analysis.indicators

        close = indicators["close"]
        ema = indicators["EMA50"]
        rsi = indicators["RSI"]

        high = indicators["high"]
        low = indicators["low"]

        # Simple Support/Resistance
        resistance = high
        support = low

        # ===== BUY CONDITION =====
        if close > ema and rsi < 65:
            entry = close
            sl = support - (0.0003 * close)
            tp = entry + (entry - sl) * 1.5

            return "BUY", entry, sl, tp

        # ===== SELL CONDITION =====
        if close < ema and rsi > 35:
            entry = close
            sl = resistance + (0.0003 * close)
            tp = entry - (sl - entry) * 1.5

            return "SELL", entry, sl, tp

        return None

    except Exception as e:
        print(f"Error: {e}")
        return None

def send_signal(symbol, signal_type, entry, sl, tp):
    message = f"""
🚀 MT5 SIGNAL

📊 Pair: {symbol}
📍 Type: {signal_type}

💰 Entry: {round(entry, 5)}
🎯 TP: {round(tp, 5)}
🛑 SL: {round(sl, 5)}

⏱ Timeframe: 1M

⚠️ Wait for candle close before entry
"""
    bot.send_message(chat_id=CHAT_ID, text=message)

# =============== MAIN LOOP =================

def run_bot():
    print("Bot started...")

    while True:
        for pair in PAIRS:
            now = time.time()

            if pair in last_signal_time:
                if now - last_signal_time[pair] < SIGNAL_COOLDOWN:
                    continue

            result = detect_signal(pair)

            if result:
                signal_type, entry, sl, tp = result
                send_signal(pair, signal_type, entry, sl, tp)
                last_signal_time[pair] = now

        time.sleep(30)

# =============== START =================

if __name__ == "__main__":
    run_bot()
