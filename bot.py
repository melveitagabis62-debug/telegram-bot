import os
import asyncio
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import pandas as pd
import ta
from pocketoptionapi_async import AsyncPocketOptionClient

# Environment Variables from Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
PO_SSID = os.getenv("PO_SSID")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Temporary dictionary to store user selections
# Format: {chat_id: {'pair': 'EURUSD_otc', 'timeframe': 60}}
USER_STATE = {}

# Timeframe mapping for humans vs Pocket Option API
TIMEFRAME_MAP = {
    "1 Min": 60,
    "3 Mins": 180,
    "5 Mins": 300
}

# --- MENU 1: Choose Pair ---
@bot.message_handler(commands=['analyze', 'start'])
def start_manual_analysis(message):
    chat_id = message.chat.id
    USER_STATE[chat_id] = {} # Reset state
    
    markup = InlineKeyboardMarkup(row_width=2)
    # Common Pocket Option OTC Pairs
    pairs = ["EURUSD_otc", "GBPUSD_otc", "AUDUSD_otc", "USDJPY_otc"]
    
    buttons = [InlineKeyboardButton(pair.upper().replace("_OTC", " OTC"), callback_data=f"pair_{pair}") for pair in pairs]
    markup.add(*buttons)
    
    bot.send_message(chat_id, "📊 **Pocket Option Manual Analyzer**\n\nStep 1: Select an OTC Currency Pair:", reply_markup=markup, parse_mode="Markdown")

# --- MENU 2: Choose Timeframe ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('pair_'))
def handle_pair_selection(call):
    chat_id = call.message.chat.id
    selected_pair = call.data.replace("pair_", "")
    USER_STATE[chat_id]['pair'] = selected_pair
    
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton(tf_text, callback_data=f"tf_{tf_text}") for tf_text in TIMEFRAME_MAP.keys()]
    markup.add(*buttons)
    
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"Selected Pair: **{selected_pair.upper()}**\n\nStep 2: Select the Timeframe:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# --- STEP 3: Trigger Analysis ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('tf_'))
def handle_timeframe_selection(call):
    chat_id = call.message.chat.id
    tf_text = call.data.replace("tf_", "")
    
    USER_STATE[chat_id]['timeframe_text'] = tf_text
    USER_STATE[chat_id]['timeframe_seconds'] = TIMEFRAME_MAP[tf_text]
    
    pair = USER_STATE[chat_id]['pair']
    
    # Send a processing message
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"⏳ Pulling live OTC data for **{pair.upper()}** ({tf_text})...\nAnalyzing indicators..."
    )
    
    # Run the async Pocket Option analysis inside the synchronous telebot handler
    asyncio.run(run_otc_analysis(chat_id, call.message.message_id))

# --- CORE STRATEGIC ANALYSIS ---
async def run_otc_analysis(chat_id, message_id):
    pair = USER_STATE[chat_id]['pair']
    tf_seconds = USER_STATE[chat_id]['timeframe_seconds']
    tf_text = USER_STATE[chat_id]['timeframe_text']
    
    if not PO_SSID:
        bot.send_message(chat_id, "❌ Error: `PO_SSID` variable is missing on Railway!")
        return

    try:
        # Connect natively to PO OTC WebSocket
        client = AsyncPocketOptionClient(PO_SSID, is_demo=True)
        await client.connect()
        
        # Pull latest 50 candlesticks
        df = await client.get_candles_dataframe(pair, tf_seconds, count=50)
        await client.disconnect()
        
        if df.empty:
            bot.send_message(chat_id, "⚠️ Pocket Option returned empty data. Please try again.")
            return

        # Fast Aggressive Indicator Math
        rsi = ta.momentum.RSIIndicator(close=df['close'], window=7).rsi()
        macd = ta.trend.MACD(close=df['close'], window_fast=12, window_slow=26, window_sign=9)
        
        latest_rsi = rsi.iloc[-1]
        latest_macd_diff = macd.macd_diff().iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # Evaluate Strategy
        signal = "⏳ NO CLEAR SIGNAL (Market Neutral)"
        emoji = "⚪"
        
        if latest_rsi > 45 and latest_rsi < 65 and latest_macd_diff > 0:
            signal = "CALL (BUY)"
            emoji = "🟢"
        elif latest_rsi < 55 and latest_rsi > 35 and latest_macd_diff < 0:
            signal = "PUT (SELL)"
            emoji = "🔴"

        # Final Signal Output Layout
        signal_message = (
            f"🚨 **POCKET OPTION OTC SIGNAL** 🚨\n"
            f"-------------------------------------\n"
            f"📈 **Asset:** {pair.upper().replace('_OTC', ' OTC')}\n"
            f"⏱️ **Timeframe:** {tf_text}\n"
            f"💵 **Current Price:** {current_price}\n"
            f"-------------------------------------\n"
            f"⚡ **Action:** {emoji} **{signal}**\n"
            f"⏳ **Expiration Recommendation:** {tf_text}\n\n"
            f"ℹ️ _RSI: {latest_rsi:.1f} | MACD Diff: {latest_macd_diff:.4f}_"
        )
        
        # Send the final signal!
        bot.send_message(chat_id, signal_message, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error analyzing chart: {str(e)}")

if __name__ == "__main__":
    print("🤖 Manual Telegram Signal Bot is active...")
    bot.infinity_polling()
    
