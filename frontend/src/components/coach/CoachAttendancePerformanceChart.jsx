const PAD_L = 44;
const PAD_R = 12;
const PAD_T = 16;
const PAD_B = 52;

export default function CoachAttendancePerformanceChart({ series, hasSkillMetrics }) {
  const metricsMissing = hasSkillMetrics === false;
  if (metricsMissing) {
    return (
      <div className="vc-coach-dash-chart">
        <h2 className="vc-panel-title">Attendance vs. Performance</h2>
        <p className="vc-modal__muted" style={{ margin: 0 }}>
          No attendance vs. performance data yet. Skill metrics appear here once they are recorded for this team.
        </p>
      </div>
    );
  }

  if (!series || !Array.isArray(series.labels) || !series.labels.length) {
    return (
      <div className="vc-coach-dash-chart">
        <h2 className="vc-panel-title">Attendance vs. Performance</h2>
        <p className="vc-modal__muted" style={{ margin: 0 }}>
          No chart data available for this team yet.
        </p>
      </div>
    );
  }

  const { labels, attendance, average_performance: performance } = series;
  const n = labels.length;
  const w = 420;
  const h = 220;
  const innerW = w - PAD_L - PAD_R;
  const innerH = h - PAD_T - PAD_B;
  const perf = Array.isArray(performance) ? performance : [];
  const att = Array.isArray(attendance) ? attendance : [];
  const maxVal = Math.max(...att, ...perf, 1);
  const groupW = innerW / n;
  const barW = Math.min(18, groupW * 0.22);
  const gap = 4;

  const bars = labels.map((label, i) => {
    const cx = PAD_L + i * groupW + groupW / 2;
    const aH = ((att[i] ?? 0) / maxVal) * innerH;
    const pH = ((perf[i] ?? 0) / maxVal) * innerH;
    const baseY = PAD_T + innerH;
    const x1 = cx - barW - gap / 2;
    const x2 = cx + gap / 2;
    return {
      label,
      labelX: cx,
      attendance: {
        x: x1,
        y: baseY - aH,
        height: aH,
        width: barW,
      },
      performance: {
        x: x2,
        y: baseY - pH,
        height: pH,
        width: barW,
      },
    };
  });

  return (
    <div className="vc-coach-dash-chart">
      <h2 className="vc-panel-title">Attendance vs. Performance</h2>
      <div className="vc-chart-wrap vc-coach-dash-chart__wrap">
        <svg className="vc-chart-svg" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid meet" aria-hidden="true">
          <line
            x1={PAD_L}
            y1={PAD_T + innerH}
            x2={PAD_L + innerW}
            y2={PAD_T + innerH}
            stroke="#e2e8f0"
            strokeWidth="1"
          />
          {bars.map((g) => (
            <g key={g.label}>
              <rect
                x={g.attendance.x}
                y={g.attendance.y}
                width={g.attendance.width}
                height={g.attendance.height}
                rx="2"
                fill="#4a90e2"
              />
              <rect
                x={g.performance.x}
                y={g.performance.y}
                width={g.performance.width}
                height={g.performance.height}
                rx="2"
                fill="#94a3b8"
              />
              <text
                x={g.labelX}
                y={h - 18}
                textAnchor="middle"
                fill="#5c6570"
                fontSize="11"
                fontWeight="600"
              >
                {g.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <div className="vc-coach-dash-chart__legend" role="list">
        <span className="vc-coach-dash-chart__legend-item" role="listitem">
          <span className="vc-coach-dash-chart__swatch vc-coach-dash-chart__swatch--attendance" /> Attendance
        </span>
        <span className="vc-coach-dash-chart__legend-item" role="listitem">
          <span className="vc-coach-dash-chart__swatch vc-coach-dash-chart__swatch--performance" /> Average Performance
        </span>
      </div>
    </div>
  );
}
