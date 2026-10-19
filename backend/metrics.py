"""Evaluation of the demo on the synthetic pilot (5 merchant personas, ~6 months).

Everything here is measured against the generator's hidden ground truth or by backtesting
on held-out data. It is evidence that the methods work on realistic data, not field results.

Run:  python -m backend.metrics
"""
from __future__ import annotations

import json
import statistics
import time
import warnings
from datetime import datetime

from . import config, db
from .features import ask, cashflow, recon, winback

warnings.filterwarnings("ignore")

# A small labelled test set for the offline intent router (question, lang, expected intent).
ASK_TESTS = [
    ("Pichle hafte kitna kamaya?", "hinglish", "sales"), ("aaj kitni bikri hui", "hinglish", "sales"),
    ("is mahine ka total sale kitna hai", "hinglish", "sales"), ("कल कितना कमाया?", "hi", "sales"),
    ("पिछले महीने की बिक्री बताओ", "hi", "sales"), ("How much did I earn last week?", "en", "sales"),
    ("Kaun se customer nahi aa rahe?", "hinglish", "lapsing"), ("purane grahak wapas kaise laun", "hinglish", "lapsing"),
    ("कौन से ग्राहक नहीं आ रहे?", "hi", "lapsing"), ("Which regulars stopped coming?", "en", "lapsing"),
    ("Diwali pe kya stock rakhun?", "hinglish", "festival"), ("tyohar ki taiyari kaise karein", "hinglish", "festival"),
    ("दिवाली पर क्या स्टॉक रखूँ?", "hi", "festival"), ("What should I stock for Dhanteras?", "en", "festival"),
    ("mujhe loan mil sakta hai kya", "hinglish", "loan"), ("क्या मुझे लोन मिलेगा?", "hi", "loan"),
    ("Am I eligible for credit?", "en", "loan"), ("balance kab kam hoga", "hinglish", "cash"),
    ("agle mahine paisa kam to nahi padega", "hinglish", "cash"), ("Will my cash balance be enough next month?", "en", "cash"),
    ("kal kitne payment fail hue", "hinglish", "failed"), ("कल कितने पेमेंट फ़ेल हुए?", "hi", "failed"),
    ("Any pending payments?", "en", "failed"), ("settlement sahi aaya kya", "hinglish", "settlement"),
    ("is hafte ka hisaab dikhao", "hinglish", "settlement"), ("Did all my settlements match?", "en", "settlement"),
    ("dukaan mein sabse zyada bheed kab hoti hai", "hinglish", "peak"), ("किस समय सबसे ज़्यादा भीड़ होती है?", "hi", "peak"),
    ("When is my shop busiest?", "en", "peak"), ("mere sabse pakke grahak kaun hain", "hinglish", "top"),
    ("Who are my top customers?", "en", "top"), ("kaunsa din sabse accha hai", "hinglish", "best_day"),
    ("Which day of the week is best?", "en", "best_day"),
]


