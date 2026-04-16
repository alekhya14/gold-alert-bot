import os

import requests
import yfinance as yf
from config import METALS_DEV_KEY
import pandas as pd
from config import MCX_CORRECTION
from truedata import TD_live, TD_hist
import time

truedata_log = os.getenv("TRUEDATA_LOGIN")
truedata_pass = os.getenv("TRUEDATA_PASSWORD")

td = TD_live(truedata_log, truedata_pass,live_port=8086)
td_hist = TD_hist(truedata_log, truedata_pass)



def fetch_mcx_gold_price() -> str:
    try:
        req_ids = td.start_live_data(["GOLD-I"])

        time.sleep(2)

        # Tick comes in via td.live_data dict
        # Poll it or attach a callback depending on your TD version
        inr_per_10g = td.live_data["GOLD-I"].ltp
        return inr_per_10g
    except:
        return "₹134,000 (fallback)"


# def fetch_mcx_gold_price() -> tuple[str, float]:
#     """
#     Fetch live gold spot price from Metals.Dev.
#     Returns (formatted INR string, raw INR per troy oz).
#     """
#     response = requests.get(
#         "https://api.metals.dev/v1/latest",
#         params={
#             "api_key" : METALS_DEV_KEY,
#             "currency": "INR",
#             "unit"    : "toz"
#         }
#     )
#     data = response.json()
#
#     try:
#         inr_per_oz  = data["metals"]["gold"]
#
#         # MCX correction factor — accounts for import duty,
#         # futures premium and USD/INR differential
#         # Calibrated on 27 Mar 2026 against actual MCX price
#         # TODO: Recalibrate monthly or when Angel One API is connected
#         # MCX_CORRECTION = 1.0522
#
#         inr_per_10g = round((inr_per_oz / 31.1035) * 10 * MCX_CORRECTION, -1)
#         # inr_per_10g = round((inr_per_oz / 31.1035) * 10, -1)
#         price_str   = f"₹{inr_per_10g:,.0f}"
#         print(f"  MCX Gold   : {price_str}")
#         return price_str, inr_per_oz
#     except (KeyError, TypeError):
#         print("  MCX Gold   : fallback price used")
#         return "₹134,000 (fallback)", 417000.0
#


