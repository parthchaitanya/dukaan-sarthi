import { useState } from "react";
import { api, inr } from "../api.js";
import { tr } from "../i18n.js";
import { H2, Loader, useData, Why } from "../components/common.jsx";

export default function Plan({ mid, lang }) {
  const state = useData(() => Promise.all([api.festival(mid, lang), api.recon(mid)]), [mid, lang]);
  return <Loader state={state} lang={lang}>{([fp, rc]) => <Body fp={fp} rc={rc} lang={lang} />}</Loader>;
}

function Body({ fp, rc, lang }) {
  const maxMult = Math.max(...fp.upcoming.map((f) => f.expected_multiplier), 2);
  return (
    <div className="px-4 pb-6">
      <h1 className="mt-4 text-2xl font-extrabold">{tr("festivals", lang)}</h1>
      <p className="px-1 text-sm text-muted">{tr("normal_day", lang)}: {fp.normal_day_label}</p>
      <ul className="mt-3 space-y-3">
        {fp.upcoming.map((f, i) => (
          <li key={f.key} className={`rounded-2xl p-4 ${i === 0 && f.days_left <= 1 ? "bg-sheet" : "bg-sheet"} shadow-[0_1px_0_#D6E0E9]`}>
            <div className="flex items-baseline justify-between gap-2">
              <h3 className="text-xl font-bold">{f.name}</h3>
              <p className="text-sm text-muted">{f.days_left === 0 ? (lang === "en" ? "today" : lang === "hi" ? "आज" : "aaj") : `${f.days_left} ${tr("days_left", lang)}`}</p>
            </div>
            <div className="mt-2 flex items-center gap-3">
              <div className="h-3 flex-1 rounded-full bg-line">
                <div className="h-3 rounded-full bg-marigold" style={{ width: `${(f.expected_multiplier / maxMult) * 100}%` }} />
              </div>
              <span className="w-16 text-right text-lg font-extrabold">{f.expected_multiplier}x</span>
            </div>
            <p className="mt-1 text-[15px]">{f.extra_sales_label} {tr("extra_sales", lang)}</p>
            {f.stock.length > 0 && <p className="mt-2 text-[15px]"><b>{tr("stock_up", lang)}:</b> {f.stock.join(", ")}</p>}
            {f.staff && <p className="text-[15px] text-muted">{f.staff}</p>}
            <Why lang={lang}>{f.why}</Why>
          </li>
        ))}
      </ul>

      {fp.past.length > 0 && (
        <>
          <H2>{tr("past_fest", lang)}</H2>
          <ul className="divide-y divide-line rounded-2xl bg-sheet">
            {fp.past.map((p) => (
              <li key={p.key} className="flex justify-between px-4 py-2.5 text-[16px]">
                <span>{p.name}</span><b>{p.your_uplift}x</b>
              </li>
            ))}
          </ul>
        </>
      )}

      <H2>{tr("recon_title", lang)}</H2>
      <div className="grid grid-cols-3 gap-2 text-center">
        <Stat n={rc.counts.matched || 0} label={tr("matched", lang)} tone="good" />
        <Stat n={(rc.counts.explained || 0) + (rc.counts.awaiting || 0)} label={tr("explained", lang)} tone="ink" />
        <Stat n={rc.needs_review} label={tr("review", lang)} tone={rc.needs_review ? "risk" : "ink"} />
      </div>
      {rc.needs_review === 0 && <p className="mt-2 text-good">{tr("all_matched", lang)}</p>}
      <ul className="mt-3 space-y-2">
        {rc.rows.filter((r) => r.status === "review").map((r) => <ReviewRow key={r.business_date} r={r} lang={lang} />)}
        {rc.rows.filter((r) => r.status === "explained").slice(0, 3).map((r) => (
          <li key={r.business_date} className="rounded-2xl bg-sheet p-3 text-[15px]">
            <b>{r.business_date}</b>: {r.explanation}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Stat({ n, label, tone }) {
  const c = { good: "text-good", risk: "text-risk", ink: "text-ink" }[tone];
  return <div className="rounded-2xl bg-sheet py-3"><p className={`text-3xl font-extrabold ${c}`}>{n}</p><p className="text-sm text-muted">{label}</p></div>;
}

function ReviewRow({ r, lang }) {
  const [copied, setCopied] = useState(false);
  return (
    <li className="rounded-2xl bg-risk-soft p-4">
      <p className="font-bold">{r.business_date}: {inr(r.gap)} short</p>
      <p className="text-[15px] leading-snug">{r.explanation}</p>
      {r.dispute_draft && (
        <details className="mt-2">
          <summary className="cursor-pointer text-sm font-semibold text-sky-deep">Draft</summary>
          <pre className="mt-1 whitespace-pre-wrap rounded-lg bg-sheet p-3 text-[13px] leading-snug">{r.dispute_draft}</pre>
        </details>
      )}
      <button onClick={async () => { try { await navigator.clipboard.writeText(r.dispute_draft); setCopied(true); } catch {} }}
        className="mt-2 rounded-full bg-ink px-4 py-1.5 text-sm font-bold text-white">
        {copied ? tr("copied", lang) : tr("copy_dispute", lang)}
      </button>
    </li>
  );
}
