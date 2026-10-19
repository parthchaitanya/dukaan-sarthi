"""Core tests. Run with:  python -m pytest -q   (or  python tests/test_core.py  without pytest)."""
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

from backend import config, db, sqlguard  # noqa: E402
from backend.features import ask, brief, cashflow, festival, recon, winback  # noqa: E402
from backend.i18n import inr  # noqa: E402

if not config.DB_PATH.exists():
    from backend import seed
    seed.generate()


def test_inr_grouping():
    assert inr(123456) == "₹1,23,456"
    assert inr(999) == "₹999"
    assert inr(-10500) == "−₹10,500"
    assert inr(12345678) == "₹1,23,45,678"


def test_sql_guard_blocks_writes_and_other_tables():
    for bad in ["DELETE FROM payments", "select * from payments", "select * from _truth_customers",
                "select 1; drop table payments", "select * from merchants", "select name from sqlite_master",
                "with x as (select * from payments) select * from x", "PRAGMA table_info(payments)"]:
        try:
            sqlguard.run("m1", bad)
        except sqlguard.SQLGuardError:
            continue
        raise AssertionError(f"guard allowed: {bad}")


def test_sql_guard_scopes_to_merchant():
    a = sqlguard.run("m1", "select count(*) from my_payments")["rows"][0][0]
    b = sqlguard.run("m2", "select count(*) from my_payments")["rows"][0][0]
    total = db.df("select count(*) n from payments where merchant_id in ('m1','m2')")["n"].iloc[0]
    assert a + b == total and a != b


def test_no_raw_payer_ids():
    assert db.df("select count(*) n from payments where payer like '%@%'")["n"].iloc[0] == 0


def test_brief_all_languages():
    for lang in config.LANGS:
        b = brief.brief("m1", lang)
        assert b["speech"] and len(b["actions"]) == 2
        assert b["sales"] > 0


def test_brief_flags_injected_failure_spike():
    assert brief.brief("m1", "en")["anomalies"], "the generator injects a failure spike for m1 yesterday"


def test_ask_rules_intents():
    cases = {"Pichle hafte kitna kamaya?": "sales", "Kaun se customer nahi aa rahe?": "lapsing",
             "Diwali pe kya stock rakhun?": "festival", "क्या मुझे लोन मिलेगा?": "loan",
             "When is my shop busiest?": "peak"}
    for q, intent in cases.items():
        r = ask.ask("m1", q, "hinglish")
        assert r["intent"] == intent, (q, r["intent"])
        assert r["answer"] and r["sql"]


def test_winback_recall_reasonable():
    lap = set(winback.lapsing_regulars("m1").index)
    truth = set(db.df("select payer from _truth_customers where merchant_id='m1' and kind='regular_lapsed'")["payer"])
    assert len(lap & truth) / len(truth) >= 0.7


def test_recon_catches_recent_shortfall():
    r = recon.reconcile("m1")
    assert r["needs_review"] >= 1
    assert any(x.get("dispute_draft") for x in r["rows"] if x["status"] == "review")


def test_cashflow_and_credit():
    cf = cashflow.cashflow("m1")
    assert len(cf["days"]) == cashflow.HORIZON
    cr = cashflow.credit_readiness("m1")
    assert 0 <= cr["score"] <= 100


def test_forecast_beats_naive_baseline():
    bt = cashflow.backtest_forecast("m5")
    assert bt["wape"] < bt["wape_naive"]


def test_festival_plan_has_diwali():
    assert any(f["key"] == "diwali" for f in festival.plan("m5")["upcoming"])


if __name__ == "__main__":
    fns = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for f in fns:
        f()
        print("ok ", f.__name__)
    print(f"{len(fns)} passed")