# def fetch_positional_indicators(inr_per_oz: float) -> dict | None:
#     """
#     Fetch daily candles for positional trading signals.
#     Uses slower indicators suited for 1-3 day holds.
#     """
#     ticker = yf.Ticker("GC=F")
#     hist   = ticker.history(period="6mo", interval="1d")
#
#     if hist.empty or len(hist) < 50:
#         return None
#
#     close  = hist["Close"]
#     high   = hist["High"]
#     low    = hist["Low"]
#
#     # ── RSI(14) on daily ─────────────────────────────────────────
#     delta    = close.diff()
#     avg_gain = delta.clip(lower=0).rolling(14).mean()
#     avg_loss = (-delta.clip(upper=0)).rolling(14).mean()
#     rsi      = 100 - (100 / (1 + avg_gain / avg_loss))
#
#     # ── EMA 20 / 50 (positional uses slower EMAs) ────────────────
#     ema20 = close.ewm(span=20, adjust=False).mean()
#     ema50 = close.ewm(span=50, adjust=False).mean()
#
#     ema_cross = "none"
#     for i in range(-3, 0):
#         if ema20.iloc[i-1] < ema50.iloc[i-1] and ema20.iloc[i] > ema50.iloc[i]:
#             ema_cross = "bullish_crossover"
#             break
#         elif ema20.iloc[i-1] > ema50.iloc[i-1] and ema20.iloc[i] < ema50.iloc[i]:
#             ema_cross = "bearish_crossover"
#             break
#
#     # ── MACD (12, 26, 9) on daily ────────────────────────────────
#     macd_line   = close.ewm(span=12, adjust=False).mean() - \
#                   close.ewm(span=26, adjust=False).mean()
#     signal_line = macd_line.ewm(span=9, adjust=False).mean()
#     macd_signal = "bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] else "bearish"
#
#     macd_cross = "none"
#     if macd_line.iloc[-2] < signal_line.iloc[-2] and \
#        macd_line.iloc[-1] > signal_line.iloc[-1]:
#         macd_cross = "bullish_crossover"
#     elif macd_line.iloc[-2] > signal_line.iloc[-2] and \
#          macd_line.iloc[-1] < signal_line.iloc[-1]:
#         macd_cross = "bearish_crossover"
#
#     # ── ADX — trend strength ──────────────────────────────────────
#     # ADX > 25 = trending, < 20 = ranging
#     tr    = pd.concat([
#         high - low,
#         (high - close.shift()).abs(),
#         (low  - close.shift()).abs()
#     ], axis=1).max(axis=1)
#
#     dm_plus  = high.diff().clip(lower=0)
#     dm_minus = (-low.diff()).clip(lower=0)
#
#     atr      = tr.rolling(14).mean()
#     di_plus  = (dm_plus.rolling(14).mean()  / atr) * 100
#     di_minus = (dm_minus.rolling(14).mean() / atr) * 100
#     dx       = ((di_plus - di_minus).abs() / (di_plus + di_minus)) * 100
#     adx      = dx.rolling(14).mean()
#
#     # ── Daily pivot levels ────────────────────────────────────────
#     prev      = hist.iloc[-2]
#     p_high    = prev["High"]
#     p_low     = prev["Low"]
#     p_close   = prev["Close"]
#
#     pivot = (p_high + p_low + p_close) / 3
#     r1    = (2 * pivot) - p_low
#     r2    = pivot + (p_high - p_low)
#     r3    = p_high + 2 * (pivot - p_low)
#     s1    = (2 * pivot) - p_high
#     s2    = pivot - (p_high - p_low)
#     s3    = p_low - 2 * (p_high - pivot)
#
#     # ── 200 EMA trend filter ──────────────────────────────────────
#     ema200    = close.ewm(span=200, adjust=False).mean()
#     uptrend   = close.iloc[-1] > ema200.iloc[-1]
#
#     # ── Convert to INR per 10g ────────────────────────────────────
#     latest_usd     = close.iloc[-1]
#     # usd_to_inr_10g = (inr_per_oz / latest_usd) / 31.1035 * 10
#     # MCX_CORRECTION = 1.0522
#     usd_to_inr_10g = (inr_per_oz / latest_usd) / 31.1035 * 10 * MCX_CORRECTION
#     def to_inr(usd_val):
#         return round(usd_val * usd_to_inr_10g, -1)
#
#     indicators = {
#         "rsi"         : round(rsi.iloc[-1], 1),
#         "ema20"       : to_inr(ema20.iloc[-1]),
#         "ema50"       : to_inr(ema50.iloc[-1]),
#         "ema200"      : to_inr(ema200.iloc[-1]),
#         "ema_cross"   : ema_cross,
#         "macd_signal" : macd_signal,
#         "macd_cross"  : macd_cross,
#         "adx"         : round(adx.iloc[-1], 1),
#         "uptrend"     : uptrend,
#         "pivot"       : to_inr(pivot),
#         "r1"          : to_inr(r1),
#         "r2"          : to_inr(r2),
#         "r3"          : to_inr(r3),
#         "s1"          : to_inr(s1),
#         "s2"          : to_inr(s2),
#         "s3"          : to_inr(s3),
#         "prev_high"   : to_inr(p_high),
#         "prev_low"    : to_inr(p_low),
#         "prev_close"  : to_inr(p_close),
#     }
#
#     print(f"  [Positional]")
#     print(f"  RSI(14)    : {indicators['rsi']}")
#     print(f"  EMA20/50   : ₹{indicators['ema20']:,.0f} / ₹{indicators['ema50']:,.0f}")
#     print(f"  ADX        : {indicators['adx']} "
#           f"({'trending' if indicators['adx'] > 25 else 'ranging'})")
#     print(f"  MACD       : {indicators['macd_signal']} ({indicators['macd_cross']})")
#     print(f"  200 EMA    : ₹{indicators['ema200']:,.0f} "
#           f"({'uptrend' if uptrend else 'downtrend'})")
#     print(f"  Pivot      : ₹{indicators['pivot']:,.0f}")
#     print(f"  R1/R2      : ₹{indicators['r1']:,.0f} / ₹{indicators['r2']:,.0f}")
#     print(f"  S1/S2      : ₹{indicators['s1']:,.0f} / ₹{indicators['s2']:,.0f}")
#
#     return indicators

