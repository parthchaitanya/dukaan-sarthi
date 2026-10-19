"""Synthetic data generator: ~6 months of realistic Paytm-style transactions for 5 merchant personas.

Run:  python -m backend.seed

The generated data has:
  * weekday, hour-of-day, salary-day, monsoon and festival patterns per category
  * regular / occasional / walk-in customers. Some regulars stop coming (they are what
    the win-back engine should find), and some new regulars appear
  * failed and pending payments, plus one injected failure spike yesterday
  * T+1 settlements with injected mismatches (missing txn, delay, refund, chargeback)
  * cash outflows (rent, salary, supplier, festival stock, owner drawings)

Ground truth for evaluation lives in tables prefixed with an underscore. These tables
are never exposed to the LLM or the SQL tool.
"""
from __future__ import annotations

import hashlib
import random
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np

from . import config
from .calendar_data import FESTIVALS, festival_intensity


@dataclass
class Persona:
    id: str
    name: str
    category: str
    city: str
    owner: str
    lang: str
    base_txns: float          # average successful txns per normal day
    ticket: float             # median ticket size (₹)
    ticket_sigma: float
    hours: dict               # hour -> relative weight
    dow: list                 # Mon..Sun multipliers
    weather_sens: float       # effect of a rainy day
    n_regulars: int
    n_occasional: int
    share_regular: float
    share_occasional: float
    rent: float
    salary: float
    utilities: float
    cogs: float               # supplier cost as share of sales
    drawings: float           # weekly owner drawings (₹)
    opening_balance: float
    trend: float              # growth over the 6 months (e.g. 0.06 = +6%)


def _hours(spec):
    w = {h: 0.0 for h in range(24)}
    for (a, b), val in spec.items():
        for h in range(a, b):
            w[h] = val
    return w


PERSONAS = [
    Persona("m1", "Sharma General Store", "kirana", "Noida", "Ramesh Sharma", "hinglish",
            92, 165, 0.75, _hours({(7, 9): 0.8, (9, 12): 1.4, (12, 16): 0.7, (16, 18): 1.0, (18, 21): 1.7, (21, 22): 0.6}),
            [0.95, 0.92, 0.95, 0.97, 1.02, 1.12, 1.15], -0.08, 140, 420, 0.55, 0.25,
            22000, 24000, 4500, 0.80, 12000, 70000, 0.06),
    Persona("m2", "Glow Unisex Salon", "salon", "Ghaziabad", "Pooja Verma", "hinglish",
            24, 320, 0.6, _hours({(10, 12): 0.8, (12, 16): 1.0, (16, 21): 1.6}),
            [1.0, 0.45, 0.95, 0.95, 1.05, 1.45, 1.6], -0.2, 70, 260, 0.5, 0.25,
            18000, 30000, 3500, 0.18, 9000, 60000, 0.04),
    Persona("m3", "Chai Sutta Corner", "cafe", "Noida", "Aman Yadav", "hinglish",
            205, 38, 0.55, _hours({(7, 10): 1.6, (10, 13): 0.8, (13, 16): 0.9, (16, 19): 1.7, (19, 22): 0.9}),
            [1.08, 1.05, 1.05, 1.04, 1.02, 0.9, 0.8], 0.15, 160, 380, 0.5, 0.2,
            12000, 16000, 3000, 0.45, 9000, 30000, 0.03),
    Persona("m4", "Gupta Medicos", "pharmacy", "Greater Noida", "Sunil Gupta", "hi",
            58, 240, 0.85, _hours({(8, 11): 1.2, (11, 17): 0.8, (17, 22): 1.5}),
            [1.08, 1.0, 1.0, 1.0, 1.0, 0.98, 0.9], 0.05, 160, 300, 0.6, 0.2,
            20000, 22000, 4000, 0.76, 11000, 65000, 0.05),
    Persona("m5", "Mithaas Sweets", "sweets", "Noida", "Kavita Agarwal", "hinglish",
            46, 380, 0.7, _hours({(9, 12): 0.9, (12, 16): 0.8, (16, 22): 1.6}),
            [0.92, 0.9, 0.92, 0.95, 1.0, 1.15, 1.25], -0.05, 110, 340, 0.45, 0.25,
            26000, 36000, 6000, 0.60, 14000, 90000, 0.05),
]

MODES = (("UPI", 0.9), ("Card", 0.04), ("Wallet", 0.06))

