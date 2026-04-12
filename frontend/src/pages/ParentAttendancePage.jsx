import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchParentChildAttendanceHistory } from "../api";

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

export default function ParentAttendancePage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);
  /** "all" | stringified user id */
  const [childFilter, setChildFilter] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchParentChildAttendanceHistory();
      setPayload(data);
    } catch (err) {
      setError(err.message || "Could not load attendance.");
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const records = payload?.records || [];
  const linked = payload?.linked_children || [];
  const notice = payload?.message;

  const displayedRecords = useMemo(() => {
    if (childFilter === "all") return records;
    const id = Number(childFilter);
    if (!Number.isFinite(id)) return records;
    return records.filter((row) => Number(row.child?.id) === id);
  }, [records, childFilter]);

  const showChildColumn = linked.length > 1 && childFilter === "all";

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
            Confirmation status for practices and matches (newest first).
          </p>
        </div>
      </header>

      {linked.length > 1 ? (
        <div className="vc-dash-team-field" style={{ marginBottom: "1rem", maxWidth: 360 }}>
          <label className="vc-dash-team-field__label" htmlFor="parent-att-child-filter">
            View
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