def fetch_positional_indicators() -> dict | None:
    """
    Fetch daily candles from TrueData (MCX GOLD-I) for positional trading signals.
    Uses slower indicators suited for 1-3 day holds.
    No USD→INR conversion needed — TrueData returns MCX prices directly in INR.
    """

    try:
        hist = td_hist.get_historic_data(
            "GOLD-I",
            bar_size   = "1day",
            start_time = (pd.Timestamp.now() - pd.Timedelta(days=365))  # 1yr for EMA200
        )

        if hist is None or hist.empty or len(hist) < 50:
            return None

        hist.columns = [c.lower() for c in hist.columns]

        close = hist["close"]
        high  = hist["high"]
        low   = hist["low"]

    except Exception as e:
        print(f"  TrueData   : failed to fetch daily bars ({e})")
        return None

    # ── RSI(14) on daily ──────────────────────────────────────────────────────
    delta    = close.diff()
    avg_gain = delta.clip(lower=0).rolling(14).mean()
    avg_loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi      = 100 - (100 / (1 + avg_gain / avg_loss))

    # ── EMA 20 / 50 / 200 ────────────────────────────────────────────────────
    ema20  = close.ewm(span=20,  adjust=False).mean()
    ema50  = close.ewm(span=50,  adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    ema_cross = "none"
    for i in range(-3, 0):
        if ema20.iloc[i-1] < ema50.iloc[i-1] and ema20.iloc[i] > ema50.iloc[i]:
            ema_cross = "bullish_crossover"
            break
        elif ema20.iloc[i-1] > ema50.iloc[i-1] and ema20.iloc[i] < ema50.iloc[i]:
            ema_cross = "bearish_crossover"
            break

    # ── MACD (12, 26, 9) on daily ────────────────────────────────────────────
    macd_line   = close.ewm(span=12, adjust=False).mean() - \
                  close.ewm(span=26, adjust=False).mean()
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_signal = "bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] else "bearish"

    macd_cross = "none"
    if macd_line.iloc[-2] < signal_line.iloc[-2] and \
       macd_line.iloc[-1] > signal_line.iloc[-1]:
        macd_cross = "bullish_crossover"
    elif macd_line.iloc[-2] > signal_line.iloc[-2] and \
         macd_line.iloc[-1] < signal_line.iloc[-1]:
        macd_cross = "bearish_crossover"

    # ── ADX — trend strength ──────────────────────────────────────────────────
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)

    dm_plus  = high.diff().clip(lower=0)
    dm_minus = (-low.diff()).clip(lower=0)

    atr      = tr.rolling(14).mean()
    di_plus  = (dm_plus.rolling(14).mean()  / atr) * 100
    di_minus = (dm_minus.rolling(14).mean() / atr) * 100
    dx       = ((di_plus - di_minus).abs() / (di_plus + di_minus)) * 100
    adx      = dx.rolling(14).mean()

    # ── 200 EMA trend filter ──────────────────────────────────────────────────
    uptrend = close.iloc[-1] > ema200.iloc[-1]

    # ── Daily pivot levels (previous session) ─────────────────────────────────
    # Use iloc[-2] — last completed MCX session
    prev    = hist.iloc[-2]
    p_high  = prev["high"]
    p_low   = prev["low"]
    p_close = prev["close"]

    pivot = (p_high + p_low + p_close) / 3
    r1    = (2 * pivot) - p_low
    r2    = pivot + (p_high - p_low)
    r3    = p_high + 2 * (pivot - p_low)
    s1    = (2 * pivot) - p_high
    s2    = pivot - (p_high - p_low)
    s3    = p_low - 2 * (p_high - pivot)

    # ── Build result — already INR per 10g, no conversion needed ─────────────
    def r(val):
        return round(val, -1)

    indicators = {
        "rsi"         : round(rsi.iloc[-1], 1),
        "ema20"       : r(ema20.iloc[-1]),
        "ema50"       : r(ema50.iloc[-1]),
        "ema200"      : r(ema200.iloc[-1]),
        "ema_cross"   : ema_cross,
        "macd_signal" : macd_signal,
        "macd_cross"  : macd_cross,
        "adx"         : round(adx.iloc[-1], 1),
        "uptrend"     : uptrend,
        "pivot"       : r(pivot),
        "r1"          : r(r1),
        "r2"          : r(r2),
        "r3"          : r(r3),
        "s1"          : r(s1),
        "s2"          : r(s2),
        "s3"          : r(s3),
        "prev_high"   : r(p_high),
        "prev_low"    : r(p_low),
        "prev_close"  : r(p_close),
    }

    print(f"  [Positional]")
    print(f"  RSI(14)    : {indicators['rsi']}")
    print(f"  EMA20/50   : ₹{indicators['ema20']:,.0f} / ₹{indicators['ema50']:,.0f}")
    print(f"  ADX        : {indicators['adx']} "
          f"({'trending' if indicators['adx'] > 25 else 'ranging'})")
    print(f"  MACD       : {indicators['macd_signal']} ({indicators['macd_cross']})")
    print(f"  200 EMA    : ₹{indicators['ema200']:,.0f} "
          f"({'uptrend' if uptrend else 'downtrend'})")
    print(f"  Pivot      : ₹{indicators['pivot']:,.0f}")
    print(f"  R1/R2      : ₹{indicators['r1']:,.0f} / ₹{indicators['r2']:,.0f}")
    print(f"  S1/S2      : ₹{indicators['s1']:,.0f} / ₹{indicators['s2']:,.0f}")

    return indicators

