from flask import Flask, request, render_template, jsonify
import os
from PIL import Image, ImageEnhance, ImageFilter, ImageStat
import numpy as np
import datetime

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def preprocess_image(image):
    gray = image.convert('L')
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.5)
    enhanced = enhanced.filter(ImageFilter.SHARPEN)
    return enhanced

def analyze_chart(image):
    try:
        processed = preprocess_image(image)
        text = pytesseract.image_to_string(processed, config=r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,%+- ')
        lower = text.lower().strip()
        
        score = 0
        reasons = []
        
        bullish_words = ['bull', 'uptrend', 'breakout', 'support', 'buy', 'long', 'bounce', 'reversal up']
        bearish_words = ['bear', 'downtrend', 'breakdown', 'resistance', 'sell', 'short', 'drop', 'reversal down']
        
        if any(w in lower for w in bullish_words):
            score += 3
            reasons.append("Strong bullish keywords")
        if any(w in lower for w in bearish_words):
            score -= 3
            reasons.append("Strong bearish keywords")
        
        # Advanced heuristics
        if "rsi" in lower and ("oversold" in lower or "30" in lower):
            score += 2
            reasons.append("RSI oversold")
        if "rsi" in lower and ("overbought" in lower or "70" in lower):
            score -= 2
            reasons.append("RSI overbought")
        
        if "ma" in lower or "moving average" in lower:
            if "cross" in lower and "up" in lower:
                score += 2
        
        # Final decision
        if score >= 4:
            trend = "Strong Bullish"
            confidence = "High"
        elif score >= 2:
            trend = "Bullish"
            confidence = "Medium-High"
        elif score <= -4:
            trend = "Strong Bearish"
            confidence = "High"
        elif score <= -2:
            trend = "Bearish"
            confidence = "Medium-High"
        else:
            trend = "Neutral / Sideways"
            confidence = "Medium"
        
        analysis = {
            "timestamp": datetime.datetime.now().isoformat(),
            "extracted_text": text.strip()[:800],
            "trend": trend,
            "confidence": confidence,
            "score": score,
            "reasons": reasons
        }
        
        return analysis
    except Exception as e:
        return {"error": str(e)}

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
