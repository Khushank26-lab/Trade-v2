"""Best-effort fundamentals + news check for the shortlisted names only (Yahoo Finance data; coverage of Indian
small/mid caps is patchy, so missing data is reported as 'unverified', never guessed)."""
import json, threading, time
from concurrent.futures import ThreadPoolExecutor
from .config import DATA_DIR

CACHE_FILE = DATA_DIR / "enrich_cache.json"
TTL = 24 * 3600
_lock = threading.Lock()
POS = {"profit", "growth", "surge", "record", "upgrade", "wins", "order", "beats", "strong", "expansion", "approval", "bags", "rises", "gains", "buy", "dividend", "bonus", "raises"}
NEG = {"loss", "fall", "falls", "plunge", "downgrade", "weak", "miss", "misses", "decline", "cuts", "slump", "warning", "layoffs", "sell", "drop", "drops"}
RED = {"fraud", "probe", "sebi", "raid", "default", "resigns", "resignation", "penalty", "lawsuit", "insolvency", "bankruptcy", "ban", "scam", "arrest", "pledge", "auditor", "qualified", "delisting", "forensic", "fir"}

def _load():
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return {}

def _save(c):
    try:
        CACHE_FILE.write_text(json.dumps(c))
    except Exception:
        pass

def _num(x):
    return x if isinstance(x, (int, float)) and x == x else None

def _fund(ticker, price):
    import yfinance as yf
    info = yf.Ticker(ticker).info or {}
    checks = []
    def add(name, val, ok, fmt):
        checks.append({"name": name, "value": None if val is None else fmt(val), "ok": ok})
    roe = _num(info.get("returnOnEquity")); add("ROE >= 15%", roe, None if roe is None else roe >= 0.15, lambda v: f"{v*100:.1f}%")
    rg = _num(info.get("revenueGrowth")); add("Revenue growth >= 10%", rg, None if rg is None else rg >= 0.10, lambda v: f"{v*100:.1f}%")
    eg = _num(info.get("earningsGrowth")); add("Earnings growth >= 10%", eg, None if eg is None else eg >= 0.10, lambda v: f"{v*100:.1f}%")
    fin = "financial" in str(info.get("sector", "")).lower()
    de = _num(info.get("debtToEquity"))
    add("Debt/Equity <= 1" + (" (exempt)" if fin else ""), de, True if fin else (None if de is None else de <= 100), lambda v: f"{v/100:.2f}")
    ocf = _num(info.get("operatingCashflow")); add("Operating cash flow positive", ocf, None if ocf is None else ocf > 0, lambda v: f"{v/1e7:,.0f} cr")
    mc = _num(info.get("marketCap")); add("Market cap >= 5,000 cr", mc, None if mc is None else mc >= 5e10, lambda v: f"{v/1e7:,.0f} cr")
    fe, te = _num(info.get("forwardEps")), _num(info.get("trailingEps"))
    fg = (fe / te - 1) if (fe and te and te > 0 and fe > 0) else None
    add("Forward EPS growth >= 15%", fg, None if fg is None else fg >= 0.15, lambda v: f"{v*100:.1f}%")
    na, rm = _num(info.get("numberOfAnalystOpinions")), _num(info.get("recommendationMean"))
    add("Analysts >= 3 and consensus Buy", rm, None if (na is None or rm is None) else (na >= 3 and rm <= 2.5), lambda v: f"{v:.1f}")
    tp = _num(info.get("targetMeanPrice"))
    up = (tp / price - 1) if (tp and price) else None
    add("Analyst target upside >= 5%", up, None if up is None else up >= 0.05, lambda v: f"{v*100:.1f}%")
    avail = [c for c in checks if c["ok"] is not None]
    passed = sum(1 for c in avail if c["ok"])
    if len(avail) < 5:
        verdict = "unverified"
    else:
        verdict = "strong" if passed >= max(5, 0.67 * len(avail)) else "weak"
    return {"checks": checks, "passed": passed, "available": len(avail), "verdict": verdict}

def _news(ticker):
    import yfinance as yf
    items = yf.Ticker(ticker).news or []
    titles = []
    for it in items[:15]:
        t = it.get("title") or (it.get("content") or {}).get("title")
        if t:
            titles.append(t)
    pos = neg = 0; red = False
    for t in titles:
        w = set(x.strip(".,:;!?'\"()").lower() for x in t.split())
        p, n = len(w & POS), len(w & NEG)
        if w & RED: red = True
        if p > n: pos += 1
        elif n > p: neg += 1
    tot = len(titles)
    return {"count": tot, "pos": pos, "neg": neg, "net": round((pos - neg) / tot, 2) if tot else None, "red_flag": red, "headlines": titles[:3]}

def get(ticker, price):
    with _lock:
        cache = _load()
    ent = cache.get(ticker)
    if ent and time.time() - ent["ts"] < TTL:
        return ent["data"]
    data = {}
    try: data["fund"] = _fund(ticker, price)
    except Exception: data["fund"] = {"checks": [], "passed": 0, "available": 0, "verdict": "unverified"}
    try: data["news"] = _news(ticker)
    except Exception: data["news"] = {"count": 0, "pos": 0, "neg": 0, "net": None, "red_flag": False, "headlines": []}
    with _lock:
        cache = _load(); cache[ticker] = {"ts": time.time(), "data": data}; _save(cache)
    return data

def many(items, workers=6):
    """items: list of (ticker, price) -> dict ticker -> data"""
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return dict(zip([t for t, _ in items], ex.map(lambda tp: get(*tp), items)))
