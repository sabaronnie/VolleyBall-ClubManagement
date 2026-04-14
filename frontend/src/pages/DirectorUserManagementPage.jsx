import { useCallback, useEffect, useRef, useState } from "react";
import {
  directorResolveParentLink,
  directorSetUserAccountRole,
  fetchCurrentUser,
  fetchDirectorPendingParentLinks,
  fetchDirectorUserDirectory,
} from "../api";

const AUTH_TOKEN_KEY = "netup.auth.token";

function navigate(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

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

export default function DirectorUserManagementPage({
  embedded = false,
  onOpenPayments = null,
}) {
  const [allUsers, setAllUsers] = useState([]);
  const [directoryCount, setDirectoryCount] = useState(0);
  const [loadingDirectory, setLoadingDirectory] = useState(true);
  const [viewerIsStaff, setViewerIsStaff] = useState(false);
  const [viewerUserId, setViewerUserId] = useState(null);
  const [ownedClubs, setOwnedClubs] = useState([]);
  const [canManageRoles, setCanManageRoles] = useState(false);
  const [showParentLinks, setShowParentLinks] = useState(false);
  const [directoryScopeKind, setDirectoryScopeKind] = useState("club");
  const [directoryHeading, setDirectoryHeading] = useState("All people in your club");
  const [directoryDescription, setDirectoryDescription] = useState(
    "This list is limited to people connected to the clubs you direct, including linked parents.",
  );
  const [error, setError] = useState("");
  const [directoryError, setDirectoryError] = useState("");
  const [actionKey, setActionKey] = useState("");
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

  const loadDirectory = useCallback(async () => {
    setLoadingDirectory(true);
    setDirectoryError("");
    try {
      const me = await fetchCurrentUser();
      setViewerIsStaff(Boolean(me.viewer_is_staff));
      setViewerUserId(me.user?.id ?? null);
      setOwnedClubs(me.owned_clubs || []);
      const directorView = Boolean(me.viewer_is_staff || me.is_director_or_staff || (me.owned_clubs || []).length > 0);
      const coachedTeams = me.coached_teams || [];
      setCanManageRoles(directorView);
      setShowParentLinks(directorView);
      const payload = await fetchDirectorUserDirectory(800);
      const rows = payload.users || [];
      const scopeKind = payload.scope?.kind || (directorView ? "club" : "team");
      setDirectoryScopeKind(scopeKind);
      if (scopeKind === "team") {
        setDirectoryHeading(coachedTeams.length > 1 ? "All people on your teams" : "All people on your team");
        setDirectoryDescription(
          "This list is limited to the coaches, players, and linked parents connected to the teams you coach.",
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
      {parentLinkError ? <div className="vc-director-error">{parentLinkError}</div> : null}
      {parentLinkSuccess ? <div className="vc-director-success">{parentLinkSuccess}</div> : null}

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
      ) : null}

      <section className="vc-director-section">
          <h2 className="vc-panel-title">{directoryHeading}</h2>
          <p className="vc-modal__muted" style={{ marginTop: 0 }}>
            {directoryDescription}{" "}
            {canManageRoles ? (
              <>
                Each person has one <strong>role</strong> (Director, Coach, Player, or Parent). Changing it updates
                their permissions. You cannot remove your own Director role; you can promote others to Director for a
                club you manage, or change another Director to a different role.
              </>
            ) : (
              <>This view is read-only for coaches.</>
            )}
          </p>
          {loadingDirectory ? (
            <p className="vc-director-loading">Loading directory…</p>
          ) : (
            <div className="vc-director-table-wrap">
              <p className="vc-director-loading" style={{ color: "#6b7580", marginBottom: "0.75rem" }}>
                Showing {allUsers.length} of {directoryCount} loaded
                {directoryScopeKind === "team" ? " from your team scope" : directoryScopeKind === "club" ? " from your club scope" : ""}.
              </p>
              <table className="vc-director-table">
                <thead>
                  <tr>
                    <th>User ID</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Status</th>
                    <th>Role</th>
                    {canManageRoles ? <th /> : null}
                  </tr>
                </thead>
                <tbody>
                  {allUsers.length === 0 ? (
                    <tr>
                      <td colSpan={canManageRoles ? 6 : 5} style={{ color: "#6b7580", fontWeight: 600 }}>
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
                            {canManageRoles ? (
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
                            ) : (
                              <span>{currentRole ? currentRole.charAt(0).toUpperCase() + currentRole.slice(1) : "—"}</span>
                            )}
                          </td>
                          {canManageRoles ? (
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
                          ) : null}
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
