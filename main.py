from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.ext import MessageHandler, filters

from tradingview_ta import TA_Handler, Interval
import logging
import os
import datetime

TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [6351041498]

# === TRACKING SYSTEM ===
WIN = 0
LOSS = 0
MARTINGALE_STEP = 0
MARTINGALE_ENABLED = True

def get_trade_amount(base=1):
    if not MARTINGALE_ENABLED:
        return base
    return base * (2 ** MARTINGALE_STEP)

def reset_martingale():
    global MARTINGALE_STEP
    MARTINGALE_STEP = 0

def increase_martingale():
    global MARTINGALE_STEP
    MARTINGALE_STEP += 1

def get_entry_timing(timeframe):
    now = datetime.datetime.utcnow()
    if timeframe == "1m":
        total_seconds = 60
        seconds_passed = now.second
    elif timeframe == "5m":
        total_seconds = 300
        seconds_passed = (now.minute % 5) * 60 + now.second
    else:
        total_seconds = 900
        seconds_passed = (now.minute % 15) * 60 + now.second

    remaining = total_seconds - seconds_passed
    if remaining > total_seconds * 0.55:
        return f"⏳ WAIT ({remaining}s left)"
    elif remaining > total_seconds * 0.25:
        return f"⚠️ PREPARE ({remaining}s)"
    else:
        return f"🔥 ENTER NOW ({remaining}s)"

async def session_notifier(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.utcnow()
    hour = now.hour
    if 7 <= hour < 13:
        session = "🇬🇧 London Session OPEN"
    elif 13 <= hour < 17:
        session = "🔥 London-New York OVERLAP (BEST TIME)"
    elif 17 <= hour < 22:
        session = "🇺🇸 New York Session OPEN"
    else:
        return
    for user_id in ALLOWED_USERS:
        await context.bot.send_message(chat_id=user_id, text=f"{session}\n\n💡 Multi-Candle Analysis Active!")

def result_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ WIN", callback_data="result_win"),
         InlineKeyboardButton("❌ LOSS", callback_data="result_loss")]
    ])

PAIRS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD","EURJPY","GBPJPY","AUDJPY","CADJPY","CHFJPY","EURGBP","EURCHF","EURAUD","EURCAD","GBPAUD","GBPCAD","GBPCHF","AUDCAD","AUDCHF","CADCHF"]
CRYPTO_PAIRS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]

def main_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📊 Forex", callback_data="forex")],[InlineKeyboardButton("💰 Crypto", callback_data="crypto")]])

def forex_menu():
    keyboard, row = [], []
    for i, pair in enumerate(PAIRS, 1):
        row.append(InlineKeyboardButton(pair[:3]+"/"+pair[3:], callback_data=pair))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def crypto_menu():
    keyboard, row = [], []
    for i, pair in enumerate(CRYPTO_PAIRS, 1):
        row.append(InlineKeyboardButton(pair.replace("USDT","/USDT"), callback_data=f"crypto_{pair}"))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def timeframe_menu(pair):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1m", callback_data=f"{pair}_1m"), InlineKeyboardButton("5m", callback_data=f"{pair}_5m")],
        [InlineKeyboardButton("15m", callback_data=f"{pair}_15m")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_forex")]
    ])

# === MULTI-FACTOR ANALYSIS ===
INTERVAL_MAP = {
    "1m": Interval.INTERVAL_1_MINUTE,
    "5m": Interval.INTERVAL_5_MINUTES,
    "15m": Interval.INTERVAL_15_MINUTES
}
# Higher timeframe used to confirm the trade timeframe's trend
CONFLUENCE_TF = {
    "1m": Interval.INTERVAL_5_MINUTES,
    "5m": Interval.INTERVAL_15_MINUTES,
    "15m": Interval.INTERVAL_1_HOUR,
}
# A further-out timeframe, checked in addition to CONFLUENCE_TF, so the
# setup has a second independent chance to show real trend agreement
# instead of leaning on just one higher timeframe.
CONFLUENCE_TF2 = {
    "1m": Interval.INTERVAL_15_MINUTES,
    "5m": Interval.INTERVAL_1_HOUR,
    "15m": Interval.INTERVAL_4_HOURS,
}

def get_analysis_obj(pair, interval):
    try:
        handler = TA_Handler(
            symbol=pair,
            screener="crypto" if "USDT" in pair else "forex",
            exchange="BINANCE" if "USDT" in pair else "FX_IDC",
            interval=interval
        )
        return handler.get_analysis()
    except Exception as e:
        print("TA fetch error:", e)
        return None

