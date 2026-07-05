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
You are an elite sniper trader.

Analyze this chart and SCORE it.

Scoring system:
- Trend alignment (2 pts)
- Support/Resistance reaction (2 pts)
- Engulfing pattern (2 pts)
- Doji rejection (1 pt)
- Strong momentum (1 pt)
- Clean structure (1 pt)

Max score = 9

RULES:
- Score >=5 → VALID TRADE
- Score 3-4 → WEAK TRADE
- Score <3 → NO TRADE

Return EXACT format:

Signal: BUY / SELL / NO TRADE
Score: X/9
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
        image_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"

        # AI Analysis
        result = analyze_image(image_url)

        # Extract score
        import re
        match = re.search(r"Score:\s*(\d+)", result)

        score = int(match.group(1)) if match else 0

            # SMART FILTER (NOT TOO STRICT)
        if score < 3:
    
            await update.message.reply_text("⏳ No setup (too weak)")
                
                return

            # Allow weak trades but mark them
        if 3 <= score <= 4:
            await update.message.reply_text(f"⚠️ WEAK SETUP\n\n{result}")
                
                return

         # Strong trades
            await update.message.reply_text(f"🔥 STRONG SETUP\n\n{result}")

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
