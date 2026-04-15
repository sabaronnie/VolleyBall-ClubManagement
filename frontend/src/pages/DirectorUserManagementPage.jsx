import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  directorRemovePlayerFromTeam,
  directorResolveParentLink,
  directorSetUserAccountRole,
  fetchTeamMembers,
  fetchCurrentUser,
  fetchDirectorPendingParentLinks,
  fetchDirectorUserDirectory,
  fetchPendingPlayerParentInvitations,
  resolvePlayerParentInvitation,
} from "../api";
import InlineDropdown from "../components/InlineDropdown";

const AUTH_TOKEN_KEY = "netup.auth.token";

function navigate(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

const DIRECTORY_ROLE_OPTIONS = [
  { value: "director", label: "Director" },
  { value: "coach", label: "Coach" },
  { value: "player", label: "Player" },
];

function formatDirectoryRole(role) {
  const match = DIRECTORY_ROLE_OPTIONS.find((option) => option.value === role);
  if (match) return match.label;
  if (role === "parent") return "Parent";
  return role ? role.charAt(0).toUpperCase() + role.slice(1) : "—";
}

function formatVerificationStatus(status) {
  if (status === "pending") {
    return "Pending review";
  }
  if (status === "rejected") {
    return "Rejected";
  }
  if (status === "verified") {
    return "Verified";
  }
  return status || "—";
}

function userTeamLabels(user) {
  const labels = [];
  const seen = new Set();

  (Array.isArray(user?.teams) ? user.teams : []).forEach((team) => {
    const label = team?.short_name || team?.name || "";
    if (label && !seen.has(label)) {
      seen.add(label);
      labels.push(label);
    }
  });

  (Array.isArray(user?.team_short_names) ? user.team_short_names : []).forEach((label) => {
    const normalized = String(label || "").trim();
    if (normalized && !seen.has(normalized)) {
      seen.add(normalized);
      labels.push(normalized);
    }
  });

  return labels;
}

function mergeDirectoryUsersWithRosterTeams(users, teams, rosterPayloadsByTeamId) {
  const labelsByUserId = new Map();

  (Array.isArray(users) ? users : []).forEach((user) => {
    const existing = userTeamLabels(user);
    if (existing.length) {
      labelsByUserId.set(user.id, existing);
    }
  });

  (Array.isArray(teams) ? teams : []).forEach((team) => {
    const roster = rosterPayloadsByTeamId.get(Number(team.id));
    const members = Array.isArray(roster?.members) ? roster.members : [];
    const label = team?.short_name || team?.name || "";
    if (!label) return;

    members.forEach((member) => {
      const userId = Number(member?.user?.id ?? member?.user_id ?? member?.id);
      if (!Number.isFinite(userId)) return;
      const current = labelsByUserId.get(userId) || [];
      if (!current.includes(label)) {
        labelsByUserId.set(userId, [...current, label]);
      }
    });
  });

  return (Array.isArray(users) ? users : []).map((user) => {
    const labels = labelsByUserId.get(user.id) || [];
    if (!labels.length) {
      return user;
    }
    return {
      ...user,
      team_short_names: labels,
      teams:
        Array.isArray(user?.teams) && user.teams.length
          ? user.teams
          : labels.map((label) => ({ short_name: label, name: label })),
    };
  });
}

export default function DirectorUserManagementPage({
  embedded = false,
  onOpenPayments = null,
  focusedTeamId = null,
  showParentLinkRequests = true,
}) {
  const [allUsers, setAllUsers] = useState([]);
  const [directoryCount, setDirectoryCount] = useState(0);
  const [loadingDirectory, setLoadingDirectory] = useState(true);
  const [viewerIsStaff, setViewerIsStaff] = useState(false);
  const [viewerUserId, setViewerUserId] = useState(null);
  const [ownedClubs, setOwnedClubs] = useState([]);
  const [canManageRoles, setCanManageRoles] = useState(false);
  const [canRemovePlayers, setCanRemovePlayers] = useState(false);
  const [showParentLinks, setShowParentLinks] = useState(false);
  const [showPlayerParentInvites, setShowPlayerParentInvites] = useState(false);
  const [directoryScopeKind, setDirectoryScopeKind] = useState("club");
  const [directoryHeading, setDirectoryHeading] = useState("All people in your club");
  const [directoryDescription, setDirectoryDescription] = useState(
    "This list is limited to people connected to the clubs you direct, including linked parents.",
  );
  const [directoryTeams, setDirectoryTeams] = useState([]);
  const [error, setError] = useState("");
  const [directoryError, setDirectoryError] = useState("");
  const [actionKey, setActionKey] = useState("");
  const [roleEdits, setRoleEdits] = useState({});
  const [directorClubEdits, setDirectorClubEdits] = useState({});
  const [parentLinkRows, setParentLinkRows] = useState([]);
  const [loadingParentLinks, setLoadingParentLinks] = useState(true);
  const [parentLinkError, setParentLinkError] = useState("");
  const [parentLinkSuccess, setParentLinkSuccess] = useState("");
  const [playerParentInviteRows, setPlayerParentInviteRows] = useState([]);
  const [loadingPlayerParentInvites, setLoadingPlayerParentInvites] = useState(true);
  const [playerParentInviteError, setPlayerParentInviteError] = useState("");
  const [playerParentInviteSuccess, setPlayerParentInviteSuccess] = useState("");
  const [teamFilter, setTeamFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [directorySuccess, setDirectorySuccess] = useState("");
  const parentLinkSuccessTimerRef = useRef(null);

  useEffect(() => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
      navigate("/login");
    }
  }, []);

  const loadDirectory = useCallback(async () => {
    setLoadingDirectory(true);
    setDirectoryError("");
    setDirectorySuccess("");
    try {
      const me = await fetchCurrentUser();
      setViewerIsStaff(Boolean(me.viewer_is_staff));
      setViewerUserId(me.user?.id ?? null);
      setOwnedClubs(me.owned_clubs || []);
      const directorView = Boolean(me.viewer_is_staff || me.is_director_or_staff || (me.owned_clubs || []).length > 0);
      const coachView = !directorView && (me.coached_teams || []).length > 0;
      setCanManageRoles(directorView);
      setCanRemovePlayers(directorView || coachView);
      setShowParentLinks(directorView && showParentLinkRequests);
      setShowPlayerParentInvites(directorView || coachView);
      setDirectoryTeams(directorView ? (me.director_teams || []) : (me.coached_teams || []));
      const payload = await fetchDirectorUserDirectory(800, { teamId: focusedTeamId });
      const rows = payload.users || [];
      const scopeKind = payload.scope?.kind || (directorView ? "club" : "team");
      setDirectoryScopeKind(scopeKind);
      if (scopeKind === "team") {
        const scopedTeamName = payload.scope?.names?.[0] || "";
        setDirectoryHeading(scopedTeamName ? `People in ${scopedTeamName}` : "All people on your team");
        setDirectoryDescription(
          "This list is limited to the coaches, players, and linked parents connected to your team.",
        );
      } else if (scopeKind === "all") {
        setDirectoryHeading("All people in the app");
        setDirectoryDescription("This list includes every account in the app.");
      } else {
        setDirectoryHeading(
          (me.owned_clubs || []).length > 1 ? "All people in your clubs" : "All people in your club",
        );
        setDirectoryDescription(
          "This list is limited to the directors, coaches, players, and linked parents connected to your club.",
        );
      }
      const accessibleTeams = directorView ? (me.director_teams || []) : (me.coached_teams || []);
      const needsRosterFallback = rows.some((row) => !userTeamLabels(row).length);
      let finalRows = rows;
      if (needsRosterFallback && accessibleTeams.length) {
        const rosterEntries = await Promise.all(
          accessibleTeams.map(async (team) => {
            try {
              const roster = await fetchTeamMembers(team.id);
              return [Number(team.id), roster];
            } catch {
              return [Number(team.id), null];
            }
          }),
        );
        finalRows = mergeDirectoryUsersWithRosterTeams(rows, accessibleTeams, new Map(rosterEntries));
      }
      setAllUsers(finalRows);
      setDirectoryCount(payload.count ?? rows.length);
      setRoleEdits({});
      setDirectorClubEdits({});
    } catch (err) {
      setAllUsers([]);
      setDirectoryCount(0);
      setDirectoryTeams([]);
      setDirectoryError(err.message || "Could not load user directory.");
    } finally {
      setLoadingDirectory(false);
    }
  }, [focusedTeamId, showParentLinkRequests]);

  const availableTeamFilters = useMemo(() => {
    const names = new Set();
    directoryTeams.forEach((team) => {
      const label = team?.short_name || team?.name || "";
      if (label) {
        names.add(label);
      }
    });
    allUsers.forEach((user) => {
      (user.teams || []).forEach((team) => {
        const label = team?.short_name || team?.name || "";
        if (label) {
          names.add(label);
        }
      });
      (user.team_short_names || []).forEach((teamShortName) => {
        if (teamShortName) {
          names.add(teamShortName);
        }
      });
    });
    return Array.from(names).sort((left, right) => left.localeCompare(right));
  }, [allUsers, directoryTeams]);

  const teamFilterOptions = useMemo(
    () => [
      { value: "", label: "All teams" },
      ...availableTeamFilters.map((teamShortName) => ({
        value: teamShortName,
        label: teamShortName,
      })),
    ],
    [availableTeamFilters],
  );

  const filteredUsers = useMemo(() => {
    const normalizedTeam = teamFilter.trim().toLowerCase();
    const normalizedSearch = searchQuery.trim().toLowerCase();

    return allUsers.filter((user) => {
      const fullName = `${user.first_name || ""} ${user.last_name || ""}`.trim().toLowerCase();
      const email = (user.email || "").toLowerCase();
      const teamLabels = userTeamLabels(user).map((value) => String(value).toLowerCase());

      if (normalizedTeam && !teamLabels.includes(normalizedTeam)) {
        return false;
      }
      if (normalizedSearch && !fullName.includes(normalizedSearch) && !email.includes(normalizedSearch)) {
        return false;
      }
      return true;
    });
  }, [allUsers, searchQuery, teamFilter]);

  const loadParentLinks = useCallback(async () => {
    setLoadingParentLinks(true);
    setParentLinkError("");
    try {
      const payload = await fetchDirectorPendingParentLinks();
      setParentLinkRows(payload.requests || []);
    } catch (err) {
      setParentLinkRows([]);
      setParentLinkError(err.message || "Could not load parent link requests.");
    } finally {
      setLoadingParentLinks(false);
    }
  }, []);

  const loadPlayerParentInvites = useCallback(async () => {
    setLoadingPlayerParentInvites(true);
    setPlayerParentInviteError("");
    try {
      const payload = await fetchPendingPlayerParentInvitations();
      setPlayerParentInviteRows(payload.requests || []);
    } catch (err) {
      setPlayerParentInviteRows([]);
      setPlayerParentInviteError(err.message || "Could not load player parent invitations.");
    } finally {
      setLoadingPlayerParentInvites(false);
    }
  }, []);

  useEffect(() => {
    void loadDirectory();
  }, [loadDirectory]);

  useEffect(() => {
    if (showParentLinks) {
      void loadParentLinks();
      return;
    }
    setParentLinkRows([]);
    setParentLinkError("");
    setLoadingParentLinks(false);
  }, [loadParentLinks, showParentLinks]);

  useEffect(() => {
    if (showPlayerParentInvites) {
      void loadPlayerParentInvites();
      return;
    }
    setPlayerParentInviteRows([]);
    setPlayerParentInviteError("");
    setLoadingPlayerParentInvites(false);
  }, [loadPlayerParentInvites, showPlayerParentInvites]);

  useEffect(() => {
    return () => {
      if (parentLinkSuccessTimerRef.current != null) {
        window.clearTimeout(parentLinkSuccessTimerRef.current);
      }
    };
  }, []);

  const effectiveRole = (row) => (roleEdits[row.id] !== undefined ? roleEdits[row.id] : row.role || "");

  const onSaveAccountRole = async (userId) => {
    const key = `role-${userId}`;
    setActionKey(key);
    setError("");
    try {
      const row = allUsers.find((u) => u.id === userId);
      const nextRole = effectiveRole(row);
      if (!nextRole) {
        setError("Choose a role before saving.");
        return;
      }
      const body = { role: nextRole };
      if (nextRole === "director" && ownedClubs.length > 1) {
        const cid = directorClubEdits[userId] ?? ownedClubs[0]?.id;
        if (cid != null) {
          body.club_id = Number(cid);
        }
      }
      if (nextRole === "coach" || nextRole === "player") {
        const teamId =
          focusedTeamId != null && focusedTeamId !== "__all__"
            ? focusedTeamId
            : Array.isArray(row?.teams) && row.teams.length === 1
              ? row.teams[0]?.id
              : null;
        if (teamId != null) {
          body.team_id = Number(teamId);
        }
      }
      await directorSetUserAccountRole(userId, body);
      setRoleEdits((m) => {
        const next = { ...m };
        delete next[userId];
        return next;
      });
      setDirectorClubEdits((m) => {
        const next = { ...m };
        delete next[userId];
        return next;
      });
      await loadDirectory();
    } catch (err) {
      setError(err.message || "Could not update role.");
    } finally {
      setActionKey("");
    }
  };

  const onResolveParentLink = async (relationId, action) => {
    const key = `plink-${relationId}-${action}`;
    setActionKey(key);
    setParentLinkError("");
    setParentLinkSuccess("");
    if (parentLinkSuccessTimerRef.current != null) {
      window.clearTimeout(parentLinkSuccessTimerRef.current);
      parentLinkSuccessTimerRef.current = null;
    }
    try {
      await directorResolveParentLink(relationId, action);
      await loadParentLinks();
      if (action === "approve") {
        setParentLinkSuccess("Parent link approved successfully.");
        parentLinkSuccessTimerRef.current = window.setTimeout(() => {
          setParentLinkSuccess("");
          parentLinkSuccessTimerRef.current = null;
        }, 8000);
      }
    } catch (err) {
      setParentLinkSuccess("");
      setParentLinkError(err.message || "Could not update link request.");
    } finally {
      setActionKey("");
    }
  };

  const onResolvePlayerParentInvite = async (invitationId, action) => {
    const key = `player-parent-invite-${invitationId}-${action}`;
    setActionKey(key);
    setPlayerParentInviteError("");
    setPlayerParentInviteSuccess("");
    try {
      const res = await resolvePlayerParentInvitation(invitationId, action);
      setPlayerParentInviteSuccess(
        res?.message || (action === "approve" ? "Approval saved successfully." : "Request rejected."),
      );
      await loadPlayerParentInvites();
    } catch (err) {
      setPlayerParentInviteSuccess("");
      setPlayerParentInviteError(err.message || "Could not update player parent invitation.");
    } finally {
      setActionKey("");
    }
  };

  const onRemovePlayer = async (row) => {
    const rowTeams = Array.isArray(row?.teams) ? row.teams : [];
    const targetTeamId =
      focusedTeamId != null && focusedTeamId !== ""
        ? Number(focusedTeamId)
        : rowTeams.length === 1
          ? Number(rowTeams[0]?.id)
          : null;

    if (!targetTeamId) {
      setError("Pick a single team scope before removing a player who belongs to multiple teams.");
      return;
    }

    const key = `remove-player-${row.id}`;
    setActionKey(key);
    setError("");
    setDirectorySuccess("");
    try {
      const res = await directorRemovePlayerFromTeam(row.id, { team_id: targetTeamId });
      setDirectorySuccess(res?.message || "Player removed from team successfully.");
      await loadDirectory();
    } catch (err) {
      setError(err.message || "Could not remove player.");
    } finally {
      setActionKey("");
    }
  };

  const cardContent = (
    <div className={`vc-director-card${embedded ? " vc-director-card--embedded" : ""}`}>
      {!embedded ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center" }}>
          <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
            ← Dashboard
          </button>
          <button
            type="button"
            className="vc-link-cyan"
            onClick={() => {
              if (onOpenPayments) {
                onOpenPayments();
                return;
              }
              navigate(canManageRoles ? "/director/payments" : "/payments");
            }}
          >
            Payments & fees
          </button>
        </div>
      ) : null}

      {error || directoryError ? (
        <div className="vc-director-error">{error || directoryError}</div>
      ) : null}
      {directorySuccess ? <div className="vc-director-success">{directorySuccess}</div> : null}
      {parentLinkError ? <div className="vc-director-error">{parentLinkError}</div> : null}
      {parentLinkSuccess ? <div className="vc-director-success">{parentLinkSuccess}</div> : null}
      {playerParentInviteError ? <div className="vc-director-error">{playerParentInviteError}</div> : null}
      {playerParentInviteSuccess ? <div className="vc-director-success">{playerParentInviteSuccess}</div> : null}

      {showParentLinks ? (
        <section className="vc-director-section">
            <h2 className="vc-panel-title">Parent–child link requests</h2>
            <p className="vc-modal__muted" style={{ marginTop: 0 }}>
              Parents must be approved before they can view or pay a linked player&apos;s fees.
            </p>
            {loadingParentLinks ? (
              <p className="vc-director-loading">Loading requests…</p>
            ) : (
              <div className="vc-director-table-wrap">
                <table className="vc-director-table">
                  <thead>
                    <tr>
                      <th>Parent</th>
                      <th>Player</th>
                      <th>Club / team</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {parentLinkRows.length === 0 ? (
                      <tr>
                        <td colSpan={5} style={{ color: "#6b7580", fontWeight: 600 }}>
                          No pending parent link requests.
                        </td>
                      </tr>
                    ) : (
                      parentLinkRows.map((row) => {
                        const rel = row.relation || {};
                        const parentUser = rel.parent || {};
                        const playerUser = row.player || {};
                        const rid = rel.id;
                        const busyA = actionKey === `plink-${rid}-approve`;
                        const busyR = actionKey === `plink-${rid}-reject`;
                        const parentLabel =
                          [parentUser.first_name, parentUser.last_name].filter(Boolean).join(" ").trim() ||
                          parentUser.email ||
                          "—";
                        const playerLabel =
                          [playerUser.first_name, playerUser.last_name].filter(Boolean).join(" ").trim() ||
                          playerUser.email ||
                          "—";
                        return (
                          <tr key={rid}>
                            <td>
                              <div style={{ fontWeight: 600 }}>{parentLabel}</div>
                              <div className="vc-modal__muted" style={{ fontSize: "0.85rem" }}>
                                ID {parentUser.id} {parentUser.email ? `· ${parentUser.email}` : ""}
                              </div>
                            </td>
                            <td>
                              <div style={{ fontWeight: 600 }}>{playerLabel}</div>
                              <div className="vc-modal__muted" style={{ fontSize: "0.85rem" }}>
                                ID {playerUser.id || rel.player_id} {playerUser.email ? `· ${playerUser.email}` : ""}
                              </div>
                            </td>
                            <td>
                              {row.club_name || "—"}
                              <br />
                              <span className="vc-modal__muted">{row.team_name || "—"}</span>
                            </td>
                            <td style={{ textTransform: "capitalize" }}>{rel.approval_status || "pending"}</td>
                            <td>
                              <button
                                type="button"
                                className="vc-du-action vc-du-action--success"
                                disabled={busyA || busyR}
                                onClick={() => void onResolveParentLink(rid, "approve")}
                              >
                                {busyA ? "…" : "Approve"}
                              </button>
                              <button
                                type="button"
                                className="vc-du-action vc-du-action--danger"
                                disabled={busyA || busyR}
                                onClick={() => void onResolveParentLink(rid, "reject")}
                              >
                                {busyR ? "…" : "Reject"}
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            )}
        </section>
      ) : null}

      {showPlayerParentInvites ? (
        <section className="vc-director-section">
          <h2 className="vc-panel-title">Player parent invitations</h2>
          <p className="vc-modal__muted" style={{ marginTop: 0 }}>
            Players can request parent access by email. A coach or a club director can approve before the invitation
            email is sent.
          </p>
          {loadingPlayerParentInvites ? (
            <p className="vc-director-loading">Loading player parent invitations…</p>
          ) : (
            <div className="vc-director-table-wrap">
              <table className="vc-director-table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Parent email</th>
                    <th>Club / team</th>
                    <th>Approvals</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {playerParentInviteRows.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ color: "#6b7580", fontWeight: 600 }}>
                        No pending player parent invitations.
                      </td>
                    </tr>
                  ) : (
                    playerParentInviteRows.map((row) => {
                      const req = row.request || {};
                      const playerUser = row.player || req.player || {};
                      const rid = req.id;
                      const busyApprove = actionKey === `player-parent-invite-${rid}-approve`;
                      const busyReject = actionKey === `player-parent-invite-${rid}-reject`;
                      const playerLabel =
                        [playerUser.first_name, playerUser.last_name].filter(Boolean).join(" ").trim() ||
                        playerUser.email ||
                        "—";
                      const approvalBits = [];
                      if (req.coach_approved) {
                        approvalBits.push("Coach approved");
                      }
                      if (req.director_approved) {
                        approvalBits.push("Director approved");
                      }
                      if (!approvalBits.length) {
                        approvalBits.push("Waiting for coach or director");
                      }
                      return (
                        <tr key={rid}>
                          <td>
                            <div style={{ fontWeight: 600 }}>{playerLabel}</div>
                            <div className="vc-modal__muted" style={{ fontSize: "0.85rem" }}>
                              ID {playerUser.id} {playerUser.email ? `· ${playerUser.email}` : ""}
                            </div>
                          </td>
                          <td>{req.invited_email || "—"}</td>
                          <td>
                            {row.club_name || req.club_name || "—"}
                            <br />
                            <span className="vc-modal__muted">{row.team_name || req.team?.name || "—"}</span>
                          </td>
                          <td>{approvalBits.join(" · ")}</td>
                          <td>
                            <button
                              type="button"
                              className="vc-du-action vc-du-action--success"
                              disabled={busyApprove || busyReject}
                              onClick={() => void onResolvePlayerParentInvite(rid, "approve")}
                            >
                              {busyApprove ? "…" : "Approve"}
                            </button>
                            <button
                              type="button"
                              className="vc-du-action vc-du-action--danger"
                              disabled={busyApprove || busyReject}
                              onClick={() => void onResolvePlayerParentInvite(rid, "reject")}
                            >
                              {busyReject ? "…" : "Reject"}
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : null}

      <section className="vc-director-section">
          <h2 className="vc-panel-title">{directoryHeading}</h2>
          <p className="vc-modal__muted" style={{ marginTop: 0 }}>
            {directoryDescription}{" "}
            {canManageRoles ? (
              <>
                Each person has one <strong>role</strong> (Director, Coach, or Player). Changing it updates
                their permissions. You cannot remove your own Director role; you can promote others to Director for a
                club you manage, or change another Director to a different role.
              </>
            ) : (
              <>As a coach, this view is limited to your team scope. You can remove players from your team, but you cannot change account roles.</>
            )}
          </p>
          <div className="vc-director-directory-filters">
            <label className="vc-director-directory-filters__field">
              <span>Team</span>
              <InlineDropdown
                value={teamFilter}
                onChange={setTeamFilter}
                options={teamFilterOptions}
                ariaLabel="Filter directory by team"
                className="vc-inline-dropdown--directory-filter"
                placeholder="All teams"
              />
            </label>
            <label className="vc-director-directory-filters__field">
              <span>Search</span>
              <input
                className="vc-director-modal__select"
                type="text"
                placeholder="Search by name or email"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </label>
          </div>
          {loadingDirectory ? (
            <p className="vc-director-loading">Loading directory…</p>
          ) : (
            <div className="vc-director-table-wrap">
              <p className="vc-director-loading" style={{ color: "#6b7580", marginBottom: "0.75rem" }}>
                Showing {filteredUsers.length} of {directoryCount} loaded
                {directoryScopeKind === "team" ? " from your team scope" : directoryScopeKind === "club" ? " from your club scope" : ""}.
              </p>
              {(() => {
                const showActionColumn = canManageRoles || canRemovePlayers;
                return (
              <table className="vc-director-table">
                <thead>
                  <tr>
                    <th>User ID</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Team</th>
                    <th>Status</th>
                    <th>Role</th>
                    {showActionColumn ? <th /> : null}
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={showActionColumn ? 7 : 6} style={{ color: "#6b7580", fontWeight: 600 }}>
                        No users found.
                      </td>
                    </tr>
                  ) : (
                    filteredUsers.map((u) => {
                      const fullName = `${u.first_name || ""} ${u.last_name || ""}`.trim() || u.email;
                      const teamLabels = userTeamLabels(u);
                      const saveBusy = actionKey === `role-${u.id}`;
                      const removeBusy = actionKey === `remove-player-${u.id}`;
                      const busy = saveBusy || removeBusy;
                      const staffLocked = u.is_staff && !viewerIsStaff;
                      const currentRole = u.role || "";
                      const selectVal = roleEdits[u.id] !== undefined ? roleEdits[u.id] : currentRole || "";
                      const selfDirectorLocked = viewerUserId === u.id && currentRole === "director";
                      const rowDirty = roleEdits[u.id] !== undefined && roleEdits[u.id] !== currentRole;
                      const saveDisabled =
                        !rowDirty || staffLocked || busy || selfDirectorLocked || !selectVal;
                      const removePlayerDisabled =
                        currentRole !== "player" ||
                        busy ||
                        !Array.isArray(u.teams) ||
                        u.teams.length === 0 ||
                        (focusedTeamId == null && u.teams.length !== 1);
                      const removePlayerTitle =
                        focusedTeamId == null && Array.isArray(u.teams) && u.teams.length > 1
                          ? "Filter to a single team before removing this player."
                          : "";
                      return (
                        <tr key={u.id}>
                          <td>
                            <code>{u.id}</code>
                          </td>
                          <td>{fullName}</td>
                          <td>{u.email}</td>
                          <td>{teamLabels.join(", ") || "—"}</td>
                          <td>{formatVerificationStatus(u.verification_status)}</td>
                          <td>
                            <div style={{ display: "grid", gap: "0.35rem", maxWidth: 280 }}>
                              <InlineDropdown
                                value={selectVal}
                                valueLabel={formatDirectoryRole(selectVal)}
                                onChange={(v) => {
                                  setRoleEdits((m) => ({ ...m, [u.id]: v }));
                                  if (v === "director" && ownedClubs.length > 1) {
                                    setDirectorClubEdits((m) => ({
                                      ...m,
                                      [u.id]: m[u.id] ?? ownedClubs[0]?.id,
                                    }));
                                  }
                                }}
                                options={DIRECTORY_ROLE_OPTIONS}
                                ariaLabel={`Account role for ${fullName}`}
                                className="vc-inline-dropdown--directory-role"
                                placeholder="—"
                                disabled={!canManageRoles || staffLocked || busy || selfDirectorLocked}
                                portal
                              />
                              {canManageRoles ? (
                                <>
                                {selectVal === "director" && ownedClubs.length > 1 ? (
                                  <label className="vc-modal__muted" style={{ fontSize: "0.82rem", display: "grid", gap: "0.25rem" }}>
                                    Club for director access
                                    <select
                                      className="vc-director-modal__select"
                                      value={String(directorClubEdits[u.id] ?? ownedClubs[0]?.id ?? "")}
                                      disabled={staffLocked || busy || selfDirectorLocked}
                                      onChange={(e) =>
                                        setDirectorClubEdits((m) => ({
                                          ...m,
                                          [u.id]: Number(e.target.value),
                                        }))
                                      }
                                    >
                                      {ownedClubs.map((c) => (
                                        <option key={c.id} value={String(c.id)}>
                                          {c.name}
                                        </option>
                                      ))}
                                    </select>
                                  </label>
                                ) : null}
                                {selfDirectorLocked ? (
                                  <span className="vc-modal__muted" style={{ fontSize: "0.8rem" }}>
                                    Your director role is fixed on your own account.
                                  </span>
                                ) : null}
                                </>
                              ) : null}
                            </div>
                          </td>
                          {showActionColumn ? (
                            <td>
                              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
                                {canManageRoles ? (
                                  <button
                                    type="button"
                                    className="vc-du-action"
                                    disabled={saveDisabled}
                                    onClick={() => void onSaveAccountRole(u.id)}
                                  >
                                    {saveBusy ? "…" : "Save"}
                                  </button>
                                ) : null}
                                <button
                                  type="button"
                                  className="vc-du-action vc-du-action--danger"
                                  disabled={!canRemovePlayers || removePlayerDisabled}
                                  title={removePlayerTitle}
                                  onClick={() => void onRemovePlayer(u)}
                                >
                                  {removeBusy ? "…" : "Remove Player"}
                                </button>
                              </div>
                            </td>
                          ) : null}
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
                );
              })()}
            </div>
          )}
      </section>
    </div>
  );

  if (embedded) {
    return cardContent;
  }

  return (
    <div className="vc-director-page">
      <p className="vc-director-kicker">User Management</p>
      {cardContent}
    </div>
  );
}
