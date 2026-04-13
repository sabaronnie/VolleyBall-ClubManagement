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
  const [isDirectorOrStaff, setIsDirectorOrStaff] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
      navigate("/login");
    }
  }, []);

  const resolveClub = useCallback(async () => {
    const me = await fetchCurrentUser();
    setIsDirectorOrStaff(Boolean(me.is_director_or_staff));
    setViewerAccountRole(me.user?.role || null);
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
  const activeClub =
    overview?.club ||
    ownedClubs.find((club) => club.id === clubId) ||
    ownedClubs[0] ||
    null;
  const attendanceTeams = overview?.attendance?.by_team || [];

  const shortcutLinks = [
    { label: "Users", onClick: () => navigate("/director/users") },
    {
      label: "Payments",
      onClick: () => navigate(`/director/payments?club_id=${clubId || ownedClubs[0]?.id || ""}`),
      disabled: !clubId && !ownedClubs[0]?.id,
    },
    {
      label: "Logs",
      onClick: () => navigate(`/director/payments/logs?club_id=${clubId || ownedClubs[0]?.id || ""}`),
      disabled: !clubId && !ownedClubs[0]?.id,
    },
    { label: "Teams", onClick: () => navigate("/director/teams") },
    { label: "Schedules", onClick: () => navigate("/payments") },
  ];

  const metricCards = [
    {
      label: "Registered players",
      value: loading || !kpis ? "—" : `${kpis.registration_player_count}`,
      note: "Active athletes in the club",
    },
    {
      label: "Monthly revenue",
      value: loading || !kpis ? "—" : money(kpis.monthly_revenue_currency, kpis.monthly_revenue),
      note: "Collected in the current billing window",
    },
    {
      label: "Attendance rate",
      value:
        loading || !kpis || kpis.attendance_rate == null
          ? "—"
          : `${Math.round(Number(kpis.attendance_rate) * 100) / 100}%`,
      note: "Rolling team average across recent closed sessions",
    },
    {
      label: "Families with balance",
      value: loading || !kpis ? "—" : `${kpis.outstanding_payer_count}`,
      note: "Accounts still carrying unpaid fees",
    },
  ];

  const actionCards = [
    {
      title: "Registration",
      description: "Approve people, manage accounts, and keep membership data tidy.",
      onClick: () => navigate("/director/users"),
    },
    {
      title: "Payment logs",
      description: "Review submitted receipts and confirm the payment timeline.",
      onClick: () => navigate(`/director/payments/logs?club_id=${clubId || ""}`),
      disabled: !clubId,
    },
    {
      title: "Teams",
      description: "Adjust rosters, coach assignments, and season structure.",
      onClick: () => navigate("/director/teams"),
    },
    {
      title: "Schedules",
      description: "Open fee schedules and recurring payment setup for the club.",
      onClick: () => navigate("/payments"),
    },
  ];

  const dashboardTitle = activeClub?.name || "Club dashboard";
  const dashboardSummary = loading
    ? "Pulling together your latest club numbers."
    : !clubId
      ? "Create or select a club to unlock payments, attendance, and team insights."
      : "Keep an eye on registrations, fee collection, and attendance without jumping between tools.";

  return (
    <ClubWorkspaceLayout
      activeTab="dashboard"
      viewerAccountRole={viewerAccountRole}
      showPlayerSessionsTab={hasPlayerTeams}
      showCoachAttendanceTab={showCoachAttendanceTab}
    >
      <section className="vc-dashboard-hero">
        <div className="vc-dashboard-hero__content">
          <div className="vc-dashboard-hero__copy">
            <span className="vc-dashboard-hero__eyebrow">Director workspace</span>
            <h1 className="vc-dashboard-hero__title">{dashboardTitle}</h1>
            <p className="vc-dashboard-hero__summary">{dashboardSummary}</p>
            <div className="vc-dashboard-hero__meta">
              <span className="vc-dashboard-chip">{loading ? "Syncing" : "Live overview"}</span>
              {activeClub?.name ? <span className="vc-dashboard-chip vc-dashboard-chip--soft">{activeClub.name}</span> : null}
              {ownedClubs.length > 1 ? (
                <span className="vc-dashboard-chip vc-dashboard-chip--soft">{ownedClubs.length} clubs linked</span>
              ) : null}
            </div>
          </div>

          {ownedClubs.length > 1 ? (
            <div className="vc-dashboard-hero__select-card">
              <label className="vc-dashboard-hero__select-label" htmlFor="dash-club-select">
                Active club
              </label>
              <select
                id="dash-club-select"
                className="vc-dashboard-hero__select"
                value={clubId || ""}
                onChange={(e) => onClubSelect(e.target.value)}
              >
                {ownedClubs.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <p className="vc-dashboard-hero__select-note">Switch clubs to refresh the overview instantly.</p>
            </div>
          ) : null}
        </div>

        {ownedClubs.length > 0 || isDirectorOrStaff ? (
          <nav className="vc-dash-subnav" aria-label="Director shortcuts">
            {shortcutLinks.map((item) => (
              <button
                key={item.label}
                type="button"
                className="vc-dash-subnav__link"
                disabled={item.disabled}
                onClick={item.onClick}
              >
                {item.label}
              </button>
            ))}
          </nav>
        ) : null}
      </section>

      {successMessage ? <div className="vc-director-success vc-dashboard-alert">{successMessage}</div> : null}
      {error ? <div className="vc-director-error vc-dashboard-alert">{error}</div> : null}

      <section className="vc-dashboard-metrics" aria-label="Club metrics">
        {metricCards.map((metric) => (
          <article key={metric.label} className="vc-dashboard-metric">
            <div className="vc-dashboard-metric__label">{metric.label}</div>
            <div className="vc-dashboard-metric__value">{metric.value}</div>
            <p className="vc-dashboard-metric__note">{metric.note}</p>
          </article>
        ))}
      </section>

      <div className="vc-dash-row vc-dash-row--dashboard">
        <section className="vc-panel vc-panel--dashboard">
          <div className="vc-dashboard-panel-head">
            <div>
              <p className="vc-dashboard-panel-head__eyebrow">Attendance</p>
              <h2 className="vc-panel-title">Team consistency</h2>
            </div>
            {!loading && attendanceTeams.length ? (
              <span className="vc-dashboard-inline-note">{attendanceTeams.length} tracked teams</span>
            ) : null}
          </div>
          <div className="vc-chart-wrap vc-chart-wrap--dashboard">
            {loading ? (
              <p className="vc-modal__muted" style={{ margin: 0 }}>
                Loading…
              </p>
            ) : !clubId || !overview?.attendance ? (
              <p className="vc-modal__muted" style={{ margin: 0 }}>
                Add training sessions to see team rates (about the last 12 weeks).
              </p>
            ) : (
              <>
                <p className="vc-dashboard-inline-copy">{overview.attendance.calculation_summary}</p>
                <ul className="vc-summary-list vc-summary-list--dashboard" style={{ margin: 0 }}>
                  {attendanceTeams.map((t) => (
                    <li key={t.team_id}>
                      <div className="vc-dashboard-rate-row">
                        <span>{t.team_name}</span>
                        {t.closed_roster_slots ? (
                          <span className="vc-dashboard-inline-note">
                            {t.closed_roster_slots} closed slots
                          </span>
                        ) : null}
                      </div>
                      <strong>
                        {t.average_rate_percent != null ? `${Number(t.average_rate_percent).toFixed(1)}%` : "—"}
                      </strong>
                    </li>
                  ))}
                </ul>
                {!attendanceTeams.length ? (
                  <p className="vc-modal__muted" style={{ margin: "0.75rem 0 0" }}>
                    No teams or no closed sessions in this window yet.
                  </p>
                ) : null}
              </>
            )}
          </div>
        </section>

        <section className="vc-panel vc-panel--dashboard">
          <div className="vc-dashboard-panel-head">
            <div>
              <p className="vc-dashboard-panel-head__eyebrow">Payments</p>
              <h2 className="vc-panel-title">Outstanding families</h2>
            </div>
            <button
              type="button"
              className="vc-link-cyan vc-link-cyan--compact"
              disabled={!clubId}
              onClick={() => navigate(`/director/payments?club_id=${clubId}`)}
            >
              View all
            </button>
          </div>
          {loading ? (
            <p className="vc-modal__muted">Loading payment data…</p>
          ) : !clubId ? (
            <p className="vc-modal__muted">Create a club as director to see fee tracking.</p>
          ) : (
            <>
              <div className="vc-dashboard-table-wrap">
                <table className="vc-table vc-table--dashboard">
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
              </div>
            </>
          )}
        </section>
      </div>

      <section className="vc-dashboard-actions" aria-label="Director actions">
        {actionCards.map((card) => (
          <button
            key={card.title}
            type="button"
            className="vc-dashboard-action-card"
            disabled={card.disabled}
            onClick={card.onClick}
          >
            <span className="vc-dashboard-action-card__eyebrow">Open</span>
            <span className="vc-dashboard-action-card__title">{card.title}</span>
            <span className="vc-dashboard-action-card__description">{card.description}</span>
            <span className="vc-dashboard-action-card__arrow" aria-hidden="true">
              ›
            </span>
          </button>
        ))}
      </section>

      <div className="vc-dash-bottom vc-dash-bottom--dashboard">
        <section className="vc-panel vc-panel--dashboard">
          <div className="vc-summary-head vc-summary-head--dashboard">
            <div>
              <p className="vc-dashboard-panel-head__eyebrow">Overview</p>
              <h2 className="vc-panel-title" style={{ margin: 0 }}>
                Club at a glance
              </h2>
            </div>
            <button type="button" className="vc-link-cyan vc-link-cyan--compact" style={{ margin: 0 }} onClick={() => navigate("/director/teams")}>
              Teams
            </button>
          </div>
          <ul className="vc-summary-list vc-summary-list--dashboard">
            <li>
              <span>Club</span>
              <strong>{overview?.club?.name || activeClub?.name || "—"}</strong>
            </li>
            <li>
              <span>Players</span>
              <strong>{kpis ? String(kpis.registration_player_count) : "—"}</strong>
            </li>
            <li>
              <span>Families with balance</span>
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

        <section className="vc-panel vc-panel--dashboard">
          <div className="vc-summary-head vc-summary-head--dashboard">
            <div>
              <p className="vc-dashboard-panel-head__eyebrow">Permissions</p>
              <h2 className="vc-panel-title" style={{ margin: 0 }}>
                Role capabilities
              </h2>
            </div>
          </div>
          <div className="vc-dashboard-inline-copy" style={{ marginBottom: "0.85rem" }}>
            Quick reference for who can work with attendance, payments, and performance tools.
          </div>
          <table className="vc-table vc-table--dashboard" style={{ fontSize: "0.88rem" }}>
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
      </div>
    </ClubWorkspaceLayout>
  );
}
