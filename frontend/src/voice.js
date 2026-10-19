// Voice out and voice in.
//
// Voice out uses the server's neural voice (Sarvam Bulbul) when it's switched on, and the
// browser's own voice otherwise. The server already sends text written for speaking
// (Hinglish is spoken from Hindi script, amounts as words), so here we only:
//   * wait for the browser's voices to load (otherwise Chrome reads Hindi with an English voice),
//   * pick the clearest installed voice for the language,
//   * speak in short sentence chunks at a slightly slower rate (long utterances get cut off or slurred).

const BCP = { hi: "hi-IN", en: "en-IN", hinglish: "hi-IN" };
let serverTTS = null; // null = unknown yet, then true/false
let current = null;   // the playing <audio>

export async function initVoice() {
  try {
    const h = await (await fetch("/api/health")).json();
    serverTTS = !!h.tts && h.tts !== "browser";
  } catch { serverTTS = false; }
  return serverTTS;
}
export const usingServerVoice = () => !!serverTTS;

export const canListen = () => typeof window !== "undefined" &&
  ("webkitSpeechRecognition" in window || "SpeechRecognition" in window);
export const canSpeak = () => typeof window !== "undefined" && ("speechSynthesis" in window || serverTTS);

// ---------- browser voices
let voicesReady = null;
function loadVoices() {
  if (voicesReady) return voicesReady;
  voicesReady = new Promise((resolve) => {
    const synth = window.speechSynthesis;
    const have = synth.getVoices();
    if (have.length) return resolve(have);
    const done = () => resolve(synth.getVoices());
    synth.addEventListener?.("voiceschanged", done, { once: true });
    setTimeout(done, 1500);
  });
  return voicesReady;
}

// Higher = clearer. Network/neural voices (Google, Microsoft Online "Natural") beat the old offline ones.
function score(v, want) {
  let s = 0;
  if (v.lang === want) s += 100;
  else if (v.lang?.toLowerCase().startsWith(want.slice(0, 2))) s += 60;
  else return -1;
  const n = v.name.toLowerCase();
  if (/natural|neural|online/.test(n)) s += 40;      // Edge: "Microsoft Swara Online (Natural)"
  if (/google/.test(n)) s += 30;                      // Chrome: "Google हिन्दी"
  if (/premium|enhanced/.test(n)) s += 25;            // macOS downloaded voices
  if (/lekha|swara|kalpana|hemant|madhur|neerja|prabhat|veena|rishi/.test(n)) s += 15; // Indian voices
  if (!v.localService) s += 5;
  return s;
}

// The person can pick a voice themselves (saved per language); otherwise we pick the clearest.
const PREF_KEY = (lang) => `sarthi.voice.${lang === "en" ? "en" : "hi"}`;
export async function listVoices(lang) {
  const want = BCP[lang] || "hi-IN";
  if (!("speechSynthesis" in window)) return [];
  return (await loadVoices()).filter((v) => score(v, want) >= 0).sort((a, b) => score(b, want) - score(a, want));
}
export function preferredVoice(lang) { try { return localStorage.getItem(PREF_KEY(lang)) || ""; } catch { return ""; } }
export function setPreferredVoice(lang, name) {
  try { name ? localStorage.setItem(PREF_KEY(lang), name) : localStorage.removeItem(PREF_KEY(lang)); } catch {}
}

async function bestVoice(lang) {
  const want = BCP[lang] || "hi-IN";
  const voices = await loadVoices();
  const pick = preferredVoice(lang);
  if (pick) { const v = voices.find((x) => x.name === pick); if (v) return v; }
  let best = null, bestS = -1;
  for (const v of voices) { const s = score(v, want); if (s > bestS) { best = v; bestS = s; } }
  return best;
}

function chunks(text) {
  const parts = text.split(/(?<=[.!?।])\s+/).map((s) => s.trim()).filter(Boolean);
  const out = [];
  for (let p of parts) {
    while (p.length > 180) {
      let cut = p.lastIndexOf(",", 180);
      if (cut < 40) cut = p.lastIndexOf(" ", 180);
      out.push(p.slice(0, cut + 1).trim()); p = p.slice(cut + 1).trim();
    }
    out.push(p);
  }
  return out;
}

