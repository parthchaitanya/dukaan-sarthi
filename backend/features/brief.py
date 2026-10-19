"""Daily Business Brief: a ~30-second spoken summary + 2 actions for today."""
from __future__ import annotations

from datetime import timedelta
from functools import lru_cache

from .. import db
from ..i18n import first_name, date_label, day_name, festival_name, hour_range, hour_span, inr, inr_short, pct, t
from . import cashflow, festival, winback


def _stats(mid: str, d):
    with db.connect(readonly=True) as con:
        q = con.execute("SELECT COALESCE(SUM(amount),0), COUNT(*) FROM payments WHERE merchant_id=? AND date=? "
                        "AND status='SUCCESS'", (mid, d.isoformat())).fetchone()
    return float(q[0]), int(q[1])


@lru_cache(maxsize=64)
def brief(mid: str, lang: str = "hinglish") -> dict:
    m = db.merchant(mid)
    y = db.yesterday()
    lw = y - timedelta(days=7)
    sales_y, n_y = _stats(mid, y)
    sales_lw, n_lw = _stats(mid, lw)
    change = (sales_y - sales_lw) / sales_lw if sales_lw else 0.0
    four = [(_stats(mid, y - timedelta(days=7 * k))[0]) for k in range(1, 5)]
    avg4 = sum(four) / len(four)

    hours = db.df("SELECT hour, SUM(amount) a FROM payments WHERE merchant_id=? AND date=? AND status='SUCCESS' "
                  "GROUP BY hour", (mid, y.isoformat())).set_index("hour")["a"].reindex(range(24), fill_value=0)
    window = hours.rolling(2).sum().shift(-1).fillna(0)
    peak_h = int(window.idxmax())

    top = db.df("SELECT payer, COUNT(DISTINCT date) visits, SUM(amount) spend FROM payments WHERE merchant_id=? "
                "AND status='SUCCESS' AND date>? GROUP BY payer ORDER BY visits DESC, spend DESC LIMIT 3",
                (mid, (y - timedelta(days=30)).isoformat()))

    # anomaly: failed-payment spike yesterday vs the 30-day norm
    fails = db.df("SELECT hour, COUNT(*) n FROM payments WHERE merchant_id=? AND date=? AND status='FAILED' GROUP BY hour",
                  (mid, y.isoformat())).set_index("hour")["n"]
    norm = db.df("SELECT COUNT(*)*1.0/30 n FROM payments WHERE merchant_id=? AND status='FAILED' AND date BETWEEN ? AND ?",
                 (mid, (y - timedelta(days=31)).isoformat(), (y - timedelta(days=1)).isoformat()))["n"].iloc[0]
    anomalies = []
    if fails.sum() >= 6 and fails.sum() > 3 * max(norm, 1):
        hot = fails[fails >= 2]
        h0, h1 = int(hot.index.min()), int(hot.index.max())
        anomalies.append({
            "kind": "failed_spike", "count": int(fails.sum()), "usual": round(float(norm), 1),
            "text": t("anomaly_failed", lang, hours=hour_span(h0, h1 + 1, lang), n=int(fails.sum())),
            "why": f"{int(fails.sum())} failed payments yesterday vs ~{norm:.1f} on a normal day.",
        })

    # ---- candidate actions, ranked
    actions = []
    wb = winback.winback(mid, lang)
    if wb["lapsing_count"] >= 3:
        actions.append({"kind": "winback", "priority": 2 + wb["at_stake_monthly"] / max(avg4 * 30, 1) * 10,
                        "text": t("act_winback", lang, n=wb["lapsing_count"], days=max(wb["lapsing_min_days"], 14)),
                        "why": f"These regulars spent about {wb['at_stake_label']} a month. "
                               f"Their silence is over 4x their usual gap.",
                        "cta": "winback"})
    fp = festival.plan(mid, lang, days_ahead=25)
    big = [f for f in fp["upcoming"] if f["expected_multiplier"] >= 1.3 and f["days_left"] >= 2]
    if big:
        f = max(big, key=lambda x: x["expected_multiplier"] / (1 + x["days_left"] / 10))
        actions.append({"kind": "festival", "priority": 1.5 + f["expected_multiplier"] - f["days_left"] / 20,
                        "text": t("act_festival", lang, fest=f["name"], days=f["days_left"], mult=f["expected_multiplier"]),
                        "why": f["why"], "cta": "plan"})
    cf = cashflow.cashflow(mid)
    low = [w for w in cf["low_weeks"] if not w["partial"] or w["min_balance"] < cf["safety_buffer"]]
    if low:
        w = low[0]
        from datetime import date
        wk = date.fromisoformat(w["week_start"])
        reasons = ", ".join(f"{n} {inr(a)}" for n, a in w["big_outflows"])
        actions.append({"kind": "cash", "priority": 3.5 if w["risk"] == "red" else 2.2,
                        "text": t("act_cash", lang, week=date_label(wk, lang), amt=inr_short(w["min_balance"], lang)),
                        "why": f"Projected low of {inr(w['min_balance'])} vs your safe limit of {inr(cf['safety_buffer'])}. "
                               f"Big payments that week: {reasons}.", "cta": "money"})
    if anomalies:
        actions.append({"kind": "failed", "priority": 3.0, "text": t("act_failed", lang), "why": anomalies[0]["why"],
                        "cta": "hisaab"})
    actions.sort(key=lambda a: -a["priority"])
    actions = actions[:2]
    if len(actions) < 2:
        actions.append({"kind": "peak", "priority": 0, "text": t("act_peak", lang, hours=hour_range(peak_h, lang)),
                        "why": "Based on yesterday's busiest 2-hour window.", "cta": None})

    day = day_name(lw, lang)
    if abs(change) < 0.03:
        sales_line = t("sales_flat", lang, amt=inr_short(sales_y, lang), day=day)
    elif change > 0:
        sales_line = t("sales_up", lang, amt=inr_short(sales_y, lang), day=day, pct=pct(change))
    else:
        sales_line = t("sales_down", lang, amt=inr_short(sales_y, lang), day=day, pct=pct(change))
    lines = [t("greet", lang, owner=first_name(m["owner"], lang)), sales_line,
             t("txns_peak", lang, n=n_y, hours=hour_range(peak_h, lang))]
    if len(top):
        lines.append(t("top_customer", lang, payer=top.iloc[0]["payer"], visits=int(top.iloc[0]["visits"])))
    lines += [a["text"] for a in anomalies]
    lines.append(t("actions_intro", lang))
    lines += [f"{i + 1}. {a['text']}" for i, a in enumerate(actions)]
    lines.append(t("close", lang))

    hourly = [{"hour": h, "amount": round(float(v))} for h, v in hours.items()]
    return {
        "merchant": {k: m[k] for k in ("id", "name", "category", "city", "owner")},
        "date": y.isoformat(), "today": db.today().isoformat(),
        "sales": round(sales_y), "sales_label": inr(sales_y), "txns": n_y,
        "last_week_same_day": round(sales_lw), "change_vs_last_week": round(change, 3),
        "avg_4_weeks_same_day": round(avg4),
        "peak_hours": hour_range(peak_h, lang), "peak_hour_start": peak_h, "hourly": hourly,
        "top_customers": top.to_dict("records"),
        "anomalies": anomalies, "actions": actions,
        "speech": " ".join(lines), "lines": lines,
        "festival_next": fp["upcoming"][0] if fp["upcoming"] else None,
    }


def clear():
    brief.cache_clear()
    cashflow.cashflow.cache_clear()


_ = festival_name  # re-exported for convenience
