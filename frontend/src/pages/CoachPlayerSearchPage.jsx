import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchMatch,
  fetchPlayerTeamAttendanceSummary,
  fetchTeamMembers,
  fetchTeamTrainingSessions,
} from "../api";
import { navigate } from "../navigation";

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
const MAX_COMPARE_MATCHES = 2;
const MATCH_METRIC_KEYS = [
  "weightedScore",
  "points",
  "aces",
  "blocks",
  "assists",
  "digs",
  "errors",
  "serveEfficiency",
];

function dateTimeValue(session) {
  if (!session?.scheduled_date) return Number.NaN;
  const rawTime = typeof session?.start_time === "string" && session.start_time ? session.start_time.slice(0, 5) : "00:00";
  const dt = new Date(`${session.scheduled_date}T${rawTime}:00`);
  return dt.getTime();
}

function formatMatchDate(isoDate) {
  if (!isoDate) return "Unknown date";
  const dt = new Date(`${isoDate}T00:00:00`);
  if (!Number.isFinite(dt.getTime())) return isoDate;
  return dt.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatMetricValue(metricKey, value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "—";
  }
  const numeric = Number(value);
  if (metricKey === "serveEfficiency") {
    return `${numeric.toFixed(1)}%`;
  }
  return numeric.toFixed(1);
}

