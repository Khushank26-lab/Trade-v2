import threading, time
from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from . import engine, enrich, live, db, config, indicators as ind

app = FastAPI(title="Weekly Bullish Scanner", docs_url=None, redoc_url=None)
STATIC = config.BASE / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")
_cache, _job = {}, {"running": False}

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")

@app.get("/api/status")
def status():
    engine.load()
    return {"asof": engine.store.asof, "universe": len(engine.store.meta), "stocks_loaded": len(engine.store.feats),
            "market": live.market_status(), "ready": bool(engine.store.feats)}

@app.get("/api/screen")
def screen(target: float = Query(4.0, ge=0.5, le=30), days: int = Query(5, ge=1, le=20), stop: float = Query(2.0, ge=0.5, le=10),
           mode: str = Query("strict", pattern="^(strict|standard|relaxed)$"), min_hit: float = Query(0, ge=0, le=100),
           limit: int = Query(15, ge=1, le=50), capital: float = Query(500000, ge=1000), risk: float = Query(1.0, ge=0.1, le=5),
           exchange: str = Query("both", pattern="^(both|NSE|BSE)$"), enrich_data: bool = Query(True, alias="enrich"),
           require_fund: bool = Query(True), min_turnover_cr: float = Query(5.0, ge=0.5, le=500)):
    if not engine.load():
        raise HTTPException(503, "Data is still loading. The first full download takes 30-60+ minutes. Check back soon.")
    p = dict(target=target, days=days, stop=stop, mode=mode, min_hit=min_hit, capital=capital, risk=risk,
             exchange=exchange, min_turnover=min_turnover_cr * 1e7)
    key = (engine.store.version, tuple(sorted(p.items())), limit, enrich_data, require_fund)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    res = engine.screen(p)
    ranked = res["ranked"]
    removed = {"red_flag_news": 0, "weak_fundamentals": 0}
    if enrich_data and ranked:
        top = ranked[:30]
        enr = enrich.many([(c["ticker"], c["price"]) for c in top])
        kept = []
        for c in top:
            e = enr.get(c["ticker"], {})
            c["fund"], c["news"] = e.get("fund"), e.get("news")
            if require_fund:
                if c["news"] and c["news"]["red_flag"]:
                    removed["red_flag_news"] += 1; continue
                if c["fund"] and c["fund"]["verdict"] == "weak":
                    removed["weak_fundamentals"] += 1; continue
            kept.append(c)
        kept.sort(key=lambda c: (0 if (c.get("fund") or {}).get("verdict") == "strong" else 1))  # stable: verified first
        ranked = kept
    res["ranked"] = ranked[:limit]
    res["removed"] = removed
    res["market"] = live.market_status()
    _cache[key] = (time.time(), res)
    return res

@app.get("/api/live")
def live_quotes(tickers: str = Query(..., max_length=2000)):
    ts = [t for t in tickers.split(",") if t][:40]
    return {"market": live.market_status(), "quotes": live.quotes(ts)}

@app.get("/api/stock/{ticker}")
def stock(ticker: str):
    df = db.load(ticker)
    if df.empty:
        raise HTTPException(404, "unknown ticker")
    df = df.tail(160)
    c = db.load(ticker)["close"]
    return {"dates": [d.strftime("%Y-%m-%d") for d in df.index], "close": [round(x, 2) for x in df["close"]],
            "ema20": [round(x, 2) for x in ind.ema(c, 20).tail(160)], "ema50": [round(x, 2) for x in ind.ema(c, 50).tail(160)]}

@app.post("/api/admin/refresh")
def refresh(x_admin_token: str = Header(default="")):
    if not config.ADMIN_TOKEN or x_admin_token != config.ADMIN_TOKEN:
        raise HTTPException(403, "forbidden")
    if _job["running"]:
        return {"status": "already running"}
    def run():
        _job["running"] = True
        try:
            from . import ingest, build
            ingest.run(); build.build()
        finally:
            _job["running"] = False
    threading.Thread(target=run, daemon=True).start()
    return {"status": "started"}
