// Voice in (Web Speech API) and voice out (speechSynthesis). Both degrade gracefully.
const SPEECH_LANG = { hinglish: "hi-IN", hi: "hi-IN", en: "en-IN" };

export const canListen = () => typeof window !== "undefined" &&
  ("webkitSpeechRecognition" in window || "SpeechRecognition" in window);
export const canSpeak = () => typeof window !== "undefined" && "speechSynthesis" in window;

function pickVoice(lang) {
  const voices = window.speechSynthesis.getVoices();
  const want = SPEECH_LANG[lang];
  return voices.find((v) => v.lang === want) || voices.find((v) => v.lang.startsWith(want.slice(0, 2))) || null;
}

// Speak a list of lines one after another; onLine(i) fires as each line starts.
export function speakLines(lines, lang, { onLine, onEnd } = {}) {
  if (!canSpeak()) { onEnd?.(); return () => {}; }
  const synth = window.speechSynthesis;
  synth.cancel();
  let cancelled = false;
  const voice = pickVoice(lang);
  lines.forEach((text, i) => {
    const u = new SpeechSynthesisUtterance(text.replace(/C-([0-9A-F]{5})/g, "grahak"));
    u.lang = SPEECH_LANG[lang];
    if (voice) u.voice = voice;
    u.rate = lang === "en" ? 1.0 : 0.95;
    u.onstart = () => !cancelled && onLine?.(i);
    if (i === lines.length - 1) u.onend = () => !cancelled && onEnd?.();
    synth.speak(u);
  });
  return () => { cancelled = true; synth.cancel(); onEnd?.(); };
}

export const speak = (text, lang, opts) => speakLines([text], lang, opts);

export function listen(lang, { onResult, onError, onEnd }) {
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Rec) { onError?.("unsupported"); return () => {}; }
  const r = new Rec();
  r.lang = SPEECH_LANG[lang];
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
