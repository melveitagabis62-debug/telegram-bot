import os
import time
import pandas as pd
import pandas_ta as ta  # Efficient indicator calculation
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tvDatafeed import TvDatafeed, Interval

# --- CONFIGURATION ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
# Optional: Hardcode your TradingView credentials if needed, or leave blank
TV_USER = os.getenv("TV_USER", "")
TV_PASS = os.getenv("TV_PASS", "")

bot = telebot.TeleBot(TOKEN)
tv = TvDatafeed(TV_USER, TV_PASS) if TV_USER else TvDatafeed()

# User session tracking
user_sessions = {}

# --- CONFIGURATION (FOREX FOCUS) ---
PAIRS = {
    "EUR/USD (Euro / US Dollar)": {"symbol": "EURUSD", "exchange": "FX_IDC"},
    "GBP/USD (British Pound / US Dollar)": {"symbol": "GBPUSD", "exchange": "FX_IDC"},
    "USD/JPY (US Dollar / Japanese Yen)": {"symbol": "USDJPY", "exchange": "FX_IDC"},
    "AUD/USD (Australian Dollar / US Dollar)": {"symbol": "AUDUSD", "exchange": "FX_IDC"},
    "USD/CAD (US Dollar / Canadian Dollar)": {"symbol": "USDCAD", "exchange": "FX_IDC"},
    "EUR/GBP (Euro / British Pound)": {"symbol": "EURGBP", "exchange": "FX_IDC"}
}

TIMEFRAMES = {
    "1 Minute": Interval.in_1_minute,
    "3 Minutes": Interval.in_3_minute,
    "5 Minutes": Interval.in_5_minute,
    "15 Minutes": Interval.in_15_minute
}

# --- BOT INTERACTION ---

@bot.message_handler(commands=['start', 'scan'])
def start_scan(message):
    chat_id = message.chat.id
    user_sessions[chat_id] = {"symbol": None, "exchange": None, "interval": None, "scanning": False}
    
    markup = InlineKeyboardMarkup(row_width=1)
    for name in PAIRS.keys():
        markup.add(InlineKeyboardButton(name, callback_data=f"pair_{name}"))
        
    bot.send_message(chat_id, "⚡ **Scalper Bot** ⚡\nSelect a Pair to scan:", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pair_"))
def handle_pair(call):
    chat_id = call.message.chat.id
    pair_name = call.data.replace("pair_", "")
    
    user_sessions[chat_id]["symbol"] = PAIRS[pair_name]["symbol"]
    user_sessions[chat_id]["exchange"] = PAIRS[pair_name]["exchange"]
    
    markup = InlineKeyboardMarkup(row_width=2)
    for tf_name in TIMEFRAMES.keys():
        markup.add(InlineKeyboardButton(tf_name, callback_data=f"tf_{tf_name}"))
        
    bot.edit_message_text(f"Selected: *{pair_name}*\nNow choose a timeframe:", 
                          chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("tf_"))
def handle_timeframe(call):
    chat_id = call.message.chat.id
    tf_name = call.data.replace("tf_", "")
    
    user_sessions[chat_id]["interval"] = TIMEFRAMES[tf_name]
    user_sessions[chat_id]["scanning"] = True
    
    session = user_sessions[chat_id]
    bot.edit_message_text(f"🚀 **Scanning Started!**\nTarget: `{session['symbol']}` ({session['exchange']})\nTimeframe: `{tf_name}`\n\nI will alert you here when a high-accuracy signal appears. To stop, type /stop.", 
                          chat_id, call.message.message_id, parse_mode="Markdown")
    
    # Trigger scanner loop
    run_scanner(chat_id)

@bot.message_handler(commands=['stop'])
def stop_scan(message):
    chat_id = message.chat.id
    if chat_id in user_sessions:
        user_sessions[chat_id]["scanning"] = False
        bot.send_message(chat_id, "⏹️ Scanning stopped successfully.")
    else:
        bot.send_message(chat_id, "No active scanning session found.")

# --- SCALPING STRATEGY ENGINE ---

def run_scanner(chat_id):
    while user_sessions.get(chat_id, {}).get("scanning", False):
        session = user_sessions[chat_id]
        try:
            # Fetch last 100 bars for accurate indicator processing
            df = tv.get_hist(
                symbol=session["symbol"], 
                exchange=session["exchange"], 
                interval=session["interval"], 
                n_bars=100
            )
            
            if df is not None and not df.empty:
                # Calculate indicators
                df['EMA_9'] = ta.ema(df['close'], length=9)
                df['EMA_21'] = ta.ema(df['close'], length=21)
                df['RSI'] = ta.rsi(df['close'], length=14)
                
                # Extract the latest fully closed candle data
                latest = df.iloc[-2] 
                prev = df.iloc[-3]
                
                # Aggressive, High-Probability Conditions (Trend + Momentum Filter)
                # BUY: Fast EMA crosses above Slow EMA AND RSI bounces out of oversold territory
                buy_signal = (prev['EMA_9'] <= prev['EMA_21']) and (latest['EMA_9'] > latest['EMA_21']) and (latest['RSI'] > 40)
                
                # SELL: Fast EMA crosses below Slow EMA AND RSI drops out of overbought territory
                sell_signal = (prev['EMA_9'] >= prev['EMA_21']) and (latest['EMA_9'] < latest['EMA_21']) and (latest['RSI'] < 60)
                
                if buy_signal:
                    msg = (f"🟢 **SCALPING BUY SIGNAL** 🟢\n\n"
                           f"Pair: `{session['symbol']}`\n"
                           f"Price: `{latest['close']}`\n"
                           f"RSI: `{round(latest['RSI'], 2)}`\n"
                           f"🎯 *Target:* 1:1.5 Risk-to-Reward ratio\n"
                           f"🛡️ *Stop Loss:* Just below recent swing low.")
                    bot.send_message(chat_id, msg, parse_mode="Markdown")
                    time.sleep(60) # Prevent duplicate alerts on the same candle
                    
                elif sell_signal:
                    msg = (f"🔴 **SCALPING SELL SIGNAL** 🔴\n\n"
                           f"Pair: `{session['symbol']}`\n"
                           f"Price: `{latest['close']}`\n"
                           f"RSI: `{round(latest['RSI'], 2)}`\n"
                           f"🎯 *Target:* 1:1.5 Risk-to-Reward ratio\n"
                           f"🛡️ *Stop Loss:* Just above recent swing high.")
                    bot.send_message(chat_id, msg, parse_mode="Markdown")
                    time.sleep(60)
                    
        except Exception as e:
            print(f"Error fetching/processing data: {e}")
            
        # Sleep short intervals to poll fresh data on low timeframes (e.g., 1m/3m)
        time.sleep(15)
                
