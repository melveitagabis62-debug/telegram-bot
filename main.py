import os
import asyncio
import logging
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pocketoptionapi.stable_api import PocketOption

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurable Variables (Loaded from Railway Environment)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
POCKET_SSID = os.getenv("POCKET_OPTION_SSID")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", "2.0"))
IS_DEMO = os.getenv("IS_DEMO", "True").lower() == "true"

# Global state to control the bot via Telegram
bot_active = False
trading_task = None

def calculate_strategy(candles_list):
    """Calculates indicators on the last 20 candles and checks for signals"""
    df = pd.DataFrame(candles_list)
    if len(df) < 15:
        return None, None, None

    # 1. RSI 10 Calculation
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=10).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=10).mean()
    rs = gain / (loss + 1e-9) # avoid division by zero
    df['rsi'] = 100 - (100 / (1 + rs))

    # 2. Williams Alligator (Stanley's simplified settings)
    # Jaws: Period 10, Shift 5 | Lips: Period 3, Shift 1
    df['jaws'] = df['close'].ewm(span=10, adjust=False).mean().shift(5)
    df['lips'] = df['close'].ewm(span=3, adjust=False).mean().shift(1)

    return df.iloc[-2], df.iloc[-1] # Return previous and current candle data

async def strategy_loop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Background engine checking the 30s chart for entries"""
    global bot_active
    chat_id = update.effective_chat.id
    
    await context.bot.send_message(chat_id=chat_id, text="🔄 Connecting to Pocket Option...")
    
    # Initialize connection using the SSID token
    api = PocketOption(ssid=POCKET_SSID)
    success, error = api.connect()
    
    if not success:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Connection failed: {error}")
        bot_active = False
        return

    # Set Demo or Real Account
    balance_type = "PRACTICE" if IS_DEMO else "REAL"
    api.change_balance(balance_type)
    initial_balance = api.get_balance()
    
    await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🟢 Bot Active! Platform: {balance_type}\nInitial Balance: ${initial_balance}"
    )

    asset = "EURUSD_otc" # Example asset
    api.start_candles_stream(asset, 20)

    while bot_active:
        try:
            candles = api.get_realtime_candles(asset)
            if len(candles) >= 20:
                # Format to a readable list of dicts with float close prices
                formatted_candles = [{"close": float(c["close"])} for c in candles.values()]
                prev_candle, curr_candle = calculate_strategy(formatted_candles)
                
                if prev_candle is not None:
                    # Signal Logic: Check for bullish/bearish crossovers
                    bullish_crossover = (prev_candle['lips'] <= prev_candle['jaws']) and (curr_candle['lips'] > curr_candle['jaws'])
                    bullish_rsi = (prev_candle['rsi'] <= 50) and (curr_candle['rsi'] > 50)
                    
                    bearish_crossover = (prev_candle['lips'] >= prev_candle['jaws']) and (curr_candle['lips'] < curr_candle['jaws'])
                    bearish_rsi = (prev_candle['rsi'] >= 50) and (curr_candle['rsi'] < 50)

                    # Trigger CALL (Buy)
                    if bullish_crossover and bullish_rsi:
                        await context.bot.send_message(chat_id=chat_id, text=f"📈 BUY Signal Detected! Placing CALL trade...")
                        api.buy(asset, TRADE_AMOUNT, "call", 60) # 1-minute expiration

                    # Trigger PUT (Sell)
                    elif bearish_crossover and bearish_rsi:
                        await context.bot.send_message(chat_id=chat_id, text=f"📉 SELL Signal Detected! Placing PUT trade...")
                        api.buy(asset, TRADE_AMOUNT, "put", 60)

            await asyncio.sleep(5) # Check state every 5 seconds
        except Exception as e:
            logger.error(f"Error in strategy loop: {e}")
            await asyncio.sleep(10)

    api.close()
    await context.bot.send_message(chat_id=chat_id, text="🔴 Bot stopped successfully.")

async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active, trading_task
    if bot_active:
        await update.message.reply_text("⚠️ The bot is already running!")
        return
    bot_active = True
    trading_task = asyncio.create_task(strategy_loop(update, context))

async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    if not bot_active:
        await update.message.reply_text("⚠️ The bot is already stopped.")
        return
    bot_active = False
    await update.message.reply_text("🛑 Stopping the bot...")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start_bot))
    application.add_handler(CommandHandler("stop", stop_bot))
    application.run_polling()

if __name__ == "__main__":
    main()
    
