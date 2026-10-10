"""Offline smoke test with SYNTHETIC random-walk data. Results are meaningless financially; it only proves the pipeline runs."""
import os, tempfile, sys
tmp = tempfile.mkdtemp(); os.environ["DATA_DIR"] = tmp
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np, pandas as pd
from app import db, build, engine, scoring as sc, config

def test_outcomes():
    o = np.array([100.0] * 12, dtype="float32"); h = o.copy(); l = o.copy()
    h[3] = 105; l[3] = 100            # target day 3 after signal at t=1 (window = bars 2..)
    idx = np.array([1])
    hit, tf = sc.outcomes(o, h, l, idx, 5, 0.04, 0.02)
    assert hit[0] and tf[0] == 1
    l2 = l.copy(); l2[2] = 97         # stop touched first
    hit, _ = sc.outcomes(o, h, l2, idx, 5, 0.04, 0.02)
    assert not hit[0]
    print("outcomes ok")

def synth(n=1400, seed=0, drift=0.0006, vol=0.016, base=300):
    rng = np.random.default_rng(seed)
    r = rng.normal(drift, vol, n)
    c = base * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.003, n))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.006, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.006, n)))
    v = rng.lognormal(13.5, 0.4, n)
    d = pd.bdate_range(end="2026-10-09", periods=n)
    return d, o, h, l, c, v

def main():
    test_outcomes()
    db.init()
    uni = []
    for i in range(60):
        d, o, h, l, c, v = synth(seed=i, drift=0.0004 + 0.0004 * (i % 3), base=200 + 7 * i)
        t = f"SYN{i}.NS"
        db.upsert([(t, x.strftime("%Y-%m-%d"), float(a), float(b), float(cc), float(e), float(f)) for x, a, b, cc, e, f in zip(d, o, h, l, c, v)])
        uni.append((t, f"Synthetic {i}", "NSE", f"SYN{i}", f"INE{i:04d}"))
    d, o, h, l, c, v = synth(seed=999, drift=0.0004, vol=0.01, base=18000)
    db.upsert([("^NSEI", x.strftime("%Y-%m-%d"), float(a), float(b), float(cc), float(e), float(f)) for x, a, b, cc, e, f in zip(d, o, h, l, c, v)])
    pd.DataFrame(uni, columns=["ticker", "name", "exchange", "code", "isin"]).to_csv(config.UNIVERSE_CSV, index=False)
    build.build()
    for mode in ("strict", "standard", "relaxed"):
        p = dict(target=4, days=5, stop=2, mode=mode, min_hit=0, capital=500000, risk=1, exchange="both", min_turnover=1e6)
        r = engine.screen(p)
        print(mode, r["funnel"], "pool", r["pool"], "ranked", len(r["ranked"]))
        for c in r["ranked"][:2]:
            print("  ", c["symbol"], c["score"], c["k"], c["n"], c["p_est"], c["p_low"], c["qty"])
    p["min_hit"] = 99; p["mode"] = "relaxed"
    r = engine.screen(p)
    assert r["met_min_hit"] is False or len(r["ranked"]) == 0 or all(c["p_est"] >= 0.99 for c in r["ranked"])
    print("99% filter behaves:", r["met_min_hit"], len(r["ranked"]))
    print("ALL OK")

if __name__ == "__main__":
    main()
