"""Downloads daily OHLCV for every ticker via Yahoo Finance (free, ~15 min delayed). Swap this module for NSE/BSE bhavcopy
or a paid vendor feed if you need exchange-grade data."""
import argparse, datetime as dt, time
import pandas as pd
from . import db, universe
from .config import YEARS, EXTRA_INDICES
import concurrent.futures

def _extract(df, batch):
    res = {}
    if df is None or len(df) == 0:
        return res
    if isinstance(df.columns, pd.MultiIndex):
        top = set(df.columns.get_level_values(0))
        parts = {t: df[t] for t in batch if t in top}
    else:
        parts = {batch[0]: df}
    for t, sub in parts.items():
        try:
            sub = sub[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        except KeyError:
            continue
        if sub.empty:
            continue
        sub = sub.fillna({"Volume": 0})
        res[t] = [(t, pd.Timestamp(i).strftime("%Y-%m-%d"), float(r.Open), float(r.High), float(r.Low), float(r.Close), float(r.Volume))
                  for i, r in zip(sub.index, sub.itertuples())]
    return res

def _download(batch, start):
    import yfinance as yf
    for attempt in (1, 2):
        try:
            return yf.download(tickers=batch, start=str(start), group_by="ticker", auto_adjust=True, threads=True, progress=False)
        except Exception as e:
            print(f"[ingest] batch failed (attempt {attempt}): {e}"); time.sleep(5)
    return None

def run(years=1, batch_size=100, pause=1.0, limit=None):
    db.init()
    uni = universe.build_universe()
    tickers = list(dict.fromkeys(list(uni["ticker"])[: limit or None] + EXTRA_INDICES))
    last = db.last_dates()
    today = dt.date.today()
    full_start = today - dt.timedelta(days=int(years * 366))
    new = [t for t in tickers if t not in last]
    old = [t for t in tickers if t in last]
    inc_start = (dt.date.fromisoformat(max(last[t] for t in old)) - dt.timedelta(days=10)) if old else full_start
    got = failed = 0
    for group, start in ((new, full_start), (old, inc_start)):
        for i in range(0, len(group), batch_size):
            batch = group[i:i + batch_size]
            data = _extract(_download(batch, start), batch)
            for rows in data.values():
                db.upsert(rows)
            got += len(data); failed += len(batch) - len(data)
            print(f"[ingest] {min(i + batch_size, len(group))}/{len(group)} (start {start}) ok={got} no-data={failed}")
            time.sleep(pause)
    db.trim(str(full_start))
    print(f"[ingest] done. {got} tickers updated, {failed} returned no data (delisted/suspended/unsupported).")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=YEARS); ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    run(a.years, limit=a.limit)
def fetch_single_ticker(ticker, start_date="2020-10-10"):
    """Downloads one stock and catches delisted/dead tickers."""
    try:
        df = yf.download(ticker, start=start_date, progress=False, ignore_tz=True)
        if df.empty or len(df) < 50:  # Filters out empty or newly dead stocks
            return ticker, None
        return ticker, df
    except Exception:
        return ticker, None

def run_ingestion(tickers, max_workers=10):
    """Downloads historical data concurrently using multithreading."""
    successful_downloads = {}
    skipped_stocks = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_single_ticker, t): t for t in tickers}
        for future in concurrent.futures.as_completed(futures):
            ticker, df = future.result()
            if df is not None:
                successful_downloads[ticker] = df
            else:
                skipped_stocks.append(ticker)

    print(f"Downloaded: {len(successful_downloads)} | Skipped (dead/empty): {len(skipped_stocks)}")
    return successful_downloads    
    
