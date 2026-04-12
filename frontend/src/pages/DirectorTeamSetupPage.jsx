import { useCallback, useEffect, useMemo, useState } from "react";
import { directorAddTeamMember, directorCreateTeam, fetchCurrentUser, fetchTeamMembers } from "../api";
import { navigate } from "../navigation";

const AUTH_TOKEN_KEY = "netup.auth.token";
const CLUB_STORAGE_KEY = "netup.director.teams.club_id";

function roleLabel(role) {
  if (role === "coach") return "Coach";
  if (role === "player") return "Player";
  return role || "—";
}

export default function DirectorTeamSetupPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [ownedClubs, setOwnedClubs] = useState([]);
  const [directorTeams, setDirectorTeams] = useState([]);
  const [clubId, setClubId] = useState(null);
  const [teamId, setTeamId] = useState("");
  const [membersPayload, setMembersPayload] = useState(null);
  const [membersLoading, setMembersLoading] = useState(false);

  const [createName, setCreateName] = useState("");
  const [createSeason, setCreateSeason] = useState("");
  const [createBusy, setCreateBusy] = useState(false);

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
      if (!clubs.length) {
        setClubId(null);
        return;
      }
      const params = new URLSearchParams(window.location.search);
      const qClub = params.get("club_id");
      const fromQuery = qClub && clubs.some((c) => c.id === Number(qClub)) ? Number(qClub) : null;
      const stored = sessionStorage.getItem(CLUB_STORAGE_KEY);
      const fromStore = stored ? Number(stored) : null;
      const pick =
        fromQuery ||
        (fromStore && clubs.some((c) => c.id === fromStore) ? fromStore : clubs[0].id);
      setClubId(pick);
      sessionStorage.setItem(CLUB_STORAGE_KEY, String(pick));
    } catch (e) {
      setError(e.message || "Could not load your account.");
    } finally {
      setLoading(false);
    }
  }, []);

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
    setTeamId("");
  }, [clubId]);

  const clubTeams = useMemo(
    () => directorTeams.filter((t) => Number(t.club_id) === Number(clubId)),
    [directorTeams, clubId],
  );

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

  const onClubChange = (id) => {
    const n = Number(id);
    setClubId(n);
    sessionStorage.setItem(CLUB_STORAGE_KEY, String(n));
    const params = new URLSearchParams(window.location.search);
    params.set("club_id", String(n));
    window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
  };

  const onCreateTeam = async () => {
    if (!clubId || !createName.trim()) {
      setError("Team name is required.");
      return;
    }
    setCreateBusy(true);
    setError("");
    setSuccessMessage("");
    try {
      const body = { name: createName.trim() };
      if (createSeason.trim()) {
        body.season = createSeason.trim();
      }
      const res = await directorCreateTeam(clubId, body);
      setCreateName("");
      setCreateSeason("");
      setSuccessMessage(res?.message || "Team created.");
      await loadMe();
      bumpTeams();
      if (res?.team?.id) {
        setTeamId(String(res.team.id));
      }
    } catch (e) {
      setError(e.message || "Could not create team.");
    } finally {
      setCreateBusy(false);
    }
  };

  const onAddMember = async () => {
    if (!teamId) {
      setError("Choose a team in this club first.");
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

  if (loading) {
    return (
      <div className="vc-director-page">
        <div className="vc-director-card">
          <p className="vc-director-loading">Loading…</p>
        </div>
      </div>
    );
  }

  if (!ownedClubs.length) {
    return (
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

  return (
    <div className="vc-director-page">
      <p className="vc-director-kicker">Teams & roster</p>
      <div className="vc-director-card">
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center" }}>
          <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
            ← Dashboard
          </button>
          <button type="button" className="vc-link-cyan" onClick={() => navigate("/dashboard")}>
            Director dashboard
          </button>
          <button type="button" className="vc-link-cyan" onClick={() => navigate("/director/users")}>
            User directory (ids)
          </button>
        </div>

        {successMessage ? <div className="vc-director-success">{successMessage}</div> : null}
        {error ? <div className="vc-director-error">{error}</div> : null}

        <div className="vc-pay-toolbar" style={{ marginTop: "1rem" }}>
          {ownedClubs.length > 1 ? (
            <label className="vc-pay-toolbar__field">
              Club
              <select
                value={clubId || ""}
                onChange={(e) => onClubChange(e.target.value)}
                className="vc-director-modal__select"
              >
                {ownedClubs.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <span className="vc-modal__muted" style={{ fontWeight: 600 }}>
              {ownedClubs[0]?.name}
            </span>
          )}
        </div>

        <section className="vc-director-section">
          <h2 className="vc-panel-title">Create a team</h2>
          <p className="vc-modal__muted" style={{ marginTop: 0 }}>
            Adds a team under the selected club. Name must be unique within the club.
          </p>
          <div className="vc-pay-create-grid">
            <input
              className="vc-director-modal__select"
              placeholder="Team name (required)"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
            />
            <input
              className="vc-director-modal__select"
              placeholder="Season (optional, e.g. 2026)"
              value={createSeason}
              onChange={(e) => setCreateSeason(e.target.value)}
            />
            <button
              type="button"
              className="vc-director-modal__btn"
              disabled={createBusy || !clubId}
              onClick={() => void onCreateTeam()}
            >
              {createBusy ? "Creating…" : "Create team"}
            </button>
          </div>
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
                {clubTeams.map((t) => (
                  <option key={t.id} value={String(t.id)}>
                    {t.name}
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
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}

          {!membersLoading && teamId && membersPayload && !membersPayload.members?.length ? (
            <p className="vc-modal__muted">No one on this team yet. Add a coach or player below.</p>
          ) : null}

          {teamId && membersPayload && (membersPayload.can_add_player || membersPayload.can_add_coach) ? (
            <div className="vc-pay-create-grid" style={{ marginTop: "1rem" }}>
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
          ) : null}
          {teamId && membersPayload && !membersPayload.can_add_player && !membersPayload.can_add_coach ? (
            <p className="vc-modal__muted" style={{ marginTop: "0.75rem" }}>
              Your account cannot add people to this team.
            </p>
          ) : null}
        </section>
      </div>
    </div>
  );
}
