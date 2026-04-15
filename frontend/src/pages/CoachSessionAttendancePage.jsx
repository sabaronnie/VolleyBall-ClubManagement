import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  cancelTrainingSession,
  createTeamTrainingSession,
  fetchCoachTrainingSessionAttendance,
  fetchTeamAttendanceAnalytics,
  fetchTeamTrainingSessions,
  remindUnconfirmedTrainingSession,
} from "../api";

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

function engagementBadgeClass(flag) {
  if (flag === "high") return "vc-status-paid";
  if (flag === "low") return "vc-status-overdue";
  if (flag === "medium") return "vc-status-pending";
  return "vc-modal__muted";
}

function engagementLabel(flag) {
  if (flag === "high") return "Strong";
  if (flag === "low") return "Needs attention";
  if (flag === "medium") return "Steady";
  return "Not enough data";
}

function isoDateLocal(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function sessionHasStarted(session) {
  if (!session?.scheduled_date) return false;
  const startTime = typeof session.start_time === "string" && session.start_time ? session.start_time.slice(0, 5) : "00:00";
  const dt = new Date(`${session.scheduled_date}T${startTime}:00`);
  return Number.isFinite(dt.getTime()) ? dt.getTime() <= Date.now() : false;
}

export default function CoachSessionAttendancePage({ activeTeam }) {
  const teamId = activeTeam?.id && activeTeam.id !== "__all__" ? activeTeam.id : null;
  const defaultRange = useMemo(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - 84);
    return { start: isoDateLocal(start), end: isoDateLocal(end) };
  }, []);
  const [listPayload, setListPayload] = useState(null);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [detailPayload, setDetailPayload] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [analyticsStart, setAnalyticsStart] = useState(defaultRange.start);
  const [analyticsEnd, setAnalyticsEnd] = useState(defaultRange.end);
  const [analyticsGrouping, setAnalyticsGrouping] = useState("week");
  const [analyticsLastN, setAnalyticsLastN] = useState("");
  const [analyticsPayload, setAnalyticsPayload] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState("");
  const [analyticsExpanded, setAnalyticsExpanded] = useState(false);
  const [newSessionTitle, setNewSessionTitle] = useState("");
  const [newSessionDate, setNewSessionDate] = useState(() => isoDateLocal(new Date()));
  const [newSessionStart, setNewSessionStart] = useState("18:00");
  const [newSessionEnd, setNewSessionEnd] = useState("19:30");
  const [newSessionLocation, setNewSessionLocation] = useState("");
  const [newSessionNotifyPlayers, setNewSessionNotifyPlayers] = useState(true);
  const [newSessionNotifyParents, setNewSessionNotifyParents] = useState(true);
  const [createSessionBusy, setCreateSessionBusy] = useState(false);
  const [createSessionError, setCreateSessionError] = useState("");
  const titleInputRef = useRef(null);
  const [createSessionSuccess, setCreateSessionSuccess] = useState("");
  const [remindBusy, setRemindBusy] = useState(false);
  const [remindMessage, setRemindMessage] = useState("");
  const [remindError, setRemindError] = useState("");
  const [cancelBusy, setCancelBusy] = useState(false);
  const [cancelMessage, setCancelMessage] = useState("");
  const [cancelError, setCancelError] = useState("");

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
    setAnalyticsStart(defaultRange.start);
    setAnalyticsEnd(defaultRange.end);
    setAnalyticsGrouping("week");
    setAnalyticsLastN("");
    setAnalyticsExpanded(false);
    setAnalyticsPayload(null);
    setCreateSessionError("");
    setCreateSessionSuccess("");
    setRemindMessage("");
    setRemindError("");
    setCancelMessage("");
    setCancelError("");
  }, [teamId, defaultRange.start, defaultRange.end]);

  useEffect(() => {
    const syncCoachTeamFromUrl = () => {
      const path = window.location.pathname.replace(/\/$/, "") || "/";
      if (!path.endsWith("/coach/attendance")) {
        return;
      }
      const params = new URLSearchParams(window.location.search);
      const tr = params.get("team");
      const tid = tr ? Number(tr) : NaN;
      if (Number.isFinite(tid) && tid > 0) {
        window.dispatchEvent(new CustomEvent("netup-set-active-team", { detail: { teamId: tid } }));
      }
    };
    syncCoachTeamFromUrl();
    window.addEventListener("popstate", syncCoachTeamFromUrl);
    return () => window.removeEventListener("popstate", syncCoachTeamFromUrl);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tr = params.get("team");
    const sr = params.get("session");
    if (!teamId || !tr || String(teamId) !== String(Number(tr))) {
      return;
    }
    const sid = sr ? Number(sr) : NaN;
    if (Number.isFinite(sid) && sid > 0) {
      setSelectedSessionId(sid);
    }
  }, [teamId]);

  const loadAnalytics = useCallback(
    async (overrides) => {
      if (!teamId) {
        setAnalyticsPayload(null);
        return;
      }
      const startDate = overrides?.startDate ?? analyticsStart;
      const endDate = overrides?.endDate ?? analyticsEnd;
      const grouping = overrides?.grouping ?? analyticsGrouping;
      const rawLast = overrides?.lastNSessions ?? analyticsLastN;
      setAnalyticsLoading(true);
      setAnalyticsError("");
      try {
        const data = await fetchTeamAttendanceAnalytics(teamId, {
          startDate,
          endDate,
          grouping,
          lastNSessions: String(rawLast || "").trim() || undefined,
        });
        setAnalyticsPayload(data);
      } catch (err) {
        setAnalyticsPayload(null);
        setAnalyticsError(err.message || "Could not load attendance analytics.");
      } finally {
        setAnalyticsLoading(false);
      }
    },
    [teamId, analyticsStart, analyticsEnd, analyticsGrouping, analyticsLastN],
  );

  useEffect(() => {
    if (!teamId || !analyticsExpanded) {
      return;
    }
    // Load the default analytics when the panel is first expanded for this team.
    // We intentionally avoid depending on `loadAnalytics` here so updates to the
    // filter inputs (which change `loadAnalytics` identity) do not re-run this
    // effect and reset the view to defaults while the user is editing filters.
    void loadAnalytics({
      startDate: defaultRange.start,
      endDate: defaultRange.end,
      grouping: "week",
      lastNSessions: "",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [teamId, analyticsExpanded, defaultRange.start, defaultRange.end]);

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
    setRemindMessage("");
    setRemindError("");
    setCancelMessage("");
    setCancelError("");
    void loadDetail(selectedSessionId);
  }, [selectedSessionId, loadDetail]);

  const canManageTraining = Boolean(listPayload?.can_manage_training);

  const onCreateTrainingSession = useCallback(async () => {
    if (!teamId || !newSessionTitle.trim()) {
      setCreateSessionError("Enter a session title.");
      if (titleInputRef.current && typeof titleInputRef.current.focus === "function") {
        titleInputRef.current.focus();
      }
      return;
    }
    setCreateSessionBusy(true);
    setCreateSessionError("");
    setCreateSessionSuccess("");
    try {
      const startT = newSessionStart.length > 5 ? newSessionStart.slice(0, 5) : newSessionStart;
      const endT = newSessionEnd.length > 5 ? newSessionEnd.slice(0, 5) : newSessionEnd;
      await createTeamTrainingSession(teamId, {
        title: newSessionTitle.trim(),
        session_type: "training",
        scheduled_date: newSessionDate,
        start_time: startT,
        end_time: endT,
        location: newSessionLocation.trim(),
        notify_players: newSessionNotifyPlayers,
        notify_parents: newSessionNotifyParents,
      });
      setCreateSessionSuccess("Session added. Check notify options above if families should get an in-app alert.");
      setNewSessionTitle("");
      // signal other parts of the app (schedule page) to refresh
      try {
        window.dispatchEvent(new Event("netup-schedule-changed"));
      } catch (e) {
        // ignore if dispatch fails in some environments
      }
      await loadList();
    } catch (err) {
      setCreateSessionError(err.message || "Could not create session.");
    } finally {
      setCreateSessionBusy(false);
    }
  }, [
    teamId,
    newSessionTitle,
    newSessionDate,
    newSessionStart,
    newSessionEnd,
    newSessionLocation,
    newSessionNotifyPlayers,
    newSessionNotifyParents,
    loadList,
  ]);

  const sendAttendanceReminder = useCallback(
    async (audience) => {
      const sess = detailPayload?.session;
      if (!teamId || !sess || sess.status === "cancelled") {
        return;
      }
      setRemindBusy(true);
      setRemindError("");
      setRemindMessage("");
      try {
        const res = await remindUnconfirmedTrainingSession(sess.id, audience);
        const n = res.recipient_count ?? 0;
        const np = res.player_recipient_count ?? 0;
        const npar = res.parent_recipient_count ?? 0;
        if (n === 0) {
          setRemindMessage(res.message || "No matching recipients.");
        } else {
          const parts = [];
          if (np) parts.push(`${np} player${np === 1 ? "" : "s"}`);
          if (npar) parts.push(`${npar} parent${npar === 1 ? "" : "s"}`);
          setRemindMessage(`Sent to ${parts.join(" and ")} (${n} notification${n === 1 ? "" : "s"}).`);
        }
      } catch (err) {
        setRemindError(err.message || "Could not send reminder.");
      } finally {
        setRemindBusy(false);
      }
    },
    [teamId, detailPayload],
  );

  const onCancelSession = useCallback(async () => {
    const sess = detailPayload?.session;
    if (!teamId || !sess || sess.status === "cancelled" || sessionHasStarted(sess)) {
      return;
    }
    setCancelBusy(true);
    setCancelMessage("");
    setCancelError("");
    try {
      await cancelTrainingSession(sess.id);
      setCancelMessage("Session cancelled. It will no longer appear on the weekly schedule.");
      try {
        window.dispatchEvent(new Event("netup-schedule-changed"));
      } catch (e) {
        // ignore if dispatch fails in some environments
      }
      await loadList();
      await loadDetail(sess.id);
      if (analyticsExpanded) {
        await loadAnalytics();
      }
    } catch (err) {
      setCancelError(err.message || "Could not cancel session.");
    } finally {
      setCancelBusy(false);
    }
  }, [teamId, detailPayload, loadList, loadDetail, analyticsExpanded, loadAnalytics]);

  const today = useMemo(() => {
    const t = new Date();
    return new Date(t.getFullYear(), t.getMonth(), t.getDate());
  }, []);

  // custom grouping dropdown state
  const [groupOpen, setGroupOpen] = useState(false);
  const groupSelectRef = useRef(null);

  useEffect(() => {
    function onDocClick(e) {
      if (!groupSelectRef.current) return;
      if (!groupSelectRef.current.contains(e.target)) {
        setGroupOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
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
  const canCancelDetailSession =
    Boolean(canManageTraining && detailSession && detailSession.status !== "cancelled" && !sessionHasStarted(detailSession));

  return (
    <section className="teams-page-shell">
      <header className="teams-page-header">
        <div className="teams-page-heading">
          <p className="teams-page-kicker">Coaching</p>
          <h1>Session attendance</h1>
          <p className="teams-page-subtitle">
            Plan practices and matches for <strong>{listPayload?.team?.name || activeTeam?.name}</strong>. Schedule a
            session below so players and parents can confirm from their apps; open a session to review the roster and
            send reminders.
          </p>
        </div>
      </header>

      {canManageTraining ? (
        <section
          className="vc-coach-analytics-panel"
          style={{
            marginBottom: "1.25rem",
            padding: "1.1rem 1.25rem",
            borderRadius: "12px",
            border: "1px solid #e4e7ec",
            background: "#fff",
          }}
          aria-labelledby="coach-add-session-heading"
        >
          <h2 id="coach-add-session-heading" style={{ fontSize: "1.05rem", margin: "0 0 0.5rem" }}>
            Schedule a new session
          </h2>
          <p className="vc-modal__muted" style={{ margin: "0 0 1rem", fontSize: "0.88rem", lineHeight: 1.5 }}>
            Creates a practice on the team calendar and optionally notifies roster players and linked parents (same as
            other session alerts).
          </p>
          {createSessionSuccess ? (
            <p className="vc-director-success" style={{ marginBottom: "0.65rem" }}>
              {createSessionSuccess}
            </p>
          ) : null}
          {createSessionError ? (
            <p className="schedule-feedback schedule-feedback--error" style={{ marginBottom: "0.65rem" }}>
              {createSessionError}
            </p>
          ) : null}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: "0.65rem",
              alignItems: "end",
            }}
          >
            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.82rem" }}>
              <span className="vc-modal__muted">Title</span>
              <input
                ref={titleInputRef}
                className="vc-dash-team-select"
                value={newSessionTitle}
                onChange={(e) => setNewSessionTitle(e.target.value)}
                placeholder="e.g. Evening practice"
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.82rem" }}>
              <span className="vc-modal__muted">Date</span>
              <input
                type="date"
                className="vc-dash-team-select"
                value={newSessionDate}
                onChange={(e) => setNewSessionDate(e.target.value)}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.82rem" }}>
              <span className="vc-modal__muted">Start</span>
              <input
                type="time"
                className="vc-dash-team-select"
                value={newSessionStart}
                onChange={(e) => setNewSessionStart(e.target.value)}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.82rem" }}>
              <span className="vc-modal__muted">End</span>
              <input
                type="time"
                className="vc-dash-team-select"
                value={newSessionEnd}
                onChange={(e) => setNewSessionEnd(e.target.value)}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.82rem", gridColumn: "1 / -1" }}>
              <span className="vc-modal__muted">Location (optional)</span>
              <input
                className="vc-dash-team-select"
                value={newSessionLocation}
                onChange={(e) => setNewSessionLocation(e.target.value)}
                placeholder="Main gym"
              />
            </label>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", marginTop: "0.75rem", alignItems: "center" }}>
            <label className="session-toggle" style={{ fontSize: "0.88rem" }}>
              <input
                type="checkbox"
                checked={newSessionNotifyPlayers}
                onChange={(e) => setNewSessionNotifyPlayers(e.target.checked)}
              />
              <span className="vc-switch__track"><span className="vc-switch__thumb" /></span>
              <span>Notify players</span>
            </label>

            <label className="session-toggle" style={{ fontSize: "0.88rem" }}>
              <input
                type="checkbox"
                checked={newSessionNotifyParents}
                onChange={(e) => setNewSessionNotifyParents(e.target.checked)}
              />
              <span className="vc-switch__track"><span className="vc-switch__thumb" /></span>
              <span>Notify parents</span>
            </label>
          </div>
          <div style={{ marginTop: "0.85rem" }}>
            <button
              type="button"
              className="vc-action-btn"
              disabled={createSessionBusy}
              onClick={() => void onCreateTrainingSession()}
            >
              {createSessionBusy ? "Saving…" : "Add session"}
            </button>
          </div>
        </section>
      ) : null}

      {!analyticsExpanded ? (
        <div style={{ marginBottom: "1.25rem" }}>
          <button type="button" className="vc-action-btn" onClick={() => setAnalyticsExpanded(true)}>
            Show attendance trends &amp; player analytics
          </button>
        </div>
      ) : (
        <div style={{ marginBottom: "0.65rem" }}>
          <button
            type="button"
            className="vc-link-cyan"
            style={{ fontSize: "0.88rem", padding: 0, border: "none", background: "none", cursor: "pointer" }}
            onClick={() => setAnalyticsExpanded(false)}
          >
            Hide attendance trends
          </button>
        </div>
      )}

      {analyticsExpanded ? (
      <section
        className="vc-coach-analytics-panel"
        style={{
          marginBottom: "1.75rem",
          padding: "1.25rem 1.35rem",
          borderRadius: "12px",
          border: "1px solid #e4e7ec",
          background: "#fbfcfe",
        }}
        aria-labelledby="coach-analytics-heading"
      >
        <h2 id="coach-analytics-heading" style={{ fontSize: "1.08rem", margin: "0 0 0.75rem" }}>
          Attendance trends &amp; engagement
        </h2>
        <p className="vc-modal__muted" style={{ margin: "0 0 1rem", lineHeight: 1.55, fontSize: "0.9rem" }}>
          <span style={{ color: "#374151" }}>
            {analyticsPayload?.calculation_summary ||
              "Load analytics to see how attendance percentages are calculated for this team."}
          </span>
        </p>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "0.65rem",
            alignItems: "flex-end",
            marginBottom: "1rem",
          }}
        >
          <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.82rem" }}>
            <span className="vc-modal__muted">Start</span>
            <input
              type="date"
              className="vc-input"
              value={analyticsStart}
              onChange={(e) => setAnalyticsStart(e.target.value)}
              style={{ padding: "0.45rem 0.5rem", borderRadius: "8px", border: "1px solid #d0d5dd" }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.82rem" }}>
            <span className="vc-modal__muted">End</span>
            <input
              type="date"
              className="vc-input"
              value={analyticsEnd}
              onChange={(e) => setAnalyticsEnd(e.target.value)}
              style={{ padding: "0.45rem 0.5rem", borderRadius: "8px", border: "1px solid #d0d5dd" }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.82rem" }}>
            <span className="vc-modal__muted">Group trend by</span>
            <div
              className="vc-fake-select"
              ref={groupSelectRef}
            >
              <button
                type="button"
                className="vc-fake-select__btn"
                aria-haspopup="listbox"
                aria-expanded={groupOpen}
                onClick={() => setGroupOpen((v) => !v)}
              >
                {analyticsGrouping === "week" ? "Week" : "Session"}
                <span className="vc-fake-select__caret" aria-hidden>▾</span>
              </button>
              {groupOpen ? (
                <ul className="vc-fake-select__menu" role="listbox" tabIndex={-1}>
                  <li
                    role="option"
                    className="vc-fake-select__item"
                    onClick={() => {
                      setAnalyticsGrouping("week");
                      setGroupOpen(false);
                    }}
                  >
                    Week
                  </li>
                  <li
                    role="option"
                    className="vc-fake-select__item"
                    onClick={() => {
                      setAnalyticsGrouping("session");
                      setGroupOpen(false);
                    }}
                  >
                    Session
                  </li>
                </ul>
              ) : null}
            </div>
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.82rem" }}>
            <span className="vc-modal__muted">Last N closed sessions (optional)</span>
            <input
              type="number"
              min={1}
              placeholder="e.g. 8"
              value={analyticsLastN}
              onChange={(e) => setAnalyticsLastN(e.target.value)}
              style={{ padding: "0.45rem 0.5rem", borderRadius: "8px", border: "1px solid #d0d5dd", width: "7rem" }}
            />
          </label>
          <button
            type="button"
            className="vc-action-btn vc-action-btn--sm"
            onClick={() => void loadAnalytics()}
            disabled={analyticsLoading}
          >
            <span>{analyticsLoading ? "Refreshing…" : "Apply filters"}</span>
          </button>
        </div>
        {analyticsLoading && !analyticsPayload ? (
          <p className="vc-modal__muted">Loading analytics…</p>
        ) : null}
        {analyticsError ? <p className="schedule-feedback schedule-feedback--error">{analyticsError}</p> : null}
        {analyticsPayload && !analyticsError ? (
          <>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                gap: "0.75rem",
                marginBottom: "1.1rem",
              }}
            >
              <div style={{ padding: "0.75rem 1rem", background: "#fff", borderRadius: "10px", border: "1px solid #e4e7ec" }}>
                <div className="vc-modal__muted" style={{ fontSize: "0.78rem" }}>
                  Team avg (closed sessions)
                </div>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, marginTop: "0.2rem" }}>
                  {analyticsPayload.team_average_attendance_rate_percent != null
                    ? `${analyticsPayload.team_average_attendance_rate_percent}%`
                    : "—"}
                </div>
              </div>
              <div style={{ padding: "0.75rem 1rem", background: "#fff", borderRadius: "10px", border: "1px solid #e4e7ec" }}>
                <div className="vc-modal__muted" style={{ fontSize: "0.78rem" }}>
                  Closed sessions in scope
                </div>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, marginTop: "0.2rem" }}>
                  {analyticsPayload.closed_sessions_in_scope ?? 0}
                </div>
              </div>
              <div style={{ padding: "0.75rem 1rem", background: "#fff", borderRadius: "10px", border: "1px solid #e4e7ec" }}>
                <div className="vc-modal__muted" style={{ fontSize: "0.78rem" }}>
                  Roster players
                </div>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, marginTop: "0.2rem" }}>
                  {analyticsPayload.roster_player_count ?? 0}
                </div>
              </div>
            </div>
            {analyticsPayload.closed_sessions_in_scope === 0 ? (
              <section className="schedule-empty-card" style={{ marginBottom: "1rem" }}>
                <h3 style={{ marginTop: 0 }}>No completed sessions in this range</h3>
                <p style={{ marginBottom: 0 }}>
                  Adjust the dates or wait until sessions move into the past to see attendance rates. Upcoming sessions
                  still appear in the per-player pending counts when applicable.
                </p>
              </section>
            ) : null}
            {analyticsPayload.trend?.length ? (
              <div style={{ marginBottom: "1.15rem" }}>
                <h3 style={{ fontSize: "0.98rem", margin: "0 0 0.5rem" }}>Team trend</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                  {analyticsPayload.trend.map((row) => (
                    <div key={row.period_key} style={{ display: "flex", alignItems: "center", gap: "0.65rem" }}>
                      <span style={{ width: "8.5rem", flexShrink: 0, fontSize: "0.82rem" }} className="vc-modal__muted">
                        {row.label}
                      </span>
                      <div style={{ flex: 1, height: "10px", background: "#eef2f6", borderRadius: "6px", overflow: "hidden" }}>
                        <div
                          style={{
                            width: `${row.attendance_rate_percent != null ? row.attendance_rate_percent : 0}%`,
                            height: "100%",
                            background: "linear-gradient(90deg, #0d9488, #2563eb)",
                            borderRadius: "6px",
                          }}
                        />
                      </div>
                      <span style={{ width: "3.5rem", textAlign: "right", fontSize: "0.82rem", fontWeight: 700 }}>
                        {row.attendance_rate_percent != null ? `${row.attendance_rate_percent}%` : "—"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {analyticsPayload.players?.length ? (
              <div style={{ overflowX: "auto" }}>
                <table className="vc-table" style={{ fontSize: "0.88rem", width: "100%" }}>
                  <thead>
                    <tr>
                      <th>Player</th>
                      <th>Sessions (range)</th>
                      <th>Counted for %</th>
                      <th>Attended</th>
                      <th>Absent</th>
                      <th>Pending</th>
                      <th>Rate</th>
                      <th>Engagement</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analyticsPayload.players.map((row) => (
                      <tr key={row.player_id}>
                        <td>{row.player_name}</td>
                        <td>{row.sessions_in_date_range}</td>
                        <td>{row.sessions_counted_for_rate}</td>
                        <td>{row.attended_sessions}</td>
                        <td>{row.absent_sessions}</td>
                        <td>{row.pending_sessions}</td>
                        <td>{row.attendance_rate_percent != null ? `${row.attendance_rate_percent}%` : "—"}</td>
                        <td>
                          <span className={engagementBadgeClass(row.engagement_flag)}>
                            {engagementLabel(row.engagement_flag)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="vc-modal__muted">No players on this roster.</p>
            )}
          </>
        ) : null}
      </section>
      ) : null}

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
              {canManageTraining && detailSession.status !== "cancelled" ? (
                <section
                  style={{
                    marginBottom: "1rem",
                    padding: "0.85rem 1rem",
                    borderRadius: "10px",
                    border: "1px solid #e0e7ff",
                    background: "#f8faff",
                  }}
                  aria-labelledby="coach-remind-attendance-heading"
                >
                  <h4 id="coach-remind-attendance-heading" style={{ margin: "0 0 0.35rem", fontSize: "0.95rem" }}>
                    Remind who still needs to confirm
                  </h4>
                  <p className="vc-modal__muted" style={{ margin: "0 0 0.65rem", fontSize: "0.82rem", lineHeight: 1.5 }}>
                    In-app notifications go only to roster players (and their linked parents when allowed) who have{" "}
                    <strong>not</strong> confirmed yet. Parents are not included for past practices or cancelled
                    sessions.
                  </p>
                  {typeof detailSession.unconfirmed_roster_count === "number" ? (
                    <p style={{ margin: "0 0 0.65rem", fontSize: "0.84rem", fontWeight: 600 }}>
                      {detailSession.unconfirmed_roster_count} player
                      {detailSession.unconfirmed_roster_count === 1 ? "" : "s"} without confirmation
                    </p>
                  ) : null}
                  {detailSession.remind_parents_allowed === false ? (
                    <p className="vc-modal__muted" style={{ margin: "0 0 0.65rem", fontSize: "0.82rem" }}>
                      This session is already over—only players without a confirmation can be nudged (not parents).
                    </p>
                  ) : null}
                  {remindMessage ? <p className="vc-director-success" style={{ marginBottom: "0.5rem" }}>{remindMessage}</p> : null}
                  {remindError ? (
                    <p className="schedule-feedback schedule-feedback--error" style={{ marginBottom: "0.5rem" }}>
                      {remindError}
                    </p>
                  ) : null}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.45rem" }}>
                    <button
                      type="button"
                      className="vc-action-btn"
                      style={{ fontSize: "0.85rem", padding: "0.4rem 0.75rem" }}
                      disabled={remindBusy}
                      onClick={() => void sendAttendanceReminder("players")}
                    >
                      {remindBusy ? "Sending…" : "Notify unconfirmed players"}
                    </button>
                    <button
                      type="button"
                      className="vc-action-btn"
                      style={{ fontSize: "0.85rem", padding: "0.4rem 0.75rem" }}
                      disabled={remindBusy || detailSession.remind_parents_allowed === false}
                      title={
                        detailSession.remind_parents_allowed === false
                          ? "Parents are not notified for past or cancelled practices"
                          : undefined
                      }
                      onClick={() => void sendAttendanceReminder("parents")}
                    >
                      {remindBusy ? "Sending…" : "Notify parents (unconfirmed only)"}
                    </button>
                    <button
                      type="button"
                      className="vc-action-btn"
                      style={{ fontSize: "0.85rem", padding: "0.4rem 0.75rem" }}
                      disabled={remindBusy}
                      onClick={() => void sendAttendanceReminder("all")}
                    >
                      {remindBusy
                        ? "Sending…"
                        : detailSession.remind_parents_allowed === false
                          ? "Notify unconfirmed players only"
                          : "Notify players & parents (unconfirmed)"}
                    </button>
                  </div>
                </section>
              ) : null}
              {canManageTraining ? (
                <section
                  style={{
                    marginBottom: "1rem",
                    padding: "0.85rem 1rem",
                    borderRadius: "10px",
                    border: "1px solid #f1d2d2",
                    background: "#fff5f5",
                  }}
                  aria-labelledby="coach-cancel-session-heading"
                >
                  <h4 id="coach-cancel-session-heading" style={{ margin: "0 0 0.35rem", fontSize: "0.95rem" }}>
                    Session status
                  </h4>
                  {detailSession.status === "cancelled" ? (
                    <p className="vc-modal__muted" style={{ margin: 0, fontSize: "0.84rem", lineHeight: 1.5 }}>
                      This session has been cancelled. It should no longer appear in the weekly schedule, and cancelled
                      sessions are excluded from attendance-rate calculations.
                    </p>
                  ) : canCancelDetailSession ? (
                    <>
                      <p className="vc-modal__muted" style={{ margin: "0 0 0.65rem", fontSize: "0.84rem", lineHeight: 1.5 }}>
                        This session has not started yet. You can cancel it here to remove it from the schedule and
                        mark it as cancelled in the sessions list.
                      </p>
                      {cancelMessage ? <p className="vc-director-success" style={{ marginBottom: "0.5rem" }}>{cancelMessage}</p> : null}
                      {cancelError ? (
                        <p className="schedule-feedback schedule-feedback--error" style={{ marginBottom: "0.5rem" }}>
                          {cancelError}
                        </p>
                      ) : null}
                      <button
                        type="button"
                        className="vc-action-btn"
                        style={{ background: "linear-gradient(135deg, #d44b4b, #b83232)" }}
                        disabled={cancelBusy}
                        onClick={() => void onCancelSession()}
                      >
                        {cancelBusy ? "Cancelling..." : "Cancel session"}
                      </button>
                    </>
                  ) : (
                    <p className="vc-modal__muted" style={{ margin: 0, fontSize: "0.84rem", lineHeight: 1.5 }}>
                      Only sessions that have not started yet can be cancelled here.
                    </p>
                  )}
                </section>
              ) : null}
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
