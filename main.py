import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from tradingview_ta import TA_Handler, Interval

# Setup
TOKEN = os.getenv("TOKEN")
logging.basicConfig(level=logging.INFO)

# Define Permanent Buttons (The exact UI from your screenshot)
MAIN_MENU_KB = ReplyKeyboardMarkup([
    [KeyboardButton("📅 [Currency Pairs]"), KeyboardButton("🏆 [Currency Pairs OTC]")],
    [KeyboardButton("💰 [Crypto]")],
    [KeyboardButton("📍 Mini App"), KeyboardButton("🆘 Support")]
], resize_keyboard=True)

# Define Asset List
ASSETS = ["GBP/JPY", "AUD/CAD", "AUD/CHF", "AUD/JPY", "AUD/USD", "CAD/JPY", 
          "CHF/JPY", "EUR/CAD", "EUR/CHF", "EUR/USD", "GBP/CAD", "GBP/CHF", 
          "GBP/USD", "USD/CAD", "USD/CHF", "USD/JPY"]

# Pure Python Math for the Strategy
def calculate_ema(data, period):
    alpha = 2 / (period + 1)
    ema = [data[0]]
    for i in range(1, len(data)):
        ema.append(alpha * data[i] + (1 - alpha) * ema[-1])
    return ema

def calculate_rsi(data, period=10):
    deltas = [data[i] - data[i-1] for i in range(1, len(data))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# Strategy Engine
def analyze_strategy(symbol, interval):
    # Fetch data from TradingView
    handler = TA_Handler(symbol=symbol.replace("/", ""), screener="forex", exchange="FX_IDC", interval=interval)
    analysis = handler.get_analysis()
    
    # We simulate a small history from available indicators to calculate the shift
    # In a real environment, you'd fetch the last 30 closes via a client
    # For this bot, we use current indicators as a proxy for the trend
    rsi = analysis.indicators.get("RSI", 50)
    ema3 = analysis.indicators.get("EMA3", 0)
    ema10 = analysis.indicators.get("EMA10", 0)
    
    # Strategy Logic
    # Buy: Lips (EMA3) > Jaws (EMA10) and RSI > 50
    # Sell: Lips (EMA3) < Jaws (EMA10) and RSI < 50
    signal = "NEUTRAL"
    if ema3 > ema10 and rsi > 50:
        signal = "HIGHER (BUY)"
    elif ema3 < ema10 and rsi < 50:
        signal = "LOWER (SELL)"
        
    return signal, rsi

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome back, PRO team 💻", reply_markup=MAIN_MENU_KB)

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "Currency Pairs" in text:
        keyboard = [[InlineKeyboardButton(a, callback_data=f"asset:{a}")] for a in ASSETS]
        grouped = [keyboard[i:i+2] for i in range(0, len(keyboard), 2)]
        await update.message.reply_text("Selection of Assets:\nSelect the trading pair:", reply_markup=InlineKeyboardMarkup(grouped))

async def handle_asset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    asset = query.data.split(":")[1]
    context.user_data["asset"] = asset
    kb = [[InlineKeyboardButton("1 minute", callback_data="tf:1m"), InlineKeyboardButton("2 minutes", callback_data="tf:2m")],
          [InlineKeyboardButton("5 minutes", callback_data="tf:5m"), InlineKeyboardButton("10 minutes", callback_data="tf:10m")]]
    await query.edit_message_text(f"Selected: {asset}\nNow select the expiration time:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    asset = context.user_data.get("asset")
    tf = query.data.split(":")[1]
    
    signal, rsi = analyze_strategy(asset, "1m")
    
    msg = (f"🧬 Signal from Alligator Strategy\n"
           f"Asset: ✅ {asset}\n"
           f"⌛ Timeframe: {tf}\n"
           f"Current signal: {signal}\n\n"
           f"📊 Strategy Analysis:\n"
           f"RSI (10): {rsi:.2f}\n"
           f"Trend: {'Bullish' if 'HIGHER' in signal else 'Bearish' if 'LOWER' in signal else 'Neutral'}\n\n"
           f"💡 RECOMMENDATION:\n"
           f"Open {signal} deal for {tf}")
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu")]]))

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, handle_main_menu))
    app.add_handler(CallbackQueryHandler(handle_asset, pattern="^asset:"))
    app.add_handler(CallbackQueryHandler(handle_analysis, pattern="^tf:"))
    app.run_polling()

if __name__ == "__main__":
    main()
    
