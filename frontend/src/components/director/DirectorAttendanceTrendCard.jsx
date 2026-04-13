function TrendSvg({ points }) {
  if (!points?.length) {
    return null;
  }
  const w = 560;
  const h = 200;
  const padL = 36;
  const padR = 12;
  const padT = 16;
  const padB = 28;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const n = points.length;
  const coords = points.map((p, i) => {
    const x = padL + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW);
    const rate = p.rate_percent;
    const y =
      rate == null
        ? padT + innerH
        : padT + innerH - (Math.min(100, Math.max(0, Number(rate))) / 100) * innerH;
    return { x, y, rate, date: p.date };
  });
  const withRate = coords.filter((c) => c.rate != null);
  const lineD = withRate
    .map((c, idx) => `${idx === 0 ? "M" : "L"} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`)
    .join(" ");
  const baseY = (padT + innerH).toFixed(1);
  const areaD =
    withRate.length > 1
      ? `${withRate.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`).join(" ")} L ${withRate[withRate.length - 1].x.toFixed(1)} ${baseY} L ${withRate[0].x.toFixed(1)} ${baseY} Z`
      : "";

  return (
    <svg
      className="vc-director-trend-svg"
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="Attendance rate by day"
    >
      <line x1={padL} y1={padT + innerH} x2={padL + innerW} y2={padT + innerH} stroke="#e2e8f0" strokeWidth="1" />
      <text x={padL} y={h - 6} fill="#94a3b8" fontSize="11">
        Last 30 days
      </text>
      {coords.map((c) =>
        c.rate != null ? (
          <circle key={c.date} cx={c.x} cy={c.y} r={3} fill="#2563eb" opacity={0.9} />
        ) : null,
      )}
      {areaD ? <path d={areaD} fill="rgba(37, 99, 235, 0.12)" stroke="none" /> : null}
      {lineD ? <path d={lineD} fill="none" stroke="#2563eb" strokeWidth={2} strokeLinejoin="round" /> : null}
    </svg>
  );
}

export default function DirectorAttendanceTrendCard({ loading, clubId, trend }) {
  const points = trend?.points || [];
  const hasData = points.some((p) => p.closed_slots > 0);

  return (
    <section className="vc-panel vc-panel--dashboard vc-panel--director-white">
      <div className="vc-dashboard-panel-head">
        <div>
          <p className="vc-dashboard-panel-head__eyebrow">Analytics</p>
          <h2 className="vc-panel-title">Attendance Trend (Last 30 Days)</h2>
        </div>
      </div>
      <div className="vc-director-trend-body">
        {loading ? (
          <p className="vc-modal__muted" style={{ margin: 0 }}>
            Loading…
          </p>
        ) : !clubId ? (
          <p className="vc-modal__muted" style={{ margin: 0 }}>
            Select a club to load attendance history.
          </p>
        ) : !hasData ? (
          <p className="vc-modal__muted" style={{ margin: 0 }}>
            No closed session attendance in the last 30 days yet. Schedule and close sessions to see this
            chart fill in.
          </p>
        ) : (
          <>
            {trend?.calculation_summary ? (
              <p className="vc-dashboard-inline-copy" style={{ marginTop: 0 }}>
                {trend.calculation_summary}
              </p>
            ) : null}
            <div className="vc-director-trend-chart">
              <TrendSvg points={points} />
            </div>
          </>
        )}
      </div>
    </section>
  );
}
