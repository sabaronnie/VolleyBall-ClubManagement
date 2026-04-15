import { useCallback, useEffect, useState } from "react";
import {
  createClub,
  fetchCoachTeamDashboard,
  fetchCurrentUser,
  fetchDirectorPaymentOverview,
  fetchTeamAttendanceAnalytics,
  fetchTeamAttendanceSummary,
  fetchTeamMembers,
  fetchTeamPlayerPayments,
  updateUserEmergencyContact,
} from "../api";
import ClubWorkspaceLayout from "../components/ClubWorkspaceLayout";
import EmergencyContactForm from "../components/EmergencyContactForm";
import DirectorAttendanceTrendCard from "../components/director/DirectorAttendanceTrendCard";
import DirectorClubSummaryCard from "../components/director/DirectorClubSummaryCard";
import DirectorPaymentsOverviewCard from "../components/director/DirectorPaymentsOverviewCard";
import DirectorSummaryRow from "../components/director/DirectorSummaryRow";
import { navigate } from "../navigation";
import CoachPaymentsPage from "./CoachPaymentsPage";
import DirectorPaymentLogsPage from "./DirectorPaymentLogsPage";
import DirectorPaymentsPage from "./DirectorPaymentsPage";
import DirectorTeamSetupPage from "./DirectorTeamSetupPage";
import DirectorUserManagementPage from "./DirectorUserManagementPage";

const AUTH_TOKEN_KEY = "netup.auth.token";
const CLUB_STORAGE_KEY = "netup.director.payment.club_id";
const LOW_PARTICIPATION_THRESHOLD_PERCENT = 70;
const MIN_CLOSED_SLOTS_FOR_TEAM_ALERT = 4;

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

function formatDateInputValue(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function normalizePaymentStatus(status, totalRemaining) {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "overdue") {
    return "overdue";
  }
  if (Number(totalRemaining || 0) > 0) {
    return "pending";
  }
  return "paid";
}

function aggregateCoachPaymentRows(rows = []) {
  const grouped = new Map();
  for (const row of Array.isArray(rows) ? rows : []) {
    const key = row.player_id ?? row.family_label ?? row.id;
    if (!grouped.has(key)) {
      grouped.set(key, {
        player_id: row.player_id ?? key,
        family_label: row.family_label || "Player",
        total_paid: 0,
        total_remaining: 0,
        currency: row.currency || "USD",
        hasOverdue: false,
      });
    }
    const current = grouped.get(key);
    current.total_paid += Number(row.total_paid ?? row.amount_paid ?? 0);
    current.total_remaining += Number(row.total_remaining ?? row.remaining ?? 0);
    current.hasOverdue = current.hasOverdue || String(row.status || "").trim().toLowerCase() === "overdue";
    if (!current.currency && row.currency) {
      current.currency = row.currency;
    }
  }

  const bundled = [...grouped.values()].map((row) => ({
    player_id: row.player_id,
    family_label: row.family_label,
    total_paid: Number(row.total_paid.toFixed(2)),
    total_remaining: Number(row.total_remaining.toFixed(2)),
    currency: row.currency || "USD",
    status: row.hasOverdue
      ? "overdue"
      : normalizePaymentStatus(null, row.total_remaining),
  }));

  bundled.sort((a, b) => {
    const remainingDiff = Number(b.total_remaining || 0) - Number(a.total_remaining || 0);
    if (remainingDiff !== 0) {
      return remainingDiff;
    }
    return String(a.family_label || "").localeCompare(String(b.family_label || ""));
  });
  return bundled;
}

