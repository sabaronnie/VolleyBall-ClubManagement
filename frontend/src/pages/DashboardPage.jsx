import { useCallback, useEffect, useState } from "react";
import { createClub, fetchCurrentUser, fetchDirectorPaymentOverview } from "../api";
import ClubWorkspaceLayout from "../components/ClubWorkspaceLayout";
import DirectorAttendanceTrendCard from "../components/director/DirectorAttendanceTrendCard";
import DirectorClubSummaryCard from "../components/director/DirectorClubSummaryCard";
import DirectorPaymentsOverviewCard from "../components/director/DirectorPaymentsOverviewCard";
import DirectorRolesPermissionCard from "../components/director/DirectorRolesPermissionCard";
import DirectorSummaryRow from "../components/director/DirectorSummaryRow";
import CoachPaymentsPage from "./CoachPaymentsPage";
import DirectorPaymentLogsPage from "./DirectorPaymentLogsPage";
import DirectorPaymentsPage from "./DirectorPaymentsPage";
import DirectorTeamSetupPage from "./DirectorTeamSetupPage";
import DirectorUserManagementPage from "./DirectorUserManagementPage";

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

function CreateClubFieldLabel({ htmlFor, children, optional = false }) {
  return (
    <label className="vc-director-modal__label" htmlFor={htmlFor}>
      {children}
      {optional ? (
        <>
          {" "}
          <span className="vc-director-modal__optional">(optional)</span>
        </>
      ) : (
        <span className="vc-director-modal__required" aria-hidden="true">
          *
        </span>
      )}
    </label>
  );
}

function DashboardCreateClubCard({
  title,
  description,
  buttonLabel = "Create a Club",
  onOpen,
  className = "",
  titleId,
}) {
  const sectionClassName = className
    ? `vc-dashboard-onboarding ${className}`
    : "vc-dashboard-onboarding";

  return (
    <section className={sectionClassName} aria-labelledby={titleId}>
      <div className="vc-dashboard-onboarding__card">
        <span className="vc-dashboard-onboarding__eyebrow">Director workspace</span>
        <h1 id={titleId} className="vc-dashboard-onboarding__title">
          {title}
        </h1>
        <p className="vc-dashboard-onboarding__text">{description}</p>
        <button type="button" className="vc-dashboard-onboarding__cta" onClick={onOpen}>
          {buttonLabel}
        </button>
      </div>
    </section>
  );
}