# def fetch_pivot_levels(inr_per_oz: float) -> dict | None:
#     """
#     Fetch previous session OHLC from Yahoo Finance (GC=F)
#     and calculate standard pivot points in MCX INR per 10g.
#     """
#     hist = yf.Ticker("GC=F").history(period="30d", interval="1d")
#
#     if hist.empty:
#         return None
#
#     prev  = hist.iloc[-2]
#     latest_usd = hist.iloc[-1]["Close"]
#
#     high, low, close = prev["High"], prev["Low"], prev["Close"]
#
#     pivot = (high + low + close) / 3
#     r1    = (2 * pivot) - low
#     r2    = pivot + (high - low)
#     r3    = high + 2 * (pivot - low)
#     s1    = (2 * pivot) - high
#     s2    = pivot - (high - low)
#     s3    = low - 2 * (high - pivot)
#
#     # MCX_CORRECTION = 1.0522
#
#     def to_mcx(usd):
#         return round((usd * (inr_per_oz / latest_usd) / 31.1035) * 10 * MCX_CORRECTION, -1)
#     # def to_mcx(usd):
#     #     return round((usd * (inr_per_oz / latest_usd) / 31.1035) * 10, -1)
#
#     levels = {
#         "pivot"     : to_mcx(pivot),
#         "r1"        : to_mcx(r1),
#         "r2"        : to_mcx(r2),
#         "r3"        : to_mcx(r3),
#         "s1"        : to_mcx(s1),
#         "s2"        : to_mcx(s2),
#         "s3"        : to_mcx(s3),
#         "prev_high" : to_mcx(high),
#         "prev_low"  : to_mcx(low),
#         "prev_close": to_mcx(close),
#     }
#
#     print(f"  Pivot      : ₹{levels['pivot']:,.0f}")
#     print(f"  R1/R2      : ₹{levels['r1']:,.0f} / ₹{levels['r2']:,.0f}")
#     print(f"  S1/S2      : ₹{levels['s1']:,.0f} / ₹{levels['s2']:,.0f}")
#     return levels


