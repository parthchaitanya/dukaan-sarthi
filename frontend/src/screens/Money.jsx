import { api, inr } from "../api.js";
import { tr } from "../i18n.js";
import { H2, Loader, useData } from "../components/common.jsx";
import { BalanceChart, Gauge } from "../components/charts.jsx";

export default function Money({ mid, lang }) {
  const state = useData(() => Promise.all([api.cashflow(mid), api.credit(mid)]), [mid]);
  return <Loader state={state} lang={lang}>{([cf, cr]) => <Body cf={cf} cr={cr} lang={lang} />}</Loader>;
}

const fmtDate = (d, lang) => new Date(d).toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", { day: "numeric", month: "short" });

function Body({ cf, cr, lang }) {
  return (
    <div className="px-4 pb-6">
      <section className="mt-3 rounded-[28px] bg-sheet p-5 shadow-[0_1px_0_#D6E0E9]">
        <p className="text-sm text-muted">{tr("balance_now", lang)}</p>
        <p className="text-4xl font-extrabold tracking-tight">{inr(cf.start_balance)}</p>
        <p className="mt-1 text-sm text-muted">{tr("safe_limit", lang)}: {inr(cf.safety_buffer)}</p>
        <div className="mt-3">
          <BalanceChart history={cf.history} days={cf.days} buffer={cf.safety_buffer} label={tr("balance_path", lang)}
            todayLabel={lang === "en" ? "today" : lang === "hi" ? "आज" : "aaj"} />
          <p className="text-xs text-muted">{tr("balance_path", lang)}. — — {tr("forecast", lang)}</p>
        </div>
      </section>

      <H2>{tr("tight_weeks", lang)}</H2>
      {cf.low_weeks.length === 0 ? (
        <p className="rounded-2xl bg-good-soft p-4 font-semibold text-good">{tr("no_tight", lang)}</p>
      ) : (
        <ul className="space-y-2">
          {cf.low_weeks.map((w) => (
            <li key={w.week_start} className={`rounded-2xl p-4 ${w.risk === "red" ? "bg-risk-soft" : "bg-marigold-soft"}`}>
              <div className="flex items-baseline justify-between">
                <p className="text-lg font-bold">{lang === "en" ? `${tr("week_of", lang)} ${fmtDate(w.week_start, lang)}` : `${fmtDate(w.week_start, lang)} ${tr("week_of", lang)}`}</p>
                <p className={`text-sm font-bold ${w.risk === "red" ? "text-risk" : "text-[#8A5A00]"}`}>{tr(w.risk, lang)}</p>
              </div>
              <p className="text-[17px]"><b>{inr(w.min_balance)}</b> {tr("may_dip", lang)}</p>
              <p className="mt-1 text-sm text-muted">{w.big_outflows.map(([n, a]) => `${n} ${inr(a)}`).join(", ")}</p>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 px-1 text-sm text-muted">
        {tr("next30", lang)}: +{inr(cf.next30_inflow)} / −{inr(cf.next30_outflow)}
      </p>

      <H2>{tr("credit_title", lang)}</H2>
      <section className="rounded-2xl bg-sheet p-4">
        <div className="flex items-center gap-4">
          <Gauge score={cr.score} />
          <div>
            <p className="text-lg font-bold">{cr.band}</p>
            {cr.indicative_limit > 0 && (
              <p className="text-[15px] leading-snug"><b className="text-2xl">{cr.indicative_limit_label}</b><br />{tr("indicative", lang)}</p>
            )}
          </div>
        </div>
        <ul className="mt-4 space-y-2.5">
          {cr.parts.map((p) => (
            <li key={p.key}>
              <div className="flex justify-between text-[15px]"><span className="font-semibold">{p.label}</span><span className="text-muted">{p.detail}</span></div>
              <div className="mt-1 h-2 rounded-full bg-line"><div className="h-2 rounded-full bg-sky-deep" style={{ width: `${p.value * 100}%` }} /></div>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-muted">{cr.note}</p>
      </section>
    </div>
  );
}
