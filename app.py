from flask import Flask, request, render_template, jsonify
import os
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
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
    gray = image.convert('L')
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.0)
    enhanced = enhanced.filter(ImageFilter.SHARPEN)
    return enhanced

# ================= CANDLE DETECTION =================
def detect_candles(image):
    img = np.array(image.resize((200, 200)))

    green = np.sum((img[:,:,1] > 150) & (img[:,:,0] < 100))
    red = np.sum((img[:,:,0] > 150) & (img[:,:,1] < 100))

    total = green + red + 1
    green_ratio = green / total
    red_ratio = red / total

    pattern = None
    score = 0

    if green_ratio > 0.65:
        pattern = "Bullish Engulfing Zone"
        score += 2
    elif red_ratio > 0.65:
        pattern = "Bearish Engulfing Zone"
        score -= 2

    if 0.45 < green_ratio < 0.55:
        pattern = "Doji / Indecision"
        score -= 1

    return pattern, score

# ================= SUPPORT / RESISTANCE =================
def detect_zones(image):
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    horizontal = np.sum(edges, axis=1)
    peaks = np.where(horizontal > np.mean(horizontal) * 1.5)[0]

    score = 0
    zone_type = None

    if len(peaks) > 5:
        zone_type = "Strong S/R Zone"
        score += 2
    elif len(peaks) > 2:
        zone_type = "Weak S/R Zone"
        score += 1

    return zone_type, score

# ================= TREND DETECTION =================
def detect_trend(image):
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=50, maxLineGap=10)

    slope_score = 0
    trend = None

    if lines is not None:
        slopes = []
        for line in lines[:20]:
            x1, y1, x2, y2 = line[0]
            if x2 - x1 != 0:
                slope = (y2 - y1) / (x2 - x1)
                slopes.append(slope)

        if slopes:
            avg = np.mean(slopes)

            if avg < -0.2:
                trend = "Uptrend"
                slope_score += 2
            elif avg > 0.2:
                trend = "Downtrend"
                slope_score -= 2

    return trend, slope_score

# ================= MAIN ANALYSIS =================
def analyze_chart(image):
    try:
        processed = preprocess_image(image)
        text = pytesseract.image_to_string(processed, config=r'--oem 3 --psm 6')
        lower_text = text.lower()

        score = 0
        reasons = []

        # TEXT SIGNALS
        if any(w in lower_text for w in ['buy', 'bull', 'support']):
            score += 2
            reasons.append("Bullish text")

        if any(w in lower_text for w in ['sell', 'bear', 'resistance']):
            score -= 2
            reasons.append("Bearish text")

        # CANDLES
        candle_pattern, candle_score = detect_candles(image)
        score += candle_score
        if candle_pattern:
            reasons.append(candle_pattern)

        # SUPPORT / RESISTANCE
        zone, zone_score = detect_zones(image)
        score += zone_score
        if zone:
            reasons.append(zone)

        # TREND
        trend, trend_score = detect_trend(image)
        score += trend_score
        if trend:
            reasons.append(trend)

        # RSI TEXT
        if "rsi" in lower_text:
            if "30" in lower_text:
                score += 2
                reasons.append("RSI Oversold")
            elif "70" in lower_text:
                score -= 2
                reasons.append("RSI Overbought")

        # FINAL DECISION
        if score >= 6:
            trend_out = "STRONG BUY"
            confidence = "High"
        elif score >= 3:
            trend_out = "BUY"
            confidence = "Medium"
        elif score <= -6:
            trend_out = "STRONG SELL"
            confidence = "High"
        elif score <= -3:
            trend_out = "SELL"
            confidence = "Medium"
        else:
            trend_out = "NEUTRAL"
            confidence = "Low"

        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "extracted_text": text[:400],
            "trend": trend_out,
            "confidence": confidence,
            "score": score,
            "reasons": reasons[:6]
        }

    except Exception as e:
        return {"error": str(e)}

# ================= ROUTES =================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
        try:
            filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            image = Image.open(filepath)
            result = analyze_chart(image)

            return jsonify({
                "status": "success",
                "filename": filename,
                "analysis": result
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "Invalid file type"}), 400

# ================= RUN =================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
