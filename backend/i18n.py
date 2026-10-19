"""Language helpers: Hinglish (default), Hindi (Devanagari) and English.

Every user-facing sentence the app produces without an LLM comes from here, so the
demo works offline and the wording is predictable.
"""
from __future__ import annotations

from datetime import date

HI_DAYS = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
HG_DAYS = ["Somvaar", "Mangalvaar", "Budhvaar", "Guruvaar", "Shukravaar", "Shanivaar", "Ravivaar"]
EN_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
HI_MONTHS = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
EN_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

FESTIVAL_HI = {
    "Independence Day": "स्वतंत्रता दिवस", "Raksha Bandhan": "रक्षा बंधन", "Janmashtami": "जन्माष्टमी",
    "Ganesh Chaturthi": "गणेश चतुर्थी", "Navratri": "नवरात्रि", "Dussehra": "दशहरा", "Karwa Chauth": "करवा चौथ",
    "Dhanteras": "धनतेरस", "Diwali": "दिवाली", "Bhai Dooj": "भाई दूज", "Chhath Puja": "छठ पूजा", "Christmas": "क्रिसमस",
}


def inr(x: float) -> str:
    """Indian digit grouping: 123456 -> ₹1,23,456."""
    neg = x < 0
    n = int(round(abs(x)))
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("−₹" if neg else "₹") + s


def inr_short(x: float, lang: str = "hinglish") -> str:
    """Spoken-friendly amounts: ₹1.2 lakh, ₹45 hazaar."""
    a = abs(x)
    if a >= 100000:
        v = f"{a / 100000:.1f}".rstrip("0").rstrip(".")
        unit = {"hi": "लाख", "en": "lakh"}.get(lang, "lakh")
        return f"₹{v} {unit}"
    if a >= 1000 and lang != "en":
        v = f"{a / 1000:.1f}".rstrip("0").rstrip(".")
        return f"₹{v} " + ("हज़ार" if lang == "hi" else "hazaar")
    return inr(x)


def day_name(d: date, lang: str) -> str:
    return {"hi": HI_DAYS, "en": EN_DAYS}.get(lang, HG_DAYS)[d.weekday()]


def date_label(d: date, lang: str) -> str:
    if lang == "hi":
        return f"{d.day} {HI_MONTHS[d.month - 1]}"
    return f"{d.day} {EN_MONTHS[d.month - 1]}"


def festival_name(name: str, lang: str) -> str:
    return FESTIVAL_HI.get(name, name) if lang == "hi" else name


def _fmt_hour(x: int) -> str:
    x = x % 24
    return f"{x % 12 or 12}{'am' if x < 12 else 'pm'}"


def hour_span(h0: int, h1: int, lang: str) -> str:
    """From hour h0 to hour h1 (exclusive end), e.g. 13, 16 -> '1pm se 4pm'."""
    a, b = _fmt_hour(h0), _fmt_hour(h1)
    if lang == "hi":
        part = "सुबह" if h0 < 12 else ("दोपहर" if h0 < 16 else ("शाम" if h0 < 20 else "रात"))
        return f"{part} {h0 % 12 or 12} से {h1 % 12 or 12} बजे"
    if lang == "en":
        return f"{a}–{b}"
    return f"{a} se {b}"


def hour_range(h: int, lang: str) -> str:
    return hour_span(h, h + 2, lang)


def pct(change: float) -> str:
    return f"{abs(change) * 100:.0f}%"


