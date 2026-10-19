"""Ask Anything: voice/chat questions answered from the merchant's own data.

Two engines:
  * "claude": Claude with tool calling (guarded SQL + feature tools). Used when ANTHROPIC_API_KEY is set.
  * "rules":  a built-in Hinglish/Hindi/English intent router with SQL templates. Always available,
              used offline and as the fallback if the API is slow or unreachable.
Every answer returns the SQL it ran and the rows it used, so the UI can show "Why?".
"""
from __future__ import annotations

import json
import re
import time
from calendar import monthrange
from datetime import date, timedelta

from .. import config, db, llm, speech, sqlguard
from ..i18n import day_name, festival_name, hour_range, inr, inr_short
from . import cashflow, festival, recon, winback

# ------------------------------------------------------------------ periods
def parse_period(q: str):
    today, y = db.today(), db.yesterday()
    ql = q.lower()
    m = re.search(r"(\d+)\s*(din|days|दिन)", ql)
    if re.search(r"\baaj\b|today|आज", ql):
        return today, today, {"hinglish": "aaj ab tak", "hi": "आज अब तक", "en": "so far today"}
    if re.search(r"\bkal\b|yesterday|कल", ql):
        return y, y, {"hinglish": "kal", "hi": "कल", "en": "yesterday"}
    if re.search(r"pich+le hafte|last week|पिछले हफ़्ते|पिछले हफ्ते|pichhla hafta|pichla hafta", ql):
        mon = today - timedelta(days=today.weekday() + 7)
        return mon, mon + timedelta(days=6), {"hinglish": "pichle hafte", "hi": "पिछले हफ़्ते", "en": "last week"}
    if re.search(r"is hafte|this week|इस हफ़्ते|इस हफ्ते", ql):
        mon = today - timedelta(days=today.weekday())
        return mon, today, {"hinglish": "is hafte", "hi": "इस हफ़्ते", "en": "this week"}
    if re.search(r"pich+le mahine|last month|पिछले महीने", ql):
        first = date(today.year, today.month, 1)
        last_prev = first - timedelta(days=1)
        return date(last_prev.year, last_prev.month, 1), last_prev, {"hinglish": "pichle mahine", "hi": "पिछले महीने", "en": "last month"}
    if re.search(r"is mahine|this month|इस महीने", ql):
        return date(today.year, today.month, 1), y, {"hinglish": "is mahine", "hi": "इस महीने", "en": "this month"}
    if m:
        n = int(m.group(1))
        return y - timedelta(days=n - 1), y, {"hinglish": f"pichle {n} din", "hi": f"पिछले {n} दिन", "en": f"the last {n} days"}
    return y - timedelta(days=6), y, {"hinglish": "pichle 7 din", "hi": "पिछले 7 दिन", "en": "the last 7 days"}


INTENTS = [
    ("lapsing", r"nahi?n? aa rahe|nahi?n? aaye|nahi?n? aate|lapsing|stopped coming|inactive|नहीं आ रहे|नहीं आए|wapas|win.?back|kho gaye"),
    ("festival", r"diwali|dhanteras|tyohar|tyohaar|festival|karwa|chhath|bhai dooj|stock|त्योहार|दिवाली|धनतेरस|स्टॉक"),
    ("loan", r"\bloan\b|credit|udhaa?r|karz|लोन|उधार|कर्ज़"),
    ("cash", r"\bcash\b|balance|paisa kam|paise kam|kharch|बैलेंस|नकद|खर्च"),
    ("failed", r"\bfail|atak|pending|फ़ेल|फेल|अटक"),
    ("settlement", r"settle|\butr\b|hisaab|सेटलमेंट|हिसाब"),
    ("peak", r"kis time|kis samay|\bkab\b|peak|bheed|busy|busiest|crowd|rush|भीड़|किस समय|व्यस्त"),
    ("top", r"\btop\b|sabse (acch?e|achh?e|pakk?e|bad[ae])|best customer|loyal|पक्के|सबसे अच्छे"),
    ("best_day", r"kaun ?sa din|which day|best day|कौन सा दिन"),
    ("sales", r"kitna|kamaya|kamai|bikri|becha|sale|revenue|earn|income|कमाया|कमाई|बिक्री|बेचा"),
]


