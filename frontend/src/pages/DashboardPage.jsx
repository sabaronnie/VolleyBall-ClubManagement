import { useCallback, useEffect, useState } from "react";
import { fetchCurrentUser, fetchDirectorPaymentOverview } from "../api";
import ClubWorkspaceLayout from "../components/ClubWorkspaceLayout";
import DirectorActionButtons from "../components/director/DirectorActionButtons";
import DirectorAttendanceTrendCard from "../components/director/DirectorAttendanceTrendCard";
import DirectorClubSummaryCard from "../components/director/DirectorClubSummaryCard";
import DirectorPaymentsOverviewCard from "../components/director/DirectorPaymentsOverviewCard";
import DirectorRolesPermissionCard from "../components/director/DirectorRolesPermissionCard";
import DirectorSummaryRow from "../components/director/DirectorSummaryRow";
import { navigate } from "../navigation";

const AUTH_TOKEN_KEY = "netup.auth.token";
const CLUB_STORAGE_KEY = "netup.director.payment.club_id";

export function formatMoney(cur, amount) {
  const n = Number(amount);
  if (Number.isNaN(n)) {
    return `${cur || "USD"} ${amount}`;
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency: cur || "USD" }).format(n);
}

export function formatPercent(rate) {
  if (rate == null || rate === "") {
    return "—";
  }
  const n = Number(rate);
  if (Number.isNaN(n)) {
    return "—";
  }
  return `${Math.round(n * 100) / 100}%`;
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

  const kpis = overview?.kpis;
  const activeClub =
    overview?.club ||
    ownedClubs.find((club) => club.id === clubId) ||
    ownedClubs[0] ||
    null;

  const paymentRows =
    overview?.payments_overview ??
    (overview?.family_summaries || []).map((b) => ({
      player_id: b.player_id,
      family_label: b.family_label,
      total_paid: b.total_paid,
      total_remaining: b.total_remaining,
      currency: b.currency,
      status: b.overall_status,
    }));

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

  const dashboardTitle = activeClub?.name || "Club dashboard";
  const dashboardSummary = loading
    ? "Pulling together your latest club numbers."
    : !clubId
      ? "Create or select a club to unlock payments, attendance, and team insights."
      : "Registrations, fee collection, and attendance in one director workspace.";

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
              {activeClub?.name ? (
                <span className="vc-dashboard-chip vc-dashboard-chip--soft">{activeClub.name}</span>
              ) : null}
              {ownedClubs.length > 1 ? (
                <span className="vc-dashboard-chip vc-dashboard-chip--soft">
                  {ownedClubs.length} clubs linked
                </span>
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

      <DirectorSummaryRow
        loading={loading}
        kpis={kpis}
        formatMoney={formatMoney}
        formatPercent={formatPercent}
      />

      <div className="vc-dash-row vc-dash-row--dashboard">
        <DirectorAttendanceTrendCard
          loading={loading}
          clubId={clubId}
          trend={overview?.attendance_trend_30d}
        />
        <DirectorPaymentsOverviewCard
          loading={loading}
          clubId={clubId}
          rows={paymentRows}
          formatMoney={formatMoney}
        />
      </div>

      <DirectorActionButtons clubId={clubId} />

      <div className="vc-dash-bottom vc-dash-bottom--dashboard">
        <DirectorRolesPermissionCard loading={loading} matrix={overview?.roles_permission_matrix} />
        <DirectorClubSummaryCard
          loading={loading}
          clubId={clubId}
          clubSummary={overview?.club_summary}
          formatMoney={formatMoney}
        />
      </div>
    </ClubWorkspaceLayout>
  );
}
