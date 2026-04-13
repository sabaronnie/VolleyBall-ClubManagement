import { useCallback, useEffect, useState } from "react";
import { createClub, fetchCurrentUser, fetchDirectorPaymentOverview } from "../api";
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

export function userHasAnyClubAffiliation(me) {
  if (!me || typeof me !== "object") {
    return false;
  }
  const owned = Array.isArray(me.owned_clubs) ? me.owned_clubs.length : 0;
  const dirTeams = Array.isArray(me.director_teams) ? me.director_teams.length : 0;
  const coachTeams = Array.isArray(me.coached_teams) ? me.coached_teams.length : 0;
  const playTeams = Array.isArray(me.player_teams) ? me.player_teams.length : 0;
  const childTeams = Array.isArray(me.children)
    ? me.children.some((c) => Array.isArray(c.teams) && c.teams.length > 0)
    : false;
  return owned + dirTeams + coachTeams + playTeams > 0 || childTeams;
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
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState("");
  const [hasAnyClubAffiliation, setHasAnyClubAffiliation] = useState(false);
  const [createClubOpen, setCreateClubOpen] = useState(false);
  const [createClubBusy, setCreateClubBusy] = useState(false);
  const [createClubError, setCreateClubError] = useState("");
  const [newClubName, setNewClubName] = useState("");
  const [newClubDescription, setNewClubDescription] = useState("");
  const [newClubCity, setNewClubCity] = useState("");
  const [newClubCountry, setNewClubCountry] = useState("");

  useEffect(() => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
      navigate("/login");
    }
  }, []);

  const resolveClub = useCallback(async () => {
    setProfileError("");
    try {
      const me = await fetchCurrentUser();
      setIsDirectorOrStaff(Boolean(me.is_director_or_staff));
      setViewerAccountRole(me.user?.role || null);
      setHasPlayerTeams(Array.isArray(me.player_teams) && me.player_teams.length > 0);
      setShowCoachAttendanceTab(
        (me.coached_teams || []).some((t) => t.can_manage_training) ||
          (me.director_teams || []).some((t) => t.can_manage_training),
      );
      setHasAnyClubAffiliation(userHasAnyClubAffiliation(me));
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
    } catch (err) {
      setProfileError(err.message || "Could not load your profile.");
      setOwnedClubs([]);
      setClubId(null);
      setHasAnyClubAffiliation(false);
    } finally {
      setProfileLoading(false);
    }
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

  const paymentRows = Array.isArray(overview?.payments_overview)
    ? overview.payments_overview
    : (overview?.family_summaries || []).map((b) => ({
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

  const showNoClubOnboarding = !profileLoading && !hasAnyClubAffiliation;
  const showDirectorWorkspace = !profileLoading && hasAnyClubAffiliation;
  const dashboardTitle = activeClub?.name || "Club dashboard";
  const dashboardSummary = loading
    ? "Pulling together your latest club numbers."
    : !clubId
      ? "Create or select a club to unlock payments, attendance, and team insights."
      : "Registrations, fee collection, and attendance in one director workspace.";

  const openCreateClubModal = () => {
    setCreateClubError("");
    setNewClubName("");
    setNewClubDescription("");
    setNewClubCity("");
    setNewClubCountry("");
    setCreateClubOpen(true);
  };

  const submitCreateClub = async (e) => {
    e.preventDefault();
    setCreateClubError("");
    const name = newClubName.trim();
    if (!name) {
      setCreateClubError("Club name is required.");
      return;
    }
    setCreateClubBusy(true);
    try {
      const payload = await createClub({
        name,
        description: newClubDescription.trim(),
        city: newClubCity.trim(),
        country: newClubCountry.trim(),
      });
      const createdId = payload?.club?.id;
      if (createdId != null) {
        sessionStorage.setItem(CLUB_STORAGE_KEY, String(createdId));
      }
      setCreateClubOpen(false);
      setSuccessMessage(payload?.message || "Club created successfully.");
      setProfileLoading(true);
      await resolveClub();
      window.dispatchEvent(new Event("netup-teams-changed"));
    } catch (err) {
      setCreateClubError(err.message || "Could not create club.");
    } finally {
      setCreateClubBusy(false);
    }
  };

  return (
    <ClubWorkspaceLayout
      activeTab="dashboard"
      viewerAccountRole={viewerAccountRole}
      showPlayerSessionsTab={hasPlayerTeams}
      showCoachAttendanceTab={showCoachAttendanceTab}
    >
      {profileError ? <div className="vc-director-error vc-dashboard-alert">{profileError}</div> : null}

      {profileLoading ? (
        <p className="vc-dashboard-profile-loading vc-modal__muted">Loading your workspace…</p>
      ) : null}

      {showNoClubOnboarding ? (
        <section className="vc-dashboard-onboarding" aria-labelledby="vc-onboarding-title">
          <div className="vc-dashboard-onboarding__card">
            <span className="vc-dashboard-onboarding__eyebrow">Director workspace</span>
            <h1 id="vc-onboarding-title" className="vc-dashboard-onboarding__title">
              No Club Yet
            </h1>
            <p className="vc-dashboard-onboarding__text">
              Create your club to start managing teams, schedules, attendance, and payments.
            </p>
            <button type="button" className="vc-dashboard-onboarding__cta" onClick={openCreateClubModal}>
              Create a Club
            </button>
          </div>
        </section>
      ) : null}

      {showDirectorWorkspace ? (
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
                {ownedClubs.length > 0 ? (
                  <button
                    type="button"
                    className="vc-dashboard-hero__ghost-btn"
                    onClick={openCreateClubModal}
                  >
                    Create another club
                  </button>
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
      ) : null}

      {successMessage ? <div className="vc-director-success vc-dashboard-alert">{successMessage}</div> : null}
      {error ? <div className="vc-director-error vc-dashboard-alert">{error}</div> : null}

      {showDirectorWorkspace ? (
        <>
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
        </>
      ) : null}

      {createClubOpen ? (
        <div
          className="vc-director-modal-backdrop"
          role="presentation"
          onClick={(ev) => {
            if (ev.target === ev.currentTarget && !createClubBusy) {
              setCreateClubOpen(false);
            }
          }}
        >
          <div
            className="vc-director-modal vc-director-modal--wide"
            role="dialog"
            aria-modal="true"
            aria-labelledby="vc-create-club-title"
            onClick={(ev) => ev.stopPropagation()}
          >
            <h3 id="vc-create-club-title">Create a club</h3>
            <p className="vc-director-modal__meta">
              You will be assigned as the club director and can invite coaches and players next.
            </p>
            <form onSubmit={submitCreateClub}>
              <label className="vc-director-modal__label" htmlFor="vc-create-club-name">
                Club name
              </label>
              <input
                id="vc-create-club-name"
                className="vc-director-modal__select"
                type="text"
                autoComplete="organization"
                value={newClubName}
                onChange={(ev) => setNewClubName(ev.target.value)}
                disabled={createClubBusy}
                required
              />
              <label className="vc-director-modal__label" htmlFor="vc-create-club-description">
                Description{" "}
                <span className="vc-director-modal__optional">(optional)</span>
              </label>
              <textarea
                id="vc-create-club-description"
                className="vc-director-modal__textarea"
                rows={3}
                value={newClubDescription}
                onChange={(ev) => setNewClubDescription(ev.target.value)}
                disabled={createClubBusy}
              />
              <label className="vc-director-modal__label" htmlFor="vc-create-club-city">
                City <span className="vc-director-modal__optional">(optional)</span>
              </label>
              <input
                id="vc-create-club-city"
                className="vc-director-modal__select"
                type="text"
                autoComplete="address-level2"
                value={newClubCity}
                onChange={(ev) => setNewClubCity(ev.target.value)}
                disabled={createClubBusy}
              />
              <label className="vc-director-modal__label" htmlFor="vc-create-club-country">
                Country <span className="vc-director-modal__optional">(optional)</span>
              </label>
              <input
                id="vc-create-club-country"
                className="vc-director-modal__select"
                type="text"
                autoComplete="country-name"
                value={newClubCountry}
                onChange={(ev) => setNewClubCountry(ev.target.value)}
                disabled={createClubBusy}
              />
              {createClubError ? <p className="vc-director-modal__error">{createClubError}</p> : null}
              <div className="vc-director-modal__actions">
                <button
                  type="button"
                  className="vc-director-modal__btn vc-director-modal__btn--ghost"
                  disabled={createClubBusy}
                  onClick={() => setCreateClubOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="vc-director-modal__btn" disabled={createClubBusy}>
                  {createClubBusy ? "Creating…" : "Create club"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </ClubWorkspaceLayout>
  );
}
