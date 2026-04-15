import { useCallback, useEffect, useMemo, useState } from "react";
import {
  confirmTrainingSession,
  fetchCurrentUser,
  fetchPlayerTeamAttendanceSummary,
  fetchTeamTrainingSessions,
  unconfirmTrainingSession,
} from "../api";

function parseLocalDate(iso) {
  if (!iso || typeof iso !== "string") return null;
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

export default function PlayerAttendancePage({ activeTeam }) {
  const [me, setMe] = useState(null);
  const [sessionsPayload, setSessionsPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [confirmingId, setConfirmingId] = useState(null);
  const [summaryPayload, setSummaryPayload] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");

  const teamId = activeTeam?.id && activeTeam.id !== "__all__" ? activeTeam.id : null;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchCurrentUser();
        if (!cancelled) setMe(data);
      } catch {
        if (!cancelled) setMe(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const myUserId = me?.user?.id;

  const loadSessions = useCallback(async () => {
    if (!teamId) {
      setSessionsPayload(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    setActionError("");
    try {
      const data = await fetchTeamTrainingSessions(teamId);
      setSessionsPayload(data);
    } catch (err) {
      setSessionsPayload(null);
      setError(err.message || "Could not load sessions.");
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (!teamId || !myUserId) {
      setSummaryPayload(null);
      setSummaryError("");
      return;
    }
    let cancelled = false;
    setSummaryLoading(true);
    setSummaryError("");
    void fetchPlayerTeamAttendanceSummary(teamId, myUserId)
      .then((data) => {
        if (!cancelled) setSummaryPayload(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setSummaryPayload(null);
          setSummaryError(err.message || "Could not load attendance summary.");
        }
      })
      .finally(() => {
        if (!cancelled) setSummaryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [teamId, myUserId]);

  const today = useMemo(() => {
    const t = new Date();
    return new Date(t.getFullYear(), t.getMonth(), t.getDate());
  }, []);

  const { upcomingSessions, pastSessions } = useMemo(() => {
    const sessions = sessionsPayload?.sessions || [];
    const upcoming = [];
    const past = [];
    for (const s of sessions) {
      const d = parseLocalDate(s.scheduled_date);
      if (!d) {
        upcoming.push(s);
        continue;
      }
      if (d >= today) upcoming.push(s);
      else past.push(s);
    }
    const byDate = (a, b) => {
      const da = parseLocalDate(a.scheduled_date);
      const db = parseLocalDate(b.scheduled_date);
      if (!da || !db) return 0;
      return da - db || String(a.start_time).localeCompare(String(b.start_time));
    };
    upcoming.sort(byDate);
    past.sort((a, b) => -byDate(a, b));
    return { upcomingSessions: upcoming, pastSessions: past };
  }, [sessionsPayload, today]);

  const onToggleConfirmation = async (sessionId, confirmed) => {
    setActionError("");
    setSuccessMessage("");
    setConfirmingId(sessionId);
    try {
      if (confirmed) {
        await unconfirmTrainingSession(sessionId, null);
        setSuccessMessage("Attendance confirmation removed.");
      } else {
        await confirmTrainingSession(sessionId, null);
        setSuccessMessage("Attendance saved.");
      }
      await loadSessions();
    } catch (err) {
      setActionError(err.message || "Could not update attendance.");
    } finally {
      setConfirmingId(null);
    }
  };

  const findMyRow = (session) => {
    if (!myUserId || !session?.player_confirmations) return null;
    return session.player_confirmations.find((row) => Number(row.player_id) === Number(myUserId)) || null;
  };

  if (!teamId) {
    return (
      <section className="teams-page-shell">
        <header className="teams-page-header">
          <div className="teams-page-heading">
            <p className="teams-page-kicker">Attendance</p>
            <h1>My sessions</h1>
            <p className="teams-page-subtitle">Choose a team in the toolbar to see practices and matches.</p>
          </div>
        </header>
        <section className="schedule-empty-card">
          <h2>No team selected</h2>
          <p>Select a team above to load upcoming sessions and confirm your attendance.</p>
        </section>
      </section>
    );
  }

  if (loading) {
    return (
      <section className="teams-page-shell" style={{ paddingTop: "1rem" }}>
        <p className="vc-modal__muted">Loading sessions…</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="teams-page-shell" style={{ paddingTop: "1rem" }}>
        <p className="schedule-feedback schedule-feedback--error">{error}</p>
      </section>
    );
  }

  return (
    <section className="teams-page-shell">
      <header className="teams-page-header">
        <div className="teams-page-heading">
          <p className="teams-page-kicker">Attendance</p>
          <h1>My sessions</h1>
          <p className="teams-page-subtitle">
            Upcoming training and matches for <strong>{sessionsPayload?.team?.name || activeTeam?.name}</strong>. Confirm
            so your coach knows you are coming.
          </p>
        </div>
      </header>

      {successMessage ? <p className="vc-director-success" style={{ margin: "0 0 0.75rem" }}>{successMessage}</p> : null}
      {actionError ? <p className="schedule-feedback schedule-feedback--error">{actionError}</p> : null}

      <section className="vc-panel" style={{ marginBottom: "1.25rem" }}>
        <h2 className="vc-panel-title" style={{ fontSize: "1.05rem" }}>
          Your attendance summary
        </h2>
        {summaryLoading ? (
          <p className="vc-modal__muted" style={{ margin: 0 }}>
            Loading summary…
          </p>
        ) : summaryError ? (
          <p className="schedule-feedback schedule-feedback--error" style={{ margin: 0 }}>
            {summaryError}
          </p>
        ) : summaryPayload?.player ? (
          <>
            <p className="vc-modal__muted" style={{ marginTop: 0, marginBottom: "0.75rem", fontSize: "0.88rem" }}>
              Last ~12 weeks on this team (from server). Cancelled sessions excluded; rate uses completed days only.
            </p>
            <div className="vc-dash-kpi-card" style={{ flexWrap: "wrap" }}>
              <div className="vc-kpi">
                <span className="vc-kpi-icon" aria-hidden="true">
                  ✅
                </span>
                <div>
                  <div className="vc-kpi-label">Attendance rate</div>
                  <div className="vc-kpi-value">
                    {summaryPayload.player.attendance_rate_percent != null
                      ? `${Number(summaryPayload.player.attendance_rate_percent).toFixed(1)}%`
                      : "—"}
                  </div>
                </div>
              </div>
              <div className="vc-kpi">
                <span className="vc-kpi-icon" aria-hidden="true">
                  📅
                </span>
                <div>
                  <div className="vc-kpi-label">Closed sessions counted</div>
                  <div className="vc-kpi-value">{summaryPayload.player.sessions_counted_for_rate ?? "—"}</div>
                </div>
              </div>
              <div className="vc-kpi">
                <span className="vc-kpi-icon" aria-hidden="true">
                  ⏳
                </span>
                <div>
                  <div className="vc-kpi-label">Pending (upcoming / today)</div>
                  <div className="vc-kpi-value">{summaryPayload.player.pending_sessions ?? "—"}</div>
                </div>
              </div>
            </div>
          </>
        ) : (
          <p className="vc-modal__muted" style={{ margin: 0 }}>
            No summary available.
          </p>
        )}
      </section>

      <div className="team-training-panel">
        <div className="team-training-panel__header">
          <h2 style={{ fontSize: "1.15rem", margin: 0 }}>Upcoming</h2>
        </div>
        {upcomingSessions.length ? (
          <div className="training-session-list">
            {upcomingSessions.map((session) => {
              const mine = findMyRow(session);
              const isCancelled = session.status === "cancelled";
              const canPress = Boolean(mine?.can_confirm) && !isCancelled;
              const confirmed = Boolean(mine?.is_confirmed);
              return (
                <article key={session.id} className="training-session-card">
                  <div className="training-session-card__top">
                    <div>
                      <div className="training-session-card__meta">
                        <span>{session.session_type_label || session.session_type}</span>
                        {isCancelled ? (
                          <span className="training-status-badge training-status-badge--cancelled">Cancelled</span>
                        ) : null}
                      </div>
                      <h3>{session.title}</h3>
                      <p className="training-session-card__location">
                        {session.scheduled_date} · {session.start_time} – {session.end_time}
                        {session.location ? ` · ${session.location}` : ""}
                      </p>
                      {session.session_type === "match" && session.opponent ? (
                        <p className="training-session-card__match-meta">vs {session.opponent}</p>
                      ) : null}
                    </div>
                    <button
                      type="button"
                      className="vc-action-btn"
                      disabled={!canPress || confirmingId === session.id}
                      onClick={() => void onToggleConfirmation(session.id, confirmed)}
                      title={confirmed ? "Click to unconfirm attendance" : "Confirm attendance"}
                    >
                      {confirmingId === session.id
                        ? "Saving…"
                        : isCancelled
                          ? "Cancelled"
                          : confirmed
                            ? "Confirmed ✓"
                            : "Confirm attendance"}
                    </button>
                  </div>
                  {mine ? (
                    <div className="training-confirmation-summary" style={{ marginTop: "0.75rem" }}>
                      <span>
                        Your status:{" "}
                        {confirmed ? (
                          <strong style={{ color: "#15803d" }}>Attending</strong>
                        ) : isCancelled ? (
                          <strong>—</strong>
                        ) : (
                          <strong style={{ color: "#b45309" }}>Not confirmed yet</strong>
                        )}
                      </span>
                      {mine.confirmed_at ? (
                        <span className="vc-modal__muted" style={{ fontWeight: 600 }}>
                          Updated {new Date(mine.confirmed_at).toLocaleString()}
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                  {!mine?.can_confirm && !isCancelled && myUserId ? (
                    <p className="vc-modal__muted" style={{ marginTop: "0.65rem", fontSize: "0.88rem" }}>
                      Self-confirmation is currently unavailable for your account. If a parent manages your permissions,
                      they may need to allow attendance confirmations first.
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : (
          <section className="training-empty-state">
            <h3>No upcoming sessions</h3>
            <p>When your coach schedules practices or matches, they will show up here.</p>
          </section>
        )}
      </div>

      {pastSessions.length ? (
        <div className="team-training-panel">
          <div className="team-training-panel__header">
            <h2 style={{ fontSize: "1.05rem", margin: 0 }}>Recent past</h2>
          </div>
          <div className="training-session-list">
            {pastSessions.slice(0, 8).map((session) => {
              const mine = findMyRow(session);
              const confirmed = Boolean(mine?.is_confirmed);
              return (
                <article key={session.id} className="training-session-card">
                  <div className="training-session-card__top">
                    <div>
                      <h3 style={{ fontSize: "1rem" }}>{session.title}</h3>
                      <p className="training-session-card__location">
                        {session.scheduled_date} · {session.start_time} – {session.end_time}
                      </p>
                    </div>
                    <span className={confirmed ? "vc-status-paid" : "vc-status-pending"}>
                      {confirmed ? "Confirmed" : "No confirmation"}
                    </span>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      ) : null}
    </section>
  );
}
