import os
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "prices.db"
FEATURES_PATH = DATA_DIR / "features.pkl"
UNIVERSE_CSV = DATA_DIR / "universe.csv"
YEARS = int(os.getenv("YEARS", "5"))
MIN_PRICE = float(os.getenv("MIN_PRICE", "50"))
MIN_TURNOVER = float(os.getenv("MIN_TURNOVER", "50000000"))  # rupees per day
DEDUPE_ISIN = os.getenv("DEDUPE_ISIN", "true").lower() == "true"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
INDEX_TICKER = os.getenv("INDEX_TICKER", "^NSEI")
EXTRA_INDICES = ["^NSEI", "^BSESN", "^INDIAVIX"]
LIVE_TTL = 20  # seconds
