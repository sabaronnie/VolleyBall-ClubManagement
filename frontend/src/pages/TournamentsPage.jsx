import { useEffect, useMemo, useState } from "react";
import {
  createTournament,
  fetchClubTeams,
  fetchCurrentUser,
  fetchMyTournamentMatches,
  fetchTournamentBracket,
  fetchTournamentMatches,
  fetchTournamentStandings,
  fetchTournaments,
  generateTournamentBracket,
  generateTournamentPoolMatches,
  generateTournamentPools,
  rescheduleTournamentMatch,
  submitTournamentMatchResult,
} from "../api";

const TABS_DIRECTOR = ["setup", "overview", "pools", "bracket", "matches"];
const TABS_VIEWER = ["overview", "pools", "bracket", "matches"];

function formatTabLabel(tabId) {
  const labels = { setup: "Setup", overview: "Overview", pools: "Pools", bracket: "Bracket", matches: "Matches" };
  return labels[tabId] || tabId.charAt(0).toUpperCase() + tabId.slice(1);
}

/** Local date + time range (aligns with Schedule session start/end from the same source). */
function TournamentStartCell({ iso, endIso }) {
  if (!iso) {
    return "—";
  }
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) {
    return "—";
  }
  const dateStr = d.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  const opt = { hour: "numeric", minute: "2-digit" };
  const timeStr = d.toLocaleTimeString(undefined, opt);
  let timeLine = timeStr;
  if (endIso) {
    const e = new Date(endIso);
    if (Number.isFinite(e.getTime())) {
      timeLine = `${timeStr} – ${e.toLocaleTimeString(undefined, opt)}`;
    }
  }
  return (
    <span className="tournament-time-cell">
      <span className="tournament-time-cell__date">{dateStr}</span>
      <span className="tournament-time-cell__time">{timeLine}</span>
    </span>
  );
}

function isoToDatetimeLocalValue(iso) {
  if (!iso) {
    return "";
  }
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) {
    return "";
  }
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Date + time range for Bracket / Matches cards; matches Schedule when API sends scheduled_end_time. */
function formatBracketWhenWhereLine(match, tournament) {
  if (!match?.scheduled_time) {
    return { when: null, where: null };
  }
  const start = new Date(match.scheduled_time);
  if (!Number.isFinite(start.getTime())) {
    return { when: null, where: null };
  }
  let end = match.scheduled_end_time ? new Date(match.scheduled_end_time) : null;
  if (!end || !Number.isFinite(end.getTime())) {
    const dur = Number(match.duration_minutes) || Number(tournament?.match_duration_minutes) || 90;
    end = new Date(start.getTime() + dur * 60 * 1000);
  }
  const dateLine = start.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
  const opt = { hour: "numeric", minute: "2-digit" };
  const t1 = start.toLocaleTimeString(undefined, opt);
  const t2 = Number.isFinite(end.getTime()) ? end.toLocaleTimeString(undefined, opt) : t1;
  return {
    when: `${dateLine} · ${t1} – ${t2}`,
    where: (match.location && String(match.location).trim()) || null,
  };
}

const FORMATS = [
  { value: "pool_only", label: "Pool Play" },
  { value: "bracket_only", label: "Bracket" },
  { value: "pool_and_bracket", label: "Pool + Bracket" },
];

function getMatchOutcomeCopy(match) {
  const a = match.team_a_name || "TBD";
  const b = match.team_b_name || "TBD";
  if (match.status === "cancelled") {
    return { line1: "Cancelled", line2: null };
  }
  if (match.status === "completed" && match.team_a_score != null && match.team_b_score != null) {
    return {
      line1: `${a} ${match.team_a_score} - ${match.team_b_score} ${b}`,
      line2: match.winner_team_name ? `Winner: ${match.winner_team_name}` : null,
    };
  }
  if (match.status === "scheduled") {
    return { line1: "Not played yet", line2: null };
  }
  if (match.team_a_score != null && match.team_b_score != null) {
    const leader = match.team_a_score > match.team_b_score ? a : match.team_b_score > match.team_a_score ? b : null;
    return {
      line1: `${a} ${match.team_a_score} - ${match.team_b_score} ${b}`,
      line2: leader ? `Leading: ${leader}` : null,
    };
  }
  if (match.status === "ongoing") {
    return { line1: "In progress", line2: "Waiting for final scores" };
  }
  return { line1: "Not played yet", line2: null };
}

function getBracketWaitMessage(match, allMatches) {
  if (match.pool_id) return null;
  if (match.status === "completed" || (match.team_a_id && match.team_b_id)) return null;
  const waiting = [];
  if (!match.team_a_id) {
    const f = allMatches.find((m) => m.next_match_id === match.id && m.next_match_slot === "A");
    if (f && f.status !== "completed") waiting.push(`Match ${f.match_number}`);
  }
  if (!match.team_b_id) {
    const f = allMatches.find((m) => m.next_match_id === match.id && m.next_match_slot === "B");
    if (f && f.status !== "completed") waiting.push(`Match ${f.match_number}`);
  }
  if (waiting.length === 0) return null;
  return `Waiting for winner of ${waiting.join(" & ")}`;
}

function getAdvanceBlurb(match, matchById) {
  if (match.status !== "completed" || !match.winner_team_name) return null;
  if (String(match.bracket_round || "").toLowerCase() === "final") return null;
  if (!match.next_match_id) return null;
  const n = matchById[match.next_match_id];
  if (n?.bracket_round) return `Advances to ${n.bracket_round}`;
  return "Advances to next round";
}

function MatchOutcomeLines({ match, bracketWait, advanceBlurb, compact = false, showWaitPairLine = true }) {
  const o = getMatchOutcomeCopy(match);
  const classRoot = compact ? "tournament-outcome tournament-outcome--compact" : "tournament-outcome";
  const waitFirst = Boolean(bracketWait) && match.status !== "completed";
  return (
    <div className={classRoot}>
      {waitFirst ? (
        <>
          <div className="tournament-outcome__primary tournament-outcome__wait">{bracketWait}</div>
          {showWaitPairLine ? (
            <div className="tournament-outcome__pair">
              {match.team_a_name || "TBD"}{" "}
              <span className="tournament-outcome__vs">vs</span> {match.team_b_name || "TBD"}
            </div>
          ) : null}
        </>
      ) : (
        <>
          <div className="tournament-outcome__primary">{o.line1}</div>
          {o.line2 ? <div className="tournament-outcome__secondary">{o.line2}</div> : null}
        </>
      )}
      {advanceBlurb ? <div className="tournament-outcome__advance">{advanceBlurb}</div> : null}
    </div>
  );
}

