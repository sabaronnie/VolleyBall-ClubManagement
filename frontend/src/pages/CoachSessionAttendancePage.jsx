import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCoachTrainingSessionAttendance, fetchTeamTrainingSessions } from "../api";

function parseLocalDate(iso) {
  if (!iso || typeof iso !== "string") return null;
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

function statusBadgeClass(status) {
  if (status === "present") return "vc-status-paid";
  if (status === "pending") return "vc-status-pending";
  if (status === "absent") return "vc-status-overdue";
  if (status === "cancelled") return "vc-modal__muted";
  return "";
}

export default function CoachSessionAttendancePage({ activeTeam }) {
  const teamId = activeTeam?.id && activeTeam.id !== "__all__" ? activeTeam.id : null;
  const [listPayload, setListPayload] = useState(null);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [detailPayload, setDetailPayload] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

  const loadList = useCallback(async () => {
    if (!teamId) {
      setListPayload(null);
      setListLoading(false);
      return;
    }
    setListLoading(true);
    setListError("");
    try {
      const data = await fetchTeamTrainingSessions(teamId);
      setListPayload(data);
    } catch (err) {
      setListPayload(null);
      setListError(err.message || "Could not load sessions.");
    } finally {
      setListLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    setSelectedSessionId(null);
    setDetailPayload(null);
    setDetailError("");
  }, [teamId]);

  const loadDetail = useCallback(async (sessionId) => {
    setDetailLoading(true);
    setDetailError("");
    try {
      const data = await fetchCoachTrainingSessionAttendance(sessionId);
      setDetailPayload(data);
    } catch (err) {
      setDetailPayload(null);
      setDetailError(err.message || "Could not load attendance.");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedSessionId) {
      setDetailPayload(null);
      return;
    }
    void loadDetail(selectedSessionId);
  }, [selectedSessionId, loadDetail]);

  const today = useMemo(() => {
    const t = new Date();
    return new Date(t.getFullYear(), t.getMonth(), t.getDate());
  }, []);

  const sortedSessions = useMemo(() => {
    const sessions = listPayload?.sessions || [];
    const copy = [...sessions];
    const byDate = (a, b) => {
      const da = parseLocalDate(a.scheduled_date);
      const db = parseLocalDate(b.scheduled_date);
      if (!da || !db) return 0;
      return db - da || String(b.start_time).localeCompare(String(a.start_time));
    };
    copy.sort(byDate);
    return copy;
  }, [listPayload]);

  if (!teamId) {
    return (
      <section className="teams-page-shell">
        <header className="teams-page-header">
          <div className="teams-page-heading">
            <p className="teams-page-kicker">Coaching</p>
            <h1>Session attendance</h1>
            <p className="teams-page-subtitle">Pick a team you coach in the toolbar to load practices and matches.</p>
          </div>
        </header>
        <section className="schedule-empty-card">
          <h2>No team selected</h2>
          <p>Coaches and directors with training access should choose a team first.</p>
        </section>
      </section>
    );
  }

  if (listLoading) {
    return (
      <section className="teams-page-shell" style={{ paddingTop: "1rem" }}>
        <p className="vc-modal__muted">Loading sessions…</p>
      </section>
    );
  }

  if (listError) {
    return (
      <section className="teams-page-shell" style={{ paddingTop: "1rem" }}>
        <p className="schedule-feedback schedule-feedback--error">{listError}</p>
      </section>
    );
  }

  const detailSession = detailPayload?.session;

  return (
    <section className="teams-page-shell">
      <header className="teams-page-header">
        <div className="teams-page-heading">
          <p className="teams-page-kicker">Coaching</p>
          <h1>Session attendance</h1>
          <p className="teams-page-subtitle">
            Plan practices and matches for <strong>{listPayload?.team?.name || activeTeam?.name}</strong>. Open a
            session to see the full roster with present, pending, and absent states.
          </p>
        </div>
      </header>

      <div className="coach-attendance-layout">
        <div className="team-training-panel">
          <div className="team-training-panel__header">
            <h2 style={{ fontSize: "1.05rem", margin: 0 }}>Sessions</h2>
          </div>
          {sortedSessions.length ? (
            <div className="training-session-list">
              {sortedSessions.map((session) => {
                const d = parseLocalDate(session.scheduled_date);
                const isPast = d && d < today;
                const active = Number(selectedSessionId) === Number(session.id);
                return (
                  <article
                    key={session.id}
                    className={`training-session-card${active ? " training-session-card--active" : ""}`}
                  >
                    <button
                      type="button"
                      onClick={() => setSelectedSessionId(session.id)}
                      className="coach-session-select-btn"
                      style={{
                        width: "100%",
                        textAlign: "left",
                        background: "transparent",
                        border: "none",
                        padding: 0,
                        cursor: "pointer",
                        font: "inherit",
                        color: "inherit",
                      }}
                    >
                      <div className="training-session-card__top">
                        <div>
                          <div className="training-session-card__meta">
                            <span>{session.session_type_label || session.session_type}</span>
                            {session.status === "cancelled" ? (
                              <span className="training-status-badge training-status-badge--cancelled">Cancelled</span>
                            ) : isPast ? (
                              <span className="vc-modal__muted" style={{ fontSize: "0.78rem" }}>
                                Past
                              </span>
                            ) : null}
                          </div>
                          <h3 style={{ margin: "0.35rem 0 0.25rem" }}>{session.title}</h3>
                          <p className="training-session-card__location">
                            {session.scheduled_date} · {session.start_time} – {session.end_time}
                            {session.location ? ` · ${session.location}` : ""}
                          </p>
                          {session.session_type === "match" && session.opponent ? (
                            <p className="training-session-card__match-meta">vs {session.opponent}</p>
                          ) : null}
                          <p className="vc-modal__muted" style={{ fontSize: "0.82rem", marginTop: "0.35rem" }}>
                            Confirmed {session.confirmed_count ?? 0} · Pending {session.pending_count ?? 0}
                          </p>
                        </div>
                      </div>
                    </button>
                  </article>
                );
              })}
            </div>
          ) : (
            <section className="training-empty-state">
              <h3>No sessions yet</h3>
              <p>When sessions are scheduled for this team, they will appear here.</p>
            </section>
          )}
        </div>

        <div className="team-training-panel">
          <div className="team-training-panel__header">
            <h2 style={{ fontSize: "1.05rem", margin: 0 }}>Roster &amp; status</h2>
          </div>
          {!selectedSessionId ? (
            <section className="schedule-empty-card" style={{ margin: 0 }}>
              <h3>Select a session</h3>
              <p>Choose a session on the left to load attendance for every roster player.</p>
            </section>
          ) : detailLoading ? (
            <p className="vc-modal__muted" style={{ padding: "0.5rem 0" }}>
              Loading attendance…
            </p>
          ) : detailError ? (
            <p className="schedule-feedback schedule-feedback--error">{detailError}</p>
          ) : detailSession ? (
            <div>
              <header style={{ marginBottom: "0.75rem" }}>
                <h3 style={{ fontSize: "1.1rem", margin: "0 0 0.25rem" }}>{detailSession.title}</h3>
                <p className="vc-modal__muted" style={{ margin: 0, lineHeight: 1.5 }}>
                  {detailSession.scheduled_date} · {detailSession.start_time} – {detailSession.end_time}
                  {detailSession.location ? ` · ${detailSession.location}` : ""}
                  <br />
                  {detailSession.session_type_label}
                  {detailSession.session_type === "match" && detailSession.opponent ? ` · vs ${detailSession.opponent}` : ""}
                  {detailSession.description ? (
                    <>
                      <br />
                      <span style={{ color: "#4b5563" }}>{detailSession.description}</span>
                    </>
                  ) : null}
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.65rem" }}>
                  <span className="vc-status-paid">Present {detailSession.summary?.present_count ?? 0}</span>
                  <span className="vc-status-pending">Pending {detailSession.summary?.pending_count ?? 0}</span>
                  <span className="vc-status-overdue">Absent {detailSession.summary?.absent_count ?? 0}</span>
                  {detailSession.summary?.cancelled_count ? (
                    <span className="vc-modal__muted">Cancelled {detailSession.summary.cancelled_count}</span>
                  ) : null}
                  <span className="vc-modal__muted">Roster {detailSession.summary?.roster_size ?? 0}</span>
                </div>
              </header>
              {detailSession.players?.length ? (
                <div style={{ overflowX: "auto" }}>
                  <table className="vc-table" style={{ fontSize: "0.9rem", width: "100%" }}>
                    <thead>
                      <tr>
                        <th>Player</th>
                        <th>#</th>
                        <th>Position</th>
                        <th>Status</th>
                        <th>Confirmed by</th>
                        <th>When</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detailSession.players.map((row) => (
                        <tr key={row.player_id}>
                          <td>{row.player_name}</td>
                          <td>{row.jersey_number != null ? row.jersey_number : "—"}</td>
                          <td>{row.primary_position || "—"}</td>
                          <td>
                            <span className={statusBadgeClass(row.attendance_status)}>{row.attendance_label}</span>
                          </td>
                          <td>{row.confirmed_by_name || "—"}</td>
                          <td>{row.confirmed_at ? new Date(row.confirmed_at).toLocaleString() : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <section className="training-empty-state">
                  <h3>No players on roster</h3>
                  <p>Add players to this team to plan attendance.</p>
                </section>
              )}
            </div>
          ) : null}
        </div>
      </div>

    </section>
  );
}
