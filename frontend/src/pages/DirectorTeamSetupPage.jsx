import { useCallback, useEffect, useMemo, useState } from "react";
import {
  directorAddTeamMember,
  directorCreateTeam,
  directorDeleteClub,
  directorRemoveTeamMember,
  directorDeleteTeam,
  fetchCurrentUser,
  fetchTeamMembers,
  inviteTeamMemberByEmail,
} from "../api";
import { navigate } from "../navigation";

const AUTH_TOKEN_KEY = "netup.auth.token";

function roleLabel(role) {
  if (role === "coach") return "Coach";
  if (role === "player") return "Player";
  return role || "—";
}

export default function DirectorTeamSetupPage({
  embedded = false,
  preferredClubId = null,
  onOpenUsers = null,
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [ownedClubs, setOwnedClubs] = useState([]);
  const [directorTeams, setDirectorTeams] = useState([]);
  const [teamId, setTeamId] = useState("");
  const [membersPayload, setMembersPayload] = useState(null);
  const [membersLoading, setMembersLoading] = useState(false);
  const [createDraftByClub, setCreateDraftByClub] = useState({});
  const [createBusyClubId, setCreateBusyClubId] = useState(null);
  const [deleteTeamBusyId, setDeleteTeamBusyId] = useState(null);
  const [deleteClubBusy, setDeleteClubBusy] = useState(null);
  const [deleteClubBusyId, setDeleteClubBusyId] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteBusy, setInviteBusy] = useState(false);
  const [removeBusyKey, setRemoveBusyKey] = useState("");

  const [memberUserId, setMemberUserId] = useState("");
  const [memberRole, setMemberRole] = useState("player");
  const [addBusy, setAddBusy] = useState(false);

  const bumpTeams = () => window.dispatchEvent(new Event("netup-teams-changed"));

  const loadMe = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const me = await fetchCurrentUser();
      const clubs = me.owned_clubs || [];
      setOwnedClubs(clubs);
      setDirectorTeams(me.director_teams || []);
    } catch (e) {
      setError(e.message || "Could not load your account.");
    } finally {
      setLoading(false);
    }
  }, [preferredClubId]);

  useEffect(() => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
      navigate("/login");
      return;
    }
    void loadMe();
  }, [loadMe]);

  useEffect(() => {
    setSuccessMessage("");
    setMembersPayload(null);
  }, [ownedClubs.length]);

  const teamsByClubId = useMemo(() => {
    const out = {};
    directorTeams.forEach((team) => {
      const key = Number(team.club_id);
      if (!out[key]) {
        out[key] = [];
      }
      out[key].push(team);
    });
    return out;
  }, [directorTeams]);

  useEffect(() => {
    if (!teamId) {
      setMembersPayload(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setMembersLoading(true);
      setError("");
      try {
        const data = await fetchTeamMembers(Number(teamId));
        if (!cancelled) {
          setMembersPayload(data);
        }
      } catch (e) {
        if (!cancelled) {
          setMembersPayload(null);
          setError(e.message || "Could not load team members.");
        }
      } finally {
        if (!cancelled) {
          setMembersLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [teamId]);

  useEffect(() => {
    if (!membersPayload) {
      return;
    }
    setMemberRole((prev) => {
      if (prev === "coach" && !membersPayload.can_add_coach && membersPayload.can_add_player) {
        return "player";
      }
      if (prev === "player" && !membersPayload.can_add_player && membersPayload.can_add_coach) {
        return "coach";
      }
      return prev;
    });
  }, [membersPayload]);

  const updateCreateDraft = (targetClubId, field, value) => {
    const key = Number(targetClubId);
    setCreateDraftByClub((prev) => ({
      ...prev,
      [key]: {
        name: prev[key]?.name || "",
        season: prev[key]?.season || "",
        [field]: value,
      },
    }));
  };

  const onCreateTeam = async (targetClubId) => {
    const resolvedClubId = Number(targetClubId);
    const draft = createDraftByClub[resolvedClubId] || { name: "", season: "" };
    if (!resolvedClubId || !draft.name.trim()) {
      setError("Team name is required.");
      return;
    }
    setCreateBusyClubId(resolvedClubId);
    setError("");
    setSuccessMessage("");
    try {
      const body = { name: draft.name.trim() };
      if ((draft.season || "").trim()) {
        body.season = draft.season.trim();
      }
      const res = await directorCreateTeam(resolvedClubId, body);
      setCreateDraftByClub((prev) => ({
        ...prev,
        [resolvedClubId]: { name: "", season: "" },
      }));
      setSuccessMessage(res?.message || "Team created.");
      await loadMe();
      bumpTeams();
      if (res?.team?.id) {
        setTeamId(String(res.team.id));
      }
    } catch (e) {
      setError(e.message || "Could not create team.");
    } finally {
      setCreateBusyClubId(null);
    }
  };

  const performDeleteTeam = async (targetTeam) => {
    if (!targetTeam?.id) {
      return;
    }
    setDeleteTeamBusyId(targetTeam.id);
    setError("");
    setSuccessMessage("");
    try {
      const res = await directorDeleteTeam(targetTeam.id);
      setSuccessMessage(res?.message || "Team deleted successfully.");
      if (String(teamId) === String(targetTeam.id)) {
        setTeamId("");
        setMembersPayload(null);
      }
      await loadMe();
      bumpTeams();
    } catch (e) {
      setError(e.message || "Could not delete team.");
    } finally {
      setDeleteTeamBusyId(null);
    }
  };

  const performDeleteClub = async (targetClubId) => {
    const resolvedClubId = Number(targetClubId);
    if (!resolvedClubId) {
      return;
    }
    setDeleteClubBusy(resolvedClubId);
    setDeleteClubBusyId(resolvedClubId);
    setError("");
    setSuccessMessage("");
    try {
      const res = await directorDeleteClub(resolvedClubId);
      setSuccessMessage(res?.message || "Club deleted successfully.");
      setTeamId("");
      setMembersPayload(null);
      await loadMe();
      bumpTeams();
    } catch (e) {
      setError(e.message || "Could not delete club.");
    } finally {
      setDeleteClubBusy(null);
      setDeleteClubBusyId(null);
    }
  };

  const openDeleteTeamConfirm = (team, club) => {
    setConfirmDialog({
      kind: "team",
      teamId: team.id,
      teamName: team.name,
      clubName: club.name,
      message:
        "Are you sure you want to delete this team? This will remove all team memberships and notify affected members.",
    });
  };

  const openDeleteClubConfirm = (club) => {
    setConfirmDialog({
      kind: "club",
      clubId: club.id,
      clubName: club.name,
      message:
        "Are you sure you want to delete this club? This will delete its teams, remove affected memberships, and notify affected members.",
    });
  };

  const openRemoveMemberConfirm = (team, memberRow) => {
    setConfirmDialog({
      kind: "member",
      teamId: team.id,
      memberUserId: memberRow?.user?.id,
      message: `Remove ${memberRow?.user?.email || "this member"} from "${team.name}"?`,
    });
  };

  const onInviteByEmail = async (team) => {
    const email = inviteEmail.trim().toLowerCase();
    if (!email) {
      setError("Enter an email address.");
      return;
    }
    setInviteBusy(true);
    setError("");
    setSuccessMessage("");
    try {
      const res = await inviteTeamMemberByEmail(Number(team.id), { email, role: "player" });
      setInviteEmail("");
      setSuccessMessage(res?.message || "Invitation sent successfully.");
    } catch (e) {
      setError(e.message || "Could not invite member.");
    } finally {
      setInviteBusy(false);
    }
  };

  const performRemoveMember = async (teamIdValue, userId) => {
    if (!teamIdValue || !userId) {
      return;
    }
    const busyKey = `${teamIdValue}:${userId}`;
    setRemoveBusyKey(busyKey);
    setError("");
    setSuccessMessage("");
    try {
      const res = await directorRemoveTeamMember(Number(teamIdValue), Number(userId));
      setSuccessMessage(res?.message || "Member removed successfully.");
      if (String(teamId) === String(teamIdValue)) {
        const data = await fetchTeamMembers(Number(teamIdValue));
        setMembersPayload(data);
      }
      bumpTeams();
    } catch (e) {
      setError(e.message || "Could not remove member.");
    } finally {
      setRemoveBusyKey("");
    }
  };

  const onConfirmDelete = async () => {
    if (!confirmDialog) {
      return;
    }
    if (confirmDialog.kind === "team") {
      const team = directorTeams.find((row) => Number(row.id) === Number(confirmDialog.teamId));
      if (team) {
        await performDeleteTeam(team);
      }
    } else if (confirmDialog.kind === "club") {
      await performDeleteClub(confirmDialog.clubId);
    } else if (confirmDialog.kind === "member") {
      await performRemoveMember(confirmDialog.teamId, confirmDialog.memberUserId);
    }
    setConfirmDialog(null);
  };

  const onAddMember = async () => {
    if (!teamId) {
      setError("Choose a team first.");
      return;
    }
    const uid = Number(memberUserId.trim());
    if (!memberUserId.trim() || Number.isNaN(uid) || uid < 1) {
      setError("Enter the member’s numeric user id (they must already have an account).");
      return;
    }
    if (memberRole === "player" && membersPayload && !membersPayload.can_add_player) {
      setError("You cannot add players to this team with your current role.");
      return;
    }
    if (memberRole === "coach" && membersPayload && !membersPayload.can_add_coach) {
      setError("You cannot add coaches to this team with your current role.");
      return;
    }
    setAddBusy(true);
    setError("");
    setSuccessMessage("");
    try {
      await directorAddTeamMember(Number(teamId), { user_id: uid, role: memberRole });
      setMemberUserId("");
      setSuccessMessage("Member added to the team.");
      await loadMe();
      bumpTeams();
      const data = await fetchTeamMembers(Number(teamId));
      setMembersPayload(data);
    } catch (e) {
      setError(e.message || "Could not add member.");
    } finally {
      setAddBusy(false);
    }
  };

  if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
    return null;
  }

  const cardContent = (
    <div className={`vc-director-card${embedded ? " vc-director-card--embedded" : ""}`}>
      {!embedded ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center" }}>
          <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
            ← Dashboard
          </button>
          <button type="button" className="vc-link-cyan" onClick={() => navigate("/dashboard")}>
            Director dashboard
          </button>
          <button
            type="button"
            className="vc-link-cyan"
            onClick={() => {
              if (onOpenUsers) {
                onOpenUsers();
                return;
              }
              navigate("/director/users");
            }}
          >
            User directory (ids)
          </button>
        </div>
      ) : null}

        {successMessage ? <div className="vc-director-success">{successMessage}</div> : null}
        {error ? <div className="vc-director-error">{error}</div> : null}

        <section className="vc-director-section">
          <h2 className="vc-panel-title">Teams</h2>
          <p className="vc-modal__muted" style={{ marginTop: 0 }}>
            Clubs and their teams are grouped below. Delete actions are available on each row.
          </p>
          {ownedClubs.map((club) => {
            const clubTeams = teamsByClubId[Number(club.id)] || [];
            const draft = createDraftByClub[Number(club.id)] || { name: "", season: "" };
            return (
              <div
                key={club.id}
                style={{
                  borderTop: "1px solid #e8ecef",
                  marginTop: "0.9rem",
                  paddingTop: "0.9rem",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "0.75rem",
                  }}
                >
                  <h3 style={{ margin: 0, fontSize: "1rem" }}>{club.name}</h3>
                  <button
                    type="button"
                    className="vc-du-action"
                    disabled={deleteClubBusy != null || createBusyClubId != null || deleteTeamBusyId != null}
                    onClick={() => openDeleteClubConfirm(club)}
                  >
                    {deleteClubBusy && Number(deleteClubBusyId) === Number(club.id) ? "…" : "Delete club"}
                  </button>
                </div>

                <p className="vc-modal__muted" style={{ marginTop: "0.65rem", marginBottom: "0.5rem" }}>
                  Existing teams:
                </p>
                <div className="vc-director-table-wrap">
                  <table className="vc-director-table">
                    <tbody>
                      {!clubTeams.length ? (
                        <tr>
                          <td colSpan={2} style={{ color: "#6b7580", fontWeight: 600 }}>
                            No teams under this club yet.
                          </td>
                        </tr>
                      ) : (
                        clubTeams.map((team) => (
                          <tr key={team.id}>
                            <td>
                              {team.name}
                              {team.season ? ` (${team.season})` : ""}
                            </td>
                            <td style={{ textAlign: "right", width: "1%", whiteSpace: "nowrap" }}>
                              <button
                                type="button"
                                className="vc-du-action"
                                disabled={deleteTeamBusyId === team.id || deleteClubBusy != null}
                                onClick={() => openDeleteTeamConfirm(team, club)}
                              >
                                {deleteTeamBusyId === team.id ? "…" : "Delete team"}
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <p className="vc-modal__muted" style={{ marginTop: "0.75rem", marginBottom: "0.5rem" }}>
                  Create a team form for this club:
                </p>
                <div className="vc-pay-create-grid">
                  <input
                    className="vc-director-modal__select"
                    placeholder="Team name (required)"
                    value={draft.name}
                    onChange={(e) => updateCreateDraft(club.id, "name", e.target.value)}
                  />
                  <input
                    className="vc-director-modal__select"
                    placeholder="Season (optional, e.g. 2026)"
                    value={draft.season}
                    onChange={(e) => updateCreateDraft(club.id, "season", e.target.value)}
                  />
                  <button
                    type="button"
                    className="vc-director-modal__btn"
                    disabled={createBusyClubId != null || deleteClubBusy != null || deleteTeamBusyId != null}
                    onClick={() => void onCreateTeam(club.id)}
                  >
                    {createBusyClubId === Number(club.id) ? "Creating…" : "Create team"}
                  </button>
                </div>
              </div>
            );
          })}
        </section>

        <section className="vc-director-section">
          <h2 className="vc-panel-title">Team members</h2>
          <p className="vc-modal__muted" style={{ marginTop: 0 }}>
            Choose a team to see who is on it. Add a coach or player by user ID — they must already have an account.
          </p>
          <div className="vc-pay-toolbar">
            <label className="vc-pay-toolbar__field">
              Team
              <select
                value={teamId}
                onChange={(e) => setTeamId(e.target.value)}
                className="vc-director-modal__select"
              >
                <option value="">Select a team…</option>
                {directorTeams.map((t) => (
                  <option key={t.id} value={String(t.id)}>
                    {(t.club_name ? `${t.club_name} — ` : "") + t.name}
                    {t.season ? ` (${t.season})` : ""}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {membersLoading ? <p className="vc-modal__muted">Loading members…</p> : null}

          {!membersLoading && membersPayload?.members?.length ? (
            <table className="vc-table" style={{ marginTop: "0.75rem" }}>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {membersPayload.members.map((row) => (
                  <tr key={row.user?.id}>
                    <td>
                      {[row.user?.first_name, row.user?.last_name].filter(Boolean).join(" ").trim() ||
                        row.user?.email ||
                        "—"}
                    </td>
                    <td>{row.user?.email || "—"}</td>
                    <td>{roleLabel(row.membership?.role)}</td>
                    <td style={{ textAlign: "right", width: "1%", whiteSpace: "nowrap" }}>
                      {(() => {
                        const selectedTeam = directorTeams.find((team) => String(team.id) === String(teamId));
                        const canInvitePlayer = !!membersPayload?.can_add_player;
                        const canInviteCoach = !!membersPayload?.can_add_coach;
                        const canRemove =
                          canInviteCoach || (row.membership?.role === "player" && canInvitePlayer);
                        const busyKey = `${teamId}:${row.user?.id}`;
                        if (!selectedTeam || !canRemove) {
                          return <span className="vc-modal__muted">—</span>;
                        }
                        return (
                          <button
                            type="button"
                            className="vc-du-action"
                            disabled={removeBusyKey === busyKey || deleteClubBusy != null || deleteTeamBusyId != null}
                            onClick={() => openRemoveMemberConfirm(selectedTeam, row)}
                          >
                            {removeBusyKey === busyKey ? "…" : "Remove"}
                          </button>
                        );
                      })()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}

          {!membersLoading && teamId && membersPayload && !membersPayload.members?.length ? (
            <p className="vc-modal__muted">No one on this team yet. Add a coach or player below.</p>
          ) : null}

          {teamId && membersPayload ? (
            <>
              <p className="vc-modal__muted" style={{ marginTop: "1rem", marginBottom: "0.45rem" }}>
                Invite by email
              </p>
              <div className="vc-pay-create-grid">
                <input
                  className="vc-director-modal__select"
                  placeholder="Email address"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                />
                <div />
                <button
                  type="button"
                  className="vc-director-modal__btn"
                  disabled={inviteBusy || !membersPayload.can_add_player || !teamId}
                  onClick={() => {
                    const selectedTeam = directorTeams.find((team) => String(team.id) === String(teamId));
                    if (selectedTeam) {
                      void onInviteByEmail(selectedTeam);
                    }
                  }}
                >
                  {inviteBusy ? "Inviting…" : "Invite"}
                </button>
              </div>
            </>
          ) : null}

          {teamId && membersPayload && (membersPayload.can_add_player || membersPayload.can_add_coach) ? (
            <>
              <p className="vc-modal__muted" style={{ marginTop: "1rem", marginBottom: "0.45rem" }}>
                Add existing user by ID
              </p>
              <div className="vc-pay-create-grid">
              {membersPayload.can_add_player && !membersPayload.can_add_coach ? (
                <p className="vc-modal__muted" style={{ gridColumn: "1 / -1", margin: 0 }}>
                  Coaches may add <strong>players</strong> only; parent or director accounts cannot be added here.
                </p>
              ) : null}
              <input
                className="vc-director-modal__select"
                placeholder="Member user id"
                value={memberUserId}
                onChange={(e) => setMemberUserId(e.target.value)}
              />
              <select
                className="vc-director-modal__select"
                value={memberRole}
                onChange={(e) => setMemberRole(e.target.value)}
              >
                {membersPayload.can_add_player ? <option value="player">Player</option> : null}
                {membersPayload.can_add_coach ? <option value="coach">Coach</option> : null}
              </select>
              <button
                type="button"
                className="vc-director-modal__btn"
                disabled={
                  addBusy ||
                  !teamId ||
                  (memberRole === "player" && !membersPayload.can_add_player) ||
                  (memberRole === "coach" && !membersPayload.can_add_coach)
                }
                onClick={() => void onAddMember()}
              >
                {addBusy ? "Adding…" : "Add to team"}
              </button>
              </div>
            </>
          ) : null}
          {teamId && membersPayload && !membersPayload.can_add_player && !membersPayload.can_add_coach ? (
            <p className="vc-modal__muted" style={{ marginTop: "0.75rem" }}>
              Your account cannot add people to this team.
            </p>
          ) : null}
        </section>
      </div>
  );

  const confirmBusy = deleteTeamBusyId != null || deleteClubBusy != null || !!removeBusyKey;
  const confirmTitle =
    confirmDialog?.kind === "club"
      ? "Delete club"
      : confirmDialog?.kind === "member"
        ? "Remove member"
        : "Delete team";

  if (loading) {
    return embedded ? (
      <div className="vc-director-card vc-director-card--embedded">
        <p className="vc-director-loading">Loading…</p>
      </div>
    ) : (
      <div className="vc-director-page">
        <div className="vc-director-card">
          <p className="vc-director-loading">Loading…</p>
        </div>
      </div>
    );
  }

  if (!ownedClubs.length) {
    return embedded ? (
      <div className="vc-director-card vc-director-card--embedded">
        <p className="vc-director-loading">You need an owned club (club director) to create teams and roster.</p>
      </div>
    ) : (
      <div className="vc-director-page">
        <div className="vc-director-card">
          <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
            ← Dashboard
          </button>
          <p className="vc-director-loading">You need an owned club (club director) to create teams and roster.</p>
        </div>
      </div>
    );
  }

  if (embedded) {
    return (
      <>
        {cardContent}
        {confirmDialog ? (
          <div
            className="vc-director-modal-backdrop"
            role="presentation"
            onClick={(event) => {
              if (event.target === event.currentTarget && !confirmBusy) {
                setConfirmDialog(null);
              }
            }}
          >
            <div
              className="vc-director-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="vc-confirm-delete-title"
              onClick={(event) => event.stopPropagation()}
            >
              <h3 id="vc-confirm-delete-title">{confirmTitle}</h3>
              <p className="vc-director-modal__meta">{confirmDialog.message}</p>
              <div className="vc-director-modal__actions">
                <button
                  type="button"
                  className="vc-director-modal__btn vc-director-modal__btn--ghost"
                  disabled={confirmBusy}
                  onClick={() => setConfirmDialog(null)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="vc-director-modal__btn"
                  disabled={confirmBusy}
                  onClick={() => void onConfirmDelete()}
                >
                  {confirmBusy ? "Deleting…" : "Confirm delete"}
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </>
    );
  }

  return (
    <div className="vc-director-page">
      <p className="vc-director-kicker">Teams & roster</p>
      {cardContent}
      {confirmDialog ? (
        <div
          className="vc-director-modal-backdrop"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget && !confirmBusy) {
              setConfirmDialog(null);
            }
          }}
        >
          <div
            className="vc-director-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="vc-confirm-delete-title"
            onClick={(event) => event.stopPropagation()}
          >
            <h3 id="vc-confirm-delete-title">{confirmTitle}</h3>
            <p className="vc-director-modal__meta">{confirmDialog.message}</p>
            <div className="vc-director-modal__actions">
              <button
                type="button"
                className="vc-director-modal__btn vc-director-modal__btn--ghost"
                disabled={confirmBusy}
                onClick={() => setConfirmDialog(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="vc-director-modal__btn"
                disabled={confirmBusy}
                onClick={() => void onConfirmDelete()}
              >
                {confirmBusy ? "Deleting…" : "Confirm delete"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
