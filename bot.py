import os
import time
import requests
import pandas as pd
import ta  # Technical Analysis library

# Environment Variables (Set these in Railway)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Configuration
SYMBOL = "BTC/USDT"  # You can change this to standard assets
INTERVAL = "1m"      # 1-minute bars for aggressive scalping

def send_telegram_signal(signal_type, price):
    emoji = "🟢 CALL (BUY)" if signal_type == "CALL" else "🔴 PUT (SELL)"
    message = (
        f"🚨 **POCKET OPTION SIGNAL** 🚨\n\n"
        f"Asset: {SYMBOL}\n"
        f"Action: {emoji}\n"
        f"Entry Price: {price}\n"
        f"Expiration: 1-3 Mins\n"
        f"Strategy: Aggressive Momentum"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
        print(f"Signal sent: {signal_type}")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def fetch_data():
    # Fetching live public data from Binance as a proxy for asset movement
    url = f"https://api.binance.com/api/v3/klines?symbol={SYMBOL.replace('/', '')}&interval={INTERVAL}&limit=100"
    res = requests.get(url).json()
    df = pd.DataFrame(res, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
    df['close'] = df['close'].astype(float)
    return df

def analyze_strategy():
    try:
        df = fetch_data()
        
        # Calculate Indicators using 'ta' library
        rsi = ta.momentum.RSIIndicator(close=df['close'], window=7).rsi() # Short window for aggressiveness
        macd = ta.trend.MACD(close=df['close'], window_fast=12, window_slow=26, window_sign=9)
        
        latest_rsi = rsi.iloc[-1]
        latest_macd_diff = macd.macd_diff().iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # --- AGGRESSIVE QUALITY STRATEGY ---
        # CALL Conditions: RSI is oversold or turning up (> 45) AND MACD histogram is turning positive
        if latest_rsi > 45 and latest_rsi < 65 and latest_macd_diff > 0:
            send_telegram_signal("CALL", current_price)
            
        # PUT Conditions: RSI is overbought or turning down (< 55) AND MACD histogram is turning negative
        elif latest_rsi < 55 and latest_rsi > 35 and latest_macd_diff < 0:
            send_telegram_signal("PUT", current_price)
            
    except Exception as e:
        print(f"Error in analysis loop: {e}")

if __name__ == "__main__":
    print("🚀 Aggressive Pocket Option Signal Bot Started...")
    while True:
        analyze_strategy()
        time.sleep(60)  # Check every 60 seconds for a new candle
