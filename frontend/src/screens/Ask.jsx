import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { tr } from "../i18n.js";
import { canListen, listen, speak } from "../voice.js";
import { Icon } from "../components/common.jsx";

export default function Ask({ mid, lang }) {
  const [log, setLog] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [hearing, setHearing] = useState(false);
  const [note, setNote] = useState(null);
  const stopRef = useRef(null);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [log, busy]);
  useEffect(() => { setLog([]); }, [mid]);

  const askQ = async (q) => {
    q = q.trim();
    if (!q) return;
    setText("");
    setLog((l) => [...l, { role: "me", text: q }]);
    setBusy(true);
    try {
      const r = await api.ask(mid, q, lang);
      setLog((l) => [...l, { role: "sarthi", ...r }]);
      speak(r.answer, lang);
    } catch (e) {
      setLog((l) => [...l, { role: "sarthi", answer: tr("error", lang), error: true }]);
    } finally { setBusy(false); }
  };

  const mic = () => {
    if (hearing) { stopRef.current?.(); return; }
    if (!canListen()) { setNote(tr("no_mic", lang)); return; }
    setNote(null);
    setHearing(true);
    let finalText = "";
    stopRef.current = listen(lang, {
      onResult: (t, isFinal) => { setText(t); if (isFinal) finalText = t; },
      onError: () => setHearing(false),
      onEnd: () => { setHearing(false); if (finalText) askQ(finalText); },
    });
  };

  return (
    <div className="flex min-h-[calc(100vh-150px)] flex-col px-4 pb-4">
      <h1 className="mt-4 text-2xl font-extrabold leading-tight">{tr("ask_title", lang)}</h1>

      {log.length === 0 && (
        <ul className="mt-4 flex flex-wrap gap-2">
          {tr("suggestions", lang).map((s) => (
            <li key={s}>
              <button onClick={() => askQ(s)} className="rounded-full border-2 border-line bg-sheet px-4 py-2 text-left text-[16px] font-medium">
                {s}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex-1 space-y-3" aria-live="polite">
        {log.map((m, i) => m.role === "me" ? (
          <p key={i} className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-sky px-4 py-2.5 text-[17px] font-medium text-ink">{m.text}</p>
        ) : (
          <Answer key={i} m={m} lang={lang} />
        ))}
        {busy && <p className="max-w-[85%] rounded-2xl rounded-bl-md bg-sheet px-4 py-3 text-muted">{tr("thinking", lang)}</p>}
        <div ref={endRef} />
      </div>

      {note && <p className="mb-2 rounded-xl bg-marigold-soft p-3 text-[15px]">{note}</p>}

      <div className="sticky bottom-[84px] mt-3 flex flex-col items-center gap-3 bg-paper pt-2">
        <button onClick={mic} aria-pressed={hearing}
          className={`relative grid h-20 w-20 place-items-center rounded-full text-ink shadow-[0_6px_0_#0E2A47] active:translate-y-1 active:shadow-[0_2px_0_#0E2A47] ${hearing ? "bg-sky ring text-sky" : "bg-marigold"}`}>
          <span className="relative z-10 text-ink"><Icon name="mic" className="h-9 w-9" /></span>
          <span className="sr-only">{tr("tap_to_speak", lang)}</span>
        </button>
        <p className="text-sm text-muted">{hearing ? tr("listening", lang) : tr("tap_to_speak", lang)}</p>
        <form className="flex w-full gap-2" onSubmit={(e) => { e.preventDefault(); askQ(text); }}>
          <label className="sr-only" htmlFor="ask-input">{tr("ask_placeholder", lang)}</label>
          <input id="ask-input" value={text} onChange={(e) => setText(e.target.value)} placeholder={tr("ask_placeholder", lang)}
            className="min-w-0 flex-1 rounded-full border-2 border-line bg-sheet px-4 py-2.5 text-[17px] outline-none focus:border-sky" />
          <button disabled={busy || !text.trim()} className="rounded-full bg-ink px-5 font-bold text-white disabled:opacity-40">
            {tr("send", lang)}
          </button>
        </form>
      </div>
    </div>
  );
}

function Answer({ m, lang }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="max-w-[92%] rounded-2xl rounded-bl-md bg-sheet px-4 py-3 shadow-[0_1px_0_#D6E0E9]">
      <p className={`text-[17px] leading-snug ${m.error ? "text-risk" : ""}`}>{m.answer}</p>
      {!m.error && (
        <div className="mt-2 flex items-center gap-4 text-sm">
          <button onClick={() => speak(m.answer, lang)} className="flex items-center gap-1 font-semibold text-sky-deep">
            <Icon name="speaker" className="h-4 w-4" />{tr("play", lang)}
          </button>
          <button onClick={() => setOpen(!open)} aria-expanded={open} className="font-semibold text-sky-deep underline decoration-dotted underline-offset-4">
            {tr("how_answered", lang)}
          </button>
          <span className="ml-auto text-xs text-muted">{m.engine?.startsWith("claude") ? tr("engine_claude", lang) : tr("engine_rules", lang)}, {m.ms} ms</span>
        </div>
      )}
      {open && (
        <div className="mt-2 space-y-1">
          {m.sql.map((s, i) => (
            <pre key={i} className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-ink p-2.5 font-mono text-[12px] leading-relaxed text-[#CFE6F7]">{s}</pre>
          ))}
          {m.fallback_reason && <p className="text-xs text-muted">Fallback: {m.fallback_reason}</p>}
        </div>
      )}
    </div>
  );
}
