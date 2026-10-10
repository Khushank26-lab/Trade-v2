import pickle, time, sys
import pandas as pd
from . import db, scoring, universe
from .config import FEATURES_PATH, INDEX_TICKER, UNIVERSE_CSV

def build(limit=None):
    db.init()
    uni = universe.read_universe()
    idx_df = db.load(INDEX_TICKER)
    feats, skipped = {}, 0
    con = db.conn()
    try:
        tickers = list(uni["ticker"])[: limit or None]
        for i, t in enumerate(tickers, 1):
            df = db.load(t, con)
            if len(df) < 300:
                skipped += 1; continue
            try:
                feats[t] = scoring.compute_static(df, idx_df)
            except Exception as e:
                print("[build] skip", t, e); skipped += 1
            if i % 500 == 0:
                print(f"[build] {i}/{len(tickers)}")
    finally:
        con.close()
    asof = max((f["last"]["date"] for f in feats.values()), default=None)
    tmp = FEATURES_PATH.with_suffix(".tmp")
    with open(tmp, "wb") as fh:
        pickle.dump({"feats": feats, "asof": asof, "built": time.time()}, fh, protocol=4)
    tmp.replace(FEATURES_PATH)
    print(f"[build] {len(feats)} stocks with features, {skipped} skipped (short history). data as of {asof}")

if __name__ == "__main__":
    build(int(sys.argv[1]) if len(sys.argv) > 1 else None)