SCHEMA = """
CREATE TABLE merchants(id TEXT PRIMARY KEY, name TEXT, category TEXT, city TEXT, owner TEXT, lang TEXT,
  opening_balance REAL, opening_date TEXT, safety_buffer REAL, cogs_ratio REAL);
CREATE TABLE payments(id INTEGER PRIMARY KEY, merchant_id TEXT, ts TEXT, date TEXT, hour INTEGER,
  amount REAL, payer TEXT, mode TEXT, status TEXT);
CREATE INDEX ix_pay ON payments(merchant_id, date);
CREATE INDEX ix_pay_payer ON payments(merchant_id, payer);
CREATE TABLE refunds(id INTEGER PRIMARY KEY, merchant_id TEXT, payment_id INTEGER, date TEXT, amount REAL, reason TEXT);
CREATE TABLE settlements(id INTEGER PRIMARY KEY, merchant_id TEXT, business_date TEXT, settled_on TEXT,
  amount REAL, utr TEXT);
CREATE INDEX ix_set ON settlements(merchant_id, business_date);
CREATE TABLE expenses(id INTEGER PRIMARY KEY, merchant_id TEXT, date TEXT, category TEXT, amount REAL, note TEXT);
CREATE TABLE recurring_expenses(merchant_id TEXT, name TEXT, kind TEXT, day INTEGER, amount REAL);
CREATE TABLE planned_expenses(merchant_id TEXT, date TEXT, name TEXT, amount REAL);
CREATE TABLE weather(city TEXT, date TEXT, rainy INTEGER);
CREATE TABLE campaigns(id INTEGER PRIMARY KEY, merchant_id TEXT, created_at TEXT, segment TEXT, lang TEXT,
  message TEXT, n_customers INTEGER, status TEXT);
CREATE TABLE live_payments(id INTEGER PRIMARY KEY, merchant_id TEXT, ts TEXT, amount REAL);
CREATE TABLE _truth_customers(merchant_id TEXT, payer TEXT, kind TEXT, start_date TEXT, churn_date TEXT);
CREATE TABLE _truth_recon(settlement_id INTEGER, merchant_id TEXT, anomaly TEXT);
"""


def payer_hash(mid: str, raw: str) -> str:
    """Payer VPAs are hashed at ingestion. Raw IDs are never stored."""
    return "C-" + hashlib.sha1(f"{mid}:{raw}".encode()).hexdigest()[:5].upper()


def generate(db_path=config.DB_PATH, today: date = config.DEMO_TODAY, days: int = config.HISTORY_DAYS,
             seed: int = config.SEED) -> None:
    rng = np.random.default_rng(seed)
    pyr = random.Random(seed)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)

    start = today - timedelta(days=days)
    dates = [start + timedelta(days=i) for i in range(days)]  # up to yesterday

    cities = sorted({p.city for p in PERSONAS})
    rain = {}
    for city in cities:
        for d in dates + [today]:
            p_rain = 0.42 if d.month in (7, 8, 9) else (0.12 if d.month in (6, 10) else 0.05)
            rain[(city, d)] = int(rng.random() < p_rain)
            con.execute("INSERT INTO weather VALUES (?,?,?)", (city, d.isoformat(), rain[(city, d)]))

    for p in PERSONAS:
        _gen_merchant(con, p, dates, today, rain, rng, pyr)
    con.commit()
    con.close()


