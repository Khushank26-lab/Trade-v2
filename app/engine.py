import math, os, pickle, threading
import numpy as np
from .config import FEATURES_PATH, MIN_PRICE
from . import scoring as sc, universe

MODES = {"strict": 11, "standard": 10, "relaxed": 9}
M_SHRINK = 30
_lock = threading.Lock()

class Store:
    feats, asof, mtime, meta, version = {}, None, 0.0, {}, 0
store = Store()

def load(force=False):
    if not FEATURES_PATH.exists():
        return False
    mt = os.path.getmtime(FEATURES_PATH)
    if not force and mt == store.mtime:
        return True
    with _lock:
        with open(FEATURES_PATH, "rb") as fh:
            data = pickle.load(fh)
        store.feats, store.asof, store.mtime = data["feats"], data.get("asof"), mt
        uni = universe.read_universe()
        store.meta = {r.ticker: {"name": r.name, "exchange": r.exchange, "code": r.code} for r in uni.itertuples()}
        store.version += 1
    return True

def display(t):
    m = store.meta.get(t, {})
    return (t[:-3] if t.endswith((".NS", ".BO")) else t), m.get("name", t), m.get("exchange", "")

def screen(p):
    """p: target(%), days, stop(%), mode, min_hit(%), exchange, min_turnover(Rs), capital, risk(%)"""
    load()
    thr, days = MODES[p["mode"]], int(p["days"])
    tgt, stp = p["target"] / 100.0, p["stop"] / 100.0
    fun = {"universe": len(store.meta), "with_history": len(store.feats), "liquid": 0, "score_pass": 0, "feasible": 0}
    K = N = 0
    raw = []
    for t, f in store.feats.items():
        last, meta = f["last"], store.meta.get(t, {})
        if p["exchange"] != "both" and meta.get("exchange") != p["exchange"]:
            continue
        if last["turnover20"] < p["min_turnover"] or last["price"] < MIN_PRICE or len(f["c"]) < 300:
            continue
        fun["liquid"] += 1
        arr = f["score"]
        idx = sc.thin(np.flatnonzero(arr >= thr), days)
        hit, _ = sc.outcomes(f["o"], f["h"], f["l"], idx, days, tgt, stp)
        k, n = int(hit.sum()), len(hit)
        K += k; N += n
        if arr[-1] >= thr:
            fun["score_pass"] += 1
            if sc.feasible(last["atr_pct"], tgt, days):
                fun["feasible"] += 1
                raw.append((t, f, k, n))
    p_pool = (K / N) if N else 0.0
    cands = []
    for t, f, k, n in raw:
        last = f["last"]
        k_eff, n_eff = k + M_SHRINK * p_pool, n + M_SHRINK
        p_est = k_eff / n_eff
        sym, name, exch = display(t)
        entry = last["price"]
        risk_ps = entry * stp
        qty = max(0, min(int(p["capital"] * p["risk"] / 100.0 / risk_ps) if risk_ps > 0 else 0, int(p["capital"] * 0.25 / entry)))
        cands.append({
            "ticker": t, "symbol": sym, "name": name, "exchange": exch, "asof": last["date"], "price": round(entry, 2),
            "score": int(f["score"][-1]), "npts": sc.NPTS, "setups": last["setups"],
            "flags": [{"name": nm, "ok": ok} for nm, ok in zip(sc.POINTS, last["flags"])],
            "k": k, "n": n, "p_stock": round(k / n, 4) if n else None, "p_pool": round(p_pool, 4),
            "p_est": round(p_est, 4), "p_low": round(sc.wilson_low(k_eff, n_eff), 4),
            "atr_pct": round(last["atr_pct"] * 100, 2), "rsi": round(last["rsi"], 1), "adx": round(last["adx"], 1),
            "ret3": round(last["ret3"] * 100, 1), "rs": round(last["rs"] * 100, 1), "dist52": round(last["dist52"] * 100, 1),
            "entry": round(entry, 2), "stop": round(entry * (1 - stp), 2),
            "t1": round(entry * (1 + 0.6 * tgt), 2), "t2": round(entry * (1 + tgt), 2),
            "rr": round(tgt / stp, 2), "qty": qty, "position_value": round(qty * entry), "risk_amount": round(qty * risk_ps)})
    cands.sort(key=lambda c: (c["p_low"], c["score"]), reverse=True)
    best = cands[0]["p_est"] if cands else None
    ok = [c for c in cands if c["p_est"] * 100 >= p["min_hit"]]
    met = bool(ok) or p["min_hit"] <= 0
    ranked = ok if (ok or p["min_hit"] <= 0) else cands[:10]
    return {"asof": store.asof, "funnel": fun, "pool": {"k": K, "n": N, "p": round(p_pool, 4)},
            "ranked": ranked[:60], "met_min_hit": met, "best_p_est": best, "params": p}
