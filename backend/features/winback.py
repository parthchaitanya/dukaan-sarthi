"""Customer Win-back Engine: RFM + k-means segments, lapsing-regular detection, and offer messages."""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from .. import db
from ..i18n import inr

LOOKBACK_DAYS = 150

OFFERS = {
    "kirana": {"code": "WAPSI20", "hinglish": "₹200 ki kharidari par ₹20 ki chhoot", "hi": "₹200 की ख़रीदारी पर ₹20 की छूट",
               "en": "₹20 off on a ₹200+ purchase"},
    "salon": {"code": "GLOW15", "hinglish": "agli service par 15% off", "hi": "अगली सर्विस पर 15% छूट",
              "en": "15% off your next service"},
    "cafe": {"code": "CHAI1", "hinglish": "kisi bhi snack ke saath ek chai free", "hi": "किसी भी स्नैक के साथ एक चाय मुफ़्त",
             "en": "a free chai with any snack"},
    "pharmacy": {"code": "SEHAT5", "hinglish": "dawai par 5% off aur free BP check", "hi": "दवाई पर 5% छूट और मुफ़्त BP जाँच",
                 "en": "5% off medicines and a free BP check"},
    "sweets": {"code": "MITHAAS50", "hinglish": "1 kg mithai par ₹50 off", "hi": "1 किलो मिठाई पर ₹50 की छूट",
               "en": "₹50 off on 1 kg of sweets"},
}

MSG = {
    "hinglish": "Namaste! 🙏 {shop} mein aapki kami mehsoos ho rahi hai. Is hafte aaiye, aapke liye {offer}. Code: {code}",
    "hi": "नमस्ते! 🙏 {shop} में आपकी कमी महसूस हो रही है। इस हफ़्ते आइए, आपके लिए {offer}। कोड: {code}",
    "en": "Hello! 🙏 We've missed you at {shop}. Drop by this week for {offer}. Code: {code}",
}

SEGMENT_LABELS = {
    "champions": {"hinglish": "Pakke grahak", "hi": "पक्के ग्राहक", "en": "Champions"},
    "loyal": {"hinglish": "Niyamit grahak", "hi": "नियमित ग्राहक", "en": "Loyal"},
    "at_risk": {"hinglish": "Door ho rahe", "hi": "दूर हो रहे", "en": "At risk"},
    "occasional": {"hinglish": "Kabhi-kabhi wale", "hi": "कभी-कभी वाले", "en": "Occasional"},
}


def rfm(mid: str) -> pd.DataFrame:
    end = db.yesterday()
    start = end - timedelta(days=LOOKBACK_DAYS)
    p = db.df("SELECT date, amount, payer FROM payments WHERE merchant_id=? AND status='SUCCESS' AND date BETWEEN ? AND ?",
              (mid, start.isoformat(), end.isoformat()))
    p["date"] = pd.to_datetime(p["date"])
    g = p.groupby("payer")
    out = pd.DataFrame({
        "last": g["date"].max(),
        "first": g["date"].min(),
        "visits": g["date"].nunique(),
        "spend": g["amount"].sum(),
    })
    out["recency"] = (pd.Timestamp(end) - out["last"]).dt.days
    # typical gap between visits (span between first and last visit / number of gaps)
    span = (out["last"] - out["first"]).dt.days
    out["median_gap"] = (span / (out["visits"] - 1).clip(lower=1)).where(out["visits"] > 2)
    return out


def segment(mid: str) -> pd.DataFrame:
    r = rfm(mid)
    r = r[r["visits"] >= 2].copy()  # one-time walk-ins are not a segment to win back
    X = np.column_stack([np.log1p(r["recency"]), np.log1p(r["visits"]), np.log1p(r["spend"])])
    Xs = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=4, n_init=10, random_state=0).fit(Xs)
    r["cluster"] = km.labels_
    # Name clusters from their centroids so labels are stable across runs.
    c = pd.DataFrame(km.cluster_centers_, columns=["r", "f", "m"])
    c["score"] = c["f"] + c["m"] - c["r"]
    order = c.sort_values("score", ascending=False).index.tolist()
    names = {}
    names[order[0]] = "champions"
    rest = order[1:]
    # among the rest: the one with highest recency (long gone) but decent frequency is "at_risk"
    at_risk = max(rest, key=lambda k: c.loc[k, "r"] + 0.5 * c.loc[k, "f"])
    names[at_risk] = "at_risk"
    remaining = [k for k in rest if k != at_risk]
    remaining.sort(key=lambda k: c.loc[k, "f"], reverse=True)
    names[remaining[0]] = "loyal"
    names[remaining[1]] = "occasional"
    r["segment"] = r["cluster"].map(names)
    return r


def lapsing_regulars(mid: str) -> pd.DataFrame:
    """Regulars whose silence is unusual for *them*: they came often, and now it's been
    much longer than their normal gap."""
    r = rfm(mid)
    reg = r[(r["visits"] >= 6) & (r["median_gap"] <= 12)].copy()
    reg["threshold"] = np.maximum(14, 4 * reg["median_gap"])
    lap = reg[reg["recency"] > reg["threshold"]].copy()
    lap["why"] = lap.apply(lambda x: f"Used to come every ~{x.median_gap:.0f} days; last visit {x.recency:.0f} days ago",
                           axis=1)
    return lap.sort_values("spend", ascending=False)


def message(mid: str, lang: str) -> dict:
    m = db.merchant(mid)
    o = OFFERS[m["category"]]
    text = MSG[lang].format(shop=m["name"], offer=o[lang], code=o["code"])
    return {"text": text, "code": o["code"]}


def winback(mid: str, lang: str = "hinglish") -> dict:
    seg = segment(mid)
    lap = lapsing_regulars(mid)
    counts = seg["segment"].value_counts().to_dict()
    summary = []
    for key in ("champions", "loyal", "at_risk", "occasional"):
        s = seg[seg["segment"] == key]
        summary.append({
            "key": key, "label": SEGMENT_LABELS[key][lang], "count": int(counts.get(key, 0)),
            "avg_spend": round(float(s["spend"].mean()) if len(s) else 0),
            "avg_recency": round(float(s["recency"].mean()) if len(s) else 0),
        })
    monthly_value = 0.0
    rows = []
    for payer, x in lap.head(25).iterrows():
        per_visit = x.spend / x.visits
        monthly = per_visit * 30 / max(x.median_gap, 1)
        monthly_value += monthly
        rows.append({"payer": payer, "visits": int(x.visits), "spend": round(float(x.spend)),
                     "last_visit_days": int(x.recency), "usual_gap_days": float(x.median_gap),
                     "monthly_value": round(monthly), "why": x.why})
    total_monthly = sum(
        (x.spend / x.visits) * 30 / max(x.median_gap, 1) for _, x in lap.iterrows())
    min_days = int(lap["recency"].min()) if len(lap) else 0
    return {
        "segments": summary,
        "lapsing": rows,
        "lapsing_count": int(len(lap)),
        "lapsing_min_days": min_days,
        "at_stake_monthly": round(total_monthly),
        "at_stake_label": inr(total_monthly),
        "message": message(mid, lang),
        "method": "RFM (recency, frequency, spend) over 150 days + k-means (k=4). A regular is 'lapsing' when "
                  "their silence is over 4x their own usual gap between visits (min 14 days).",
    }
