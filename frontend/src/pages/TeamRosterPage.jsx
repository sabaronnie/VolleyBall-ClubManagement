import { useCallback, useEffect, useState } from "react";
import { directorAddTeamMember, fetchTeamMembers } from "../api";
import { navigate } from "../navigation";

function roleLabel(role) {
  if (role === "coach") return "Coach";
  if (role === "player") return "Player";
  return role || "\u2014";
}

export default function TeamRosterPage({ team }) {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [userId, setUserId] = useState("");
  const [role, setRole] = useState("player");
  const [busy, setBusy] = useState(false);

  const teamId = team?.id && team.id !== "__all__" ? team.id : null;
  const teamName = team?.name || "Team";

  const load = useCallback(async () => {
    if (!teamId) {
      setPayload(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await fetchTeamMembers(teamId);
      setPayload(data);
    } catch (err) {
      setError(err.message || "Could not load roster.");
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!payload) return;
    setRole((prev) => {
      if (prev === "coach" && !payload.can_add_coach && payload.can_add_player) return "player";
      if (prev === "player" && !payload.can_add_player && payload.can_add_coach) return "coach";
      return prev;
    });
  }, [payload]);

  const onAdd = async () => {
    const uid = Number(userId.trim());
    if (!userId.trim() || Number.isNaN(uid) || uid < 1) {
      setError("Enter the member\u2019s user ID (a positive number).");
      return;
    }
    if (role === "player" && payload && !payload.can_add_player) {
      setError("You cannot add players to this team.");
      return;
    }
    if (role === "coach" && payload && !payload.can_add_coach) {
      setError("You cannot add coaches to this team.");
      return;
    }
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await directorAddTeamMember(teamId, { user_id: uid, role });
      setUserId("");
      setSuccess("Member added successfully. They now appear on this roster.");
      window.dispatchEvent(new Event("netup-teams-changed"));
      await load();
    } catch (err) {
      setError(err.message || "Could not add member.");
    } finally {
      setBusy(false);
    }
  };

  if (!teamId) {
    return (
      <section style={{ padding: "2rem 1.75rem", maxWidth: 720, margin: "0 auto" }}>
        <h1 style={{ fontSize: "1.3rem", marginBottom: "0.75rem" }}>Team roster</h1>
        <p style={{ color: "#5c6570", lineHeight: 1.5 }}>
          No active team selected. Use the <strong>Team</strong> dropdown in the bar above to choose a team, or open the{" "}
          <button type="button" className="vc-link-cyan" onClick={() => navigate("/dashboard")}>
            dashboard
          </button>{" "}
          to pick a team and return to the roster.
        </p>
      </section>
    );
  }

  const members = payload?.members || [];
  const canAdd = payload?.can_add_player || payload?.can_add_coach;

  return (
    <section style={{ padding: "2rem 1.75rem", maxWidth: 780, margin: "0 auto" }}>
      <h1 style={{ fontSize: "1.3rem", marginBottom: "1.25rem" }}>{teamName} Roster</h1>

      {success ? <div className="vc-director-success">{success}</div> : null}
      {error ? <div className="vc-director-error">{error}</div> : null}

      {loading ? <p className="vc-modal__muted">Loading roster\u2026</p> : null}

      {!loading && members.length ? (
        <table className="vc-table" style={{ marginBottom: "1rem" }}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
            </tr>
          </thead>
          <tbody>
            {members.map((row) => (
              <tr key={row.user?.id}>
                <td>
                  {[row.user?.first_name, row.user?.last_name].filter(Boolean).join(" ").trim() ||
                    row.user?.email || "\u2014"}
                </td>
                <td>{row.user?.email || "\u2014"}</td>
                <td>{roleLabel(row.membership?.role)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      {!loading && !members.length ? (
        <p className="vc-modal__muted" style={{ marginBottom: "1rem" }}>
          No members on this team yet.
        </p>
      ) : null}

      {!loading && canAdd ? (
        <div style={{ marginTop: "0.5rem" }}>
          <h2 style={{ fontSize: "1.05rem", marginBottom: "0.65rem" }}>Add a member</h2>
          {payload?.can_add_player && !payload?.can_add_coach ? (
            <p className="vc-modal__muted" style={{ marginTop: 0, marginBottom: "0.65rem" }}>
              As a coach you may add <strong>players</strong> only. The server will reject accounts whose primary role
              is parent or director.
            </p>
          ) : null}
          <p className="vc-modal__muted" style={{ marginTop: 0, marginBottom: "0.75rem" }}>
            Enter the user ID of the person you want to add. They must already have a registered account
            (check the Registration page or their profile for their ID).
          </p>
          <div className="vc-pay-create-grid">
            <input
              className="vc-director-modal__select"
              placeholder="User ID"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void onAdd();
              }}
            />
            <select
              className="vc-director-modal__select"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              {payload?.can_add_player ? <option value="player">Player</option> : null}
              {payload?.can_add_coach ? <option value="coach">Coach</option> : null}
            </select>
            <button
              type="button"
              className="vc-director-modal__btn"
              disabled={busy}
              onClick={() => void onAdd()}
            >
              {busy ? "Adding\u2026" : "Add to team"}
            </button>
          </div>
        </div>
      ) : null}

      {!loading && payload && !canAdd ? (
        <p className="vc-modal__muted" style={{ marginTop: "0.5rem" }}>
          Your account does not have permission to add members to this team.
        </p>
      ) : null}
    </section>
  );
}
