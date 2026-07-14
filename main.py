import asyncio
from datetime import datetime
from telegram import Bot
from tradingview_ta import TA_Handler, Interval

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")
CHAT_ID = "YOUR_CHAT_ID"

PAIR = "EURUSD"
TIMEFRAME = Interval.INTERVAL_5_MINUTES

SCAN_INTERVAL = 30  # seconds
COOLDOWN = 300  # 5 minutes between signals

# ================= INIT =================
bot = Bot(token=TOKEN)
last_signal_time = 0

# ================= SESSION FILTER =================
def is_trading_session():
    hour = datetime.utcnow().hour
    return 7 <= hour <= 22  # London + NY

# ================= ENTRY TIMING =================
def get_entry_timing():
    now = datetime.utcnow()
    seconds = now.second

    if seconds >= 50:
        return "⏳ PREPARE (Almost new candle)"
    elif seconds <= 5:
        return "🚀 ENTER NOW (New candle)"
    else:
        return "⌛ WAIT"

# ================= ANALYSIS =================
def get_analysis():
    handler = TA_Handler(
        symbol=PAIR,
        screener="forex",
        exchange="FX_IDC",
        interval=TIMEFRAME
    )
    return handler.get_analysis()

# ================= PRO SIGNAL ENGINE =================
def generate_signal():
    try:
        analysis = get_analysis()
        ind = analysis.indicators

        price = ind["close"]
        rsi = ind["RSI"]
        ema20 = ind["EMA20"]
        ema50 = ind["EMA50"]
        macd = ind["MACD.macd"]
        macd_signal = ind["MACD.signal"]

        high = ind["high"]
        low = ind["low"]
        open_price = ind["open"]

        body = abs(price - open_price)
        candle_range = high - low

        # ================= TREND =================
        trend_up = price > ema50 and ema20 > ema50
        trend_down = price < ema50 and ema20 < ema50

        # ================= MOMENTUM =================
        strong_buy = rsi > 55 and macd > macd_signal
        strong_sell = rsi < 45 and macd < macd_signal

        # ================= CANDLE QUALITY =================
        strong_body = body > (candle_range * 0.5)
        small_candle = candle_range < (price * 0.0005)

        # ================= NO TRADE FILTER =================
        if small_candle:
            return None

        # ================= SNIPER CONDITIONS =================
        if trend_up and strong_buy and strong_body:
            return "CALL"

        if trend_down and strong_sell and strong_body:
            return "PUT"

        return None

    except:
        return None

# ================= AUTO LOOP =================
async def auto_trade():
    global last_signal_time

    while True:
        try:
            if not is_trading_session():
                await asyncio.sleep(SCAN_INTERVAL)
                continue

            signal = generate_signal()
            now = datetime.utcnow().timestamp()

            if signal and (now - last_signal_time > COOLDOWN):
                timing = get_entry_timing()

                message = f"""
🔥 PRO SNIPER SIGNAL 🔥

PAIR: {PAIR}
TF: 5M

SIGNAL: {signal}
{timing}

⚡ Trade at correct timing only
⚡ Avoid late entry
"""

                await bot.send_message(chat_id=CHAT_ID, text=message)
                last_signal_time = now

        except Exception as e:
            print("Error:", e)

        await asyncio.sleep(SCAN_INTERVAL)

# ================= START COMMAND =================
async def start_bot():
    await bot.send_message(chat_id=CHAT_ID, text="✅ Bot is running (AUTO MODE ACTIVE)")

# ================= MAIN =================
async def main():
    await start_bot()
    await auto_trade()

if __name__ == "__main__":
    asyncio.run(main())