def detect_intent(q: str) -> str:
    ql = q.lower()
    for name, pat in INTENTS:
        if re.search(pat, ql):
            return name
    return "sales"


def _say(lang, hinglish, hi, en):
    return {"hinglish": hinglish, "hi": hi, "en": en}[lang]


# ------------------------------------------------------------------ rule engine
def answer_rules(mid: str, q: str, lang: str) -> dict:
    intent = detect_intent(q)
    start, end, plabel = parse_period(q)
    pl = plabel[lang]
    sqls, data = [], None

    def run(sql):
        r = sqlguard.run(mid, sql)
        sqls.append(r["sql"])
        return r

    if intent == "sales":
        r = run(f"SELECT ROUND(SUM(amount)) AS sales, COUNT(*) AS payments, ROUND(AVG(amount)) AS avg_ticket "
                f"FROM my_payments WHERE status='SUCCESS' AND date BETWEEN '{start}' AND '{end}'")
        sales, n, avg = r["rows"][0]
        sales, n, avg = sales or 0, n or 0, avg or 0
        days = (end - start).days + 1
        pstart, pend = start - timedelta(days=days), start - timedelta(days=1)
        r2 = run(f"SELECT ROUND(SUM(amount)) FROM my_payments WHERE status='SUCCESS' AND date BETWEEN '{pstart}' AND '{pend}'")
        prev = r2["rows"][0][0] or 0
        ch = (sales - prev) / prev if prev and start != db.today() else None
        cmp = ""
        if ch is not None:
            up = ch >= 0
            cmp = _say(lang, f" Pichle utne hi dinon se {abs(ch) * 100:.0f}% {'zyada' if up else 'kam'}.",
                       f" पिछले उतने ही दिनों से {abs(ch) * 100:.0f}% {'ज़्यादा' if up else 'कम'}।",
                       f" That's {abs(ch) * 100:.0f}% {'more' if up else 'less'} than the {days} days before.")
        text = _say(lang, f"{pl.capitalize()} aapne {inr(sales)} kamaye, {n} payments se. Average bill {inr(avg)}.{cmp}",
                    f"{pl} आपने {inr(sales)} कमाए, {n} पेमेंट से। औसत बिल {inr(avg)}।{cmp}",
                    f"You made {inr(sales)} {pl} from {n} payments. Average bill {inr(avg)}.{cmp}")
        data = {"sales": sales, "payments": n, "avg_ticket": avg, "previous_period": prev}
    elif intent == "peak":
        r = run(f"SELECT hour, ROUND(SUM(amount)) AS sales, COUNT(*) AS payments FROM my_payments WHERE status='SUCCESS' "
                f"AND date BETWEEN '{start}' AND '{end}' GROUP BY hour ORDER BY hour")
        by = {h: s for h, s, _ in r["rows"]}
        best = max(range(24), key=lambda h: by.get(h, 0) + by.get(h + 1, 0))
        quiet = min((h for h in range(7, 21) if h in by), key=lambda h: by.get(h, 0) + by.get(h + 1, 0), default=best)
        text = _say(lang, f"{pl.capitalize()} sabse zyada bikri {hour_range(best, lang)} hui. Sabse shaant time {hour_range(quiet, lang)} tha.",
                    f"{pl} सबसे ज़्यादा बिक्री {hour_range(best, lang)} हुई। सबसे शांत समय {hour_range(quiet, lang)} था।",
                    f"{pl.capitalize()}, your busiest time was {hour_range(best, lang)}; the quietest was {hour_range(quiet, lang)}.")
        data = {"hourly": r["rows"]}
    elif intent == "top":
        r = run(f"SELECT payer, COUNT(DISTINCT date) AS visits, ROUND(SUM(amount)) AS spend FROM my_payments "
                f"WHERE status='SUCCESS' AND date >= date('{db.today()}', '-30 day') GROUP BY payer ORDER BY spend DESC LIMIT 5")
        top = r["rows"]
        names = ", ".join(f"{p} ({inr(s)})" for p, _, s in top[:3])
        text = _say(lang, f"Pichle 30 din ke top grahak: {names}. Sabse upar wale {top[0][1]} baar aaye.",
                    f"पिछले 30 दिन के टॉप ग्राहक: {names}। सबसे ऊपर वाले {top[0][1]} बार आए।",
                    f"Your top customers in the last 30 days: {names}. The top one came {top[0][1]} times.")
        data = {"top": top}
    elif intent == "best_day":
        r = run("SELECT CAST(strftime('%w', date) AS INT) AS dow, ROUND(SUM(amount)/COUNT(DISTINCT date)) AS avg_sales "
                f"FROM my_payments WHERE status='SUCCESS' AND date >= date('{db.today()}', '-56 day') AND date < '{db.today()}' "
                "GROUP BY dow ORDER BY avg_sales DESC")
        rows = r["rows"]
        to_py = lambda w: (w - 1) % 7  # sqlite %w: 0=Sunday
        best_d, worst_d = date(2026, 10, 12 + to_py(rows[0][0])), date(2026, 10, 12 + to_py(rows[-1][0]))
        text = _say(lang, f"Sabse accha din {day_name(best_d, lang)} hai (average {inr(rows[0][1])}), sabse halka {day_name(worst_d, lang)} ({inr(rows[-1][1])}).",
                    f"सबसे अच्छा दिन {day_name(best_d, lang)} है (औसत {inr(rows[0][1])}), सबसे हल्का {day_name(worst_d, lang)} ({inr(rows[-1][1])})।",
                    f"Your best day is {day_name(best_d, lang)} (avg {inr(rows[0][1])}); the slowest is {day_name(worst_d, lang)} ({inr(rows[-1][1])}).")
        data = {"by_weekday": rows}
    elif intent == "failed":
        r = run(f"SELECT status, COUNT(*), ROUND(SUM(amount)) FROM my_payments WHERE date BETWEEN '{start}' AND '{end}' "
                "AND status != 'SUCCESS' GROUP BY status")
        st = {s: (n, a) for s, n, a in r["rows"]}
        fn, fa = st.get("FAILED", (0, 0))
        pn, pa = st.get("PENDING", (0, 0))
        text = _say(lang, f"{pl.capitalize()} {fn} payment fail hue ({inr(fa or 0)}) aur {pn} pending hain. Fail hue payment customer ke account se nahi kate, unse dobara lijiye.",
                    f"{pl} {fn} पेमेंट फ़ेल हुए ({inr(fa or 0)}) और {pn} पेंडिंग हैं। फ़ेल हुए पेमेंट ग्राहक के खाते से नहीं कटे, उनसे दोबारा लीजिए।",
                    f"{pl.capitalize()}, {fn} payments failed ({inr(fa or 0)}) and {pn} are pending. Failed payments were not debited, so collect them again.")
        data = {"failed": fn, "failed_amount": fa, "pending": pn}
    elif intent == "lapsing":
        wb = winback.winback(mid, lang)
        sqls.append("-- RFM + k-means over my_payments (last 150 days); see winback.py")
        text = _say(lang, f"{wb['lapsing_count']} pakke grahak aajkal nahi aa rahe. Ye mahine mein lagbhag {wb['at_stake_label']} ka business dete the. Grahak tab mein ek tap mein offer bhej sakte hain.",
                    f"{wb['lapsing_count']} पक्के ग्राहक आजकल नहीं आ रहे। ये महीने में लगभग {wb['at_stake_label']} का बिज़नेस देते थे। ग्राहक टैब से एक टैप में ऑफ़र भेज सकते हैं।",
                    f"{wb['lapsing_count']} regulars have stopped coming. They were worth about {wb['at_stake_label']} a month. Send them an offer in one tap from the Customers tab.")
        data = {"lapsing": wb["lapsing"][:5], "count": wb["lapsing_count"]}
    elif intent == "festival":
        fp = festival.plan(mid, lang)
        want = next((f for f in fp["upcoming"] if f["key"].split("_")[0] in q.lower()), None)
        f = want or max(fp["upcoming"], key=lambda x: x["expected_multiplier"], default=None)
        sqls.append("-- festival calendar + your past festival uplift; see festival.py")
        if not f:
            text = _say(lang, "Agle 45 din mein koi bada tyohar nahi hai.", "अगले 45 दिन में कोई बड़ा त्योहार नहीं है।",
                        "No big festival in the next 45 days.")
        else:
            stock = ", ".join(f["stock"][:3])
            text = _say(lang, f"{f['name']} {f['days_left']} din mein hai. Bikri aam din se {f['expected_multiplier']}x tak ja sakti hai, yaani lagbhag {f['extra_sales_label']} extra. Ye stock rakhiye: {stock}.",
                        f"{f['name']} {f['days_left']} दिन में है। बिक्री आम दिन से {f['expected_multiplier']} गुना तक जा सकती है, यानी लगभग {f['extra_sales_label']} ज़्यादा। ये स्टॉक रखिए: {stock}।",
                        f"{f['name']} is {f['days_left']} days away. Sales could reach {f['expected_multiplier']}x a normal day, about {f['extra_sales_label']} extra. Stock up on: {stock}.")
        data = {"festival": f}
    elif intent == "loan":
        cr = cashflow.credit_readiness(mid)
        sqls.append("-- credit readiness from 6 months of payments & settlements; see cashflow.py")
        if cr["indicative_limit"]:
            text = _say(lang, f"Aapka Sarthi credit score {cr['score']}/100 hai. Aap lagbhag {cr['indicative_limit_label']} tak ke working-capital loan ke liye taiyaar dikhte hain. Final faisla Paytm ka lending partner karega.",
                        f"आपका सारथी क्रेडिट स्कोर {cr['score']}/100 है। आप लगभग {cr['indicative_limit_label']} तक के वर्किंग-कैपिटल लोन के लिए तैयार दिखते हैं। अंतिम फ़ैसला Paytm का लेंडिंग पार्टनर करेगा।",
                        f"Your Sarthi credit score is {cr['score']}/100, which suggests you're ready for a working-capital loan of about {cr['indicative_limit_label']}. Paytm's lending partner makes the final decision.")
        else:
            text = _say(lang, f"Aapka score {cr['score']}/100 hai. Thoda aur history banaiye.", f"आपका स्कोर {cr['score']}/100 है। थोड़ी और हिस्ट्री बनाइए।",
                        f"Your score is {cr['score']}/100. Build a little more history first.")
        data = cr
    elif intent == "cash":
        cf = cashflow.cashflow(mid)
        sqls.append("-- 30-day settlement forecast + known payments; see cashflow.py")
        low = cf["low_weeks"]
        if low:
            w = low[0]
            from ..i18n import date_label
            wk = date_label(date.fromisoformat(w["week_start"]), lang)
            text = _say(lang, f"Abhi balance {inr(cf['start_balance'])} hai. {wk} wale hafte ye {inr(w['min_balance'])} tak gir sakta hai, kyunki {', '.join(n for n, _ in w['big_outflows'])} ek saath hain.",
                        f"अभी बैलेंस {inr(cf['start_balance'])} है। {wk} वाले हफ़्ते ये {inr(w['min_balance'])} तक गिर सकता है, क्योंकि {', '.join(n for n, _ in w['big_outflows'])} एक साथ हैं।",
                        f"Your balance is {inr(cf['start_balance'])}. In the week of {wk} it may dip to {inr(w['min_balance'])} because {', '.join(n for n, _ in w['big_outflows'])} fall together.")
        else:
            text = _say(lang, f"Abhi balance {inr(cf['start_balance'])} hai, aur agle 30 din tension ki baat nahi.",
                        f"अभी बैलेंस {inr(cf['start_balance'])} है, और अगले 30 दिन चिंता की बात नहीं।",
                        f"Your balance is {inr(cf['start_balance'])}, and the next 30 days look fine.")
        data = {"low_weeks": low, "start_balance": cf["start_balance"]}
    else:  # settlement
        rc = recon.reconcile(mid)
        sqls.append("-- settlements matched to daily sales; see recon.py")
        text = _say(lang, f"Pichle 30 din ke {rc['total']} settlement mein se {rc['auto_resolved']} apne aap match ho gaye. {rc['needs_review']} ko dekhna hai.",
                    f"पिछले 30 दिन के {rc['total']} सेटलमेंट में से {rc['auto_resolved']} अपने आप मैच हो गए। {rc['needs_review']} को देखना है।",
                    f"{rc['auto_resolved']} of {rc['total']} settlements in the last 30 days matched automatically. {rc['needs_review']} need a look.")
        data = {"needs_review": [r for r in rc["rows"] if r["status"] == "review"]}
    return {"answer": text, "intent": intent, "sql": sqls, "data": data, "engine": "rules"}


