import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  cancelTrainingSession,
  createMatch,
  createTeamTrainingSession,
  endMatch,
  fetchCoachTrainingSessionAttendance,
  fetchCurrentUser,
  fetchMatch,
  fetchTeamAttendanceAnalytics,
  fetchTeamTrainingSessions,
  remindUnconfirmedTrainingSession,
  resumeMatch,
  updateMatchPlayerStats,
} from "../api";
import InlineDropdown from "../components/InlineDropdown";
import { formatTimeRange12h, TimeSelect } from "../timeUtils";

function parseLocalDate(iso) {
  if (!iso || typeof iso !== "string") return null;
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

function statusBadgeClass(status) {
  if (status === "present") return "vc-status-paid";
  if (status === "pending") return "vc-status-pending";
  if (status === "absent") return "vc-status-overdue";
  if (status === "cancelled") return "vc-modal__muted";
  return "";
}

function matchResultBadgeClass(result) {
  if (result === "win") return "vc-status-paid";
  if (result === "loss") return "vc-status-overdue";
  if (result === "draw") return "vc-status-pending";
  return "vc-modal__muted";
}

function engagementBadgeClass(flag) {
  if (flag === "high") return "vc-status-paid";
  if (flag === "low") return "vc-status-overdue";
  if (flag === "medium") return "vc-status-pending";
  return "vc-modal__muted";
}

function engagementLabel(flag) {
  if (flag === "high") return "Strong";
  if (flag === "low") return "Needs attention";
  if (flag === "medium") return "Steady";
  return "Not enough data";
}

function isoDateLocal(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function sessionHasStarted(session) {
  if (!session?.scheduled_date) return false;
  const startTime = typeof session.start_time === "string" && session.start_time ? session.start_time.slice(0, 5) : "00:00";
  const dt = new Date(`${session.scheduled_date}T${startTime}:00`);
  return Number.isFinite(dt.getTime()) ? dt.getTime() <= Date.now() : false;
}

function sessionDateTimeValue(session, timeKey, fallbackTime) {
  if (!session?.scheduled_date) return Number.NaN;
  const rawTime = typeof session?.[timeKey] === "string" && session[timeKey] ? session[timeKey].slice(0, 5) : fallbackTime;
  const dt = new Date(`${session.scheduled_date}T${rawTime}:00`);
  return dt.getTime();
}

function sessionSortBucket(session, nowMs) {
  const isCancelled = session?.status === "cancelled";
  const isMatch = session?.session_type === "match";
  const isEndedMatch = isMatch && Boolean(session?.is_ended);
  const startMs = sessionDateTimeValue(session, "start_time", "00:00");
  const endMs = sessionDateTimeValue(session, "end_time", "23:59");
  const hasStarted = Number.isFinite(startMs) ? startMs <= nowMs : false;
  const hasFinishedByClock = Number.isFinite(endMs) ? endMs < nowMs : false;

  if (isCancelled) {
    return 2;
  }
  if (isMatch) {
    if (isEndedMatch && hasFinishedByClock) {
      return 2;
    }
    if (hasStarted && !isEndedMatch) {
      return 0;
    }
    return 1;
  }
  if (hasStarted && !hasFinishedByClock) {
    return 0;
  }
  if (hasFinishedByClock) {
    return 2;
  }
  return 1;
}

function formatDateTimeLabel(isoString) {
  if (!isoString) return "";
  const dt = new Date(isoString);
  if (!Number.isFinite(dt.getTime())) return "";
  return dt.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

const MATCH_STAT_FIELDS = [
  { key: "points_scored", label: "Points" },
  { key: "aces", label: "Aces" },
  { key: "blocks", label: "Blocks" },
  { key: "assists", label: "Assists" },
  { key: "errors", label: "Errors" },
  { key: "digs", label: "Digs" },
];

const EVENT_TYPE_OPTIONS = [
  { value: "training", label: "Training" },
  { value: "fundraiser", label: "Fundraiser" },
  { value: "game", label: "Game" },
];

const SESSION_LIST_FILTER_OPTIONS = [
  { value: "all", label: "All", badgeClassName: "session-category-badge session-category-badge--all" },
  { value: "game", label: "Game", badgeClassName: "session-category-badge session-category-badge--game" },
  { value: "training", label: "Training", badgeClassName: "session-category-badge session-category-badge--training" },
  {
    value: "fundraiser",
    label: "Fundraiser",
    badgeClassName: "session-category-badge session-category-badge--fundraiser",
  },
];

function sessionCategoryValue(session) {
  if (session?.session_type === "match") {
    return "game";
  }
  const normalizedTitle = String(session?.title || "")
    .trim()
    .toLowerCase();
  if (normalizedTitle.includes("fundraiser")) {
    return "fundraiser";
  }
  return "training";
}

function sessionCategoryBadgeClass(session) {
  return `session-category-badge session-category-badge--${sessionCategoryValue(session)}`;
}

function sessionCategoryLabel(session) {
  const match = SESSION_LIST_FILTER_OPTIONS.find((option) => option.value === sessionCategoryValue(session));
  return match?.label || "Training";
}

function normalizeStatValue(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.floor(n);
}

function clientMatchWeightedScore(stats) {
  return (
    normalizeStatValue(stats?.points_scored) +
    normalizeStatValue(stats?.aces) * 2 +
    normalizeStatValue(stats?.blocks) * 2 +
    normalizeStatValue(stats?.assists) * 1.5 +
    normalizeStatValue(stats?.digs) -
    normalizeStatValue(stats?.errors)
  );
}

function collectVisibleTeams(me) {
  const map = new Map();
  const addTeam = (team) => {
    if (!team?.id || map.has(Number(team.id))) return;
    map.set(Number(team.id), team);
  };
  (me?.director_teams || []).forEach(addTeam);
  (me?.coached_teams || []).forEach(addTeam);
  (me?.player_teams || []).forEach(addTeam);
  (me?.children || []).forEach((child) => (child.teams || []).forEach(addTeam));
  return Array.from(map.values());
}

function GameOpponentDropdown({
  teams,
  searchValue,
  onSearchChange,
  selectedTeam,
  selectedTeamId,
  onSelectTeam,
  useExternalOpponent,
  externalOpponentName,
  onUseExternalOpponent,
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const displayValue = useExternalOpponent
    ? externalOpponentName.trim() || "External team"
    : selectedTeam?.name || "Choose opponent";

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const onPointerDown = (event) => {
      if (!wrapRef.current?.contains(event.target)) {
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

  return (
    <div className={`match-opponent-dropdown${open ? " is-open" : ""}`} ref={wrapRef}>
      <button
        type="button"
        className="match-opponent-dropdown__trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => {
          setOpen((current) => {
            const nextOpen = !current;
            if (nextOpen) {
              onSearchChange("");
            }
            return nextOpen;
          });
        }}
      >
        <span>{displayValue}</span>
      </button>
      {open ? (
        <div className="match-opponent-dropdown__menu" role="listbox" aria-label="Opponent team">
          <input
            className="match-opponent-dropdown__search"
            value={searchValue}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search teams"
          />
          <div className="match-opponent-dropdown__options">
            {teams.length ? (
              teams.map((team) => (
                <button
                  key={team.id}
                  type="button"
                  role="option"
                  aria-selected={!useExternalOpponent && Number(selectedTeamId) === Number(team.id)}
                  className={`match-opponent-dropdown__option${
                    !useExternalOpponent && Number(selectedTeamId) === Number(team.id) ? " is-selected" : ""
                  }`}
                  onPointerDown={(event) => {
                    event.preventDefault();
                    onSelectTeam(team);
                    setOpen(false);
                  }}
                  onClick={(event) => {
                    if (event.detail === 0) {
                      onSelectTeam(team);
                      setOpen(false);
                    }
                  }}
                >
                  {team.name}
                </button>
              ))
            ) : (
              <p className="match-opponent-dropdown__empty">No teams found</p>
            )}
            <button
              type="button"
              className={`match-opponent-dropdown__option${useExternalOpponent ? " is-selected" : ""}`}
              onPointerDown={(event) => {
                event.preventDefault();
                onUseExternalOpponent();
                setOpen(false);
              }}
              onClick={(event) => {
                if (event.detail === 0) {
                  onUseExternalOpponent();
                  setOpen(false);
                }
              }}
            >
              Other external team
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function CoachSessionAttendancePage({ activeTeam }) {
  const teamId = activeTeam?.id && activeTeam.id !== "__all__" ? activeTeam.id : null;
  const defaultRange = useMemo(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - 84);
    return { start: isoDateLocal(start), end: isoDateLocal(end) };
  }, []);
  const [listPayload, setListPayload] = useState(null);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [detailPayload, setDetailPayload] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [analyticsStart, setAnalyticsStart] = useState(defaultRange.start);
  const [analyticsEnd, setAnalyticsEnd] = useState(defaultRange.end);
  const [analyticsGrouping, setAnalyticsGrouping] = useState("week");
  const [analyticsLastN, setAnalyticsLastN] = useState("");
  const [analyticsPayload, setAnalyticsPayload] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState("");
  const [analyticsExpanded, setAnalyticsExpanded] = useState(false);
  const [sessionListFilter, setSessionListFilter] = useState("all");
  const [newEventType, setNewEventType] = useState("training");
  const [newSessionTitle, setNewSessionTitle] = useState("");
  const [newSessionDate, setNewSessionDate] = useState(() => isoDateLocal(new Date()));
  const [newSessionStart, setNewSessionStart] = useState("18:00");
  const [newSessionEnd, setNewSessionEnd] = useState("19:30");
  const [newSessionLocation, setNewSessionLocation] = useState("");
  const [newSessionNotifyPlayers, setNewSessionNotifyPlayers] = useState(true);
  const [newSessionNotifyParents, setNewSessionNotifyParents] = useState(true);
  const [createSessionBusy, setCreateSessionBusy] = useState(false);
  const [createSessionError, setCreateSessionError] = useState("");
  const titleInputRef = useRef(null);
  const locationInputRef = useRef(null);
  const [createSessionSuccess, setCreateSessionSuccess] = useState("");
  const [opponentTeams, setOpponentTeams] = useState([]);
  const [opponentSearch, setOpponentSearch] = useState("");
  const [selectedOpponentTeamId, setSelectedOpponentTeamId] = useState("");
  const [useExternalOpponent, setUseExternalOpponent] = useState(false);
  const [externalOpponentName, setExternalOpponentName] = useState("");
  const [matchPayload, setMatchPayload] = useState(null);
  const [matchLoading, setMatchLoading] = useState(false);
  const [matchError, setMatchError] = useState("");
  const [expandedMatchPlayerId, setExpandedMatchPlayerId] = useState(null);
  const [savingStatsByPlayerId, setSavingStatsByPlayerId] = useState({});
  const [statsSaveError, setStatsSaveError] = useState("");
  const [endMatchBusy, setEndMatchBusy] = useState(false);
  const [endMatchError, setEndMatchError] = useState("");
  const [endMatchMessage, setEndMatchMessage] = useState("");
  const [opponentFinalScoreInput, setOpponentFinalScoreInput] = useState("");
  const statsSaveTimersRef = useRef({});
  const [remindBusy, setRemindBusy] = useState(false);
  const [remindMessage, setRemindMessage] = useState("");
  const [remindError, setRemindError] = useState("");
  const [cancelBusy, setCancelBusy] = useState(false);
  const [cancelMessage, setCancelMessage] = useState("");
  const [cancelError, setCancelError] = useState("");
  const listLoadSeqRef = useRef(0);
  const sessionListPanelRef = useRef(null);
  const sessionDetailPanelRef = useRef(null);
  const scrollRestoreRef = useRef(null);

  const preserveViewportPosition = useCallback(() => {
    if (typeof window === "undefined") {
      return;
    }

    const restoreState = {
      x: window.scrollX,
      y: window.scrollY,
      until: Date.now() + 1200,
    };
    scrollRestoreRef.current = restoreState;

    const restore = () => {
      if (scrollRestoreRef.current !== restoreState) {
        return;
      }
      window.scrollTo(restoreState.x, restoreState.y);
    };

    requestAnimationFrame(() => {
      restore();
      requestAnimationFrame(restore);
    });
    setTimeout(restore, 100);
    setTimeout(restore, 300);
  }, []);

  const handleSelectSession = useCallback(
    (sessionId) => {
      preserveViewportPosition();
      setSelectedSessionId(sessionId);
    },
    [preserveViewportPosition],
  );

  const loadList = useCallback(async () => {
    const requestSeq = listLoadSeqRef.current + 1;
    listLoadSeqRef.current = requestSeq;
    if (!teamId) {
      setListPayload(null);
      setListLoading(false);
      return;
    }
    setListLoading(true);
    setListError("");
    try {
      const data = await fetchTeamTrainingSessions(teamId);
      if (listLoadSeqRef.current !== requestSeq) {
        return;
      }
      setListPayload(data);
    } catch (err) {
      if (listLoadSeqRef.current !== requestSeq) {
        return;
      }
      setListPayload(null);
      setListError(err.message || "Could not load sessions.");
    } finally {
      if (listLoadSeqRef.current === requestSeq) {
        setListLoading(false);
      }
    }
  }, [teamId]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    const source = sessionDetailPanelRef.current;
    const target = sessionListPanelRef.current;
    if (!source || !target) {
      return undefined;
    }

    let frameId = 0;
    const syncSessionListHeight = () => {
      if (frameId) {
        cancelAnimationFrame(frameId);
      }
      frameId = requestAnimationFrame(() => {
        const detailHeight = Math.ceil(source.getBoundingClientRect().height);
        const nextHeight = selectedSessionId ? detailHeight : Math.max(detailHeight + 180, 620);
        if (nextHeight > 0) {
          target.style.setProperty("--session-list-panel-height", `${nextHeight}px`);
        }
      });
    };

    syncSessionListHeight();
    window.addEventListener("resize", syncSessionListHeight);

    let observer = null;
    if (typeof ResizeObserver === "function") {
      observer = new ResizeObserver(syncSessionListHeight);
      observer.observe(source);
    }

    return () => {
      if (frameId) {
        cancelAnimationFrame(frameId);
      }
      window.removeEventListener("resize", syncSessionListHeight);
      if (observer) {
        observer.disconnect();
      }
    };
  }, [teamId, selectedSessionId, detailLoading, detailPayload, matchPayload, expandedMatchPlayerId]);

  useEffect(() => {
    const restoreState = scrollRestoreRef.current;
    if (!restoreState || typeof window === "undefined") {
      return undefined;
    }
    if (Date.now() > restoreState.until) {
      scrollRestoreRef.current = null;
      return undefined;
    }

    let frameId = requestAnimationFrame(() => {
      window.scrollTo(restoreState.x, restoreState.y);
    });
    const timerId = setTimeout(() => {
      if (scrollRestoreRef.current === restoreState) {
        window.scrollTo(restoreState.x, restoreState.y);
      }
    }, 80);

    return () => {
      cancelAnimationFrame(frameId);
      clearTimeout(timerId);
    };
  }, [selectedSessionId, detailLoading, detailPayload, matchPayload]);

  useEffect(() => {
    let cancelled = false;
    fetchCurrentUser()
      .then((me) => {
        if (!cancelled) {
          setOpponentTeams(collectVisibleTeams(me));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setOpponentTeams([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      Object.values(statsSaveTimersRef.current || {}).forEach((timer) => clearTimeout(timer));
    };
  }, []);

  useEffect(() => {
    setSelectedSessionId(null);
    setDetailPayload(null);
    setDetailError("");
    setAnalyticsStart(defaultRange.start);
    setAnalyticsEnd(defaultRange.end);
    setAnalyticsGrouping("week");
    setAnalyticsLastN("");
    setAnalyticsExpanded(false);
    setSessionListFilter("all");
    setAnalyticsPayload(null);
    setNewEventType("training");
    setNewSessionTitle("");
    setCreateSessionError("");
    setCreateSessionSuccess("");
    setOpponentSearch("");
    setSelectedOpponentTeamId("");
    setUseExternalOpponent(false);
    setExternalOpponentName("");
    setMatchPayload(null);
    setMatchError("");
    setExpandedMatchPlayerId(null);
    setSavingStatsByPlayerId({});
    setStatsSaveError("");
    setEndMatchError("");
    setEndMatchMessage("");
    setOpponentFinalScoreInput("");
    setRemindMessage("");
    setRemindError("");
    setCancelMessage("");
    setCancelError("");
  }, [teamId, defaultRange.start, defaultRange.end]);

  useEffect(() => {
    const syncCoachTeamFromUrl = () => {
      const path = window.location.pathname.replace(/\/$/, "") || "/";
      if (!path.endsWith("/coach/attendance")) {
        return;
      }
      const params = new URLSearchParams(window.location.search);
      const tr = params.get("team");
      const tid = tr ? Number(tr) : NaN;
      if (Number.isFinite(tid) && tid > 0) {
        window.dispatchEvent(new CustomEvent("netup-set-active-team", { detail: { teamId: tid } }));
      }
    };
    syncCoachTeamFromUrl();
    window.addEventListener("popstate", syncCoachTeamFromUrl);
    return () => window.removeEventListener("popstate", syncCoachTeamFromUrl);
  }, []);

  useEffect(() => {
    const syncSessionFromUrl = () => {
      const params = new URLSearchParams(window.location.search);
      const tr = params.get("team");
      const sr = params.get("session");
      if (!teamId || !tr || String(teamId) !== String(Number(tr))) {
        return;
      }
      const sid = sr ? Number(sr) : NaN;
      if (Number.isFinite(sid) && sid > 0) {
        setSelectedSessionId(sid);
      }
    };

    syncSessionFromUrl();
    window.addEventListener("popstate", syncSessionFromUrl);
    return () => window.removeEventListener("popstate", syncSessionFromUrl);
  }, [teamId]);

  const loadAnalytics = useCallback(
    async (overrides) => {
      if (!teamId) {
        setAnalyticsPayload(null);
        return;
      }
      const startDate = overrides?.startDate ?? analyticsStart;
      const endDate = overrides?.endDate ?? analyticsEnd;
      const grouping = overrides?.grouping ?? analyticsGrouping;
      const rawLast = overrides?.lastNSessions ?? analyticsLastN;
      setAnalyticsLoading(true);
      setAnalyticsError("");
      try {
        const data = await fetchTeamAttendanceAnalytics(teamId, {
          startDate,
          endDate,
          grouping,
          lastNSessions: String(rawLast || "").trim() || undefined,
        });
        setAnalyticsPayload(data);
      } catch (err) {
        setAnalyticsPayload(null);
        setAnalyticsError(err.message || "Could not load attendance analytics.");
      } finally {
        setAnalyticsLoading(false);
      }
    },
    [teamId, analyticsStart, analyticsEnd, analyticsGrouping, analyticsLastN],
  );

  useEffect(() => {
    if (!teamId || !analyticsExpanded) {
      return;
    }
    // Load the default analytics when the panel is first expanded for this team.
    // We intentionally avoid depending on `loadAnalytics` here so updates to the
    // filter inputs (which change `loadAnalytics` identity) do not re-run this
    // effect and reset the view to defaults while the user is editing filters.
    void loadAnalytics({
      startDate: defaultRange.start,
      endDate: defaultRange.end,
      grouping: "week",
      lastNSessions: "",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [teamId, analyticsExpanded, defaultRange.start, defaultRange.end]);

  const loadDetail = useCallback(async (sessionId) => {
    setDetailLoading(true);
    setDetailError("");
    try {
      const data = await fetchCoachTrainingSessionAttendance(sessionId, teamId);
      setDetailPayload(data);
    } catch (err) {
      setDetailPayload(null);
      setDetailError(err.message || "Could not load attendance.");
    } finally {
      setDetailLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    if (!selectedSessionId) {
      setDetailPayload(null);
      setMatchPayload(null);
      return;
    }
    setRemindMessage("");
    setRemindError("");
    setCancelMessage("");
    setCancelError("");
    setEndMatchError("");
    setEndMatchMessage("");
    void loadDetail(selectedSessionId);
  }, [selectedSessionId, loadDetail]);

  const loadMatchDetail = useCallback(async (matchId) => {
    if (!matchId) {
      setMatchPayload(null);
      return;
    }
    setMatchLoading(true);
    setMatchError("");
    try {
      const data = await fetchMatch(matchId, teamId);
      setMatchPayload(data);
    } catch (err) {
      setMatchPayload(null);
      setMatchError(err.message || "Could not load match stats.");
    } finally {
      setMatchLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    if (detailPayload?.session?.session_type !== "match") {
      setMatchPayload(null);
      setExpandedMatchPlayerId(null);
      setOpponentFinalScoreInput("");
      return;
    }
    void loadMatchDetail(detailPayload.session.id);
  }, [detailPayload, loadMatchDetail]);

  useEffect(() => {
    const score = matchPayload?.match?.summary?.final_score?.opponent_score;
    setOpponentFinalScoreInput(score == null ? "" : String(score));
  }, [matchPayload?.match?.id, matchPayload?.match?.summary?.final_score?.opponent_score]);

  const canManageTraining = Boolean(listPayload?.can_manage_training);

  const filteredOpponentTeams = useMemo(() => {
    const q = opponentSearch.trim().toLowerCase();
    return opponentTeams
      .filter((team) => Number(team.id) !== Number(teamId))
      .filter((team) => {
        if (!q) return true;
        return `${team.name || ""} ${team.club_name || team.clubName || ""}`.toLowerCase().includes(q);
      })
      .slice(0, 8);
  }, [opponentTeams, opponentSearch, teamId]);

  const selectedOpponentTeam = useMemo(
    () => opponentTeams.find((team) => Number(team.id) === Number(selectedOpponentTeamId)) || null,
    [opponentTeams, selectedOpponentTeamId],
  );

  const onCreateEvent = useCallback(async () => {
    if (!teamId) return;
    if (newEventType === "training" && !newSessionTitle.trim()) {
      setCreateSessionError("Enter the type of training.");
      if (titleInputRef.current && typeof titleInputRef.current.focus === "function") {
        titleInputRef.current.focus();
      }
      return;
    }
    if (!newSessionLocation.trim()) {
      setCreateSessionError("Enter a location.");
      if (locationInputRef.current && typeof locationInputRef.current.focus === "function") {
        locationInputRef.current.focus();
      }
      return;
    }
    if (newEventType === "game" && !useExternalOpponent && !selectedOpponentTeamId) {
      setCreateSessionError("Choose an opponent team or select Other.");
      return;
    }
    if (newEventType === "game" && useExternalOpponent && !externalOpponentName.trim()) {
      setCreateSessionError("Enter the external opponent name.");
      return;
    }

    setCreateSessionBusy(true);
    setCreateSessionError("");
    setCreateSessionSuccess("");
    try {
      const startT = newSessionStart.length > 5 ? newSessionStart.slice(0, 5) : newSessionStart;
      const endT = newSessionEnd.length > 5 ? newSessionEnd.slice(0, 5) : newSessionEnd;

      if (newEventType === "game") {
        const data = await createMatch({
          team_id: teamId,
          scheduled_date: newSessionDate,
          start_time: startT,
          end_time: endT,
          location: newSessionLocation.trim(),
          opponent_team_id: useExternalOpponent ? null : selectedOpponentTeamId,
          external_opponent: useExternalOpponent ? externalOpponentName.trim() : "",
          notify_players: newSessionNotifyPlayers,
          notify_parents: newSessionNotifyParents,
        });
        const match = data?.match;
        setCreateSessionSuccess(data?.message || "Game added.");
        setOpponentSearch("");
        setSelectedOpponentTeamId("");
        setUseExternalOpponent(false);
        setExternalOpponentName("");
        if (match?.id) {
          setSelectedSessionId(match.id);
          setMatchPayload(data);
        }
      } else {
        const data = await createTeamTrainingSession(teamId, {
          title: newEventType === "fundraiser" ? "Fundraiser" : newSessionTitle.trim(),
          session_type: "training",
          scheduled_date: newSessionDate,
          start_time: startT,
          end_time: endT,
          location: newSessionLocation.trim(),
          notify_players: newSessionNotifyPlayers,
          notify_parents: newSessionNotifyParents,
        });
        setCreateSessionSuccess(
          newEventType === "fundraiser"
            ? "Fundraiser added. Check notify options if families should get an in-app alert."
            : "Training added. Check notify options if families should get an in-app alert.",
        );
        setNewSessionTitle("");
        if (data?.session) {
          setListPayload((current) => {
            const currentSessions = current?.sessions || [];
            const nextSessions = [
              data.session,
              ...currentSessions.filter((session) => Number(session.id) !== Number(data.session.id)),
            ];
            return {
              ...(current || {}),
              team: current?.team || null,
              can_manage_training: current?.can_manage_training ?? true,
              sessions: nextSessions,
            };
          });
          setSelectedSessionId(data.session.id);
        }
      }

      setNewSessionLocation("");
      try {
        window.dispatchEvent(new Event("netup-schedule-changed"));
      } catch (e) {
        // ignore if dispatch fails in some environments
      }
      await loadList();
    } catch (err) {
      setCreateSessionError(err.message || "Could not create event.");
    } finally {
      setCreateSessionBusy(false);
    }
  }, [
    teamId,
    newEventType,
    newSessionTitle,
    newSessionDate,
    newSessionStart,
    newSessionEnd,
    newSessionLocation,
    newSessionNotifyPlayers,
    newSessionNotifyParents,
    useExternalOpponent,
    selectedOpponentTeamId,
    externalOpponentName,
    loadList,
  ]);

  const sendAttendanceReminder = useCallback(
    async (audience) => {
      const sess = detailPayload?.session;
      if (!teamId || !sess || sess.status === "cancelled") {
        return;
      }
      setRemindBusy(true);
      setRemindError("");
      setRemindMessage("");
      try {
        const res = await remindUnconfirmedTrainingSession(sess.id, audience, teamId);
        const n = res.recipient_count ?? 0;
        const np = res.player_recipient_count ?? 0;
        const npar = res.parent_recipient_count ?? 0;
        if (n === 0) {
          setRemindMessage(res.message || "No matching recipients.");
        } else {
          const parts = [];
          if (np) parts.push(`${np} player${np === 1 ? "" : "s"}`);
          if (npar) parts.push(`${npar} parent${npar === 1 ? "" : "s"}`);
          setRemindMessage(`Sent to ${parts.join(" and ")} (${n} notification${n === 1 ? "" : "s"}).`);
        }
      } catch (err) {
        setRemindError(err.message || "Could not send reminder.");
      } finally {
        setRemindBusy(false);
      }
    },
    [teamId, detailPayload],
  );

  const onCancelSession = useCallback(async () => {
    const sess = detailPayload?.session;
    if (!teamId || !sess || sess.status === "cancelled" || sessionHasStarted(sess)) {
      return;
    }
    setCancelBusy(true);
    setCancelMessage("");
    setCancelError("");
    try {
      await cancelTrainingSession(sess.id);
      setCancelMessage("Session cancelled. It will no longer appear on the weekly schedule.");
      try {
        window.dispatchEvent(new Event("netup-schedule-changed"));
      } catch (e) {
        // ignore if dispatch fails in some environments
      }
      await loadList();
      await loadDetail(sess.id);
      if (analyticsExpanded) {
        await loadAnalytics();
      }
    } catch (err) {
      setCancelError(err.message || "Could not cancel session.");
    } finally {
      setCancelBusy(false);
    }
  }, [teamId, detailPayload, loadList, loadDetail, analyticsExpanded, loadAnalytics]);

  const onEndMatch = useCallback(async () => {
    const match = matchPayload?.match;
    const sess = detailPayload?.session;
    if (!teamId || !match?.id || !sess || !match.can_end_match) {
      return;
    }

    const payload = {};
    if (!match.is_shared_match) {
      const trimmedScore = String(opponentFinalScoreInput || "").trim();
      if (!trimmedScore) {
        setEndMatchError("Enter the opponent's final score before ending the match.");
        return;
      }
      payload.opponent_final_score = trimmedScore;
    }

    setEndMatchBusy(true);
    setEndMatchError("");
    setEndMatchMessage("");
    try {
      const data = await endMatch(match.id, payload, teamId);
      setMatchPayload(data);
      setEndMatchMessage(data?.message || "Match ended.");
      try {
        window.dispatchEvent(new Event("netup-standings-changed"));
      } catch (e) {
        // ignore if dispatch fails in some environments
      }
      await loadList();
      await loadDetail(sess.id);
    } catch (err) {
      setEndMatchError(err.message || "Could not end the match.");
    } finally {
      setEndMatchBusy(false);
    }
  }, [teamId, detailPayload, matchPayload, opponentFinalScoreInput, loadList, loadDetail]);

  const onResumeMatch = useCallback(async () => {
    const match = matchPayload?.match;
    const sess = detailPayload?.session;
    if (!teamId || !match?.id || !sess || !match.can_resume_match) {
      return;
    }
    setEndMatchBusy(true);
    setEndMatchError("");
    setEndMatchMessage("");
    try {
      const data = await resumeMatch(match.id, teamId);
      setMatchPayload(data);
      setEndMatchMessage(data?.message || "Match resumed.");
      try {
        window.dispatchEvent(new Event("netup-standings-changed"));
      } catch (e) {
        // ignore if dispatch fails in some environments
      }
      await loadList();
      await loadDetail(sess.id);
    } catch (err) {
      setEndMatchError(err.message || "Could not resume the match.");
    } finally {
      setEndMatchBusy(false);
    }
  }, [teamId, detailPayload, matchPayload, loadList, loadDetail]);

  const schedulePlayerStatSave = useCallback((playerId, nextStats) => {
    const matchId = detailPayload?.session?.id;
    if (!matchId || !playerId) return;
    if (statsSaveTimersRef.current[playerId]) {
      clearTimeout(statsSaveTimersRef.current[playerId]);
    }
    statsSaveTimersRef.current[playerId] = setTimeout(async () => {
      setSavingStatsByPlayerId((prev) => ({ ...prev, [playerId]: true }));
      setStatsSaveError("");
      try {
        const data = await updateMatchPlayerStats(matchId, playerId, nextStats, teamId);
        setMatchPayload(data);
      } catch (err) {
        setStatsSaveError(err.message || "Could not auto-save player stats.");
      } finally {
        setSavingStatsByPlayerId((prev) => ({ ...prev, [playerId]: false }));
      }
    }, 450);
  }, [detailPayload, teamId]);

  const onChangePlayerStat = useCallback((playerId, field, value) => {
    const normalizedValue = normalizeStatValue(value);
    const currentPlayer = matchPayload?.match?.players?.find(
      (player) => Number(player.player_id) === Number(playerId),
    );
    if (!currentPlayer) {
      return;
    }
    const nextStats = {
      ...(currentPlayer.stats || {}),
      [field]: normalizedValue,
    };

    setMatchPayload((prev) => {
      if (!prev?.match) return prev;
      const players = (prev.match.players || []).map((player) => {
        if (Number(player.player_id) !== Number(playerId)) return player;
        return {
          ...player,
          stats: nextStats,
          weighted_score: Math.round(clientMatchWeightedScore(nextStats) * 100) / 100,
        };
      });
      const totalTeamPoints = players.reduce((sum, player) => sum + normalizeStatValue(player.stats?.points_scored), 0);
      const scoredPlayers = players.map((player) => {
        const stats = player.stats || {};
        const weightedScore =
          normalizeStatValue(stats.points_scored) +
          normalizeStatValue(stats.aces) * 2 +
          normalizeStatValue(stats.blocks) * 2 +
          normalizeStatValue(stats.assists) * 1.5 +
          normalizeStatValue(stats.digs) -
          normalizeStatValue(stats.errors);
        return { player, weightedScore };
      });
      const hasRecordedStats = players.some((player) =>
        MATCH_STAT_FIELDS.some((field) => normalizeStatValue(player.stats?.[field.key]) > 0),
      );
      const mvp = scoredPlayers.reduce((best, row) => (!best || row.weightedScore > best.weightedScore ? row : best), null);
      return {
        ...prev,
        match: {
          ...prev.match,
          summary: {
            ...(prev.match.summary || {}),
            total_team_points: totalTeamPoints,
            mvp_suggestion: hasRecordedStats && mvp
              ? {
                  player_id: mvp.player.player_id,
                  player_name: mvp.player.player_name,
                  weighted_score: Math.round(mvp.weightedScore * 100) / 100,
                }
              : null,
          },
          players,
        },
      };
    });
    schedulePlayerStatSave(playerId, nextStats);
  }, [matchPayload, schedulePlayerStatSave]);

  const today = useMemo(() => {
    const t = new Date();
    return new Date(t.getFullYear(), t.getMonth(), t.getDate());
  }, []);

  // custom grouping dropdown state
  const [groupOpen, setGroupOpen] = useState(false);
  const groupSelectRef = useRef(null);

  useEffect(() => {
    function onDocClick(e) {
      if (!groupSelectRef.current) return;
      if (!groupSelectRef.current.contains(e.target)) {
        setGroupOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const sortedSessions = useMemo(() => {
    const sessions = listPayload?.sessions || [];
    const filtered =
      sessionListFilter === "all"
        ? sessions
        : sessions.filter((session) => sessionCategoryValue(session) === sessionListFilter);
    const copy = [...filtered];
    const nowMs = Date.now();
    const byDate = (a, b) => {
      const bucketA = sessionSortBucket(a, nowMs);
      const bucketB = sessionSortBucket(b, nowMs);
      if (bucketA !== bucketB) {
        return bucketA - bucketB;
      }

      const startA = sessionDateTimeValue(a, "start_time", "00:00");
      const startB = sessionDateTimeValue(b, "start_time", "00:00");
      if (!Number.isFinite(startA) || !Number.isFinite(startB)) {
        return 0;
      }

      if (bucketA === 1) {
        return startA - startB;
      }
      return startB - startA;
    };
    copy.sort(byDate);
    return copy;
  }, [listPayload, sessionListFilter]);

  const activeSessionFilter = useMemo(
    () => SESSION_LIST_FILTER_OPTIONS.find((option) => option.value === sessionListFilter) || SESSION_LIST_FILTER_OPTIONS[0],
    [sessionListFilter],
  );

  if (!teamId) {
    return (
      <section className="teams-page-shell">
        <header className="teams-page-header">
          <div className="teams-page-heading">
            <p className="teams-page-kicker">Coaching</p>
            <h1>Session attendance</h1>
            <p className="teams-page-subtitle">Pick a team you coach in the toolbar to load practices and matches.</p>
          </div>
        </header>
        <section className="schedule-empty-card">
          <h2>No team selected</h2>
          <p>Coaches and directors with training access should choose a team first.</p>
        </section>
      </section>
    );
  }

  if (listLoading) {
    return (
      <section className="teams-page-shell" style={{ paddingTop: "1rem" }}>
        <p className="vc-modal__muted">Loading sessions…</p>
      </section>
    );
  }

  if (listError) {
    return (
      <section className="teams-page-shell" style={{ paddingTop: "1rem" }}>
        <p className="schedule-feedback schedule-feedback--error">{listError}</p>
      </section>
    );
  }

  const detailSession = detailPayload?.session;
  const detailMatch = matchPayload?.match;
  const detailMatchSummary = detailMatch?.summary?.final_score || null;
  const canCancelDetailSession =
    Boolean(canManageTraining && detailSession && detailSession.status !== "cancelled" && !sessionHasStarted(detailSession));

  return (
    <section className="teams-page-shell">
      <header className="teams-page-header">
        <div className="teams-page-heading">
          <p className="teams-page-kicker">Coaching</p>
          <h1>Session attendance</h1>
          <p className="teams-page-subtitle">
            Plan practices and matches for <strong>{listPayload?.team?.name || activeTeam?.name}</strong>. Schedule a
            session below so players and parents can confirm from their apps; open a session to review the roster and
            send reminders.
          </p>
        </div>
      </header>

      {canManageTraining ? (
        <section
          className="vc-coach-analytics-panel"
          style={{
            marginBottom: "1.25rem",
            padding: "1.1rem 1.25rem",
            borderRadius: "12px",
            border: "1px solid #e4e7ec",
            background: "#fff",
          }}
          aria-labelledby="coach-add-session-heading"
        >
          <h2 id="coach-add-session-heading" style={{ fontSize: "1.05rem", margin: "0 0 0.5rem" }}>
            Schedule a new event
          </h2>
          <p className="vc-modal__muted" style={{ margin: "0 0 1rem", fontSize: "0.88rem", lineHeight: 1.5 }}>
            Create training, fundraiser, or game events on the team calendar and optionally notify roster players and
            linked parents.
          </p>
          {createSessionSuccess ? (
            <p className="vc-director-success" style={{ marginBottom: "0.65rem" }}>
              {createSessionSuccess}
            </p>
          ) : null}
          {createSessionError ? (
            <p className="schedule-feedback schedule-feedback--error" style={{ marginBottom: "0.65rem" }}>
              {createSessionError}
            </p>
          ) : null}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: "0.65rem",
              alignItems: "end",
            }}
          >
            <label className="match-form-field">
              <span className="vc-modal__muted">Event Type</span>
              <InlineDropdown
                ariaLabel="Event Type"
                className="vc-inline-dropdown--event-type"
                options={EVENT_TYPE_OPTIONS}
                value={newEventType}
                onChange={(value) => {
                  setNewEventType(value);
                  setCreateSessionError("");
                  setCreateSessionSuccess("");
                }}
              />
            </label>
            {newEventType === "training" ? (
              <label className="match-form-field">
                <span className="vc-modal__muted">Training Type</span>
                <input
                  ref={titleInputRef}
                  className="vc-dash-team-select"
                  value={newSessionTitle}
                  onChange={(e) => setNewSessionTitle(e.target.value)}
                  placeholder="e.g. Conditioning"
                />
              </label>
            ) : null}
            <label className="match-form-field">
              <span className="vc-modal__muted">Date</span>
              <input
                type="date"
                className="vc-dash-team-select"
                value={newSessionDate}
                onChange={(e) => setNewSessionDate(e.target.value)}
              />
            </label>
            <label className="match-form-field">
              <span className="vc-modal__muted">Start</span>
              <TimeSelect
                className="vc-dash-team-select"
                value={newSessionStart}
                onChange={setNewSessionStart}
              />
            </label>
            <label className="match-form-field">
              <span className="vc-modal__muted">End</span>
              <TimeSelect
                className="vc-dash-team-select"
                value={newSessionEnd}
                onChange={setNewSessionEnd}
              />
            </label>
            <label className="match-form-field">
              <span className="vc-modal__muted">Location</span>
              <input
                ref={locationInputRef}
                className="vc-dash-team-select"
                required
                value={newSessionLocation}
                onChange={(e) => setNewSessionLocation(e.target.value)}
                placeholder="Main gym"
              />
            </label>
            {newEventType === "game" ? (
              <div className="match-form-field match-form-field--wide">
                <span className="vc-modal__muted">Versus</span>
                <GameOpponentDropdown
                  teams={filteredOpponentTeams}
                  searchValue={opponentSearch}
                  onSearchChange={setOpponentSearch}
                  selectedTeam={selectedOpponentTeam}
                  selectedTeamId={selectedOpponentTeamId}
                  onSelectTeam={(team) => {
                    setUseExternalOpponent(false);
                    setExternalOpponentName("");
                    setSelectedOpponentTeamId(team.id);
                    setOpponentSearch(team.name || "");
                  }}
                  useExternalOpponent={useExternalOpponent}
                  externalOpponentName={externalOpponentName}
                  onUseExternalOpponent={() => {
                    setUseExternalOpponent(true);
                    setSelectedOpponentTeamId("");
                    setOpponentSearch("");
                  }}
                />
                {useExternalOpponent ? (
                  <input
                    className="vc-dash-team-select match-opponent-dropdown__external-input"
                    value={externalOpponentName}
                    onChange={(event) => setExternalOpponentName(event.target.value)}
                    placeholder="External team name"
                  />
                ) : null}
              </div>
            ) : null}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", marginTop: "0.75rem", alignItems: "center" }}>
            <label className="session-toggle" style={{ fontSize: "0.88rem" }}>
              <input
                type="checkbox"
                checked={newSessionNotifyPlayers}
                onChange={(e) => setNewSessionNotifyPlayers(e.target.checked)}
              />
              <span className="vc-switch__track"><span className="vc-switch__thumb" /></span>
              <span>Notify players</span>
            </label>

            <label className="session-toggle" style={{ fontSize: "0.88rem" }}>
              <input
                type="checkbox"
                checked={newSessionNotifyParents}
                onChange={(e) => setNewSessionNotifyParents(e.target.checked)}
              />
              <span className="vc-switch__track"><span className="vc-switch__thumb" /></span>
              <span>Notify parents</span>
            </label>
          </div>
          <div style={{ marginTop: "0.85rem" }}>
            <button
              type="button"
              className="vc-action-btn"
              disabled={createSessionBusy}
              onClick={() => void onCreateEvent()}
            >
              {createSessionBusy ? "Saving…" : "Add event"}
            </button>
          </div>
        </section>
      ) : null}

      {!analyticsExpanded ? (
        <div style={{ marginBottom: "1.25rem" }}>
          <button type="button" className="vc-action-btn" onClick={() => setAnalyticsExpanded(true)}>
            Show attendance trends &amp; player analytics
          </button>
        </div>
      ) : (
        <div style={{ marginBottom: "0.65rem" }}>
          <button
            type="button"
            className="vc-link-cyan"
            style={{ fontSize: "0.88rem", padding: 0, border: "none", background: "none", cursor: "pointer" }}
            onClick={() => setAnalyticsExpanded(false)}
          >
            Hide attendance trends
          </button>
        </div>
      )}

      {analyticsExpanded ? (
      <section
        className="vc-coach-analytics-panel"
        style={{
          marginBottom: "1.75rem",
          padding: "1.25rem 1.35rem",
          borderRadius: "12px",
          border: "1px solid #e4e7ec",
          background: "#fbfcfe",
        }}
        aria-labelledby="coach-analytics-heading"
      >
        <h2 id="coach-analytics-heading" style={{ fontSize: "1.08rem", margin: "0 0 0.75rem" }}>
          Attendance trends &amp; engagement
        </h2>
        <p className="vc-modal__muted" style={{ margin: "0 0 1rem", lineHeight: 1.55, fontSize: "0.9rem" }}>
          <span style={{ color: "#374151" }}>
            {analyticsPayload?.calculation_summary ||
              "Load analytics to see how attendance percentages are calculated for this team."}
          </span>
        </p>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "0.65rem",
            alignItems: "flex-end",
            marginBottom: "1rem",
          }}
        >
          <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.82rem" }}>
            <span className="vc-modal__muted">Start</span>
            <input
              type="date"
              className="vc-input"
              value={analyticsStart}
              onChange={(e) => setAnalyticsStart(e.target.value)}
              style={{ padding: "0.45rem 0.5rem", borderRadius: "8px", border: "1px solid #d0d5dd" }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.82rem" }}>
            <span className="vc-modal__muted">End</span>
            <input
              type="date"
              className="vc-input"
              value={analyticsEnd}
              onChange={(e) => setAnalyticsEnd(e.target.value)}
              style={{ padding: "0.45rem 0.5rem", borderRadius: "8px", border: "1px solid #d0d5dd" }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.82rem" }}>
            <span className="vc-modal__muted">Group trend by</span>
            <div
              className="vc-fake-select"
              ref={groupSelectRef}
            >
              <button
                type="button"
                className="vc-fake-select__btn"
                aria-haspopup="listbox"
                aria-expanded={groupOpen}
                onClick={() => setGroupOpen((v) => !v)}
              >
                {analyticsGrouping === "week" ? "Week" : "Session"}
                <span className="vc-fake-select__caret" aria-hidden>▾</span>
              </button>
              {groupOpen ? (
                <ul className="vc-fake-select__menu" role="listbox" tabIndex={-1}>
                  <li
                    role="option"
                    className="vc-fake-select__item"
                    onClick={() => {
                      setAnalyticsGrouping("week");
                      setGroupOpen(false);
                    }}
                  >
                    Week
                  </li>
                  <li
                    role="option"
                    className="vc-fake-select__item"
                    onClick={() => {
                      setAnalyticsGrouping("session");
                      setGroupOpen(false);
                    }}
                  >
                    Session
                  </li>
                </ul>
              ) : null}
            </div>
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.82rem" }}>
            <span className="vc-modal__muted">Last N closed sessions (optional)</span>
            <input
              type="number"
              min={1}
              placeholder="e.g. 8"
              value={analyticsLastN}
              onChange={(e) => setAnalyticsLastN(e.target.value)}
              style={{ padding: "0.45rem 0.5rem", borderRadius: "8px", border: "1px solid #d0d5dd", width: "7rem" }}
            />
          </label>
          <button
            type="button"
            className="vc-action-btn vc-action-btn--sm"
            onClick={() => void loadAnalytics()}
            disabled={analyticsLoading}
          >
            <span>{analyticsLoading ? "Refreshing…" : "Apply filters"}</span>
          </button>
        </div>
        {analyticsLoading && !analyticsPayload ? (
          <p className="vc-modal__muted">Loading analytics…</p>
        ) : null}
        {analyticsError ? <p className="schedule-feedback schedule-feedback--error">{analyticsError}</p> : null}
        {analyticsPayload && !analyticsError ? (
          <>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                gap: "0.75rem",
                marginBottom: "1.1rem",
              }}
            >
              <div style={{ padding: "0.75rem 1rem", background: "#fff", borderRadius: "10px", border: "1px solid #e4e7ec" }}>
                <div className="vc-modal__muted" style={{ fontSize: "0.78rem" }}>
                  Team avg (closed sessions)
                </div>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, marginTop: "0.2rem" }}>
                  {analyticsPayload.team_average_attendance_rate_percent != null
                    ? `${analyticsPayload.team_average_attendance_rate_percent}%`
                    : "—"}
                </div>
              </div>
              <div style={{ padding: "0.75rem 1rem", background: "#fff", borderRadius: "10px", border: "1px solid #e4e7ec" }}>
                <div className="vc-modal__muted" style={{ fontSize: "0.78rem" }}>
                  Closed sessions in scope
                </div>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, marginTop: "0.2rem" }}>
                  {analyticsPayload.closed_sessions_in_scope ?? 0}
                </div>
              </div>
              <div style={{ padding: "0.75rem 1rem", background: "#fff", borderRadius: "10px", border: "1px solid #e4e7ec" }}>
                <div className="vc-modal__muted" style={{ fontSize: "0.78rem" }}>
                  Roster players
                </div>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, marginTop: "0.2rem" }}>
                  {analyticsPayload.roster_player_count ?? 0}
                </div>
              </div>
            </div>
            {analyticsPayload.closed_sessions_in_scope === 0 ? (
              <section className="schedule-empty-card" style={{ marginBottom: "1rem" }}>
                <h3 style={{ marginTop: 0 }}>No completed sessions in this range</h3>
                <p style={{ marginBottom: 0 }}>
                  Adjust the dates or wait until sessions move into the past to see attendance rates. Upcoming sessions
                  still appear in the per-player pending counts when applicable.
                </p>
              </section>
            ) : null}
            {analyticsPayload.trend?.length ? (
              <div style={{ marginBottom: "1.15rem" }}>
                <h3 style={{ fontSize: "0.98rem", margin: "0 0 0.5rem" }}>Team trend</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                  {analyticsPayload.trend.map((row) => (
                    <div key={row.period_key} style={{ display: "flex", alignItems: "center", gap: "0.65rem" }}>
                      <span style={{ width: "8.5rem", flexShrink: 0, fontSize: "0.82rem" }} className="vc-modal__muted">
                        {row.label}
                      </span>
                      <div style={{ flex: 1, height: "10px", background: "#eef2f6", borderRadius: "6px", overflow: "hidden" }}>
                        <div
                          style={{
                            width: `${row.attendance_rate_percent != null ? row.attendance_rate_percent : 0}%`,
                            height: "100%",
                            background: "linear-gradient(90deg, #0d9488, #2563eb)",
                            borderRadius: "6px",
                          }}
                        />
                      </div>
                      <span style={{ width: "3.5rem", textAlign: "right", fontSize: "0.82rem", fontWeight: 700 }}>
                        {row.attendance_rate_percent != null ? `${row.attendance_rate_percent}%` : "—"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {analyticsPayload.players?.length ? (
              <div style={{ overflowX: "auto" }}>
                <table className="vc-table" style={{ fontSize: "0.88rem", width: "100%" }}>
                  <thead>
                    <tr>
                      <th>Player</th>
                      <th>Sessions (range)</th>
                      <th>Counted for %</th>
                      <th>Attended</th>
                      <th>Absent</th>
                      <th>Pending</th>
                      <th>Rate</th>
                      <th>Engagement</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analyticsPayload.players.map((row) => (
                      <tr key={row.player_id}>
                        <td>{row.player_name}</td>
                        <td>{row.sessions_in_date_range}</td>
                        <td>{row.sessions_counted_for_rate}</td>
                        <td>{row.attended_sessions}</td>
                        <td>{row.absent_sessions}</td>
                        <td>{row.pending_sessions}</td>
                        <td>{row.attendance_rate_percent != null ? `${row.attendance_rate_percent}%` : "—"}</td>
                        <td>
                          <span className={engagementBadgeClass(row.engagement_flag)}>
                            {engagementLabel(row.engagement_flag)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="vc-modal__muted">No players on this roster.</p>
            )}
          </>
        ) : null}
      </section>
      ) : null}

      <div className="coach-attendance-layout">
        <div
          className={`team-training-panel team-training-panel--session-list${
            selectedSessionId ? " has-session-selected" : " has-no-session-selected"
          }`}
          ref={sessionListPanelRef}
        >
          <div className="team-training-panel__header">
            <div>
              <h2 style={{ fontSize: "1.05rem", margin: 0 }}>Sessions</h2>
              <p className="team-training-panel__subhead">
                Showing {sortedSessions.length} of {listPayload?.sessions?.length || 0}
              </p>
            </div>
            <InlineDropdown
              value={sessionListFilter}
              onChange={setSessionListFilter}
              options={SESSION_LIST_FILTER_OPTIONS}
              ariaLabel="Filter sessions by category"
              className="vc-inline-dropdown--session-filter"
            />
          </div>
          {sortedSessions.length ? (
            <div className="training-session-list">
              {sortedSessions.map((session) => {
                const d = parseLocalDate(session.scheduled_date);
                const isPast = d && d < today;
                const active = Number(selectedSessionId) === Number(session.id);
                return (
                  <article
                    key={session.id}
                    className={`training-session-card${active ? " training-session-card--active" : ""}`}
                  >
                    <button
                      type="button"
                      onClick={() => handleSelectSession(session.id)}
                      className="coach-session-select-btn"
                      style={{
                        width: "100%",
                        textAlign: "left",
                        background: "transparent",
                        border: "none",
                        padding: 0,
                        cursor: "pointer",
                        font: "inherit",
                        color: "inherit",
                      }}
                    >
                      <div className="training-session-card__top">
                        <div>
                          <div className="training-session-card__meta">
                            <span className={sessionCategoryBadgeClass(session)}>{sessionCategoryLabel(session)}</span>
                            {session.status === "cancelled" ? (
                              <span className="training-status-badge training-status-badge--cancelled">Cancelled</span>
                            ) : session.session_type === "match" && session.is_ended ? (
                              <span className="training-status-badge training-status-badge--ended">Ended</span>
                            ) : isPast ? (
                              <span className="vc-modal__muted" style={{ fontSize: "0.78rem" }}>
                                Past
                              </span>
                            ) : null}
                          </div>
                          <h3 style={{ margin: "0.35rem 0 0.25rem" }}>{session.title}</h3>
                          <p className="training-session-card__location">
                            {session.scheduled_date} · {formatTimeRange12h(session.start_time, session.end_time)}
                            {session.location ? ` · ${session.location}` : ""}
                          </p>
                          {session.session_type === "match" && session.opponent ? (
                            <p className="training-session-card__match-meta">vs {session.opponent}</p>
                          ) : null}
                          {session.session_type === "match" && session.match_request_status !== "none" ? (
                            <p className="vc-modal__muted" style={{ fontSize: "0.8rem", marginTop: "0.3rem" }}>
                              {session.match_request_status_label}
                            </p>
                          ) : null}
                          <p className="vc-modal__muted" style={{ fontSize: "0.82rem", marginTop: "0.35rem" }}>
                            Confirmed {session.confirmed_count ?? 0} · Pending {session.pending_count ?? 0}
                          </p>
                        </div>
                      </div>
                    </button>
                  </article>
                );
              })}
            </div>
          ) : (
            <section className="training-empty-state">
              <h3>{sessionListFilter === "all" ? "No sessions yet" : `No ${activeSessionFilter.label.toLowerCase()} sessions`}</h3>
              <p>
                {sessionListFilter === "all"
                  ? "When sessions are scheduled for this team, they will appear here."
                  : "Try another filter or create a new event for this category."}
              </p>
            </section>
          )}
        </div>

        <div className="team-training-panel team-training-panel--session-detail" ref={sessionDetailPanelRef}>
          <div className="team-training-panel__header">
            <h2 style={{ fontSize: "1.05rem", margin: 0 }}>Roster &amp; status</h2>
          </div>
          {!selectedSessionId ? (
            <section className="schedule-empty-card" style={{ margin: 0 }}>
              <h3>Select a session</h3>
              <p>Choose a session on the left to load attendance for every roster player.</p>
            </section>
          ) : detailLoading ? (
            <p className="vc-modal__muted" style={{ padding: "0.5rem 0" }}>
              Loading attendance…
            </p>
          ) : detailError ? (
            <p className="schedule-feedback schedule-feedback--error">{detailError}</p>
          ) : detailSession ? (
            <div>
              <header style={{ marginBottom: "0.75rem" }}>
                <h3 style={{ fontSize: "1.1rem", margin: "0 0 0.25rem" }}>{detailSession.title}</h3>
                <p className="vc-modal__muted" style={{ margin: 0, lineHeight: 1.5 }}>
                  {detailSession.scheduled_date} · {formatTimeRange12h(detailSession.start_time, detailSession.end_time)}
                  {detailSession.location ? ` · ${detailSession.location}` : ""}
                  <br />
                  {detailSession.session_type_label}
                  {detailSession.session_type === "match" && detailSession.opponent ? ` · vs ${detailSession.opponent}` : ""}
                  {detailSession.session_type === "match" && detailSession.match_request_status !== "none" ? (
                    <>
                      <br />
                      <span style={{ color: "#4b5563" }}>{detailSession.match_request_status_label}</span>
                    </>
                  ) : null}
                  {detailSession.description ? (
                    <>
                      <br />
                      <span style={{ color: "#4b5563" }}>{detailSession.description}</span>
                    </>
                  ) : null}
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.65rem" }}>
                  <span className="vc-status-paid">Present {detailSession.summary?.present_count ?? 0}</span>
                  <span className="vc-status-pending">Pending {detailSession.summary?.pending_count ?? 0}</span>
                  <span className="vc-status-overdue">Absent {detailSession.summary?.absent_count ?? 0}</span>
                  {detailSession.session_type === "match" && detailMatch?.is_ended ? (
                    <span className="training-status-badge training-status-badge--ended">
                      Ended {formatDateTimeLabel(detailMatch.ended_at)}
                    </span>
                  ) : null}
                  {detailSession.summary?.cancelled_count ? (
                    <span className="vc-modal__muted">Cancelled {detailSession.summary.cancelled_count}</span>
                  ) : null}
                  <span className="vc-modal__muted">Roster {detailSession.summary?.roster_size ?? 0}</span>
                </div>
              </header>
              {detailSession.session_type === "match" ? (
                <section className="match-stats-panel" aria-labelledby="match-stats-heading">
                  <div className="match-stats-panel__head">
                    <div>
                      <h4 id="match-stats-heading">Match performance tracking</h4>
                      <p className="vc-modal__muted">
                        {detailMatch?.is_ended
                          ? "This match is closed. Resume it if you want to keep editing player stats."
                          : "Stats auto-save per player while the match is open. Record the final result once scores are complete."}
                      </p>
                    </div>
                    <div className="match-stats-summary">
                      <span>Total points: {detailMatch?.summary?.total_team_points ?? 0}</span>
                      <span>
                        MVP: {detailMatch?.summary?.mvp_suggestion?.player_name || "No stats yet"}
                      </span>
                      {(detailMatch?.summary?.team_totals || []).map((row) => (
                        <span key={row.team_id}>
                          {row.team_name}: {row.total_points}
                        </span>
                      ))}
                    </div>
                  </div>
                  {detailMatch ? (
                    <div className="match-stats-toolbar">
                      {detailMatch.is_shared_match && !detailMatch.is_ended ? (
                        <p className="vc-modal__muted" style={{ margin: 0 }}>
                          Shared match final score is calculated from both teams' recorded player stats.
                        </p>
                      ) : null}
                      {!detailMatch.is_shared_match && !detailMatch.is_ended ? (
                        <label className="match-stat-input match-stat-input--compact">
                          <span>Opponent final score</span>
                          <input
                            type="number"
                            min="0"
                            value={opponentFinalScoreInput}
                            onChange={(event) => setOpponentFinalScoreInput(event.target.value)}
                            disabled={endMatchBusy}
                            placeholder="0"
                          />
                        </label>
                      ) : null}
                      {detailMatch.can_end_match ? (
                        <button type="button" className="vc-action-btn" onClick={() => void onEndMatch()} disabled={endMatchBusy}>
                          {endMatchBusy ? "Saving result…" : "Record Result"}
                        </button>
                      ) : null}
                      {detailMatch.can_resume_match ? (
                        <button
                          type="button"
                          className="match-secondary-btn"
                          onClick={() => void onResumeMatch()}
                          disabled={endMatchBusy}
                        >
                          {endMatchBusy ? "Resuming…" : "Resume Match"}
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                  {detailMatch?.is_ended && detailMatchSummary ? (
                    <div className="match-final-summary">
                      <div className="match-final-summary__hero">
                        <div>
                          <p className="match-final-summary__eyebrow">Final score</p>
                          <h5>{detailMatchSummary.final_score_label}</h5>
                          <div className="match-final-summary__chips">
                            <span className={matchResultBadgeClass(detailMatchSummary.result)}>
                              {detailMatchSummary.result_label}
                            </span>
                            {detailMatch.ended_at ? (
                              <span className="vc-modal__muted">Closed {formatDateTimeLabel(detailMatch.ended_at)}</span>
                            ) : null}
                          </div>
                        </div>
                        <div className="match-score-rings" aria-hidden="true">
                          {(detailMatchSummary.score_rows || []).map((row) => {
                            const maxScore = Math.max(
                              ...((detailMatchSummary.score_rows || []).map((item) => Number(item.score) || 0)),
                              1,
                            );
                            const score = Number(row.score) || 0;
                            const fill = `${Math.max(14, Math.round((score / maxScore) * 100))}%`;
                            return (
                              <div key={`${row.team_id || row.team_name}-ring`} className="match-score-rings__item">
                                <div
                                  className={`match-score-rings__disc${
                                    row.is_context_team ? " match-score-rings__disc--context" : ""
                                  }`}
                                  style={{ "--match-ring-fill": fill }}
                                >
                                  <strong>{row.score ?? "?"}</strong>
                                </div>
                                <span>{row.team_name}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                      <div className="match-final-summary__cards">
                        <article className="match-summary-card">
                          <span>Winner</span>
                          <strong>
                            {detailMatchSummary.winner_name || "Waiting for final result"}
                          </strong>
                        </article>
                        <article className="match-summary-card">
                          <span>Match duration</span>
                          <strong>{detailMatchSummary.duration_label || "In progress"}</strong>
                        </article>
                        <article className="match-summary-card">
                          <span>Tournament</span>
                          <strong>{detailMatchSummary.tournament_label || "Friendly"}</strong>
                        </article>
                      </div>
                      <div className="match-score-bars">
                        {(detailMatchSummary.score_rows || []).map((row) => {
                          const maxScore = Math.max(
                            ...((detailMatchSummary.score_rows || []).map((item) => Number(item.score) || 0)),
                            1,
                          );
                          const score = Number(row.score) || 0;
                          return (
                            <div key={`${row.team_id || row.team_name}-bar`} className="match-score-bars__row">
                              <div className="match-score-bars__label">
                                <strong>{row.team_name}</strong>
                                <span>{row.score ?? "?"}</span>
                              </div>
                              <div className="match-score-bars__track">
                                <div
                                  className={`match-score-bars__fill${row.is_context_team ? " is-context" : ""}`}
                                  style={{ width: `${Math.max(8, Math.round((score / maxScore) * 100))}%` }}
                                />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}
                  {matchLoading && !matchPayload ? <p className="vc-modal__muted">Loading match stats…</p> : null}
                  {matchError ? <p className="schedule-feedback schedule-feedback--error">{matchError}</p> : null}
                  {endMatchMessage ? <p className="vc-director-success">{endMatchMessage}</p> : null}
                  {endMatchError ? <p className="schedule-feedback schedule-feedback--error">{endMatchError}</p> : null}
                  {statsSaveError ? <p className="schedule-feedback schedule-feedback--error">{statsSaveError}</p> : null}
                  {detailMatch?.players?.length ? (
                    <div className="match-player-stat-list">
                      {detailMatch.players.map((player) => {
                        const isOpen = Number(expandedMatchPlayerId) === Number(player.player_id);
                        const saving = Boolean(savingStatsByPlayerId[player.player_id]);
                        return (
                          <article key={player.player_id} className="match-player-stat-card">
                            <button
                              type="button"
                              className="match-player-stat-card__trigger"
                              onClick={() => setExpandedMatchPlayerId(isOpen ? null : player.player_id)}
                              aria-expanded={isOpen}
                            >
                              <span>
                                <strong>{player.player_name}</strong>
                                <small>
                                  {player.team_name}
                                  {" · "}
                                  {player.is_confirmed ? "Confirmed" : "Pending attendance"}
                                </small>
                              </span>
                              <span className="match-player-stat-card__score">
                                {saving ? "Saving…" : `Score ${player.weighted_score ?? 0}`}
                              </span>
                            </button>
                            {isOpen ? (
                              <div className="match-player-stat-card__body">
                                <div className="match-stat-grid">
                                  {MATCH_STAT_FIELDS.map((field) => (
                                    <label key={field.key} className="match-stat-input">
                                      <span>{field.label}</span>
                                      <input
                                        type="number"
                                        min="0"
                                        value={player.stats?.[field.key] ?? 0}
                                        disabled={!detailMatch.can_manage_stats}
                                        onChange={(e) => onChangePlayerStat(player.player_id, field.key, e.target.value)}
                                      />
                                    </label>
                                  ))}
                                </div>
                                <p className="vc-modal__muted">
                                  Last saved: {player.updated_at ? new Date(player.updated_at).toLocaleString() : "Not saved yet"}
                                  {player.updated_by_name ? ` by ${player.updated_by_name}` : ""}
                                </p>
                              </div>
                            ) : null}
                          </article>
                        );
                      })}
                    </div>
                  ) : !matchLoading ? (
                    <p className="vc-modal__muted">No roster players available for this match.</p>
                  ) : null}
                </section>
              ) : null}
              {canManageTraining && detailSession.status !== "cancelled" && detailSession.can_send_reminders !== false ? (
                <section
                  style={{
                    marginBottom: "1rem",
                    padding: "0.85rem 1rem",
                    borderRadius: "10px",
                    border: "1px solid #e0e7ff",
                    background: "#f8faff",
                  }}
                  aria-labelledby="coach-remind-attendance-heading"
                >
                  <h4 id="coach-remind-attendance-heading" style={{ margin: "0 0 0.35rem", fontSize: "0.95rem" }}>
                    Remind who still needs to confirm
                  </h4>
                  <p className="vc-modal__muted" style={{ margin: "0 0 0.65rem", fontSize: "0.82rem", lineHeight: 1.5 }}>
                    In-app notifications go only to roster players (and their linked parents when allowed) who have{" "}
                    <strong>not</strong> confirmed yet. Parents are not included for past practices or cancelled
                    sessions.
                  </p>
                  {typeof detailSession.unconfirmed_roster_count === "number" ? (
                    <p style={{ margin: "0 0 0.65rem", fontSize: "0.84rem", fontWeight: 600 }}>
                      {detailSession.unconfirmed_roster_count} player
                      {detailSession.unconfirmed_roster_count === 1 ? "" : "s"} without confirmation
                    </p>
                  ) : null}
                  {detailSession.remind_parents_allowed === false ? (
                    <p className="vc-modal__muted" style={{ margin: "0 0 0.65rem", fontSize: "0.82rem" }}>
                      This session is already over—only players without a confirmation can be nudged (not parents).
                    </p>
                  ) : null}
                  {remindMessage ? <p className="vc-director-success" style={{ marginBottom: "0.5rem" }}>{remindMessage}</p> : null}
                  {remindError ? (
                    <p className="schedule-feedback schedule-feedback--error" style={{ marginBottom: "0.5rem" }}>
                      {remindError}
                    </p>
                  ) : null}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.45rem" }}>
                    <button
                      type="button"
                      className="vc-action-btn"
                      style={{ fontSize: "0.85rem", padding: "0.4rem 0.75rem" }}
                      disabled={remindBusy}
                      onClick={() => void sendAttendanceReminder("players")}
                    >
                      {remindBusy ? "Sending…" : "Notify unconfirmed players"}
                    </button>
                    <button
                      type="button"
                      className="vc-action-btn"
                      style={{ fontSize: "0.85rem", padding: "0.4rem 0.75rem" }}
                      disabled={remindBusy || detailSession.remind_parents_allowed === false}
                      title={
                        detailSession.remind_parents_allowed === false
                          ? "Parents are not notified for past or cancelled practices"
                          : undefined
                      }
                      onClick={() => void sendAttendanceReminder("parents")}
                    >
                      {remindBusy ? "Sending…" : "Notify parents (unconfirmed only)"}
                    </button>
                    <button
                      type="button"
                      className="vc-action-btn"
                      style={{ fontSize: "0.85rem", padding: "0.4rem 0.75rem" }}
                      disabled={remindBusy}
                      onClick={() => void sendAttendanceReminder("all")}
                    >
                      {remindBusy
                        ? "Sending…"
                        : detailSession.remind_parents_allowed === false
                          ? "Notify unconfirmed players only"
                          : "Notify players & parents (unconfirmed)"}
                    </button>
                  </div>
                </section>
              ) : null}
              {canManageTraining ? (
                <section
                  style={{
                    marginBottom: "1rem",
                    padding: "0.85rem 1rem",
                    borderRadius: "10px",
                    border: "1px solid #f1d2d2",
                    background: "#fff5f5",
                  }}
                  aria-labelledby="coach-cancel-session-heading"
                >
                  <h4 id="coach-cancel-session-heading" style={{ margin: "0 0 0.35rem", fontSize: "0.95rem" }}>
                    Session status
                  </h4>
                  {detailSession.status === "cancelled" ? (
                    <p className="vc-modal__muted" style={{ margin: 0, fontSize: "0.84rem", lineHeight: 1.5 }}>
                      This session has been cancelled. It should no longer appear in the weekly schedule, and cancelled
                      sessions are excluded from attendance-rate calculations.
                    </p>
                  ) : canCancelDetailSession && detailSession.can_cancel !== false ? (
                    <>
                      <p className="vc-modal__muted" style={{ margin: "0 0 0.65rem", fontSize: "0.84rem", lineHeight: 1.5 }}>
                        This session has not started yet. You can cancel it here to remove it from the schedule and
                        mark it as cancelled in the sessions list.
                      </p>
                      {cancelMessage ? <p className="vc-director-success" style={{ marginBottom: "0.5rem" }}>{cancelMessage}</p> : null}
                      {cancelError ? (
                        <p className="schedule-feedback schedule-feedback--error" style={{ marginBottom: "0.5rem" }}>
                          {cancelError}
                        </p>
                      ) : null}
                      <button
                        type="button"
                        className="vc-action-btn"
                        style={{ background: "linear-gradient(135deg, #d44b4b, #b83232)" }}
                        disabled={cancelBusy}
                        onClick={() => void onCancelSession()}
                      >
                        {cancelBusy ? "Cancelling..." : "Cancel session"}
                      </button>
                    </>
                  ) : (
                    <p className="vc-modal__muted" style={{ margin: 0, fontSize: "0.84rem", lineHeight: 1.5 }}>
                      {detailSession.can_cancel === false
                        ? "Only the team that created this session can cancel it here."
                        : "Only sessions that have not started yet can be cancelled here."}
                    </p>
                  )}
                </section>
              ) : null}
              {detailSession.players?.length ? (
                <div style={{ overflowX: "auto" }}>
                  <table className="vc-table" style={{ fontSize: "0.9rem", width: "100%" }}>
                    <thead>
                      <tr>
                        <th>Player</th>
                        {detailSession.is_shared_match ? <th>Team</th> : null}
                        <th>#</th>
                        <th>Position</th>
                        <th>Status</th>
                        <th>Confirmed by</th>
                        <th>When</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detailSession.players.map((row) => (
                        <tr key={row.player_id}>
                          <td>{row.player_name}</td>
                          {detailSession.is_shared_match ? <td>{row.team_name}</td> : null}
                          <td>{row.jersey_number != null ? row.jersey_number : "—"}</td>
                          <td>{row.primary_position || "—"}</td>
                          <td>
                            <span className={statusBadgeClass(row.attendance_status)}>{row.attendance_label}</span>
                          </td>
                          <td>{row.confirmed_by_name || "—"}</td>
                          <td>{row.confirmed_at ? new Date(row.confirmed_at).toLocaleString() : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <section className="training-empty-state">
                  <h3>No players on roster</h3>
                  <p>Add players to this team to plan attendance.</p>
                </section>
              )}
            </div>
          ) : null}
        </div>
      </div>

    </section>
  );
}
