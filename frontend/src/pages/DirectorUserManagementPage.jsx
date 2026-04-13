import { useCallback, useEffect, useRef, useState } from "react";
import {
  directorRejectUser,
  directorResolveParentLink,
  directorSetUserAccountRole,
  directorVerifyUser,
  fetchCurrentUser,
  fetchDirectorPendingParentLinks,
  fetchDirectorPendingUsers,
  fetchDirectorUserDirectory,
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

const DIRECTORY_ROLE_OPTIONS = [
  { value: "director", label: "Director" },
  { value: "coach", label: "Coach" },
  { value: "player", label: "Player" },
  { value: "parent", label: "Parent" },
];

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

export default function DirectorUserManagementPage() {
  const [pendingUsers, setPendingUsers] = useState([]);
  const [assignableTeams, setAssignableTeams] = useState([]);
  const [loadingPending, setLoadingPending] = useState(true);
  const [allUsers, setAllUsers] = useState([]);
  const [directoryCount, setDirectoryCount] = useState(0);
  const [loadingDirectory, setLoadingDirectory] = useState(true);
  const [viewerIsStaff, setViewerIsStaff] = useState(false);
  const [viewerUserId, setViewerUserId] = useState(null);
  const [ownedClubs, setOwnedClubs] = useState([]);
  const [error, setError] = useState("");
  const [directoryError, setDirectoryError] = useState("");
  const [actionKey, setActionKey] = useState("");
  const [verifyTarget, setVerifyTarget] = useState(null);
  const [verifyRole, setVerifyRole] = useState("player");
  const [verifyTeamId, setVerifyTeamId] = useState("");
  const [verifyModalError, setVerifyModalError] = useState("");
  const [roleEdits, setRoleEdits] = useState({});
  const [directorClubEdits, setDirectorClubEdits] = useState({});
  const [parentLinkRows, setParentLinkRows] = useState([]);
  const [loadingParentLinks, setLoadingParentLinks] = useState(true);
  const [parentLinkError, setParentLinkError] = useState("");
  const [parentLinkSuccess, setParentLinkSuccess] = useState("");
  const parentLinkSuccessTimerRef = useRef(null);

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

  const loadDirectory = useCallback(async () => {
    setLoadingDirectory(true);
    setDirectoryError("");
    try {
      const me = await fetchCurrentUser();
      setViewerIsStaff(Boolean(me.viewer_is_staff));
      setViewerUserId(me.user?.id ?? null);
      setOwnedClubs(me.owned_clubs || []);
      const payload = await fetchDirectorUserDirectory(800);
      const rows = payload.users || [];
      setAllUsers(rows);
      setDirectoryCount(payload.count ?? rows.length);
      setRoleEdits({});
      setDirectorClubEdits({});
    } catch (err) {
      setAllUsers([]);
      setDirectoryCount(0);
      setDirectoryError(err.message || "Could not load user directory.");
    } finally {
      setLoadingDirectory(false);
    }
  }, []);

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

  useEffect(() => {
    loadPending();
  }, [loadPending]);

  useEffect(() => {
    void loadDirectory();
  }, [loadDirectory]);

  useEffect(() => {
    void loadParentLinks();
  }, [loadParentLinks]);

  useEffect(() => {
    return () => {
      if (parentLinkSuccessTimerRef.current != null) {
        window.clearTimeout(parentLinkSuccessTimerRef.current);
      }
    };
  }, []);

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
      await loadDirectory();
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
      await loadDirectory();
    } catch (err) {
      setError(err.message || "Reject failed.");
    } finally {
      setActionKey("");
    }
  };

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

  const pendingCount = pendingUsers.length;
  const showOptionalTeamAssign = verifyRole === "player" || verifyRole === "coach";

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

  return (
    <div className="vc-director-page">
      <p className="vc-director-kicker">User Management for Director</p>
      <div className="vc-director-card">
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center" }}>
          <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
            ← Dashboard
          </button>
          <button type="button" className="vc-link-cyan" onClick={() => navigate("/director/payments")}>
            Payments & fees
          </button>
        </div>

        {error || directoryError ? (
          <div className="vc-director-error">{error || directoryError}</div>
        ) : null}
        {parentLinkError ? <div className="vc-director-error">{parentLinkError}</div> : null}
        {parentLinkSuccess ? <div className="vc-director-success">{parentLinkSuccess}</div> : null}

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
                              className="vc-du-action"
                              disabled={busyA || busyR}
                              onClick={() => void onResolveParentLink(rid, "approve")}
                            >
                              {busyA ? "…" : "Approve"}
                            </button>
                            <button
                              type="button"
                              className="vc-du-action"
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

        <section className="vc-director-section">
          <h2 className="vc-panel-title">Pending Accounts</h2>
          <p className="vc-modal__muted" style={{ marginTop: 0 }}>
            New accounts now verify themselves with an email OTP during signup, so this queue should normally stay
            empty.
          </p>
          <div className="vc-director-layout">
            <div className="vc-director-table-wrap">
              {loadingPending ? (
                <p className="vc-director-loading">Loading pending accounts…</p>
              ) : (
                <table className="vc-director-table vc-director-table--pending">
                  <thead>
                    <tr>
                      <th>User ID</th>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingUsers.length === 0 ? (
                      <tr>
                        <td colSpan={4} style={{ color: "#6b7580", fontWeight: 600 }}>
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
                            <td>
                              <code>{u.id}</code>
                            </td>
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

        <section className="vc-director-section">
          <h2 className="vc-panel-title">All people in the app</h2>
          <p className="vc-modal__muted" style={{ marginTop: 0 }}>
            Each person has one <strong>role</strong> (Director, Coach, Player, or Parent). Changing it updates their
            permissions. You cannot remove your own Director role; you can promote others to Director for a club you
            manage, or change another Director to a different role.
          </p>
          {loadingDirectory ? (
            <p className="vc-director-loading">Loading directory…</p>
          ) : (
            <div className="vc-director-table-wrap">
              <p className="vc-director-loading" style={{ color: "#6b7580", marginBottom: "0.75rem" }}>
                Showing {allUsers.length} of {directoryCount} loaded (max 800).
              </p>
              <table className="vc-director-table">
                <thead>
                  <tr>
                    <th>User ID</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Status</th>
                    <th>Role</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {allUsers.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ color: "#6b7580", fontWeight: 600 }}>
                        No users found.
                      </td>
                    </tr>
                  ) : (
                    allUsers.map((u) => {
                      const fullName = `${u.first_name || ""} ${u.last_name || ""}`.trim() || u.email;
                      const busy = actionKey === `role-${u.id}`;
                      const staffLocked = u.is_staff && !viewerIsStaff;
                      const currentRole = u.role || "";
                      const selectVal = roleEdits[u.id] !== undefined ? roleEdits[u.id] : currentRole || "";
                      const selfDirectorLocked = viewerUserId === u.id && currentRole === "director";
                      const rowDirty = roleEdits[u.id] !== undefined && roleEdits[u.id] !== currentRole;
                      const saveDisabled =
                        !rowDirty || staffLocked || busy || selfDirectorLocked || !selectVal;
                      return (
                        <tr key={u.id}>
                          <td>
                            <code>{u.id}</code>
                          </td>
                          <td>{fullName}</td>
                          <td>{u.email}</td>
                          <td>{formatVerificationStatus(u.verification_status)}</td>
                          <td>
                            <div style={{ display: "grid", gap: "0.35rem", maxWidth: 280 }}>
                              <select
                                className="vc-director-modal__select"
                                style={{ minWidth: "9rem" }}
                                value={selectVal}
                                disabled={staffLocked || busy || selfDirectorLocked}
                                title={
                                  selfDirectorLocked
                                    ? "You cannot remove your own Director role."
                                    : staffLocked
                                      ? "Staff account — only platform staff can change this."
                                      : ""
                                }
                                onChange={(e) => {
                                  const v = e.target.value;
                                  setRoleEdits((m) => ({ ...m, [u.id]: v }));
                                  if (v === "director" && ownedClubs.length > 1) {
                                    setDirectorClubEdits((m) => ({
                                      ...m,
                                      [u.id]: m[u.id] ?? ownedClubs[0]?.id,
                                    }));
                                  }
                                }}
                              >
                                {!currentRole ? (
                                  <option value="">
                                    {"\u2014"}
                                  </option>
                                ) : null}
                                {DIRECTORY_ROLE_OPTIONS.map((opt) => (
                                  <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                  </option>
                                ))}
                              </select>
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
                            </div>
                          </td>
                          <td>
                            <button
                              type="button"
                              className="vc-du-action"
                              disabled={saveDisabled}
                              onClick={() => void onSaveAccountRole(u.id)}
                            >
                              {busy ? "…" : "Save"}
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
              User ID <code>{verifyTarget.id}</code>
              {" · "}
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
