import { useEffect, useMemo, useState } from "react";
import {
  directorCreateTeam,
  fetchCoachTeamDashboard,
  fetchCurrentUser,
  fetchMyFees,
  fetchTeamMembers,
  requestParentLinkToPlayer,
} from "../api";
import ClubWorkspaceLayout from "../components/ClubWorkspaceLayout";
import CoachDashboardBody from "../components/coach/CoachDashboardBody";
import MemberPlayerDashboard from "../components/member/MemberPlayerDashboard";
import { navigate } from "../navigation";

const AUTH_TOKEN_KEY = "netup.auth.token";
const ACTIVE_TEAM_KEY = "netup.active.team";

function money(cur, amount) {
  const n = Number(amount);
  if (Number.isNaN(n)) {
    return `${cur || "USD"} ${amount}`;
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency: cur || "USD" }).format(n);
}

function setActiveTeamAndNavigate(teamId, path) {
  window.dispatchEvent(new CustomEvent("netup-set-active-team", { detail: { teamId } }));
  navigate(path);
}

export default function MemberHubPage() {
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [childrenFees, setChildrenFees] = useState([]);
  const [ownFees, setOwnFees] = useState([]);
  const [newTeamName, setNewTeamName] = useState("");
  const [newTeamSeason, setNewTeamSeason] = useState("");
  const [newTeamClubId, setNewTeamClubId] = useState("");
  const [createTeamBusy, setCreateTeamBusy] = useState(false);
  const [createTeamError, setCreateTeamError] = useState("");
  const [createTeamSuccess, setCreateTeamSuccess] = useState("");
  const [linkPlayerId, setLinkPlayerId] = useState("");
  const [linkLegalGuardian, setLinkLegalGuardian] = useState(false);
  const [linkBusy, setLinkBusy] = useState(false);
  const [linkMessage, setLinkMessage] = useState("");
  const [linkError, setLinkError] = useState("");
  /** teamId -> { playerCount, coachCount } */
  const [coachTeamRoster, setCoachTeamRoster] = useState({});
  const [coachDashTeamId, setCoachDashTeamId] = useState("");
  const [coachDashData, setCoachDashData] = useState(null);
  const [coachDashLoading, setCoachDashLoading] = useState(false);
  const [coachDashError, setCoachDashError] = useState("");

  useEffect(() => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
      navigate("/login");
      return undefined;
    }
    let cancelled = false;
    (async () => {
      setError("");
      try {
        const [data, feesData] = await Promise.all([fetchCurrentUser(), fetchMyFees()]);
        if (!cancelled) {
          setMe(data);
          setOwnFees(feesData.own_fees || []);
          setChildrenFees(feesData.children_fees || []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Could not load your club home.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!me) {
      return undefined;
    }
    setCoachDashTeamId(localStorage.getItem(ACTIVE_TEAM_KEY) || "");
    return undefined;
  }, [me]);

  useEffect(() => {
    const onSetTeam = (e) => {
      const tid = e.detail?.teamId;
      if (tid != null) {
        setCoachDashTeamId(String(tid));
      }
    };
    window.addEventListener("netup-set-active-team", onSetTeam);
    return () => window.removeEventListener("netup-set-active-team", onSetTeam);
  }, []);

  const ownedClubs = me?.owned_clubs || [];
  const isDirector = Boolean(me?.is_director_or_staff) || ownedClubs.length > 0;
  const coached = me?.coached_teams || [];
  const playing = me?.player_teams || [];
  const children = me?.children || [];
  const childTeamCount = children.reduce((n, ch) => n + (ch.teams || []).length, 0);
  const fees = me?.account_profile?.pending_fees || {};
  const feeDue = typeof fees.total_due === "number" ? fees.total_due : 0;
  const hasTeams = coached.length + playing.length + childTeamCount > 0;
  const accountRoles = me?.account_profile?.roles || [];
  const pendingParentLinks = me?.pending_parent_links || [];
  const showParentLinking =
    accountRoles.includes("parent") ||
    me?.user?.role === "parent" ||
    children.length > 0 ||
    pendingParentLinks.length > 0;
  const coachOnlyPayer =
    coached.length > 0 && !playing.length && !children.length && !isDirector;

  const coachTeamsManaging = useMemo(
    () => (me?.coached_teams || []).filter((t) => t.can_manage_training),
    [me?.coached_teams],
  );

  const resolvedCoachTeamId = useMemo(() => {
    if (!coachTeamsManaging.length) {
      return null;
    }
    const ids = new Set(coachTeamsManaging.map((t) => String(t.id)));
    const stored = coachDashTeamId;
    if (stored && ids.has(stored)) {
      return Number(stored);
    }
    return coachTeamsManaging[0].id;
  }, [coachTeamsManaging, coachDashTeamId]);

  const showCoachDashboard = coachTeamsManaging.length > 0;

  const handleCoachTeamSelect = (team) => {
    const id = String(team.id);
    localStorage.setItem(ACTIVE_TEAM_KEY, id);
    setCoachDashTeamId(id);
    window.dispatchEvent(new CustomEvent("netup-set-active-team", { detail: { teamId: id } }));
  };

  useEffect(() => {
    if (!resolvedCoachTeamId || !showCoachDashboard) {
      setCoachDashData(null);
      setCoachDashError("");
      setCoachDashLoading(false);
      return undefined;
    }
    let cancelled = false;
    setCoachDashLoading(true);
    setCoachDashError("");
    void fetchCoachTeamDashboard(resolvedCoachTeamId)
      .then((data) => {
        if (!cancelled) {
          setCoachDashData(data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setCoachDashError(err.message || "Could not load coach dashboard.");
          setCoachDashData(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCoachDashLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [resolvedCoachTeamId, showCoachDashboard]);

  const ownUnpaidFees = ownFees.filter((f) => f.status !== "paid");
  const childUnpaidFees = childrenFees.filter((f) => f.status !== "paid");
  const payCur =
    ownUnpaidFees[0]?.currency || childUnpaidFees[0]?.currency || fees.currency || "USD";
  const totalOwnUnpaid = ownUnpaidFees.reduce((s, f) => s + Number(f.remaining || 0), 0);
  const totalChildUnpaid = childUnpaidFees.reduce((s, f) => s + Number(f.remaining || 0), 0);
  const unpaidLineCount = ownUnpaidFees.length + childUnpaidFees.length;
  const totalUnpaidAll = totalOwnUnpaid + totalChildUnpaid;
  const playerWorkspaceTitle = children.length
    ? "Family player workspace"
    : playing[0]?.name || "Player workspace";
  const playerWorkspaceSummary = children.length
    ? "Follow linked players, review fees, and confirm attendance from one family workspace."
    : "Your schedule, sessions, fees, and development progress in one player workspace.";
  const playerWorkspaceTeamCount = playing.length + childTeamCount;

  const coachClubOptions = useMemo(() => {
    const m = new Map();
    for (const t of coached) {
      const id = t.club_id;
      if (id != null && !m.has(id)) {
        m.set(id, t.club_name || `Club #${id}`);
      }
    }
    return [...m.entries()].map(([id, name]) => ({ id, name }));
  }, [coached]);

  const coachedTeamIdsKey = useMemo(
    () =>
      (me?.coached_teams || [])
        .map((t) => t.id)
        .filter((id) => id != null)
        .sort((a, b) => a - b)
        .join(","),
    [me?.coached_teams],
  );

  useEffect(() => {
    if (!coachedTeamIdsKey) {
      setCoachTeamRoster({});
      return undefined;
    }
    const teamIds = coachedTeamIdsKey
      .split(",")
      .map((s) => Number(s))
      .filter((n) => Number.isFinite(n) && n > 0);
    if (!teamIds.length) {
      setCoachTeamRoster({});
      return undefined;
    }
    let cancelled = false;
    void (async () => {
      const next = {};
      await Promise.all(
        teamIds.map(async (tid) => {
          try {
            const data = await fetchTeamMembers(tid);
            const members = data.members || [];
            let playerCount = 0;
            let coachCount = 0;
            for (const row of members) {
              const role = row.membership?.role;
              if (role === "player") playerCount += 1;
              else if (role === "coach") coachCount += 1;
            }
            next[tid] = { playerCount, coachCount, error: null };
          } catch {
            next[tid] = { playerCount: null, coachCount: null, error: "Could not load roster." };
          }
        }),
      );
      if (!cancelled) {
        setCoachTeamRoster(next);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [coachedTeamIdsKey]);

  useEffect(() => {
    if (!coachClubOptions.length) {
      setNewTeamClubId("");
      return;
    }
    setNewTeamClubId((prev) => {
      if (prev && coachClubOptions.some((o) => o.id === prev)) {
        return prev;
      }
      return coachClubOptions[0].id;
    });
  }, [coachClubOptions]);

  const onRequestParentLink = async () => {
    const uid = Number(linkPlayerId.trim());
    if (!linkPlayerId.trim() || Number.isNaN(uid) || uid < 1) {
      setLinkError("Enter your child’s numeric user ID.");
      return;
    }
    setLinkBusy(true);
    setLinkError("");
    setLinkMessage("");
    try {
      const res = await requestParentLinkToPlayer(uid, { is_legal_guardian: linkLegalGuardian });
      setLinkMessage(res.message || "Request submitted.");
      setLinkPlayerId("");
      const data = await fetchCurrentUser();
      setMe(data);
      const feesData = await fetchMyFees();
      setOwnFees(feesData.own_fees || []);
      setChildrenFees(feesData.children_fees || []);
      window.dispatchEvent(new Event("vc-member-dashboard-refresh"));
    } catch (err) {
      setLinkError(err.message || "Could not submit link request.");
    } finally {
      setLinkBusy(false);
    }
  };

  const onCreateTeamForCoach = async () => {
    const clubId = Number(newTeamClubId);
    const name = newTeamName.trim();
    if (!clubId || Number.isNaN(clubId)) {
      setCreateTeamError("Select a club.");
      return;
    }
    if (!name) {
      setCreateTeamError("Enter a team name.");
      return;
    }
    setCreateTeamBusy(true);
    setCreateTeamError("");
    setCreateTeamSuccess("");
    try {
      const out = await directorCreateTeam(clubId, {
        name,
        season: newTeamSeason.trim(),
      });
      const teamId = out.team?.id;
      setNewTeamName("");
      setNewTeamSeason("");
      setCreateTeamSuccess(`Team "${out.team?.name || name}" was created. Opening its roster…`);
      const data = await fetchCurrentUser();
      setMe(data);
      window.dispatchEvent(new Event("netup-teams-changed"));
      if (teamId) {
        window.setTimeout(() => {
          setActiveTeamAndNavigate(teamId, "/roster");
        }, 400);
      }
    } catch (err) {
      setCreateTeamError(err.message || "Could not create the team.");
    } finally {
      setCreateTeamBusy(false);
    }
  };

  const showCoachAttendanceTab =
    (me?.coached_teams || []).some((t) => t.can_manage_training) ||
    (me?.director_teams || []).some((t) => t.can_manage_training);

  return (
    <ClubWorkspaceLayout
      activeTab="dashboard"
      viewerAccountRole={me?.user?.role || null}
      showPlayerSessionsTab={playing.length > 0}
      showCoachAttendanceTab={showCoachAttendanceTab}
      teamOptions={showCoachDashboard ? coachTeamsManaging : []}
      activeTeamId={showCoachDashboard && resolvedCoachTeamId != null ? String(resolvedCoachTeamId) : ""}
      onChangeTeam={showCoachDashboard ? handleCoachTeamSelect : null}
      teamSelectorVariant={showCoachDashboard ? "native" : "custom"}
      includeAllTeamsOption={showCoachDashboard && coachTeamsManaging.length > 1}
    >
      <section
        className={`vc-member-hub${showCoachDashboard ? " vc-member-hub--coach-dash" : ""}`}
        style={{
          padding: "1.5rem 1.75rem 2.5rem",
          maxWidth: "min(1180px, 100%)",
          margin: "0 auto",
        }}
      >
        {showCoachDashboard ? (
          <header style={{ marginBottom: "1.25rem" }}>
            <h1 style={{ fontSize: "1.45rem", margin: "0 0 0.35rem", fontWeight: 700 }}>Dashboard</h1>
            <p style={{ margin: 0, color: "#5c6570", lineHeight: 1.5, maxWidth: 640 }}>
              Team overview, analytics, and quick coaching actions.
            </p>
          </header>
        ) : (
          <section className="vc-dashboard-hero">
            <div className="vc-dashboard-hero__content">
              <div className="vc-dashboard-hero__copy">
                <span className="vc-dashboard-hero__eyebrow">Player workspace</span>
                <h1 className="vc-dashboard-hero__title">{playerWorkspaceTitle}</h1>
                <p className="vc-dashboard-hero__summary">{playerWorkspaceSummary}</p>
                <div className="vc-dashboard-hero__meta">
                  <span className="vc-dashboard-chip">{loading ? "Syncing" : "Live overview"}</span>
                  <span className="vc-dashboard-chip vc-dashboard-chip--soft">
                    {playerWorkspaceTeamCount} team{playerWorkspaceTeamCount === 1 ? "" : "s"} linked
                  </span>
                  <span className="vc-dashboard-chip vc-dashboard-chip--soft">
                    {money(payCur, totalUnpaidAll)} due
                  </span>
                  {children.length ? (
                    <span className="vc-dashboard-chip vc-dashboard-chip--soft">
                      {children.length} linked player{children.length === 1 ? "" : "s"}
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
          </section>
        )}

        {loading ? <p className="vc-modal__muted">{"Loading\u2026"}</p> : null}
        {error ? <p className="vc-modal__error">{error}</p> : null}

        {!loading && !error ? (
          <>
            {showCoachDashboard ? (
              <CoachDashboardBody
                dashboard={coachDashData}
                loading={coachDashLoading}
                error={coachDashError}
              />
            ) : (
              <MemberPlayerDashboard />
            )}

            {showCoachDashboard ? (
              <section
                className="vc-dash-kpi-card"
                style={{ marginBottom: "1.25rem" }}
                aria-label="Quick links"
              >
                <h2 style={{ fontSize: "1.05rem", margin: "0 0 0.75rem" }}>Quick links</h2>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
                    gap: "0.5rem",
                  }}
                >
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/schedule")}>
                    Schedule
                  </button>
                  <button
                    type="button"
                    className="vc-action-btn"
                    onClick={() => navigate(coachOnlyPayer ? "/payments" : "/my-fees")}
                  >
                    {coachOnlyPayer ? "Team fees" : "My fees"}
                  </button>
                  {showCoachAttendanceTab ? (
                    <button type="button" className="vc-action-btn" onClick={() => navigate("/coach/attendance")}>
                      Team attendance
                    </button>
                  ) : null}
                  {playing.length > 0 ? (
                    <button type="button" className="vc-action-btn" onClick={() => navigate("/player/attendance")}>
                      My sessions
                    </button>
                  ) : null}
                  {accountRoles.includes("parent") || children.length > 0 ? (
                    <button type="button" className="vc-action-btn" onClick={() => navigate("/parent/attendance")}>
                      Family attendance
                    </button>
                  ) : null}
                </div>
                {!hasTeams ? (
                  <p className="vc-modal__muted" style={{ margin: "0.75rem 0 0", fontSize: "0.88rem", lineHeight: 1.5 }}>
                    No team yet? Your director can add you to a roster.
                  </p>
                ) : null}
              </section>
            ) : null}

            {showCoachDashboard && coachOnlyPayer ? (
              <section
                className="vc-dash-kpi-card"
                style={{ marginBottom: "1.25rem" }}
                aria-labelledby="hub-coach-payments-heading"
              >
                <h2 id="hub-coach-payments-heading" style={{ fontSize: "1.05rem", margin: "0 0 0.5rem" }}>
                  Team payments (monitoring)
                </h2>
                <p style={{ margin: "0 0 0.75rem", color: "#5c6570", lineHeight: 1.5 }}>
                  Review fee records for players on the teams you coach. Personal player dues do not apply to this view.
                </p>
                <button type="button" className="vc-action-btn" onClick={() => navigate("/payments")}>
                  Open team payments
                </button>
              </section>
            ) : null}

            {isDirector ? (
              <section className="vc-dash-kpi-card" style={{ marginBottom: "1.25rem" }} aria-labelledby="hub-director-heading">
                <h2 id="hub-director-heading" style={{ fontSize: "1.05rem", margin: "0 0 0.65rem" }}>
                  Director tools
                </h2>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/dashboard")}>
                    Club dashboard
                  </button>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/director/payments")}>
                    Payments
                  </button>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/director/users")}>
                    Users
                  </button>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/director/teams")}>
                    Teams
                  </button>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/payments")}>
                    Fee schedules
                  </button>
                </div>
              </section>
            ) : null}

            {coached.length ? (
              <section className="vc-dash-kpi-card" style={{ marginBottom: "1.25rem" }} aria-labelledby="hub-coach-heading">
                <h2 id="hub-coach-heading" style={{ fontSize: "1.05rem", margin: "0 0 0.5rem" }}>
                  Coaching
                </h2>
                <p style={{ margin: "0 0 0.85rem", color: "#5c6570", lineHeight: 1.5, fontSize: "0.9rem" }}>
                  Add sessions under <strong>Team attendance</strong> so players and parents can confirm; manage roster
                  and fees per team below.
                </p>
                <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "0.75rem" }}>
                  {coached.map((team) => (
                    <li
                      key={team.id}
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "0.5rem",
                        alignItems: "center",
                        justifyContent: "space-between",
                        borderBottom: "1px solid #e8ecef",
                        paddingBottom: "0.65rem",
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 600 }}>{team.name}</div>
                        {coachTeamRoster[team.id]?.error ? (
                          <p className="vc-modal__muted" style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
                            {coachTeamRoster[team.id].error}
                          </p>
                        ) : coachTeamRoster[team.id]?.playerCount != null ? (
                          <p className="vc-modal__muted" style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
                            {coachTeamRoster[team.id].playerCount} player
                            {coachTeamRoster[team.id].playerCount === 1 ? "" : "s"}
                            {coachTeamRoster[team.id].coachCount != null && coachTeamRoster[team.id].coachCount > 0
                              ? ` · ${coachTeamRoster[team.id].coachCount} coach${
                                  coachTeamRoster[team.id].coachCount === 1 ? "" : "es"
                                }`
                              : ""}{" "}
                            on roster
                          </p>
                        ) : (
                          <p className="vc-modal__muted" style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
                            Loading roster…
                          </p>
                        )}
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                        <button
                          type="button"
                          className="vc-action-btn"
                          onClick={() => setActiveTeamAndNavigate(team.id, "/roster")}
                        >
                          Roster & add members
                        </button>
                        <button
                          type="button"
                          className="vc-action-btn"
                          onClick={() => setActiveTeamAndNavigate(team.id, "/payments")}
                        >
                          Payments
                        </button>
                        <button
                          type="button"
                          className="vc-action-btn"
                          onClick={() => setActiveTeamAndNavigate(team.id, "/schedule")}
                        >
                          Schedule
                        </button>
                        <button
                          type="button"
                          className="vc-action-btn"
                          onClick={() => setActiveTeamAndNavigate(team.id, "/coach/attendance")}
                        >
                          Session attendance
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
                <div
                  style={{
                    marginTop: "1.25rem",
                    paddingTop: "1rem",
                    borderTop: "1px solid #e8ecef",
                  }}
                >
                  <h3 style={{ fontSize: "0.98rem", margin: "0 0 0.65rem", fontWeight: 700 }}>Create a new team</h3>
                  {createTeamSuccess ? (
                    <p className="vc-director-success" style={{ marginBottom: "0.65rem" }}>
                      {createTeamSuccess}
                    </p>
                  ) : null}
                  {createTeamError ? (
                    <p className="vc-director-error" style={{ marginBottom: "0.65rem" }}>
                      {createTeamError}
                    </p>
                  ) : null}
                  <div style={{ display: "grid", gap: "0.65rem", maxWidth: 420 }}>
                    {coachClubOptions.length > 1 ? (
                      <label className="vc-dash-team-field__label" style={{ display: "grid", gap: "0.35rem" }}>
                        Club
                        <select
                          className="vc-dash-team-select"
                          value={newTeamClubId}
                          onChange={(e) => setNewTeamClubId(Number(e.target.value))}
                        >
                          {coachClubOptions.map((o) => (
                            <option key={o.id} value={o.id}>
                              {o.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    <label className="vc-dash-team-field__label" style={{ display: "grid", gap: "0.35rem" }}>
                      Team name
                      <input
                        className="vc-dash-team-select"
                        value={newTeamName}
                        onChange={(e) => setNewTeamName(e.target.value)}
                        placeholder="e.g. U14 Girls"
                        autoComplete="off"
                      />
                    </label>
                    <label className="vc-dash-team-field__label" style={{ display: "grid", gap: "0.35rem" }}>
                      Season{" "}
                      <span style={{ fontWeight: 400, color: "#6b7580" }}>(optional)</span>
                      <input
                        className="vc-dash-team-select"
                        value={newTeamSeason}
                        onChange={(e) => setNewTeamSeason(e.target.value)}
                        placeholder="e.g. 2026"
                        autoComplete="off"
                      />
                    </label>
                    <button
                      type="button"
                      className="vc-action-btn"
                      disabled={createTeamBusy || !newTeamName.trim()}
                      onClick={() => void onCreateTeamForCoach()}
                    >
                      {createTeamBusy ? "Creating…" : "Create team & open roster"}
                    </button>
                  </div>
                </div>
              </section>
            ) : null}

            {showCoachDashboard && playing.length ? (
              <section className="vc-dash-kpi-card" style={{ marginBottom: "1.25rem" }} aria-labelledby="hub-player-heading">
                <h2 id="hub-player-heading" style={{ fontSize: "1.05rem", margin: "0 0 0.75rem" }}>
                  Your teams
                </h2>
                <ul style={{ listStyle: "none", margin: "0 0 1rem", padding: 0, display: "grid", gap: "0.5rem" }}>
                  {playing.map((team) => (
                    <li key={team.id} style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
                      <span style={{ fontWeight: 600 }}>{team.name}</span>
                      <button
                        type="button"
                        className="vc-action-btn"
                        onClick={() => setActiveTeamAndNavigate(team.id, "/schedule")}
                      >
                        View schedule
                      </button>
                      <button
                        type="button"
                        className="vc-action-btn"
                        onClick={() => setActiveTeamAndNavigate(team.id, "/player/attendance")}
                      >
                        My sessions
                      </button>
                    </li>
                  ))}
                </ul>
                <div style={{ color: "#5c6570", lineHeight: 1.5, marginBottom: "0.75rem" }}>
                  <strong style={{ color: "#2b3035" }}>Fees:</strong>{" "}
                  {feeDue > 0
                    ? `${money(fees.currency, feeDue)} outstanding`
                    : `${money(fees.currency || "USD", 0)} (nothing due)`}
                  {fees.note ? ` — ${fees.note}` : ""}
                </div>
                <button type="button" className="vc-action-btn" onClick={() => navigate("/my-fees")}>
                  View & pay fees
                </button>
              </section>
            ) : null}

            {showParentLinking ? (
              <section
                className="vc-dash-kpi-card"
                style={{ marginBottom: "1.25rem" }}
                aria-labelledby="hub-parent-link-heading"
              >
                <h2 id="hub-parent-link-heading" style={{ fontSize: "1.05rem", margin: "0 0 0.75rem" }}>
                  Parent linking
                </h2>
                <p style={{ margin: "0 0 0.75rem", color: "#5c6570", lineHeight: 1.5 }}>
                  Request access to a child&apos;s player account by user ID. A club director must approve before you can
                  see their payments or pay on their behalf.
                </p>
                {pendingParentLinks.length ? (
                  <ul className="vc-modal__muted" style={{ margin: "0 0 0.75rem", paddingLeft: "1.1rem" }}>
                    {pendingParentLinks.map((row) => (
                      <li key={row.relation_id}>
                        Pending approval for player ID {row.player?.id}
                        {row.player?.email ? ` (${row.player.email})` : ""}.
                      </li>
                    ))}
                  </ul>
                ) : null}
                {linkMessage ? <p className="vc-director-success">{linkMessage}</p> : null}
                {linkError ? <p className="vc-director-error">{linkError}</p> : null}
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
                  <input
                    className="vc-dash-team-select"
                    style={{ maxWidth: 200 }}
                    placeholder="Child user ID"
                    value={linkPlayerId}
                    onChange={(e) => setLinkPlayerId(e.target.value)}
                  />
                  <label style={{ display: "flex", gap: "0.35rem", alignItems: "center", fontSize: "0.9rem" }}>
                    <input
                      type="checkbox"
                      checked={linkLegalGuardian}
                      onChange={(e) => setLinkLegalGuardian(e.target.checked)}
                    />
                    Legal guardian
                  </label>
                  <button
                    type="button"
                    className="vc-action-btn"
                    disabled={linkBusy}
                    onClick={() => void onRequestParentLink()}
                  >
                    {linkBusy ? "Submitting…" : "Request link"}
                  </button>
                </div>
              </section>
            ) : null}

            {showCoachDashboard && children.length ? (
              <section className="vc-dash-kpi-card" style={{ marginBottom: "1.25rem" }} aria-labelledby="hub-parent-heading">
                <h2 id="hub-parent-heading" style={{ fontSize: "1.05rem", margin: "0 0 0.75rem" }}>
                  Family & linked players
                </h2>
                <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "0.75rem" }}>
                  {children.map((ch) => {
                    const u = ch.user || {};
                    const label = [u.first_name, u.last_name].filter(Boolean).join(" ").trim() || u.email || "Linked player";
                    const teamList = ch.teams || [];
                    const childDueFees = childrenFees.filter(
                      (f) => f.player?.id === u.id && f.status !== "paid",
                    );
                    const childDueTotal = childDueFees.reduce(
                      (sum, f) => sum + Number(f.remaining || 0),
                      0,
                    );
                    const childCur = childDueFees[0]?.currency || "USD";
                    return (
                      <li key={u.id ?? label} style={{ borderBottom: "1px solid #e8ecef", paddingBottom: "0.65rem" }}>
                        <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>{label}</div>
                        <div style={{ color: "#5c6570", fontSize: "0.9rem", marginBottom: "0.35rem" }}>
                          Teams: {teamList.length ? teamList.map((t) => t.name).join(", ") : "\u2014"}
                        </div>
                        {childDueFees.length > 0 ? (
                          <div style={{ color: "#c0392b", fontSize: "0.9rem", fontWeight: 600, marginBottom: "0.35rem" }}>
                            {money(childCur, childDueTotal)} outstanding ({childDueFees.length} payment{childDueFees.length > 1 ? "s" : ""} due)
                          </div>
                        ) : (
                          <div style={{ color: "#27ae60", fontSize: "0.9rem", marginBottom: "0.35rem" }}>
                            No payments due
                          </div>
                        )}
                        {teamList.map((t) => (
                          <button
                            key={t.id}
                            type="button"
                            className="vc-action-btn"
                            style={{ marginRight: "0.35rem", marginTop: "0.25rem" }}
                            onClick={() => setActiveTeamAndNavigate(t.id, "/schedule")}
                          >
                            {t.name} schedule
                          </button>
                        ))}
                      </li>
                    );
                  })}
                </ul>
                <div style={{ marginTop: "0.85rem", display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/parent/attendance")}>
                    Family attendance
                  </button>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/my-fees")}>
                    View & pay children&apos;s fees
                  </button>
                </div>
              </section>
            ) : null}

            {showCoachDashboard && !isDirector && !coached.length && !playing.length && !children.length ? (
              <p className="vc-modal__muted">
                When your director links you to a team or family, coach, player, and parent shortcuts appear here.
              </p>
            ) : null}
          </>
        ) : null}
      </section>
    </ClubWorkspaceLayout>
  );
}