function buildCoachWorkspaceFallback({
  team,
  membersPayload,
  paymentRowsPayload,
  attendanceSummaryPayload,
  attendanceAnalyticsPayload,
}) {
  if (!team) {
    return null;
  }

  const rosterPlayers = Array.isArray(membersPayload?.members)
    ? membersPayload.members.filter((member) => member.membership?.role === "player")
    : [];
  const familySummaries = aggregateCoachPaymentRows(paymentRowsPayload?.fee_rows || []);
  const monthlyRevenue = familySummaries.reduce((sum, row) => sum + Number(row.total_paid || 0), 0);
  const currency =
    familySummaries.find((row) => row.currency)?.currency ||
    paymentRowsPayload?.fee_rows?.find((row) => row.currency)?.currency ||
    "USD";
  const attendanceRate = attendanceSummaryPayload?.team_average_attendance_rate_percent ?? null;
  const closedSlots = Number(attendanceSummaryPayload?.closed_roster_slots_total || 0);
  const lowParticipation =
    attendanceRate != null &&
    closedSlots >= MIN_CLOSED_SLOTS_FOR_TEAM_ALERT &&
    Number(attendanceRate) < LOW_PARTICIPATION_THRESHOLD_PERCENT
      ? {
          team_id: team.id,
          team_name: team.name,
          rate_percent: Number(attendanceRate),
          message: `${team.name} is below ${LOW_PARTICIPATION_THRESHOLD_PERCENT}% attendance in the last 30 days (${Number(attendanceRate).toFixed(1)}%).`,
        }
      : null;
  const analyticsTrend = Array.isArray(attendanceAnalyticsPayload?.trend)
    ? attendanceAnalyticsPayload.trend
    : [];

  return {
    kpis: {
      registration_player_count: rosterPlayers.length,
      monthly_revenue: Number(monthlyRevenue.toFixed(2)),
      monthly_revenue_currency: currency,
      attendance_rate: attendanceRate,
      outstanding_payer_count: familySummaries.filter((row) => Number(row.total_remaining || 0) > 0).length,
    },
    attendance_trend_30d: {
      calculation_summary: attendanceSummaryPayload?.calculation_summary || "",
      points: analyticsTrend.map((point) => ({
        date: point.period_start,
        rate_percent: point.attendance_rate_percent,
        closed_slots: Number(point.present_slots || 0) + Number(point.absent_slots || 0),
        attended_slots: Number(point.present_slots || 0),
      })),
    },
    payments_overview: familySummaries.slice(0, 8),
    family_summaries: familySummaries,
    team_summary: {
      average_attendance_percent: attendanceRate,
      best_participating_team:
        attendanceRate != null && closedSlots > 0
          ? {
              team_id: team.id,
              team_name: team.name,
              rate_percent: Number(attendanceRate),
            }
          : null,
      low_participation: lowParticipation,
      monthly_profit: Number(monthlyRevenue.toFixed(2)),
      monthly_profit_currency: currency,
    },
  };
}

function hasCoachTrendData(trend) {
  return Array.isArray(trend?.points) && trend.points.some((point) => Number(point.closed_slots || 0) > 0);
}

function mergeCoachKpis(primaryKpis, fallbackKpis) {
  if (!primaryKpis && !fallbackKpis) {
    return null;
  }
  if (!primaryKpis) {
    return fallbackKpis;
  }
  if (!fallbackKpis) {
    return primaryKpis;
  }
  return {
    ...fallbackKpis,
    ...primaryKpis,
    registration_player_count:
      primaryKpis.registration_player_count != null && primaryKpis.registration_player_count !== ""
        ? primaryKpis.registration_player_count
        : fallbackKpis.registration_player_count,
    monthly_revenue:
      primaryKpis.monthly_revenue != null && primaryKpis.monthly_revenue !== ""
        ? primaryKpis.monthly_revenue
        : fallbackKpis.monthly_revenue,
    monthly_revenue_currency:
      primaryKpis.monthly_revenue_currency || fallbackKpis.monthly_revenue_currency,
    attendance_rate:
      primaryKpis.attendance_rate != null && primaryKpis.attendance_rate !== ""
        ? primaryKpis.attendance_rate
        : fallbackKpis.attendance_rate,
    outstanding_payer_count:
      primaryKpis.outstanding_payer_count != null && primaryKpis.outstanding_payer_count !== ""
        ? primaryKpis.outstanding_payer_count
        : fallbackKpis.outstanding_payer_count,
  };
}

