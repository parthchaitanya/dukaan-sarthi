import { useEffect, useRef, useState } from "react";
import { api, inr } from "../api.js";
import { tr } from "../i18n.js";
import { chime, listVoices, preferredVoice, setPreferredVoice, speak, speakLines, usingServerVoice } from "../voice.js";
import { H2, Icon, Loader, useData, Why } from "../components/common.jsx";
import { HourBars } from "../components/charts.jsx";

// The card shows the summary; alerts and actions are spoken too, and shown as rows below.
const SUMMARY_LINES = 4;
const ACTION_TAB = { winback: "customers", plan: "plan", money: "money", hisaab: "plan" };

export default function Today({ mid, lang, go }) {
  const state = useData(() => api.brief(mid, lang), [mid, lang]);
  return (
    <Loader state={state} lang={lang}>
      {(b) => <Brief b={b} lang={lang} mid={mid} go={go} />}
    </Loader>
  );
}

function Brief({ b, lang, mid, go }) {
  const [line, setLine] = useState(-1);
  const stopRef = useRef(null);
  const playing = line >= 0;
  useEffect(() => () => stopRef.current?.(), []);
  useEffect(() => { stopRef.current?.(); setLine(-1); }, [b]);

  const toggle = () => {
    if (playing) { stopRef.current?.(); setLine(-1); return; }
    setLine(0);
    stopRef.current = speakLines(b.speak_lines || b.lines, b.speak_lang || lang, { onLine: setLine, onEnd: () => setLine(-1) });
  };
  const ch = b.change_vs_last_week;
  const up = ch >= 0;

  return (
    <div className="px-4 pb-6">
      {/* The Soundbox card: the brief, spoken. */}
      <section className="relative mt-3 overflow-hidden rounded-[28px] bg-ink text-white" aria-labelledby="brief-h">
        <div className="grille pointer-events-none absolute -right-6 -top-6 h-40 w-40 rounded-full opacity-70" aria-hidden="true" />
        <div className="relative p-5">
          <div className="flex items-center justify-between">
            <h1 id="brief-h" className="text-2xl font-extrabold">{tr("brief_title", lang)}</h1>
            <span className="text-sm text-[#9FC3E0]">{new Date(b.today).toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", { weekday: "long", day: "numeric", month: "long" })}</span>
          </div>
          <ol className="mt-3 space-y-1.5 text-[17px] leading-snug" aria-live="polite">
            {b.lines.slice(0, SUMMARY_LINES).map((l, i) => (
              <li key={i} className={`speaking-line ${playing ? (i === line ? "text-white" : "text-white/45") : "text-white/90"}`}>{l}</li>
            ))}
            {playing && line >= SUMMARY_LINES && (
              <li className="speaking-line rounded-xl bg-white/10 px-3 py-2 text-white">{b.lines[line]}</li>
            )}
          </ol>
          <button onClick={toggle}
            className="mt-5 flex w-full items-center justify-center gap-3 rounded-full bg-marigold py-3.5 text-xl font-bold text-ink active:scale-[0.99]">
            <span className={`relative grid h-9 w-9 place-items-center rounded-full bg-ink text-marigold ${playing ? "ring" : ""}`}>
              <Icon name={playing ? "stop" : "play"} filled className="h-5 w-5" />
            </span>
            {playing ? tr("stop", lang) : tr("play", lang)}
          </button>
        </div>
      </section>

      {/* Yesterday at a glance */}
      <section className="mt-4 grid grid-cols-[1.4fr_1fr] gap-3">
        <div className="rounded-2xl bg-sheet p-4 shadow-[0_1px_0_#D6E0E9]">
          <p className="text-sm text-muted">{tr("yesterday_sales", lang)}</p>
          <p className="text-3xl font-extrabold tracking-tight">{b.sales_label}</p>
          <p className={`text-sm font-semibold ${up ? "text-good" : "text-risk"}`}>
            {Math.abs(ch * 100).toFixed(0)}% {up ? tr("up", lang) : tr("down", lang)} <span className="font-normal text-muted">{tr("vs_last", lang)}</span>
          </p>
        </div>
        <div className="rounded-2xl bg-sheet p-4 shadow-[0_1px_0_#D6E0E9]">
          <p className="text-sm text-muted">{tr("busiest", lang)}</p>
          <p className="text-xl font-bold leading-tight">{b.peak_hours}</p>
          <p className="text-sm text-muted">{b.txns} {tr("payments", lang)}</p>
        </div>
      </section>

      {b.anomalies.map((a) => (
        <div key={a.kind} className="mt-3 flex gap-3 rounded-2xl bg-risk-soft p-4 text-risk" role="status">
          <Icon name="alert" className="mt-0.5 h-6 w-6 shrink-0" />
          <p className="text-[16px] leading-snug text-ink">{a.text}</p>
        </div>
      ))}

      <H2>{tr("todo", lang)}</H2>
      <ol className="divide-y divide-line overflow-hidden rounded-2xl bg-sheet">
        {b.actions.map((a, i) => (
          <li key={i} className="flex gap-3 p-4">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-marigold-soft text-lg font-extrabold text-ink">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <p className="text-[17px] leading-snug">{a.text}</p>
              <div className="flex items-center justify-between">
                <Why lang={lang}>{a.why}</Why>
                {a.cta && ACTION_TAB[a.cta] && (
                  <button onClick={() => go(ACTION_TAB[a.cta])} className="mt-1 rounded-full border-2 border-ink px-4 py-1 text-sm font-bold">
                    {tr("open", lang)}
                  </button>
                )}
              </div>
            </div>
          </li>
        ))}
      </ol>

      <H2>{tr("sales_by_hour", lang)}</H2>
      <div className="rounded-2xl bg-sheet p-3"><HourBars hourly={b.hourly} peak={b.peak_hour_start} /></div>

      <Soundbox mid={mid} lang={lang} />
      <VoicePicker lang={lang} />
    </div>
  );
}

const AMOUNTS = [40, 120, 250, 560];

function Soundbox({ mid, lang }) {
  const st = useData(() => api.soundbox(mid), [mid]);
  const [last, setLast] = useState(null);
  const [busy, setBusy] = useState(false);
  const pay = async (amt) => {
    setBusy(true);
    try {
      chime();
      const r = await api.pay(mid, amt, lang);
      setLast(r);
      setTimeout(() => speak(r.speak, r.speak_lang || lang), 450);
      st.reload();
    } finally { setBusy(false); }
  };
  const s = st.data;
  return (
    <section aria-labelledby="sb-h">
      <H2 aside={s ? s.clock : null}><span id="sb-h">{tr("soundbox", lang)}</span></H2>
      <div className="rounded-2xl bg-ink-2 p-4 text-white">
        <p className="text-[15px] text-[#BFD8EE]">{tr("soundbox_hint", lang)}</p>
        <div className="mt-3 grid grid-cols-4 gap-2">
          {AMOUNTS.map((a) => (
            <button key={a} disabled={busy} onClick={() => pay(a)}
              className="rounded-xl bg-sky py-3 text-lg font-bold text-ink disabled:opacity-60">₹{a}</button>
          ))}
        </div>
        {s && (
          <p className="mt-3 text-[15px]">
            <b className="text-2xl">{s.count_today}</b> {tr("sales_today", lang)}, {s.yesterday_same_time} {tr("same_time_yday", lang)}
            <span className="block text-sm text-[#BFD8EE]">{tr("next_milestone", lang)}: {s.next_milestone}</span>
          </p>
        )}
        {last && (
          <p className="mt-3 rounded-xl bg-white/10 p-3 text-[16px] leading-snug" aria-live="polite">
            <Icon name="speaker" className="mr-2 inline h-5 w-5 text-sky" />{last.text || last.speak}
          </p>
        )}
        <button onClick={async () => { await api.resetSoundbox(mid); setLast(null); st.reload(); }}
          className="mt-3 text-sm text-[#BFD8EE] underline underline-offset-4">{tr("reset", lang)}</button>
      </div>
    </section>
  );
}

export { inr };

const SAMPLE = { hi: "नमस्ते, मैं हूँ आपका दुकान सारथी। कल की बिक्री 27 हज़ार 500 रुपये रही।",
  en: "Hello, this is your Dukaan Sarthi. Yesterday you sold 27 thousand 500 rupees." };

// Lets the shopkeeper (or presenter) choose the clearest voice installed on this device.
function VoicePicker({ lang }) {
  const vlang = lang === "en" ? "en" : "hi";
  const [voices, setVoices] = useState([]);
  const [pick, setPick] = useState(preferredVoice(vlang));
  useEffect(() => { listVoices(vlang).then(setVoices); setPick(preferredVoice(vlang)); }, [vlang]);
  if (usingServerVoice() || voices.length === 0) return null;
  const change = (name) => { setPick(name); setPreferredVoice(vlang, name); speak(SAMPLE[vlang], vlang); };
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 px-1 text-sm">
      <label htmlFor="voice" className="font-semibold">{tr("voice", lang)}</label>
      <select id="voice" value={pick} onChange={(e) => change(e.target.value)}
        className="min-w-0 flex-1 rounded-full border-2 border-line bg-sheet px-3 py-1.5">
        <option value="">{tr("voice_auto", lang)}</option>
        {voices.map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}
      </select>
      <button onClick={() => speak(SAMPLE[vlang], vlang)} className="rounded-full border-2 border-ink px-3 py-1 font-bold">
        {tr("voice_test", lang)}
      </button>
    </div>
  );
}
