from flask import Flask, request, jsonify
from PIL import Image
import numpy as np
import cv2

from tradingview_ta import TA_Handler, Interval

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

# ================= IMAGE ANALYSIS =================
def detect_candles(image):
    img = np.array(image.convert("RGB").resize((300, 300)))

    green = np.sum((img[:,:,1] > 140) & (img[:,:,0] < 120))
    red   = np.sum((img[:,:,0] > 140) & (img[:,:,1] < 120))

    total = green + red + 1

    if green / total > 0.55:
        return "BULLISH"
    elif red / total > 0.55:
        return "BEARISH"
    else:
        return "NEUTRAL"


def detect_trend(image):
    img = np.array(image.convert("RGB").resize((300, 300)))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100)

    slopes = []

    if lines is not None:
        for line in lines:
            x1,y1,x2,y2 = line[0]
            if abs(x2-x1) > 10:
                slopes.append((y2-y1)/(x2-x1))

    if len(slopes) < 5:
        return "SIDEWAYS"

    avg = np.mean(slopes)

    if avg > 0.3:
        return "UPTREND"
    elif avg < -0.3:
        return "DOWNTREND"
    else:
        return "SIDEWAYS"

# ================= FOREX DATA =================
def get_forex(symbol):
    handler = TA_Handler(
        symbol=symbol,
        screener="forex",
        exchange="FX_IDC",
        interval=Interval.INTERVAL_5_MINUTES
    )
    return handler.get_analysis()

# ================= MAIN AI =================
def analyze_chart(image, symbol="EURUSD"):
    candle = detect_candles(image)
    trend_img = detect_trend(image)

    data = get_forex(symbol)

    rsi = data.indicators["RSI"]
    ema = data.indicators["EMA10"]
    price = data.indicators["close"]

    trend_data = "UPTREND" if price > ema else "DOWNTREND"

    signal = "NO SIGNAL"

    # ================= HYBRID LOGIC =================
    if (
        candle == "BULLISH" and
        trend_img == "UPTREND" and
        trend_data == "UPTREND" and
        rsi < 40
    ):
        signal = "BUY"

    elif (
        candle == "BEARISH" and
        trend_img == "DOWNTREND" and
        trend_data == "DOWNTREND" and
        rsi > 60
    ):
        signal = "SELL"

    return {
        "signal": signal,
        "image_trend": trend_img,
        "data_trend": trend_data,
        "candle_bias": candle,
        "rsi": round(rsi, 2)
    }

# ================= ROUTE =================
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]

    symbol = request.form.get("symbol", "EURUSD")

    image = Image.open(file.stream)

    result = analyze_chart(image, symbol)

    return jsonify(result)

# ================= START =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