function mergeCoachWorkspaceOverview(primaryOverview, fallbackOverview) {
  if (!primaryOverview && !fallbackOverview) {
    return null;
  }
  if (!primaryOverview) {
    return fallbackOverview;
  }
  if (!fallbackOverview) {
    return primaryOverview;
  }
  return {
    ...fallbackOverview,
    ...primaryOverview,
    kpis: mergeCoachKpis(primaryOverview.kpis, fallbackOverview.kpis),
    attendance_trend_30d: hasCoachTrendData(primaryOverview.attendance_trend_30d)
      ? primaryOverview.attendance_trend_30d
      : fallbackOverview.attendance_trend_30d,
    payments_overview:
      Array.isArray(primaryOverview.payments_overview) && primaryOverview.payments_overview.length
        ? primaryOverview.payments_overview
        : fallbackOverview.payments_overview,
    family_summaries:
      Array.isArray(primaryOverview.family_summaries) && primaryOverview.family_summaries.length
        ? primaryOverview.family_summaries
        : fallbackOverview.family_summaries,
    team_summary: primaryOverview.team_summary || fallbackOverview.team_summary,
  };
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

export default function DashboardPage({
  teamOptions = [],
  activeTeamId = "",
  onChangeTeam = null,
  includeAllTeamsOption = true,
}) {
  const [ownedClubs, setOwnedClubs] = useState([]);
  const [coachedTeams, setCoachedTeams] = useState([]);
  const [clubId, setClubId] = useState(null);
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [coachOverview, setCoachOverview] = useState(null);
  const [coachOverviewLoading, setCoachOverviewLoading] = useState(false);
  const [coachOverviewError, setCoachOverviewError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [viewerAccountRole, setViewerAccountRole] = useState(null);
  const [profileMe, setProfileMe] = useState(null);
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
      setProfileMe(me);
      setIsDirectorOrStaff(Boolean(me.is_director_or_staff));
      setViewerAccountRole(me.user?.role || null);
      setHasPlayerTeams(Array.isArray(me.player_teams) && me.player_teams.length > 0);
      setCoachedTeams(me.coached_teams || []);
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
      setCoachedTeams([]);
      setProfileMe(null);
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
  const activeCoachTeam =
    coachedTeams.find((team) => String(team.id) === String(activeTeamId)) ||
    coachedTeams[0] ||
    null;
  const isCoachWorkspace = !isDirectorOrStaff && coachedTeams.length > 0;

  useEffect(() => {
    if (!isCoachWorkspace || !activeCoachTeam?.id) {
      setCoachOverview(null);
      setCoachOverviewError("");
      setCoachOverviewLoading(false);
      return;
    }
    let cancelled = false;
    setCoachOverviewLoading(true);
    setCoachOverviewError("");
    const today = new Date();
    const startDate = new Date(today);
    startDate.setDate(today.getDate() - 29);
    const attendanceParams = {
      startDate: formatDateInputValue(startDate),
      endDate: formatDateInputValue(today),
    };
    void Promise.allSettled([
      fetchCoachTeamDashboard(activeCoachTeam.id),
      fetchTeamMembers(activeCoachTeam.id),
      fetchTeamPlayerPayments(activeCoachTeam.id),
      fetchTeamAttendanceSummary(activeCoachTeam.id, attendanceParams),
      fetchTeamAttendanceAnalytics(activeCoachTeam.id, {
        ...attendanceParams,
        grouping: "session",
      }),
    ])
      .then(([dashboardResult, membersResult, paymentsResult, summaryResult, analyticsResult]) => {
        if (cancelled) {
          return;
        }
        const coachDashboardPayload =
          dashboardResult.status === "fulfilled" ? dashboardResult.value || null : null;
        const primaryWorkspaceOverview =
          coachDashboardPayload?.workspace_overview ||
          coachDashboardPayload?.workspaceOverview ||
          coachDashboardPayload?.dashboard?.workspace_overview ||
          coachDashboardPayload?.data?.workspace_overview ||
          (coachDashboardPayload?.kpis || coachDashboardPayload?.attendance_trend_30d || coachDashboardPayload?.team_summary
            ? coachDashboardPayload
            : null);
        const fallbackWorkspaceOverview = buildCoachWorkspaceFallback({
          team: activeCoachTeam,
          membersPayload: membersResult.status === "fulfilled" ? membersResult.value : null,
          paymentRowsPayload: paymentsResult.status === "fulfilled" ? paymentsResult.value : null,
          attendanceSummaryPayload: summaryResult.status === "fulfilled" ? summaryResult.value : null,
          attendanceAnalyticsPayload: analyticsResult.status === "fulfilled" ? analyticsResult.value : null,
        });
        const mergedWorkspaceOverview = mergeCoachWorkspaceOverview(
          primaryWorkspaceOverview,
          fallbackWorkspaceOverview,
        );

        if (coachDashboardPayload) {
          setCoachOverview({
            ...coachDashboardPayload,
            workspace_overview: mergedWorkspaceOverview,
          });
        } else if (mergedWorkspaceOverview) {
          setCoachOverview({
            team: {
              id: activeCoachTeam.id,
              name: activeCoachTeam.name,
            },
            workspace_overview: mergedWorkspaceOverview,
          });
        } else {
          setCoachOverview(null);
        }

        if (dashboardResult.status === "rejected" && !mergedWorkspaceOverview) {
          setCoachOverviewError(dashboardResult.reason?.message || "Could not load team overview.");
        } else {
          setCoachOverviewError("");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCoachOverviewLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeCoachTeam?.id, isCoachWorkspace]);

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
  const coachWorkspaceOverview =
    coachOverview?.workspace_overview ||
    (coachOverview?.kpis || coachOverview?.attendance_trend_30d || coachOverview?.team_summary ? coachOverview : null);
  const coachPaymentRows = Array.isArray(coachWorkspaceOverview?.family_summaries)
    ? coachWorkspaceOverview.family_summaries.map((b) => ({
        player_id: b.player_id,
        family_label: b.family_label,
        total_paid: b.total_paid,
        total_remaining: b.total_remaining,
        currency: b.currency,
        status: normalizePaymentStatus(b.status || b.overall_status, b.total_remaining),
      }))
    : Array.isArray(coachWorkspaceOverview?.payments_overview)
    ? coachWorkspaceOverview.payments_overview.map((b) => ({
        player_id: b.player_id,
        family_label: b.family_label,
        total_paid: b.total_paid,
        total_remaining: b.total_remaining,
        currency: b.currency,
        status: normalizePaymentStatus(b.status || b.overall_status, b.total_remaining),
      }))
    : (coachWorkspaceOverview?.family_summaries || []).map((b) => ({
        player_id: b.player_id,
        family_label: b.family_label,
        total_paid: b.total_paid,
        total_remaining: b.total_remaining,
        currency: b.currency,
        status: normalizePaymentStatus(b.status || b.overall_status, b.total_remaining),
      }));
  const paymentSnapshot = {
    outstandingTotal: paymentRows.reduce((sum, row) => sum + Number(row.total_remaining || 0), 0),
    unpaidCount: paymentRows.filter((row) => row.status !== "paid").length,
    paidCount: paymentRows.filter((row) => row.status === "paid").length,
    currency: paymentRows.find((row) => row.currency)?.currency || overview?.club_summary?.monthly_profit_currency || "USD",
    label: "Outstanding / Unpaid / Paid",
  };
  const coachPaymentSnapshot = {
    outstandingTotal: coachPaymentRows.reduce((sum, row) => sum + Number(row.total_remaining || 0), 0),
    unpaidCount: coachPaymentRows.filter((row) => normalizePaymentStatus(row.status, row.total_remaining) !== "paid").length,
    paidCount: coachPaymentRows.filter((row) => normalizePaymentStatus(row.status, row.total_remaining) === "paid").length,
    currency:
      coachPaymentRows.find((row) => row.currency)?.currency || coachWorkspaceOverview?.team_summary?.monthly_profit_currency || "USD",
    label: "Outstanding / Unpaid / Paid",
  };

  const showNoClubOnboarding = !profileLoading && !hasAnyClubAffiliation;
  const showWorkspace = !profileLoading && hasAnyClubAffiliation;
  const dashboardTitle = isCoachWorkspace
    ? activeCoachTeam?.name || "Coaching workspace"
    : activeClub?.name || "Club dashboard";
  const dashboardSummary = isCoachWorkspace
    ? "Roster updates, player invitations, balances, and attendance tools in one coaching workspace."
    : loading
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

  const saveOwnEmergencyContact = async (nextValue, countryCode) => {
    const userId = profileMe?.user?.id;
    if (!userId) {
      throw new Error("Could not identify your account.");
    }
    const result = await updateUserEmergencyContact(userId, nextValue, countryCode);
    setProfileMe((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        user: {
          ...(current.user || {}),
          emergency_contact: result?.user?.emergency_contact ?? nextValue,
        },
      };
    });
    return result;
  };

  const toggleDirectorSection = (sectionId) => {
    setOpenDirectorSection((current) => (current === sectionId ? "" : sectionId));
  };

  const openDirectorSectionPanel = (sectionId) => {
    setOpenDirectorSection(sectionId);
    window.setTimeout(() => {
      const trigger = document.getElementById(`dashboard-${sectionId}-trigger`);
      if (trigger && typeof trigger.scrollIntoView === "function") {
        trigger.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }, 0);
  };

  return (
    <ClubWorkspaceLayout
      activeTab="dashboard"
      viewerAccountRole={viewerAccountRole}
      teamOptions={teamOptions}
      activeTeamId={activeTeamId}
      onChangeTeam={onChangeTeam}
      includeAllTeamsOption={includeAllTeamsOption}
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

      {showWorkspace ? (
        <section className="vc-dashboard-hero">
          <div className="vc-dashboard-hero__content">
            <div className="vc-dashboard-hero__copy">
              <span className="vc-dashboard-hero__eyebrow">
                {isCoachWorkspace ? "Coaching workspace" : "Director workspace"}
              </span>
              <h1 className="vc-dashboard-hero__title">{dashboardTitle}</h1>
              <p className="vc-dashboard-hero__summary">{dashboardSummary}</p>
              <div className="vc-dashboard-hero__meta">
                <span className="vc-dashboard-chip">{loading ? "Syncing" : "Live overview"}</span>
                {!isCoachWorkspace && activeClub?.name ? (
                  <span className="vc-dashboard-chip vc-dashboard-chip--soft">{activeClub.name}</span>
                ) : null}
                {isCoachWorkspace && activeCoachTeam?.club_name ? (
                  <span className="vc-dashboard-chip vc-dashboard-chip--soft">{activeCoachTeam.club_name}</span>
                ) : null}
                {ownedClubs.length > 1 ? (
                  <span className="vc-dashboard-chip vc-dashboard-chip--soft">
                    {ownedClubs.length} clubs linked
                  </span>
                ) : null}
              </div>
            </div>

            {!isCoachWorkspace && ownedClubs.length > 1 ? (
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

      {showWorkspace && profileMe?.user ? (
        <EmergencyContactForm
          value={profileMe.user.emergency_contact || ""}
          canEdit={profileMe.account_profile?.can_update_emergency_contact !== false}
          disabledReason="Your parent-managed settings do not allow you to update this contact."
          onSave={saveOwnEmergencyContact}
        />
      ) : null}

      {successMessage ? <div className="vc-director-success vc-dashboard-alert">{successMessage}</div> : null}
      {error ? <div className="vc-director-error vc-dashboard-alert">{error}</div> : null}

      {showWorkspace && !isCoachWorkspace ? (
        <>
          <DirectorSummaryRow
            loading={loading}
            kpis={kpis}
            paymentSnapshot={paymentSnapshot}
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
            <DirectorClubSummaryCard
              loading={loading}
              clubId={clubId}
              clubSummary={overview?.club_summary}
              paymentSnapshot={paymentSnapshot}
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
              description="Manage roles and review your club directory."
              isOpen={openDirectorSection === "users"}
              onToggle={() => toggleDirectorSection("users")}
            >
              <DirectorUserManagementPage
                embedded
                onOpenPayments={() => openDirectorSectionPanel("payments")}
                showParentLinkRequests={false}
              />
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

      {showWorkspace && isCoachWorkspace ? (
        <>
          <DirectorSummaryRow
            loading={coachOverviewLoading}
            kpis={coachWorkspaceOverview?.kpis}
            paymentSnapshot={coachPaymentSnapshot}
            formatMoney={formatMoney}
            formatPercent={formatPercent}
          />

          <div className="vc-dash-row vc-dash-row--dashboard">
            <DirectorAttendanceTrendCard
              loading={coachOverviewLoading}
              clubId={activeCoachTeam?.id || null}
              trend={coachWorkspaceOverview?.attendance_trend_30d}
              emptySelectionMessage="Select a team to load attendance history."
              emptyDataMessage="No attendance data is available yet for this team in the last 30 days. Close training sessions so the team trend can appear here."
            />
            <DirectorPaymentsOverviewCard
              loading={coachOverviewLoading}
              clubId={activeCoachTeam?.id || null}
              rows={coachPaymentRows}
              formatMoney={formatMoney}
              onViewAll={() => openDirectorSectionPanel("payments")}
              emptySelectionMessage="Select a team to review player balances."
              emptyDataMessage="No payment records are available yet for this team."
            />
          </div>

          <div className="vc-dash-bottom vc-dash-bottom--dashboard">
            <DirectorClubSummaryCard
              loading={coachOverviewLoading}
              clubId={activeCoachTeam?.id || null}
              clubSummary={coachWorkspaceOverview?.team_summary}
              paymentSnapshot={coachPaymentSnapshot}
              formatMoney={formatMoney}
              onManageTeams={() => openDirectorSectionPanel("teams")}
              title="Team Summary"
              manageLabel="Open Team Tools"
              emptySelectionMessage="Select a team to see summary metrics."
              bestLabel="Current Team"
              lowLabel="Participation Alert"
              lowFallbackMessage="No participation warning for this team in the last 30 days."
              profitLabel="Monthly Revenue"
            />
          </div>

          {coachOverviewError ? <div className="vc-director-error vc-dashboard-alert">{coachOverviewError}</div> : null}

          <section className="vc-dashboard-toolbox" aria-labelledby="vc-dashboard-toolbox-title">
            <div className="vc-dashboard-toolbox__header">
              <div>
                <p className="vc-dashboard-panel-head__eyebrow">Workspace Tools</p>
                <h2 id="vc-dashboard-toolbox-title" className="vc-panel-title">
                  Coach Tools
                </h2>
              </div>
              <p className="vc-modal__muted">
                Expand a section below to manage your roster, invite players, review team fees, and make player-only changes from one workspace.
              </p>
            </div>

            <DirectorDashboardDropdown
              id="dashboard-users"
              title="Users"
              description="Review your team directory and remove players from your roster."
              isOpen={openDirectorSection === "users"}
              onToggle={() => toggleDirectorSection("users")}
            >
              <DirectorUserManagementPage embedded focusedTeamId={activeCoachTeam?.id || null} />
            </DirectorDashboardDropdown>

            <DirectorDashboardDropdown
              id="dashboard-payments"
              title="Payments"
              description="Review balances for the players on your selected team."
              isOpen={openDirectorSection === "payments"}
              onToggle={() => toggleDirectorSection("payments")}
            >
              <CoachPaymentsPage
                embedded
                team={
                  activeCoachTeam
                    ? {
                        id: activeCoachTeam.id,
                        name: activeCoachTeam.name,
                        clubId: activeCoachTeam.club_id,
                        clubName: activeCoachTeam.club_name,
                      }
                    : null
                }
              />
            </DirectorDashboardDropdown>

            <DirectorDashboardDropdown
              id="dashboard-teams"
              title="Teams"
              description="Invite players to your team and manage player-only team actions."
              isOpen={openDirectorSection === "teams"}
              onToggle={() => toggleDirectorSection("teams")}
            >
              <DirectorTeamSetupPage
                embedded
                workspaceRole="coach"
                onOpenUsers={() => openDirectorSectionPanel("users")}
              />
            </DirectorDashboardDropdown>
          </section>
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