# ------------------------------------------------------------------ Claude engine
TOOLS = [
    {"name": "run_sql", "description": "Run ONE read-only SQLite SELECT over the merchant's own data. " ,
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "get_lapsing_customers", "description": "Regular customers who stopped coming, with the money at stake.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_cashflow_outlook", "description": "30-day balance forecast and low-cash weeks.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_festival_plan", "description": "Upcoming festivals with expected sales multiplier and stock tips.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_credit_readiness", "description": "Credit readiness score and indicative working-capital limit.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_reconciliation", "description": "Last 30 days of settlements matched against sales.",
     "input_schema": {"type": "object", "properties": {}}},
]

LANG_RULE = {
    "hinglish": "Reply in Hinglish (Hindi words in Latin script), like a friendly shop helper.",
    "hi": "Reply in simple Hindi in Devanagari script.",
    "en": "Reply in simple Indian English.",
}


def _tool(mid, name, args, lang):
    if name == "run_sql":
        return sqlguard.run(mid, args.get("query", ""), max_rows=50)
    if name == "get_lapsing_customers":
        wb = winback.winback(mid, lang)
        return {"count": wb["lapsing_count"], "monthly_value_at_stake": wb["at_stake_monthly"], "top": wb["lapsing"][:5]}
    if name == "get_cashflow_outlook":
        cf = cashflow.cashflow(mid)
        return {"start_balance": cf["start_balance"], "safety_buffer": cf["safety_buffer"], "weeks": cf["weeks"]}
    if name == "get_festival_plan":
        return festival.plan(mid, lang)["upcoming"]
    if name == "get_credit_readiness":
        return cashflow.credit_readiness(mid)
    if name == "get_reconciliation":
        rc = recon.reconcile(mid)
        return {"counts": rc["counts"], "needs_review": [r for r in rc["rows"] if r["status"] == "review"]}
    raise ValueError(name)


