import os
import time

from config import METALS_DEV_KEY
import pandas as pd

from kiteconnect import KiteConnect
from kiteconnect.exceptions import KiteException
import requests
from config import MCX_CORRECTION, KITE_TRADING_SYMBOL, KITE_INSTRUMENT_TOKEN

KITE_GOLD_SYMBOL = KITE_TRADING_SYMBOL

KITE_QUOTE_RETRIES   = 2
KITE_QUOTE_RETRY_WAIT = 2  # seconds


def _fetch_kite_ltp() -> float:
    kite = KiteConnect(api_key=os.getenv("KITE_API_KEY"))
    kite.set_access_token(os.getenv("KITE_ACCESS_TOKEN"))

    last_error = None
    for attempt in range(1, KITE_QUOTE_RETRIES + 1):
        try:
            quote = kite.quote([KITE_TRADING_SYMBOL])
            ltp = float(quote[KITE_TRADING_SYMBOL]["last_price"])

            if ltp == 0:
                raise ValueError("LTP is 0 — market closed")

            return ltp
        except (KiteException, ValueError, KeyError, requests.RequestException) as e:
            last_error = e
            if attempt < KITE_QUOTE_RETRIES:
                print(f"  Kite quote attempt {attempt} failed ({e}) — retrying")
                time.sleep(KITE_QUOTE_RETRY_WAIT)

    raise last_error


def fetch_mcx_gold_price() -> float:
    try:
        ltp = _fetch_kite_ltp()
        print(f"  MCX Gold   : ₹{ltp:,.0f} (Kite Connect)")
        return ltp

    except (KiteException, ValueError, KeyError, requests.RequestException) as e:
        print(f"  Kite failed ({e}) — using gold-api fallback")
        try:
            response = requests.get(
                "https://api.gold-api.com/price/XAU/INR", timeout=10
            )
            response.raise_for_status()
            data        = response.json()
            inr_per_oz  = float(data["price"])
            inr_per_10g = round((inr_per_oz / 31.1035) * 10 * MCX_CORRECTION, -1)
            print(f"  MCX Gold   : ₹{inr_per_10g:,.0f} (gold-api fallback)")
            return inr_per_10g
        except (requests.RequestException, ValueError, KeyError) as fallback_error:
            raise RuntimeError(
                f"Could not fetch MCX gold price: Kite failed ({e}), "
                f"gold-api fallback also failed ({fallback_error})"
            ) from fallback_error

