import math
import os
import pickle
import threading
import numpy as np
from .config import FEATURES_PATH, MIN_PRICE
from . import scoring as sc, universe

MODES = {"strict": 11, "standard": 10, "relaxed": 9}
M_SHRINK = 30
_lock = threading.Lock()

class Store:
    def __init__(self):
        self.feats = {}
        self.asof = None
        self.mtime = 0.0
        self.meta = {}
        self.version = 0

store = Store()

def load(force=False):
    if not FEATURES_PATH or not FEATURES_PATH.exists():
        return False
    try:
        mt = os.path.getmtime(FEATURES_PATH)
        if not force and mt == store.mtime and store.feats:
            return True
        with _lock:
            with open(FEATURES_PATH, "rb") as fh:
                data = pickle.load(fh)
            store.feats = data.get("feats", {})
            store.asof = data.get("asof")
            store.mtime = mt
            uni = universe.read_universe()
            if uni is not None and not uni.empty:
                store.meta = {r.ticker: {"name": r.name, "exchange": r.exchange, "code": r.code} for r in uni.itertuples()}
            store.version += 1
        return True
    except Exception as e:
        print(f"Error loading features: {e}")
        return False

def display(t):
    m = store.meta.get(t, {})
    clean_t = (t[:-3] if t.endswith((".NS", ".BO")) else t)
    return clean_t, m.get("name", t), m.get("exchange", "")

def screen(p):
    """
    p: target(%), days, stop(%), mode, min_hit(%), exchange, min_turnover(Rs), capital, risk(%)
    """
    # Fallback defaults to prevent KeyErrors if called without complete parameters
    params = {
        "mode": "standard",
        "days": 20,
        "target": 5.0,
        "stop": 3.0,
        "exchange": "both",
        "min_turnover": 1000000,
        "capital": 100000,
        "risk": 1.0,
        "min_hit": 50.0,
    }
    if p:
        params.update(p)
    p = params

    loaded = load()
    if not loaded or not store.feats:
        return {
            "asof": None,
            "funnel": {"universe": 0, "with_history": 0, "liquid": 0, "score_pass": 0, "feasible": 0},
            "pool": {"k": 0, "n": 0, "p": 0.0},
            "ranked": [],
            "met_min_hit": False,
            "best_p_est": None,
            "params": p
        }

    mode_key = p.get("mode", "standard")
    thr = MODES.get(mode_key, 10)
    days = int(p.get("days", 20))
    tgt = float(p.get("target", 5.0)) / 100.0
    stp = float(p.get("stop", 3.0)) / 100.0
    min_turnover = float(p.get("min_turnover", 0))
    exch_filter = p.get("exchange", "both")
    min_hit = float(p.get("min_hit", 0.0))
    capital = float(p.get("capital", 100000))
    risk_pct = float(p.get("risk", 1.0))

    fun = {"universe": len(store.meta), "with_history": len(store.feats), "liquid": 0, "score_pass": 0, "feasible": 0}
    K = N = 0
    raw = []

    for t, f in store.feats.items():
        last = f.get("last", {})
        meta = store.meta.get(t, {})
        if exch_filter != "both" and meta.get("exchange") != exch_filter:
            continue
        if last.get("turnover20", 0) < min_turnover or last.get("price", 0) < MIN_PRICE or len(f.get("c", [])) < 300:
            continue
        fun["liquid"] += 1
        arr = f.get("score")
        if arr is None:
            continue
        idx = sc.thin(np.flatnonzero(arr >= thr), days)
        hit, _ = sc.outcomes(f["o"], f["h"], f["l"], idx, days, tgt, stp)
        k, n = int(hit.sum()), len(hit)
        K += k
        N += n
        if arr[-1] >= thr:
            fun["score_pass"] += 1
            if sc.feasible(last.get("atr_pct", 0), tgt, days):
                fun["feasible"] += 1
                raw.append((t, f, k, n))

    p_pool = (K / N) if N else 0.0
    cands = []
    for t, f, k, n in raw:
        last = f["last"]
        k_eff, n_eff = k + M_SHRINK * p_pool, n + M_SHRINK
        p_est = k_eff / n_eff
        sym, name, exch = display(t)
        entry = last.get("price", 0)
        risk_ps = entry * stp
        qty = max(0, min(int(capital * risk_pct / 100.0 / risk_ps) if risk_ps > 0 else 0, int(capital * 0.25 / entry) if entry > 0 else 0))
        
        cands.append({
            "ticker": t, "symbol": sym, "name": name, "exchange": exch, "asof": last.get("date"), "price": round(entry, 2),
            "score": int(f["score"][-1]), "npts": getattr(sc, "NPTS", 0), "setups": last.get("setups", []),
            "flags": [{"name": nm, "ok": ok} for nm, ok in zip(getattr(sc, "POINTS", []), last.get("flags", []))],
            "k": k, "n": n, "p_stock": round(k / n, 4) if n else None, "p_pool": round(p_pool, 4),
            "p_est": round(p_est, 4), "p_low": round(sc.wilson_low(k_eff, n_eff), 4),
            "atr_pct": round(last.get("atr_pct", 0) * 100, 2), "rsi": round(last.get("rsi", 0), 1), "adx": round(last.get("adx", 0), 1),
            "ret3": round(last.get("ret3", 0) * 100, 1), "rs": round(last.get("rs", 0) * 100, 1), "dist52": round(last.get("dist52", 0) * 100, 1),
            "entry": round(entry, 2), "stop": round(entry * (1 - stp), 2),
            "t1": round(entry * (1 + 0.6 * tgt), 2), "t2": round(entry * (1 + tgt), 2),
            "rr": round(tgt / stp, 2) if stp > 0 else 0.0, "qty": qty, "position_value": round(qty * entry), "risk_amount": round(qty * risk_ps)
        })

    cands.sort(key=lambda c: (c["p_low"], c["score"]), reverse=True)
    best = cands[0]["p_est"] if cands else None
    ok = [c for c in cands if c["p_est"] * 100 >= min_hit]
    met = bool(ok) or min_hit <= 0
    ranked = ok if (ok or min_hit <= 0) else cands[:10]
    return {
        "asof": store.asof, "funnel": fun, "pool": {"k": K, "n": N, "p": round(p_pool, 4)},
        "ranked": ranked[:60], "met_min_hit": met, "best_p_est": best, "params": p
    }
