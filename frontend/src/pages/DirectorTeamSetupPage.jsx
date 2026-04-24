import { useCallback, useEffect, useMemo, useState } from "react";
import {
  directorCreateTeam,
  directorDeleteClub,
  directorDeleteTeam,
  fetchCurrentUser,
  inviteTeamMember,
} from "../api";
import InlineDropdown from "../components/InlineDropdown";
import { navigate } from "../navigation";

const AUTH_TOKEN_KEY = "netup.auth.token";
const INVITE_ROLE_OPTIONS = [
  { value: "player", label: "Player" },
  { value: "coach", label: "Coach" },
];

function CreateTeamFieldLabel({ htmlFor, children, optional = false }) {
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

export default function DirectorTeamSetupPage({
  embedded = false,
  preferredClubId = null,
  onOpenUsers = null,
  workspaceRole = "director",
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [ownedClubs, setOwnedClubs] = useState([]);
  const [directorTeams, setDirectorTeams] = useState([]);
  const [coachTeams, setCoachTeams] = useState([]);
  const [teamId, setTeamId] = useState("");
  const [createTeamDialogClub, setCreateTeamDialogClub] = useState(null);
  const [createTeamError, setCreateTeamError] = useState("");
  const [newTeamName, setNewTeamName] = useState("");
  const [newTeamShortName, setNewTeamShortName] = useState("");
  const [newTeamDescription, setNewTeamDescription] = useState("");
  const [newTeamSeason, setNewTeamSeason] = useState("");
  const [newTeamAgeGroup, setNewTeamAgeGroup] = useState("");
  const [newTeamGender, setNewTeamGender] = useState("");
  const [newTeamHomeVenue, setNewTeamHomeVenue] = useState("");
  const [createBusyClubId, setCreateBusyClubId] = useState(null);
  const [deleteTeamBusyId, setDeleteTeamBusyId] = useState(null);
  const [deleteClubBusy, setDeleteClubBusy] = useState(null);
  const [deleteClubBusyId, setDeleteClubBusyId] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteEmailRole, setInviteEmailRole] = useState("player");
  const [inviteEmailBusy, setInviteEmailBusy] = useState(false);
  const [inviteUserId, setInviteUserId] = useState("");
  const [inviteUserIdRole, setInviteUserIdRole] = useState("player");
  const [inviteUserIdBusy, setInviteUserIdBusy] = useState(false);

  const isCoachWorkspace = workspaceRole === "coach";
  const accessibleTeams = isCoachWorkspace ? coachTeams : directorTeams;
  const inviteRoleOptions = isCoachWorkspace ? [INVITE_ROLE_OPTIONS[0]] : INVITE_ROLE_OPTIONS;

  const bumpTeams = () => window.dispatchEvent(new Event("netup-teams-changed"));

  const loadMe = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const me = await fetchCurrentUser();
      const clubs = me.owned_clubs || [];
      setOwnedClubs(clubs);
      setDirectorTeams(me.director_teams || []);
      setCoachTeams(me.coached_teams || []);
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

  const invitationTeamOptions = useMemo(
    () => [
      { value: "", label: "Select a team…" },
      ...accessibleTeams.map((team) => ({
        value: String(team.id),
        label: `${team.club_name ? `${team.club_name} — ` : ""}${team.name}${team.season ? ` (${team.season})` : ""}`,
      })),
    ],
    [accessibleTeams],
  );

  useEffect(() => {
    if (!teamId) {
      return;
    }
    const teamStillExists = accessibleTeams.some((team) => String(team.id) === String(teamId));
    if (!teamStillExists) {
      setTeamId("");
    }
  }, [accessibleTeams, teamId]);

  const openCreateTeamModal = (club) => {
    setCreateTeamDialogClub(club);
    setCreateTeamError("");
    setNewTeamName("");
    setNewTeamShortName("");
    setNewTeamDescription("");
    setNewTeamSeason("");
    setNewTeamAgeGroup("");
    setNewTeamGender("");
    setNewTeamHomeVenue("");
  };

  const onCreateTeam = async (event) => {
    event?.preventDefault?.();
    const resolvedClubId = Number(createTeamDialogClub?.id);
    const name = newTeamName.trim();
    const shortName = newTeamShortName.trim();
    const ageGroup = newTeamAgeGroup.trim();
    const gender = newTeamGender.trim();
    const homeVenue = newTeamHomeVenue.trim();

    if (!resolvedClubId) {
      setCreateTeamError("Choose a club first.");
      return;
    }
    if (!name || !shortName || !ageGroup || !gender || !homeVenue) {
      setCreateTeamError("Please fill in every required field.");
      return;
    }

    setCreateBusyClubId(resolvedClubId);
    setCreateTeamError("");
    setError("");
    setSuccessMessage("");
    try {
      const body = {
        name,
        short_name: shortName,
        description: newTeamDescription.trim(),
        season: newTeamSeason.trim(),
        age_group: ageGroup,
        gender,
        home_venue: homeVenue,
      };
      const res = await directorCreateTeam(resolvedClubId, body);
      setCreateTeamDialogClub(null);
      setSuccessMessage(res?.message || "Team created.");
      await loadMe();
      bumpTeams();
      if (res?.team?.id) {
        setTeamId(String(res.team.id));
      }
    } catch (e) {
      setCreateTeamError(e.message || "Could not create team.");
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

  const onInviteByEmail = async (team) => {
    const email = inviteEmail.trim().toLowerCase();
    if (!email) {
      setError("Enter an email address.");
      return;
    }
    setInviteEmailBusy(true);
    setError("");
    setSuccessMessage("");
    try {
      const res = await inviteTeamMember(Number(team.id), {
        email,
        role: inviteEmailRole,
      });
      setInviteEmail("");
      setInviteEmailRole("player");
      setSuccessMessage(res?.message || "Invitation sent successfully.");
    } catch (e) {
      setError(e.message || "Could not invite member.");
    } finally {
      setInviteEmailBusy(false);
    }
  };

  const onInviteById = async (team) => {
    const uid = Number(inviteUserId.trim());
    if (!inviteUserId.trim() || Number.isNaN(uid) || uid < 1) {
      setError("Enter a valid user ID.");
      return;
    }
    setInviteUserIdBusy(true);
    setError("");
    setSuccessMessage("");
    try {
      const res = await inviteTeamMember(Number(team.id), {
        user_id: uid,
        role: inviteUserIdRole,
      });
      setInviteUserId("");
      setInviteUserIdRole("player");
      setSuccessMessage(res?.message || "Invitation sent successfully.");
      bumpTeams();
    } catch (e) {
      setError(e.message || "Could not send invitation.");
    } finally {
      setInviteUserIdBusy(false);
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
    }
    setConfirmDialog(null);
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
            {isCoachWorkspace ? "Coaching dashboard" : "Director dashboard"}
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

        {!isCoachWorkspace ? (
        <section className="vc-director-section">
          <h2 className="vc-panel-title">Teams</h2>
          <p className="vc-modal__muted" style={{ marginTop: 0 }}>
            Clubs and their teams are grouped below. Delete actions are available on each row.
          </p>
          {ownedClubs.map((club) => {
            const clubTeams = teamsByClubId[Number(club.id)] || [];
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
                    className="vc-du-action vc-du-action--danger"
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
                                className="vc-du-action vc-du-action--danger"
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

                <div style={{ marginTop: "0.85rem" }}>
                  <button
                    type="button"
                    className="vc-director-modal__btn"
                    disabled={createBusyClubId != null || deleteClubBusy != null || deleteTeamBusyId != null}
                    onClick={() => openCreateTeamModal(club)}
                  >
                    Create a new team
                  </button>
                </div>
              </div>
            );
          })}
        </section>
        ) : null}

        <section className="vc-director-section">
          <div className="vc-team-invitations__header">
            <div className="vc-team-invitations__copy">
              <h2 className="vc-panel-title" style={{ marginBottom: 0 }}>
                Team invitations
              </h2>
              <p className="vc-modal__muted" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                {isCoachWorkspace
                  ? "Invite players by email or by ID."
                  : "Invite coaches or players by email or by ID."}
              </p>
            </div>
            <div className="vc-team-invitations__picker">
              <span className="vc-team-invitations__picker-label">Team</span>
              <InlineDropdown
                value={teamId}
                onChange={setTeamId}
                options={invitationTeamOptions}
                ariaLabel="Select a team for invitations"
                className="vc-inline-dropdown--team-picker"
              />
            </div>
          </div>

          {!teamId ? (
            <p className="vc-modal__muted" style={{ marginTop: "0.25rem" }}>
              Select a team to start inviting people.
            </p>
          ) : null}

          {teamId ? (
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
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      const selectedTeam = accessibleTeams.find((team) => String(team.id) === String(teamId));
                      if (selectedTeam) {
                        void onInviteByEmail(selectedTeam);
                      }
                    }
                  }}
                />
                <InlineDropdown
                  value={inviteEmailRole}
                  onChange={setInviteEmailRole}
                  options={inviteRoleOptions}
                  ariaLabel="Invitation role for email"
                />
                <button
                  type="button"
                  className="vc-director-modal__btn"
                  disabled={inviteEmailBusy || !teamId}
                  onClick={() => {
                    const selectedTeam = accessibleTeams.find((team) => String(team.id) === String(teamId));
                    if (selectedTeam) {
                      void onInviteByEmail(selectedTeam);
                    }
                  }}
                >
                  {inviteEmailBusy ? "Inviting…" : "Invite"}
                </button>
              </div>

              <p className="vc-modal__muted" style={{ marginTop: "1rem", marginBottom: "0.45rem" }}>
                Invite by ID
              </p>
              <div className="vc-pay-create-grid">
                <input
                  className="vc-director-modal__select"
                  placeholder="User ID"
                  value={inviteUserId}
                  onChange={(e) => setInviteUserId(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      const selectedTeam = accessibleTeams.find((team) => String(team.id) === String(teamId));
                      if (selectedTeam) {
                        void onInviteById(selectedTeam);
                      }
                    }
                  }}
                />
                <InlineDropdown
                  value={inviteUserIdRole}
                  onChange={setInviteUserIdRole}
                  options={inviteRoleOptions}
                  ariaLabel="Invitation role for user ID"
                />
                <button
                  type="button"
                  className="vc-director-modal__btn"
                  disabled={inviteUserIdBusy || !teamId}
                  onClick={() => {
                    const selectedTeam = accessibleTeams.find((team) => String(team.id) === String(teamId));
                    if (selectedTeam) {
                      void onInviteById(selectedTeam);
                    }
                  }}
                >
                  {inviteUserIdBusy ? "Inviting…" : "Invite by ID"}
                </button>
              </div>
            </>
          ) : null}
        </section>
      </div>
  );

  const confirmBusy = deleteTeamBusyId != null || deleteClubBusy != null;
  const confirmTitle =
    confirmDialog?.kind === "club"
      ? "Delete club"
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

  if (!ownedClubs.length && !isCoachWorkspace) {
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

  if (!accessibleTeams.length && isCoachWorkspace) {
    return embedded ? (
      <div className="vc-director-card vc-director-card--embedded">
        <p className="vc-director-loading">
          {isCoachWorkspace
            ? "You need at least one coached team to invite players from this workspace."
            : "You need at least one team to manage invitations."}
        </p>
      </div>
    ) : (
      <div className="vc-director-page">
        <div className="vc-director-card">
          <p className="vc-director-loading">
            {isCoachWorkspace
              ? "You need at least one coached team to invite players from this workspace."
              : "You need at least one team to manage invitations."}
          </p>
        </div>
      </div>
    );
  }

  if (embedded) {
    return (
      <>
        {cardContent}
        {createTeamDialogClub ? (
          <div
            className="vc-director-modal-backdrop"
            role="presentation"
            onClick={(event) => {
              if (event.target === event.currentTarget && createBusyClubId == null) {
                setCreateTeamDialogClub(null);
              }
            }}
          >
            <div
              className="vc-director-modal vc-director-modal--wide"
              role="dialog"
              aria-modal="true"
              aria-labelledby="vc-create-team-title"
              onClick={(event) => event.stopPropagation()}
            >
              <h3 id="vc-create-team-title">Create a team</h3>
              <p className="vc-director-modal__meta">
                This team will be created inside <strong>{createTeamDialogClub.name}</strong>.
              </p>
              <form onSubmit={onCreateTeam}>
                <div className="vc-create-club-form__grid">
                  <div className="vc-create-club-form__field">
                    <CreateTeamFieldLabel htmlFor="vc-create-team-name">Name</CreateTeamFieldLabel>
                    <input
                      id="vc-create-team-name"
                      className="vc-director-modal__select"
                      type="text"
                      value={newTeamName}
                      onChange={(event) => setNewTeamName(event.target.value)}
                      disabled={createBusyClubId != null}
                      required
                    />
                  </div>
                  <div className="vc-create-club-form__field">
                    <CreateTeamFieldLabel htmlFor="vc-create-team-short-name">Short Name</CreateTeamFieldLabel>
                    <input
                      id="vc-create-team-short-name"
                      className="vc-director-modal__select"
                      type="text"
                      value={newTeamShortName}
                      onChange={(event) => setNewTeamShortName(event.target.value)}
                      disabled={createBusyClubId != null}
                      required
                    />
                  </div>
                  <div className="vc-create-club-form__field vc-create-club-form__field--full">
                    <CreateTeamFieldLabel htmlFor="vc-create-team-description" optional>
                      Description
                    </CreateTeamFieldLabel>
                    <textarea
                      id="vc-create-team-description"
                      className="vc-director-modal__textarea"
                      rows={3}
                      value={newTeamDescription}
                      onChange={(event) => setNewTeamDescription(event.target.value)}
                      disabled={createBusyClubId != null}
                    />
                  </div>
                  <div className="vc-create-club-form__field">
                    <CreateTeamFieldLabel htmlFor="vc-create-team-season" optional>
                      Season
                    </CreateTeamFieldLabel>
                    <input
                      id="vc-create-team-season"
                      className="vc-director-modal__select"
                      type="text"
                      value={newTeamSeason}
                      onChange={(event) => setNewTeamSeason(event.target.value)}
                      disabled={createBusyClubId != null}
                    />
                  </div>
                  <div className="vc-create-club-form__field">
                    <CreateTeamFieldLabel htmlFor="vc-create-team-age-group">Age Group</CreateTeamFieldLabel>
                    <input
                      id="vc-create-team-age-group"
                      className="vc-director-modal__select"
                      type="text"
                      value={newTeamAgeGroup}
                      onChange={(event) => setNewTeamAgeGroup(event.target.value)}
                      disabled={createBusyClubId != null}
                      required
                    />
                  </div>
                  <div className="vc-create-club-form__field">
                    <CreateTeamFieldLabel htmlFor="vc-create-team-gender">Gender</CreateTeamFieldLabel>
                    <select
                      id="vc-create-team-gender"
                      className="vc-director-modal__select"
                      value={newTeamGender}
                      onChange={(event) => setNewTeamGender(event.target.value)}
                      disabled={createBusyClubId != null}
                      required
                    >
                      <option value="">Select gender…</option>
                      <option value="boys">Boys</option>
                      <option value="girls">Girls</option>
                      <option value="mixed">Mixed</option>
                    </select>
                  </div>
                  <div className="vc-create-club-form__field">
                    <CreateTeamFieldLabel htmlFor="vc-create-team-home-venue">Home Venue</CreateTeamFieldLabel>
                    <input
                      id="vc-create-team-home-venue"
                      className="vc-director-modal__select"
                      type="text"
                      value={newTeamHomeVenue}
                      onChange={(event) => setNewTeamHomeVenue(event.target.value)}
                      disabled={createBusyClubId != null}
                      required
                    />
                  </div>
                </div>
                {createTeamError ? <p className="vc-director-modal__error">{createTeamError}</p> : null}
                <div className="vc-director-modal__actions">
                  <button
                    type="button"
                    className="vc-director-modal__btn vc-director-modal__btn--ghost"
                    disabled={createBusyClubId != null}
                    onClick={() => setCreateTeamDialogClub(null)}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="vc-director-modal__btn" disabled={createBusyClubId != null}>
                    {createBusyClubId != null ? "Creating…" : "Create team"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        ) : null}
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
      {createTeamDialogClub ? (
        <div
          className="vc-director-modal-backdrop"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget && createBusyClubId == null) {
              setCreateTeamDialogClub(null);
            }
          }}
        >
          <div
            className="vc-director-modal vc-director-modal--wide"
            role="dialog"
            aria-modal="true"
            aria-labelledby="vc-create-team-title"
            onClick={(event) => event.stopPropagation()}
          >
            <h3 id="vc-create-team-title">Create a team</h3>
            <p className="vc-director-modal__meta">
              This team will be created inside <strong>{createTeamDialogClub.name}</strong>.
            </p>
            <form onSubmit={onCreateTeam}>
              <div className="vc-create-club-form__grid">
                <div className="vc-create-club-form__field">
                  <CreateTeamFieldLabel htmlFor="vc-create-team-name-standalone">Name</CreateTeamFieldLabel>
                  <input
                    id="vc-create-team-name-standalone"
                    className="vc-director-modal__select"
                    type="text"
                    value={newTeamName}
                    onChange={(event) => setNewTeamName(event.target.value)}
                    disabled={createBusyClubId != null}
                    required
                  />
                </div>
                <div className="vc-create-club-form__field">
                  <CreateTeamFieldLabel htmlFor="vc-create-team-short-name-standalone">Short Name</CreateTeamFieldLabel>
                  <input
                    id="vc-create-team-short-name-standalone"
                    className="vc-director-modal__select"
                    type="text"
                    value={newTeamShortName}
                    onChange={(event) => setNewTeamShortName(event.target.value)}
                    disabled={createBusyClubId != null}
                    required
                  />
                </div>
                <div className="vc-create-club-form__field vc-create-club-form__field--full">
                  <CreateTeamFieldLabel htmlFor="vc-create-team-description-standalone" optional>
                    Description
                  </CreateTeamFieldLabel>
                  <textarea
                    id="vc-create-team-description-standalone"
                    className="vc-director-modal__textarea"
                    rows={3}
                    value={newTeamDescription}
                    onChange={(event) => setNewTeamDescription(event.target.value)}
                    disabled={createBusyClubId != null}
                  />
                </div>
                <div className="vc-create-club-form__field">
                  <CreateTeamFieldLabel htmlFor="vc-create-team-season-standalone" optional>
                    Season
                  </CreateTeamFieldLabel>
                  <input
                    id="vc-create-team-season-standalone"
                    className="vc-director-modal__select"
                    type="text"
                    value={newTeamSeason}
                    onChange={(event) => setNewTeamSeason(event.target.value)}
                    disabled={createBusyClubId != null}
                  />
                </div>
                <div className="vc-create-club-form__field">
                  <CreateTeamFieldLabel htmlFor="vc-create-team-age-group-standalone">Age Group</CreateTeamFieldLabel>
                  <input
                    id="vc-create-team-age-group-standalone"
                    className="vc-director-modal__select"
                    type="text"
                    value={newTeamAgeGroup}
                    onChange={(event) => setNewTeamAgeGroup(event.target.value)}
                    disabled={createBusyClubId != null}
                    required
                  />
                </div>
                <div className="vc-create-club-form__field">
                  <CreateTeamFieldLabel htmlFor="vc-create-team-gender-standalone">Gender</CreateTeamFieldLabel>
                  <select
                    id="vc-create-team-gender-standalone"
                    className="vc-director-modal__select"
                    value={newTeamGender}
                    onChange={(event) => setNewTeamGender(event.target.value)}
                    disabled={createBusyClubId != null}
                    required
                  >
                    <option value="">Select gender…</option>
                    <option value="boys">Boys</option>
                    <option value="girls">Girls</option>
                    <option value="mixed">Mixed</option>
                  </select>
                </div>
                <div className="vc-create-club-form__field">
                  <CreateTeamFieldLabel htmlFor="vc-create-team-home-venue-standalone">Home Venue</CreateTeamFieldLabel>
                  <input
                    id="vc-create-team-home-venue-standalone"
                    className="vc-director-modal__select"
                    type="text"
                    value={newTeamHomeVenue}
                    onChange={(event) => setNewTeamHomeVenue(event.target.value)}
                    disabled={createBusyClubId != null}
                    required
                  />
                </div>
              </div>
              {createTeamError ? <p className="vc-director-modal__error">{createTeamError}</p> : null}
              <div className="vc-director-modal__actions">
                <button
                  type="button"
                  className="vc-director-modal__btn vc-director-modal__btn--ghost"
                  disabled={createBusyClubId != null}
                  onClick={() => setCreateTeamDialogClub(null)}
                >
                  Cancel
                </button>
                <button type="submit" className="vc-director-modal__btn" disabled={createBusyClubId != null}>
                  {createBusyClubId != null ? "Creating…" : "Create team"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
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
