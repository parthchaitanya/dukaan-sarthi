import { useEffect, useState } from "react";
import { api } from "./api.js";
import { LANGS, tr } from "./i18n.js";
import { Icon } from "./components/common.jsx";
import { initVoice, stopAll } from "./voice.js";
import Today from "./screens/Today.jsx";
import Ask from "./screens/Ask.jsx";
import Customers from "./screens/Customers.jsx";
import Money from "./screens/Money.jsx";
import Plan from "./screens/Plan.jsx";
import Metrics from "./screens/Metrics.jsx";

const TABS = [
  { key: "today", icon: "today", label: "tab_today", C: Today },
  { key: "ask", icon: "ask", label: "tab_ask", C: Ask },
  { key: "customers", icon: "customers", label: "tab_customers", C: Customers },
  { key: "money", icon: "money", label: "tab_money", C: Money },
  { key: "plan", icon: "plan", label: "tab_plan", C: Plan },
];

const read = (k, d) => { try { return localStorage.getItem(k) || d; } catch { return d; } };
const write = (k, v) => { try { localStorage.setItem(k, v); } catch {} };
const route = () => (location.pathname.startsWith("/metrics") ? "metrics" : (location.hash.replace(/^#\/?/, "") || "today"));

export default function App() {
  const [tab, setTab] = useState(route());
  const [lang, setLang] = useState(read("sarthi.lang", "hinglish"));
  const [mid, setMid] = useState(read("sarthi.mid", "m1"));
  const [merchants, setMerchants] = useState([]);

  useEffect(() => { const f = () => setTab(route()); window.addEventListener("hashchange", f); return () => window.removeEventListener("hashchange", f); }, []);
  useEffect(() => { api.merchants().then(setMerchants).catch(() => {}); }, []);
  useEffect(() => { write("sarthi.lang", lang); document.documentElement.lang = lang === "en" ? "en" : "hi"; }, [lang]);
  useEffect(() => { write("sarthi.mid", mid); }, [mid]);
  useEffect(() => { window.scrollTo(0, 0); stopAll(); }, [tab]);
  useEffect(() => { initVoice(); }, []);

  if (tab === "metrics") return <Metrics />;
  const go = (k) => { location.hash = `#/${k}`; };
  const T = TABS.find((t) => t.key === tab) || TABS[0];
  const m = merchants.find((x) => x.id === mid);

  return (
    <div className="mx-auto min-h-screen max-w-[440px] bg-paper pb-24 sm:my-6 sm:min-h-[calc(100vh-3rem)] sm:rounded-[36px] sm:shadow-[0_0_0_10px_#0E2A47]">
      <header className="sticky top-0 z-20 flex items-center gap-3 bg-paper/95 px-4 pb-2 pt-4 backdrop-blur">
        <div className="min-w-0 flex-1">
          <label className="sr-only" htmlFor="shop">Shop</label>
          <select id="shop" value={mid} onChange={(e) => setMid(e.target.value)}
            className="w-full truncate bg-transparent text-lg font-extrabold leading-tight outline-none">
            {merchants.length === 0 && <option value={mid}>Dukaan Sarthi</option>}
            {merchants.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
          {m && <p className="truncate text-sm text-muted">{m.owner}, {m.city}</p>}
        </div>
        <div className="flex rounded-full bg-sheet p-1 shadow-[inset_0_0_0_1px_#D6E0E9]" role="group" aria-label="Language">
          {LANGS.map((l) => (
            <button key={l.key} onClick={() => setLang(l.key)} aria-pressed={lang === l.key}
              className={`rounded-full px-2.5 py-1 text-sm font-bold ${lang === l.key ? "bg-ink text-white" : "text-muted"}`}>
              {l.label}
            </button>
          ))}
        </div>
      </header>

      <main><T.C mid={mid} lang={lang} go={go} /></main>

      <nav className="fixed bottom-0 left-1/2 z-30 w-full max-w-[440px] -translate-x-1/2 border-t border-line bg-sheet pb-[env(safe-area-inset-bottom)] sm:bottom-6 sm:rounded-b-[36px]">
        <ul className="grid grid-cols-5">
          {TABS.map((t) => {
            const on = t.key === T.key;
            return (
              <li key={t.key}>
                <a href={`#/${t.key}`} aria-current={on ? "page" : undefined}
                  className={`flex flex-col items-center gap-0.5 py-2.5 text-[13px] font-semibold ${on ? "text-ink" : "text-muted"}`}>
                  <span className={`grid h-8 w-12 place-items-center rounded-full ${on ? "bg-sky/25" : ""}`}><Icon name={t.icon} /></span>
                  {tr(t.label, lang)}
                </a>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
