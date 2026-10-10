import sqlite3
import pandas as pd
from .config import DB_PATH

def conn():
    c = sqlite3.connect(DB_PATH, timeout=120)
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init():
    with conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS prices (ticker TEXT, d TEXT, o REAL, h REAL, l REAL, c REAL, v REAL, PRIMARY KEY (ticker, d)) WITHOUT ROWID")

def upsert(rows):
    if not rows:
        return
    with conn() as c:
        c.executemany("INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?)", rows)

def last_dates():
    with conn() as c:
        return dict(c.execute("SELECT ticker, MAX(d) FROM prices GROUP BY ticker").fetchall())

def trim(cutoff_iso):
    with conn() as c:
        c.execute("DELETE FROM prices WHERE d < ?", (cutoff_iso,))

def load(ticker, c=None):
    own = c is None
    c = c or conn()
    try:
        df = pd.read_sql_query("SELECT d,o,h,l,c,v FROM prices WHERE ticker=? ORDER BY d", c, params=(ticker,))
    finally:
        if own:
            c.close()
    if df.empty:
        return df
    df.index = pd.to_datetime(df.pop("d"))
    df.columns = ["open", "high", "low", "close", "volume"]
    return df
