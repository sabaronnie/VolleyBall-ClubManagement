import { useEffect, useMemo, useState } from "react";
import { fetchParentChildPerformanceSummary } from "../api";

const METRIC_OPTIONS = [
  { key: "weightedScore", label: "Score" },
  { key: "points", label: "Points" },
  { key: "aces", label: "Aces" },
  { key: "blocks", label: "Blocks" },
  { key: "assists", label: "Assists" },
  { key: "digs", label: "Digs" },
  { key: "errors", label: "Errors" },
  { key: "serveEfficiency", label: "Serve Efficiency" },
];

function childDisplayName(child) {
  const name = [child?.first_name, child?.last_name].filter(Boolean).join(" ").trim();
  return name || child?.email || "Child";
}

function formatMetricValue(metricKey, value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  const numeric = Number(value);
  if (metricKey === "serveEfficiency") return `${numeric.toFixed(1)}%`;
  return numeric.toFixed(1);
}

function formatMatchDate(isoDate) {
  if (!isoDate) return "Unknown date";
  const dt = new Date(`${isoDate}T00:00:00`);
  if (!Number.isFinite(dt.getTime())) return isoDate;
  return dt.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function ParentStatisticsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);
  const [selectedChildId, setSelectedChildId] = useState(null);
  const [selectedMetricKey, setSelectedMetricKey] = useState("weightedScore");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    void fetchParentChildPerformanceSummary(selectedChildId)
      .then((data) => {
        if (!cancelled) {
          setPayload(data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setPayload(null);
          setError(err.message || "Could not load child statistics.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedChildId]);

  const linkedChildren = Array.isArray(payload?.linked_children) ? payload.linked_children : [];
  const selectedChild = payload?.selected_child || null;
  const showChildSelector = linkedChildren.length === 2;

  const rows = useMemo(() => {
    const historyRows = Array.isArray(payload?.history) ? payload.history : [];
    return historyRows.map((row) => ({
      matchId: row.match_id,
      scheduledDate: row.scheduled_date,
      opponent: row.opponent || "Opponent",
      teamName: row.team_name || "Team",
      weightedScore: Number(row.weighted_score || 0),
      points: Number(row.stats?.points_scored || 0),
      aces: Number(row.stats?.aces || 0),
      blocks: Number(row.stats?.blocks || 0),
      assists: Number(row.stats?.assists || 0),
      digs: Number(row.stats?.digs || 0),
      errors: Number(row.stats?.errors || 0),
      serveEfficiency: row.serve_efficiency != null ? Number(row.serve_efficiency) : null,
    }));
  }, [payload]);

  const selectedMetric = METRIC_OPTIONS.find((option) => option.key === selectedMetricKey) || METRIC_OPTIONS[0];
  const selectedMetricValues = rows
    .map((row) => row?.[selectedMetric.key])
    .filter((value) => value != null)
    .map((value) => Number(value));
  const selectedMetricAverage = selectedMetricValues.length
    ? (selectedMetricValues.reduce((sum, value) => sum + value, 0) / selectedMetricValues.length).toFixed(1)
    : null;

  const developmentNote = useMemo(() => {
    if (selectedMetricValues.length < 2) return "More matches are needed to show a development trend.";
    const mid = Math.floor(selectedMetricValues.length / 2);
    const early = selectedMetricValues.slice(0, mid || 1);
    const recent = selectedMetricValues.slice(mid || 1);
    const earlyAvg = early.reduce((sum, value) => sum + value, 0) / early.length;
    const recentAvg = recent.reduce((sum, value) => sum + value, 0) / recent.length;
    const delta = recentAvg - earlyAvg;
    if (Math.abs(delta) < 0.2) return `${selectedMetric.label} has stayed mostly steady recently.`;
    return delta > 0
      ? `${selectedMetric.label} is trending upward in recent matches.`
      : `${selectedMetric.label} has dipped in recent matches.`;
  }, [selectedMetric.label, selectedMetricValues]);

  const chartPoints = useMemo(() => {
    if (!rows.length) return null;
    const sorted = [...rows].sort((left, right) => {
      const leftMs = new Date(`${left.scheduledDate}T12:00:00`).getTime();
      const rightMs = new Date(`${right.scheduledDate}T12:00:00`).getTime();
      if (leftMs !== rightMs) return leftMs - rightMs;
      return Number(left.matchId) - Number(right.matchId);
    });
    const plotted = sorted.filter((row) => row?.[selectedMetric.key] != null);
    if (!plotted.length) return null;

    const width = 640;
    const height = 230;
    const padLeft = 56;
    const padRight = 20;
    const padTop = 18;
    const padBottom = 60;
    const chartWidth = width - padLeft - padRight;
    const chartHeight = height - padTop - padBottom;
    const values = plotted.map((row) => Number(row?.[selectedMetric.key] || 0));
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const yPadding = Math.max((maxValue - minValue) * 0.12, 1);
    const yMin = Math.max(0, minValue - yPadding);
    const yMax = maxValue + yPadding;
    const yRange = Math.max(yMax - yMin, 1);
    const xStep = plotted.length > 1 ? chartWidth / (plotted.length - 1) : 0;
    const points = plotted.map((row, index) => {
      const value = Number(row?.[selectedMetric.key] || 0);
      return {
        x: padLeft + index * xStep,
        y: padTop + (1 - (value - yMin) / yRange) * chartHeight,
        value,
        label: formatMatchDate(row.scheduledDate),
      };
    });
    const yTicks = Array.from({ length: 5 }, (_, index) => {
      const ratio = index / 4;
      return {
        y: padTop + ratio * chartHeight,
        value: yMax - ratio * (yMax - yMin),
      };
    });
    return {
      width,
      height,
      points,
      path: points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" "),
      yTicks,
      chartLeft: padLeft,
      chartRight: width - padRight,
      chartTop: padTop,
      chartBottom: height - padBottom,
      rotate: points.length > 6,
    };
  }, [rows, selectedMetric]);

  return (
    <section className="teams-page-shell">
      <header className="teams-page-header">
        <div
          className="teams-page-heading"
          style={{ display: "flex", justifyContent: "space-between", gap: "0.8rem", alignItems: "flex-start" }}
        >
          <div>
            <p className="teams-page-kicker">Parent</p>
            <h1>Statistics</h1>
            <p className="teams-page-subtitle">
              Follow your child&apos;s development with a simple performance summary over time.
            </p>
          </div>
          {showChildSelector ? (
            <label className="vc-modal__muted" style={{ display: "grid", gap: "0.25rem", minWidth: "220px" }}>
              <span style={{ fontSize: "0.82rem", textAlign: "right" }}>Child</span>
              <select
                className="vc-director-modal__select"
                value={String(selectedChildId || selectedChild?.id || "")}
                onChange={(event) => setSelectedChildId(Number(event.target.value))}
              >
                {linkedChildren.map((child) => (
                  <option key={child.id} value={String(child.id)}>
                    {childDisplayName(child)}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
      </header>

      <section className="vc-panel">
        {loading ? <p className="vc-modal__muted">Loading statistics…</p> : null}
        {error ? <p className="vc-modal__error">{error}</p> : null}
        {!loading && !error && payload?.message ? <p className="vc-modal__muted">{payload.message}</p> : null}

        {!loading && !error && !payload?.message && !rows.length ? (
          <p className="vc-modal__muted">
            No performance records yet for {childDisplayName(selectedChild)}. Stats appear once match performance is
            recorded.
          </p>
        ) : null}

        {!loading && !error && rows.length ? (
          <div style={{ display: "grid", gap: "0.9rem" }}>
            <div>
              <strong>{childDisplayName(selectedChild)}</strong>
              <p className="vc-modal__muted" style={{ margin: "0.2rem 0 0" }}>{selectedChild?.email || "—"}</p>
            </div>

            <div className="vc-dash-kpi-card" style={{ flexWrap: "wrap" }}>
              <div className="vc-kpi">
                <span className="vc-kpi-label">Matches tracked</span>
                <span className="vc-kpi-value">{payload?.summary?.matches ?? rows.length}</span>
              </div>
              <div className="vc-kpi">
                <span className="vc-kpi-label">Average score</span>
                <span className="vc-kpi-value">
                  {formatMetricValue("weightedScore", payload?.summary?.average_weighted_score)}
                </span>
              </div>
              <div className="vc-kpi">
                <span className="vc-kpi-label">Total points</span>
                <span className="vc-kpi-value">{payload?.summary?.points ?? "—"}</span>
              </div>
              <div className="vc-kpi">
                <span className="vc-kpi-label">Total aces</span>
                <span className="vc-kpi-value">{payload?.summary?.aces ?? "—"}</span>
              </div>
            </div>

            <label className="vc-modal__muted" style={{ display: "grid", gap: "0.25rem", maxWidth: "17rem" }}>
              <span style={{ fontSize: "0.82rem" }}>Progress metric</span>
              <select
                className="vc-director-modal__select"
                value={selectedMetricKey}
                onChange={(event) => setSelectedMetricKey(event.target.value)}
              >
                {METRIC_OPTIONS.map((option) => (
                  <option key={option.key} value={option.key}>{option.label}</option>
                ))}
              </select>
            </label>

            <p className="vc-modal__muted" style={{ margin: 0 }}>
              Average ({selectedMetric.label}):{" "}
              <strong>{selectedMetricAverage != null ? formatMetricValue(selectedMetric.key, selectedMetricAverage) : "—"}</strong>
              {" · "}
              {developmentNote}
            </p>

            {chartPoints ? (
              <section
                style={{
                  border: "1px solid #e4e7ec",
                  borderRadius: "10px",
                  padding: "0.7rem 0.8rem",
                  background: "#fbfcfe",
                }}
              >
                <h3 style={{ margin: "0 0 0.35rem", fontSize: "0.94rem" }}>{selectedMetric.label} trend over time</h3>
                <svg viewBox={`0 0 ${chartPoints.width} ${chartPoints.height}`} style={{ width: "100%", height: 220 }}>
                  {chartPoints.yTicks.map((tick) => (
                    <g key={`yt-${tick.y}`}>
                      <line
                        x1={chartPoints.chartLeft}
                        y1={tick.y}
                        x2={chartPoints.chartRight}
                        y2={tick.y}
                        stroke="#e5eaf1"
                        strokeWidth="1"
                      />
                      <text x={chartPoints.chartLeft - 8} y={tick.y + 3} fill="#6b7280" fontSize="10" textAnchor="end">
                        {formatMetricValue(selectedMetric.key, tick.value)}
                      </text>
                    </g>
                  ))}
                  <line
                    x1={chartPoints.chartLeft}
                    y1={chartPoints.chartBottom}
                    x2={chartPoints.chartRight}
                    y2={chartPoints.chartBottom}
                    stroke="#cfd8e3"
                    strokeWidth="1"
                  />
                  <line
                    x1={chartPoints.chartLeft}
                    y1={chartPoints.chartTop}
                    x2={chartPoints.chartLeft}
                    y2={chartPoints.chartBottom}
                    stroke="#cfd8e3"
                    strokeWidth="1"
                  />
                  <polyline fill="none" stroke="#2563eb" strokeWidth="2.5" points={chartPoints.path} />
                  {chartPoints.points.map((point, index) => (
                    <g key={`p-${index}`}>
                      <circle cx={point.x} cy={point.y} r="3.5" fill="#2563eb" />
                      <title>{`${point.label}: ${formatMetricValue(selectedMetric.key, point.value)}`}</title>
                    </g>
                  ))}
                  {chartPoints.points.map((point, index) =>
                    chartPoints.rotate ? (
                      <text
                        key={`x-${index}`}
                        x={point.x}
                        y={chartPoints.chartBottom + 18}
                        fill="#6b7280"
                        fontSize="10"
                        textAnchor="end"
                        transform={`rotate(-30 ${point.x} ${chartPoints.chartBottom + 18})`}
                      >
                        {point.label}
                      </text>
                    ) : (
                      <text
                        key={`x-${index}`}
                        x={point.x}
                        y={chartPoints.chartBottom + 18}
                        fill="#6b7280"
                        fontSize="10"
                        textAnchor="middle"
                      >
                        {point.label}
                      </text>
                    ),
                  )}
                </svg>
              </section>
            ) : null}

            <div style={{ overflowX: "auto" }}>
              <table className="vc-table" style={{ fontSize: "0.88rem", width: "100%" }}>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Team</th>
                    <th>Opponent</th>
                    <th>Score</th>
                    <th>Points</th>
                    <th>Aces</th>
                    <th>Blocks</th>
                    <th>Assists</th>
                    <th>Digs</th>
                    <th>Errors</th>
                    <th>Serve Efficiency</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.matchId}>
                      <td>{row.scheduledDate}</td>
                      <td>{row.teamName}</td>
                      <td>{row.opponent}</td>
                      <td>{row.weightedScore.toFixed(1)}</td>
                      <td>{row.points}</td>
                      <td>{row.aces}</td>
                      <td>{row.blocks}</td>
                      <td>{row.assists}</td>
                      <td>{row.digs}</td>
                      <td>{row.errors}</td>
                      <td>{formatMetricValue("serveEfficiency", row.serveEfficiency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </section>
    </section>
  );
}
