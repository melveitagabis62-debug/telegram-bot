import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from openai import OpenAI

# ==============================
# CONFIG
# ==============================
BOT_TOKEN = os.getenv("TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

logging.basicConfig(level=logging.INFO)

# ==============================
# AI ANALYSIS FUNCTION
# ==============================
def analyze_image(image_url):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """
You are an elite ICT sniper trader.

Analyze the trading chart using:
- Market trend
- Support & Resistance zones
- Engulfing & Doji candlestick patterns
- Fake breakout detection

STRICT RULES:
- Only give 1 clear signal
- Maximum 3–10 signals per day quality
- Avoid low-quality trades

Return EXACT format:

Signal: BUY / SELL / NO TRADE
Confidence: XX%
Entry: price
Take Profit: price
Stop Loss: price
Reason: short explanation
"""
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url}
                    }
                ]
            }
        ]
    )

    return response.choices[0].message.content

# ==============================
# TELEGRAM HANDLER
# ==============================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("🧠 Analyzing with AI...")

        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)

        file_path = file.file_path

        # Convert to real URL
        image_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        # AI Analysis
        result = analyze_image(image_url)

        # OPTIONAL FILTER (only block VERY weak signals)
        if "NO TRADE" in result:
            await update.message.reply_text("⏳ No valid setup (filtered)")
            return

        await update.message.reply_text(f"📊 AI TRADE SETUP\n\n{result}")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        print("ERROR:", e)

# ==============================
# START BOT
# ==============================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("🚀 AI SNIPER BOT RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
