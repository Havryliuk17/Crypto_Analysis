from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Query
from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement
import redis



SYMBOLS = ["ETHUSD", "ADAUSD", "DOGEUSD", "SOLUSD", "BTCUSD", "BNBUSD", "XRPUSD"]

UTC = timezone.utc

app = FastAPI(title="Crypto Analytics API")


cluster = Cluster(['cassandra'])
session = cluster.connect()
session.set_keyspace('crypto_data')

redis_cli = redis.Redis(host="redis", port=6379, db=0)


def prev_full_hour(ts: datetime) -> datetime:
    """Latest *completed* hour bucket start."""
    return ts.replace(minute=0, second=0, microsecond=0, tzinfo=UTC)

def prev_full_minute(ts: datetime) -> datetime:
    """Latest *completed* minute bucket start."""
    return ts.replace(second=0, microsecond=0, tzinfo=UTC)


@app.get("/reports/hourly-counts")
def hourly_counts_last_6h() -> List[Dict]:
    """
    Return num_trades per symbol for each of the last 6 **completed**
    hours, **excluding the immediate previous hour**.
    """
    now = datetime.now(UTC)
    end = prev_full_hour(now)
    start = end - timedelta(hours=6)
    stmt = session.prepare(
        """
        SELECT window_start, num_trades
        FROM hourly_aggregates_by_symbol
        WHERE symbol=? AND window_start>=? AND window_start<?
        """
    )

    rows: List[Dict] = []
    for sym in SYMBOLS:
        for r in session.execute(stmt, [sym, start, end]):
            rows.append(
                {
                    "symbol": sym,
                    "hour": r.window_start.isoformat(),
                    "num_trades": r.num_trades,
                }
            )
    return rows


@app.get("/reports/volume-6h")
def volume_last_6h() -> Dict[str, int]:
    """
    Total trading volume per symbol for the last 6 completed hours,
    excluding the immediate previous hour.
    """
    now = datetime.now(UTC)
    end = prev_full_hour(now)
    start = end - timedelta(hours=6)
    stmt = session.prepare(
        """
        SELECT total_volume
        FROM hourly_aggregates_by_symbol
        WHERE symbol=? AND window_start>=? AND window_start<?
        """
    )

    result: Dict[str, int] = {}
    for sym in SYMBOLS:
        vol = sum(r.total_volume or 0 for r in session.execute(stmt, [sym, start, end]))
        result[sym] = vol
    return result


@app.get("/reports/hourly-count-volume")
def hourly_count_volume_last_12h() -> List[Dict]:
    """
    Number of trades and total volume for each symbol for each of the
    last 12 completed hours, **excluding the current hour**.
    """
    now = datetime.now(UTC)
    end = prev_full_hour(now)
    start = end - timedelta(hours=12)
    stmt = session.prepare(
        """
        SELECT window_start, num_trades, total_volume
        FROM hourly_aggregates_by_symbol
        WHERE symbol=? AND window_start>=? AND window_start<?
        """
    )
    rows: List[Dict] = []
    for sym in SYMBOLS:
        for r in session.execute(stmt, [sym, start, end]):
            rows.append(
                {
                    "symbol": sym,
                    "hour": r.window_start.isoformat(),
                    "num_trades": r.num_trades,
                    "total_volume": r.total_volume,
                }
            )
    return rows


@app.get("/query/{symbol}/trades")
def trades_last_n_minutes(
    symbol: str, minutes: int = Query(..., gt=0, le=120)
):
    """
    Number of trades in `symbol` during the last N completed minutes,
    excluding the latest minute bucket.
    """
    if symbol not in SYMBOLS:
        raise HTTPException(404, "Unknown symbol")

    now = datetime.now(UTC)
    end = prev_full_minute(now) - timedelta(minutes=1)
    start = end - timedelta(minutes=minutes)

    stmt = session.prepare(
        """
        SELECT num_trades
        FROM minute_aggregates_by_symbol
        WHERE symbol=? AND window_start>=? AND window_start<?
        """
    )
    total = sum(r.num_trades or 0 for r in session.execute(stmt, [symbol, start, end]))
    return {"symbol": symbol, "minutes": minutes, "num_trades": total}


@app.get("/query/top-volume")
def top_n_volume(limit: int = Query(..., gt=0, le=50)):
    """
    Top-N symbols by volume in the previous full hour.
    """
    now = datetime.now(UTC)
    hour_bucket = prev_full_hour(now) - timedelta(hours=1)

    cql = f"""
        SELECT symbol, total_volume
        FROM hourly_volume_ranking
        WHERE window_start = ?
        LIMIT {int(limit)}
    """
    stmt = session.prepare(cql)

    out = [dict(row._asdict()) for row in session.execute(stmt, [hour_bucket])]
    return {"hour_start": hour_bucket.isoformat(), "top": out}


@app.get("/query/{symbol}/price")
def current_price(symbol: str):
    if symbol not in SYMBOLS:
        raise HTTPException(404, "Unknown symbol")

    buy = redis_cli.get(f"{symbol}_Buy")
    sell = redis_cli.get(f"{symbol}_Sell")

    if buy is None and sell is None:
        raise HTTPException(404, "Price not cached yet, try again later")

    return {
        "symbol": symbol,
        "buy": float(buy) if buy else None,
        "sell": float(sell) if sell else None,
    }