function DirectorDashboardDropdown({
  id,
  title,
  description,
  isOpen,
  onToggle,
  children,
}) {
  return (
    <section className={`vc-dashboard-dropdown${isOpen ? " is-open" : ""}`}>
      <button
        id={`${id}-trigger`}
        type="button"
        className="vc-dashboard-dropdown__trigger"
        aria-expanded={isOpen}
        aria-controls={`${id}-panel`}
        onClick={onToggle}
      >
        <span>
          <strong>{title}</strong>
          <small>{description}</small>
        </span>
        <span className="vc-dashboard-dropdown__caret" aria-hidden="true">
          {isOpen ? "−" : "+"}
        </span>
      </button>
      {isOpen ? (
        <div id={`${id}-panel`} className="vc-dashboard-dropdown__panel" role="region" aria-labelledby={`${id}-trigger`}>
          {children}
        </div>
      ) : null}
    </section>
  );
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
  const [newClubShortName, setNewClubShortName] = useState("");
  const [newClubDescription, setNewClubDescription] = useState("");
  const [newClubContactEmail, setNewClubContactEmail] = useState("");
  const [newClubContactPhone, setNewClubContactPhone] = useState("");
  const [newClubWebsite, setNewClubWebsite] = useState("");
  const [newClubCity, setNewClubCity] = useState("");
  const [newClubCountry, setNewClubCountry] = useState("");
  const [newClubAddress, setNewClubAddress] = useState("");
  const [newClubFoundedYear, setNewClubFoundedYear] = useState("");
  const [openDirectorSection, setOpenDirectorSection] = useState("payments");

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
    setNewClubShortName("");
    setNewClubDescription("");
    setNewClubContactEmail("");
    setNewClubContactPhone("");
    setNewClubWebsite("");
    setNewClubCity("");
    setNewClubCountry("");
    setNewClubAddress("");
    setNewClubFoundedYear("");
    setCreateClubOpen(true);
  };

  const submitCreateClub = async (e) => {
    e.preventDefault();
    setCreateClubError("");
    const name = newClubName.trim();
    const shortName = newClubShortName.trim();
    const contactEmail = newClubContactEmail.trim().toLowerCase();
    const contactPhone = newClubContactPhone.trim();
    const website = newClubWebsite.trim();
    const country = newClubCountry.trim();
    const city = newClubCity.trim();
    const address = newClubAddress.trim();
    const foundedYearValue = newClubFoundedYear.trim();
    const currentYear = new Date().getFullYear();

    if (!name || !shortName || !contactEmail || !contactPhone || !country || !city || !address || !foundedYearValue) {
      setCreateClubError("Please fill in every required field.");
      return;
    }

    const foundedYear = Number(foundedYearValue);
    if (!Number.isInteger(foundedYear) || foundedYear < 1800 || foundedYear > currentYear) {
      setCreateClubError(`Founded year must be a whole number between 1800 and ${currentYear}.`);
      return;
    }

    setCreateClubBusy(true);
    try {
      const payload = await createClub({
        name,
        short_name: shortName,
        description: newClubDescription.trim(),
        contact_email: contactEmail,
        contact_phone: contactPhone,
        website,
        country,
        city,
        address,
        founded_year: foundedYear,
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

  const toggleDirectorSection = (sectionId) => {
    setOpenDirectorSection((current) => (current === sectionId ? "" : sectionId));
  };

  const openDirectorSectionPanel = (sectionId) => {
    setOpenDirectorSection(sectionId);
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
        <DashboardCreateClubCard
          titleId="vc-onboarding-title"
          title="No Club Yet"
          description="Create your club to start managing teams, schedules, attendance, and payments."
          onOpen={openCreateClubModal}
        />
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
              onViewAll={() => openDirectorSectionPanel("payments")}
            />
          </div>

          <div className="vc-dash-bottom vc-dash-bottom--dashboard">
            <DirectorRolesPermissionCard loading={loading} matrix={overview?.roles_permission_matrix} />
            <DirectorClubSummaryCard
              loading={loading}
              clubId={clubId}
              clubSummary={overview?.club_summary}
              formatMoney={formatMoney}
              onManageTeams={() => openDirectorSectionPanel("teams")}
            />
          </div>

          <section className="vc-dashboard-toolbox" aria-labelledby="vc-dashboard-toolbox-title">
            <div className="vc-dashboard-toolbox__header">
              <div>
                <p className="vc-dashboard-panel-head__eyebrow">Workspace Tools</p>
                <h2 id="vc-dashboard-toolbox-title" className="vc-panel-title">
                  Director Tools
                </h2>
              </div>
              <p className="vc-modal__muted">
                Expand a section below to manage users, payments, logs, teams, and payment schedules without leaving
                the dashboard.
              </p>
            </div>

            <DirectorDashboardDropdown
              id="dashboard-users"
              title="Users"
              description="Manage roles and review parent-child link requests."
              isOpen={openDirectorSection === "users"}
              onToggle={() => toggleDirectorSection("users")}
            >
              <DirectorUserManagementPage embedded onOpenPayments={() => openDirectorSectionPanel("payments")} />
            </DirectorDashboardDropdown>

            <DirectorDashboardDropdown
              id="dashboard-payments"
              title="Payments"
              description="Review balances, send reminders, and record payments."
              isOpen={openDirectorSection === "payments"}
              onToggle={() => toggleDirectorSection("payments")}
            >
              <DirectorPaymentsPage
                embedded
                preferredClubId={clubId}
                onOpenUsers={() => openDirectorSectionPanel("users")}
                onOpenLogs={() => openDirectorSectionPanel("logs")}
              />
            </DirectorDashboardDropdown>

            <DirectorDashboardDropdown
              id="dashboard-logs"
              title="Logs"
              description="Audit recent payment activity for the active club."
              isOpen={openDirectorSection === "logs"}
              onToggle={() => toggleDirectorSection("logs")}
            >
              <DirectorPaymentLogsPage
                embedded
                preferredClubId={clubId}
                onOpenPayments={() => openDirectorSectionPanel("payments")}
              />
            </DirectorDashboardDropdown>

            <DirectorDashboardDropdown
              id="dashboard-teams"
              title="Teams"
              description="Create teams and manage roster assignments."
              isOpen={openDirectorSection === "teams"}
              onToggle={() => toggleDirectorSection("teams")}
            >
              <DirectorTeamSetupPage
                embedded
                preferredClubId={clubId}
                onOpenUsers={() => openDirectorSectionPanel("users")}
              />
            </DirectorDashboardDropdown>

            <DirectorDashboardDropdown
              id="dashboard-schedules"
              title="Schedules"
              description="Manage payment schedules for the active club."
              isOpen={openDirectorSection === "schedules"}
              onToggle={() => toggleDirectorSection("schedules")}
            >
              <CoachPaymentsPage
                embedded
                scheduleOnly
                preferredClubId={clubId}
                team={activeClub ? { clubId: activeClub.id, clubName: activeClub.name } : null}
              />
            </DirectorDashboardDropdown>
          </section>

          <DashboardCreateClubCard
            className="vc-dashboard-onboarding--bottom"
            titleId="vc-create-club-bottom-title"
            title="Create Another Club"
            description="Need to add another club to this workspace? Start a fresh club setup here without leaving the dashboard."
            buttonLabel="Create a Club"
            onOpen={openCreateClubModal}
          />
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
            <form className="vc-create-club-form" onSubmit={submitCreateClub}>
              <div className="vc-create-club-form__grid">
                <div className="vc-create-club-form__field">
                  <CreateClubFieldLabel htmlFor="vc-create-club-name">Club name</CreateClubFieldLabel>
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
                </div>
                <div className="vc-create-club-form__field">
                  <CreateClubFieldLabel htmlFor="vc-create-club-short-name">Short name</CreateClubFieldLabel>
                  <input
                    id="vc-create-club-short-name"
                    className="vc-director-modal__select"
                    type="text"
                    value={newClubShortName}
                    onChange={(ev) => setNewClubShortName(ev.target.value)}
                    disabled={createClubBusy}
                    required
                  />
                </div>
                <div className="vc-create-club-form__field vc-create-club-form__field--full">
                  <CreateClubFieldLabel htmlFor="vc-create-club-description" optional>
                    Description
                  </CreateClubFieldLabel>
                  <textarea
                    id="vc-create-club-description"
                    className="vc-director-modal__textarea"
                    rows={3}
                    value={newClubDescription}
                    onChange={(ev) => setNewClubDescription(ev.target.value)}
                    disabled={createClubBusy}
                  />
                </div>
                <div className="vc-create-club-form__field">
                  <CreateClubFieldLabel htmlFor="vc-create-club-contact-email">Contact email</CreateClubFieldLabel>
                  <input
                    id="vc-create-club-contact-email"
                    className="vc-director-modal__select"
                    type="email"
                    autoComplete="email"
                    value={newClubContactEmail}
                    onChange={(ev) => setNewClubContactEmail(ev.target.value)}
                    disabled={createClubBusy}
                    required
                  />
                </div>
                <div className="vc-create-club-form__field">
                  <CreateClubFieldLabel htmlFor="vc-create-club-contact-phone">Contact phone</CreateClubFieldLabel>
                  <input
                    id="vc-create-club-contact-phone"
                    className="vc-director-modal__select"
                    type="tel"
                    autoComplete="tel"
                    value={newClubContactPhone}
                    onChange={(ev) => setNewClubContactPhone(ev.target.value)}
                    disabled={createClubBusy}
                    required
                  />
                </div>
                <div className="vc-create-club-form__field">
                  <CreateClubFieldLabel htmlFor="vc-create-club-website" optional>
                    Website
                  </CreateClubFieldLabel>
                  <input
                    id="vc-create-club-website"
                    className="vc-director-modal__select"
                    type="url"
                    autoComplete="url"
                    value={newClubWebsite}
                    onChange={(ev) => setNewClubWebsite(ev.target.value)}
                    disabled={createClubBusy}
                  />
                </div>
                <div className="vc-create-club-form__field">
                  <CreateClubFieldLabel htmlFor="vc-create-club-founded-year">Founded year</CreateClubFieldLabel>
                  <input
                    id="vc-create-club-founded-year"
                    className="vc-director-modal__select"
                    type="number"
                    inputMode="numeric"
                    min="1800"
                    max={String(new Date().getFullYear())}
                    value={newClubFoundedYear}
                    onChange={(ev) => setNewClubFoundedYear(ev.target.value)}
                    disabled={createClubBusy}
                    required
                  />
                </div>
                <div className="vc-create-club-form__field">
                  <CreateClubFieldLabel htmlFor="vc-create-club-country">Country</CreateClubFieldLabel>
                  <input
                    id="vc-create-club-country"
                    className="vc-director-modal__select"
                    type="text"
                    autoComplete="country-name"
                    value={newClubCountry}
                    onChange={(ev) => setNewClubCountry(ev.target.value)}
                    disabled={createClubBusy}
                    required
                  />
                </div>
                <div className="vc-create-club-form__field">
                  <CreateClubFieldLabel htmlFor="vc-create-club-city">City</CreateClubFieldLabel>
                  <input
                    id="vc-create-club-city"
                    className="vc-director-modal__select"
                    type="text"
                    autoComplete="address-level2"
                    value={newClubCity}
                    onChange={(ev) => setNewClubCity(ev.target.value)}
                    disabled={createClubBusy}
                    required
                  />
                </div>
                <div className="vc-create-club-form__field vc-create-club-form__field--full">
                  <CreateClubFieldLabel htmlFor="vc-create-club-address">Address</CreateClubFieldLabel>
                  <input
                    id="vc-create-club-address"
                    className="vc-director-modal__select"
                    type="text"
                    autoComplete="street-address"
                    value={newClubAddress}
                    onChange={(ev) => setNewClubAddress(ev.target.value)}
                    disabled={createClubBusy}
                    required
                  />
                </div>
              </div>
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