def get_trend_bias(pair, interval):
    analysis = get_analysis_obj(pair, interval)
    if not analysis:
        return None
    ind = analysis.indicators
    price, ema50 = ind.get("close"), ind.get("EMA50")
    if price is None or ema50 is None:
        return None
    return "UP" if price > ema50 else "DOWN"

def generate_signal(pair, timeframe):
    try:
        analysis = get_analysis_obj(pair, INTERVAL_MAP[timeframe])
        if not analysis:
            return "❌ Data fetch error"

        ind = analysis.indicators
        price, open_price, high, low = ind.get("close"), ind.get("open"), ind.get("high"), ind.get("low")
        if None in (price, open_price, high, low):
            return "❌ Incomplete data — try again"

        rsi = ind.get("RSI", 50)
        ema50 = ind.get("EMA50", price)
        macd, macd_signal = ind.get("MACD.macd", 0), ind.get("MACD.signal", 0)
        stoch_k, stoch_d = ind.get("Stoch.K", 50), ind.get("Stoch.D", 50)
        adx = ind.get("ADX", 20)
        bb_upper, bb_lower = ind.get("BB.upper"), ind.get("BB.lower")
        atr = ind.get("ATR")

        trend = "UP" if price > ema50 else "DOWN"
        strong_trend = adx and adx > 20

        # Candle structure off the current bar
        candle_range = max(high - low, 1e-9)
        body = abs(price - open_price)
        body_ratio = body / candle_range
        upper_wick = high - max(open_price, price)
        lower_wick = min(open_price, price) - low
        bullish_candle = price > open_price
        engulf = body_ratio > 0.55
        wick_reject_up = lower_wick > body * 1.8
        wick_reject_down = upper_wick > body * 1.8

        percent_b = None
        if bb_upper is not None and bb_lower is not None and bb_upper != bb_lower:
            percent_b = (price - bb_lower) / (bb_upper - bb_lower)

        # TradingView's own aggregate of ~20 oscillator/MA indicators — real confluence, not one metric
        try:
            osc, ma = analysis.oscillators, analysis.moving_averages
            buy_votes = osc["BUY"] + ma["BUY"]
            sell_votes = osc["SELL"] + ma["SELL"]
            votes_available = True
        except Exception:
            buy_votes = sell_votes = 0
            votes_available = False

        bullish_bias = trend == "UP" and 35 < rsi < 70
        bearish_bias = trend == "DOWN" and 30 < rsi < 65

        signal = None
        if bullish_bias and (not votes_available or buy_votes >= sell_votes):
            signal = "BUY"
        elif bearish_bias and (not votes_available or sell_votes >= buy_votes):
            signal = "SELL"

        if not signal:
            return "⏳ Waiting for setup"

        reasons = []
        score = 0.0

        score += min(adx, 40) / 40 * 1.5
        if strong_trend:
            reasons.append("ADX trend confirmed")

        if votes_available:
            vote_gap = abs(buy_votes - sell_votes)
            if vote_gap >= 4:
                score += 2; reasons.append("Strong indicator consensus")
            elif vote_gap >= 2:
                score += 1; reasons.append("Indicator consensus")

        macd_hist = macd - macd_signal
        macd_ok = (signal == "BUY" and macd_hist > 0) or (signal == "SELL" and macd_hist < 0)
        if macd_ok:
            score += 1; reasons.append("MACD confirms")
            if atr and abs(macd_hist) / max(atr, 1e-9) > 0.15:
                score += 0.5; reasons.append("MACD momentum strong")

        stoch_gap = abs(stoch_k - stoch_d)
        if (signal == "BUY" and stoch_k > stoch_d) or (signal == "SELL" and stoch_k < stoch_d):
            score += min(stoch_gap / 10, 1) * 0.8

        mom = ind.get("Mom")
        if mom is not None and ((signal == "BUY" and mom > 0) or (signal == "SELL" and mom < 0)):
            score += 0.5; reasons.append("Momentum aligns")

        plus_di, minus_di = ind.get("ADX+DI"), ind.get("ADX-DI")
        if plus_di is not None and minus_di is not None:
            if (signal == "BUY" and plus_di > minus_di) or (signal == "SELL" and minus_di > plus_di):
                score += 1; reasons.append("Directional index confirms")

        cci = ind.get("CCI20")
        if cci is not None and ((signal == "BUY" and cci > 0) or (signal == "SELL" and cci < 0)):
            score += 0.5; reasons.append("CCI aligns")

        if (signal == "BUY" and bullish_candle) or (signal == "SELL" and not bullish_candle):
            score += min(body_ratio, 1) * 1.2
            if engulf:
                reasons.append("Candle structure confirms")

        if (signal == "BUY" and wick_reject_up) or (signal == "SELL" and wick_reject_down):
            score += 0.8; reasons.append("Wick rejection")

        if percent_b is not None:
            extremity = max(0, 0.3 - percent_b) / 0.3 if signal == "BUY" else max(0, percent_b - 0.7) / 0.3
            if extremity > 0:
                score += min(extremity, 1) * 1.3
                reasons.append("At Bollinger extreme")

        higher_tf = CONFLUENCE_TF.get(timeframe)
        if higher_tf and get_trend_bias(pair, higher_tf) == trend:
            score += 1.5; reasons.append("Higher-TF trend agrees")

        higher_tf2 = CONFLUENCE_TF2.get(timeframe)
        if higher_tf2 and get_trend_bias(pair, higher_tf2) == trend:
            score += 1; reasons.append("Macro-TF trend agrees")

        if atr and price and atr / price < 0.0008:
            score -= 1; reasons.append("Low volatility (reduced)")

        score = round(min(max(score, 0), 10), 1)

        # Moderate bar — scores on evidence, doesn't hard-gate on any single condition
        if score < 5.5:
            return f"⏳ Setup forming, not clean yet (score {score}/10)"

        expiration = {"1m": "1-3 minutes", "5m": "4-8 minutes", "15m": "12-25 minutes"}[timeframe]
        amount = get_trade_amount()
        timing = get_entry_timing(timeframe)
        arrow = "🟢 BUY" if signal == "BUY" else "🔴 SELL"

        return f"""
📊 **Sigma AI Signal — Multi-Factor v4**

💱 Pair: {pair}
⏱ TF: {timeframe}

{arrow} @ {round(price,5)}
{timing}

🔥 Score: {score}/10
📋 Confirmations: { " | ".join(reasons) if reasons else "base setup" }

💰 Amount: {amount}
📉 Martingale step: {MARTINGALE_STEP}

⏳ Expiration: {expiration}

📊 RSI: {round(rsi,1)} | Trend: {trend} | TV votes: {buy_votes}B/{sell_votes}S

⚠️ Heuristic score — not a backtested win rate.
"""
    except Exception as e:
        print("Signal Error:", e)
        return "❌ Data error — try again"

