import logging
import asyncio
import random
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

# ===== CONFIG =====
TOKEN = "YOUR_BOT_TOKEN_HERE"

PAIRS = ["EURUSD", "GBPUSD", "USDJPY"]
AUTO_MODE = False

# ===== LOGGING =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ===== INDICATOR SIMULATION (Replace later with real data) =====
def generate_signal(pair):
    trend = random.choice(["UP", "DOWN"])
    rsi = random.randint(10, 90)
    macd = random.choice(["BUY", "SELL"])

    if trend == "UP" and rsi < 35 and macd == "BUY":
        return "BUY", random.randint(70, 85)
    elif trend == "DOWN" and rsi > 65 and macd == "SELL":
        return "SELL", random.randint(70, 85)

    return None, 0


# ===== SIGNAL FORMAT =====
def format_signal(pair, signal, confidence):
    entry = round(random.uniform(1.0700, 1.1000), 4)
    tp = round(entry + 0.0020, 4)
    sl = round(entry - 0.0020, 4)

    return f"""
📊 {pair} (M5)

{"🟢 BUY" if signal == "BUY" else "🔴 SELL"}

📍 Entry: {entry}
🎯 TP: {tp}
🛑 SL: {sl}

⚡ Confidence: {confidence}%
🕒 {datetime.now().strftime('%H:%M:%S')}
"""


# ===== COMMANDS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot Activated (PRO MODE)")


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    messages = []

    for pair in PAIRS:
        sig, conf = generate_signal(pair)
        if sig:
            messages.append(format_signal(pair, sig, conf))

    if messages:
        await update.message.reply_text("\n\n".join(messages))
    else:
        await update.message.reply_text("⚠️ No strong signals right now")


async def auto_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTO_MODE
    AUTO_MODE = True
    await update.message.reply_text("🤖 Auto signals ON")


async def auto_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTO_MODE
    AUTO_MODE = False
    await update.message.reply_text("🛑 Auto signals OFF")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = "ON" if AUTO_MODE else "OFF"
    await update.message.reply_text(f"📡 Auto Mode: {mode}")


# ===== AUTO SIGNAL LOOP =====

async def auto_signals(app):
    while True:
        if AUTO_MODE:
            for pair in PAIRS:
                sig, conf = generate_signal(pair)
                if sig and conf >= 75:
                    msg = format_signal(pair, sig, conf)

                    for chat_id in app.chat_data.keys():
                        try:
                            await app.bot.send_message(chat_id=chat_id, text=msg)
                        except:
                            pass

        await asyncio.sleep(60)


# ===== MAIN =====

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("auto_on", auto_on))
    app.add_handler(CommandHandler("auto_off", auto_off))
    app.add_handler(CommandHandler("status", status))

    # ✅ start background task BEFORE polling
    asyncio.create_task(auto_signals(app))

    print("🚀 Bot running...")

    # ✅ run bot
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
