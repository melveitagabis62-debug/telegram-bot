import os
import asyncio
import urllib.parse
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import pandas as pd
import ta
from pocketoptionapi_async import AsyncPocketOptionClient

# Environment Variables from Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
PO_SSID = os.getenv("PO_SSID")

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
    USER_STATE[chat_id]['timeframe_seconds'] = TIMEFRAME_MAP[tf_text]
    
    pair = USER_STATE[chat_id]['pair']
    
    await bot.answer_callback_query(call.id)
    
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"⏳ Pulling live OTC data for **{pair.upper().replace('_OTC', ' OTC')}** ({tf_text})...\nAnalyzing indicators..."
    )
    
    await run_otc_analysis(chat_id, call.message.message_id)

# --- CORE STRATEGIC ANALYSIS ---
async def run_otc_analysis(chat_id, message_id):
    pair = USER_STATE[chat_id]['pair']
    tf_seconds = USER_STATE[chat_id]['timeframe_seconds']
    tf_text = USER_STATE[chat_id]['timeframe_text']
    
    if not PO_SSID:
        await bot.send_message(chat_id, "❌ Error: `PO_SSID` variable is missing or blank on Railway!")
        return

    # Advanced data normalizer to unpack raw or encoded mobile data variants flawlessly
    raw_decoded = urllib.parse.unquote(PO_SSID.strip().replace('"', '').replace("'", ""))
    
    # Strip away any 'ci_session=' prefix strings to match expected API structures
    if raw_decoded.startswith("ci_session="):
        clean_ssid = raw_decoded.replace("ci_session=", "")
    else:
        clean_ssid = raw_decoded

    try:
        # Initializing clean client with zero extra arguments
        client = AsyncPocketOptionClient(clean_ssid, is_demo=True)
        await client.connect()
        
        df = await client.get_candles_dataframe(pair, tf_seconds, count=50)
        await client.disconnect()
        
        if df is None or df.empty:
            await bot.send_message(chat_id, "⚠️ Server replied with an empty stream. Your session token might have expired. Try re-copying it!")
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
        await bot.send_message(chat_id, f"❌ Connection Error: {str(e)}")

if __name__ == "__main__":
    print("🤖 Async Manual Telegram Signal Bot is running...")
    asyncio.run(bot.infinity_polling())
    