def compute() -> dict:
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "demo_today": config.DEMO_TODAY.isoformat(),
           "merchants": db.merchants(), "per_merchant": {}}
    # 1. lapsing-regular detection vs ground truth
    tp = found = truth_n = 0
    for m in db.merchants():
        mid = m["id"]
        lap = set(winback.lapsing_regulars(mid).index)
        t = db.df("SELECT payer FROM _truth_customers WHERE merchant_id=? AND kind='regular_lapsed'", (mid,))
        truth = set(t["payer"])
        tp_m = len(lap & truth)
        tp, found, truth_n = tp + tp_m, found + len(lap), truth_n + len(truth)
        out["per_merchant"].setdefault(mid, {})["winback"] = {"found": len(lap), "true_lapsed": len(truth), "correct": tp_m}
    out["winback"] = {"found": found, "true_lapsed": truth_n, "correct": tp,
                      "recall": round(tp / truth_n, 3), "precision": round(tp / found, 3)}

    # 2. sales forecast accuracy (30-day holdout) vs seasonal-naive baseline
    num = den = num_naive = 0.0
    for m in db.merchants():
        b = cashflow.backtest_forecast(m["id"])
        num += b["abs_err"]
        num_naive += b["abs_err_naive"]
        den += b["actual"]
        out["per_merchant"][m["id"]]["forecast"] = {k: round(v, 3) if isinstance(v, float) else v for k, v in b.items()}
    out["forecast"] = {"wape": round(num / den, 3), "wape_naive": round(num_naive / den, 3),
                       "improvement": round(1 - num / num_naive, 3)}

    # 3. low-cash weeks warned 8-14 days ahead
    lt = lf = lfn = lweeks = 0
    for m in db.merchants():
        weeks = cashflow.backtest_low_cash(m["id"])["weeks"]
        a = sum(w["flagged"] and w["actual_low"] for w in weeks)
        f = sum(w["flagged"] and not w["actual_low"] for w in weeks)
        n = sum((not w["flagged"]) and w["actual_low"] for w in weeks)
        lt, lf, lfn, lweeks = lt + a, lf + f, lfn + n, lweeks + len(weeks)
        out["per_merchant"][m["id"]]["low_cash"] = {"caught": a, "false_alarms": f, "missed": n, "weeks": len(weeks)}
    out["low_cash"] = {"actual_low_weeks": lt + lfn, "caught": lt, "false_alarms": lf, "missed": lfn,
                       "weeks_tested": lweeks, "normal_weeks": lweeks - lt - lfn}

    # 4. reconciliation over the full history
    tot = review = 0
    caught = injected = false_review = 0
    for m in db.merchants():
        mid = m["id"]
        r = recon.reconcile(mid, days=config.HISTORY_DAYS - 1, end=db.yesterday() - __import__("datetime").timedelta(days=2))
        truth = db.df("SELECT settlement_id, anomaly FROM _truth_recon WHERE merchant_id=?", (mid,))
        bad = set(truth.loc[truth.anomaly.isin(["missing_txn", "chargeback"]), "settlement_id"])
        flagged = {x.get("settlement_id") for x in r["rows"] if x["status"] == "review"}
        tot += r["total"]
        review += r["needs_review"]
        injected += len(bad)
        caught += len(bad & flagged)
        false_review += len(flagged - bad)
    out["reconciliation"] = {"settlements": tot, "needs_review": review, "auto_resolved": tot - review,
                             "manual_share": round(review / tot, 3), "shortfalls_injected": injected,
                             "shortfalls_caught": caught, "false_reviews": false_review}

    # 5. Ask Anything (offline engine): intent accuracy + latency
    correct, lat = 0, []
    for q, lang, want in ASK_TESTS:
        t0 = time.perf_counter()
        r = ask.answer_rules("m1", q, lang)
        lat.append((time.perf_counter() - t0) * 1000)
        correct += r["intent"] == want
    lat.sort()
    out["ask"] = {"questions": len(ASK_TESTS), "intent_correct": correct,
                  "p50_ms": round(statistics.median(lat)), "p95_ms": round(lat[int(0.95 * (len(lat) - 1))])}

    # 6. privacy check: no raw payer handles stored
    raw = db.df("SELECT COUNT(*) n FROM payments WHERE payer LIKE '%@%'")["n"].iloc[0]
    out["privacy"] = {"raw_payer_ids_stored": int(raw), "payer_id_format": "C-xxxxx (salted SHA-1 prefix)"}
    return out


def load(refresh: bool = False) -> dict:
    if not refresh and config.METRICS_CACHE.exists():
        return json.loads(config.METRICS_CACHE.read_text())
    data = compute()
    config.METRICS_CACHE.write_text(json.dumps(data, indent=2, default=str))
    return data


if __name__ == "__main__":
    print(json.dumps({k: v for k, v in load(refresh=True).items() if k not in ("per_merchant", "merchants")}, indent=2))