// ---------- server voice (Sarvam Bulbul)
const audioCache = new Map();
function fetchAudio(text, lang) {
  const key = lang + "|" + text;
  if (!audioCache.has(key)) {
    audioCache.set(key, fetch("/api/tts", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text, lang }),
    }).then((r) => {
      if (r.status !== 200) throw new Error("tts " + r.status);
      return r.blob();
    }).then((b) => URL.createObjectURL(b)).catch((e) => { audioCache.delete(key); throw e; }));
  }
  return audioCache.get(key);
}

function playUrl(url, isCancelled) {
  return new Promise((resolve, reject) => {
    if (isCancelled()) return resolve();
    const a = new Audio(url);
    current = a;
    a.onended = () => resolve();
    a.onerror = () => reject(new Error("audio"));
    a.play().catch(reject);
  });
}

// ---------- public API
// Speak lines one after another; onLine(i) fires when line i starts. Returns a stop() function.
export function speakLines(lines, lang, { onLine, onEnd } = {}) {
  let cancelled = false;
  const isCancelled = () => cancelled;
  stopAll();

  const browserFrom = async (start) => {
    if (!("speechSynthesis" in window)) return onEnd?.();
    const synth = window.speechSynthesis;
    const voice = await bestVoice(lang);
    if (cancelled) return;
    const queue = [];
    lines.slice(start).forEach((line, k) => chunks(line).forEach((c, j) => queue.push({ c, i: start + k, first: j === 0 })));
    queue.forEach((q, idx) => {
      const u = new SpeechSynthesisUtterance(q.c);
      u.lang = BCP[lang] || "hi-IN";
      if (voice) u.voice = voice;
      u.rate = lang === "en" ? 0.95 : 0.88;
      u.pitch = 1;
      if (q.first) u.onstart = () => !cancelled && onLine?.(q.i);
      if (idx === queue.length - 1) u.onend = () => !cancelled && onEnd?.();
      synth.speak(u);
    });
    if (!queue.length) onEnd?.();
  };

  (async () => {
    if (serverTTS === null) await initVoice();
    if (serverTTS) {
      try {
        for (let i = 0; i < lines.length; i++) {
          if (cancelled) return;
          const url = await fetchAudio(lines[i], lang);
          if (i + 1 < lines.length) fetchAudio(lines[i + 1], lang).catch(() => {}); // prefetch the next line
          onLine?.(i);
          await playUrl(url, isCancelled);
        }
        if (!cancelled) onEnd?.();
        return;
      } catch {
        // server voice failed (offline, quota): carry on with the browser's voice
      }
    }
    browserFrom(0);
  })();

  return () => { cancelled = true; stopAll(); onEnd?.(); };
}

export const speak = (text, lang, opts) => speakLines([text], lang, opts);

export function stopAll() {
  try { window.speechSynthesis?.cancel(); } catch {}
  if (current) { try { current.pause(); } catch {} current = null; }
}

export function listen(lang, { onResult, onError, onEnd }) {
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Rec) { onError?.("unsupported"); return () => {}; }
  const r = new Rec();
  r.lang = BCP[lang] || "hi-IN";
  r.interimResults = true;
  r.maxAlternatives = 1;
  r.onresult = (e) => {
    const res = e.results[e.results.length - 1];
    onResult?.(res[0].transcript, res.isFinal);
  };
  r.onerror = (e) => onError?.(e.error);
  r.onend = () => onEnd?.();
  r.start();
  return () => r.stop();
}

// A short two-note chime, like a Soundbox before it announces a payment.
export function chime() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [880, 1320].forEach((f, i) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = f; o.type = "sine";
      g.gain.setValueAtTime(0.0001, ctx.currentTime + i * 0.14);
      g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + i * 0.14 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + i * 0.14 + 0.35);
      o.connect(g).connect(ctx.destination);
      o.start(ctx.currentTime + i * 0.14); o.stop(ctx.currentTime + i * 0.14 + 0.4);
    });
  } catch {}
}
