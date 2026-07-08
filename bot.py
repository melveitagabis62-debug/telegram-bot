import os
import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import pandas as pd
import ta
import yfinance as yf

# Environment Variables from Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

bot = AsyncTeleBot(TELEGRAM_TOKEN)

# Temporary dictionary to store user selections
USER_STATE = {}

# Timeframe mapping to Yahoo Finance (1m, 2m, 5m intervals)
TIMEFRAME_MAP = {
    "1 Min": "1m",
    "3 Mins": "2m", # yfinance uses 2m as closest liquid asset variant
    "5 Mins": "5m"
}

# Mapping Pocket Option internal names to real-world Market symbols
ASSET_MAP = {
    "eurusd_otc": "EURUSD=X",
    "gbpusdt_otc": "GBPUSD=X",
    "audusd_otc": "AUDUSD=X",
    "usdjpy_otc": "JPY=X"
}

# --- MENU 1: Choose Pair ---
@bot.message_handler(commands=['analyze', 'start'])
async def start_manual_analysis(message):
    chat_id = message.chat.id
    USER_STATE[chat_id] = {}  # Reset state
    
    markup = InlineKeyboardMarkup(row_width=2)
    pairs = ["eurusd_otc", "gbpusdt_otc", "audusd_otc", "usdjpy_otc"]
    
    buttons = [InlineKeyboardButton(pair.upper().replace("_OTC", " OTC"), callback_data=f"pair_{pair}") for pair in pairs]
    markup.add(*buttons)
    
    await bot.send_message(chat_id, "📊 **Pocket Option Manual Analyzer**\n\nStep 1: Select an OTC Currency Pair:", reply_markup=markup, parse_mode="Markdown")

# --- MENU 2: Choose Timeframe ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('pair_'))
async def handle_pair_selection(call):
    chat_id = call.message.chat.id
    selected_pair = call.data.replace("pair_", "")
    
    if chat_id not in USER_STATE:
        USER_STATE[chat_id] = {}
    USER_STATE[chat_id]['pair'] = selected_pair
    
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton(tf_text, callback_data=f"tf_{tf_text}") for tf_text in TIMEFRAME_MAP.keys()]
    markup.add(*buttons)
    
    await bot.answer_callback_query(call.id)
    
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"Selected Pair: **{selected_pair.upper().replace('_OTC', ' OTC')}**\n\nStep 2: Select the Timeframe:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# --- STEP 3: Trigger Analysis ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('tf_'))
async def handle_timeframe_selection(call):
    chat_id = call.message.chat.id
    tf_text = call.data.replace("tf_", "")
    
    if chat_id not in USER_STATE or 'pair' not in USER_STATE[chat_id]:
        await bot.send_message(chat_id, "❌ Session expired. Please type /start again.")
        return
        
    USER_STATE[chat_id]['timeframe_text'] = tf_text
    USER_STATE[chat_id]['interval'] = TIMEFRAME_MAP[tf_text]
    
    pair = USER_STATE[chat_id]['pair']
    
    await bot.answer_callback_query(call.id)
    
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"⏳ Pulling live tracking data for **{pair.upper().replace('_OTC', ' OTC')}** ({tf_text})...\nAnalyzing indicators..."
    )
    
    # Run data retrieval safely in the background threads
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, run_market_analysis, chat_id)

# --- CORE STRATEGIC ANALYSIS ---
def run_market_analysis(chat_id):
    pair_key = USER_STATE[chat_id]['pair']
    interval = USER_STATE[chat_id]['interval']
    tf_text = USER_STATE[chat_id]['timeframe_text']
    
    ticker_symbol = ASSET_MAP.get(pair_key, "EURUSD=X")

    try:
        # Download data directly from public streams instantly with zero cookies
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period="1d", interval=interval)
        
        if df is None or df.empty:
            asyncio.run_coroutine_threadsafe(bot.send_message(chat_id, "⚠️ Failed to fetch feed data. Retrying..."), bot.loop)
            return

        # Clean column labels to fit technical indicator calculations
        df.columns = [col.lower() for col in df.columns]

        rsi = ta.momentum.RSIIndicator(close=df['close'], window=7).rsi()
        macd = ta.trend.MACD(close=df['close'], window_fast=12, window_slow=26, window_sign=9)
        
        latest_rsi = rsi.iloc[-1]
        latest_macd_diff = macd.macd_diff().iloc[-1]
        current_price = df['close'].iloc[-1]
        
        signal = "⏳ NO CLEAR SIGNAL (Market Neutral)"
        emoji = "⚪"
        
        if latest_rsi > 45 and latest_rsi < 65 and latest_macd_diff > 0:
            signal = "CALL (BUY)"
            emoji = "🟢"
        elif latest_rsi < 55 and latest_rsi > 35 and latest_macd_diff < 0:
            signal = "PUT (SELL)"
            emoji = "🔴"

        signal_message = (
            f"🚨 **POCKET OPTION AUTOMATED SIGNAL** 🚨\n"
            f"-------------------------------------\n"
            f"📈 **Asset:** {pair_key.upper().replace('_OTC', ' OTC')}\n"
            f"⏱️ **Timeframe:** {tf_text}\n"
            f"💵 **Current Price:** {current_price:.5f}\n"
            f"-------------------------------------\n"
            f"⚡ **Action:** {emoji} **{signal}**\n"
            f"⏳ **Expiration Recommendation:** {tf_text}\n\n"
            f"ℹ️ _RSI: {latest_rsi:.1f} | MACD Diff: {latest_macd_diff:.5f}_"
        )
        
        asyncio.run_coroutine_threadsafe(bot.send_message(chat_id, signal_message, parse_mode="Markdown"), bot.loop)
        
    except Exception as e:
        asyncio.run_coroutine_threadsafe(bot.send_message(chat_id, f"❌ Engine Error: {str(e)}"), bot.loop)

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    print("🤖 Async Manual Telegram Signal Bot is running...")
    asyncio.run(bot.infinity_polling())
