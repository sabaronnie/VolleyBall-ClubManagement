import { useCallback, useEffect, useMemo, useState } from "react";
import {
  confirmTrainingSession,
  fetchCurrentUser,
  fetchParentChildAttendanceHistory,
  fetchTeamTrainingSessions,
} from "../api";

function statusClass(status) {
  if (status === "present") return "vc-status-paid";
  if (status === "pending") return "vc-status-pending";
  if (status === "absent") return "vc-status-overdue";
  if (status === "cancelled") return "vc-modal__muted";
  return "";
}

function childDisplayName(child) {
  const name = [child?.first_name, child?.last_name].filter(Boolean).join(" ").trim();
  return name || child?.email || "Player";
}

function parseLocalDate(iso) {
  if (!iso || typeof iso !== "string") return null;
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

/** Build { childId, teamId, ... } rows from /me children, else from history records. */
function buildConfirmContexts(me, records) {
  if (me?.children?.length) {
    const out = [];
    for (const ch of me.children) {
      const u = ch.user;
      const cid = u?.id;
      if (!cid) continue;
      const name = [u.first_name, u.last_name].filter(Boolean).join(" ").trim() || u.email || "Player";
      for (const t of ch.teams || []) {
        if (t?.id == null) continue;
        out.push({
          key: `${cid}-${t.id}`,
          childId: cid,
          teamId: t.id,
          childName: name,
          teamName: t.name || `Team ${t.id}`,
        });
      }
    }
    if (out.length) return out;
  }
  const map = new Map();
  for (const row of records) {
    const cid = row.child?.id;
    const tid = row.team?.id;
    if (cid == null || tid == null) continue;
    const key = `${cid}-${tid}`;
    if (!map.has(key)) {
      map.set(key, {
        key,
        childId: cid,
        teamId: tid,
        childName: childDisplayName(row.child),
        teamName: row.team?.name || `Team ${tid}`,
      });
    }
  }
  return Array.from(map.values());
}

export default function ParentAttendancePage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);
  const [me, setMe] = useState(null);
  /** "all" | stringified user id */
  const [childFilter, setChildFilter] = useState("all");

  const [confirmContextKey, setConfirmContextKey] = useState("");
  const [sessionsPayload, setSessionsPayload] = useState(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState("");
  const [confirmingKey, setConfirmingKey] = useState("");
  const [confirmBanner, setConfirmBanner] = useState("");
  const [confirmBannerError, setConfirmBannerError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [data, meData] = await Promise.all([
        fetchParentChildAttendanceHistory(),
        fetchCurrentUser().catch(() => null),
      ]);
      setPayload(data);
      setMe(meData);
    } catch (err) {
      setError(err.message || "Could not load attendance.");
      setPayload(null);
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshHistoryAfterConfirm = useCallback(async () => {
    try {
      const data = await fetchParentChildAttendanceHistory();
      setPayload(data);
    } catch {
      /* keep existing table if refresh fails */
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const records = payload?.records || [];
  const linked = payload?.linked_children || [];
  const notice = payload?.message;

  const confirmContexts = useMemo(() => buildConfirmContexts(me, records), [me, records]);

  const activeConfirmContext = useMemo(() => {
    if (!confirmContexts.length) return null;
    const found = confirmContexts.find((c) => c.key === confirmContextKey);
    return found || confirmContexts[0];
  }, [confirmContexts, confirmContextKey]);

  useEffect(() => {
    if (!confirmContexts.length) {
      setConfirmContextKey("");
      return;
    }
    if (!confirmContextKey || !confirmContexts.some((c) => c.key === confirmContextKey)) {
      setConfirmContextKey(confirmContexts[0].key);
    }
  }, [confirmContexts, confirmContextKey]);

  const loadSessionsForContext = useCallback(async (teamId) => {
    if (!teamId) {
      setSessionsPayload(null);
      return;
    }
    setSessionsLoading(true);
    setSessionsError("");
    try {
      const data = await fetchTeamTrainingSessions(teamId);
      setSessionsPayload(data);
    } catch (err) {
      setSessionsPayload(null);
      setSessionsError(err.message || "Could not load sessions.");
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!activeConfirmContext?.teamId) {
      setSessionsPayload(null);
      return;
    }
    void loadSessionsForContext(activeConfirmContext.teamId);
  }, [activeConfirmContext?.teamId, loadSessionsForContext]);

  const today = useMemo(() => {
    const t = new Date();
    return new Date(t.getFullYear(), t.getMonth(), t.getDate());
  }, []);

  const upcomingForChild = useMemo(() => {
    if (!sessionsPayload?.sessions || !activeConfirmContext) return [];
    const cid = activeConfirmContext.childId;
    const list = [];
    for (const s of sessionsPayload.sessions) {
      const d = parseLocalDate(s.scheduled_date);
      if (d && d < today) continue;
      const row = (s.player_confirmations || []).find((p) => Number(p.player_id) === Number(cid));
      list.push({ session: s, childRow: row || null });
    }
    const byDate = (a, b) => {
      const da = parseLocalDate(a.session.scheduled_date);
      const db = parseLocalDate(b.session.scheduled_date);
      if (!da || !db) return 0;
      return da - db || String(a.session.start_time).localeCompare(String(b.session.start_time));
    };
    list.sort(byDate);
    return list;
  }, [sessionsPayload, activeConfirmContext, today]);

  const onConfirmForChild = async (sessionId, childId) => {
    setConfirmBanner("");
    setConfirmBannerError("");
    setConfirmingKey(`${sessionId}-${childId}`);
    try {
      await confirmTrainingSession(sessionId, childId);
      setConfirmBanner("Attendance saved for your child.");
      if (activeConfirmContext?.teamId) {
        await loadSessionsForContext(activeConfirmContext.teamId);
      }
      await refreshHistoryAfterConfirm();
    } catch (err) {
      setConfirmBannerError(err.message || "Could not confirm.");
    } finally {
      setConfirmingKey("");
    }
  };

  const displayedRecords = useMemo(() => {
    if (childFilter === "all") return records;
    const id = Number(childFilter);
    if (!Number.isFinite(id)) return records;
    return records.filter((row) => Number(row.child?.id) === id);
  }, [records, childFilter]);

  const showChildColumn = linked.length > 1 && childFilter === "all";

  const renderConfirmSection = () => {
    if (!confirmContexts.length) return null;

    return (
      <section className="team-training-panel" style={{ marginBottom: "2rem" }}>
        <div className="team-training-panel__header">
          <div>
            <p className="teams-page-kicker" style={{ marginBottom: "0.25rem" }}>
              Confirm for your child
            </p>
            <h2 style={{ fontSize: "1.15rem", margin: 0 }}>
              Upcoming sessions (under 14)
            </h2>
            <p className="vc-modal__muted" style={{ marginTop: "0.5rem", maxWidth: 640, lineHeight: 1.5 }}>
              If your child is under 14, you can confirm their attendance here. Teenagers with the Player account
              role usually confirm on <strong>My sessions</strong>.
            </p>
          </div>
        </div>

        {confirmContexts.length > 1 ? (
          <div className="vc-dash-team-field" style={{ marginBottom: "1rem", maxWidth: 420 }}>
            <label className="vc-dash-team-field__label" htmlFor="parent-confirm-context">
              Child &amp; team
            </label>
            <select
              id="parent-confirm-context"
              className="vc-dash-team-select"
              value={activeConfirmContext?.key || ""}
              onChange={(e) => setConfirmContextKey(e.target.value)}
            >
              {confirmContexts.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.childName} — {c.teamName}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        {confirmBanner ? <p className="vc-director-success" style={{ marginBottom: "0.65rem" }}>{confirmBanner}</p> : null}
        {confirmBannerError ? (
          <p className="schedule-feedback schedule-feedback--error" style={{ marginBottom: "0.65rem" }}>
            {confirmBannerError}
          </p>
        ) : null}

        {sessionsLoading ? (
          <p className="vc-modal__muted">Loading sessions…</p>
        ) : sessionsError ? (
          <p className="schedule-feedback schedule-feedback--error">{sessionsError}</p>
        ) : !upcomingForChild.length ? (
          <section className="training-empty-state">
            <h3>No upcoming sessions</h3>
            <p>When coaches schedule practices or matches for this team, they will appear here.</p>
          </section>
        ) : (
          <div className="training-session-list">
            {upcomingForChild.map(({ session, childRow }) => {
              const isCancelled = session.status === "cancelled";
              const canPress = Boolean(childRow?.can_confirm) && !isCancelled;
              const confirmed = Boolean(childRow?.is_confirmed);
              const busyKey = `${session.id}-${activeConfirmContext.childId}`;
              return (
                <article key={session.id} className="training-session-card">
                  <div className="training-session-card__top">
                    <div>
                      <div className="training-session-card__meta">
                        <span>{session.session_type_label || session.session_type}</span>
                        {confirmContexts.length > 1 ? (
                          <span className="training-status-badge">{activeConfirmContext.childName}</span>
                        ) : null}
                        {isCancelled ? (
                          <span className="training-status-badge training-status-badge--cancelled">Cancelled</span>
                        ) : null}
                      </div>
                      <h3>{session.title}</h3>
                      <p className="training-session-card__location">
                        {session.scheduled_date} · {session.start_time} – {session.end_time}
                        {session.location ? ` · ${session.location}` : ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="vc-action-btn"
                      disabled={!canPress || confirmingKey === busyKey}
                      onClick={() => void onConfirmForChild(session.id, activeConfirmContext.childId)}
                    >
                      {confirmingKey === busyKey
                        ? "Saving…"
                        : isCancelled
                          ? "Cancelled"
                          : confirmed
                            ? "Confirmed ✓"
                            : "Confirm attendance"}
                    </button>
                  </div>
                  {childRow ? (
                    <div className="training-confirmation-summary" style={{ marginTop: "0.75rem" }}>
                      <span>
                        {activeConfirmContext.childName}:{" "}
                        {confirmed ? (
                          <strong style={{ color: "#15803d" }}>Attending</strong>
                        ) : isCancelled ? (
                          <strong>—</strong>
                        ) : (
                          <strong style={{ color: "#b45309" }}>Not confirmed yet</strong>
                        )}
                      </span>
                      {childRow.confirmed_at ? (
                        <span className="vc-modal__muted" style={{ fontWeight: 600 }}>
                          Updated {new Date(childRow.confirmed_at).toLocaleString()}
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                  {!childRow?.can_confirm && !isCancelled && activeConfirmContext ? (
                    <p className="vc-modal__muted" style={{ marginTop: "0.65rem", fontSize: "0.88rem" }}>
                      You can only confirm here when your child is under 14 and linked to your account. Older players
                      confirm for themselves on <strong>My sessions</strong>.
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </section>
    );
  };

  if (loading) {
    return (
      <section className="teams-page-shell" style={{ paddingTop: "1rem" }}>
        <p className="vc-modal__muted">Loading attendance…</p>
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

  if (notice && !records.length) {
    return (
      <section className="teams-page-shell">
        <header className="teams-page-header">
          <div className="teams-page-heading">
            <p className="teams-page-kicker">Family</p>
            <h1>Child attendance</h1>
            <p className="teams-page-subtitle">{notice}</p>
          </div>
        </header>
        {renderConfirmSection()}
        <section className="schedule-empty-card">
          <h2>No attendance yet</h2>
          <p>When your linked player joins team sessions, their attendance will appear here.</p>
        </section>
      </section>
    );
  }

  if (!records.length && !notice) {
    return (
      <section className="teams-page-shell">
        <header className="teams-page-header">
          <div className="teams-page-heading">
            <p className="teams-page-kicker">Family</p>
            <h1>Child attendance</h1>
            <p className="teams-page-subtitle">
              Training and match sessions for{" "}
              {linked.length === 1
                ? `${linked[0].first_name || "your child"}'s teams`
                : "your linked players"}
              .
            </p>
          </div>
        </header>
        {renderConfirmSection()}
        <section className="schedule-empty-card">
          <h2>No sessions yet</h2>
          <p>There are no scheduled sessions on your linked players&apos; teams, or rosters are still being set up.</p>
        </section>
      </section>
    );
  }

  const filteredEmpty = records.length > 0 && displayedRecords.length === 0;

  return (
    <section className="teams-page-shell">
      <header className="teams-page-header">
        <div className="teams-page-heading">
          <p className="teams-page-kicker">Family</p>
          <h1>Child attendance</h1>
          <p className="teams-page-subtitle">
            Confirm upcoming sessions for young players, then review confirmation status (newest first in the table).
          </p>
        </div>
      </header>

      {renderConfirmSection()}

      {linked.length > 1 ? (
        <div className="vc-dash-team-field" style={{ marginBottom: "1rem", maxWidth: 360 }}>
          <label className="vc-dash-team-field__label" htmlFor="parent-att-child-filter">
            History — view
          </label>
          <select
            id="parent-att-child-filter"
            className="vc-dash-team-select"
            value={childFilter}
            onChange={(e) => setChildFilter(e.target.value)}
          >
            <option value="all">All children</option>
            {linked.map((c) => (
              <option key={c.id} value={String(c.id)}>
                {childDisplayName(c)}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      {filteredEmpty ? (
        <section className="schedule-empty-card">
          <h2>No rows for this child</h2>
          <p>Try &quot;All children&quot; or pick another player.</p>
        </section>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="vc-table" style={{ fontSize: "0.9rem" }}>
            <thead>
              <tr>
                <th>Date</th>
                {showChildColumn ? <th>Child</th> : null}
                <th>Type</th>
                <th>Session</th>
                <th>Time</th>
                <th>Location</th>
                <th>Team</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {displayedRecords.map((row) => (
                <tr key={`${row.session_id}-${row.child?.id}`}>
                  <td>{row.scheduled_date}</td>
                  {showChildColumn ? (
                    <td>{childDisplayName(row.child) || "—"}</td>
                  ) : null}
                  <td>{row.session_type_label || row.session_type}</td>
                  <td>{row.title}</td>
                  <td>
                    {row.start_time} – {row.end_time}
                  </td>
                  <td>{row.location || "—"}</td>
                  <td>{row.team?.name || "—"}</td>
                  <td>
                    <span className={statusClass(row.attendance_status)}>
                      {row.attendance_label || row.attendance_status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