def _system(mid: str, lang: str) -> str:
    m = db.merchant(mid)
    speak_rule = ("After the answer, add one final line that starts with 'SPEAK:' and repeats the same answer in "
                  "simple Hindi written in Devanagari script, with amounts as words (e.g. '1 लाख 95 हज़ार रुपये'), "
                  "so a Hindi voice can read it aloud. " if lang == "hinglish" else "")
    return (
        f"You are Dukaan Sarthi, a business copilot for {m['name']}, a small {m['category']} shop in {m['city']}, India. "
        f"{LANG_RULE[lang]} Answer in at most 3 short sentences that sound natural when spoken aloud. "
        "Always use the tools to get numbers. Never invent figures. Use ₹ with Indian digit grouping. "
        "Customer IDs (like C-1A2B3) are pseudonymous: never try to identify a person. "
        "If a question is outside the shop's data, say so briefly. " + speak_rule + "\n\n"
        + sqlguard.SCHEMA_DOC.format(today=db.today().isoformat()))


def _split_speak(text: str) -> tuple[str, str | None]:
    """Separate the optional 'SPEAK:' line (Devanagari version for the voice) from the answer."""
    if "SPEAK:" in text:
        ans, spk = text.split("SPEAK:", 1)
        return ans.strip(), spk.strip()
    return text.strip(), None


