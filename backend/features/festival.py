"""Demand & Festival Planner: upcoming spikes from festivals, salary days and weekends."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from .. import db
from ..calendar_data import FESTIVALS, STOCK_TIPS, UPLIFT
from ..i18n import festival_name, inr


def _measured_uplift(sales: pd.Series, fdate) -> float | None:
    """Sales on a past festival day vs the median of the same weekday in the 4 weeks around it."""
    ts = pd.Timestamp(fdate)
    if ts not in sales.index:
        return None
    ref = [ts + pd.Timedelta(days=7 * k) for k in (-3, -2, -1, 1, 2)]
    ref = [r for r in ref if r in sales.index]
    if len(ref) < 3:
        return None
    base = sales[ref].median()
    return float(sales[ts] / base) if base else None


def plan(mid: str, lang: str = "hinglish", days_ahead: int = 45) -> dict:
    m = db.merchant(mid)
    cat = m["category"]
    today = db.today()
    sales = db.daily_sales(mid)
    normal_day = float(sales.iloc[-28:].median())

    past = []
    for key, name, fd, *_ in FESTIVALS:
        if fd < today:
            u = _measured_uplift(sales, fd)
            if u:
                past.append({"key": key, "name": festival_name(name, lang), "date": fd.isoformat(),
                             "your_uplift": round(u, 2), "category_prior": UPLIFT[cat][key]})

    upcoming = []
    for key, name, fd, before, after in FESTIVALS:
        dd = (fd - today).days
        if 0 <= dd <= days_ahead:
            prior = UPLIFT[cat][key]
            # calibrate the network prior with how this shop actually reacted to past festivals
            calib = [p["your_uplift"] / p["category_prior"] for p in past if p["category_prior"] >= 1.2]
            factor = sum(calib) / len(calib) if calib else 1.0
            expected = 1 + (prior - 1) * factor
            extra = normal_day * max(expected - 1, 0) * (1 + 0.6 * before)
            tips = STOCK_TIPS.get(cat, {}).get(key) or (STOCK_TIPS[cat]["default"] if expected >= 1.3 else [])
            staff = None
            if expected >= 1.8:
                staff = f"Add 1 extra helper for {before + 1} days before {name}"
            elif expected >= 1.4:
                staff = f"Extend hours on {name} and the day before"
            upcoming.append({
                "key": key, "name": festival_name(name, lang), "date": fd.isoformat(), "days_left": dd,
                "expected_multiplier": round(expected, 1), "extra_sales": round(extra), "extra_sales_label": inr(extra),
                "stock": tips, "staff": staff,
                "why": f"{name} usually brings ~{prior:.1f}x sales for {cat} shops; your past festivals ran "
                       f"{factor:.2f}x of the usual for your category.",
            })
    # salary days and weekends
    nxt_salary = next(today + timedelta(days=k) for k in range(0, 40) if (today + timedelta(days=k)).day == 1)
    by_dow = sales.iloc[-56:].groupby(sales.iloc[-56:].index.dayofweek).mean()
    best_dow = int(by_dow.idxmax())
    worst_dow = int(by_dow.idxmin())
    return {
        "normal_day": round(normal_day), "normal_day_label": inr(normal_day),
        "upcoming": upcoming, "past": past,
        "salary_window": {"start": nxt_salary.isoformat(), "end": (nxt_salary + timedelta(days=4)).isoformat(),
                          "note": "Salary days (1st–5th) usually lift sales ~5–8%."},
        "weekday_pattern": {"best": best_dow, "worst": worst_dow,
                            "best_vs_worst": round(float(by_dow.max() / by_dow.min()), 2)},
    }