export default function CoachPlayerSearchPage({ activeTeam }) {
  const [urlTeamId, setUrlTeamId] = useState(null);
  const [selectedPlayerId, setSelectedPlayerId] = useState(null);
  const [selectedMetricKey, setSelectedMetricKey] = useState("weightedScore");
  const [selectedComparisonMatchIds, setSelectedComparisonMatchIds] = useState([]);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profilePayload, setProfilePayload] = useState(null);
  const activeTeamId =
    activeTeam?.id != null && activeTeam.id !== "__all__" ? Number(activeTeam.id) : null;
  const teamId = activeTeamId || urlTeamId;

  useEffect(() => {
    const syncFromUrl = () => {
      const path = window.location.pathname.replace(/\/$/, "") || "/";
      if (path !== "/coach/player-search") {
        return;
      }
      const params = new URLSearchParams(window.location.search);
      const urlTeam = Number(params.get("team"));
      const urlPlayer = Number(params.get("player"));
      if (Number.isFinite(urlTeam) && urlTeam > 0) {
        setUrlTeamId(urlTeam);
      } else {
        setUrlTeamId(null);
      }
      if (Number.isFinite(urlTeam) && urlTeam > 0 && urlTeam !== activeTeamId) {
        window.dispatchEvent(new CustomEvent("netup-set-active-team", { detail: { teamId: urlTeam } }));
      }
      if (Number.isFinite(urlPlayer) && urlPlayer > 0) {
        setSelectedPlayerId(urlPlayer);
      } else {
        setSelectedPlayerId(null);
      }
    };

    syncFromUrl();
    window.addEventListener("popstate", syncFromUrl);
    return () => window.removeEventListener("popstate", syncFromUrl);
  }, [activeTeamId]);

  const loadPlayerProfile = useCallback(async () => {
    if (!teamId || !selectedPlayerId) {
      setProfilePayload(null);
      setProfileError("");
      setProfileLoading(false);
      return;
    }

    let cancelled = false;
    setProfileLoading(true);
    setProfileError("");

    try {
      const [attendanceSummary, teamMembers, sessionsPayload] = await Promise.all([
        fetchPlayerTeamAttendanceSummary(teamId, selectedPlayerId),
        fetchTeamMembers(teamId).catch(() => null),
        fetchTeamTrainingSessions(teamId).catch(() => null),
      ]);

      if (cancelled) {
        return;
      }

      const rosterMembers = Array.isArray(teamMembers?.members) ? teamMembers.members : [];
      const selectedMember = rosterMembers.find(
        (row) => row?.membership?.role === "player" && Number(row?.user?.id) === Number(selectedPlayerId),
      );

      const sessions = Array.isArray(sessionsPayload?.sessions) ? sessionsPayload.sessions : [];
      const candidateMatches = sessions
        .filter((session) => session?.session_type === "match")
        .sort((left, right) => dateTimeValue(right) - dateTimeValue(left))
        .slice(0, 12);

      const matchDetails = await Promise.all(
        candidateMatches.map(async (session) => {
          try {
            const detail = await fetchMatch(session.id, teamId);
            return { session, detail };
          } catch {
            return null;
          }
        }),
      );

      if (cancelled) {
        return;
      }

      const performanceRows = matchDetails
        .filter(Boolean)
        .map((entry) => {
          const player = entry?.detail?.match?.players?.find(
            (row) => Number(row?.player_id) === Number(selectedPlayerId),
          );
          if (!player) return null;
          const stats = player.stats || {};
          const hasAnyStat = Object.values(stats).some((value) => Number(value || 0) > 0);
          if (!hasAnyStat && Number(player.weighted_score || 0) <= 0) {
            return null;
          }
          return {
            matchId: entry.session.id,
            scheduledDate: entry.session.scheduled_date,
            opponent: entry.session.opponent || entry.detail?.match?.opponent || "Opponent",
            weightedScore: Number(player.weighted_score || 0),
            points: Number(stats.points_scored || 0),
            aces: Number(stats.aces || 0),
            blocks: Number(stats.blocks || 0),
            assists: Number(stats.assists || 0),
            digs: Number(stats.digs || 0),
            errors: Number(stats.errors || 0),
            serveEfficiency:
              Number(stats.aces || 0) + Number(stats.errors || 0) > 0
                ? (Number(stats.aces || 0) / (Number(stats.aces || 0) + Number(stats.errors || 0))) * 100
                : null,
          };
        })
        .filter(Boolean)
        .sort((left, right) => dateTimeValue({ scheduled_date: left.scheduledDate }) - dateTimeValue({ scheduled_date: right.scheduledDate }));

      const totals = performanceRows.reduce(
        (acc, row) => ({
          matches: acc.matches + 1,
          weightedScore: acc.weightedScore + row.weightedScore,
          points: acc.points + row.points,
          aces: acc.aces + row.aces,
          blocks: acc.blocks + row.blocks,
          assists: acc.assists + row.assists,
          digs: acc.digs + row.digs,
          errors: acc.errors + row.errors,
        }),
        {
          matches: 0,
          weightedScore: 0,
          points: 0,
          aces: 0,
          blocks: 0,
          assists: 0,
          digs: 0,
          errors: 0,
        },
      );

      setProfilePayload({
        attendanceSummary,
        selectedMember,
        performanceRows,
        totals,
      });
    } catch (err) {
      if (!cancelled) {
        setProfilePayload(null);
        setProfileError(err.message || "Could not load player profile.");
      }
    } finally {
      if (!cancelled) {
        setProfileLoading(false);
      }
    }
  }, [teamId, selectedPlayerId]);

  useEffect(() => {
    void loadPlayerProfile();
  }, [loadPlayerProfile]);

  useEffect(() => {
    if (!teamId || !selectedPlayerId) {
      return undefined;
    }

    const refresh = () => {
      void loadPlayerProfile();
    };
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") {
        refresh();
      }
    };

    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    window.addEventListener("netup-player-performance-changed", refresh);
    return () => {
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
      window.removeEventListener("netup-player-performance-changed", refresh);
    };
  }, [teamId, selectedPlayerId, loadPlayerProfile]);

  const chartPoints = useMemo(() => {
    const sourceRows = profilePayload?.performanceRows || [];
    if (!sourceRows.length) {
      return null;
    }
    const metric = METRIC_OPTIONS.find((option) => option.key === selectedMetricKey) || METRIC_OPTIONS[0];

    const rows = [...sourceRows].sort((left, right) => {
      const leftMs = dateTimeValue({ scheduled_date: left.scheduledDate });
      const rightMs = dateTimeValue({ scheduled_date: right.scheduledDate });
      if (leftMs !== rightMs) {
        return leftMs - rightMs;
      }
      return Number(left.matchId) - Number(right.matchId);
    });

    const width = 640;
    const height = 240;
    const padLeft = 56;
    const padRight = 20;
    const padTop = 20;
    const padBottom = 64;
    const chartWidth = width - padLeft - padRight;
    const chartHeight = height - padTop - padBottom;
    const plottedRows = rows.filter((row) => row?.[metric.key] != null);
    if (!plottedRows.length) {
      return null;
    }
    const values = plottedRows.map((row) => Number(row?.[metric.key] || 0));
    const valueMin = Math.min(...values);
    const valueMax = Math.max(...values);
    const yPadding = Math.max((valueMax - valueMin) * 0.12, 1);
    const yMin = Math.max(0, valueMin - yPadding);
    const yMax = valueMax + yPadding;
    const yRange = Math.max(yMax - yMin, 1);
    const xStep = plottedRows.length > 1 ? chartWidth / (plottedRows.length - 1) : 0;
    const labelOccurrences = new Map();
    const points = plottedRows.map((row, index) => {
      const x = padLeft + index * xStep;
      const metricValue = Number(row?.[metric.key] || 0);
      const y = padTop + (1 - (metricValue - yMin) / yRange) * chartHeight;
      const baseLabel = `${formatMatchDate(row.scheduledDate)} · ${row.opponent || "Opponent"}`;
      const seenCount = labelOccurrences.get(baseLabel) || 0;
      labelOccurrences.set(baseLabel, seenCount + 1);
      const label = seenCount > 0 ? `${baseLabel} #${seenCount + 1}` : baseLabel;
      return {
        x,
        y,
        label,
        value: metricValue,
        shortLabel: `${formatMatchDate(row.scheduledDate)} #${index + 1}`,
      };
    });

    const yTicks = Array.from({ length: 5 }, (_, index) => {
      const ratio = index / 4;
      const tickValue = yMax - ratio * (yMax - yMin);
      const y = padTop + ratio * chartHeight;
      return { y, value: tickValue };
    });

    const rawLabelStep = Math.ceil(points.length / 6);
    const labelStep = Math.max(1, rawLabelStep);
    const xTicks = points
      .map((point, index) => ({ point, index }))
      .filter(({ index }) => index === 0 || index === points.length - 1 || index % labelStep === 0)
      .map(({ point }) => ({ x: point.x, label: point.shortLabel }));

    return {
      width,
      height,
      path: points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" "),
      points,
      yTicks,
      xTicks,
      chartLeft: padLeft,
      chartRight: width - padRight,
      chartTop: padTop,
      chartBottom: height - padBottom,
      metricLabel: metric.label,
      metricKey: metric.key,
      shouldRotateXLabels: points.length > 6,
    };
  }, [profilePayload?.performanceRows, selectedMetricKey]);

  const performanceRows = profilePayload?.performanceRows || [];
  const selectedMetric = METRIC_OPTIONS.find((option) => option.key === selectedMetricKey) || METRIC_OPTIONS[0];
  const performanceRowsById = useMemo(
    () => new Map(performanceRows.map((row) => [Number(row.matchId), row])),
    [performanceRows],
  );
  const selectedComparisonRows = useMemo(
    () =>
      selectedComparisonMatchIds
        .map((id) => performanceRowsById.get(Number(id)))
        .filter(Boolean),
    [performanceRowsById, selectedComparisonMatchIds],
  );
  const selectedComparisonRowsByDate = useMemo(
    () =>
      [...selectedComparisonRows].sort((left, right) => {
        const leftMs = dateTimeValue({ scheduled_date: left.scheduledDate });
        const rightMs = dateTimeValue({ scheduled_date: right.scheduledDate });
        if (leftMs !== rightMs) {
          return leftMs - rightMs;
        }
        return Number(left.matchId) - Number(right.matchId);
      }),
    [selectedComparisonRows],
  );
  const comparisonTrend = useMemo(() => {
    if (selectedComparisonRowsByDate.length < 2) {
      return null;
    }
    const first = selectedComparisonRowsByDate[0];
    const last = selectedComparisonRowsByDate[selectedComparisonRowsByDate.length - 1];
    const firstValue = Number(first?.[selectedMetric.key] || 0);
    const lastValue = Number(last?.[selectedMetric.key] || 0);
    const delta = lastValue - firstValue;
    const almostEqual = Math.abs(delta) < 0.001;
    const isLowerBetter = selectedMetric.key === "errors";
    if (almostEqual) {
      return {
        label: "Consistent",
        color: "#4b5563",
        deltaText: formatMetricValue(selectedMetric.key, 0),
      };
    }
    const improved = isLowerBetter ? delta < 0 : delta > 0;
    return {
      label: improved ? "Improved" : "Regressed",
      color: improved ? "#0f9f6e" : "#b42318",
      deltaText: `${delta > 0 ? "+" : ""}${formatMetricValue(selectedMetric.key, delta)}`,
    };
  }, [selectedComparisonRowsByDate, selectedMetric]);

  useEffect(() => {
    const validIds = new Set(performanceRows.map((row) => Number(row.matchId)));
    setSelectedComparisonMatchIds((current) => current.filter((id) => validIds.has(Number(id))));
  }, [performanceRows]);

  if (!teamId) {
    return (
      <section className="teams-page-shell">
        <header className="teams-page-header">
          <div className="teams-page-heading">
            <p className="teams-page-kicker">Coaching</p>
            <h1>Player Performance</h1>
            <p className="teams-page-subtitle">Select a coached team first to open a player performance profile.</p>
          </div>
        </header>
      </section>
    );
  }

  const attendancePlayer = profilePayload?.attendanceSummary?.player || null;
  const profileMember = profilePayload?.selectedMember || null;
  const totals = profilePayload?.totals || null;
  const avgWeightedScore =
    totals && totals.matches > 0 ? (totals.weightedScore / totals.matches).toFixed(1) : "—";
  const selectedMetricValues = performanceRows
    .map((row) => row?.[selectedMetric.key])
    .filter((value) => value != null)
    .map((value) => Number(value));
  const selectedMetricAverage = selectedMetricValues.length
    ? (selectedMetricValues.reduce((sum, value) => sum + value, 0) / selectedMetricValues.length).toFixed(1)
    : null;

  const toggleComparisonMatch = (matchId) => {
    const normalizedId = Number(matchId);
    setSelectedComparisonMatchIds((current) => {
      if (current.includes(normalizedId)) {
        return current.filter((id) => id !== normalizedId);
      }
      if (current.length >= MAX_COMPARE_MATCHES) {
        return current;
      }
      return [...current, normalizedId];
    });
  };

  return (
    <section className="teams-page-shell">
      <header className="teams-page-header">
        <div className="teams-page-heading">
          <p className="teams-page-kicker">Coaching</p>
          <h1>Player Performance</h1>
          <p className="teams-page-subtitle">
            Opened from Statistics for <strong>{activeTeam?.name}</strong>. This view auto-syncs with saved match stats.
          </p>
          <button
            type="button"
            className="vc-link-cyan"
            style={{
              marginTop: "0.55rem",
              width: "fit-content",
              border: "none",
              background: "none",
              padding: 0,
              fontSize: "0.9rem",
              cursor: "pointer",
            }}
            onClick={() => navigate("/dashboard")}
          >
            Back to Dashboard
          </button>
        </div>
      </header>

      <section className="vc-panel">
        <h2 className="vc-panel-title" style={{ fontSize: "1.05rem" }}>Player Profile</h2>
        {!selectedPlayerId ? (
          <p className="vc-modal__muted" style={{ margin: 0 }}>
            Open a player from Statistics search results to view their performance profile.
          </p>
        ) : profileLoading ? (
          <p className="vc-modal__muted" style={{ margin: 0 }}>Loading player profile…</p>
        ) : profileError ? (
          <p className="vc-modal__error" style={{ margin: 0 }}>{profileError}</p>
        ) : attendancePlayer ? (
          <div style={{ display: "grid", gap: "0.65rem" }}>
            <div><strong>{attendancePlayer.player_name || "Player"}</strong></div>
            <div className="vc-modal__muted">
              {profileMember?.user?.email || "—"}
              {profileMember?.membership?.role ? ` · ${profileMember.membership.role}` : ""}
            </div>
            <div>
              Attendance rate:{" "}
              <strong>
                {attendancePlayer.attendance_rate_percent != null
                  ? `${Number(attendancePlayer.attendance_rate_percent).toFixed(1)}%`
                  : "—"}
              </strong>
              {" · "}
              Sessions counted: <strong>{attendancePlayer.sessions_counted_for_rate ?? "—"}</strong>
              {" · "}
              Pending: <strong>{attendancePlayer.pending_sessions ?? "—"}</strong>
            </div>
            <div>
              Performance overview: Matches <strong>{totals?.matches ?? 0}</strong>
              {" · "}
              Avg score <strong>{avgWeightedScore}</strong>
              {" · "}
              Points <strong>{totals?.points ?? 0}</strong>
              {" · "}
              Aces <strong>{totals?.aces ?? 0}</strong>
              {" · "}
              Blocks <strong>{totals?.blocks ?? 0}</strong>
            </div>
            <div style={{ display: "grid", gap: "0.35rem", marginTop: "0.2rem" }}>
              <label className="vc-modal__muted" style={{ display: "grid", gap: "0.2rem", maxWidth: "17rem" }}>
                <span style={{ fontSize: "0.82rem" }}>Performance metric</span>
                <select
                  className="vc-director-modal__select"
                  value={selectedMetricKey}
                  onChange={(event) => setSelectedMetricKey(event.target.value)}
                >
                  {METRIC_OPTIONS.map((option) => (
                    <option key={option.key} value={option.key}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <p className="vc-modal__muted" style={{ margin: 0 }}>
                Selected metric average ({selectedMetric.label}):{" "}
                <strong>
                  {selectedMetricAverage != null
                    ? formatMetricValue(selectedMetric.key, selectedMetricAverage)
                    : "No data"}
                </strong>
              </p>
            </div>
            {chartPoints ? (
              <section
                style={{
                  marginTop: "0.35rem",
                  border: "1px solid #e4e7ec",
                  borderRadius: "10px",
                  padding: "0.7rem 0.8rem",
                  background: "#fbfcfe",
                }}
              >
                <h3 style={{ margin: "0 0 0.35rem", fontSize: "0.94rem" }}>
                  {chartPoints.metricLabel} trend over time
                </h3>
                <svg viewBox={`0 0 ${chartPoints.width} ${chartPoints.height}`} style={{ width: "100%", height: 220 }}>
                  {chartPoints.yTicks.map((tick) => (
                    <g key={`ytick-${tick.y}`}>
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
                  {chartPoints.points.map((point) => (
                    <g key={`${point.label}-${point.x}`}>
                      <circle cx={point.x} cy={point.y} r="3.5" fill="#2563eb" />
                      <title>{`${point.label}: ${formatMetricValue(selectedMetric.key, point.value)}`}</title>
                    </g>
                  ))}
                  {chartPoints.xTicks.map((tick) => (
                    chartPoints.shouldRotateXLabels ? (
                      <text
                        key={`xtick-${tick.x}`}
                        x={tick.x}
                        y={chartPoints.chartBottom + 18}
                        fill="#6b7280"
                        fontSize="10"
                        textAnchor="end"
                        transform={`rotate(-30 ${tick.x} ${chartPoints.chartBottom + 18})`}
                      >
                        {tick.label}
                      </text>
                    ) : (
                      <text
                        key={`xtick-${tick.x}`}
                        x={tick.x}
                        y={chartPoints.chartBottom + 18}
                        fill="#6b7280"
                        fontSize="10"
                        textAnchor="middle"
                      >
                        {tick.label}
                      </text>
                    )
                  ))}
                </svg>
              </section>
            ) : (
              <p className="vc-modal__muted" style={{ margin: "0.35rem 0 0" }}>
                No data available for {selectedMetric.label.toLowerCase()} in this player&apos;s recent matches.
              </p>
            )}
            {performanceRows.length ? (
              <div style={{ overflowX: "auto", marginTop: "0.35rem" }}>
                <div className="vc-modal__muted" style={{ marginBottom: "0.55rem" }}>
                  Select matches to compare ({selectedComparisonRows.length}/{MAX_COMPARE_MATCHES} selected)
                </div>
                <table className="vc-table" style={{ fontSize: "0.88rem", width: "100%" }}>
                  <thead>
                    <tr>
                      <th>Compare</th>
                      <th>Date</th>
                      <th>Opponent</th>
                      <th style={selectedMetricKey === "weightedScore" ? { background: "#eef4ff" } : undefined}>Score</th>
                      <th style={selectedMetricKey === "points" ? { background: "#eef4ff" } : undefined}>Pts</th>
                      <th style={selectedMetricKey === "aces" ? { background: "#eef4ff" } : undefined}>Aces</th>
                      <th style={selectedMetricKey === "blocks" ? { background: "#eef4ff" } : undefined}>Blocks</th>
                      <th style={selectedMetricKey === "assists" ? { background: "#eef4ff" } : undefined}>Assists</th>
                      <th style={selectedMetricKey === "digs" ? { background: "#eef4ff" } : undefined}>Digs</th>
                      <th style={selectedMetricKey === "errors" ? { background: "#eef4ff" } : undefined}>Errors</th>
                      <th style={selectedMetricKey === "serveEfficiency" ? { background: "#eef4ff" } : undefined}>Serve Efficiency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...performanceRows].reverse().map((row) => (
                      <tr key={row.matchId}>
                        <td>
                          <input
                            type="checkbox"
                            aria-label={`Compare match ${row.scheduledDate} vs ${row.opponent}`}
                            checked={selectedComparisonMatchIds.includes(Number(row.matchId))}
                            onChange={() => toggleComparisonMatch(row.matchId)}
                            disabled={
                              !selectedComparisonMatchIds.includes(Number(row.matchId)) &&
                              selectedComparisonMatchIds.length >= MAX_COMPARE_MATCHES
                            }
                          />
                        </td>
                        <td>{row.scheduledDate}</td>
                        <td>{row.opponent}</td>
                        <td style={selectedMetricKey === "weightedScore" ? { background: "#f5f8ff", fontWeight: 700 } : undefined}>
                          {row.weightedScore.toFixed(1)}
                        </td>
                        <td style={selectedMetricKey === "points" ? { background: "#f5f8ff", fontWeight: 700 } : undefined}>{row.points}</td>
                        <td style={selectedMetricKey === "aces" ? { background: "#f5f8ff", fontWeight: 700 } : undefined}>{row.aces}</td>
                        <td style={selectedMetricKey === "blocks" ? { background: "#f5f8ff", fontWeight: 700 } : undefined}>{row.blocks}</td>
                        <td style={selectedMetricKey === "assists" ? { background: "#f5f8ff", fontWeight: 700 } : undefined}>{row.assists}</td>
                        <td style={selectedMetricKey === "digs" ? { background: "#f5f8ff", fontWeight: 700 } : undefined}>{row.digs}</td>
                        <td style={selectedMetricKey === "errors" ? { background: "#f5f8ff", fontWeight: 700 } : undefined}>{row.errors}</td>
                        <td style={selectedMetricKey === "serveEfficiency" ? { background: "#f5f8ff", fontWeight: 700 } : undefined}>
                          {formatMetricValue("serveEfficiency", row.serveEfficiency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {selectedComparisonRows.length >= 2 ? (
              <section
                style={{
                  marginTop: "0.75rem",
                  border: "1px solid #e6e9ef",
                  borderRadius: "10px",
                  padding: "0.8rem",
                  background: "#fcfdff",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                  <h3 style={{ margin: 0, fontSize: "0.94rem" }}>Match comparison</h3>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.7rem", flexWrap: "wrap" }}>
                    {comparisonTrend ? (
                      <span className="vc-modal__muted">
                        {selectedMetric.label} trend:{" "}
                        <strong style={{ color: comparisonTrend.color }}>
                          {comparisonTrend.label} ({comparisonTrend.deltaText})
                        </strong>
                      </span>
                    ) : null}
                    <button
                      type="button"
                      className="team-card__button team-card__button--ghost"
                      style={{ padding: "0.45rem 0.75rem", fontSize: "0.82rem" }}
                      onClick={() => setSelectedComparisonMatchIds([])}
                    >
                      Clear selection
                    </button>
                  </div>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.45rem", marginTop: "0.6rem" }}>
                  {METRIC_OPTIONS.map((option) => (
                    <button
                      key={`metric-quick-${option.key}`}
                      type="button"
                      onClick={() => setSelectedMetricKey(option.key)}
                      style={{
                        border: "1px solid #d8dee8",
                        borderRadius: "999px",
                        padding: "0.3rem 0.65rem",
                        fontSize: "0.78rem",
                        fontWeight: 700,
                        cursor: "pointer",
                        color: selectedMetricKey === option.key ? "#1d4ed8" : "#374151",
                        background: selectedMetricKey === option.key ? "#eef4ff" : "#ffffff",
                      }}
                      aria-pressed={selectedMetricKey === option.key}
                      title={`Set trend metric to ${option.label}`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                <div style={{ overflowX: "auto", marginTop: "0.55rem" }}>
                  <table className="vc-table" style={{ fontSize: "0.86rem" }}>
                    <thead>
                      <tr>
                        <th>Metric</th>
                        {selectedComparisonRowsByDate.map((row, index) => (
                          <th key={`cmp-head-${row.matchId}`}>
                            {formatMatchDate(row.scheduledDate)} · {row.opponent || "Opponent"} #{index + 1}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {MATCH_METRIC_KEYS.map((metricKey) => {
                        const metricMeta = METRIC_OPTIONS.find((option) => option.key === metricKey);
                        return (
                          <tr key={`cmp-row-${metricKey}`}>
                            <td style={metricKey === selectedMetricKey ? { background: "#f5f8ff", fontWeight: 700 } : undefined}>
                              <button
                                type="button"
                                onClick={() => setSelectedMetricKey(metricKey)}
                                style={{
                                  border: "none",
                                  background: "none",
                                  padding: 0,
                                  font: "inherit",
                                  fontWeight: "inherit",
                                  color: "inherit",
                                  cursor: "pointer",
                                }}
                                title={`Compare trend by ${metricMeta?.label || metricKey}`}
                              >
                                {metricMeta?.label || metricKey}
                              </button>
                            </td>
                            {selectedComparisonRowsByDate.map((row) => (
                              <td
                                key={`cmp-cell-${metricKey}-${row.matchId}`}
                                style={metricKey === selectedMetricKey ? { background: "#f5f8ff", fontWeight: 700 } : undefined}
                              >
                                {formatMetricValue(metricKey, row?.[metricKey])}
                              </td>
                            ))}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            ) : selectedComparisonRows.length === 1 ? (
              <p className="vc-modal__muted" style={{ margin: "0.7rem 0 0" }}>
                Select one more match to compare this player&apos;s performance.
              </p>
            ) : null}
          </div>
        ) : (
          <p className="vc-modal__muted" style={{ margin: 0 }}>No profile data available for this player on the selected team.</p>
        )}
      </section>
    </section>
  );
}
