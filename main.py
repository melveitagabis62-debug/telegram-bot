import os
import asyncio
import logging
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

def calculate_ema(values, span):
    """Calculates Exponential Moving Average (matches Pandas EWM)"""
    if not values:
        return []
    alpha = 2 / (span + 1)
    ema_values = [values[0]]
    for val in values[1:]:
        ema_values.append(alpha * val + (1 - alpha) * ema_values[-1])
    return ema_values

def calculate_rsi(closes, period=10):
    """Calculates Relative Strength Index in pure Python"""
    if len(closes) < period + 1:
        return [50.0] * len(closes)
    
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]
    
    rsi_values = [50.0] * period  # Fill initial values
    for i in range(period - 1, len(deltas)):
        avg_gain = sum(gains[i - period + 1 : i + 1]) / period
        avg_loss = sum(losses[i - period + 1 : i + 1]) / period
        if avg_loss == 0:
            rsi_val = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            rsi_val = 100.0 - (100.0 / (1.0 + rs))
        rsi_values.append(rsi_val)
    return rsi_values

def check_signals(candles_list):
    """Parses raw candle prices and checks for indicator crossovers"""
    if len(candles_list) < 20:
        return False, False
        
    closes = [float(c["close"]) for c in candles_list]
    
    # Calculate indicators
    ema_10 = calculate_ema(closes, 10)
    ema_3 = calculate_ema(closes, 3)
    rsi_values = calculate_rsi(closes, 10)
    
    # Williams Alligator (with shift offsets extracted manually)
    curr_jaws = ema_10[-6]  # shift 5
    prev_jaws = ema_10[-7]
    
    curr_lips = ema_3[-2]   # shift 1
    prev_lips = ema_3[-3]
    
    curr_rsi = rsi_values[-1]
    prev_rsi = rsi_values[-2]
    
    # 1. Bullish (BUY/Call) Crossover
    bullish_crossover = (prev_lips <= prev_jaws) and (curr_lips > curr_jaws)
    bullish_rsi = (prev_rsi <= 50) and (curr_rsi > 50)
    buy_signal = bullish_crossover and bullish_rsi
    
    # 2. Bearish (SELL/Put) Crossover
    bearish_crossover = (prev_lips >= prev_jaws) and (curr_lips < curr_jaws)
    bearish_rsi = (prev_rsi >= 50) and (curr_rsi < 50)
    sell_signal = bearish_crossover and bearish_rsi
    
    return buy_signal, sell_signal

async def strategy_loop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Background engine checking the 30s chart for entries"""
    global bot_active
    chat_id = update.effective_chat.id
    
    await context.bot.send_message(chat_id=chat_id, text="🔄 Connecting to Pocket Option...")
    
    api = PocketOption(ssid=POCKET_SSID)
    success, error = api.connect()
    
    if not success:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Connection failed: {error}")
        bot_active = False
        return

    balance_type = "PRACTICE" if IS_DEMO else "REAL"
    api.change_balance(balance_type)
    initial_balance = api.get_balance()
    
    await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🟢 Bot Active! Platform: {balance_type}\nInitial Balance: ${initial_balance}"
    )

    asset = "EURUSD_otc"
    api.start_candles_stream(asset, 20)

    while bot_active:
        try:
            candles = api.get_realtime_candles(asset)
            if len(candles) >= 20:
                # Sort candles chronologically by their timestamp keys
                sorted_candles = [candles[k] for k in sorted(candles.keys())]
                buy_signal, sell_signal = check_signals(sorted_candles)
                
                if buy_signal:
                    await context.bot.send_message(chat_id=chat_id, text="📈 BUY Signal Detected! Placing CALL trade...")
                    api.buy(asset, TRADE_AMOUNT, "call", 60)

                elif sell_signal:
                    await context.bot.send_message(chat_id=chat_id, text="📉 SELL Signal Detected! Placing PUT trade...")
                    api.buy(asset, TRADE_AMOUNT, "put", 60)

            await asyncio.sleep(5)  # Check state every 5 seconds
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
        
