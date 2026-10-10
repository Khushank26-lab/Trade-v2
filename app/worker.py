"""Runs the nightly refresh: ingest prices -> rebuild features. First run happens immediately if the database is empty."""
import datetime as dt, time, traceback
from zoneinfo import ZoneInfo
from . import db, ingest, build
from .config import FEATURES_PATH
IST = ZoneInfo("Asia/Kolkata")
RUN_AT = dt.time(17, 30)  # after market close + data lag

def job():
    try:
        ingest.run(); build.build()
    except Exception:
        traceback.print_exc()

def seconds_until(now):
    t = now.replace(hour=RUN_AT.hour, minute=RUN_AT.minute, second=0, microsecond=0)
    if t <= now:
        t += dt.timedelta(days=1)
    return (t - now).total_seconds()

if __name__ == "__main__":
    db.init()
    if not FEATURES_PATH.exists():
        print("[worker] first run - loading history (this can take 30-60+ minutes)")
        job()
    while True:
        wait = seconds_until(dt.datetime.now(IST))
        print(f"[worker] next refresh in {wait/3600:.1f} h")
        time.sleep(wait)
        if dt.datetime.now(IST).weekday() < 5:
            job()
