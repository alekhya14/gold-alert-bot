import json
from config import validate_config
from skills.news_fetcher import fetch_all_headlines
from skills.price_fetcher import (
    fetch_mcx_gold_price,
    fetch_technical_indicators,
    fetch_positional_indicators,
)
from skills.classifier import (
    run_news_classifier,
    run_technical_analyst,
    run_positional_analyst,
    run_signal_composer,
)
from skills.notifier import handle_alert
from skills.logger import log_run



def build_price_data(gold_price: str, levels: dict | None, indicators: dict | None) -> str:
    """Assemble the price context string passed into Skill 2."""
    parts = [f"Current MCX Gold price: {gold_price}"]

    if levels:
        parts.append(f"""
Pivot levels (previous session OHLC):
- Pivot : ₹{levels['pivot']:,.0f}
- R1    : ₹{levels['r1']:,.0f}
- R2    : ₹{levels['r2']:,.0f}
- R3    : ₹{levels['r3']:,.0f}
- S1    : ₹{levels['s1']:,.0f}
- S2    : ₹{levels['s2']:,.0f}
- S3    : ₹{levels['s3']:,.0f}
Previous session: High ₹{levels['prev_high']:,.0f} | Low ₹{levels['prev_low']:,.0f} | Close ₹{levels['prev_close']:,.0f}
        """.strip())

    if indicators:
        rsi_label = (
            "— overbought, avoid longs" if indicators['rsi'] > 70
            else "— oversold, avoid shorts" if indicators['rsi'] < 30
            else "— bullish momentum" if indicators['rsi'] > 55
            else "— bearish momentum" if indicators['rsi'] < 45
            else "— neutral"
        )

        vwap_bias = (
            "price above VWAP — bullish intraday bias"
            if indicators['price_vs_vwap'] > 0
            else "price below VWAP — bearish intraday bias"
        )

        parts.append(f"""
    Intraday momentum indicators (GC=F 15min — momentum signals valid,
    price levels approximate until Angel One MCX data connected):
    - RSI(14)        : {indicators['rsi']} {rsi_label}
    - EMA9           : ₹{indicators['ema9']:,.0f} (approximate)
    - EMA21          : ₹{indicators['ema21']:,.0f} (approximate)
    - EMA cross      : {indicators['ema_cross']}
    - MACD           : {indicators['macd_signal']} ({indicators['macd_cross']})
    - VWAP direction : {vwap_bias}
    - VWAP cross     : {indicators['vwap_cross']}

    NOTE: Use RSI/EMA/MACD direction for signal, ignore absolute price levels
    until MCX-specific data source connected.
            """.strip())

    return "\n\n".join(parts)

def build_positional_data(
    gold_price  : str,
    positional  : dict | None
) -> str:
    """Assemble price context for positional Skill 2b."""
    parts = [f"Current MCX Gold price: {gold_price}"]

    if positional:
        trend = "UPTREND" if positional.get("uptrend") else "DOWNTREND"
        adx_label = "trending" if positional.get("adx", 0) > 25 else "ranging"

        parts.append(f"""
Daily indicators (positional):
- RSI(14)    : {positional['rsi']}
- EMA20      : ₹{positional['ema20']:,.0f}
- EMA50      : ₹{positional['ema50']:,.0f}
- EMA200     : ₹{positional['ema200']:,.0f} — {trend}
- EMA cross  : {positional['ema_cross']}
- MACD       : {positional['macd_signal']} ({positional['macd_cross']})
- ADX        : {positional['adx']} ({adx_label})

Daily pivot levels:
- Pivot      : ₹{positional['pivot']:,.0f}
- R1 / R2    : ₹{positional['r1']:,.0f} / ₹{positional['r2']:,.0f}
- R3         : ₹{positional['r3']:,.0f}
- S1 / S2    : ₹{positional['s1']:,.0f} / ₹{positional['s2']:,.0f}
- S3         : ₹{positional['s3']:,.0f}

Previous session:
- High       : ₹{positional['prev_high']:,.0f}
- Low        : ₹{positional['prev_low']:,.0f}
- Close      : ₹{positional['prev_close']:,.0f}
        """.strip())

    return "\n\n".join(parts)