def _gen_merchant(con, p: Persona, dates, today, rain, rng, pyr):
    mid = p.id
    hours = np.array([p.hours[h] for h in range(24)])
    hours = hours / hours.sum()
    first, last = dates[0], dates[-1]

    # --- customers -------------------------------------------------------
    regulars = []
    for i in range(p.n_regulars):
        raw = f"{mid}reg{i}@upi"
        h = payer_hash(mid, raw)
        rate = rng.gamma(2.5, 1.0)
        start_d, churn_d, kind = first, None, "regular"
        u = rng.random()
        if u < 0.13:  # stops coming 3-7 weeks before today
            churn_d = today - timedelta(days=int(rng.integers(22, 50)))
            kind = "regular_lapsed"
        elif u < 0.21:  # new regular who started recently
            start_d = today - timedelta(days=int(rng.integers(25, 70)))
            kind = "regular_new"
        regulars.append([h, rate, start_d, churn_d])
        con.execute("INSERT INTO _truth_customers VALUES (?,?,?,?,?)",
                    (mid, h, kind, start_d.isoformat(), churn_d.isoformat() if churn_d else None))
    occasional = [payer_hash(mid, f"{mid}occ{i}@upi") for i in range(p.n_occasional)]
    for h in occasional:
        con.execute("INSERT INTO _truth_customers VALUES (?,?,?,?,?)", (mid, h, "occasional", first.isoformat(), None))
    walkin_counter = 0

    # --- payments ---------------------------------------------------------
    pay_rows = []
    daily_success = {}
    pay_id = con.execute("SELECT COALESCE(MAX(id),0) FROM payments").fetchone()[0]
    all_days = dates + [today]
    for idx, d in enumerate(all_days):
        f_mult, f_key = festival_intensity(d, p.category)
        mult = p.dow[d.weekday()] * f_mult
        mult *= 1 + p.trend * (idx / len(dates))
        if d.day <= 5:
            mult *= 1.06  # salary days
        if rain[(p.city, d)]:
            mult *= 1 + p.weather_sens
        if d.month in (7, 8) and p.category == "pharmacy":
            mult *= 1.08  # monsoon illness season
        lam = p.base_txns * mult * rng.lognormal(0, 0.09)
        n = int(rng.poisson(lam))
        if d == today:
            # Today is still in progress: payments up to ~10:30 so far.
            cutoff = 10.5
        else:
            cutoff = 24
        active = [r for r in regulars if r[2] <= d and (r[3] is None or d < r[3])]
        weights = np.array([r[1] for r in active]) if active else None
        if weights is not None:
            weights = weights / weights.sum()
        tot = 0.0
        for _ in range(n):
            hr = int(rng.choice(24, p=hours))
            minute = int(rng.integers(0, 60))
            if hr + minute / 60 > cutoff:
                continue
            u = rng.random()
            if u < p.share_regular and active:
                payer = active[int(rng.choice(len(active), p=weights))][0]
                ticket_mult = 1.05
            elif u < p.share_regular + p.share_occasional:
                payer = occasional[int(rng.integers(0, len(occasional)))]
                ticket_mult = 1.0
            else:
                walkin_counter += 1
                payer = payer_hash(mid, f"{mid}walk{walkin_counter}@upi")
                ticket_mult = 0.9
            amt = p.ticket * ticket_mult * rng.lognormal(0, p.ticket_sigma)
            if f_key:
                amt *= 1.25
            amt = max(10, round(amt / 5) * 5)
            mode = pyr.choices([m for m, _ in MODES], [w for _, w in MODES])[0]
            r = rng.random()
            fail_rate = 0.012
            if d == today - timedelta(days=1) and mid == "m1" and 12 <= hr < 16:
                fail_rate = 0.5  # injected bank-side failure spike yesterday afternoon
            status = "FAILED" if r < fail_rate else ("PENDING" if r < fail_rate + 0.003 else "SUCCESS")
            pay_id += 1
            ts = datetime(d.year, d.month, d.day, hr, minute, int(rng.integers(0, 60)))
            pay_rows.append((pay_id, mid, ts.isoformat(sep=" "), d.isoformat(), hr, amt, payer, mode, status))
            if status == "SUCCESS":
                tot += amt
        daily_success[d] = tot
    con.executemany("INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?)", pay_rows)

    # --- refunds, settlements and injected mismatches ----------------------
    utr_n = 0
    settlement_cash = {}  # settled_on -> amount (cash inflow)
    by_date = {}
    for row in pay_rows:
        if row[8] == "SUCCESS":
            by_date.setdefault(row[3], []).append(row)
    for d in dates:  # business dates up to yesterday
        amount = daily_success[d]
        anomaly = None
        r = rng.random()
        if mid == "m1" and d == today - timedelta(days=4):
            r = 0.04  # make sure the demo merchant has one recent unexplained shortfall
        day_pays = by_date.get(d.isoformat(), [])
        if r < 0.035 and day_pays:
            # customer refund: recorded in the refunds table, so it is explainable
            pr = day_pays[int(rng.integers(0, len(day_pays)))]
            con.execute("INSERT INTO refunds(merchant_id,payment_id,date,amount,reason) VALUES (?,?,?,?,?)",
                        (mid, pr[0], d.isoformat(), pr[5], "Customer return"))
            amount -= pr[5]
            anomaly = "refund"
        elif r < 0.055 and day_pays:
            pr = day_pays[int(rng.integers(0, len(day_pays)))]
            amount -= pr[5]
            anomaly = "missing_txn"
        elif r < 0.065 and day_pays:
            pr = day_pays[int(rng.integers(0, len(day_pays)))]
            amount -= pr[5]
            anomaly = "chargeback"
        delay = 1
        if rng.random() < 0.03:
            delay = 3
            anomaly = anomaly or "delayed"
        settled_on = d + timedelta(days=delay)
        if settled_on > today:
            continue  # still on its way: shows up as "awaiting settlement"
        utr_n += 1
        cur = con.execute("INSERT INTO settlements(merchant_id,business_date,settled_on,amount,utr) VALUES (?,?,?,?,?)",
                          (mid, d.isoformat(), settled_on.isoformat(), round(amount, 2), f"PYTM{mid[1:]}{utr_n:06d}"))
        if anomaly:
            con.execute("INSERT INTO _truth_recon VALUES (?,?,?)", (cur.lastrowid, mid, anomaly))
        settlement_cash[settled_on] = settlement_cash.get(settled_on, 0) + amount

    # --- cash outflows ------------------------------------------------------
    recurring = [("Shop rent", "monthly", 5, p.rent), ("Staff salary", "monthly", 1, p.salary),
                 ("Electricity & internet", "monthly", 10, p.utilities),
                 ("Owner drawings: keeps this balance, takes the rest home", "weekly", 6, 0),
                 ("Supplier payment", "supplier", 0, p.cogs)]
    for name, kind, day, amt in recurring:
        con.execute("INSERT INTO recurring_expenses VALUES (?,?,?,?,?)", (mid, name, kind, day, amt))

    exp_rows = []
    for d in dates:
        if d.day == 5:
            exp_rows.append((mid, d.isoformat(), "rent", p.rent, "Shop rent"))
        if d.day == 1:
            exp_rows.append((mid, d.isoformat(), "salary", p.salary, "Staff salary"))
        if d.day == 10:
            exp_rows.append((mid, d.isoformat(), "utilities", round(p.utilities * rng.uniform(0.85, 1.2)), "Electricity & internet"))
        if d.weekday() == 0:  # Monday: pay supplier for last week's sales
            last_week = sum(daily_success.get(d - timedelta(days=k), 0) for k in range(1, 8))
            exp_rows.append((mid, d.isoformat(), "supplier", round(p.cogs * last_week * rng.uniform(0.9, 1.1)), "Supplier payment"))
    # festival stock bought a week ahead (sweets & kirana & salon)
    for key, name, fd, *_ in FESTIVALS:
        buy_day = fd - timedelta(days=7)
        mult, _ = festival_intensity(fd, p.category)
        if mult >= 1.5:
            extra = round(p.base_txns * p.ticket * (mult - 1) * 3 * p.cogs, -2)
            if first <= buy_day < today:
                exp_rows.append((mid, buy_day.isoformat(), "festival_stock", extra, f"{name} stock"))
            elif buy_day >= today:
                con.execute("INSERT INTO planned_expenses VALUES (?,?,?,?)", (mid, buy_day.isoformat(), f"{name} stock", extra))
    # Owner drawings: every Sunday the owner takes home most of the cash above a level
    # they like to keep in the account. This keeps the balance realistic (it does not pile up).
    safety = p.rent + p.salary  # "enough to pay rent and staff"
    keep = round(safety * 1.0, -3)
    out_by_day = {}
    for row in exp_rows:
        out_by_day[row[1]] = out_by_day.get(row[1], 0) + row[3]
    bal = p.opening_balance
    for d in dates:
        bal += settlement_cash.get(d, 0) - out_by_day.get(d.isoformat(), 0)
        # Monday's supplier bill is known on Sunday, so the owner leaves money for it.
        bill = p.cogs * sum(daily_success.get(d - timedelta(days=k), 0) for k in range(0, 7))
        if d.weekday() == 6 and bal - bill > keep:
            draw = round((bal - bill - keep) * rng.uniform(0.85, 0.97), -2)
            bal -= draw
            exp_rows.append((mid, d.isoformat(), "drawings", draw, "Owner drawings"))
    con.execute("UPDATE recurring_expenses SET amount=? WHERE merchant_id=? AND kind='weekly'", (keep, mid))
    con.executemany("INSERT INTO expenses(merchant_id,date,category,amount,note) VALUES (?,?,?,?,?)", exp_rows)

    con.execute("INSERT INTO merchants VALUES (?,?,?,?,?,?,?,?,?,?)",
                (mid, p.name, p.category, p.city, p.owner, p.lang, p.opening_balance, first.isoformat(),
                 safety, p.cogs))


if __name__ == "__main__":
    generate()
    con = sqlite3.connect(config.DB_PATH)
    for row in con.execute("SELECT merchant_id, COUNT(*), ROUND(SUM(amount)) FROM payments GROUP BY 1"):
        print(row)
    print("Seeded", config.DB_PATH)
