import { useState } from "react";
import { api, inr } from "../api.js";
import { tr } from "../i18n.js";
import { H2, Icon, Loader, useData } from "../components/common.jsx";

const SEG_COLORS = { champions: "#0E2A47", loyal: "#0068B3", at_risk: "#F2A900", occasional: "#BFD0DF" };

export default function Customers({ mid, lang }) {
  const state = useData(() => api.winback(mid, lang), [mid, lang]);
  return <Loader state={state} lang={lang}>{(w) => <Body w={w} mid={mid} lang={lang} />}</Loader>;
}

function Body({ w, mid, lang }) {
  const [sent, setSent] = useState(null);
  const [sending, setSending] = useState(false);
  const total = w.segments.reduce((a, s) => a + s.count, 0);
  const send = async () => {
    setSending(true);
    try {
      const r = await api.campaign({ merchant_id: mid, lang, segment: "lapsing", message: w.message.text, n_customers: w.lapsing_count });
      setSent(r);
    } finally { setSending(false); }
  };
  return (
    <div className="px-4 pb-6">
      <section className="mt-3 rounded-[28px] bg-ink p-5 text-white">
        <h1 className="text-2xl font-extrabold leading-tight">{tr("lapsing_title", lang)}</h1>
        <p className="mt-2 text-[17px]">
          <b className="text-4xl font-extrabold text-marigold">{w.lapsing_count}</b>
          <span className="ml-2">{lang === "en" ? "regulars" : lang === "hi" ? "पक्के ग्राहक" : "pakke grahak"}, </span>
          <b>{w.at_stake_label}</b> {tr("at_stake", lang)}
        </p>
      </section>

      <H2>{tr("offer_preview", lang)}</H2>
      <div className="rounded-2xl bg-[#DCF8C6] p-4 text-[17px] leading-snug text-[#123]">{w.message.text}</div>
      {sent ? (
        <p className="mt-3 flex items-center gap-2 rounded-xl bg-good-soft p-3 font-semibold text-good" role="status">
          <Icon name="check" className="h-5 w-5" />{tr("offer_sent", lang)} ({w.lapsing_count})
        </p>
      ) : (
        <button onClick={send} disabled={sending || !w.lapsing_count}
          className="mt-3 w-full rounded-full bg-marigold py-3.5 text-xl font-bold text-ink disabled:opacity-50">
          {tr("send_offer", lang)} ({w.lapsing_count})
        </button>
      )}
      <div className="mt-2 flex items-center justify-between gap-3">
        <p className="text-sm text-muted">{tr("privacy_note", lang)}</p>
        <a className="shrink-0 text-sm font-semibold text-sky-deep underline underline-offset-4" target="_blank" rel="noreferrer"
          href={`https://wa.me/?text=${encodeURIComponent(w.message.text)}`}>{tr("share_wa", lang)}</a>
      </div>

      <H2 aside={`${w.lapsing.length}/${w.lapsing_count}`}>{lang === "en" ? "Who they are" : lang === "hi" ? "कौन हैं" : "Kaun hain"}</H2>
      <ul className="divide-y divide-line overflow-hidden rounded-2xl bg-sheet">
        {w.lapsing.slice(0, 8).map((c) => (
          <li key={c.payer} className="flex items-center justify-between gap-3 px-4 py-3">
            <div>
              <p className="font-mono text-[15px] font-semibold">{c.payer}</p>
              <p className="text-sm text-muted">{tr("usually", lang)} {Math.round(c.usual_gap_days)} {tr("days", lang)}, {c.visits} {tr("visits", lang)}</p>
            </div>
            <div className="text-right">
              <p className="text-lg font-bold text-risk">{c.last_visit_days}</p>
              <p className="text-xs text-muted">{tr("last_visit", lang)}</p>
            </div>
          </li>
        ))}
      </ul>

      <H2>{tr("segments", lang)}</H2>
      <div className="rounded-2xl bg-sheet p-4">
        <div className="flex h-5 overflow-hidden rounded-full" role="img" aria-label="Customer segments">
          {w.segments.map((s) => <div key={s.key} style={{ width: `${(s.count / total) * 100}%`, background: SEG_COLORS[s.key] }} />)}
        </div>
        <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2">
          {w.segments.map((s) => (
            <li key={s.key} className="flex items-start gap-2">
              <span className="mt-1.5 h-3 w-3 shrink-0 rounded-full" style={{ background: SEG_COLORS[s.key] }} />
              <span><b>{s.count}</b> {s.label}<span className="block text-xs text-muted">{inr(s.avg_spend)}, {s.avg_recency} {tr("days", lang)}</span></span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs leading-snug text-muted">{w.method}</p>
      </div>
    </div>
  );
}
