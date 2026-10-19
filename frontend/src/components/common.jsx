import { useEffect, useState, useCallback } from "react";
import { tr } from "../i18n.js";

export function useData(fn, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const load = useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: null }));
    fn().then((data) => setState({ data, error: null, loading: false }))
      .catch((error) => setState({ data: null, error, loading: false }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(load, [load]);
  return { ...state, reload: load };
}

export function Loader({ state, lang, children }) {
  if (state.error) {
    return (
      <div className="m-4 rounded-2xl bg-risk-soft p-5 text-risk" role="alert">
        <p className="text-lg font-semibold">{tr("error", lang)}</p>
        <p className="mt-1 text-sm opacity-80">{String(state.error.message || state.error)}</p>
        <button onClick={state.reload} className="mt-3 rounded-full bg-risk px-5 py-2 text-base font-semibold text-white">
          {tr("retry", lang)}
        </button>
      </div>
    );
  }
  if (!state.data) {
    return <p className="p-6 text-center text-lg text-muted" aria-live="polite">{tr("loading", lang)}</p>;
  }
  return children(state.data);
}

export function H2({ children, aside }) {
  return (
    <div className="mb-2 mt-7 flex items-baseline justify-between gap-3 px-1">
      <h2 className="text-xl font-bold leading-tight text-ink">{children}</h2>
      {aside && <span className="text-sm text-muted">{aside}</span>}
    </div>
  );
}

export function Why({ lang, children }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen(!open)} aria-expanded={open}
        className="mt-1 text-sm font-semibold text-sky-deep underline decoration-dotted underline-offset-4">
        {tr("why", lang)}
      </button>
      {open && <p className="mt-1 rounded-lg bg-paper px-3 py-2 text-sm leading-snug text-muted">{children}</p>}
    </div>
  );
}

const PATHS = {
  today: "M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4M12 8a4 4 0 100 8 4 4 0 000-8z",
  ask: "M12 3a3 3 0 00-3 3v6a3 3 0 006 0V6a3 3 0 00-3-3zM5 11a7 7 0 0014 0M12 18v3",
  customers: "M9 11a4 4 0 100-8 4 4 0 000 8zM2 21v-1a6 6 0 0112 0v1M16 3.5a4 4 0 010 7M22 21v-1a6 6 0 00-4-5.6",
  money: "M3 7h18v12H3zM3 10h18M7 15h3",
  plan: "M4 5h16v15H4zM4 9h16M9 3v4M15 3v4M8 13h3v3H8z",
  play: "M8 5v14l11-7z",
  stop: "M7 7h10v10H7z",
  mic: "M12 3a3 3 0 00-3 3v6a3 3 0 006 0V6a3 3 0 00-3-3zM5 11a7 7 0 0014 0M12 18v3",
  speaker: "M4 9v6h4l5 4V5L8 9zM16 9a4 4 0 010 6M18.5 6.5a8 8 0 010 11",
  alert: "M12 3l10 18H2zM12 10v5M12 18v.5",
  check: "M5 12l5 5L20 7",
};

export function Icon({ name, className = "h-6 w-6", filled = false }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" fill={filled ? "currentColor" : "none"}
      stroke={filled ? "none" : "currentColor"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d={PATHS[name]} />
    </svg>
  );
}
