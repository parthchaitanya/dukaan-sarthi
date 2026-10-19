import { inr } from "../api.js";

// Bars for sales by hour; the busiest two hours are drawn in Paytm blue.
export function HourBars({ hourly, peak }) {
  const data = hourly.filter((h) => h.hour >= 6 && h.hour <= 22);
  const max = Math.max(...data.map((d) => d.amount), 1);
  const W = 340, H = 90, bw = W / data.length;
  return (
    <svg viewBox={`0 0 ${W} ${H + 18}`} className="w-full" role="img"
      aria-label={`Sales by hour. Busiest from ${peak}:00 to ${peak + 2}:00.`}>
      {data.map((d, i) => {
        const h = (d.amount / max) * H;
        const hot = d.hour === peak || d.hour === peak + 1;
        return (
          <g key={d.hour}>
            <rect x={i * bw + 2} y={H - h} width={bw - 4} height={Math.max(h, 1)} rx="3"
              fill={hot ? "#00B9F1" : "#BFD0DF"}>
              <title>{`${d.hour}:00 ${inr(d.amount)}`}</title>
            </rect>
            {d.hour % 3 === 0 && (
              <text x={i * bw + bw / 2} y={H + 14} textAnchor="middle" fontSize="11" fill="#5A6B7E">
                {d.hour % 12 || 12}{d.hour < 12 ? "a" : "p"}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// Balance history (solid) + forecast (dashed), with the safe limit as a reference line.
export function BalanceChart({ history, days, buffer, label, todayLabel = "today" }) {
  const pts = [...history.map((h) => ({ ...h, f: false })), ...days.map((d) => ({ date: d.date, balance: d.balance, f: true }))];
  const vals = pts.map((p) => p.balance).concat([buffer]);
  const min = Math.min(...vals) * 0.9, max = Math.max(...vals) * 1.05;
  const W = 340, H = 150, P = 4;
  const x = (i) => P + (i / (pts.length - 1)) * (W - 2 * P);
  const y = (v) => H - ((v - min) / (max - min)) * H;
  const line = (arr, off) => arr.map((p, i) => `${i ? "L" : "M"}${x(i + off).toFixed(1)},${y(p.balance).toFixed(1)}`).join("");
  const nh = history.length;
  const fc = pts.slice(nh - 1);
  const lows = days.map((d, i) => ({ ...d, i: i + nh })).filter((d) => d.balance < buffer * 1.2);
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H + 20}`} className="w-full" role="img" aria-label={label}>
        <rect x="0" y={y(buffer)} width={W} height={H - y(buffer)} fill="#FBE7E5" />
        <line x1="0" x2={W} y1={y(buffer)} y2={y(buffer)} stroke="#C8372D" strokeDasharray="4 4" strokeWidth="1.5" />
        <path d={line(pts.slice(0, nh), 0)} fill="none" stroke="#0E2A47" strokeWidth="2.5" />
        <path d={line(fc, nh - 1)} fill="none" stroke="#0068B3" strokeWidth="2.5" strokeDasharray="6 5" />
        <line x1={x(nh - 1)} x2={x(nh - 1)} y1="0" y2={H} stroke="#5A6B7E" strokeWidth="1" />
        {lows.map((d) => <circle key={d.date} cx={x(d.i)} cy={y(d.balance)} r="3.5" fill={d.balance < buffer ? "#C8372D" : "#F2A900"} />)}
        <text x={x(nh - 1) - 4} y={H + 15} textAnchor="end" fontSize="11" fill="#5A6B7E">{todayLabel}</text>
        <text x={W - 2} y={y(buffer) - 5} textAnchor="end" fontSize="11" fill="#C8372D">{inr(buffer)}</text>
      </svg>
    </figure>
  );
}

// Semicircle gauge for the credit score.
export function Gauge({ score }) {
  const r = 70, c = Math.PI * r, frac = Math.max(0, Math.min(score, 100)) / 100;
  const color = score >= 75 ? "#1F7A52" : score >= 60 ? "#F2A900" : "#C8372D";
  return (
    <svg viewBox="0 0 180 100" className="w-40" role="img" aria-label={`Score ${score} out of 100`}>
      <path d="M20 90 A70 70 0 0 1 160 90" fill="none" stroke="#D6E0E9" strokeWidth="16" strokeLinecap="round" />
      <path d="M20 90 A70 70 0 0 1 160 90" fill="none" stroke={color} strokeWidth="16" strokeLinecap="round"
        strokeDasharray={`${c * frac} ${c}`} />
      <text x="90" y="82" textAnchor="middle" fontSize="34" fontWeight="800" fill="#0E2A47">{score}</text>
    </svg>
  );
}
