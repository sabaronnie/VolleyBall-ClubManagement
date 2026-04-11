import { useCallback, useEffect, useState } from "react";
import {
  directorRejectUser,
  directorVerifyUser,
  fetchDirectorPendingUsers,
} from "../api";

const AUTH_TOKEN_KEY = "netup.auth.token";

function navigate(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

const APPROVAL_ROLES = [
  { value: "player", label: "Player" },
  { value: "parent", label: "Parent" },
  { value: "coach", label: "Coach" },
];

export default function DirectorUserManagementPage() {
  const [pendingUsers, setPendingUsers] = useState([]);
  const [assignableTeams, setAssignableTeams] = useState([]);
  const [loadingPending, setLoadingPending] = useState(true);
  const [error, setError] = useState("");
  const [actionKey, setActionKey] = useState("");
  const [verifyTarget, setVerifyTarget] = useState(null);
  const [verifyRole, setVerifyRole] = useState("player");
  const [verifyTeamId, setVerifyTeamId] = useState("");
  const [verifyModalError, setVerifyModalError] = useState("");

  useEffect(() => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
      navigate("/login");
    }
  }, []);

  const loadPending = useCallback(async () => {
    setLoadingPending(true);
    setError("");
    try {
      const payload = await fetchDirectorPendingUsers();
      setPendingUsers(payload.pending_users || []);
      setAssignableTeams(payload.assignable_teams || []);
    } catch (err) {
      setError(err.message || "Could not load pending accounts.");
      setPendingUsers([]);
      setAssignableTeams([]);
    } finally {
      setLoadingPending(false);
    }
  }, []);

  useEffect(() => {
    loadPending();
  }, [loadPending]);

  const openVerifyModal = (userRow) => {
    setVerifyTarget(userRow);
    setVerifyRole("player");
    setVerifyTeamId("");
    setVerifyModalError("");
  };

  const closeVerifyModal = () => {
    setVerifyTarget(null);
    setVerifyModalError("");
  };

  const submitVerify = async () => {
    if (!verifyTarget) {
      return;
    }
    setVerifyModalError("");
    const key = `v-${verifyTarget.id}`;
    setActionKey(key);
    setError("");
    try {
      const body = { role: verifyRole };
      if ((verifyRole === "player" || verifyRole === "coach") && verifyTeamId) {
        body.team_id = Number(verifyTeamId);
      }
      await directorVerifyUser(verifyTarget.id, body);
      closeVerifyModal();
      await loadPending();
    } catch (err) {
      setVerifyModalError(err.message || "Approve failed.");
    } finally {
      setActionKey("");
    }
  };

  const onReject = async (userId) => {
    const key = `r-${userId}`;
    setActionKey(key);
    setError("");
    try {
      await directorRejectUser(userId);
      await loadPending();
    } catch (err) {
      setError(err.message || "Reject failed.");
    } finally {
      setActionKey("");
    }
  };

  const pendingCount = pendingUsers.length;
  const showOptionalTeamAssign = verifyRole === "player" || verifyRole === "coach";

  return (
    <div className="vc-director-page">
      <p className="vc-director-kicker">User Management for Director</p>
      <div className="vc-director-card">
        <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
          ← Return to Dashboard
        </button>

        {error ? <div className="vc-director-error">{error}</div> : null}

        <section className="vc-director-section">
          <h2 className="vc-panel-title">Pending Accounts</h2>
          <div className="vc-director-layout">
            <div className="vc-director-table-wrap">
              {loadingPending ? (
                <p className="vc-director-loading">Loading pending accounts…</p>
              ) : (
                <table className="vc-director-table vc-director-table--pending">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingUsers.length === 0 ? (
                      <tr>
                        <td colSpan={3} style={{ color: "#6b7580", fontWeight: 600 }}>
                          No pending accounts.
                        </td>
                      </tr>
                    ) : (
                      pendingUsers.map((u, index) => {
                        const fullName = `${u.first_name || ""} ${u.last_name || ""}`.trim() || u.email;
                        const busyV = actionKey === `v-${u.id}`;
                        const busyR = actionKey === `r-${u.id}`;
                        return (
                          <tr key={u.id} className={index === 0 ? "vc-row-new" : undefined}>
                            <td className={index === 0 ? "vc-pending-name-cell" : undefined}>
                              {index === 0 ? <span className="vc-row-new-badge">NEW</span> : null}
                              {fullName}
                            </td>
                            <td>{u.email}</td>
                            <td>
                              <button
                                type="button"
                                className="vc-du-action"
                                disabled={busyV || busyR}
                                onClick={() => openVerifyModal(u)}
                              >
                                <span className="vc-dot vc-dot--green" />
                                {busyV ? "…" : "Approve"}
                              </button>
                              <button
                                type="button"
                                className="vc-du-action"
                                disabled={busyV || busyR}
                                onClick={() => onReject(u.id)}
                              >
                                <span className="vc-dot vc-dot--red" />
                                {busyR ? "…" : "Reject"}
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              )}
            </div>
            <div className="vc-pill-stack">
              <div className="vc-pill vc-pill--blue">Pending requests: {pendingCount}</div>
            </div>
          </div>
        </section>
      </div>

      {verifyTarget ? (
        <div
          className="vc-director-modal-backdrop"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closeVerifyModal();
            }
          }}
        >
          <div className="vc-director-modal" role="dialog" aria-modal="true" aria-labelledby="vc-approve-title">
            <h3 id="vc-approve-title">Approve account</h3>
            <p className="vc-director-modal__meta">
              {`${verifyTarget.first_name || ""} ${verifyTarget.last_name || ""}`.trim() || verifyTarget.email}{" "}
              <span className="vc-director-modal__email">{verifyTarget.email}</span>
            </p>

            <label className="vc-director-modal__label" htmlFor="vc-approve-role">
              Role for this user
            </label>
            <select
              id="vc-approve-role"
              className="vc-director-modal__select"
              value={verifyRole}
              onChange={(event) => {
                setVerifyRole(event.target.value);
                setVerifyTeamId("");
                setVerifyModalError("");
              }}
            >
              {APPROVAL_ROLES.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            {showOptionalTeamAssign ? (
              <>
                <label className="vc-director-modal__label" htmlFor="vc-approve-team">
                  Assign to a team now (optional)
                </label>
                {assignableTeams.length ? (
                  <select
                    id="vc-approve-team"
                    className="vc-director-modal__select"
                    value={verifyTeamId}
                    onChange={(event) => setVerifyTeamId(event.target.value)}
                  >
                    <option value="">Not now — assign a team later</option>
                    {assignableTeams.map((t) => (
                      <option key={t.id} value={String(t.id)}>
                        {t.club_name ? `${t.club_name} — ${t.name}` : t.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <p className="vc-director-modal__hint">
                    No teams are listed for quick assignment yet. You can still approve; add them to a roster whenever
                    you are ready.
                  </p>
                )}
              </>
            ) : null}

            {verifyModalError ? <p className="vc-director-modal__error">{verifyModalError}</p> : null}

            <div className="vc-director-modal__actions">
              <button type="button" className="vc-director-modal__btn vc-director-modal__btn--ghost" onClick={closeVerifyModal}>
                Cancel
              </button>
              <button
                type="button"
                className="vc-director-modal__btn"
                onClick={() => void submitVerify()}
                disabled={Boolean(actionKey)}
              >
                {actionKey ? "Saving…" : "Confirm approval"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
