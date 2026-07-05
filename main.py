import os
import base64
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# ==============================
# 🧠 SEND IMAGE TO AI
# ==============================
def analyze_with_ai(image_path):
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json"
    }

    prompt = """
You are a professional forex trader.

Analyze this chart screenshot and return STRICT JSON:

{
 "trend": "bullish or bearish",
 "entry": "price or zone",
 "stop_loss": "price",
 "take_profit_1": "price",
 "take_profit_2": "price",
 "confidence": "0-100",
 "reason": "short explanation"
}

Rules:
- Be realistic (not always high confidence)
- Use price zones visible
- If unclear → return "no trade"
"""

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 500
    }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload
    )

    return response.json()

# ==============================
# 🧾 FORMAT RESULT
# ==============================
def format_signal(data):
    try:
        content = data["choices"][0]["message"]["content"]

        return f"""
📊 AI TRADE SETUP

{content}
"""
    except:
        return "❌ Failed to analyze image"

# ==============================
# 🤖 TELEGRAM HANDLER
# ==============================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()

    path = "chart.jpg"
    await file.download_to_drive(path)

    await update.message.reply_text("🧠 Analyzing with AI...")

    result = analyze_with_ai(path)
    message = format_signal(result)

    await update.message.reply_text(message)

# ==============================
# ▶️ RUN BOT
# ==============================
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

print("🚀 AI PRO BOT RUNNING...")
app.run_polling()
