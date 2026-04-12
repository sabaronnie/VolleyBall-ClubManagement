import { useCallback, useEffect, useState } from "react";
import { fetchCurrentUser, fetchDirectorPaymentOverview } from "../api";
import ClubWorkspaceLayout from "../components/ClubWorkspaceLayout";
import { navigate } from "../navigation";

const AUTH_TOKEN_KEY = "netup.auth.token";
const CLUB_STORAGE_KEY = "netup.director.payment.club_id";

function money(cur, amount) {
  const n = Number(amount);
  if (Number.isNaN(n)) {
    return `${cur || "USD"} ${amount}`;
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency: cur || "USD" }).format(n);
}

function statusBadge(status) {
  if (status === "paid") {
    return <span className="vc-status-paid">Paid</span>;
  }
  if (status === "overdue") {
    return <span className="vc-status-overdue">Overdue</span>;
  }
  return <span className="vc-status-pending">Pending</span>;
}

export default function DashboardPage() {
  const [ownedClubs, setOwnedClubs] = useState([]);
  const [clubId, setClubId] = useState(null);
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [viewerAccountRole, setViewerAccountRole] = useState(null);
  const [hasPlayerTeams, setHasPlayerTeams] = useState(false);
  const [showCoachAttendanceTab, setShowCoachAttendanceTab] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
      navigate("/login");
    }
  }, []);

  const resolveClub = useCallback(async () => {
    const me = await fetchCurrentUser();
    setViewerAccountRole(me.user?.assigned_account_role || null);
    setHasPlayerTeams(Array.isArray(me.player_teams) && me.player_teams.length > 0);
    setShowCoachAttendanceTab(
      (me.coached_teams || []).some((t) => t.can_manage_training) ||
        (me.director_teams || []).some((t) => t.can_manage_training),
    );
    const clubs = me.owned_clubs || [];
    setOwnedClubs(clubs);
    if (!clubs.length) {
      setClubId(null);
      return;
    }
    const stored = sessionStorage.getItem(CLUB_STORAGE_KEY);
    const fromStore = stored ? Number(stored) : null;
    const pick =
      fromStore && clubs.some((c) => c.id === fromStore) ? fromStore : clubs[0].id;
    setClubId(pick);
  }, []);

  const loadOverview = useCallback(async () => {
    if (!clubId) {
      setOverview(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await fetchDirectorPaymentOverview(clubId);
      setOverview(data);
    } catch (err) {
      setError(err.message || "Could not load dashboard data.");
      setOverview(null);
    } finally {
      setLoading(false);
    }
  }, [clubId]);

  useEffect(() => {
    void resolveClub();
  }, [resolveClub]);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    setSuccessMessage("");
  }, [clubId]);

  const onClubSelect = (id) => {
    const n = Number(id);
    setClubId(n);
    sessionStorage.setItem(CLUB_STORAGE_KEY, String(n));
  };

  const rows = overview?.family_summaries || [];

  const kpis = overview?.kpis;

  return (
    <ClubWorkspaceLayout
      activeTab="dashboard"
      viewerAccountRole={viewerAccountRole}
      showPlayerSessionsTab={hasPlayerTeams}
      showCoachAttendanceTab={showCoachAttendanceTab}
    >
      {ownedClubs.length ? (
        <nav className="vc-dash-subnav" aria-label="Director shortcuts">
          <button type="button" className="vc-dash-subnav__link" onClick={() => navigate("/director/users")}>
            Registration
          </button>
          <span className="vc-dash-subnav__sep" aria-hidden="true">
            ·
          </span>
          <button
            type="button"
            className="vc-dash-subnav__link"
            onClick={() => navigate(`/director/payments?club_id=${clubId || ownedClubs[0]?.id || ""}`)}
          >
            Full payments
          </button>
          <span className="vc-dash-subnav__sep" aria-hidden="true">
            ·
          </span>
          <button
            type="button"
            className="vc-dash-subnav__link"
            onClick={() => navigate(`/director/payments/logs?club_id=${clubId || ownedClubs[0]?.id || ""}`)}
          >
            Payment logs
          </button>
          <span className="vc-dash-subnav__sep" aria-hidden="true">
            ·
          </span>
          <button type="button" className="vc-dash-subnav__link" onClick={() => navigate("/director/teams")}>
            Teams & roster
          </button>
          <span className="vc-dash-subnav__sep" aria-hidden="true">
            ·
          </span>
          <button type="button" className="vc-dash-subnav__link" onClick={() => navigate("/payments")}>
            Payment schedule
          </button>
        </nav>
      ) : null}
      {successMessage ? (
        <div className="vc-director-success" style={{ marginBottom: "1rem" }}>
          {successMessage}
        </div>
      ) : null}
      {error ? (
        <div className="vc-director-error" style={{ marginBottom: "1rem" }}>
          {error}
        </div>
      ) : null}

      {ownedClubs.length > 1 ? (
        <div className="vc-dash-team-field" style={{ marginBottom: "1rem", maxWidth: 360 }}>
          <label className="vc-dash-team-field__label" htmlFor="dash-club-select">
            Club
          </label>
          <select
            id="dash-club-select"
            className="vc-dash-team-select"
            value={clubId || ""}
            onChange={(e) => onClubSelect(e.target.value)}
          >
            {ownedClubs.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      <section className="vc-dash-kpi-card">
        <div className="vc-kpi">
          <span className="vc-kpi-icon" aria-hidden="true">
            👥
          </span>
          <div>
            <div className="vc-kpi-label">Registration</div>
            <div className="vc-kpi-value">
              {loading || !kpis ? "—" : `${kpis.registration_player_count} players`}
            </div>
          </div>
        </div>
        <div className="vc-kpi">
          <span className="vc-kpi-icon" aria-hidden="true">
            💲
          </span>
          <div>
            <div className="vc-kpi-label">Monthly revenue</div>
            <div className="vc-kpi-value">
              {loading || !kpis
                ? "—"
                : money(kpis.monthly_revenue_currency, kpis.monthly_revenue)}
            </div>
          </div>
        </div>
        <div className="vc-kpi">
          <span className="vc-kpi-icon" aria-hidden="true">
            📈
          </span>
          <div>
            <div className="vc-kpi-label">Attendance rate</div>
            <div className="vc-kpi-value">
              {loading || !kpis || kpis.attendance_rate == null
                ? "—"
                : `${Math.round(Number(kpis.attendance_rate) * 100) / 100}%`}
            </div>
          </div>
        </div>
        <div className="vc-kpi">
          <span className="vc-kpi-icon" aria-hidden="true">
            📋
          </span>
          <div>
            <div className="vc-kpi-label">Outstanding payments</div>
            <div className="vc-kpi-value">
              {loading || !kpis ? "—" : `${kpis.outstanding_payer_count} families`}
            </div>
          </div>
        </div>
      </section>

      <div className="vc-dash-row">
        <section className="vc-panel">
          <h2 className="vc-panel-title">Attendance trend (last 30 months)</h2>
          <div className="vc-chart-wrap">
            <p className="vc-modal__muted" style={{ margin: 0 }}>
              No attendance taken in the last 30 months.
            </p>
          </div>
        </section>

        <section className="vc-panel">
          <h2 className="vc-panel-title">Payments overview</h2>
          {loading ? (
            <p className="vc-modal__muted">Loading payment data…</p>
          ) : !clubId ? (
            <p className="vc-modal__muted">Create a club as director to see fee tracking.</p>
          ) : (
            <>
              <table className="vc-table">
                <thead>
                  <tr>
                    <th>Family</th>
                    <th>ID</th>
                    <th>Total remaining</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan={4} style={{ color: "#6b7580", fontWeight: 600 }}>
                        No outstanding family balances in the preview. Open <strong>Full payments</strong> for the
                        complete list.
                      </td>
                    </tr>
                  ) : (
                    rows.map((r) => (
                      <tr key={r.player_id}>
                        <td>{r.family_label}</td>
                        <td>{r.player_id}</td>
                        <td>{money(r.currency, r.total_remaining)}</td>
                        <td>{statusBadge(r.overall_status)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              <div className="vc-summary-head" style={{ marginTop: "0.75rem" }}>
                <span />
                <button
                  type="button"
                  className="vc-link-cyan"
                  disabled={!clubId}
                  onClick={() => navigate(`/director/payments?club_id=${clubId}`)}
                >
                  View all
                </button>
              </div>
            </>
          )}
        </section>
      </div>

      <div className="vc-actions-row">
        <button type="button" className="vc-action-btn" onClick={() => navigate("/director/users")}>
          <span>Manage registration</span>
          <span aria-hidden="true">›</span>
        </button>
        <button
          type="button"
          className="vc-action-btn"
          disabled={!clubId}
          onClick={() => navigate(`/director/payments/logs?club_id=${clubId || ""}`)}
        >
          <span>View logs</span>
          <span aria-hidden="true">›</span>
        </button>
      </div>

      <div className="vc-dash-bottom">
        <section className="vc-panel vc-roles-table">
          <h2 className="vc-panel-title">Roles and access</h2>
          <table className="vc-table">
            <thead>
              <tr>
                <th>Capability</th>
                <th>Coach</th>
                <th>Parents</th>
                <th>Player</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Attendance</td>
                <td className="vc-yes">Yes</td>
                <td className="vc-yes">Yes</td>
                <td className="vc-yes">Yes</td>
              </tr>
              <tr>
                <td>Payments</td>
                <td className="vc-no">No</td>
                <td className="vc-yes">Yes</td>
                <td className="vc-no">No</td>
              </tr>
              <tr>
                <td>Performance</td>
                <td className="vc-yes">Yes</td>
                <td className="vc-yes">Yes</td>
                <td className="vc-no">No</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section className="vc-panel">
          <div className="vc-summary-head">
            <h2 className="vc-panel-title" style={{ margin: 0 }}>
              Club summary
            </h2>
            <button type="button" className="vc-link-cyan" style={{ margin: 0 }} onClick={() => navigate("/director/teams")}>
              Manage teams
            </button>
          </div>
          <ul className="vc-summary-list">
            <li>
              <span>Active club</span>
              <strong>{overview?.club?.name || "—"}</strong>
            </li>
            <li>
              <span>Players on roster (club)</span>
              <strong>{kpis ? String(kpis.registration_player_count) : "—"}</strong>
            </li>
            <li>
              <span>Families with balance due</span>
              <strong>{kpis ? String(kpis.outstanding_payer_count) : "—"}</strong>
            </li>
            <li>
              <span>Collected this month</span>
              <strong>
                {kpis ? money(kpis.monthly_revenue_currency, kpis.monthly_revenue) : "—"}
              </strong>
            </li>
          </ul>
        </section>
      </div>
    </ClubWorkspaceLayout>
  );
}
