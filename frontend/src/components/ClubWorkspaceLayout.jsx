import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { fetchCurrentUser, fetchNotifications, fetchTeamTrainingSessions, respondToMatchRequest } from "../api";
import { ChevronDownIcon, UserCircleIcon } from "./AppIcons";
import NotificationBell from "./NotificationBell";
import SiteNavbar, { buildWorkspaceTabs } from "./SiteNavbar";
import { navigate } from "../navigation";

const AUTH_TOKEN_KEY = "netup.auth.token";
const AUTH_USER_KEY = "netup.auth.user";
const ACTIVE_TEAM_KEY = "netup.active.team";

function readStoredUser() {
  try {
    const raw = localStorage.getItem(AUTH_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function logout() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
  localStorage.removeItem(ACTIVE_TEAM_KEY);
  window.dispatchEvent(new Event("auth-state-changed"));
  navigate("/");
}

function openSessionPath(fullPath) {
  if (!fullPath || typeof fullPath !== "string") {
    return;
  }
  const qIndex = fullPath.indexOf("?");
  const search = qIndex >= 0 ? fullPath.slice(qIndex + 1) : "";
  const params = new URLSearchParams(search);
  const team = params.get("team");
  if (team) {
    const tid = Number(team);
    if (Number.isFinite(tid) && tid > 0) {
      window.dispatchEvent(new CustomEvent("netup-set-active-team", { detail: { teamId: tid } }));
    }
  }
  navigate(fullPath.startsWith("/") ? fullPath : `/${fullPath}`);
}

function formatVerificationStatus(value) {
  if (!value || typeof value !== "string") {
    return "\u2014";
  }
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatRoleWord(role) {
  if (!role || typeof role !== "string") {
    return "";
  }
  return role.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function buildTeamAssignmentLines(me) {
  if (!me) {
    return [];
  }
  const lines = [];
  (me.director_teams || []).forEach((t) => lines.push(`${t.name} \u2014 club director`));
  (me.coached_teams || []).forEach((t) => lines.push(`${t.name} \u2014 coach`));
  (me.player_teams || []).forEach((t) => lines.push(`${t.name} \u2014 player`));
  (me.children || []).forEach((ch) => {
    const name = [ch.user?.first_name, ch.user?.last_name].filter(Boolean).join(" ").trim() || "Linked child";
    const teamNames = (ch.teams || []).map((t) => t.name).join(", ");
    lines.push(`${name}'s teams: ${teamNames || "\u2014"}`);
  });
  return lines;
}

function isLiveMatchSession(session) {
  if (!session || session.session_type !== "match" || session.status === "cancelled" || session.is_ended) {
    return false;
  }
  const date = session.scheduled_date;
  if (!date) return false;
  const start = typeof session.start_time === "string" ? session.start_time.slice(0, 5) : "00:00";
  const end = typeof session.end_time === "string" ? session.end_time.slice(0, 5) : "23:59";
  const startTime = new Date(`${date}T${start}:00`);
  const endTime = new Date(`${date}T${end}:00`);
  const now = Date.now();
  return Number.isFinite(startTime.getTime()) && Number.isFinite(endTime.getTime()) && startTime.getTime() <= now && now <= endTime.getTime();
}

export default function ClubWorkspaceLayout({
  activeTab,
  heroOverlay = false,
  viewerAccountRole = null,
  teamOptions = [],
  activeTeamId = "",
  onChangeTeam = null,
  teamSelectorVariant = "custom",
  includeAllTeamsOption = true,
  /** Show "My sessions" when the user has at least one player team (roster membership). */
  showPlayerSessionsTab = false,
  /** Coach/director training: per-session attendance planning (EP-25). */
  showCoachAttendanceTab = false,
  children,
}) {
  const accountWrapRef = useRef(null);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [profileUser, setProfileUser] = useState(() => readStoredUser());
  const [profileMe, setProfileMe] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [showParentAttendanceFromProfile, setShowParentAttendanceFromProfile] = useState(false);
  const [liveMatch, setLiveMatch] = useState(null);
  const [pendingMatchRequest, setPendingMatchRequest] = useState(null);
  const [pendingMatchBusyAction, setPendingMatchBusyAction] = useState("");
  const [pendingMatchError, setPendingMatchError] = useState("");

  useEffect(() => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
      return undefined;
    }
    let cancelled = false;
    fetchCurrentUser()
      .then((me) => {
        if (!cancelled) {
          const roles = me.account_profile?.roles || [];
          const hasChildren = Array.isArray(me.children) && me.children.length > 0;
          const pendingLinks = Array.isArray(me.pending_parent_links) && me.pending_parent_links.length > 0;
          setShowParentAttendanceFromProfile(
            roles.includes("parent") || hasChildren || pendingLinks,
          );
        }
      })
      .catch(() => {
        if (!cancelled) {
          setShowParentAttendanceFromProfile(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
      setPendingMatchRequest(null);
      setPendingMatchError("");
      return undefined;
    }

    let cancelled = false;
    const loadPendingMatchRequest = async () => {
      try {
        const data = await fetchNotifications();
        if (cancelled) return;
        const firstPending =
          (data?.items || []).find(
            (item) => item.category === "match_request" && item.can_respond_to_match_request,
          ) || null;
        setPendingMatchRequest(firstPending);
        setPendingMatchError("");
      } catch (err) {
        if (!cancelled) {
          setPendingMatchRequest(null);
          setPendingMatchError(err.message || "Could not load match requests.");
        }
      }
    };

    void loadPendingMatchRequest();
    const onAuth = () => void loadPendingMatchRequest();
    const onNotificationsChanged = () => void loadPendingMatchRequest();
    window.addEventListener("auth-state-changed", onAuth);
    window.addEventListener("netup-notifications-changed", onNotificationsChanged);
    return () => {
      cancelled = true;
      window.removeEventListener("auth-state-changed", onAuth);
      window.removeEventListener("netup-notifications-changed", onNotificationsChanged);
    };
  }, []);

  useEffect(() => {
    if (!showCoachAttendanceTab || !activeTeamId || activeTeamId === "__all__") {
      setLiveMatch(null);
      return undefined;
    }

    let cancelled = false;
    const loadLiveMatch = async () => {
      try {
        const payload = await fetchTeamTrainingSessions(activeTeamId);
        if (cancelled) return;
        const match = (payload?.sessions || []).find(isLiveMatchSession) || null;
        setLiveMatch(match);
      } catch {
        if (!cancelled) {
          setLiveMatch(null);
        }
      }
    };

    void loadLiveMatch();
    const intervalId = window.setInterval(loadLiveMatch, 60000);
    const onScheduleChanged = () => void loadLiveMatch();
    window.addEventListener("netup-schedule-changed", onScheduleChanged);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
      window.removeEventListener("netup-schedule-changed", onScheduleChanged);
    };
  }, [activeTeamId, showCoachAttendanceTab]);

  const loadProfile = useCallback(async () => {
    setProfileLoading(true);
    setProfileError("");
    setProfileMe(null);
    try {
      const payload = await fetchCurrentUser();
      const user = payload.user || null;
      setProfileMe(payload);
      setProfileUser(user);
      if (user) {
        localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
      }
    } catch (err) {
      setProfileError(err.message || "Could not load profile.");
      setProfileUser(readStoredUser());
      setProfileMe(null);
    } finally {
      setProfileLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!accountMenuOpen) {
      return undefined;
    }

    const onPointerDown = (event) => {
      if (accountWrapRef.current && !accountWrapRef.current.contains(event.target)) {
        setAccountMenuOpen(false);
      }
    };

    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [accountMenuOpen]);

  useEffect(() => {
    if (!profileOpen) {
      return undefined;
    }

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        setProfileOpen(false);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [profileOpen]);

  const openProfile = () => {
    setAccountMenuOpen(false);
    setProfileOpen(true);
    void loadProfile();
  };

  const tabs = buildWorkspaceTabs({
    showPlayerSessionsTab,
    showCoachAttendanceTab,
    showCoachStatisticsTab: showCoachAttendanceTab,
    showParentAttendanceTab: viewerAccountRole === "parent" || showParentAttendanceFromProfile,
  });

  const onRespondToPendingMatch = useCallback(async (action) => {
    if (!pendingMatchRequest?.training_session_id) {
      return;
    }
    setPendingMatchBusyAction(action);
    setPendingMatchError("");
    try {
      await respondToMatchRequest(pendingMatchRequest.training_session_id, action);
      window.dispatchEvent(new Event("netup-notifications-changed"));
      window.dispatchEvent(new Event("netup-schedule-changed"));
      if (action === "accept" && pendingMatchRequest.session_path) {
        openSessionPath(pendingMatchRequest.session_path);
      } else {
        setPendingMatchRequest(null);
      }
    } catch (err) {
      setPendingMatchError(err.message || `Could not ${action} match request.`);
    } finally {
      setPendingMatchBusyAction("");
    }
  }, [pendingMatchRequest]);

  return (
    <div className={`vc-app vc-dashboard${heroOverlay ? " vc-dashboard--hero-overlay" : ""}`}>
      <SiteNavbar
        mode="workspace"
        activeTab={activeTab}
        tabs={tabs}
        teamSelector={
          <ClubTeamSelect
            teams={teamOptions}
            activeTeamId={activeTeamId}
            onChangeTeam={onChangeTeam}
            variant={teamSelectorVariant}
            includeAllTeamsOption={includeAllTeamsOption}
          />
        }
        actions={
          <>
            <NotificationBell />
            <div className="vc-account-wrap" ref={accountWrapRef}>
              <button
                type="button"
                className={`vc-dash-icon-btn${accountMenuOpen ? " is-active" : ""}`}
                aria-label="Account menu"
                aria-haspopup="menu"
                aria-expanded={accountMenuOpen}
                onClick={() => setAccountMenuOpen((open) => !open)}
              >
                <UserCircleIcon />
              </button>
              {accountMenuOpen ? (
                <div className="vc-account-dropdown" role="menu">
                  <button type="button" role="menuitem" onClick={openProfile}>
                    Profile
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className="vc-account-logout"
                    onClick={() => {
                      setAccountMenuOpen(false);
                      logout();
                    }}
                  >
                    Logout
                  </button>
                </div>
              ) : null}
            </div>
          </>
        }
      />

      {pendingMatchRequest ? (
        <section className="workspace-match-request-banner" aria-label="Pending match request">
          <div>
            <strong>{pendingMatchRequest.requesting_team_name || "Another team"} opened a match session with you.</strong>
            <p>{pendingMatchRequest.message}</p>
            {pendingMatchError ? <p className="schedule-feedback schedule-feedback--error">{pendingMatchError}</p> : null}
          </div>
          <div className="workspace-match-request-banner__actions">
            <button
              type="button"
              className="vc-action-btn"
              disabled={pendingMatchBusyAction === "accept"}
              onClick={() => void onRespondToPendingMatch("accept")}
            >
              {pendingMatchBusyAction === "accept" ? "Accepting..." : "Accept"}
            </button>
            <button
              type="button"
              className="vc-dash-icon-btn"
              style={{ width: "auto", padding: "0.65rem 1rem", borderRadius: "12px" }}
              disabled={pendingMatchBusyAction === "decline"}
              onClick={() => void onRespondToPendingMatch("decline")}
            >
              {pendingMatchBusyAction === "decline" ? "Declining..." : "Decline"}
            </button>
          </div>
        </section>
      ) : null}

      {liveMatch ? (
        <button
          type="button"
          className="live-match-banner"
          onClick={() =>
            openSessionPath(
              `/coach/attendance?team=${encodeURIComponent(String(activeTeamId))}&session=${encodeURIComponent(String(liveMatch.id))}`,
            )
          }
        >
          <span className="live-match-banner__pulse" aria-hidden="true" />
          <span>
            Live match now: <strong>{liveMatch.title}</strong>
            {liveMatch.opponent &&
            !String(liveMatch.title || "")
              .toLowerCase()
              .includes(String(liveMatch.opponent).toLowerCase())
              ? ` vs ${liveMatch.opponent}`
              : ""}
          </span>
          <span className="live-match-banner__cta">Open match stats</span>
        </button>
      ) : null}

      {profileOpen ? (
        <div
          className="vc-modal-backdrop"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              setProfileOpen(false);
            }
          }}
        >
          <div className="vc-modal vc-modal--profile" role="dialog" aria-modal="true" aria-labelledby="vc-profile-title">
            <div className="vc-modal__head">
              <h2 id="vc-profile-title">Your profile</h2>
              <button type="button" className="vc-modal__close" onClick={() => setProfileOpen(false)} aria-label="Close">
                {"\u00d7"}
              </button>
            </div>
            {profileLoading ? <p className="vc-modal__muted">{"Loading\u2026"}</p> : null}
            {profileError ? <p className="vc-modal__error">{profileError}</p> : null}
            {!profileLoading && (profileMe?.user || profileUser) ? (
              (() => {
                const user = profileMe?.user || profileUser;
                const account = profileMe?.account_profile || {};
                const roles = account.roles || [];
                const roleLine =
                  account.display_role ||
                  (roles.length ? roles.map((r) => formatRoleWord(r)).join(", ") : "") ||
                  "\u2014";
                const teamLines = buildTeamAssignmentLines(profileMe);
                const parents = account.linked_parents || [];
                const children = account.linked_children || [];
                const fees = account.pending_fees || {};
                const feeItems = fees.items || [];

                return (
                  <dl className="vc-profile-dl">
                    <div>
                      <dt>Name</dt>
                      <dd>
                        {[user.first_name, user.last_name].filter(Boolean).join(" ").trim() || "\u2014"}
                      </dd>
                    </div>
                    <div>
                      <dt>Email</dt>
                      <dd>{user.email || "\u2014"}</dd>
                    </div>
                    <div>
                      <dt>User ID</dt>
                      <dd>
                        <code className="vc-profile-user-id">{user.id != null ? String(user.id) : "\u2014"}</code>
                        <span className="vc-profile-note">Your unique account number.</span>
                      </dd>
                    </div>
                    <div>
                      <dt>Date of birth</dt>
                      <dd>
                        {user.date_of_birth
                          ? new Intl.DateTimeFormat("en-US", {
                              year: "numeric",
                              month: "long",
                              day: "numeric",
                            }).format(new Date(`${user.date_of_birth}T12:00:00`))
                          : "\u2014"}
                      </dd>
                    </div>
                    <div>
                      <dt>Account status</dt>
                      <dd>{formatVerificationStatus(user.verification_status)}</dd>
                    </div>
                    <div>
                      <dt>Role</dt>
                      <dd>{roleLine}</dd>
                    </div>
                    <div>
                      <dt>Teams</dt>
                      <dd>
                        {teamLines.length ? (
                          <ul className="vc-profile-list">
                            {teamLines.map((line, idx) => (
                              <li key={`${idx}-${line}`}>{line}</li>
                            ))}
                          </ul>
                        ) : (
                          "\u2014"
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>Linked parent accounts</dt>
                      <dd>
                        {parents.length ? (
                          <ul className="vc-profile-list">
                            {parents.map((p) => (
                              <li key={p.id}>
                                {[p.first_name, p.last_name].filter(Boolean).join(" ").trim() || p.email}
                                {p.email ? ` \u00b7 ${p.email}` : ""}
                                {p.is_legal_guardian ? " (legal guardian)" : ""}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          "\u2014"
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>Linked children (parent view)</dt>
                      <dd>
                        {children.length ? (
                          <ul className="vc-profile-list">
                            {children.map((c) => (
                              <li key={c.id}>
                                {[c.first_name, c.last_name].filter(Boolean).join(" ").trim() || c.email}
                                {c.email ? ` \u00b7 ${c.email}` : ""}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          "\u2014"
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>Pending fees</dt>
                      <dd>
                        {typeof fees.total_due === "number" && fees.total_due > 0
                          ? `${fees.currency || "USD"} ${fees.total_due.toFixed(2)}`
                          : fees.total_due === 0 && !feeItems.length
                            ? `${fees.currency || "USD"} 0.00 (nothing due)`
                            : "\u2014"}
                        {fees.note ? (
                          <span className="vc-profile-note">
                            {" "}
                            {fees.note}
                          </span>
                        ) : null}
                        {feeItems.length ? (
                          <ul className="vc-profile-list">
                            {feeItems.map((item, idx) => (
                              <li key={idx}>{typeof item === "string" ? item : JSON.stringify(item)}</li>
                            ))}
                          </ul>
                        ) : null}
                      </dd>
                    </div>
                  </dl>
                );
              })()
            ) : null}
            {!profileLoading && !profileUser && !profileError ? (
              <p className="vc-modal__muted">No profile details available.</p>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="vc-dash-shell vc-workspace-main">{children}</div>
    </div>
  );
}

export function ClubTeamSelect({
  teams,
  activeTeamId,
  onChangeTeam,
  variant = "custom",
  includeAllTeamsOption = true,
}) {
  const menuId = useId();
  const wrapRef = useRef(null);
  const [open, setOpen] = useState(false);

  const options = useMemo(() => {
    const formatTeamLabel = (team) => {
      if (!team) {
        return "None";
      }
      const clubLabel = team.clubShortName || team.clubName || "";
      return clubLabel ? `${team.name} (${clubLabel})` : team.name;
    };

    const list = [];
    list.push({ key: "", label: "None", value: "", team: null });
    if (includeAllTeamsOption && teams.length > 0) {
      list.push({
        key: "__all__",
        label: "All",
        value: "__all__",
        team: { id: "__all__", name: "All", canManageSchedule: false, canManageTraining: false },
      });
    }
    teams.forEach((team) => {
      list.push({
        key: String(team.id),
        label: formatTeamLabel(team),
        value: String(team.id),
        team,
      });
    });
    return list;
  }, [includeAllTeamsOption, teams]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const onPointerDown = (event) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) {
        setOpen(false);
      }
    };

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const selectedOption =
    options.find((option) => option.value === String(activeTeamId ?? "")) ||
    options.find((option) => option.value === "") ||
    options[0];

  const handleSelect = (option) => {
    setOpen(false);
    if (!option?.team || typeof onChangeTeam !== "function") {
      return;
    }
    onChangeTeam(option.team);
  };

  if (variant === "native") {
    return (
      <label className="vc-dash-team-field">
        <span className="vc-dash-team-field__label">Team</span>
        <select
          className="vc-dash-team-select"
          value={selectedOption?.value ?? ""}
          onChange={(event) => {
            const option = options.find((item) => item.value === event.target.value) || options[0];
            handleSelect(option);
          }}
        >
          {options.map((option) => (
            <option key={option.key} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    );
  }

  return (
    <div className="vc-dash-team-field vc-team-dropdown" ref={wrapRef}>
      <span className="vc-dash-team-field__label">
        Team
      </span>
      <button
        type="button"
        className={`vc-team-dropdown__trigger${open ? " is-open" : ""}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="vc-team-dropdown__value">{selectedOption?.label || "None"}</span>
        <ChevronDownIcon className={`vc-team-dropdown__chevron${open ? " is-open" : ""}`} />
      </button>
      {open ? (
        <div className="vc-team-dropdown__menu" id={menuId} role="listbox" aria-label="Select a team">
          {options.map((option) => (
            <button
              key={option.key}
              type="button"
              role="option"
              aria-selected={selectedOption?.value === option.value}
              className={`vc-team-dropdown__option${selectedOption?.value === option.value ? " is-selected" : ""}`}
              onClick={() => handleSelect(option)}
            >
              {option.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
