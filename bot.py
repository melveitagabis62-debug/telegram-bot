import os
import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import pandas as pd
import ta
from pocketoptionapi_async import AsyncPocketOptionClient

# Environment Variables from Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
PO_SSID = os.getenv("PO_SSID")

# Switching to full AsyncTeleBot to handle asynchronous calls natively
bot = AsyncTeleBot(TELEGRAM_TOKEN)

# Temporary dictionary to store user selections
USER_STATE = {}

# Timeframe mapping
TIMEFRAME_MAP = {
    "1 Min": 60,
    "3 Mins": 180,
    "5 Mins": 300
}

# --- MENU 1: Choose Pair ---
@bot.message_handler(commands=['analyze', 'start'])
async def start_manual_analysis(message):
    chat_id = message.chat.id
    USER_STATE[chat_id] = {}  # Reset state
    
    markup = InlineKeyboardMarkup(row_width=2)
    # Lowercase asset names matching the API requirements
    pairs = ["eurusd_otc", "gbpusd_otc", "audusd_otc", "usdjpy_otc"]
    
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
    
    # Acknowledge the callback query so the loading circle disappears on the phone
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
    USER_STATE[chat_id]['timeframe_seconds'] = TIMEFRAME_MAP[tf_text]
    
    pair = USER_STATE[chat_id]['pair']
    
    await bot.answer_callback_query(call.id)
    
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"⏳ Pulling live OTC data for **{pair.upper().replace('_OTC', ' OTC')}** ({tf_text})...\nAnalyzing indicators..."
    )
    
    # Directly await the async analysis routine safely
    await run_otc_analysis(chat_id, call.message.message_id)

# --- CORE STRATEGIC ANALYSIS ---
async def run_otc_analysis(chat_id, message_id):
    pair = USER_STATE[chat_id]['pair']
    tf_seconds = USER_STATE[chat_id]['timeframe_seconds']
    tf_text = USER_STATE[chat_id]['timeframe_text']
    
    if not PO_SSID:
        await bot.send_message(chat_id, "❌ Error: `PO_SSID` variable is missing on Railway!")
        return

    try:
        client = AsyncPocketOptionClient(PO_SSID, is_demo=True)
        await client.connect()
        
        df = await client.get_candles_dataframe(pair, tf_seconds, count=50)
        await client.disconnect()
        
        if df is None or df.empty:
            await bot.send_message(chat_id, "⚠️ Pocket Option returned empty data. Please verify your PO_SSID cookie or try again.")
            return

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
        
        await bot.send_message(chat_id, signal_message, parse_mode="Markdown")
        
    except Exception as e:
        await bot.send_message(chat_id, f"❌ Error analyzing chart: {str(e)}")

if __name__ == "__main__":
    print("🤖 Async Manual Telegram Signal Bot is running...")
    asyncio.run(bot.infinity_polling())
    