def fetch_technical_indicators() -> dict | None:
    """
    Fetch 15min intraday candles from TrueData (MCX GOLD-I) and calculate:
    RSI(14), EMA9/21, MACD, VWAP, intraday pivot levels.

    No more USD→INR conversion needed — TrueData gives MCX prices directly in INR.
    """
    import pandas as pd

    try:
        # ── Pull bar data from TrueData ───────────────────────────────────────
        hist = td_hist.get_historic_data(
            "GOLD-I",
            bar_size="15min",
            start_time=(pd.Timestamp.now() - pd.Timedelta(days=5))
        )

        if hist is None or hist.empty or len(hist) < 26:
            return None

        # TrueData column names — adjust if your version differs
        hist.columns = [c.lower() for c in hist.columns]  # normalise casing

        close = hist["close"]
        high = hist["high"]
        low = hist["low"]
        volume = hist["volume"]

    except Exception as e:
        print(f"  TrueData   : failed to fetch bars ({e})")
        return None

    # ── RSI(14) ───────────────────────────────────────────────────────────────
    delta = close.diff()
    avg_gain = delta.clip(lower=0).rolling(14).mean()
    avg_loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + avg_gain / avg_loss))

    # ── EMA 9 / 21 ────────────────────────────────────────────────────────────
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()

    ema_cross = "none"
    for i in range(-3, 0):
        if ema9.iloc[i - 1] < ema21.iloc[i - 1] and ema9.iloc[i] > ema21.iloc[i]:
            ema_cross = "bullish_crossover"
            break
        elif ema9.iloc[i - 1] > ema21.iloc[i - 1] and ema9.iloc[i] < ema21.iloc[i]:
            ema_cross = "bearish_crossover"
            break

    # ── MACD (12, 26, 9) ──────────────────────────────────────────────────────
    macd_line = close.ewm(span=12, adjust=False).mean() - \
                close.ewm(span=26, adjust=False).mean()
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_signal = "bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] else "bearish"

    macd_cross = "none"
    if macd_line.iloc[-2] < signal_line.iloc[-2] and \
            macd_line.iloc[-1] > signal_line.iloc[-1]:
        macd_cross = "bullish_crossover"
    elif macd_line.iloc[-2] > signal_line.iloc[-2] and \
            macd_line.iloc[-1] < signal_line.iloc[-1]:
        macd_cross = "bearish_crossover"

    # ── VWAP (today's MCX session only) ───────────────────────────────────────
    # MCX Gold session: 09:00 – 23:30 IST
    today = pd.Timestamp.now(tz="Asia/Kolkata").date()
    # today_mask = hist.
    today_mask = hist.timestamp.dt.date == today

    if today_mask.sum() < 3:
        today_mask = hist.index.date == sorted(set(hist.index.date))[-1]

    today_hist = hist[today_mask]
    typical_price = (today_hist["high"] + today_hist["low"] + today_hist["close"]) / 3
    cumulative_tpv = (typical_price * today_hist["volume"]).cumsum()
    cumulative_vol = today_hist["volume"].cumsum()
    vwap_series = cumulative_tpv / cumulative_vol
    current_vwap = vwap_series.iloc[-1]

    # ── VWAP cross detection ──────────────────────────────────────────────────
    vwap_cross = "none"
    if len(today_hist) >= 2:
        prev_close = today_hist["close"].iloc[-2]
        curr_close = today_hist["close"].iloc[-1]
        prev_vwap = vwap_series.iloc[-2]
        curr_vwap = vwap_series.iloc[-1]

        if prev_close < prev_vwap and curr_close > curr_vwap:
            vwap_cross = "price_crossed_above_vwap"
        elif prev_close > prev_vwap and curr_close < curr_vwap:
            vwap_cross = "price_crossed_below_vwap"

    curr_close = close.iloc[-1]
    price_vs_vwap = ((curr_close - current_vwap) / current_vwap) * 100

    # ── Intraday pivot ────────────────────────────────────────────────────────
    intraday_high = today_hist["high"].max()
    intraday_low = today_hist["low"].min()
    intraday_pivot = (intraday_high + intraday_low + curr_close) / 3

    # ── Build result — no conversion needed, already INR per 10g ─────────────
    indicators = {
        "rsi": round(rsi.iloc[-1], 1),
        "ema9": round(ema9.iloc[-1], -1),
        "ema21": round(ema21.iloc[-1], -1),
        "ema_cross": ema_cross,
        "macd_signal": macd_signal,
        "macd_cross": macd_cross,
        "vwap": round(current_vwap, -1),
        "vwap_cross": vwap_cross,
        "price_vs_vwap": round(price_vs_vwap, 2),
        "intraday_high": round(intraday_high, -1),
        "intraday_low": round(intraday_low, -1),
        "intraday_pivot": round(intraday_pivot, -1),
    }

    print(f"  RSI(14)    : {indicators['rsi']}")
    print(f"  EMA9/21    : ₹{indicators['ema9']:,.0f} / ₹{indicators['ema21']:,.0f}")
    print(f"  EMA cross  : {indicators['ema_cross']}")
    print(f"  MACD       : {indicators['macd_signal']} ({indicators['macd_cross']})")
    print(f"  VWAP       : ₹{indicators['vwap']:,.0f} "
          f"(price is {indicators['price_vs_vwap']:+.2f}% from VWAP)")
    print(f"  VWAP cross : {indicators['vwap_cross']}")
    print(f"  ID High/Low: ₹{indicators['intraday_high']:,.0f} / "
          f"₹{indicators['intraday_low']:,.0f}")

    return indicators