def _run_tool(mid, name, args, lang, sqls, data):
    try:
        out = _tool(mid, name, args, lang)
        sqls.append(out["sql"] if name == "run_sql" else f"-- tool: {name}")
        data.append({"tool": name, "result": out})
        return json.dumps(out, default=str)[:6000], False
    except Exception as e:  # guard errors go back to the model so it can fix the query
        return str(e), True


def answer_claude(mid: str, q: str, lang: str) -> dict:
    system = _system(mid, lang)
    msgs = [{"role": "user", "content": q}]
    sqls, data = [], []
    for _ in range(5):
        resp = llm.create(system, msgs, TOOLS)
        if resp.get("stop_reason") != "tool_use":
            text = "".join(b.get("text", "") for b in resp["content"] if b["type"] == "text")
            ans, spk = _split_speak(text)
            return {"answer": ans, "speak_override": spk, "intent": "llm", "sql": sqls, "data": data, "engine": "claude"}
        msgs.append({"role": "assistant", "content": resp["content"]})
        results = []
        for b in resp["content"]:
            if b["type"] == "tool_use":
                content, err = _run_tool(mid, b["name"], b.get("input", {}), lang, sqls, data)
                results.append({"type": "tool_result", "tool_use_id": b["id"], "content": content, "is_error": err})
        msgs.append({"role": "user", "content": results})
    raise llm.LLMError("Too many tool calls")


