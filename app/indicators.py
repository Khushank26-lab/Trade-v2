import numpy as np, pandas as pd

def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()

def rsi(c, n=14):
    d = c.diff()
    up, dn = d.clip(lower=0), -d.clip(upper=0)
    ru = up.ewm(alpha=1 / n, adjust=False).mean()
    rd = dn.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + ru / rd.replace(0, np.nan))

def atr(h, l, c, n=14):
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()

def adx(h, l, c, n=14):
    up, dn = h.diff(), -l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=c.index)
    ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=c.index)
    a = atr(h, l, c, n)
    pdi = 100 * pdm.ewm(alpha=1 / n, adjust=False).mean() / a
    ndi = 100 * ndm.ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()

def stoch(h, l, c, n=14):
    ll, hh = l.rolling(n).min(), h.rolling(n).max()
    return 100 * (c - ll) / (hh - ll).replace(0, np.nan)

def macd(c):
    m = ema(c, 12) - ema(c, 26)
    return m, ema(m, 9)
