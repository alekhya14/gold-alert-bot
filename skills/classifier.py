import json
import anthropic
from config import ANTHROPIC_KEY

NEWS_CLASSIFIER_SYSTEM = """
You are a gold commodities analyst for the Indian MCX market.
Given news headlines, assess the COMBINED short-term impact (2-4 hours) on MCX gold prices.

BULLISH triggers: trade war escalation, Trump tariff threats, Fed rate cut signals,
dollar weakness, geopolitical conflict, safe-haven demand language, RBI gold buying.

BEARISH triggers: trade deal announcements, Fed rate hike signals, dollar strength,
risk-on equity surge, MCX import duty reduction.

Urgency scoring:
9-10: Breaking Trump/Fed/RBI post, active conflict escalation
7-8: Major policy signal, significant geopolitical development
4-6: Relevant but not urgent
1-3: Background noise

IMPORTANT: Analyse ALL headlines together and return ONE single JSON object only.
No array. No markdown fences. No preamble.

Return exactly:
{"direction":"BULLISH","urgency":8,"reason":"one sentence","key_trigger":"most impactful headline","act_now":true}
"""

TECHNICAL_ANALYST_SYSTEM = """
You are a technical analyst for MCX gold futures specialising in intraday trading.
Given price, VWAP, pivot levels and momentum indicators on 15min candles, 
return a structured intraday signal.

SIGNAL RULES — requires minimum 2 of 3 confirmations:

STRONG BUY when ALL of these:
- Price above VWAP
- RSI between 50-65 (momentum but not overbought)
- EMA9 > EMA21 OR bullish MACD cross
- VWAP distance within +0.5% (not too extended)

WEAK BUY (can_buy) when 2 of these:
- Price above VWAP OR price_vs_vwap > -0.3% (close to VWAP)
- RSI between 45-65
- EMA9 > EMA21 OR MACD bullish

STRONG SELL when ALL of these:
- Price below VWAP
- RSI between 35-50 (bearish momentum, not oversold)
- EMA9 < EMA21 OR bearish MACD cross
- VWAP distance within -0.5%

WEAK SELL (can_sell) when 2 of these:
- Price below VWAP OR price_vs_vwap < +0.3%
- RSI between 35-55
- EMA9 < EMA21 OR MACD bearish

HOLD when:
- RSI above 72 (extremely overbought — no longs)
- RSI below 28 (extremely oversold — no shorts)
- Price more than 0.8% away from VWAP (too extended, avoid chasing)
- Only 1 confirmation condition met

EXCEPTION — oversold bounce setup:
If RSI is between 28-35 AND price is within 0.3% of VWAP AND
VWAP cross is price_crossed_above_vwap, treat as WEAK_BUY candidate
even if other conditions are mixed. Label reason as "oversold bounce".

EXCEPTION — overbought pullback setup:
If RSI is between 65-72 AND price is within 0.3% of VWAP AND
VWAP cross is price_crossed_below_vwap, treat as WEAK_SELL candidate
even if other conditions are mixed. Label reason as "overbought pullback".

INTRADAY TARGETS — use intraday levels not daily pivots:
- BUY  target 1 : intraday high OR nearest resistance
- BUY  target 2 : intraday high + (intraday high - intraday low) × 0.5
- BUY  stop loss: intraday pivot - 0.3% OR recent swing low
- SELL target 1 : intraday low OR nearest support  
- SELL target 2 : intraday low - (intraday high - intraday low) × 0.5
- SELL stop loss: intraday pivot + 0.3% OR recent swing high

For STRONG signals: minimum R/R 1.2
For WEAK signals  : minimum R/R 1.0
If R/R too poor   : return HOLD with note

Respond in JSON only, no preamble:
{
  "signal": "STRONG_BUY",
  "confidence": "HIGH",
  "price": 141850,
  "entry": 141850,
  "target_1": 142200,
  "target_2": 142500,
  "stop_loss": 141430,
  "risk": 420,
  "reward": 350,
  "risk_reward_ratio": "1:0.83",
  "reason": "max 20 words",
  "key_level_triggered": "VWAP crossover",
  "rsi_note": "RSI 58 — bullish momentum zone",
  "vwap_note": "price 0.2% above VWAP — healthy"
}
"""