def fetch_positional_indicators() -> dict | None:
    """
    Fetch daily candles from Kite Connect (MCX GOLD26JUNFUT) for positional signals.
    Returns MCX prices directly in INR — no conversion needed.
    """
    try:
        kite  = KiteConnect(api_key=os.getenv("KITE_API_KEY"))
        kite.set_access_token(os.getenv("KITE_ACCESS_TOKEN"))

        # Fetch 1 year of daily candles for EMA200
        from_date = (pd.Timestamp.now() - pd.Timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")
        to_date   = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        records = kite.historical_data(
            instrument_token = KITE_INSTRUMENT_TOKEN,   # GOLD26JUNFUT token
            from_date        = from_date,
            to_date          = to_date,
            interval         = "day"
        )

        if not records:
            print("  Kite positional: no data returned")
            return None

        hist = pd.DataFrame(records)
        hist.columns = [c.lower() for c in hist.columns]

        if len(hist) < 50:
            print("  Kite positional: insufficient data")
            return None

        print(f"  Kite positional: {len(hist)} daily candles fetched")

    except (KiteException, requests.RequestException, KeyError, ValueError) as e:
        print(f"  Kite positional failed ({e})")
        return None

    close = hist["close"]
    high  = hist["high"]
    low   = hist["low"]

    # ── RSI(14) ──────────────────────────────────────────────────
    delta    = close.diff()
    avg_gain = delta.clip(lower=0).rolling(14).mean()
    avg_loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi      = (100 - (100 / (1 + avg_gain / avg_loss))).fillna(50)

    # ── EMA 20 / 50 / 200 ────────────────────────────────────────
    ema20  = close.ewm(span=20,  adjust=False).mean()
    ema50  = close.ewm(span=50,  adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    ema_cross = "none"
    for i in range(-3, 0):
        if ema20.iloc[i-1] < ema50.iloc[i-1] and \
           ema20.iloc[i] > ema50.iloc[i]:
            ema_cross = "bullish_crossover"
            break
        elif ema20.iloc[i-1] > ema50.iloc[i-1] and \
             ema20.iloc[i] < ema50.iloc[i]:
            ema_cross = "bearish_crossover"
            break

    # ── MACD (12, 26, 9) ─────────────────────────────────────────
    macd_line   = close.ewm(span=12, adjust=False).mean() - \
                  close.ewm(span=26, adjust=False).mean()
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_signal = "bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] \
                  else "bearish"

    macd_cross = "none"
    if macd_line.iloc[-2] < signal_line.iloc[-2] and \
       macd_line.iloc[-1] > signal_line.iloc[-1]:
        macd_cross = "bullish_crossover"
    elif macd_line.iloc[-2] > signal_line.iloc[-2] and \
         macd_line.iloc[-1] < signal_line.iloc[-1]:
        macd_cross = "bearish_crossover"

    # ── ADX ──────────────────────────────────────────────────────
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
    dx       = (((di_plus - di_minus).abs() /
                (di_plus + di_minus)) * 100).fillna(0)
    adx      = dx.rolling(14).mean()

    # ── Uptrend filter ───────────────────────────────────────────
    uptrend = close.iloc[-1] > ema200.iloc[-1] * 1.01

    # ── Daily pivot levels (previous session) ────────────────────
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

def fetch_technical_indicators() -> dict | None:
    """
    Fetch 15min intraday candles from Kite Connect for intraday signals.
    """
    try:
        kite      = KiteConnect(api_key=os.getenv("KITE_API_KEY"))
        kite.set_access_token(os.getenv("KITE_ACCESS_TOKEN"))

        from_date = (pd.Timestamp.now() - pd.Timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        to_date   = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        records = kite.historical_data(
            instrument_token = KITE_INSTRUMENT_TOKEN,
            from_date        = from_date,
            to_date          = to_date,
            interval         = "15minute"
        )

        if not records:
            print("  Kite intraday: no data returned")
            return None

        hist = pd.DataFrame(records)
        hist.columns = [c.lower() for c in hist.columns]

        if len(hist) < 26:
            return None

        print(f"  Kite intraday: {len(hist)} 15min candles fetched")

    except (KiteException, requests.RequestException, KeyError, ValueError) as e:
        print(f"  Kite intraday failed ({e})")
        return None

    close  = hist["close"]
    high   = hist["high"]
    low    = hist["low"]
    volume = hist["volume"]

    # ── RSI(14) ──────────────────────────────────────────────────
    delta    = close.diff()
    avg_gain = delta.clip(lower=0).rolling(14).mean()
    avg_loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi      = (100 - (100 / (1 + avg_gain / avg_loss))).fillna(50)

    # ── EMA 9 / 21 ───────────────────────────────────────────────
    ema9  = close.ewm(span=9,  adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()

    ema_cross = "none"
    for i in range(-3, 0):
        if ema9.iloc[i-1] < ema21.iloc[i-1] and \
           ema9.iloc[i] > ema21.iloc[i]:
            ema_cross = "bullish_crossover"
            break
        elif ema9.iloc[i-1] > ema21.iloc[i-1] and \
             ema9.iloc[i] < ema21.iloc[i]:
            ema_cross = "bearish_crossover"
            break

    # ── MACD ─────────────────────────────────────────────────────
    macd_line   = close.ewm(span=12, adjust=False).mean() - \
                  close.ewm(span=26, adjust=False).mean()
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_signal = "bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] \
                  else "bearish"

    macd_cross = "none"
    if macd_line.iloc[-2] < signal_line.iloc[-2] and \
       macd_line.iloc[-1] > signal_line.iloc[-1]:
        macd_cross = "bullish_crossover"
    elif macd_line.iloc[-2] > signal_line.iloc[-2] and \
         macd_line.iloc[-1] < signal_line.iloc[-1]:
        macd_cross = "bearish_crossover"

    # ── VWAP (today's session only) ──────────────────────────────
    hist["date"] = pd.to_datetime(hist["date"])
    today_mask   = hist["date"].dt.date == pd.Timestamp.now().date()

    if today_mask.sum() < 3:
        today_mask = hist["date"].dt.date == hist["date"].dt.date.iloc[-1]

    today_hist    = hist[today_mask]
    typical_price = (today_hist["high"] +
                     today_hist["low"] +
                     today_hist["close"]) / 3
    vwap_series   = (typical_price * today_hist["volume"]).cumsum() / \
                     today_hist["volume"].cumsum()
    current_vwap  = vwap_series.iloc[-1]

    curr_close    = close.iloc[-1]
    price_vs_vwap = ((curr_close - current_vwap) / current_vwap) * 100

    vwap_cross = "none"
    if len(today_hist) >= 2:
        if today_hist["close"].iloc[-2] < vwap_series.iloc[-2] and \
           today_hist["close"].iloc[-1] > vwap_series.iloc[-1]:
            vwap_cross = "price_crossed_above_vwap"
        elif today_hist["close"].iloc[-2] > vwap_series.iloc[-2] and \
             today_hist["close"].iloc[-1] < vwap_series.iloc[-1]:
            vwap_cross = "price_crossed_below_vwap"

    intraday_high  = today_hist["high"].max()
    intraday_low   = today_hist["low"].min()
    intraday_pivot = (intraday_high + intraday_low + curr_close) / 3

    indicators = {
        "rsi"           : round(rsi.iloc[-1], 1),
        "ema9"          : round(ema9.iloc[-1], -1),
        "ema21"         : round(ema21.iloc[-1], -1),
        "ema_cross"     : ema_cross,
        "macd_signal"   : macd_signal,
        "macd_cross"    : macd_cross,
        "vwap"          : round(current_vwap, -1),
        "vwap_cross"    : vwap_cross,
        "price_vs_vwap" : round(price_vs_vwap, 2),
        "intraday_high" : round(intraday_high, -1),
        "intraday_low"  : round(intraday_low, -1),
        "intraday_pivot": round(intraday_pivot, -1),
    }

    print(f"  RSI(14)    : {indicators['rsi']}")
    print(f"  EMA9/21    : ₹{indicators['ema9']:,.0f} / ₹{indicators['ema21']:,.0f}")
    print(f"  EMA cross  : {indicators['ema_cross']}")
    print(f"  MACD       : {indicators['macd_signal']} ({indicators['macd_cross']})")
    print(f"  VWAP       : ₹{indicators['vwap']:,.0f} "
          f"({'bullish' if price_vs_vwap > 0 else 'bearish'} "
          f"{price_vs_vwap:+.2f}%)")
    print(f"  VWAP cross : {indicators['vwap_cross']}")
    print(f"  ID High/Low: ₹{indicators['intraday_high']:,.0f} / "
          f"₹{indicators['intraday_low']:,.0f}")

    return indicators