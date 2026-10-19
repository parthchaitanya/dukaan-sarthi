import { api } from "../api.js";
import { Loader, useData } from "../components/common.jsx";

const pct = (x) => `${(x * 100).toFixed(0)}%`;

export default function Metrics() {
  const state = useData(() => api.metrics(), []);
  return (
    <main className="mx-auto max-w-3xl px-5 py-10 text-ink">
      <a href="#/" className="text-sm font-semibold text-sky-deep underline underline-offset-4">Back to the app</a>
      <Loader state={state} lang="en">{(m) => <Body m={m} />}</Loader>
    </main>
  );
}

function Row({ big, title, detail }) {
  return (
    <div className="grid grid-cols-[150px_1fr] gap-5 border-t border-line py-5 sm:grid-cols-[200px_1fr]">
      <p className="text-4xl font-extrabold leading-none tracking-tight text-sky-deep sm:text-5xl">{big}</p>
      <div>
        <h3 className="text-xl font-bold leading-tight">{title}</h3>
        <p className="mt-1 text-[16px] leading-snug text-muted">{detail}</p>
      </div>
    </div>
  );
}

function Body({ m }) {
  const w = m.winback, r = m.reconciliation, l = m.low_cash, f = m.forecast, a = m.ask;
  return (
    <>
      <h1 className="mt-6 text-4xl font-extrabold leading-tight">How well Dukaan Sarthi works, measured</h1>
      <p className="mt-3 max-w-2xl text-lg leading-relaxed text-muted">
        Results from a simulated pilot: 5 merchant personas (kirana, salon, chai shop, pharmacy, sweet shop) with about six
        months of synthetic Paytm transactions. Each feature is checked against hidden ground truth or by backtesting on data
        it didn’t see. These are simulation results, not field data.
      </p>

      <section className="mt-8">
        <Row big={`${w.correct}/${w.true_lapsed}`} title="Lapsing regulars found"
          detail={`${pct(w.recall)} of regulars who really stopped coming were flagged. ${pct(w.precision)} of the customers flagged had truly lapsed; the rest were regulars on a long gap, for whom an offer costs little.`} />
        <Row big={pct(r.manual_share)} title="Settlements that need a manual check"
          detail={`Down from checking every settlement by hand. ${r.auto_resolved} of ${r.settlements} settlements matched or were explained automatically (refunds, delays). All ${r.shortfalls_caught} of ${r.shortfalls_injected} injected shortfalls were caught, with ${r.false_reviews} false flags.`} />
        <Row big={`${l.caught}/${l.actual_low_weeks}`} title="Low-cash weeks warned 8–14 days ahead"
          detail={`Tested over ${l.weeks_tested} merchant-weeks. ${l.false_alarms} amber or red warnings came in the ${l.normal_weeks} weeks that turned out fine. Small sample: real data will tell us more.`} />
        <Row big={pct(f.wape)} title="Sales forecast error, 30 days ahead"
          detail={`Weighted absolute percentage error across 4 rolling 30-day backtests, versus ${pct(f.wape_naive)} for a same-weekday average: ${pct(f.improvement)} more accurate, mainly by anticipating festival days.`} />
        <Row big={`${a.p95_ms} ms`} title="Ask Anything response time (95th percentile)"
          detail={`Offline engine, well under the 3-second target. ${a.intent_correct} of ${a.questions} test questions in Hinglish, Hindi and English were understood correctly. With an API key, Claude answers open-ended questions through the same guarded tools.`} />
        <Row big={m.privacy.raw_payer_ids_stored} title="Raw customer IDs stored"
          detail="Payer VPAs are hashed at ingestion into pseudonymous IDs (C-xxxxx). The AI only queries merchant-scoped read-only views." />
      </section>

      <h2 className="mt-10 text-2xl font-bold">By merchant</h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-[15px]">
          <thead className="text-muted">
            <tr><th className="py-2 pr-3 font-semibold">Merchant</th><th className="pr-3 font-semibold">Lapsing found</th>
              <th className="pr-3 font-semibold">Forecast error</th><th className="pr-3 font-semibold">Low-cash caught</th></tr>
          </thead>
          <tbody>
            {m.merchants.map((mm) => {
              const p = m.per_merchant[mm.id];
              return (
                <tr key={mm.id} className="border-t border-line">
                  <td className="py-2 pr-3"><b>{mm.name}</b><span className="block text-sm text-muted">{mm.category}, {mm.city}</span></td>
                  <td className="pr-3">{p.winback.correct}/{p.winback.true_lapsed}</td>
                  <td className="pr-3">{pct(p.forecast.wape)} <span className="text-muted">vs {pct(p.forecast.wape_naive)}</span></td>
                  <td className="pr-3">{p.low_cash.caught}/{p.low_cash.caught + p.low_cash.missed}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-8 text-sm text-muted">Generated {m.generated_at}. Demo date {m.demo_today}. Recompute with <code>python -m backend.metrics</code>.</p>
    </>
  );
}
