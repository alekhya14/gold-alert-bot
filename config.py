import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY")
FINNHUB_KEY     = os.getenv("FINNHUB_API_KEY")
METALS_DEV_KEY  = os.getenv("METALS_DEV_API_KEY")
GMAIL_USER      = os.getenv("GMAIL_USER")
GMAIL_APP_PASS  = os.getenv("GMAIL_APP_PASS")
ALERT_EMAIL     = os.getenv("ALERT_EMAIL")
MCX_CORRECTION = 1.0522
KITE_INSTRUMENT_TOKEN='125882119'
KITE_TRADING_SYMBOL='MCX:GOLDM26JUNFUT'

# Validate all keys are present on startup
def validate_config():
    missing = [
        name for name, val in {
            "ANTHROPIC_API_KEY" : ANTHROPIC_KEY,
            "FINNHUB_API_KEY"   : FINNHUB_KEY,
            "METALS_DEV_API_KEY": METALS_DEV_KEY,
            "GMAIL_USER"        : GMAIL_USER,
            "GMAIL_APP_PASS"    : GMAIL_APP_PASS,
            "ALERT_EMAIL"       : ALERT_EMAIL,
        }.items()
        if not val
    ]
    if missing:
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")