# === Bot Setup ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Not authorized")
        return
    await update.message.reply_text("🚀 Sigma AI SNIPER (Multi-Candle v3) Started!", reply_markup=main_menu())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower() in ["start", "start bot", "🚀 start bot"]:
        await start(update, context)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global WIN, LOSS
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "result_win":
        WIN += 1
        reset_martingale()
        await query.edit_message_text(f"✅ WIN\nWins: {WIN}\nLosses: {LOSS}")
    elif data == "result_loss":
        LOSS += 1
        increase_martingale()
        await query.edit_message_text(f"❌ LOSS\nWins: {WIN}\nLosses: {LOSS}\nMartingale: {MARTINGALE_STEP}")

    elif data == "forex":
        await query.edit_message_text("Choose Forex:", reply_markup=forex_menu())
    elif data == "crypto":
        await query.edit_message_text("Choose Crypto:", reply_markup=crypto_menu())
    elif data == "back_main":
        await query.edit_message_text("Main Menu:", reply_markup=main_menu())
    elif data == "back_forex":
        await query.edit_message_text("Choose Forex:", reply_markup=forex_menu())
    elif data in PAIRS:
        await query.edit_message_text(f"Select TF {data}", reply_markup=timeframe_menu(data))
    elif data.startswith("crypto_"):
        pair = data.replace("crypto_", "")
        await query.edit_message_text(f"Select TF {pair}", reply_markup=timeframe_menu(pair))
    elif "_" in data:
        pair, tf = data.split("_", 1)
        result = generate_signal(pair, tf)
        await query.edit_message_text(result, parse_mode="Markdown", reply_markup=result_buttons())

app = ApplicationBuilder().token(TOKEN).build()
app.job_queue.run_repeating(session_notifier, interval=1200, first=10)

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