export default function TournamentsPage() {
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [tab, setTab] = useState("overview");
  const [me, setMe] = useState(null);
  const [tournaments, setTournaments] = useState([]);
  const [selectedTournamentId, setSelectedTournamentId] = useState(null);
  const [matches, setMatches] = useState([]);
  const [myMatches, setMyMatches] = useState([]);
  const [standings, setStandings] = useState([]);
  const [bracketRounds, setBracketRounds] = useState([]);
  const [availableTeams, setAvailableTeams] = useState([]);
  const [teamsLoading, setTeamsLoading] = useState(false);
  const [selectedTeams, setSelectedTeams] = useState([]);
  const [form, setForm] = useState({
    name: "",
    location: "",
    start_date: new Date().toISOString().slice(0, 10),
    start_time: "09:00",
    match_duration_minutes: 90,
    court_count: 1,
    format: "pool_and_bracket",
    number_of_pools: 2,
    teams_per_pool: 4,
    top_teams_advance_per_pool: 2,
    tie_break_rule: "wins, head-to-head, point_difference, points_for, random",
    club_id: "",
  });
  /** Match selected for the enter-result modal (replaces window.prompt). */
  const [resultEntryMatch, setResultEntryMatch] = useState(null);
  const [resultFormScoreA, setResultFormScoreA] = useState("");
  const [resultFormScoreB, setResultFormScoreB] = useState("");
  const [resultModalError, setResultModalError] = useState("");
  const [scheduleEditMatch, setScheduleEditMatch] = useState(null);
  const [scheduleForm, setScheduleForm] = useState({ datetimeLocal: "", duration: 90, location: "" });
  const [scheduleModalError, setScheduleModalError] = useState("");

  const canManage = Boolean(me?.is_director_or_staff || me?.viewer_is_staff);
  const viewerRole = String(me?.user?.role || "").toLowerCase();
  const canViewTournamentActions = viewerRole !== "player" && viewerRole !== "parent";
  const selectedTournament = useMemo(
    () => tournaments.find((item) => Number(item.id) === Number(selectedTournamentId)) || null,
    [tournaments, selectedTournamentId],
  );
  const selectedTeamCount = selectedTeams.length;
  const numberOfPools = Number(form.number_of_pools);
  const teamsPerPool = Number(form.teams_per_pool);
  const requiredTeamCount = numberOfPools * teamsPerPool;
  const needsPoolLayout = form.format !== "bracket_only";
  const hasMinimumTeams = selectedTeamCount >= 2;
  const hasDuplicateTeams = new Set(selectedTeams.map((team) => Number(team.id))).size !== selectedTeamCount;
  const hasValidPoolNumbers = Number.isFinite(numberOfPools) && numberOfPools > 0 && Number.isFinite(teamsPerPool) && teamsPerPool > 0;
  const poolLayoutMatches = !needsPoolLayout || (hasValidPoolNumbers && selectedTeamCount === requiredTeamCount);
  const hasValidTopTeamsAdvance = !needsPoolLayout || Number(form.top_teams_advance_per_pool) <= teamsPerPool;
  const submitBlockReason = (() => {
    if (!canManage) return "Only directors can create tournaments.";
    if (teamsLoading) return "Teams are still loading.";
    if (!form.name.trim()) return "Tournament name is required.";
    if (!form.location.trim()) return "Location is required.";
    if (!form.start_date) return "Start date is required.";
    if (!hasMinimumTeams) return "Select at least 2 teams.";
    if (hasDuplicateTeams) return "Duplicate team selections are not allowed.";
    if (!poolLayoutMatches) {
      return `You selected ${selectedTeamCount} teams. Your pool settings require ${requiredTeamCount} teams.`;
    }
    if (!hasValidTopTeamsAdvance) return "Top teams advancing cannot exceed teams per pool.";
    return "";
  })();
  const canSubmitTournament =
    !submitBlockReason &&
    canManage &&
    !busy &&
    !teamsLoading &&
    Boolean(form.name.trim()) &&
    Boolean(form.location.trim()) &&
    Boolean(form.start_date) &&
    hasMinimumTeams &&
    !hasDuplicateTeams &&
    poolLayoutMatches &&
    hasValidTopTeamsAdvance;
  const generateBracketDisabledReason = useMemo(() => {
    if (!canManage) return "Only club directors can generate the bracket.";
    if (!selectedTournament) return "Select a tournament.";
    if (selectedTournament.format === "pool_only") {
      return "Pool-only tournaments do not use an elimination bracket.";
    }
    if (selectedTournament.format === "bracket_only") {
      return "";
    }
    const poolRows = matches.filter((row) => row.pool_id);
    if (poolRows.length === 0) {
      return "Generate pools and pool matches first.";
    }
    if (!poolRows.every((row) => row.status === "completed")) {
      return "Complete all pool matches before generating the bracket.";
    }
    return "";
  }, [canManage, selectedTournament, matches]);

  const canRunGenerateBracket = !generateBracketDisabledReason;

  const allMatchesSorted = useMemo(() => {
    return [...matches].sort((a, b) => {
      const ta = a.scheduled_time ? Date.parse(a.scheduled_time) : Number.MAX_SAFE_INTEGER;
      const tb = b.scheduled_time ? Date.parse(b.scheduled_time) : Number.MAX_SAFE_INTEGER;
      if (ta !== tb) return ta - tb;
      return (a.match_number || 0) - (b.match_number || 0);
    });
  }, [matches]);

  const poolGroups = useMemo(() => {
    const poolRows = matches.filter((row) => row.pool_id);
    const map = new Map();
    for (const m of poolRows) {
      const name = m.pool_name || "Pool";
      if (!map.has(name)) map.set(name, []);
      map.get(name).push(m);
    }
    for (const arr of map.values()) {
      arr.sort((a, b) => {
        const ta = a.scheduled_time ? Date.parse(a.scheduled_time) : 0;
        const tb = b.scheduled_time ? Date.parse(b.scheduled_time) : 0;
        return ta - tb;
      });
    }
    return Array.from(map.entries());
  }, [matches]);

  const bracketRoundsDisplayOrder = useMemo(() => {
    const weight = (name) => {
      const n = (name || "").toLowerCase();
      if (n.includes("quarter")) return 1;
      if (n.includes("semi")) return 2;
      if (n === "final" || (n.includes("final") && !n.includes("semi"))) return 4;
      if (n.includes("round")) return 3;
      return 9;
    };
    return [...bracketRounds].sort((a, b) => weight(a.name) - weight(b.name) || (a.name || "").localeCompare(b.name || ""));
  }, [bracketRounds]);

  const progressTracker = useMemo(() => {
    if (!selectedTournament) return [];
    const fmt = selectedTournament.format;
    const st = selectedTournament.status;
    const poolMs = matches.filter((m) => m.pool_id);
    const bracketMs = matches.filter((m) => !m.pool_id);
    const poolsGen = fmt !== "bracket_only" && standings.length > 0;
    const poolMatchesGen = fmt !== "bracket_only" && poolMs.length > 0;
    const poolResDone = fmt !== "bracket_only" && poolMatchesGen && poolMs.every((m) => m.status === "completed");
    const bracketGen = fmt !== "pool_only" && bracketMs.length > 0;
    const items = [{ key: "c", label: "Created", done: true, na: false }];
    if (fmt === "bracket_only") {
      items.push({ key: "pg", label: "Pools generated", done: false, na: true });
      items.push({ key: "pmg", label: "Pool matches generated", done: false, na: true });
      items.push({ key: "pr", label: "Pool results completed", done: false, na: true });
    } else {
      items.push({ key: "pg", label: "Pools generated", done: poolsGen, na: false });
      items.push({ key: "pmg", label: "Pool matches generated", done: poolMatchesGen, na: false });
      items.push({ key: "pr", label: "Pool results completed", done: poolResDone, na: false });
    }
    if (fmt === "pool_only") {
      items.push({ key: "br", label: "Bracket generated", done: false, na: true });
    } else {
      items.push({ key: "br", label: "Bracket generated", done: bracketGen, na: false });
    }
    items.push({ key: "fin", label: "Completed", done: st === "completed", na: false });
    return items;
  }, [selectedTournament, matches, standings.length]);

  const matchById = useMemo(() => {
    const o = {};
    for (const m of matches) o[m.id] = m;
    return o;
  }, [matches]);

  const overviewNarrative = useMemo(() => {
    if (!selectedTournament) return null;
    const status = selectedTournament.status;
    const fmt = selectedTournament.format;
    const bracketMs = matches.filter((m) => !m.pool_id);
    if (status === "completed") {
      const finalM = matches.find(
        (m) =>
          !m.pool_id &&
          String(m.bracket_round || "").toLowerCase() === "final" &&
          m.status === "completed" &&
          m.winner_team_name,
      );
      if (finalM) {
        return { type: "champion", line: `Champion: ${finalM.winner_team_name}` };
      }
      if (fmt === "pool_only" && standings.length) {
        const parts = standings
          .map((p) => {
            const top = p.rows?.[0];
            return top ? `${p.pool_name} — ${top.team_name}` : null;
          })
          .filter(Boolean);
        if (parts.length) {
          return { type: "champion", line: `Tournament complete — ${parts.join(" · ")}` };
        }
      }
      return { type: "champion", line: "Tournament complete" };
    }
    if (status === "pool_stage" && standings.length) {
      const parts = standings
        .map((p) => {
          const top = p.rows?.[0];
          return top ? `${p.pool_name}: ${top.team_name}` : null;
        })
        .filter(Boolean);
      if (parts.length) {
        return { type: "leaders", line: `Current leaders: ${parts.join(" · ")}` };
      }
    }
    if ((status === "bracket_stage" || (fmt === "bracket_only" && bracketMs.length)) && bracketMs.length) {
      const eliminated = new Set();
      for (const m of bracketMs) {
        if (m.status === "completed" && m.loser_team_id) eliminated.add(m.loser_team_id);
      }
      const seen = new Set();
      for (const m of bracketMs) {
        if (m.team_a_id) seen.add(m.team_a_id);
        if (m.team_b_id) seen.add(m.team_b_id);
      }
      const still = [...seen].filter((id) => !eliminated.has(id));
      const idToName = new Map();
      for (const m of bracketMs) {
        if (m.team_a_id) idToName.set(m.team_a_id, m.team_a_name);
        if (m.team_b_id) idToName.set(m.team_b_id, m.team_b_name);
      }
      const names = still.map((id) => idToName.get(id)).filter(Boolean);
      if (names.length) {
        return { type: "remaining", line: `Still in the bracket: ${names.join(", ")}` };
      }
    }
    return null;
  }, [selectedTournament, matches, standings]);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      try {
        const [profile, list, mine] = await Promise.all([fetchCurrentUser(), fetchTournaments(), fetchMyTournamentMatches()]);
        if (!mounted) return;
        setMe(profile);
        setTournaments(list?.tournaments || []);
        setMyMatches(mine?.matches || []);
        if (list?.tournaments?.length) setSelectedTournamentId(list.tournaments[0].id);
        const ownedClubId = String(profile?.owned_clubs?.[0]?.id || "");
        setForm((prev) => ({ ...prev, club_id: ownedClubId }));
        if (ownedClubId) {
          setTeamsLoading(true);
          try {
            const teamsPayload = await fetchClubTeams(ownedClubId);
            if (!mounted) return;
            setAvailableTeams((teamsPayload?.teams || []).slice().sort((a, b) => a.name.localeCompare(b.name)));
          } finally {
            if (mounted) setTeamsLoading(false);
          }
        }
      } catch (err) {
        if (mounted) setError(err.message || "Failed to load tournaments.");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    void load();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedTournamentId) return;
    let mounted = true;
    async function loadDetails() {
      try {
        const [m, s, b] = await Promise.all([
          fetchTournamentMatches(selectedTournamentId),
          fetchTournamentStandings(selectedTournamentId),
          fetchTournamentBracket(selectedTournamentId),
        ]);
        if (!mounted) return;
        setMatches(m?.matches || []);
        setStandings(s?.standings || []);
        setBracketRounds(b?.rounds || []);
      } catch (err) {
        if (mounted) setError(err.message || "Failed to load tournament details.");
      }
    }
    void loadDetails();
    return () => {
      mounted = false;
    };
  }, [selectedTournamentId]);

  useEffect(() => {
    if (!canManage && tab === "setup") {
      setTab("overview");
    }
  }, [canManage, tab]);

  useEffect(() => {
    if (!resultEntryMatch) return undefined;
    function onKey(e) {
      if (e.key === "Escape") {
        setResultEntryMatch(null);
        setResultFormScoreA("");
        setResultFormScoreB("");
        setResultModalError("");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [resultEntryMatch]);

  async function refreshAll(currentId) {
    const list = await fetchTournaments();
    setTournaments(list?.tournaments || []);
    if (!currentId) return;
    const [m, s, b] = await Promise.all([
      fetchTournamentMatches(currentId),
      fetchTournamentStandings(currentId),
      fetchTournamentBracket(currentId),
    ]);
    setMatches(m?.matches || []);
    setStandings(s?.standings || []);
    setBracketRounds(b?.rounds || []);
  }

  async function createNewTournament(event) {
    event.preventDefault();
    if (!canManage) {
      setError("Only directors can create tournaments.");
      return;
    }
    setError("");
    setMessage("");
    const teamIds = selectedTeams.map((team) => Number(team.id));
    if (!form.name.trim() || !form.location.trim() || !form.start_date || teamIds.length < 2) {
      setError("Tournament name, location, start date, and at least 2 teams are required.");
      return;
    }
    if (new Set(teamIds).size !== teamIds.length) {
      setError("Duplicate team selections are not allowed.");
      return;
    }
    if (form.format !== "bracket_only") {
      const selectedCount = selectedTeams.length;
      const pools = Number(form.number_of_pools);
      const perPool = Number(form.teams_per_pool);
      const requiredCount = pools * perPool;
      if (!Number.isFinite(pools) || !Number.isFinite(perPool) || pools < 1 || perPool < 1) {
        setError("Pool settings must be valid numbers greater than 0.");
        return;
      }
      if (selectedCount !== requiredCount) {
        setError(`You selected ${selectedCount} teams. Your pool settings require ${requiredCount} teams.`);
        return;
      }
    }
    if (form.format !== "bracket_only" && Number(form.top_teams_advance_per_pool) > Number(form.teams_per_pool)) {
      setError("Top teams advancing cannot exceed teams per pool.");
      return;
    }
    setBusy(true);
    try {
      const data = await createTournament({
        ...form,
        team_ids: teamIds,
        number_of_pools: Number(form.number_of_pools),
        teams_per_pool: Number(form.teams_per_pool),
        top_teams_advance_per_pool: Number(form.top_teams_advance_per_pool),
        court_count: Math.min(8, Math.max(1, Number(form.court_count) || 1)),
        start_time: form.start_time,
        match_duration_minutes: Math.min(180, Math.max(15, Number(form.match_duration_minutes) || 90)),
      });
      let id = data?.id ?? data?.tournament?.id ?? data?.tournament_id ?? null;
      if (!id) {
        const latest = await fetchTournaments();
        const candidate = (latest?.tournaments || []).find(
          (row) =>
            row?.name === form.name &&
            row?.start_date === form.start_date &&
            row?.format === form.format,
        ) || latest?.tournaments?.[0];
        id = candidate?.id ?? null;
      }
      if (!id) {
        const keys = data && typeof data === "object" ? Object.keys(data).join(", ") : "no-json-payload";
        throw new Error(`Tournament was created but no tournament ID was returned. Response keys: ${keys}`);
      }
      if (form.format === "bracket_only") {
        try {
          await generateTournamentBracket(id);
        } catch (stepError) {
          throw new Error(`Tournament created, but bracket generation failed: ${stepError.message || "unknown error"}`);
        }
        await refreshAll(id);
        setSelectedTournamentId(id);
        setTab("overview");
        setMessage("Tournament created and bracket generated. See Overview, Matches, and each team’s Schedule / Events.");
      } else {
        try {
          await generateTournamentPools(id);
        } catch (stepError) {
          throw new Error(`Tournament created, but pool generation failed: ${stepError.message || "unknown error"}`);
        }
        try {
          await generateTournamentPoolMatches(id);
        } catch (stepError) {
          throw new Error(`Pools generated, but pool match generation failed: ${stepError.message || "unknown error"}`);
        }
        await refreshAll(id);
        setSelectedTournamentId(id);
        setTab("overview");
        if (form.format === "pool_and_bracket") {
          setMessage(
            "Tournament created. Pool play is next — use Pools / Matches, then Setup → Generate Bracket when all pool games are done. Games sync to Schedule / Events.",
          );
        } else {
          setMessage("Tournament created. Pool play is ready — results update standings. Games sync to each team’s Schedule / Events.");
        }
      }
    } catch (err) {
      setError(err.message || "Could not generate tournament setup.");
    } finally {
      setBusy(false);
    }
  }

  async function runAction(action) {
    if (!selectedTournamentId) return;
    if (!canManage) {
      setError("Only directors can manage tournament generation.");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (action === "pools") await generateTournamentPools(selectedTournamentId);
      if (action === "poolMatches") await generateTournamentPoolMatches(selectedTournamentId);
      if (action === "bracket") await generateTournamentBracket(selectedTournamentId);
      await refreshAll(selectedTournamentId);
      if (action === "bracket") {
        setMessage("Bracket generated. Review the Matches tab; games are added to each team’s Schedule.");
      } else {
        setMessage("Action completed. Matches tab and schedules are updated when applicable.");
      }
    } catch (err) {
      setError(err.message || "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  function openResultForm(match) {
    setResultModalError("");
    setResultEntryMatch(match);
    setResultFormScoreA("");
    setResultFormScoreB("");
  }

  function closeResultForm() {
    setResultEntryMatch(null);
    setResultFormScoreA("");
    setResultFormScoreB("");
    setResultModalError("");
  }

  async function submitResultForm(event) {
    event.preventDefault();
    if (!resultEntryMatch || !selectedTournamentId) return;
    const a = Number(String(resultFormScoreA).trim());
    const b = Number(String(resultFormScoreB).trim());
    if (!Number.isFinite(a) || !Number.isFinite(b) || a < 0 || b < 0) {
      setResultModalError("Please enter valid non-negative numbers for both scores.");
      return;
    }
    if (a === b) {
      setResultModalError("Scores cannot be tied.");
      return;
    }
    setBusy(true);
    setResultModalError("");
    try {
      await submitTournamentMatchResult(resultEntryMatch.id, { team_a_score: a, team_b_score: b });
      await refreshAll(selectedTournamentId);
      closeResultForm();
      if (resultEntryMatch.pool_id) {
        setMessage("Result saved. Pool standings, bracket (if any), and Schedule / Events are updated.");
      } else {
        setMessage("Result saved. Bracket, winners, and Schedule / Events are updated.");
      }
    } catch (err) {
      setResultModalError(err.message || "Could not save result.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <section className="teams-page-shell"><p>Loading tournaments...</p></section>;

  const myMatchIds = new Set(myMatches.map((row) => row.id));
  const poolMatches = matches.filter((row) => row.pool_id);
  const allPoolMatchesComplete =
    poolMatches.length > 0 && poolMatches.every((row) => row.status === "completed");

  /** Why the Bracket tab can be empty even when status is "bracket_stage": finishing pool play
   *  only updates status; bracket rows are created by POST …/generate-bracket/ (Setup → Generate Bracket). */
  const bracketEmptyLines = (() => {
    if (!selectedTournament) return ["Select a tournament to view the bracket."];
    const fmt = selectedTournament.format;
    if (fmt === "pool_only") {
      return ["This tournament is pool-only. There is no elimination bracket."];
    }
    if (fmt === "bracket_only") {
      return [
        "The elimination bracket is not in the schedule yet.",
        canManage
          ? "Open the Setup tab and click “Generate Bracket” to create bracket matches."
          : "Ask a club director to generate the bracket from the Setup tab.",
      ];
    }
    if (poolMatches.length === 0) {
      return [
        "No pool matches are scheduled yet.",
        "Create the tournament with pools and pool matches from the Setup tab first.",
      ];
    }
    if (!allPoolMatchesComplete) {
      return [
        "Finish every pool match first.",
        "The bracket section will show matches after you click “Generate Bracket” on the Setup tab once all pool results are in.",
      ];
    }
    return [
      "Pool play is complete, but bracket matches have not been generated yet (this is a separate step).",
      canManage
        ? "Open the Setup tab and click “Generate Bracket” to build the elimination bracket."
        : "Ask a club director to open Setup and click “Generate Bracket.”",
    ];
  })();

  const canEnterThisMatch = (match) =>
    canViewTournamentActions && (canManage || myMatchIds.has(match.id)) && match.status !== "completed";

  /** Bracket (and pool) results need two assigned teams before the API accepts a score. */
  const canEnterResultForMatch = (match) =>
    canEnterThisMatch(match) && match.team_a_id && match.team_b_id;

  const canEditMatchSchedule = (match) =>
    canViewTournamentActions &&
    canManage &&
    match.status !== "completed" &&
    match.status !== "cancelled" &&
    Boolean(match.scheduled_time);

  function openScheduleEdit(match) {
    setScheduleModalError("");
    setScheduleEditMatch(match);
    setScheduleForm({
      datetimeLocal: isoToDatetimeLocalValue(match.scheduled_time),
      duration: match.duration_minutes ?? selectedTournament?.match_duration_minutes ?? 90,
      location: match.location || "",
    });
  }

  function closeScheduleEdit() {
    if (busy) {
      return;
    }
    setScheduleEditMatch(null);
  }

  async function submitScheduleEdit(event) {
    event.preventDefault();
    if (!scheduleEditMatch) {
      return;
    }
    setBusy(true);
    setScheduleModalError("");
    try {
      const d = new Date(scheduleForm.datetimeLocal);
      if (!Number.isFinite(d.getTime())) {
        setScheduleModalError("Choose a valid date and time.");
        return;
      }
      const tDefault = Number(selectedTournament?.match_duration_minutes) || 90;
      const useDur = Number(scheduleForm.duration);
      let duration_minutes = null;
      if (Number.isFinite(useDur) && useDur >= 15 && useDur !== tDefault) {
        duration_minutes = useDur;
      }
      await rescheduleTournamentMatch(scheduleEditMatch.id, {
        scheduled_time: d.toISOString(),
        location: scheduleForm.location,
        duration_minutes,
      });
      await refreshAll(selectedTournamentId);
      window.dispatchEvent(new Event("netup-schedule-changed"));
      setMessage("Match schedule updated. Schedules and Events will show the new time.");
      setScheduleEditMatch(null);
    } catch (err) {
      setScheduleModalError(err.message || "Could not update schedule.");
    } finally {
      setBusy(false);
    }
  }

  const tabList = canManage ? TABS_DIRECTOR : TABS_VIEWER;

  return (
    <section className="teams-page-shell tournament-v2-shell">
      {resultEntryMatch ? (
        <div
          className="vc-modal-backdrop"
          role="presentation"
          onClick={busy ? undefined : closeResultForm}
        >
          <div
            className="vc-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="tournament-result-form-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="vc-modal__head">
              <h2 id="tournament-result-form-title">Enter match result</h2>
              <button
                type="button"
                className="vc-modal__close"
                onClick={closeResultForm}
                disabled={busy}
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <p className="vc-modal__muted">
              {resultEntryMatch.team_a_name || "Team A"} vs {resultEntryMatch.team_b_name || "Team B"}
            </p>
            <form className="tournament-reschedule-form" onSubmit={submitResultForm}>
              <label>
                <span>{resultEntryMatch.team_a_name || "Team A"}</span>
                <input
                  type="number"
                  min="0"
                  inputMode="numeric"
                  value={resultFormScoreA}
                  onChange={(e) => setResultFormScoreA(e.target.value)}
                  required
                  autoFocus
                />
              </label>
              <label>
                <span>{resultEntryMatch.team_b_name || "Team B"}</span>
                <input
                  type="number"
                  min="0"
                  inputMode="numeric"
                  value={resultFormScoreB}
                  onChange={(e) => setResultFormScoreB(e.target.value)}
                  required
                />
              </label>
              {resultModalError ? <p className="vc-modal__error">{resultModalError}</p> : null}
              <div className="tournament-modal-actions">
                <button type="button" className="tournament-history-btn" onClick={closeResultForm} disabled={busy}>
                  Cancel
                </button>
                <button type="submit" className="vc-action-btn" disabled={busy}>
                  {busy ? "Saving…" : "Save result"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
      {scheduleEditMatch ? (
        <div
          className="vc-modal-backdrop"
          role="presentation"
          onClick={busy ? undefined : closeScheduleEdit}
        >
          <div
            className="vc-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="tournament-schedule-form-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="vc-modal__head">
              <h2 id="tournament-schedule-form-title">Edit match schedule</h2>
              <button
                type="button"
                className="vc-modal__close"
                onClick={closeScheduleEdit}
                disabled={busy}
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <p className="vc-modal__muted">
              {scheduleEditMatch.team_a_name || "Team A"} vs {scheduleEditMatch.team_b_name || "Team B"}
            </p>
            <form className="tournament-reschedule-form" onSubmit={submitScheduleEdit}>
              <label>
                <span>Start (your local time)</span>
                <input
                  type="datetime-local"
                  value={scheduleForm.datetimeLocal}
                  onChange={(e) => setScheduleForm((f) => ({ ...f, datetimeLocal: e.target.value }))}
                  required
                />
              </label>
              <label>
                <span>Match length (minutes)</span>
                <input
                  type="number"
                  min="15"
                  max="240"
                  step="5"
                  value={scheduleForm.duration}
                  onChange={(e) => setScheduleForm((f) => ({ ...f, duration: e.target.value }))}
                />
                <small className="vc-modal__muted" style={{ display: "block", marginTop: 4 }}>
                  Same as tournament default ({selectedTournament?.match_duration_minutes || 90} min) — leave as-is; change only
                  to override for this game.
                </small>
              </label>
              <label>
                <span>Court / location</span>
                <input
                  type="text"
                  value={scheduleForm.location}
                  onChange={(e) => setScheduleForm((f) => ({ ...f, location: e.target.value }))}
                  placeholder="e.g. Court 1"
                />
              </label>
              {scheduleModalError ? <p className="vc-modal__error">{scheduleModalError}</p> : null}
              <div className="tournament-modal-actions">
                <button type="button" className="tournament-history-btn" onClick={closeScheduleEdit} disabled={busy}>
                  Cancel
                </button>
                <button type="submit" className="vc-action-btn" disabled={busy}>
                  {busy ? "Saving…" : "Save schedule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
      <header className="teams-page-header">
        <div className="teams-page-heading">
          <p className="teams-page-kicker">Tournament Center</p>
          <h1>Overview · Pools · Bracket · Matches</h1>
        </div>
      </header>

      {error ? <p className="schedule-feedback schedule-feedback--error">{error}</p> : null}
      {message ? <p className="vc-director-success">{message}</p> : null}

      <div className="tournament-flow-tabs">
        {tabList.map((item) => (
          <button key={item} type="button" className={`tournament-flow-tab${tab === item ? " is-active" : ""}`} onClick={() => setTab(item)}>
            {formatTabLabel(item)}
          </button>
        ))}
      </div>

      <div className="tournament-v2-grid">
        <aside className="tournament-v2-panel">
          <h2>Tournaments</h2>
          <div className="tournament-v2-scroll">
            {tournaments.map((tournament) => (
              <button
                key={tournament.id}
                type="button"
                className={`tournament-history-item tournament-history-item--button${
                  Number(selectedTournamentId) === Number(tournament.id) ? " is-selected" : ""
                }`}
                onClick={() => setSelectedTournamentId(tournament.id)}
              >
                <strong>{tournament.name}</strong>
                <span>{tournament.status}</span>
              </button>
            ))}
          </div>
        </aside>

        <main className="tournament-v2-panel">
          {tab === "overview" ? (
            <div className="tournament-v2-scroll tournament-overview">
              {!selectedTournament ? (
                <p>Select a tournament from the list.</p>
              ) : (
                <>
                  <div className="tournament-overview__hero">
                    <h2 className="tournament-overview__title">{selectedTournament.name}</h2>
                    <p className="tournament-overview__meta">
                      <span>Format: {selectedTournament.format?.replace(/_/g, " ")}</span>
                      <span className="tournament-overview__sep">·</span>
                      <span>Status: {selectedTournament.status}</span>
                    </p>
                    {overviewNarrative ? (
                      <p
                        className={`tournament-overview__narrative tournament-overview__narrative--${overviewNarrative.type}`}
                        role="status"
                      >
                        {overviewNarrative.line}
                      </p>
                    ) : null}
                  </div>
                  {progressTracker.length ? (
                    <div className="tournament-progress-strip">
                      <p className="tournament-progress-strip__title">Progress</p>
                      <ol className="tournament-progress-steps">
                        {progressTracker.map((step) => (
                          <li
                            key={step.key}
                            className={`tournament-progress-steps__item${step.done ? " is-done" : ""}${step.na ? " is-na" : ""}`}
                          >
                            <span className="tournament-progress-steps__mark" aria-hidden>
                              {step.na ? "—" : step.done ? "✓" : "○"}
                            </span>
                            <span>{step.label}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  ) : null}
                  <div className="tournament-overview__hints">
                    <p className="tournament-overview__hints-title">When actions are blocked</p>
                    <ul>
                      {selectedTournament.format === "bracket_only" ? (
                        <li>Bracket-only tournaments do not use pools — pool steps above are not applicable.</li>
                      ) : null}
                      {selectedTournament.format === "pool_only" ? (
                        <li>Pool-only format has no elimination bracket — use pool results to finish the event.</li>
                      ) : null}
                      {selectedTournament.format === "pool_and_bracket" ? (
                        <li>Complete all pool matches before generating the bracket.</li>
                      ) : null}
                      <li>Enter results to advance winners. Pool games update standings; bracket games advance the next round.</li>
                      {generateBracketDisabledReason && selectedTournament.format === "pool_and_bracket" ? (
                        <li>
                          <strong>Generate Bracket (Setup):</strong> {generateBracketDisabledReason}
                        </li>
                      ) : null}
                      {generateBracketDisabledReason && selectedTournament.format === "pool_only" ? (
                        <li>
                          <strong>Generate Bracket (Setup):</strong> {generateBracketDisabledReason}
                        </li>
                      ) : null}
                    </ul>
                  </div>
                  <p className="tournament-matches-intro">
                    Scheduled games appear on each team’s <strong>Schedule</strong> and coach <strong>Events</strong> with tournament details, time, and scores after you enter
                    results.
                  </p>
                </>
              )}
            </div>
          ) : null}
          {tab === "setup" ? (
            <form className="tournament-form-grid" onSubmit={createNewTournament}>
              <label><span>Name</span><input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
              <label><span>Location</span><input value={form.location} onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))} /></label>
              <label><span>Start Date</span><input type="date" value={form.start_date} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} /></label>
              <label>
                <span>Day start time</span>
                <input
                  type="time"
                  value={form.start_time}
                  onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value }))}
                />
              </label>
              <label>
                <span>Match length (min)</span>
                <input
                  type="number"
                  min="15"
                  max="180"
                  value={form.match_duration_minutes}
                  onChange={(e) => setForm((f) => ({ ...f, match_duration_minutes: e.target.value }))}
                />
              </label>
              <label>
                <span>Courts (parallel)</span>
                <input
                  type="number"
                  min="1"
                  max="8"
                  value={form.court_count}
                  onChange={(e) => setForm((f) => ({ ...f, court_count: e.target.value }))}
                />
              </label>
              <label><span>Format</span><select value={form.format} onChange={(e) => setForm((f) => ({ ...f, format: e.target.value }))}>{FORMATS.map((it) => <option key={it.value} value={it.value}>{it.label}</option>)}</select></label>
              <label><span># Pools</span><input type="number" min="1" value={form.number_of_pools} onChange={(e) => setForm((f) => ({ ...f, number_of_pools: e.target.value }))} /></label>
              <label><span>Teams/Pool</span><input type="number" min="2" value={form.teams_per_pool} onChange={(e) => setForm((f) => ({ ...f, teams_per_pool: e.target.value }))} /></label>
              <label><span>Top Teams Advance</span><input type="number" min="1" value={form.top_teams_advance_per_pool} onChange={(e) => setForm((f) => ({ ...f, top_teams_advance_per_pool: e.target.value }))} /></label>
              <label><span>Tie-break Rule</span><input value={form.tie_break_rule} onChange={(e) => setForm((f) => ({ ...f, tie_break_rule: e.target.value }))} /></label>
              <label className="tournament-form-grid__full">
                <span>Select Teams</span>
                {teamsLoading ? <p>Loading teams...</p> : null}
                {!teamsLoading && !availableTeams.length ? <p>No teams available. Please create teams first.</p> : null}
                {!teamsLoading && availableTeams.length ? (
                  <div className="tournament-team-selector">
                    <div className="tournament-form-card__actions">
                      <button
                        type="button"
                        className="tournament-history-btn"
                        onClick={() => {
                          const uniqueTeams = [];
                          const seen = new Set();
                          for (const team of availableTeams) {
                            const id = Number(team.id);
                            if (seen.has(id)) continue;
                            seen.add(id);
                            uniqueTeams.push({ id: team.id, name: team.name });
                          }
                          setSelectedTeams(uniqueTeams);
                        }}
                      >
                        Select All Teams
                      </button>
                      <button
                        type="button"
                        className="tournament-history-btn"
                        onClick={() => setSelectedTeams([])}
                      >
                        Clear Teams
                      </button>
                    </div>
                    <select
                      value=""
                      onChange={(e) => {
                        const selectedId = Number(e.target.value);
                        if (!selectedId) return;
                        const selected = availableTeams.find((team) => Number(team.id) === selectedId);
                        if (!selected) return;
                        setSelectedTeams((prev) => (
                          prev.some((team) => Number(team.id) === selectedId)
                            ? prev
                            : [...prev, { id: selected.id, name: selected.name }]
                        ));
                      }}
                    >
                      <option value="">Choose a team</option>
                      {availableTeams
                        .filter((team) => !selectedTeams.some((picked) => Number(picked.id) === Number(team.id)))
                        .map((team) => (
                          <option key={team.id} value={team.id}>{team.name}</option>
                        ))}
                    </select>
                    <div className="tournament-team-chips">
                      {selectedTeams.map((team) => (
                        <button
                          key={team.id}
                          type="button"
                          className="tournament-history-btn"
                          onClick={() => setSelectedTeams((prev) => prev.filter((item) => Number(item.id) !== Number(team.id)))}
                        >
                          {team.name} ×
                        </button>
                      ))}
                    </div>
                    {needsPoolLayout ? (
                      <p>
                        You selected {selectedTeamCount} teams. Your pool settings require {requiredTeamCount} teams.
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </label>
              <div className="tournament-form-card__actions">
                <button
                  type="submit"
                  className="vc-action-btn"
                  disabled={!canSubmitTournament}
                  title={
                    submitBlockReason ||
                    (form.format === "bracket_only"
                      ? "Create tournament and generate the bracket"
                      : "Create tournament, generate pools, and generate pool matches")
                  }
                >
                  Generate Tournament
                </button>
                <button
                  type="button"
                  className="tournament-history-btn"
                  disabled={!canRunGenerateBracket || busy}
                  title={generateBracketDisabledReason || "Generate the elimination bracket"}
                  onClick={() => runAction("bracket")}
                >
                  Generate Bracket
                </button>
              </div>
              {submitBlockReason ? (
                <p className="schedule-feedback schedule-feedback--error">{submitBlockReason}</p>
              ) : null}
            </form>
          ) : null}

          {tab === "matches" ? (
            <div className="tournament-v2-scroll">
              <p className="tournament-matches-intro">
                Operational list of every pool and bracket game (sort: start time). Same games sync to <strong>Schedule</strong> and <strong>Events</strong> for each team.
              </p>
              {!allMatchesSorted.length ? <p>No matches scheduled yet.</p> : (
                <div className="tournament-fixtures-table-wrap">
                  <table className="tournament-fixtures-table tournament-fixtures-table--all-matches">
                    <thead>
                      <tr>
                        <th>Scheduled (your time)</th>
                        <th>Stage</th>
                        <th>Pool / round</th>
                        <th>Court</th>
                        <th>Team A</th>
                        <th>Team B</th>
                        <th>Outcome</th>
                        <th>Status</th>
                        {canViewTournamentActions ? <th>Action</th> : null}
                      </tr>
                    </thead>
                    <tbody>
                      {allMatchesSorted.map((match) => {
                        const scoreDone =
                          match.status === "completed" &&
                          match.team_a_score != null &&
                          match.team_b_score != null;
                        const stage = match.pool_id ? "Pool" : "Bracket";
                        const pr = match.pool_round_number;
                        const roundCol = match.pool_id
                          ? (pr ? `${match.pool_name || "Pool"} · Round ${pr}` : match.pool_name || "—")
                          : match.bracket_round || "—";
                        const bracketWait = getBracketWaitMessage(match, matches);
                        const advanceBlurb = !match.pool_id ? getAdvanceBlurb(match, matchById) : null;
                        return (
                          <tr key={match.id}>
                            <td>
                              <TournamentStartCell
                                iso={match.scheduled_time}
                                endIso={match.scheduled_end_time}
                              />
                            </td>
                            <td>{stage}</td>
                            <td>{roundCol}</td>
                            <td>{match.location || "—"}</td>
                            <td>{match.team_a_name || "TBD"}</td>
                            <td>{match.team_b_name || "TBD"}</td>
                            <td>
                              <MatchOutcomeLines
                                match={match}
                                bracketWait={!match.pool_id ? bracketWait : null}
                                advanceBlurb={advanceBlurb}
                              />
                            </td>
                            <td>{match.status}</td>
                            {canViewTournamentActions ? (
                              <td>
                                {scoreDone ? (
                                  "—"
                                ) : (
                                  <span className="tournament-row-actions">
                                    {canEditMatchSchedule(match) ? (
                                      <button
                                        type="button"
                                        className="tournament-history-btn"
                                        onClick={() => openScheduleEdit(match)}
                                        disabled={busy}
                                      >
                                        Edit schedule
                                      </button>
                                    ) : null}
                                    {canEnterResultForMatch(match) ? (
                                      <button
                                        type="button"
                                        className="tournament-history-btn"
                                        onClick={() => openResultForm(match)}
                                        disabled={busy}
                                      >
                                        Enter result
                                      </button>
                                    ) : null}
                                    {!canEditMatchSchedule(match) && !canEnterResultForMatch(match) ? "—" : null}
                                  </span>
                                )}
                              </td>
                            ) : null}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : null}

          {tab === "pools" ? (
            <div className="tournament-v2-scroll">
              {selectedTournament?.format === "bracket_only" ? (
                <p className="schedule-feedback schedule-feedback--error">Bracket-only tournaments do not use pools. Use the Bracket and Matches tabs.</p>
              ) : !poolGroups.length ? (
                <p>No pool matches yet.</p>
              ) : (
                <>
                  {poolGroups.map(([poolName, poolRoundMatches]) => (
                    <section key={poolName} className="tournament-pool-block">
                      <div className="tournament-fixture-section__head">
                        <h3>{poolName}</h3>
                        <span>{poolRoundMatches.length} matches</span>
                      </div>
                      <div className="tournament-fixtures-table-wrap">
                        <table className="tournament-fixtures-table">
                          <thead>
                            <tr>
                              <th>Scheduled start (your time)</th>
                              <th>Match</th>
                              <th>Court</th>
                              <th>Status</th>
                              <th>Outcome</th>
                              {canViewTournamentActions ? <th>Action</th> : null}
                            </tr>
                          </thead>
                          <tbody>
                            {poolRoundMatches.map((match) => {
                              const scoreDone =
                                match.status === "completed" &&
                                match.team_a_score != null &&
                                match.team_b_score != null;
                              return (
                                <tr key={match.id}>
                                  <td>
                                    <TournamentStartCell
                                      iso={match.scheduled_time}
                                      endIso={match.scheduled_end_time}
                                    />
                                  </td>
                                  <td>
                                    {match.team_a_name} vs {match.team_b_name}
                                  </td>
                                  <td>{match.location || "—"}</td>
                                  <td>{match.status}</td>
                                  <td>
                                    <MatchOutcomeLines match={match} compact />
                                  </td>
                                  {canViewTournamentActions ? (
                                    <td>
                                      {scoreDone ? (
                                        "—"
                                      ) : (
                                        <span className="tournament-row-actions">
                                          {canEditMatchSchedule(match) ? (
                                            <button
                                              type="button"
                                              className="tournament-history-btn"
                                              onClick={() => openScheduleEdit(match)}
                                              disabled={busy}
                                            >
                                              Edit schedule
                                            </button>
                                          ) : null}
                                          {canEnterResultForMatch(match) ? (
                                            <button
                                              type="button"
                                              className="tournament-history-btn"
                                              onClick={() => openResultForm(match)}
                                              disabled={busy}
                                            >
                                              Enter result
                                            </button>
                                          ) : null}
                                          {!canEditMatchSchedule(match) && !canEnterResultForMatch(match) ? "—" : null}
                                        </span>
                                      )}
                                    </td>
                                  ) : null}
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </section>
                  ))}
                  <div className="tournament-pool-standings">
                    <h3 className="tournament-pool-standings__title">Pool standings & rankings</h3>
                    {!standings.length ? (
                      <p>No standings yet. Generate pools and enter some results.</p>
                    ) : (
                      <>
                        {selectedTournament && Number(selectedTournament.top_teams_advance_per_pool) > 0 ? (
                          <p className="tournament-pool-standings__rule">
                            Top {selectedTournament.top_teams_advance_per_pool} advance
                            {selectedTournament.format === "pool_only" ? " (standings are final; no bracket)" : ""}
                          </p>
                        ) : null}
                        {standings.map((pool) => (
                        <section key={pool.pool_id} className="tournament-fixture-section">
                          <div className="tournament-fixture-section__head">
                            <h3>{pool.pool_name}</h3>
                          </div>
                          <div className="tournament-fixtures-table-wrap">
                            <table className="tournament-fixtures-table tournament-fixtures-table--matches tournament-fixtures-table--standings">
                              <thead>
                                <tr>
                                  <th className="tournament-standings-col-rank">Order</th>
                                  <th>W</th>
                                  <th>L</th>
                                  <th>Pts</th>
                                  <th>PD</th>
                                </tr>
                              </thead>
                              <tbody>
                                {pool.rows.map((row) => (
                                  <tr
                                    key={row.team_id}
                                    className={row.advances ? "standing-row--qualified" : "standing-row--eliminated"}
                                  >
                                    <td className="tournament-standings-order-cell">
                                      <span className="tournament-standings-order">
                                        {row.rank}. {row.team_name}{" "}
                                        <span className="tournament-standings-order__fate">
                                          {row.advances ? "— Qualified" : "— Eliminated"}
                                        </span>
                                      </span>
                                    </td>
                                    <td>{row.wins}</td>
                                    <td>{row.losses}</td>
                                    <td>{row.points}</td>
                                    <td>{row.point_difference}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </section>
                        ))}
                      </>
                    )}
                  </div>
                </>
              )}
            </div>
          ) : null}

          {tab === "bracket" ? (
            <div className="tournament-v2-scroll tournament-v2-bracket">
              {!bracketRounds.length ? (
                <div className="tournament-bracket-empty">
                  {bracketEmptyLines.map((line, idx) => (
                    <p key={idx} className="tournament-bracket-empty__line">
                      {line}
                    </p>
                  ))}
                </div>
              ) : bracketRoundsDisplayOrder.map((round) => (
                <section key={round.name} className="tournament-fixture-section">
                  <div className="tournament-fixture-section__head"><h3>{round.name}</h3><span>{round.matches.length} matches</span></div>
                  {round.matches.map((match) => {
                    const resolved = matches.find((m) => Number(m.id) === Number(match.id)) || match;
                    const scoreDone =
                      resolved.status === "completed" &&
                      resolved.team_a_score != null &&
                      resolved.team_b_score != null;
                    const aWin = scoreDone && resolved.winner_team_id && resolved.winner_team_id === resolved.team_a_id;
                    const bWin = scoreDone && resolved.winner_team_id && resolved.winner_team_id === resolved.team_b_id;
                    const aOut = scoreDone && resolved.loser_team_id && resolved.loser_team_id === resolved.team_a_id;
                    const bOut = scoreDone && resolved.loser_team_id && resolved.loser_team_id === resolved.team_b_id;
                    const bracketWait = getBracketWaitMessage(resolved, matches);
                    const advanceBlurb = getAdvanceBlurb(resolved, matchById);
                    const sched = formatBracketWhenWhereLine(resolved, selectedTournament);
                    return (
                    <article
                      key={match.id}
                      className={`tournament-summary-card tournament-summary-card--bracket${scoreDone ? " is-finished" : ""}`}
                    >
                      <p className="tournament-bracket-card__id">Match {resolved.match_number}</p>
                      <div className="tournament-bracket-teams" aria-label="Competitors">
                        <div
                          className={`tournament-bracket-teams__side${
                            aWin ? " is-winner" : ""}${aOut ? " is-eliminated" : ""}`}
                        >
                          {resolved.team_a_name || "TBD"}
                        </div>
                        <span className="tournament-bracket-teams__vs">vs</span>
                        <div
                          className={`tournament-bracket-teams__side${
                            bWin ? " is-winner" : ""}${bOut ? " is-eliminated" : ""}`}
                        >
                          {resolved.team_b_name || "TBD"}
                        </div>
                      </div>
                      {resolved.bracket_round ? (
                        <p className="tournament-bracket-card__round-name">{resolved.bracket_round}</p>
                      ) : null}
                      {sched.when ? (
                        <p className="tournament-bracket-card__when">{sched.when}</p>
                      ) : (
                        <p className="tournament-bracket-card__when tournament-bracket-card__when--missing">
                          Time not set — use Matches tab or edit schedule
                        </p>
                      )}
                      {sched.where ? <p className="tournament-bracket-card__where">{sched.where}</p> : null}
                      {!(bracketWait && resolved.status !== "completed") && resolved.status === "scheduled" && !scoreDone ? (
                        <p className="tournament-bracket-card__status">Status: Not played yet</p>
                      ) : null}
                      <MatchOutcomeLines
                        match={resolved}
                        bracketWait={bracketWait}
                        advanceBlurb={advanceBlurb}
                        showWaitPairLine={false}
                      />
                      {canViewTournamentActions ? (
                        <div className="tournament-bracket-card__action tournament-bracket-card__action--row">
                          {scoreDone ? (
                            <span className="tournament-bracket-card__action-note">Result final</span>
                          ) : (
                            <span className="tournament-bracket-card__action-buttons">
                              {canEditMatchSchedule(resolved) ? (
                                <button
                                  type="button"
                                  className="tournament-history-btn"
                                  onClick={() => openScheduleEdit(resolved)}
                                  disabled={busy}
                                >
                                  Edit schedule
                                </button>
                              ) : null}
                              {canEnterResultForMatch(resolved) ? (
                                <button
                                  type="button"
                                  className="tournament-history-btn"
                                  onClick={() => openResultForm(resolved)}
                                  disabled={busy}
                                >
                                  Enter result
                                </button>
                              ) : !canEditMatchSchedule(resolved) && !canEnterResultForMatch(resolved) ? (
                                <span className="tournament-bracket-card__result-muted">—</span>
                              ) : null}
                            </span>
                          )}
                        </div>
                      ) : null}
                    </article>
                    );
                  })}
                </section>
              ))}
            </div>
          ) : null}

        </main>
      </div>
    </section>
  );
}