# def fetch_technical_indicators(inr_per_oz: float) -> dict | None:
#     """
#     Fetch 15min intraday candles and calculate:
#     RSI(14), EMA9/21, MACD, VWAP, intraday pivot levels.
#     """
#     ticker = yf.Ticker("GC=F")
#     hist   = ticker.history(period="5d", interval="15m")
#
#     if hist.empty or len(hist) < 26:
#         return None
#
#     close  = hist["Close"]
#     high   = hist["High"]
#     low    = hist["Low"]
#     volume = hist["Volume"]
#
#     # ── RSI(14) ──────────────────────────────────────────────────
#     delta    = close.diff()
#     avg_gain = delta.clip(lower=0).rolling(14).mean()
#     avg_loss = (-delta.clip(upper=0)).rolling(14).mean()
#     rsi      = 100 - (100 / (1 + avg_gain / avg_loss))
#
#     # ── EMA 9 / 21 ───────────────────────────────────────────────
#     ema9  = close.ewm(span=9,  adjust=False).mean()
#     ema21 = close.ewm(span=21, adjust=False).mean()
#
#     ema_cross = "none"
#     for i in range(-3, 0):
#         if ema9.iloc[i-1] < ema21.iloc[i-1] and ema9.iloc[i] > ema21.iloc[i]:
#             ema_cross = "bullish_crossover"
#             break
#         elif ema9.iloc[i-1] > ema21.iloc[i-1] and ema9.iloc[i] < ema21.iloc[i]:
#             ema_cross = "bearish_crossover"
#             break
#
#     # ── MACD (12, 26, 9) ─────────────────────────────────────────
#     macd_line   = close.ewm(span=12, adjust=False).mean() - \
#                   close.ewm(span=26, adjust=False).mean()
#     signal_line = macd_line.ewm(span=9, adjust=False).mean()
#     macd_signal = "bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] else "bearish"
#
#     macd_cross = "none"
#     if macd_line.iloc[-2] < signal_line.iloc[-2] and \
#        macd_line.iloc[-1] > signal_line.iloc[-1]:
#         macd_cross = "bullish_crossover"
#     elif macd_line.iloc[-2] > signal_line.iloc[-2] and \
#          macd_line.iloc[-1] < signal_line.iloc[-1]:
#         macd_cross = "bearish_crossover"
#
#     # ── VWAP (today's session only) ──────────────────────────────
#     # Filter to today's candles only for accurate intraday VWAP
#     import pandas as pd
#     today      = pd.Timestamp.now(tz=hist.index.tz).date()
#     today_mask = hist.index.date == today
#
#     if today_mask.sum() < 3:
#         # Market just opened or no today data — use last session
#         today_mask = hist.index.date == sorted(set(hist.index.date))[-1]
#
#     today_hist  = hist[today_mask]
#     typical_price = (today_hist["High"] + today_hist["Low"] + today_hist["Close"]) / 3
#     cumulative_tpv = (typical_price * today_hist["Volume"]).cumsum()
#     cumulative_vol = today_hist["Volume"].cumsum()
#     vwap_series    = cumulative_tpv / cumulative_vol
#     current_vwap   = vwap_series.iloc[-1]
#
#     # ── VWAP cross detection ─────────────────────────────────────
#     vwap_cross = "none"
#     if len(today_hist) >= 2:
#         prev_close = today_hist["Close"].iloc[-2]
#         curr_close = today_hist["Close"].iloc[-1]
#         prev_vwap  = vwap_series.iloc[-2]
#         curr_vwap  = vwap_series.iloc[-1]
#
#         if prev_close < prev_vwap and curr_close > curr_vwap:
#             vwap_cross = "price_crossed_above_vwap"
#         elif prev_close > prev_vwap and curr_close < curr_vwap:
#             vwap_cross = "price_crossed_below_vwap"
#
#     curr_close   = close.iloc[-1]
#     price_vs_vwap = ((curr_close - current_vwap) / current_vwap) * 100
#
#     # ── Intraday pivot (today's session high/low/open so far) ────
#     intraday_high  = today_hist["High"].max()
#     intraday_low   = today_hist["Low"].min()
#     intraday_open  = today_hist["Open"].iloc[0]
#     intraday_pivot = (intraday_high + intraday_low + curr_close) / 3
#
#     # ── Convert to INR per 10g ────────────────────────────────────
#     latest_usd     = curr_close
#     usd_to_inr_10g = (inr_per_oz / latest_usd) / 31.1035 * 10
#
#     indicators = {
#         "rsi"           : round(rsi.iloc[-1], 1),
#         "ema9"          : round(ema9.iloc[-1]  * usd_to_inr_10g, -1),
#         "ema21"         : round(ema21.iloc[-1] * usd_to_inr_10g, -1),
#         "ema_cross"     : ema_cross,
#         "macd_signal"   : macd_signal,
#         "macd_cross"    : macd_cross,
#         "vwap"          : round(current_vwap * usd_to_inr_10g, -1),
#         "vwap_cross"    : vwap_cross,
#         "price_vs_vwap" : round(price_vs_vwap, 2),
#         "intraday_high" : round(intraday_high * usd_to_inr_10g, -1),
#         "intraday_low"  : round(intraday_low  * usd_to_inr_10g, -1),
#         "intraday_pivot": round(intraday_pivot * usd_to_inr_10g, -1),
#     }
#
#     print(f"  RSI(14)    : {indicators['rsi']}")
#     print(f"  EMA9/21    : ₹{indicators['ema9']:,.0f} / ₹{indicators['ema21']:,.0f}")
#     print(f"  EMA cross  : {indicators['ema_cross']}")
#     print(f"  MACD       : {indicators['macd_signal']} ({indicators['macd_cross']})")
#     print(f"  VWAP       : ₹{indicators['vwap']:,.0f} "
#           f"(price is {indicators['price_vs_vwap']:+.2f}% from VWAP)")
#     print(f"  VWAP cross : {indicators['vwap_cross']}")
#     print(f"  ID High/Low: ₹{indicators['intraday_high']:,.0f} / "
#           f"₹{indicators['intraday_low']:,.0f}")
#     print(f"  NOTE: Intraday levels based on CME session — "
#           f"activate Angel One for MCX intraday data")
#
#     return indicators

