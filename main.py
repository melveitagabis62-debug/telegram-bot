from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.ext import MessageHandler, filters

from tradingview_ta import TA_Handler, Interval
import logging
import os

TOKEN = os.getenv("TOKEN")
ALLOWED_USERS = [6351041498]

# ================= PAIRS =================

PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
    "USDCAD", "USDCHF", "NZDUSD",
    "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY",
    "EURGBP", "EURCHF", "EURAUD", "EURCAD",
    "GBPAUD", "GBPCAD", "GBPCHF",
    "AUDCAD", "AUDCHF", "CADCHF"
]

CRYPTO_PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]

OTC_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
    "EURJPY", "GBPJPY", "AUDJPY", "EURGBP"
]

# ================= MENU =================

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Forex", callback_data="forex")],
        [InlineKeyboardButton("💰 Crypto", callback_data="crypto")],
        [InlineKeyboardButton("🔥 OTC", callback_data="otc")]
    ]
    return InlineKeyboardMarkup(keyboard)


def forex_menu():
    keyboard = []
    row = []
    for i, pair in enumerate(PAIRS, 1):
        display = pair[:3] + "/" + pair[3:]
        row.append(InlineKeyboardButton(display, callback_data=pair))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def crypto_menu():
    keyboard = []
    row = []
    for i, pair in enumerate(CRYPTO_PAIRS, 1):
        display = pair.replace("USDT", "/USDT")
        row.append(InlineKeyboardButton(display, callback_data=f"crypto_{pair}"))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def otc_menu():
    keyboard = []
    row = []
    for i, pair in enumerate(OTC_PAIRS, 1):
        display = pair[:3] + "/" + pair[3:] + " OTC"
        row.append(InlineKeyboardButton(display, callback_data=f"otc_{pair}"))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def timeframe_menu(pair, is_otc=False):
    if is_otc:
        keyboard = [
            [InlineKeyboardButton("5s", callback_data=f"{pair}_5s"),
             InlineKeyboardButton("10s", callback_data=f"{pair}_10s")],
            [InlineKeyboardButton("1m", callback_data=f"{pair}_1m"),
             InlineKeyboardButton("5m", callback_data=f"{pair}_5m")],
            [InlineKeyboardButton("15m", callback_data=f"{pair}_15m")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("1m", callback_data=f"{pair}_1m"),
             InlineKeyboardButton("5m", callback_data=f"{pair}_5m")],
            [InlineKeyboardButton("15m", callback_data=f"{pair}_15m")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
        ]
    return InlineKeyboardMarkup(keyboard)

# ================= SIGNAL =================

def get_analysis(symbol, interval, market_type="forex"):
    try:
        if market_type == "crypto":
            handler = TA_Handler(symbol=symbol, screener="crypto", exchange="BINANCE", interval=interval)
        else:
            handler = TA_Handler(symbol=symbol, screener="forex", exchange="FX_IDC", interval=interval)
        return handler.get_analysis()
    except:
        return None

        
def generate_signal(pair, timeframe, market_type="forex"):
    try:
        interval_map = {
            "5s": Interval.INTERVAL_5_SECONDS,
            "10s": Interval.INTERVAL_10_SECONDS,
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES
        }

        selected_interval = interval_map.get(timeframe)
        
        analysis = get_analysis(pair, selected_interval, market_type)
        
        if not analysis:
            return f"❌ No data available for {pair} on {timeframe}.\nTry another pair or wait a few seconds."

        # Safe indicator extraction
        rsi = analysis.indicators.get("RSI", 50)
        ema50 = analysis.indicators.get("EMA50", 0)
        price = analysis.indicators.get("close", 0)
        high = analysis.indicators.get("high", 0)
        low = analysis.indicators.get("low", 0)

        macd = analysis.indicators.get("MACD.macd", 0)
        macd_signal = analysis.indicators.get("MACD.signal", 0)
        stoch_k = analysis.indicators.get("Stoch.K", 50)
        adx = analysis.indicators.get("ADX", 20)

        signal = "HOLD"
        confidence = 0
        warning = ""
        entry_price = round(price, 5)

        def get_trend(tf):
            try:
                a = get_analysis(pair, interval_map.get(tf, interval_map["1m"]), market_type)
                if not a:
                    return "NEUTRAL"
                return "UP" if a.indicators.get("close", 0) > a.indicators.get("EMA50", 0) else "DOWN"
            except:
                return "NEUTRAL"

        trend_1m = get_trend("1m")
        trend_5m = get_trend("5m")
        trend_15m = get_trend("15m")

        up_count = sum(t == "UP" for t in [trend_1m, trend_5m, trend_15m])
        mtf_aligned = max(up_count, 3 - up_count) >= 2

        macd_bullish = macd > macd_signal
        macd_bearish = macd < macd_signal
        stoch_oversold = stoch_k < 35
        stoch_overbought = stoch_k > 65
        volatility = (high - low) / price if price > 0 else 0

        is_ultra_short = timeframe in ["5s", "10s"]

        if market_type == "otc":
            if is_ultra_short:
                if (rsi < 42 and stoch_oversold and macd_bullish and trend_1m == "UP" and volatility > 0.00015):
                    signal = "BUY"
                    confidence = 75
                elif (rsi > 58 and stoch_overbought and macd_bearish and trend_1m == "DOWN" and volatility > 0.00015):
                    signal = "SELL"
                    confidence = 75
            else:
                if (rsi < 40 and stoch_oversold and macd_bullish and trend_1m == "UP" and volatility > 0.0003):
                    signal = "BUY"
                    confidence = 80 if adx > 25 else 68
                elif (rsi > 60 and stoch_overbought and macd_bearish and trend_1m == "DOWN" and volatility > 0.0003):
                    signal = "SELL"
                    confidence = 80 if adx > 25 else 68
        else:
            if mtf_aligned and volatility > 0.0004:
                if (rsi < 45 and stoch_oversold and macd_bullish and trend_1m == "UP"):
                    signal = "BUY"
                    confidence = 75 + (int(adx > 25) * 15)
                elif (rsi > 55 and stoch_overbought and macd_bearish and trend_1m == "DOWN"):
                    signal = "SELL"
                    confidence = 75 + (int(adx > 25) * 15)

        if signal != "HOLD" and abs(price - ema50) / price > 0.0045:
            warning = "⚠️ Fast retest recommended"

        result = f"🟢 BUY @ {entry_price}" if signal == "BUY" else \
                 f"🔴 SELL @ {entry_price}" if signal == "SELL" else "🟡 HOLD"
        conf_badge = f" | **{confidence}%**" if confidence > 0 else ""

        try:
            with open("trades.txt", "a") as f:
                f.write(f"{pair} | {timeframe} | {market_type} | {signal} | {price} | conf:{confidence}\n")
        except:
            pass

        alignment = f"{trend_1m}/{trend_5m}/{trend_15m}"
        title = f"Sigma AI Signal v2 ({'OTC' if market_type == 'otc' else market_type.title()})"

        return f"""
📊 **{title}**

💱 Pair: **{pair}{'' if market_type != 'otc' else ' OTC'}**
⏱ Timeframe: **{timeframe}**

📈 {result}{conf_badge} {warning}

📊 RSI: {round(rsi,2)} | Stoch: {round(stoch_k,1)}
📊 MACD: {"Bullish" if macd_bullish else "Bearish"}
📊 ADX: {round(adx,1)}
📊 Trend: {alignment}
"""

    except Exception as e:
        print(f"ERROR on {pair} {timeframe}: {str(e)}")
        return f"❌ Error fetching data for **{pair}** on **{timeframe}**.\n\nTry again in 10-20 seconds or use a different pair."

# Keep your get_analysis function as is (with try-except)

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Not authorized")
        return
    await update.message.reply_text("🚀 Sigma Bot Started\n\nChoose market:", reply_markup=main_menu())


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower() in ["start bot", "🚀 start bot"]:
        await start(update, context)


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "forex":
        await query.edit_message_text("📊 Choose Forex Pair:", reply_markup=forex_menu())
    elif data == "crypto":
        await query.edit_message_text("💰 Choose Crypto Pair:", reply_markup=crypto_menu())
    elif data == "otc":
        await query.edit_message_text("🔥 Pocket Option OTC Pairs:", reply_markup=otc_menu())
    elif data == "back_main":
        await query.edit_message_text("🏠 Main Menu:", reply_markup=main_menu())

    elif data in PAIRS:
        await query.edit_message_text(f"⏱ Select timeframe for {data}", reply_markup=timeframe_menu(data))
    elif data.startswith("crypto_"):
        pair = data.replace("crypto_", "")
        await query.edit_message_text(f"⏱ Select timeframe for {pair}", reply_markup=timeframe_menu(pair))
    elif data.startswith("otc_"):
        pair = data.replace("otc_", "")
        await query.edit_message_text(f"⏱ Select timeframe for {pair} OTC", reply_markup=timeframe_menu(pair, is_otc=True))

    elif "_" in data:
        parts = data.split("_", 1)
        pair = parts[0]
        timeframe = parts[1]
        if data.startswith(tuple(OTC_PAIRS)) or "otc_" in data:
            market_type = "otc"
        elif "USDT" in pair:
            market_type = "crypto"
        else:
            market_type = "forex"
        result = generate_signal(pair, timeframe, market_type)
        await query.edit_message_text(result, parse_mode="Markdown")


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
