"""Builds the NSE + BSE stock universe (target: every listed equity, 7,500+ lines before de-duplication).

NSE : data/EQUITY_L.csv   (auto-download attempted; else download 'Securities available for trading - Equity' from nseindia.com)
BSE : data/bse_scrips.csv (download 'List of Scrips' CSV from bseindia.com -> Market Data -> Equity -> List of Scrips)
"""
import pandas as pd, requests
from .config import DATA_DIR, UNIVERSE_CSV, DEDUPE_ISIN

NSE_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_FILE = DATA_DIR / "EQUITY_L.csv"
BSE_FILE = DATA_DIR / "bse_scrips.csv"
COLS = ["ticker", "name", "exchange", "code", "isin"]
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept": "text/csv,*/*"}

def try_download_nse():
    try:
        r = requests.get(NSE_URL, headers=HEADERS, timeout=40)
        r.raise_for_status()
        NSE_FILE.write_bytes(r.content)
        return True
    except Exception as e:
        print(f"[universe] NSE auto-download failed ({e}). Download the equity list manually into {NSE_FILE}")
        return False

def _find(cols, *keys):
    for c in cols:
        lc = c.strip().lower()
        if all(k in lc for k in keys):
            return c
    return None

def load_nse(path=NSE_FILE):
    if not path.exists():
        return pd.DataFrame(columns=COLS)
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip().upper() for c in df.columns]
    if "SERIES" in df.columns:
        df = df[df["SERIES"].str.strip().isin(["EQ", "BE", "BZ"])]
    sym = df["SYMBOL"].str.strip()
    name = df["NAME OF COMPANY"].str.strip() if "NAME OF COMPANY" in df.columns else sym
    isin = df["ISIN NUMBER"].str.strip() if "ISIN NUMBER" in df.columns else ""
    return pd.DataFrame({"ticker": sym + ".NS", "name": name, "exchange": "NSE", "code": sym, "isin": isin})

def load_bse(path=BSE_FILE):
    if not path.exists():
        return pd.DataFrame(columns=COLS)
    df = pd.read_csv(path, dtype=str)
    code = _find(df.columns, "security", "code")
    name = _find(df.columns, "issuer") or _find(df.columns, "security", "name")
    isin = _find(df.columns, "isin")
    status = _find(df.columns, "status")
    instr = _find(df.columns, "instrument")
    if code is None:
        raise ValueError("BSE file needs a 'Security Code' column")
    if status:
        df = df[df[status].str.strip().str.lower() == "active"]
    if instr:
        df = df[df[instr].str.strip().str.lower().str.contains("equity")]
    df = df[df[code].str.strip().str.fullmatch(r"\d{6}")]
    c = df[code].str.strip()
    return pd.DataFrame({"ticker": c + ".BO", "name": df[name].str.strip() if name else c,
                         "exchange": "BSE", "code": c, "isin": df[isin].str.strip() if isin else ""})

def build_universe(download=True):
    if download and not NSE_FILE.exists():
        try_download_nse()
    n, b = load_nse(), load_bse()
    if n.empty and b.empty:
        raise RuntimeError(f"No universe files found. Put NSE list at {NSE_FILE} and/or BSE list at {BSE_FILE}.")
    raw = len(n) + len(b)
    if DEDUPE_ISIN and not n.empty and not b.empty:
        keep = ~(b["isin"].isin(set(n["isin"])) & b["isin"].astype(bool))
        b = b[keep]
    uni = pd.concat([n, b], ignore_index=True).drop_duplicates("ticker")
    uni.to_csv(UNIVERSE_CSV, index=False)
    print(f"[universe] NSE {len(n)} + BSE {len(b)} (raw listings {raw}) -> {len(uni)} tickers (dedupe_isin={DEDUPE_ISIN})")
    return uni

def read_universe():
    return pd.read_csv(UNIVERSE_CSV, dtype=str) if UNIVERSE_CSV.exists() else pd.DataFrame(columns=COLS)
# app/universe.py

def get_clean_tickers(ticker_list):
    """Filters out known invalid formats like Rights Entitlements."""
    return [t for t in ticker_list if not t.endswith("-RE.NS")    