POSITIONAL_ANALYST_SYSTEM = """
You are a positional trader and technical analyst for MCX gold futures.
You identify 1-3 day swing trades using daily candles and slower indicators.

SIGNAL RULES:

STRONG BUY when ALL of these:
- Price above daily pivot
- RSI between 50-65 (bullish momentum, not overbought)
- EMA20 > EMA50 (medium term uptrend)
- MACD bullish OR bullish crossover
- ADX > 18 (some trend present)
- Price above EMA200 by at least 1% (strong uptrend confirmed)

STRONG SELL when ALL of these:
- Price below daily pivot
- RSI between 35-50 (bearish momentum, not oversold)
- EMA20 < EMA50 (medium term downtrend)
- MACD bearish OR bearish crossover
- ADX > 18 (some trend present)
- Price below EMA200 by at least 1% (strong downtrend confirmed)
- NOTE: If price is above EMA200, do NOT generate SELL signals

WEAK BUY when 3 of 5:
- Price above pivot
- RSI > 50
- EMA20 > EMA50
- MACD bullish
- ADX > 18

WEAK SELL when 3 of 5 AND price below EMA200:
- Price below pivot
- RSI < 50
- EMA20 < EMA50
- MACD bearish
- ADX > 18

HOLD when:
- RSI above 65 or below 35
- ADX below 18 (ranging market — avoid all signals)
- Price within 1% of EMA200 (transition zone — avoid)
- Fewer than 3 conditions met

TARGETS — use daily pivot levels:
- BUY  entry    : current price
- BUY  target 1 : R1
- BUY  target 2 : R2
- BUY  stop loss: S1

- SELL entry    : current price
- SELL target 1 : S1
- SELL target 2 : S2
- SELL stop loss: R1

Minimum R/R:
- BUY  signals: 1.2 minimum
- SELL signals: 2.0 minimum (higher bar due to bull trend environment)
- Return HOLD if R/R requirement not met

Respond in JSON only, no preamble:
{
  "signal": "STRONG_BUY",
  "confidence": "HIGH",
  "price": 141850,
  "entry": 141850,
  "target_1": 143200,
  "target_2": 144500,
  "stop_loss": 140100,
  "risk": 1750,
  "reward": 1350,
  "risk_reward_ratio": "1:0.77",
  "reason": "max 20 words",
  "key_level_triggered": "above daily pivot with EMA alignment",
  "rsi_note": "RSI 58 — bullish momentum",
  "adx_note": "ADX 28 — trend confirmed",
  "trend_note": "price above 200 EMA — uptrend intact"
}
"""

