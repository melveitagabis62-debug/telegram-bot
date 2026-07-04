import os
import cv2
import numpy as np
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

# ==============================
# 📊 IMAGE ANALYSIS ENGINE
# ==============================
def analyze_chart(image_path):
    img = cv2.imread(image_path)

    if img is None:
        return "ERROR ❌"

    # Resize for consistency
    img = cv2.resize(img, (800, 600))

    # Convert to HSV
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Detect GREEN candles (BUY pressure)
    lower_green = np.array([35, 50, 50])
    upper_green = np.array([85, 255, 255])
    green_mask = cv2.inRange(hsv, lower_green, upper_green)

    # Detect RED candles (SELL pressure)
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 50, 50])
    upper_red2 = np.array([180, 255, 255])

    red_mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    red_mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    red_mask = red_mask1 + red_mask2

    # Count pixels
    green_strength = np.sum(green_mask > 0)
    red_strength = np.sum(red_mask > 0)

    # Edge detection (trend strength)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    trend_strength = np.sum(edges > 0)

    # ==============================
    # 🎯 DECISION LOGIC
    # ==============================
    if green_strength > red_strength * 1.2 and trend_strength > 40000:
        return "BUY 📈 (Bullish Momentum)"
    elif red_strength > green_strength * 1.2 and trend_strength > 40000:
        return "SELL 📉 (Bearish Momentum)"
    else:
        return "NO TRADE ❌ (Weak / Sideways)"

# ==============================
# 📩 TELEGRAM HANDLER
# ==============================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()

    file_path = "chart.jpg"
    await file.download_to_drive(file_path)

    signal = analyze_chart(file_path)

    await update.message.reply_text(f"📊 Signal: {signal}")

# ==============================
# 🤖 START BOT
# ==============================
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

print("✅ Bot is running...")
app.run_polling()
