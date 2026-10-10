"""Technical part of Scorecard v6 that can be computed from price data alone (12 points).
Fundamentals, growth, news are added later (enrich.py) for the shortlisted names only."""
import math
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv
from . import indicators as ind

POINTS = ["Market bullish (Nifty > 20 & 50 EMA)", "EMA stack 20 > 50 > 200", "RSI between 55 and 70", "MACD above signal",
          "Volume surge (1.5x avg, last 3 days)", "Within 10% of 52-week high", "ADX trend strength >= 20",
          "Stochastic not overbought (<= 85)", "Beats index over 3 months (+2%)", "Higher highs & higher lows",
          "ATR 1.5-5% of price", "Entry trigger present"]
NPTS = len(POINTS)
SETUPS = ["20-Day Breakout", "EMA20 Pullback Bounce", "Bullish Engulfing", "Hammer", "Inside-Bar Breakout", "NR7 Breakout", "52-Week High Breakout"]

def _f(x, default=0.0):
    try:
        x = float(x)
        return x if math.isfinite(x) else default
    except Exception:
        return default

def compute_static(df, idx_df=None):
    o, h, l, c, v = (df[k].astype(float) for k in ["open", "high", "low", "close", "volume"])
    e20, e50, e200 = ind.ema(c, 20), ind.ema(c, 50), ind.ema(c, 200)
    r = ind.rsi(c); m, sg = ind.macd(c); a = ind.atr(h, l, c); atrp = a / c
    adxv = ind.adx(h, l, c); st = ind.stoch(h, l, c)
    volx = v / v.rolling(20).mean(); vol3 = volx.rolling(3).max()
    hi52 = h.rolling(252, min_periods=120).max()
    ret3 = c / c.shift(63) - 1
    if idx_df is not None and len(idx_df) > 60:
        ic = idx_df["close"].astype(float)
        mk = ((ic > ind.ema(ic, 20)) & (ic > ind.ema(ic, 50))).astype(float).reindex(df.index, method="ffill").fillna(0) > 0
        ir3 = (ic / ic.shift(63) - 1).reindex(df.index, method="ffill").fillna(0)
    else:
        mk = pd.Series(True, index=df.index); ir3 = pd.Series(0.0, index=df.index)
    hh10 = l.rolling(10).min()
    # setups
    s_break = (c > c.shift(1).rolling(20).max()) & (volx >= 1.2)
    s_pull = (l <= e20 * 1.01) & (c > e20) & (c > o) & (e20 > e50)
    s_eng = (c > o) & (c.shift() < o.shift()) & (o <= c.shift()) & (c >= o.shift())
    body = (c - o).abs(); lower = np.minimum(o, c) - l; upper = h - np.maximum(o, c)
    s_ham = (body > 0) & (lower >= 2 * body) & (upper <= body) & (c > e50) & (c < c.shift(5))
    inside = (h < h.shift()) & (l > l.shift())
    s_inside = inside.shift(fill_value=False) & (c > h.shift())
    rng = h - l
    s_nr7 = (rng == rng.rolling(7).min()).shift(fill_value=False) & (c > h.shift())
    s_52 = c >= h.shift(1).rolling(252, min_periods=120).max()
    setup_df = pd.concat([s_break, s_pull, s_eng, s_ham, s_inside, s_nr7, s_52], axis=1).fillna(False).astype(bool)
    setup_df.columns = SETUPS
    trig = setup_df.any(axis=1)
    flags = pd.DataFrame({
        "mkt": mk, "stack": (c > e20) & (e20 > e50) & (e50 > e200), "rsi": (r >= 55) & (r <= 70), "macd": m > sg,
        "vol": vol3 >= 1.5, "near": ((hi52 - c) / hi52) <= 0.10, "adx": adxv >= 20, "stoch": st <= 85,
        "rs": (ret3 - ir3) >= 0.02, "struct": (c > c.shift(20)) & (hh10 > hh10.shift(10)),
        "atr": (atrp >= 0.015) & (atrp <= 0.05), "trig": trig}).fillna(False).astype(bool)
    score = flags.sum(axis=1).astype("int8").values
    li = -1
    last = {"date": str(df.index[li].date()), "price": _f(c.iloc[li]), "rsi": _f(r.iloc[li]), "adx": _f(adxv.iloc[li]),
            "atr_pct": _f(atrp.iloc[li]), "dist52": _f((hi52.iloc[li] - c.iloc[li]) / hi52.iloc[li]),
            "ret3": _f(ret3.iloc[li]), "rs": _f(ret3.iloc[li] - ir3.iloc[li]),
            "turnover20": _f((c * v).rolling(20).mean().iloc[li]),
            "flags": [bool(x) for x in flags.iloc[li].values],
            "setups": [n for n in SETUPS if bool(setup_df[n].iloc[li])]}
    return {"o": o.values.astype("float32"), "h": h.values.astype("float32"), "l": l.values.astype("float32"),
            "c": c.values.astype("float32"), "score": score, "last": last}

def wilson_low(k, n, z=1.2816):
    if n <= 0:
        return 0.0
    ph = k / n
    d = 1 + z * z / n
    cen = ph + z * z / (2 * n)
    adj = z * math.sqrt(max(ph * (1 - ph) / n + z * z / (4 * n * n), 0))
    return max(0.0, (cen - adj) / d)

def thin(idx, gap):
    """Keep signals at least `gap` bars apart so overlapping windows are not double counted."""
    out, lastk = [], -10**9
    for i in idx:
        if i - lastk >= gap:
            out.append(i); lastk = i
    return np.array(out, dtype=int)

def outcomes(o, h, l, idx, days, tgt, stp):
    """For signals at close of bar t: buy at open of t+1, hold <= `days` sessions.
    Hit = target touched before stop (same-day both => stop wins, the conservative call)."""
    T = len(o)
    idx = idx[(idx + days) <= (T - 1)]
    if len(idx) == 0:
        return np.zeros(0, dtype=bool), np.zeros(0)
    H = swv(h[1:], days)[idx]; L = swv(l[1:], days)[idx]
    ent = o[idx + 1][:, None]
    th = H >= ent * (1 + tgt); sh = L <= ent * (1 - stp)
    tf = np.where(th.any(1), th.argmax(1), days + 1)
    sf = np.where(sh.any(1), sh.argmax(1), days + 1)
    return tf < sf, tf

def feasible(atr_pct, target, days, k=1.5):
    return target <= k * atr_pct * math.sqrt(days)
