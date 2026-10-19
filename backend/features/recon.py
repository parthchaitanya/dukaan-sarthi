"""Smart Reconciliation & Dispute Helper: match each settlement to that day's sales and explain gaps."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from .. import db
from ..i18n import inr

TOL = 1.0  # ₹


def reconcile(mid: str, days: int = 30, end: date | None = None) -> dict:
    end = end or db.yesterday()
    start = end - timedelta(days=days - 1)
    sales = db.df("SELECT date, SUM(amount) amt, COUNT(*) n FROM payments WHERE merchant_id=? AND status='SUCCESS' "
                  "AND date BETWEEN ? AND ? GROUP BY date", (mid, start.isoformat(), end.isoformat())).set_index("date")
    st = db.df("SELECT id, business_date, settled_on, amount, utr FROM settlements WHERE merchant_id=? "
               "AND business_date BETWEEN ? AND ?", (mid, start.isoformat(), end.isoformat())).set_index("business_date")
    rf = db.df("SELECT date, SUM(amount) amt FROM refunds WHERE merchant_id=? AND date BETWEEN ? AND ? GROUP BY date",
               (mid, start.isoformat(), end.isoformat())).set_index("date")["amt"]
    pending = db.df("SELECT date, COUNT(*) n, SUM(amount) amt FROM payments WHERE merchant_id=? AND status='PENDING' "
                    "AND date BETWEEN ? AND ? GROUP BY date", (mid, start.isoformat(), end.isoformat())).set_index("date")
    rows = []
    for d in pd.date_range(start, end).strftime("%Y-%m-%d"):
        expected = float(sales["amt"].get(d, 0))
        s = st.loc[d] if d in st.index else None
        item = {"business_date": d, "expected": round(expected, 2)}
        if s is None:
            item.update(status="awaiting", settled=None, gap=None,
                        explanation="Settlement not received yet. Normally arrives the next morning (T+1).")
            if d < (end - timedelta(days=1)).isoformat():
                item.update(status="review", explanation="Settlement is late by more than 1 day. Raise a ticket.")
            rows.append(item)
            continue
        gap = round(expected - float(s["amount"]), 2)
        lag = (date.fromisoformat(s["settled_on"]) - date.fromisoformat(d)).days
        item.update(settled=float(s["amount"]), gap=gap, utr=s["utr"], settled_on=s["settled_on"], settlement_id=int(s["id"]))
        refund = float(rf.get(d, 0))
        if abs(gap) <= TOL:
            item.update(status="matched", explanation="Matched exactly.")
            if lag > 1:
                item.update(status="explained", explanation=f"Matched, but arrived {lag} days later than usual.")
        elif refund and abs(gap - refund) <= TOL:
            item.update(status="explained", explanation=f"Gap equals the refund of {inr(refund)} you gave that day.")
        else:
            cand = db.df("SELECT id, ts, amount, payer, mode FROM payments WHERE merchant_id=? AND date=? AND "
                         "status='SUCCESS' AND ABS(amount-?)<=?", (mid, d, gap, TOL))
            if len(cand):
                c = cand.iloc[0]
                item.update(status="review", suspect_payment={"id": int(c["id"]), "ts": c["ts"], "amount": float(c["amount"]),
                                                              "payer": c["payer"], "mode": c["mode"]},
                            explanation=f"Short by {inr(gap)}: looks like the {inr(c['amount'])} payment at "
                                        f"{c['ts'][11:16]} from {c['payer']} was not settled (or was charged back).",
                            dispute_draft=dispute_text(mid, d, s["utr"], gap, c))
            else:
                item.update(status="review", explanation=f"Short by {inr(gap)} and no single payment explains it.",
                            dispute_draft=dispute_text(mid, d, s["utr"], gap, None))
        if d in pending.index:
            item["pending_payments"] = int(pending.loc[d, "n"])
        rows.append(item)
    counts = pd.Series([r["status"] for r in rows]).value_counts().to_dict()
    auto = counts.get("matched", 0) + counts.get("explained", 0) + counts.get("awaiting", 0)
    return {"rows": rows[::-1], "counts": counts, "auto_resolved": auto, "total": len(rows),
            "needs_review": counts.get("review", 0)}


def dispute_text(mid: str, d: str, utr: str, gap: float, cand) -> str:
    m = db.merchant(mid)
    lines = [
        "To: Paytm for Business support",
        f"Subject: Settlement shortfall for {d} (UTR {utr})",
        "",
        f"Merchant: {m['name']} ({mid})",
        f"Business date: {d}",
        f"Settlement UTR: {utr}",
        f"Shortfall: {inr(gap)}",
    ]
    if cand is not None:
        lines += [f"Likely missing payment: {inr(cand['amount'])} at {cand['ts']} via {cand['mode']} "
                  f"(payment ref #{int(cand['id'])})"]
    lines += ["", "The payment shows as successful in my Paytm app but is not part of the settlement. "
                  "Please check and credit the amount, or share the reason for the deduction.", "", "Thank you."]
    return "\n".join(lines)