# Groq uses the OpenAI tool format: {"type": "function", "function": {name, description, parameters}}
OPENAI_TOOLS = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                "parameters": t["input_schema"]}} for t in TOOLS]


def answer_groq(mid: str, q: str, lang: str) -> dict:
    msgs = [{"role": "system", "content": _system(mid, lang)}, {"role": "user", "content": q}]
    sqls, data = [], []
    for _ in range(5):
        resp = llm.groq_chat(msgs, OPENAI_TOOLS)
        msg = resp["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        if not calls:
            # some Groq models (Qwen) think out loud in <think> tags: keep only the answer
            text = re.sub(r"<think>.*?</think>", "", msg.get("content") or "", flags=re.S)
            ans, spk = _split_speak(text)
            return {"answer": ans, "speak_override": spk, "intent": "llm", "sql": sqls, "data": data, "engine": "groq"}
        msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for c in calls:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            content, err = _run_tool(mid, c["function"]["name"], args, lang, sqls, data)
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": ("ERROR: " if err else "") + content})
    raise llm.LLMError("Too many tool calls")


def ask(mid: str, q: str, lang: str = "hinglish") -> dict:
    lang = lang if lang in config.LANGS else "hinglish"
    t0 = time.perf_counter()
    out = None
    prov = llm.provider()
    if prov:
        try:
            out = answer_claude(mid, q, lang) if prov == "claude" else answer_groq(mid, q, lang)
        except Exception as e:
            out = answer_rules(mid, q, lang)
            out["engine"] = "rules (fallback)"
            out["fallback_reason"] = str(e)[:200]
    if out is None:
        out = answer_rules(mid, q, lang)
    # What the voice says: Hinglish is spoken from Hindi (Devanagari) so Hindi voices pronounce it right.
    spoken = out.pop("speak_override", None)
    if not spoken and lang == "hinglish" and out["engine"].startswith("rules"):
        try:
            spoken = answer_rules(mid, q, "hi")["answer"]
        except Exception:
            spoken = None
    out["speak"] = speech.speakable(spoken or out["answer"], "en" if lang == "en" else "hi")
    out["speak_lang"] = "en" if lang == "en" else "hi"
    out["ms"] = round((time.perf_counter() - t0) * 1000)
    out["question"] = q
    out["lang"] = lang
    return out


_ = (festival_name, inr_short, monthrange)