# def fetch_technical_indicators(inr_per_oz: float) -> dict | None:
#     """
#     Fetch 15min intraday candles and calculate RSI(14), EMA9/21, MACD.
#     """
#     hist = yf.Ticker("GC=F").history(period="5d", interval="15m")
#
#     if hist.empty or len(hist) < 26:
#         return None
#
#     close = hist["Close"]
#
#     # RSI(14)
#     delta    = close.diff()
#     avg_gain = delta.clip(lower=0).rolling(14).mean()
#     avg_loss = (-delta.clip(upper=0)).rolling(14).mean()
#     rsi      = 100 - (100 / (1 + avg_gain / avg_loss))
#     current_rsi = round(rsi.iloc[-1], 1)
#
#     # EMA 9 / 21
#     ema9  = close.ewm(span=9,  adjust=False).mean()
#     ema21 = close.ewm(span=21, adjust=False).mean()
#
#     ema_cross = "none"
#     for i in range(-3, 0):
#         if ema9.iloc[i-1] < ema21.iloc[i-1] and ema9.iloc[i] > ema21.iloc[i]:
#             ema_cross = "bullish_crossover"
#             break
#         elif ema9.iloc[i-1] > ema21.iloc[i-1] and ema9.iloc[i] < ema21.iloc[i]:
#             ema_cross = "bearish_crossover"
#             break
#
#     # MACD (12, 26, 9)
#     macd_line   = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
#     signal_line = macd_line.ewm(span=9, adjust=False).mean()
#
#     macd_signal = "bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] else "bearish"
#     macd_cross  = "none"
#     if macd_line.iloc[-2] < signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1]:
#         macd_cross = "bullish_crossover"
#     elif macd_line.iloc[-2] > signal_line.iloc[-2] and macd_line.iloc[-1] < signal_line.iloc[-1]:
#         macd_cross = "bearish_crossover"
#
#     # Convert EMA to INR per 10g
#     latest_usd     = close.iloc[-1]
#     usd_to_inr_10g = (inr_per_oz / latest_usd) / 31.1035 * 10
#
#     indicators = {
#         "rsi"         : current_rsi,
#         "ema9"        : round(ema9.iloc[-1]  * usd_to_inr_10g, -1),
#         "ema21"       : round(ema21.iloc[-1] * usd_to_inr_10g, -1),
#         "ema_cross"   : ema_cross,
#         "macd_signal" : macd_signal,
#         "macd_cross"  : macd_cross,
#     }
#
#     print(f"  RSI(14)    : {indicators['rsi']}")
#     print(f"  EMA9/21    : ₹{indicators['ema9']:,.0f} / ₹{indicators['ema21']:,.0f}")
#     print(f"  EMA cross  : {indicators['ema_cross']}")
#     print(f"  MACD       : {indicators['macd_signal']} ({indicators['macd_cross']})")
#     return indicators