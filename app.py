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


# ================= IMAGE PROCESSING =================
def preprocess_image(image):
    gray = image.convert('L')
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.5)
    enhanced = enhanced.filter(ImageFilter.SHARPEN)
    return enhanced


# ================= EXTRACT TEXT =================
def extract_text(image):
    processed = preprocess_image(image)
    text = pytesseract.image_to_string(
        processed,
        config='--oem 3 --psm 6'
    )
    return text.lower()


# ================= DETECT PRICE LEVELS =================
def extract_numbers(text):
    import re
    numbers = re.findall(r'\d+\.\d+|\d+', text)
    numbers = [float(n) for n in numbers if len(n) > 2]
    return numbers


# ================= SIMPLE TREND LOGIC =================
def analyze_logic(text, numbers):
    score = 0
    reasons = []

    # ---- STRUCTURE KEYWORDS ----
    if "higher high" in text or "uptrend" in text:
        score += 2
        reasons.append("Uptrend structure detected")

    if "lower low" in text or "downtrend" in text:
        score -= 2
        reasons.append("Downtrend structure detected")

    # ---- BREAKOUT / BREAKDOWN ----
    if "breakout" in text:
        score += 2
        reasons.append("Breakout signal")

    if "breakdown" in text:
        score -= 2
        reasons.append("Breakdown signal")

    # ---- SUPPORT / RESISTANCE ----
    if "support" in text:
        score += 1
        reasons.append("Near support")

    if "resistance" in text:
        score -= 1
        reasons.append("Near resistance")

    # ---- MOMENTUM WORDS ----
    if "strong" in text:
        score += 1
    if "weak" in text:
        score -= 1

    # ---- NUMBER-BASED LOGIC ----
    if len(numbers) >= 3:
        if numbers[-1] > numbers[0]:
            score += 1
            reasons.append("Price rising structure")
        else:
            score -= 1
            reasons.append("Price falling structure")

    return score, reasons


# ================= FINAL DECISION =================
def get_signal(score):
    if score >= 3:
        return "STRONG BUY", "High"
    elif score == 2:
        return "BUY", "Medium"
    elif score == 1:
        return "WEAK BUY", "Low"
    elif score == 0:
        return "NO TRADE", "Low"
    elif score == -1:
        return "WEAK SELL", "Low"
    elif score == -2:
        return "SELL", "Medium"
    else:
        return "STRONG SELL", "High"


# ================= MAIN ANALYSIS =================
def analyze_chart(image):
    try:
        text = extract_text(image)
        numbers = extract_numbers(text)

        score, reasons = analyze_logic(text, numbers)
        signal, confidence = get_signal(score)

        analysis = {
            "timestamp": datetime.datetime.now().isoformat(),
            "signal": signal,
            "confidence": confidence,
            "score": score,
            "numbers_detected": numbers[:10],
            "reasons": reasons[:5],
            "raw_text": text[:500]
        }

        return analysis

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
                "analysis": result
            })

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "Invalid file type"}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
