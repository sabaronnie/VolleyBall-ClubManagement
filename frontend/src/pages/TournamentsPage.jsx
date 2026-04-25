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
  submitTournamentMatchResult,
} from "../api";

const TABS = ["setup", "pools", "bracket", "standings"];
const FORMATS = [
  { value: "pool_only", label: "Pool Play" },
  { value: "bracket_only", label: "Bracket" },
  { value: "pool_and_bracket", label: "Pool + Bracket" },
];

export default function TournamentsPage() {
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [tab, setTab] = useState("pools");
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
    format: "pool_and_bracket",
    number_of_pools: 2,
    teams_per_pool: 4,
    top_teams_advance_per_pool: 2,
    tie_break_rule: "wins, head-to-head, point_difference, points_for, random",
    club_id: "",
  });

  const canManage = Boolean(me?.is_director_or_staff || me?.viewer_is_staff);
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
  const poolMatchesComplete = useMemo(
    () => matches.filter((row) => row.pool_id).every((row) => row.status === "completed"),
    [matches],
  );
  const canGenerateBracket = Boolean(
    canManage &&
      selectedTournament &&
      selectedTournament.format !== "pool_only" &&
      matches.filter((row) => row.pool_id).length > 0 &&
      poolMatchesComplete,
  );

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
      setTab("pools");
    }
  }, [canManage, tab]);

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
      setTab("pools");
      setMessage("Tournament created with pools and pool matches generated.");
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
      setMessage("Action completed.");
    } catch (err) {
      setError(err.message || "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function enterResult(match) {
    const scoreA = window.prompt(`Score for ${match.team_a_name || "Team A"}`);
    const scoreB = window.prompt(`Score for ${match.team_b_name || "Team B"}`);
    if (scoreA == null || scoreB == null) return;
    setBusy(true);
    try {
      await submitTournamentMatchResult(match.id, { team_a_score: Number(scoreA), team_b_score: Number(scoreB) });
      await refreshAll(selectedTournamentId);
      setMessage("Result entered.");
    } catch (err) {
      setError(err.message || "Could not enter result.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <section className="teams-page-shell"><p>Loading tournaments...</p></section>;

  const myMatchIds = new Set(myMatches.map((row) => row.id));
  const poolMatches = matches.filter((row) => row.pool_id);

  return (
    <section className="teams-page-shell tournament-v2-shell">
      <header className="teams-page-header">
        <div className="teams-page-heading">
          <p className="teams-page-kicker">Tournament Center</p>
          <h1>Tournament Setup, Pools, Bracket, Standings</h1>
        </div>
      </header>

      {error ? <p className="schedule-feedback schedule-feedback--error">{error}</p> : null}
      {message ? <p className="vc-director-success">{message}</p> : null}

      <div className="tournament-flow-tabs">
        {(canManage ? TABS : TABS.filter((item) => item !== "setup")).map((item) => (
          <button key={item} type="button" className={`tournament-flow-tab${tab === item ? " is-active" : ""}`} onClick={() => setTab(item)}>
            {item[0].toUpperCase() + item.slice(1)}
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
          {tab === "setup" ? (
            <form className="tournament-form-grid" onSubmit={createNewTournament}>
              <label><span>Name</span><input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
              <label><span>Location</span><input value={form.location} onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))} /></label>
              <label><span>Start Date</span><input type="date" value={form.start_date} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} /></label>
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
                  title={submitBlockReason || "Create tournament, generate pools, and generate pool matches"}
                >
                  Generate Tournament
                </button>
                <button
                  type="button"
                  className="tournament-history-btn"
                  disabled={!canGenerateBracket || busy}
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

          {tab === "pools" ? (
            <div className="tournament-v2-scroll">
              {!poolMatches.length ? <p>No pool matches yet.</p> : (
                <div className="tournament-fixtures-table-wrap">
                  <table className="tournament-fixtures-table">
                    <thead><tr><th>Pool</th><th>Match</th><th>Time</th><th>Court</th><th>Status</th><th>Action</th></tr></thead>
                    <tbody>
                      {poolMatches.map((match) => (
                        <tr key={match.id}>
                          <td>{match.pool_name}</td>
                          <td>{match.team_a_name} vs {match.team_b_name}</td>
                          <td>{match.scheduled_time ? new Date(match.scheduled_time).toLocaleString() : "-"}</td>
                          <td>{match.location || "-"}</td>
                          <td>{match.status}</td>
                          <td>{(canManage || myMatchIds.has(match.id)) && match.status !== "completed" ? <button type="button" className="tournament-history-btn" onClick={() => enterResult(match)} disabled={busy}>Enter Result</button> : "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : null}

          {tab === "bracket" ? (
            <div className="tournament-v2-scroll tournament-v2-bracket">
              {!bracketRounds.length ? <p>Bracket will be available after pool matches are completed.</p> : bracketRounds.map((round) => (
                <section key={round.name} className="tournament-fixture-section">
                  <div className="tournament-fixture-section__head"><h3>{round.name}</h3><span>{round.matches.length} matches</span></div>
                  {round.matches.map((match) => (
                    <article key={match.id} className="tournament-summary-card">
                      <strong>{match.team_a_name || "TBD"} vs {match.team_b_name || "TBD"}</strong>
                      <span>{match.winner_team_name ? `Winner: ${match.winner_team_name}` : "Winner pending"}</span>
                    </article>
                  ))}
                </section>
              ))}
            </div>
          ) : null}

          {tab === "standings" ? (
            <div className="tournament-v2-scroll">
              {!standings.length ? <p>No standings available yet.</p> : standings.map((pool) => (
                <section key={pool.pool_id} className="tournament-fixture-section">
                  <div className="tournament-fixture-section__head"><h3>{pool.pool_name}</h3></div>
                  <div className="tournament-fixtures-table-wrap">
                    <table className="tournament-fixtures-table tournament-fixtures-table--matches">
                      <thead><tr><th>Rank</th><th>Team</th><th>W</th><th>L</th><th>Pts</th><th>PD</th><th>Advance</th></tr></thead>
                      <tbody>
                        {pool.rows.map((row) => (
                          <tr key={row.team_id}>
                            <td>{row.rank}</td>
                            <td>{row.team_name}</td>
                            <td>{row.wins}</td>
                            <td>{row.losses}</td>
                            <td>{row.points}</td>
                            <td>{row.point_difference}</td>
                            <td>{row.advances ? "Yes" : "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ))}
            </div>
          ) : null}
        </main>
      </div>
    </section>
  );
}