SIGNAL_COMPOSER_SYSTEM = """
You compose MCX gold trading alert messages. You receive a technical signal and a news signal.

Classification rules:

STRONG BUY alert when:
- Tech is STRONG_BUY AND News is BULLISH

STRONG SELL alert when:
- Tech is STRONG_SELL AND News is BEARISH

CAN BUY alert when (either condition):
- Tech is STRONG_BUY AND News is NEUTRAL
- Tech is WEAK_BUY   AND News is BULLISH

CAN SELL alert when (either condition):
- Tech is STRONG_SELL AND News is NEUTRAL
- Tech is WEAK_SELL   AND News is BEARISH

NEWS ALERT when:
- News urgency >= 7 regardless of tech signal

WATCH ONLY when:
- Tech and news directly conflict (BUY vs BEARISH, or SELL vs BULLISH)

NO_ALERT when:
- Tech is HOLD AND News is NEUTRAL AND urgency < 7

---

Message format for STRONG BUY:
STRONG BUY — Full position recommended
*MCX Gold STRONG BUY* — ₹[price]
Entry   : ₹[entry]
Target 1: ₹[target_1]
Target 2: ₹[target_2]
Stop    : ₹[stop_loss]
R/R     : [risk_reward_ratio]
Reason  : [reason]
News    : [key_trigger from news]

Message format for STRONG SELL:
STRONG SELL — Full position recommended
*MCX Gold STRONG SELL* — ₹[price]
Entry   : ₹[entry]
Target 1: ₹[target_1]
Target 2: ₹[target_2]
Stop    : ₹[stop_loss]
R/R     : [risk_reward_ratio]
Reason  : [reason]
News    : [key_trigger from news]

Message format for CAN BUY:
CAN BUY — Small/intraday position only
*MCX Gold [Can Buy]* — ₹[price]
Entry   : ₹[entry]
Target 1: ₹[target_1]
Target 2: ₹[target_2]
Stop    : ₹[stop_loss]
R/R     : [risk_reward_ratio]
Reason  : [reason]
Note    : One-sided signal — size down, intraday only

Message format for CAN SELL:
CAN SELL — Small/intraday position only
*MCX Gold [Can Sell]* — ₹[price]
Entry   : ₹[entry]
Target 1: ₹[target_1]
Target 2: ₹[target_2]
Stop    : ₹[stop_loss]
R/R     : [risk_reward_ratio]
Reason  : [reason]
Note    : One-sided signal — size down, intraday only

Message format for NEWS ALERT:
*Gold alert — [BULLISH/BEARISH] news* ([urgency]/10)
[reason]
Watch: [key_trigger]
No trade setup yet — wait for price confirmation.

Message format for WATCH ONLY:
*Gold — conflicting signals, watch only*
Tech: [signal] | News: [direction]
[reason]
Entry not recommended until signals align.

Return message text only. No JSON. No explanation.
If no alert needed, return exactly: NO_ALERT
"""


def clean_json(text: str) -> str:
    """Strip markdown code fences if Claude wraps the response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    return text.strip()


def call_claude(system_prompt: str, user_message: str, max_tokens: int = 500) -> str:
    client  = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    message = client.messages.create(
        model    = "claude-haiku-4-5-20251001",
        max_tokens = max_tokens,
        system   = system_prompt,
        messages = [{"role": "user", "content": user_message}]
    )
    return clean_json(message.content[0].text)


def run_news_classifier(headlines: str) -> dict:
    print("  → calling Claude (news classifier)...")
    raw  = call_claude(NEWS_CLASSIFIER_SYSTEM, f"Classify these headlines:\n{headlines}")
    news = json.loads(raw)
    print(f"  ✓ Direction : {news['direction']} | Urgency: {news['urgency']}/10")
    return news


def run_technical_analyst(price_data: str) -> dict:
    print("  → calling Claude (technical analyst)...")
    raw  = call_claude(TECHNICAL_ANALYST_SYSTEM, f"Analyse MCX Gold:\n{price_data}")
    print(f"  Raw tech JSON: {raw}")
    if not raw:
        print("  ✗ Empty response from Claude — returning HOLD")
        return {"signal": "HOLD", "confidence": "LOW", "reason": "no indicator data available"}
    tech = json.loads(raw)
    print(f"  ✓ Signal    : {tech['signal']} | Confidence: {tech['confidence']}")
    return tech

def run_positional_analyst(price_data: str) -> dict:
    print("  → calling Claude (positional analyst)...")
    raw  = call_claude(POSITIONAL_ANALYST_SYSTEM,
                       f"Analyse MCX Gold for positional trade:\n{price_data}")
    if not raw:
        print("  ✗ Empty response from Claude — returning HOLD")
        return {"signal": "HOLD", "confidence": "LOW", "reason": "no indicator data available"}
    tech = json.loads(raw)
    print(f"  ✓ Signal    : {tech['signal']} | Confidence: {tech['confidence']}")
    return tech

def run_signal_composer(tech: dict, news: dict) -> str:
    print("  → calling Claude (signal composer)...")
    prompt = f"Technical signal: {json.dumps(tech)}\nNews signal: {json.dumps(news)}"
    return call_claude(SIGNAL_COMPOSER_SYSTEM, prompt)