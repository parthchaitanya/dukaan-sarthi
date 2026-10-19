"""Soundbox Nudges: short spoken wins after a payment."""
from __future__ import annotations

from datetime import datetime

from .. import db

MILESTONES = (25, 50, 75, 100, 150, 200, 250, 300)


def _today_counts(mid: str, upto: str):
    t, y = db.today().isoformat(), db.yesterday().isoformat()
    with db.connect(readonly=True) as con:
        today_n = con.execute("SELECT COUNT(*) FROM payments WHERE merchant_id=? AND date=? AND status='SUCCESS'",
                              (mid, t)).fetchone()[0]
        today_n += con.execute("SELECT COUNT(*) FROM live_payments WHERE merchant_id=?", (mid,)).fetchone()[0]
        today_amt = con.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE merchant_id=? AND date=? AND "
                                "status='SUCCESS'", (mid, t)).fetchone()[0]
        today_amt += con.execute("SELECT COALESCE(SUM(amount),0) FROM live_payments WHERE merchant_id=?", (mid,)).fetchone()[0]
        y_n = con.execute("SELECT COUNT(*) FROM payments WHERE merchant_id=? AND date=? AND status='SUCCESS' AND "
                          "substr(ts,12,5)<=?", (mid, y, upto)).fetchone()[0]
    return today_n, today_amt, y_n


def record_payment(mid: str, amount: float, lang: str = "hinglish") -> dict:
    """Simulate a live payment hitting the Soundbox and return what it should say."""
    db.merchant(mid)
    with db.connect() as con:
        n_live = con.execute("SELECT COUNT(*) FROM live_payments WHERE merchant_id=?", (mid,)).fetchone()[0]
        # demo clock: starts at 10:30 and moves 3 minutes per simulated payment
        minutes = 10 * 60 + 30 + 3 * (n_live + 1)
        ts = f"{db.today().isoformat()} {minutes // 60:02d}:{minutes % 60:02d}:00"
        con.execute("INSERT INTO live_payments(merchant_id, ts, amount) VALUES (?,?,?)", (mid, ts, amount))
        con.commit()
    upto = ts[11:16]
    n, amt, y_n = _today_counts(mid, upto)
    paid = {"hinglish": f"Paytm par {int(amount)} rupaye prapt hue.", "hi": f"पेटीएम पर {int(amount)} रुपये प्राप्त हुए।",
            "en": f"Received {int(amount)} rupees on Paytm."}[lang]
    nudge = None
    if n in MILESTONES or n % 50 == 0:
        diff = (n - y_n) / y_n if y_n else 0
        if lang == "hi":
            nudge = f"आज की {n}वीं बिक्री! " + (f"कल इसी समय से {abs(diff) * 100:.0f}% {'ज़्यादा' if diff >= 0 else 'कम'}।" if y_n else "")
        elif lang == "en":
            nudge = f"That's sale number {n} today! " + (f"{abs(diff) * 100:.0f}% {'ahead of' if diff >= 0 else 'behind'} this time yesterday." if y_n else "")
        else:
            nudge = f"Aaj ki {n}th sale! " + (f"Kal isi time se {abs(diff) * 100:.0f}% {'zyada' if diff >= 0 else 'kam'}." if y_n else "")
    return {"ts": ts, "count_today": n, "amount_today": round(amt), "yesterday_same_time": y_n,
            "speak": paid + (" " + nudge if nudge else ""), "nudge": nudge,
            "next_milestone": next((x for x in MILESTONES if x > n), n + 50 - n % 50)}


def reset_live(mid: str | None = None):
    with db.connect() as con:
        if mid:
            con.execute("DELETE FROM live_payments WHERE merchant_id=?", (mid,))
        else:
            con.execute("DELETE FROM live_payments")
        con.commit()


def status(mid: str) -> dict:
    with db.connect(readonly=True) as con:
        last = con.execute("SELECT MAX(ts) FROM live_payments WHERE merchant_id=?", (mid,)).fetchone()[0]
    upto = last[11:16] if last else "10:30"
    n, amt, y_n = _today_counts(mid, upto)
    return {"count_today": n, "amount_today": round(amt), "yesterday_same_time": y_n, "clock": upto,
            "next_milestone": next((x for x in MILESTONES if x > n), n + 50 - n % 50)}


if __name__ == "__main__":
    print(datetime.now(), status("m1"))
