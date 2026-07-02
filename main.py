from flask import Flask, request, render_template, jsonify
import os
from PIL import Image
import pytesseract
import numpy as np
import datetime

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

def analyze_chart(image):
    try:
        text = pytesseract.image_to_string(image, config=r'--oem 3 --psm 6')
        
        analysis = {
            "timestamp": datetime.datetime.now().isoformat(),
            "extracted_text": text.strip()[:600],
            "image_size": image.size,
            "trend": "Neutral / Unclear",
            "confidence": "Medium",
            "suggestions": []
        }
        
        lower = text.lower()
        if any(x in lower for x in ["bull", "uptrend", "breakout", "support"]):
            analysis["trend"] = "Potentially Bullish"
            analysis["suggestions"].append("Check for volume confirmation")
        elif any(x in lower for x in ["bear", "downtrend", "breakdown", "resistance"]):
            analysis["trend"] = "Potentially Bearish"
            analysis["suggestions"].append("Watch risk levels")
        
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
