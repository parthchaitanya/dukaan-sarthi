"""Database helpers (SQLite for the demo; the queries are plain SQL so PostgreSQL works the same)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd

from . import config


@contextmanager
def connect(readonly: bool = False):
    if readonly:
        con = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    else:
        con = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def df(sql: str, params=()) -> pd.DataFrame:
    with connect(readonly=True) as con:
        return pd.read_sql_query(sql, con, params=params)


def merchants() -> list[dict]:
    with connect(readonly=True) as con:
        return [dict(r) for r in con.execute("SELECT id,name,category,city,owner,lang FROM merchants ORDER BY id")]


@lru_cache(maxsize=16)
def merchant(mid: str) -> dict:
    with connect(readonly=True) as con:
        r = con.execute("SELECT * FROM merchants WHERE id=?", (mid,)).fetchone()
    if not r:
        raise KeyError(f"Unknown merchant {mid}")
    return dict(r)


def today() -> date:
    return config.DEMO_TODAY


def yesterday() -> date:
    return config.DEMO_TODAY - timedelta(days=1)


def daily_sales(mid: str, end: date | None = None) -> pd.Series:
    """Successful sales per business day, history only (excludes today, which is in progress)."""
    end = end or yesterday()
    d = df("SELECT date, SUM(amount) amt FROM payments WHERE merchant_id=? AND status='SUCCESS' AND date<=? "
           "GROUP BY date ORDER BY date", (mid, end.isoformat()))
    s = d.set_index(pd.to_datetime(d["date"]))["amt"]
    full = pd.date_range(s.index.min(), pd.Timestamp(end), freq="D")
    return s.reindex(full).fillna(0.0)


def clear_caches():
    merchant.cache_clear()
