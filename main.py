import os
import cv2
import numpy as np
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TOKEN")

last_signals = []

# ==============================
# 📊 CANDLE + PATTERN ENGINE
# ==============================
def detect_candles(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Green mask
    green = cv2.inRange(hsv, (35, 50, 50), (85, 255, 255))
    # Red mask
    red1 = cv2.inRange(hsv, (0, 50, 50), (10, 255, 255))
    red2 = cv2.inRange(hsv, (170, 50, 50), (180, 255, 255))
    red = red1 + red2

    return green, red

def detect_engulfing(green, red):
    g = np.sum(green > 0)
    r = np.sum(red > 0)

    if g > r * 1.5:
        return "BULLISH_ENGULFING"
    elif r > g * 1.5:
        return "BEARISH_ENGULFING"
    return None

def detect_doji(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 30, 100)
    edge_count = np.sum(edges > 0)

    if 15000 < edge_count < 30000:
        return True
    return False

# ==============================
# 📈 SUPPORT / RESISTANCE
# ==============================
def detect_sr(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(blur, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)

    support = 0
    resistance = 0

    if lines is not None:
        for line in lines:
            x1,y1,x2,y2 = line[0]
            if abs(y1 - y2) < 10:
                if y1 > img.shape[0] * 0.6:
                    support += 1
                elif y1 < img.shape[0] * 0.4:
                    resistance += 1

    return support, resistance

# ==============================
# 🧠 MULTI-TF (FAKE CONFIRMATION)
# ==============================
def multi_tf_logic(trend_strength):
    if trend_strength > 60000:
        return "STRONG"
    elif trend_strength > 30000:
        return "MEDIUM"
    return "WEAK"

# ==============================
# 🎯 MAIN ANALYZER
# ==============================
def analyze_chart(path):
    img = cv2.imread(path)

    if img is None:
        return "ERROR ❌", 0

    img = cv2.resize(img, (800, 600))

    green, red = detect_candles(img)
    engulfing = detect_engulfing(green, red)
    doji = detect_doji(img)
    support, resistance = detect_sr(img)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    trend_strength = np.sum(edges > 0)

    tf = multi_tf_logic(trend_strength)

    g = np.sum(green > 0)
    r = np.sum(red > 0)

    confidence = 50

    # ==============================
    # 📊 DECISION ENGINE
    # ==============================
    if engulfing == "BULLISH_ENGULFING":
        confidence += 20
    if engulfing == "BEARISH_ENGULFING":
        confidence += 20

    if doji:
        confidence -= 10

    if support > resistance:
        confidence += 10
    elif resistance > support:
        confidence += 10

    if tf == "STRONG":
        confidence += 15
    elif tf == "WEAK":
        confidence -= 10

    if g > r * 1.2:
        signal = "BUY 📈"
        confidence += 10
    elif r > g * 1.2:
        signal = "SELL 📉"
        confidence += 10
    else:
        signal = "NO TRADE ❌"
        confidence -= 20

    confidence = max(0, min(95, confidence))

    return signal, confidence

# ==============================
# 🚫 SIGNAL FILTER (ANTI-SPAM)
# ==============================
def allow_signal(signal, confidence):
    global last_signals

    now = time.time()

    # keep last 1 hour signals
    last_signals = [t for t in last_signals if now - t < 3600]

    if len(last_signals) >= 10:
        return False

    if confidence < 60:
        return False

    last_signals.append(now)
    return True

# ==============================
# 🤖 TELEGRAM HANDLER
# ==============================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()

    path = "chart.jpg"
    await file.download_to_drive(path)

    signal, confidence = analyze_chart(path)

    if allow_signal(signal, confidence):
        await update.message.reply_text(
            f"📊 {signal}\n"
            f"🔥 Confidence: {confidence}%"
        )
    else:
        await update.message.reply_text("⏳ Filtered (Low quality / Too many signals)")

# ==============================
# ▶️ RUN
# ==============================
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

print("🔥 ULTRA SNIPER BOT RUNNING...")
app.run_polling()
