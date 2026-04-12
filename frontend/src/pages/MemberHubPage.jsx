import { useEffect, useMemo, useState } from "react";
import { directorCreateTeam, fetchCurrentUser, fetchMyFees, requestParentLinkToPlayer } from "../api";
import ClubWorkspaceLayout from "../components/ClubWorkspaceLayout";
import { navigate } from "../navigation";

const AUTH_TOKEN_KEY = "netup.auth.token";

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
    me?.user?.assigned_account_role === "parent" ||
    children.length > 0 ||
    pendingParentLinks.length > 0;
  const coachOnlyPayer =
    coached.length > 0 && !playing.length && !children.length && !isDirector;

  const ownUnpaidFees = ownFees.filter((f) => f.status !== "paid");
  const childUnpaidFees = childrenFees.filter((f) => f.status !== "paid");
  const payCur =
    ownUnpaidFees[0]?.currency || childUnpaidFees[0]?.currency || fees.currency || "USD";
  const totalOwnUnpaid = ownUnpaidFees.reduce((s, f) => s + Number(f.remaining || 0), 0);
  const totalChildUnpaid = childUnpaidFees.reduce((s, f) => s + Number(f.remaining || 0), 0);
  const unpaidLineCount = ownUnpaidFees.length + childUnpaidFees.length;
  const totalUnpaidAll = totalOwnUnpaid + totalChildUnpaid;

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

  return (
    <ClubWorkspaceLayout activeTab="dashboard" viewerAccountRole={me?.user?.assigned_account_role || null}>
      <section className="vc-member-hub" style={{ padding: "1.5rem 1.75rem 2.5rem", maxWidth: 920, margin: "0 auto" }}>
        <header style={{ marginBottom: "1.5rem" }}>
          <h1 style={{ fontSize: "1.45rem", margin: "0 0 0.35rem", fontWeight: 700 }}>Dashboard</h1>
          <p style={{ margin: 0, color: "#5c6570", lineHeight: 1.55, maxWidth: 640 }}>
            Your personalized hub based on your club role.
          </p>
        </header>

        {loading ? <p className="vc-modal__muted">{"Loading\u2026"}</p> : null}
        {error ? <p className="vc-modal__error">{error}</p> : null}

        {!loading && !error ? (
          <>
            <section
              className="vc-dash-kpi-card"
              style={{ marginBottom: "1.25rem", display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center" }}
              aria-label="Workspace shortcuts"
            >
              <span style={{ fontWeight: 600, width: "100%", marginBottom: "0.15rem" }}>Workspace</span>
              <button type="button" className="vc-action-btn" onClick={() => navigate("/schedule")}>
                Schedule
              </button>
              <button
                type="button"
                className="vc-action-btn"
                onClick={() => navigate(coachOnlyPayer ? "/payments" : "/my-fees")}
              >
                {coachOnlyPayer ? "Team payments" : "My payments"}
              </button>
              {!hasTeams ? (
                <span className="vc-modal__muted" style={{ flex: "1 1 200px" }}>
                  Ask your director to add you to a roster. If you run teams, use{" "}
                  <button type="button" className="vc-link-cyan" onClick={() => navigate("/director/teams")}>
                    Teams &amp; roster setup
                  </button>{" "}
                  (directors) or create a team under Coaching below (coaches).
                </span>
              ) : null}
            </section>

            {coachOnlyPayer ? (
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
            ) : (
              <section
                className="vc-dash-kpi-card"
                style={{ marginBottom: "1.25rem" }}
                aria-labelledby="hub-payments-heading"
              >
                <h2 id="hub-payments-heading" style={{ fontSize: "1.05rem", margin: "0 0 0.5rem" }}>
                  Payments & balances
                </h2>
                <p style={{ margin: "0 0 0.75rem", color: "#5c6570", lineHeight: 1.5 }}>
                  View every fee line on your account (and linked children), see what is due, and record payments.
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "1.25rem", alignItems: "center" }}>
                  <div>
                    <div className="vc-kpi-label">Total outstanding</div>
                    <div className="vc-kpi-value">
                      {unpaidLineCount ? money(payCur, totalUnpaidAll) : money(payCur, 0)}
                    </div>
                  </div>
                  <div>
                    <div className="vc-kpi-label">Open items</div>
                    <div className="vc-kpi-value">{unpaidLineCount}</div>
                  </div>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/my-fees")}>
                    View all & pay
                  </button>
                </div>
              </section>
            )}

            {isDirector ? (
              <section className="vc-dash-kpi-card" style={{ marginBottom: "1.25rem" }} aria-labelledby="hub-director-heading">
                <h2 id="hub-director-heading" style={{ fontSize: "1.05rem", margin: "0 0 0.75rem" }}>
                  Director & staff
                </h2>
                <p style={{ margin: "0 0 1rem", color: "#5c6570", lineHeight: 1.5 }}>
                  Registration, payments, and roster tools for people who run the club.
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/dashboard")}>
                    Director dashboard
                  </button>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/director/payments")}>
                    Payments & fees
                  </button>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/director/users")}>
                    Registration
                  </button>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/director/teams")}>
                    Teams & roster setup
                  </button>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/payments")}>
                    Payment schedule
                  </button>
                </div>
              </section>
            ) : null}

            {coached.length ? (
              <section className="vc-dash-kpi-card" style={{ marginBottom: "1.25rem" }} aria-labelledby="hub-coach-heading">
                <h2 id="hub-coach-heading" style={{ fontSize: "1.05rem", margin: "0 0 0.75rem" }}>
                  Coaching
                </h2>
                <p style={{ margin: "0 0 1rem", color: "#5c6570", lineHeight: 1.5 }}>
                  Open a roster to add players or coaches by user ID, or create another team in the same club.
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
                      <span style={{ fontWeight: 600 }}>{team.name}</span>
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

            {playing.length ? (
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

            {children.length ? (
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
                <div style={{ marginTop: "0.85rem" }}>
                  <button type="button" className="vc-action-btn" onClick={() => navigate("/my-fees")}>
                    View & pay children's fees
                  </button>
                </div>
              </section>
            ) : null}

            {!isDirector && !coached.length && !playing.length && !children.length ? (
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
