import asyncio
import os
from datetime import datetime
from telegram import Bot
from tradingview_ta import TA_Handler, Interval

# ============ CONFIG ============
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

PAIR = "EURUSD"
TIMEFRAME = Interval.INTERVAL_5_MINUTES

SCAN_INTERVAL = 10

bot = Bot(token=TOKEN)

# ============ STATE ============
active_signal = None
signal_time = None

# ============ SESSION ============
def is_trading_session():
    hour = datetime.utcnow().hour
    return 7 <= hour <= 22

# ============ ENTRY TIMING ============
def get_entry_stage():
    sec = datetime.utcnow().second

    if sec >= 50:
        return "PREPARE"
    elif sec <= 3:
        return "ENTER"
    else:
        return "WAIT"

# ============ ANALYSIS ============
def get_analysis():
    handler = TA_Handler(
        symbol=PAIR,
        screener="forex",
        exchange="FX_IDC",
        interval=TIMEFRAME
    )
    return handler.get_analysis()

# ============ SIGNAL LOGIC ============
def check_signal():
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

        # filters
        small_candle = candle_range < (price * 0.0005)
        if small_candle:
            return None

        trend_up = price > ema50 and ema20 > ema50
        trend_down = price < ema50 and ema20 < ema50

        strong_buy = rsi > 55 and macd > macd_signal
        strong_sell = rsi < 45 and macd < macd_signal

        strong_body = body > (candle_range * 0.5)

        if trend_up and strong_buy and strong_body:
            return "CALL"

        if trend_down and strong_sell and strong_body:
            return "PUT"

        return None

    except:
        return None

# ============ TRACKING SYSTEM ============
async def track_signal(signal):
    global active_signal

    await bot.send_message(chat_id=CHAT_ID,
        text=f"🔥 SIGNAL LOCKED: {signal}\n\nTracking entry timing...")

    while active_signal:
        try:
            current_signal = check_signal()

            # cancel if invalid
            if current_signal != signal:
                await bot.send_message(chat_id=CHAT_ID,
                    text="❌ Signal cancelled (market changed)")
                active_signal = None
                return

            stage = get_entry_stage()

            if stage == "WAIT":
                msg = "⌛ WAIT"
            elif stage == "PREPARE":
                msg = "⏳ PREPARE"
            elif stage == "ENTER":
                msg = "🚀 ENTER NOW"
                await bot.send_message(chat_id=CHAT_ID,
                    text=f"🚀 ENTER NOW ({signal})")
                active_signal = None
                return

            await bot.send_message(chat_id=CHAT_ID,
                text=f"{signal} | {msg}")

        except Exception as e:
            print(e)

        await asyncio.sleep(5)

# ============ AUTO BOT ============
async def auto_bot():
    global active_signal

    while True:
        try:
            if not is_trading_session():
                await asyncio.sleep(SCAN_INTERVAL)
                continue

            if active_signal is None:
                signal = check_signal()

                if signal:
                    active_signal = signal
                    asyncio.create_task(track_signal(signal))

        except Exception as e:
            print("Error:", e)

        await asyncio.sleep(SCAN_INTERVAL)

# ============ START ============
async def main():
    await bot.send_message(chat_id=CHAT_ID,
        text="✅ Bot running (Sniper Tracking Active)")

    await auto_bot()

if __name__ == "__main__":
    asyncio.run(main())
