"""Guarded, read-only SQL for Ask Anything.

Layers of protection:
 1. The connection is opened read-only (SQLite `mode=ro`).
 2. The query must be a single SELECT/WITH statement (no ; chains).
 3. The merchant only ever sees per-merchant temp views (my_payments, my_settlements,
    my_refunds, my_expenses). An SQLite authorizer rejects reads of any other table,
    so one merchant can never query another merchant's rows, and the hidden
    ground-truth tables are unreachable.
 4. Results are capped (row limit) and long queries are aborted (progress handler).
Payer IDs are already pseudonymous hashes; no names, phone numbers or VPAs exist in the DB.
"""
from __future__ import annotations

import re
import sqlite3
import time

from . import config

VIEWS = {
    "my_payments": "SELECT id, ts, date, hour, amount, payer, mode, status FROM main.payments WHERE merchant_id = :m",
    "my_settlements": "SELECT business_date, settled_on, amount, utr FROM main.settlements WHERE merchant_id = :m",
    "my_refunds": "SELECT payment_id, date, amount, reason FROM main.refunds WHERE merchant_id = :m",
    "my_expenses": "SELECT date, category, amount, note FROM main.expenses WHERE merchant_id = :m",
}
BASE_TABLES = {"payments", "settlements", "refunds", "expenses"}

SCHEMA_DOC = """Tables you can query (SQLite):
my_payments(id, ts TEXT 'YYYY-MM-DD HH:MM:SS', date TEXT 'YYYY-MM-DD', hour INT, amount REAL (₹), payer TEXT (pseudonymous id like C-1A2B3), mode TEXT ('UPI','Card','Wallet'), status TEXT ('SUCCESS','FAILED','PENDING'))
my_settlements(business_date TEXT, settled_on TEXT, amount REAL, utr TEXT)
my_refunds(payment_id INT, date TEXT, amount REAL, reason TEXT)
my_expenses(date TEXT, category TEXT ('rent','salary','utilities','supplier','festival_stock','drawings'), amount REAL, note TEXT)
Sales = SUM(amount) over my_payments WHERE status='SUCCESS'. Use date('{today}', '-N day') style date maths. Today is {today}; today's data is partial."""

FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex|"
                       r"analyze|begin|commit|rollback|savepoint|release|load_extension)\b", re.I)


class SQLGuardError(ValueError):
    pass


def validate(sql: str) -> str:
    q = sql.strip().rstrip(";").strip()
    if ";" in q:
        raise SQLGuardError("Only one statement is allowed.")
    if not re.match(r"^(select|with)\b", q, re.I):
        raise SQLGuardError("Only SELECT queries are allowed.")
    if FORBIDDEN.search(q):
        raise SQLGuardError("Query contains a forbidden keyword.")
    return q


def run(merchant_id: str, sql: str, max_rows: int = 200, timeout_s: float = 2.0) -> dict:
    q = validate(sql)
    con = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    try:
        for name, body in VIEWS.items():
            # temp views live in the temp schema, so they work on a read-only connection
            con.execute(f"CREATE TEMP VIEW {name} AS " + body.replace(":m", "'" + merchant_id.replace("'", "") + "'"))

        def authorizer(action, arg1, arg2, dbname, source):
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE):
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_READ:
                table = (arg1 or "").lower()
                if table in VIEWS:
                    return sqlite3.SQLITE_OK
                if table in BASE_TABLES and (source or "").lower() in VIEWS:
                    return sqlite3.SQLITE_OK  # read through a merchant-scoped view only
                if table.startswith("sqlite_temp_master") or table == "":
                    return sqlite3.SQLITE_OK
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_DENY

        con.set_authorizer(authorizer)
        deadline = time.monotonic() + timeout_s
        con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10000)
        t0 = time.perf_counter()
        try:
            cur = con.execute(q)
        except sqlite3.DatabaseError as e:
            raise SQLGuardError(f"Query rejected: {e}") from e
        cols = [c[0] for c in cur.description]
        rows = cur.fetchmany(max_rows)
        return {"sql": q, "columns": cols, "rows": [list(r) for r in rows],
                "truncated": len(rows) == max_rows, "ms": round((time.perf_counter() - t0) * 1000, 1)}
    finally:
        con.close()
