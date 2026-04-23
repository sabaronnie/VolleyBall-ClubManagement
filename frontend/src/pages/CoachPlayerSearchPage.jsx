import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchMatch,
  fetchPlayerTeamAttendanceSummary,
  fetchTeamMembers,
  fetchTeamTrainingSessions,
} from "../api";
import { navigate } from "../navigation";

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

export default function CoachPlayerSearchPage({ activeTeam }) {
  const teamId = activeTeam?.id && activeTeam.id !== "__all__" ? Number(activeTeam.id) : null;
  const [selectedPlayerId, setSelectedPlayerId] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profilePayload, setProfilePayload] = useState(null);

  useEffect(() => {
    if (!teamId) {
      setSelectedPlayerId(null);
      return;
    }

    const syncFromUrl = () => {
      const path = window.location.pathname.replace(/\/$/, "") || "/";
      if (path !== "/coach/player-search") {
        return;
      }
      const params = new URLSearchParams(window.location.search);
      const urlTeam = Number(params.get("team"));
      const urlPlayer = Number(params.get("player"));
      if (Number.isFinite(urlTeam) && urlTeam !== teamId) {
        window.dispatchEvent(new CustomEvent("netup-set-active-team", { detail: { teamId: urlTeam } }));
        return;
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
  }, [teamId]);

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

    return () => {
      cancelled = true;
    };
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
    const values = rows.map((row) => Number(row.weightedScore || 0));
    const valueMin = Math.min(...values);
    const valueMax = Math.max(...values);
    const yPadding = Math.max((valueMax - valueMin) * 0.12, 1);
    const yMin = Math.max(0, valueMin - yPadding);
    const yMax = valueMax + yPadding;
    const yRange = Math.max(yMax - yMin, 1);
    const xStep = rows.length > 1 ? chartWidth / (rows.length - 1) : 0;
    const labelOccurrences = new Map();
    const points = rows.map((row, index) => {
      const x = padLeft + index * xStep;
      const y = padTop + (1 - (Number(row.weightedScore || 0) - yMin) / yRange) * chartHeight;
      const baseLabel = `${formatMatchDate(row.scheduledDate)} · ${row.opponent || "Opponent"}`;
      const seenCount = labelOccurrences.get(baseLabel) || 0;
      labelOccurrences.set(baseLabel, seenCount + 1);
      const label = seenCount > 0 ? `${baseLabel} #${seenCount + 1}` : baseLabel;
      return {
        x,
        y,
        label,
        value: Number(row.weightedScore || 0),
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
    };
  }, [profilePayload?.performanceRows]);

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
  const performanceRows = profilePayload?.performanceRows || [];
  const totals = profilePayload?.totals || null;
  const avgWeightedScore =
    totals && totals.matches > 0 ? (totals.weightedScore / totals.matches).toFixed(1) : "—";

  return (
    <section className="teams-page-shell">
      <header className="teams-page-header">
        <div className="teams-page-heading">
          <p className="teams-page-kicker">Coaching</p>
          <h1>Player Performance</h1>
          <p className="teams-page-subtitle">
            Opened from Users for <strong>{activeTeam?.name}</strong>. This view auto-syncs with saved match stats.
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
            Open a player from the Users table using the `View Performance` button.
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
                <h3 style={{ margin: "0 0 0.35rem", fontSize: "0.94rem" }}>Performance trend (recent matches)</h3>
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
                        {tick.value.toFixed(1)}
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
                      <title>{`${point.label}: ${point.value.toFixed(1)}`}</title>
                    </g>
                  ))}
                  {chartPoints.xTicks.map((tick) => (
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
                  ))}
                </svg>
              </section>
            ) : (
              <p className="vc-modal__muted" style={{ margin: "0.35rem 0 0" }}>
                No completed match stats yet for this player.
              </p>
            )}
            {performanceRows.length ? (
              <div style={{ overflowX: "auto", marginTop: "0.35rem" }}>
                <table className="vc-table" style={{ fontSize: "0.88rem", width: "100%" }}>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Opponent</th>
                      <th>Score</th>
                      <th>Pts</th>
                      <th>Aces</th>
                      <th>Blocks</th>
                      <th>Assists</th>
                      <th>Digs</th>
                      <th>Errors</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...performanceRows].reverse().map((row) => (
                      <tr key={row.matchId}>
                        <td>{row.scheduledDate}</td>
                        <td>{row.opponent}</td>
                        <td>{row.weightedScore.toFixed(1)}</td>
                        <td>{row.points}</td>
                        <td>{row.aces}</td>
                        <td>{row.blocks}</td>
                        <td>{row.assists}</td>
                        <td>{row.digs}</td>
                        <td>{row.errors}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="vc-modal__muted" style={{ margin: 0 }}>No profile data available for this player on the selected team.</p>
        )}
      </section>
    </section>
  );
}
