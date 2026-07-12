export default function Sparkline({ data, width = 72, height = 28, color = "var(--accent-strong)" }) {
  if (!data || data.length < 2) return null;

  const max = Math.max(...data, 1);
  const stepX = width / (data.length - 1);
  const pad = 6;
  const points = data.map((v, i) => [i * stepX, pad + (height - pad * 2) * (1 - v / max)]);
  const linePath = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${width},${height} L0,${height} Z`;
  const [lastX, lastY] = points[points.length - 1];

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="sparkline"
      role="img"
      aria-label={`7-day trend: ${data.join(", ")}`}
    >
      <path d={areaPath} fill="var(--muted)" opacity="0.08" stroke="none" />
      <path d={linePath} fill="none" stroke="var(--border-strong)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r="6" fill="var(--surface-1)" />
      <circle cx={lastX} cy={lastY} r="4" fill={color} />
    </svg>
  );
}
