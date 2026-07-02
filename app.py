from flask import Flask, request, render_template, jsonify
import os
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import numpy as np
import datetime

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def preprocess_image(image):
    """Improve image for better OCR"""
    # Convert to grayscale
    gray = image.convert('L')
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.0)
    # Sharpen
    enhanced = enhanced.filter(ImageFilter.SHARPEN)
    return enhanced

def analyze_chart(image):
    try:
        processed = preprocess_image(image)
        text = pytesseract.image_to_string(processed, config=r'--oem 3 --psm 6')
        lower_text = text.lower()
        
        score = 0
        reasons = []
        
        # Bullish signals
        if any(word in lower_text for word in ['bull', 'uptrend', 'breakout', 'support', 'buy', 'long']):
            score += 2
            reasons.append("Bullish keywords detected")
        # Bearish signals
        if any(word in lower_text for word in ['bear', 'downtrend', 'breakdown', 'resistance', 'sell', 'short']):
            score -= 2
            reasons.append("Bearish keywords detected")
        
        # Color analysis simulation (simple)
        if "green" in lower_text or "bull" in lower_text:
            score += 1
        if "red" in lower_text or "bear" in lower_text:
            score -= 1
        
        # Final trend
        if score >= 2:
            trend = "Bullish"
            confidence = "High"
        elif score <= -2:
            trend = "Bearish"
            confidence = "High"
        elif score > 0:
            trend = "Slightly Bullish"
            confidence = "Medium"
        elif score < 0:
            trend = "Slightly Bearish"
            confidence = "Medium"
        else:
            trend = "Neutral / Sideways"
            confidence = "Low"
        
        analysis = {
            "timestamp": datetime.datetime.now().isoformat(),
            "extracted_text": text.strip()[:700],
            "trend": trend,
            "confidence": confidence,
            "score": score,
            "reasons": reasons[:5]
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
