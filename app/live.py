"""Live quotes. Default provider = Yahoo Finance (about 15 min delayed for Indian exchanges).
For true real-time, replace `_one` with a broker/vendor API call (Upstox, Angel One SmartAPI, Zerodha Kite Connect, Dhan...)."""
import time, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo
from .config import LIVE_TTL
IST = ZoneInfo("Asia/Kolkata")
_cache = {}

def market_status():
    n = dt.datetime.now(IST)
    open_ = n.weekday() < 5 and dt.time(9, 15) <= n.time() <= dt.time(15, 30)
    return {"open": open_, "ist": n.strftime("%d %b %Y %H:%M:%S")}

def _g(fi, *names):
    for nm in names:
        try:
            v = fi[nm] if not hasattr(fi, nm) else getattr(fi, nm)
            if v is not None:
                return float(v)
        except Exception:
            continue
    return None

def _one(t):
    import yfinance as yf
    fi = yf.Ticker(t).fast_info
    last = _g(fi, "last_price", "lastPrice"); prev = _g(fi, "previous_close", "previousClose")
    return {"price": last, "prev": prev, "chg": ((last / prev - 1) * 100) if last and prev else None,
            "high": _g(fi, "day_high", "dayHigh"), "low": _g(fi, "day_low", "dayLow"), "volume": _g(fi, "last_volume", "lastVolume")}

def quotes(tickers):
    now, out, todo = time.time(), {}, []
    for t in tickers:
        c = _cache.get(t)
        if c and now - c[0] < LIVE_TTL:
            out[t] = c[1]
        else:
            todo.append(t)
    def safe(t):
        try: return _one(t)
        except Exception: return None
    with ThreadPoolExecutor(max_workers=8) as ex:
        for t, q in zip(todo, ex.map(safe, todo)):
            if q:
                _cache[t] = (now, q); out[t] = q
    return out
