import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { fetchCurrentUser } from "../api";
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

export default function ClubWorkspaceLayout({
  activeTab,
  heroOverlay = false,
  viewerAccountRole = null,
  teamOptions = [],
  activeTeamId = "",
  onChangeTeam = null,
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
    showParentAttendanceTab: viewerAccountRole === "parent" || showParentAttendanceFromProfile,
  });

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