# ---- template table: key -> {lang: template} --------------------------------------
T = {
    "greet": {
        "hinglish": "Namaste {owner} ji! Main hoon aapka Dukaan Sarthi.",
        "hi": "नमस्ते {owner} जी! मैं हूँ आपका दुकान सारथी।",
        "en": "Good morning, {owner}! This is your Dukaan Sarthi.",
    },
    "sales_up": {
        "hinglish": "Kal ki bikri {amt} rahi, pichle {day} se {pct} zyada.",
        "hi": "कल की बिक्री {amt} रही, पिछले {day} से {pct} ज़्यादा।",
        "en": "Yesterday you sold {amt}, {pct} more than last {day}.",
    },
    "sales_down": {
        "hinglish": "Kal ki bikri {amt} rahi, pichle {day} se {pct} kam.",
        "hi": "कल की बिक्री {amt} रही, पिछले {day} से {pct} कम।",
        "en": "Yesterday you sold {amt}, {pct} less than last {day}.",
    },
    "sales_flat": {
        "hinglish": "Kal ki bikri {amt} rahi, pichle {day} jitni hi.",
        "hi": "कल की बिक्री {amt} रही, पिछले {day} जितनी ही।",
        "en": "Yesterday you sold {amt}, about the same as last {day}.",
    },
    "txns_peak": {
        "hinglish": "{n} payments aaye, sabse zyada bheed {hours} thi.",
        "hi": "{n} पेमेंट आए, सबसे ज़्यादा भीड़ {hours} थी।",
        "en": "{n} payments came in; your busiest time was {hours}.",
    },
    "top_customer": {
        "hinglish": "Aapke sabse pakke grahak {payer} is mahine {visits} baar aaye.",
        "hi": "आपके सबसे पक्के ग्राहक {payer} इस महीने {visits} बार आए।",
        "en": "Your most loyal customer, {payer}, visited {visits} times this month.",
    },
    "anomaly_failed": {
        "hinglish": "Dhyan dijiye: {hours} ke beech {n} payment fail hue, aam din se kaafi zyada. Shayad bank ki dikkat thi.",
        "hi": "ध्यान दीजिए: {hours} के बीच {n} पेमेंट फ़ेल हुए, आम दिन से काफ़ी ज़्यादा। शायद बैंक की दिक्कत थी।",
        "en": "Heads up: {n} payments failed between {hours}, far more than usual. Likely a bank-side issue.",
    },
    "actions_intro": {
        "hinglish": "Aaj ke do kaam:",
        "hi": "आज के दो काम:",
        "en": "Two things to do today:",
    },
    "act_winback": {
        "hinglish": "{n} pakke grahak {days}+ din se nahi aaye. Unhe ek offer bhejiye.",
        "hi": "{n} पक्के ग्राहक {days}+ दिन से नहीं आए। उन्हें एक ऑफ़र भेजिए।",
        "en": "{n} regular customers haven't come in {days}+ days. Send them an offer.",
    },
    "act_festival": {
        "hinglish": "{fest} {days} din mein hai. Us din bikri aam din se {mult}x tak ja sakti hai. Stock abhi order kijiye.",
        "hi": "{fest} {days} दिन में है। बिक्री {mult} गुना तक जा सकती है। स्टॉक अभी ऑर्डर कीजिए।",
        "en": "{fest} is {days} days away and sales could reach {mult}x a normal day. Order stock now.",
    },
    "act_cash": {
        "hinglish": "{week} wale hafte balance {amt} tak gir sakta hai, aapki safe limit se neeche. Kharche aage-peeche kijiye ya chhota loan dekhiye.",
        "hi": "{week} वाले हफ़्ते बैलेंस {amt} तक गिर सकता है, आपकी सुरक्षित सीमा से नीचे। खर्चे आगे-पीछे कीजिए या छोटा लोन देखिए।",
        "en": "Your balance may dip to {amt} in the week of {week}, below your safe limit. Shift a payment or check a small loan.",
    },
    "act_failed": {
        "hinglish": "Kal fail hue payments wale grahakon se dobara payment lijiye, aur settlement check kijiye.",
        "hi": "कल फ़ेल हुए पेमेंट वाले ग्राहकों से दोबारा पेमेंट लीजिए, और सेटलमेंट चेक कीजिए।",
        "en": "Collect the failed payments from yesterday again, and check your settlement.",
    },
    "act_peak": {
        "hinglish": "Aaj {hours} sabse busy rahega. Us time counter par ek aur aadmi rakhiye.",
        "hi": "आज {hours} सबसे व्यस्त रहेगा। उस समय काउंटर पर एक और आदमी रखिए।",
        "en": "Today {hours} will be busiest. Keep an extra hand at the counter then.",
    },
    "close": {
        "hinglish": "Aapka din shubh ho!",
        "hi": "आपका दिन शुभ हो!",
        "en": "Have a great day!",
    },
}


NAMES_HI = {"Ramesh": "रमेश", "Pooja": "पूजा", "Aman": "अमन", "Sunil": "सुनील", "Kavita": "कविता"}


def first_name(owner: str, lang: str) -> str:
    n = owner.split()[0]
    return NAMES_HI.get(n, n) if lang == "hi" else n


def t(key: str, lang: str, **kw) -> str:
    lang = lang if lang in ("hinglish", "hi", "en") else "hinglish"
    return T[key][lang].format(**kw)
