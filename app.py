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

# ================= IMPROVED CANDLE DETECTION =================
def detect_candles(image):
    img = np.array(image.convert("RGB").resize((300, 300)))

    green_pixels = (img[:,:,1] > 140) & (img[:,:,0] < 120)
    red_pixels   = (img[:,:,0] > 140) & (img[:,:,1] < 120)

    green = np.sum(green_pixels)
    red   = np.sum(red_pixels)

    patterns = []
    strength = 0

    total = green + red + 1

    green_ratio = green / total
    red_ratio   = red / total

    # 🔥 stronger logic
    if green_ratio > 0.6:
        patterns.append("Strong Bullish Pressure")
        strength += 2
    elif red_ratio > 0.6:
        patterns.append("Strong Bearish Pressure")
        strength += 2

    elif green_ratio > 0.52:
        patterns.append("Bullish Bias")
        strength += 1
    elif red_ratio > 0.52:
        patterns.append("Bearish Bias")
        strength += 1

    return patterns, strength

# ================= IMPROVED SUPPORT / RESISTANCE =================
def detect_support_resistance(image):
    img = np.array(image.convert("RGB").resize((300, 300)))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 50, 150)

    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 120,
                            minLineLength=80, maxLineGap=5)

    zones = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]

            if abs(y1 - y2) < 5:  # tighter filter
                zones.append(y1)

    # 🔥 reduce noise
    zones = list(set([round(z, -1) for z in zones]))

    return zones

# ================= IMPROVED TREND =================
def detect_trend(image):
    img = np.array(image.convert("RGB").resize((300, 300)))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 50, 150)

    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 120)

    slopes = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]

            if abs(x2 - x1) > 10:
                slope = (y2 - y1) / (x2 - x1)
                slopes.append(slope)

    if len(slopes) < 5:
        return "SIDEWAYS"

    avg = np.mean(slopes)

    # 🔥 less sensitive
    if avg > 0.3:
        return "UPTREND"
    elif avg < -0.3:
        return "DOWNTREND"
    else:
        return "SIDEWAYS"

# ================= IMPROVED AI SCORE =================
def ai_score(patterns, candle_score, zones, trend):
    score = 0

    score += candle_score

    if trend == "UPTREND":
        score += 2
    elif trend == "DOWNTREND":
        score -= 2

    if len(zones) >= 2 and len(zones) <= 6:
        score += 2  # good structure
    elif len(zones) > 10:
        score -= 1  # too noisy

    # 🔥 smarter result
    if score >= 5:
        return "STRONG"
    elif score >= 3:
        return "MEDIUM"
    else:
        return "WEAK"


# ================= MAIN ANALYSIS =================
def analyze_chart(image):
    processed = preprocess_image(image)

    patterns, candle_score = detect_candles(processed)
    zones = detect_support_resistance(processed)
    trend = detect_trend(processed)

    strength = ai_score(patterns, candle_score, zones, trend)

    # Decision
    signal = "NO SIGNAL"

if strength == "STRONG":
    if trend == "UPTREND" and "Strong Bullish Pressure" in patterns:
        signal = "BUY"

    elif trend == "DOWNTREND" and "Strong Bearish Pressure" in patterns:
        signal = "SELL"

    if trend == "SIDEWAYS":
        signal = "NO SIGNAL"

    return 
        {
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