def extract_signal_tier(alert: str) -> str:
    """Derive signal tier from what the composer actually wrote."""
    text = alert.strip()
    if text == "NO_ALERT":                          return "NO_ALERT"
    if "STRONG BUY"  in text:                      return "STRONG_BUY"
    if "STRONG SELL" in text:                       return "STRONG_SELL"
    if "[Can Buy]"   in text:                       return "WEAK_BUY"
    if "[Can Sell]"  in text:                       return "WEAK_SELL"
    if "News Alert"  in text.lower():               return "NEWS_ALERT"
    if "watch only"  in text.lower():               return "WATCH_ONLY"
    return "HOLD"

def run():
    print("\n════════════════════════════════════")
    print("  MCX Gold Alert")
    print("════════════════════════════════════\n")

    validate_config()

    # ── Fetch data ────────────────────────────────────────────────
    print("[ Fetching news... ]")
    headlines = fetch_all_headlines()
    if not headlines:
        print("  No headlines — exiting")
        return

    print("\n[ Fetching price + indicators... ]")
    gold_price = fetch_mcx_gold_price()

    # Intraday data (15min candles + VWAP)
    intraday   = fetch_technical_indicators()

    # Positional data (daily candles + pivot levels)
    positional = fetch_positional_indicators()

    # ── Skill 1: News classifier (shared by both) ─────────────────
    print("\n[ Skill 1 — News Classifier ]")
    news = run_news_classifier(headlines)

    # ── Skill 2a: Intraday analyst ────────────────────────────────
    print("\n[ Skill 2a — Intraday Analyst (15min + VWAP) ]")
    intraday_data = build_price_data(gold_price, None, intraday)
    intraday_tech = run_technical_analyst(intraday_data)

    # ── Skill 2b: Positional analyst ──────────────────────────────
    print("\n[ Skill 2b — Positional Analyst (daily) ]")
    positional_data = build_positional_data(gold_price, positional)
    positional_tech = run_positional_analyst(positional_data)

    # ── Skill 3a: Compose intraday alert ──────────────────────────
    print("\n[ Skill 3a — Intraday Signal Composer ]")
    intraday_alert = run_signal_composer(intraday_tech, news)

    # ── Skill 3b: Compose positional alert ────────────────────────
    print("\n[ Skill 3b — Positional Signal Composer ]")
    positional_alert = run_signal_composer(positional_tech, news)

    # ── Send alerts independently ─────────────────────────────────
    print("\n════════════════════════════════════")
    print("  INTRADAY ALERT")
    print("════════════════════════════════════")

    intraday_signal = extract_signal_tier(intraday_alert)
    print(intraday_alert if intraday_alert.strip() != "NO_ALERT"
          else "  No intraday signal")

    print("\n════════════════════════════════════")
    print("  POSITIONAL ALERT")
    print("════════════════════════════════════")

    positional_signal = extract_signal_tier(positional_alert)
    print(positional_alert if positional_alert.strip() != "NO_ALERT"
          else "  No positional signal")


    print()

    # Send alerts
    intraday_sent = handle_alert(
        alert=intraday_alert, gold_price=gold_price,
        signal=intraday_signal, prefix="Intraday"
    )
    positional_sent = handle_alert(
        alert=positional_alert, gold_price=gold_price,
        signal=positional_signal, prefix="Positional"
    )

    # Send intraday email
    # handle_alert(
    #     alert      = intraday_alert,
    #     gold_price = gold_price,
    #     signal     = intraday_signal,
    #     prefix     = "Intraday"
    # )
    #
    # # Send positional email independently
    # handle_alert(
    #     alert      = positional_alert,
    #     gold_price = gold_price,
    #     signal     = positional_signal,
    #     prefix     = "Positional"
    # )

    log_run(
        signal=intraday_signal,signal_type="Intraday", news=news, tech=intraday_tech,
        gold_price=gold_price, alert_sent=intraday_sent,
        full_alert=intraday_alert
    )
    log_run(
        signal=positional_signal,signal_type="Positional", news=news, tech=positional_tech,
        gold_price=gold_price, alert_sent=positional_sent,
        full_alert=positional_alert
    )

if __name__ == "__main__":
    run()
