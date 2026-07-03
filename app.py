from flask import Flask, request, render_template, jsonify
import os
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import datetime
import cv2

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


# ================= IMAGE PREPROCESS =================
def preprocess_image(image):
    enhancer = ImageEnhance.Contrast(image)
    enhanced = enhancer.enhance(2.0)
    enhanced = enhanced.filter(ImageFilter.SHARPEN)
    return enhanced

# ================= CANDLE DETECTION =================
def detect_candles(image):
    img = np.array(image.convert("RGB").resize((300, 300)))
    
    green = np.sum((img[:,:,1] > 150) & (img[:,:,0] < 100))
    red = np.sum((img[:,:,0] > 150) & (img[:,:,1] < 100))

    patterns = []

    # Engulfing logic (simple approximation)
    if green > red * 1.5:
        patterns.append("Bullish Engulfing")

    elif red > green * 1.5:
        patterns.append("Bearish Engulfing")

    # Doji detection (low body vs wick idea)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    if np.mean(edges) < 20:
        patterns.append("Doji")

    return patterns


# ================= SUPPORT / RESISTANCE =================
def detect_support_resistance(image):
    img = np.array(image.convert("RGB").resize((300, 300)))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 50, 150)

    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=50, maxLineGap=10)

    zones = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]

            # horizontal lines = support/resistance
            if abs(y1 - y2) < 10:
                zones.append(y1)

    return zones


# ================= TREND DETECTION =================
def detect_trend(image):
    img = np.array(image.convert("RGB").resize((300, 300)))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 50, 150)

    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100)

    slopes = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]

            if x2 - x1 != 0:
                slope = (y2 - y1) / (x2 - x1)
                slopes.append(slope)

    if len(slopes) == 0:
        return "SIDEWAYS"

    avg = np.mean(slopes)

    if avg > 0.2:
        return "UPTREND"
    elif avg < -0.2:
        return "DOWNTREND"
    else:
        return "SIDEWAYS"


# ================= AI SCORING =================
def ai_score(patterns, zones, trend):
    score = 0

    if "Bullish Engulfing" in patterns:
        score += 3

    if "Bearish Engulfing" in patterns:
        score += 3

    if "Doji" in patterns:
        score -= 1

    if len(zones) > 5:
        score += 2

    if trend == "UPTREND":
        score += 2

    if trend == "DOWNTREND":
        score += 2

    # Final signal
    if score >= 6:
        return "STRONG"
    elif score >= 3:
        return "MEDIUM"
    else:
        return "WEAK"


# ================= MAIN ANALYSIS =================
def analyze_chart(image):
    processed = preprocess_image(image)

    patterns = detect_candles(processed)
    zones = detect_support_resistance(processed)
    trend = detect_trend(processed)

    strength = ai_score(patterns, zones, trend)

    # Decision
    signal = "NO SIGNAL"

    if strength == "STRONG":
        if trend == "UPTREND":
            signal = "BUY"
        elif trend == "DOWNTREND":
            signal = "SELL"

    return {
        "patterns": patterns,
        "zones_detected": len(zones),
        "trend": trend,
        "strength": strength,
        "signal": signal
    }


# ================= ROUTES =================
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"})

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "Empty filename"})

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    image = Image.open(filepath)

    result = analyze_chart(image)

    return jsonify(result)


# ================= RUN =================
if __name__ == '__main__':
    app.run(debug=True)
