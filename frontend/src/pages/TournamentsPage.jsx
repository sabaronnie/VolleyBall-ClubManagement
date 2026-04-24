import { useEffect, useMemo, useState } from "react";
import {
  createClubTournament,
  deleteClubTournament,
  fetchClubTournamentDetail,
  fetchClubTournaments,
  fetchCurrentUser,
} from "../api";

const TOURNAMENT_TYPE_OPTIONS = [
  { value: "pools", label: "Round-robin pools" },
  { value: "bracket", label: "Elimination bracket" },
  { value: "hybrid", label: "Pools + bracket" },
];

const SCORING_FORMAT_OPTIONS = [
  "Best of 3 to 25",
  "Best of 5 to 25",
  "Single set to 21",
];

function todayIso() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function fixtureHomeLabel(fixture) {
  return fixture.home_team?.name || fixture.placeholder_home_label || "TBD";
}

function fixtureAwayLabel(fixture) {
  return fixture.away_team?.name || fixture.placeholder_away_label || "TBD";
}

function stageSectionLabel(fixture) {
  if (fixture.stage_type === "pool") {
    return fixture.pool_name ? `${fixture.pool_name} Fixtures` : "Pool Fixtures";
  }
  return "Bracket Fixtures";
}

export default function TournamentsPage({ activeTeam = null }) {
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedClubId, setSelectedClubId] = useState("");
  const [workspace, setWorkspace] = useState(null);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [workspaceError, setWorkspaceError] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [selectedTournamentId, setSelectedTournamentId] = useState(null);
  const [selectedTournament, setSelectedTournament] = useState(null);
  const [createBusy, setCreateBusy] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createSuccess, setCreateSuccess] = useState("");
  const [roundFilter, setRoundFilter] = useState("all");
  const [name, setName] = useState("Spring Club Tournament");
  const [tournamentType, setTournamentType] = useState("pools");
  const [poolCount, setPoolCount] = useState("2");
  const [teamsPerPool, setTeamsPerPool] = useState("2");
  const [teamsQualifyingPerPool, setTeamsQualifyingPerPool] = useState("1");
  const [matchDurationMinutes, setMatchDurationMinutes] = useState("90");
  const [scoringFormat, setScoringFormat] = useState(SCORING_FORMAT_OPTIONS[0]);
  const [startDate, setStartDate] = useState(todayIso());
  const [startTime, setStartTime] = useState("18:00");
  const [venue, setVenue] = useState("");
  const [selectedTeamIds, setSelectedTeamIds] = useState([]);

  useEffect(() => {
    let cancelled = false;
    const loadMe = async () => {
      setLoading(true);
      setError("");
      try {
        const data = await fetchCurrentUser();
        if (cancelled) return;
        const ownedClubs = data?.owned_clubs || [];
        setMe(data);
        const preferredClubId =
          ownedClubs.find((club) => Number(club.id) === Number(activeTeam?.clubId))?.id ||
          ownedClubs[0]?.id ||
          "";
        setSelectedClubId(String(preferredClubId || ""));
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Could not load account.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    void loadMe();
    return () => {
      cancelled = true;
    };
  }, [activeTeam?.clubId]);

  useEffect(() => {
    if (!selectedClubId) {
      setWorkspace(null);
      setSelectedTournament(null);
      setSelectedTournamentId(null);
      return;
    }
    let cancelled = false;
    const loadWorkspace = async () => {
      setWorkspaceLoading(true);
      setWorkspaceError("");
      try {
        const data = await fetchClubTournaments(selectedClubId);
        if (cancelled) return;
        setWorkspace(data);
        const availableTeams = data?.available_teams || [];
        const currentSelection = selectedTeamIds.filter((id) =>
          availableTeams.some((team) => Number(team.id) === Number(id)),
        );
        setSelectedTeamIds(currentSelection);
        if (!venue && data?.club?.city) {
          setVenue(`${data.club.city} Arena`);
        }
        const preferredTournament = data?.current_tournament || null;
        setSelectedTournament(preferredTournament);
        setSelectedTournamentId(preferredTournament?.id || null);
      } catch (err) {
        if (!cancelled) {
          setWorkspace(null);
          setWorkspaceError(err.message || "Could not load tournaments.");
        }
      } finally {
        if (!cancelled) {
          setWorkspaceLoading(false);
        }
      }
    };
    void loadWorkspace();
    return () => {
      cancelled = true;
    };
  }, [selectedClubId]);

  useEffect(() => {
    if (!selectedClubId || !selectedTournamentId) {
      setSelectedTournament((current) =>
        current && Number(current.id) === Number(selectedTournamentId) ? current : null,
      );
      setDetailError("");
      return;
    }

    if (workspace?.current_tournament && Number(workspace.current_tournament.id) === Number(selectedTournamentId)) {
      setSelectedTournament(workspace.current_tournament);
      setDetailError("");
      return;
    }

    let cancelled = false;
    const loadTournamentDetail = async () => {
      setDetailLoading(true);
      setDetailError("");
      try {
        const data = await fetchClubTournamentDetail(selectedClubId, selectedTournamentId);
        if (cancelled) return;
        setSelectedTournament(data?.tournament || null);
      } catch (err) {
        if (!cancelled) {
          setDetailError(err.message || "Could not load tournament detail.");
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    };
    void loadTournamentDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedClubId, selectedTournamentId, workspace?.current_tournament]);

  const ownedClubs = me?.owned_clubs || [];
  const availableTeams = workspace?.available_teams || [];
  const currentTournament = workspace?.current_tournament || null;
  const tournamentHistory = workspace?.tournaments || [];
  const displayedTournament = selectedTournament || currentTournament || null;
  const roundOptions = displayedTournament?.available_rounds || [];
  const selectedTeamCount = selectedTeamIds.length;
  const expectedPoolTeamCount =
    tournamentType === "bracket" ? 0 : Number(poolCount || 0) * Number(teamsPerPool || 0);
  const selectedTeams = availableTeams.filter((team) =>
    selectedTeamIds.some((id) => Number(id) === Number(team.id)),
  );
  const hasOngoingTournament = Boolean(currentTournament);
  const isViewingCurrentTournament =
    displayedTournament && currentTournament && Number(displayedTournament.id) === Number(currentTournament.id);

  useEffect(() => {
    if (!displayedTournament) {
      setRoundFilter("all");
      return;
    }
    const stillExists =
      roundFilter === "all" ||
      roundOptions.some((row) => String(row.round_number) === String(roundFilter));
    if (!stillExists) {
      setRoundFilter("all");
    }
  }, [displayedTournament, roundFilter, roundOptions]);

  useEffect(() => {
    if (tournamentType !== "hybrid") {
      return;
    }
    const maxQualifiers = Math.max(Number(teamsPerPool || 0), 1);
    if (Number(teamsQualifyingPerPool || 0) > maxQualifiers) {
      setTeamsQualifyingPerPool(String(maxQualifiers));
    }
  }, [teamsPerPool, teamsQualifyingPerPool, tournamentType]);

  const filteredFixtures = useMemo(() => {
    if (!displayedTournament?.fixtures) {
      return [];
    }
    if (roundFilter === "all") {
      return displayedTournament.fixtures;
    }
    return displayedTournament.fixtures.filter(
      (fixture) => String(fixture.round_number) === String(roundFilter),
    );
  }, [displayedTournament, roundFilter]);

  const fixtureSections = useMemo(() => {
    if (!filteredFixtures.length) {
      return [];
    }
    const grouped = new Map();
    filteredFixtures.forEach((fixture) => {
      const key = `${fixture.stage_type}:${fixture.pool_name || "none"}`;
      if (!grouped.has(key)) {
        grouped.set(key, {
          key,
          label: stageSectionLabel(fixture),
          fixtures: [],
        });
      }
      grouped.get(key).fixtures.push(fixture);
    });
    return Array.from(grouped.values());
  }, [filteredFixtures]);

  const toggleTeam = (teamId) => {
    setSelectedTeamIds((current) =>
      current.some((id) => Number(id) === Number(teamId))
        ? current.filter((id) => Number(id) !== Number(teamId))
        : [...current, Number(teamId)],
    );
  };

  const onSelectTournament = (tournamentId) => {
    setSelectedTournamentId(Number(tournamentId));
    setCreateSuccess("");
    setCreateError("");
  };

  const onViewCurrentTournament = () => {
    if (!currentTournament?.id) {
      return;
    }
    setSelectedTournamentId(currentTournament.id);
    setSelectedTournament(currentTournament);
    setDetailError("");
  };

  const onCreateTournament = async (event) => {
    event.preventDefault();
    if (!selectedClubId) {
      setCreateError("Choose a club first.");
      return;
    }
    if (!selectedTeamCount || selectedTeamCount < 2) {
      setCreateError("Select at least two teams to create a tournament.");
      return;
    }
    if (tournamentType !== "bracket" && expectedPoolTeamCount !== selectedTeamCount) {
      setCreateError("Selected teams must equal number of pools multiplied by teams per pool.");
      return;
    }
    if (
      tournamentType === "hybrid" &&
      (Number(teamsQualifyingPerPool || 0) < 1 ||
        Number(teamsQualifyingPerPool || 0) > Number(teamsPerPool || 0))
    ) {
      setCreateError("Qualified teams per pool must be between 1 and the teams per pool count.");
      return;
    }
    setCreateBusy(true);
    setCreateError("");
    setCreateSuccess("");
    try {
      const payload = {
        name,
        tournament_type: tournamentType,
        team_ids: selectedTeamIds,
        number_of_teams: selectedTeamCount,
        pool_count: tournamentType === "bracket" ? 0 : Number(poolCount || 0),
        teams_per_pool: tournamentType === "bracket" ? 0 : Number(teamsPerPool || 0),
        teams_qualifying_per_pool:
          tournamentType === "hybrid" ? Number(teamsQualifyingPerPool || 0) : 0,
        match_duration_minutes: Number(matchDurationMinutes || 0),
        scoring_format: scoringFormat,
        start_date: startDate,
        start_time: startTime,
        venue,
      };
      const data = await createClubTournament(selectedClubId, payload);
      setCreateSuccess(data?.message || "Tournament created.");
      setWorkspace((current) => ({
        ...(current || {}),
        current_tournament: data?.tournament || null,
        tournaments: data?.tournament
          ? [
              {
                id: data.tournament.id,
                name: data.tournament.name,
                tournament_type: data.tournament.tournament_type,
                tournament_type_label: data.tournament.tournament_type_label,
                created_at: data.tournament.created_at,
                number_of_teams: data.tournament.number_of_teams,
                status: data.tournament.status,
                status_label: data.tournament.status_label,
              },
              ...((current?.tournaments || []).filter(
                (row) => Number(row.id) !== Number(data.tournament.id),
              )),
            ]
          : current?.tournaments || [],
      }));
      setSelectedTournament(data?.tournament || null);
      setSelectedTournamentId(data?.tournament?.id || null);
    } catch (err) {
      setCreateError(err.message || "Could not create tournament.");
    } finally {
      setCreateBusy(false);
    }
  };

  const onDeleteTournament = async () => {
    if (!selectedClubId || !currentTournament?.id) {
      return;
    }
    const confirmed = window.confirm(
      "Cancel this tournament and remove all of its matches from team schedules and sessions?",
    );
    if (!confirmed) {
      return;
    }
    setDeleteBusy(true);
    setCreateError("");
    setCreateSuccess("");
    try {
      const data = await deleteClubTournament(selectedClubId, currentTournament.id);
      setCreateSuccess(data?.message || "Tournament cancelled.");
      setWorkspace((current) => {
        if (!current) {
          return current;
        }
        const cancelledTournament = data?.tournament || null;
        return {
          ...current,
          current_tournament: null,
          tournaments: cancelledTournament
            ? (current.tournaments || []).map((row) =>
                Number(row.id) === Number(cancelledTournament.id)
                  ? {
                      ...row,
                      status: cancelledTournament.status,
                      status_label: cancelledTournament.status_label,
                    }
                  : row,
              )
            : current.tournaments || [],
        };
      });
      setSelectedTournament(data?.tournament || null);
      setSelectedTournamentId(data?.tournament?.id || null);
      setRoundFilter("all");
    } catch (err) {
      setCreateError(err.message || "Could not cancel tournament.");
    } finally {
      setDeleteBusy(false);
    }
  };

  if (loading) {
    return (
      <section className="teams-page-shell" style={{ padding: "1.5rem" }}>
        <p className="vc-modal__muted">Loading tournaments...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="teams-page-shell" style={{ padding: "1.5rem" }}>
        <p className="schedule-feedback schedule-feedback--error">{error}</p>
      </section>
    );
  }

  if (!ownedClubs.length) {
    return (
      <section className="teams-page-shell" style={{ padding: "1.5rem" }}>
        <h1 style={{ fontSize: "1.2rem" }}>Tournaments</h1>
        <p className="vc-modal__muted" style={{ marginTop: "0.75rem" }}>
          Only club directors can create tournaments.
        </p>
      </section>
    );
  }

  return (
    <section className="teams-page-shell">
      <header className="teams-page-header">
        <div className="teams-page-heading">
          <p className="teams-page-kicker">Tournament Center</p>
          <h1>Create and track club tournaments</h1>
          <p className="teams-page-subtitle">
            Generate pool play, elimination brackets, or both. Tournament-created matches use the
            existing session system so they appear in team events and team schedules automatically.
          </p>
        </div>
      </header>

      <section className="tournament-page-grid">
        <form className="tournament-form-card" onSubmit={onCreateTournament}>
          <div className="tournament-form-card__head">
            <div>
              <p className="teams-page-kicker" style={{ fontSize: "0.72rem", marginBottom: "0.2rem" }}>
                Create Tournament
              </p>
              <h2>Setup</h2>
            </div>
          </div>

          {createError ? <p className="schedule-feedback schedule-feedback--error">{createError}</p> : null}
          {createSuccess ? <p className="vc-director-success">{createSuccess}</p> : null}
          {workspaceError ? <p className="schedule-feedback schedule-feedback--error">{workspaceError}</p> : null}
          {hasOngoingTournament ? (
            <div className="tournament-inline-notice">
              <strong>Current tournament already exists.</strong>
              <span>
                Review the generated fixtures on the right. Creating another tournament is blocked
                until the ongoing one ends or is cancelled.
              </span>
            </div>
          ) : null}

          <div className="tournament-form-grid">
            <label>
              <span>Club</span>
              <select value={selectedClubId} onChange={(event) => setSelectedClubId(event.target.value)}>
                {ownedClubs.map((club) => (
                  <option key={club.id} value={club.id}>
                    {club.name}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span>Tournament name</span>
              <input value={name} onChange={(event) => setName(event.target.value)} />
            </label>

            <label>
              <span>Tournament type</span>
              <select value={tournamentType} onChange={(event) => setTournamentType(event.target.value)}>
                {TOURNAMENT_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span>Number of teams</span>
              <input type="number" min="0" value={selectedTeamCount} readOnly />
            </label>

            {tournamentType !== "bracket" ? (
              <>
                <label>
                  <span>Number of pools</span>
                  <input
                    type="number"
                    min="1"
                    value={poolCount}
                    onChange={(event) => setPoolCount(event.target.value)}
                  />
                </label>

                <label>
                  <span>Teams per pool</span>
                  <input
                    type="number"
                    min="2"
                    value={teamsPerPool}
                    onChange={(event) => setTeamsPerPool(event.target.value)}
                  />
                </label>

                {tournamentType === "hybrid" ? (
                  <label>
                    <span>Teams qualifying per pool</span>
                    <input
                      type="number"
                      min="1"
                      max={Math.max(Number(teamsPerPool || 0), 1)}
                      value={teamsQualifyingPerPool}
                      onChange={(event) => setTeamsQualifyingPerPool(event.target.value)}
                    />
                  </label>
                ) : null}
              </>
            ) : null}

            <label>
              <span>Match duration (minutes)</span>
              <input
                type="number"
                min="15"
                value={matchDurationMinutes}
                onChange={(event) => setMatchDurationMinutes(event.target.value)}
              />
            </label>

            <label>
              <span>Scoring format</span>
              <select value={scoringFormat} onChange={(event) => setScoringFormat(event.target.value)}>
                {SCORING_FORMAT_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span>Start date</span>
              <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            </label>

            <label>
              <span>Start time</span>
              <input type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
            </label>

            <label className="tournament-form-grid__full">
              <span>Venue</span>
              <input value={venue} onChange={(event) => setVenue(event.target.value)} />
            </label>
          </div>

          <div className="tournament-team-picker">
            <div className="tournament-team-picker__head">
              <strong>Teams</strong>
              <span>{selectedTeamCount} selected</span>
            </div>
            {workspaceLoading ? (
              <p className="vc-modal__muted">Loading teams...</p>
            ) : availableTeams.length ? (
              <div className="tournament-team-picker__list">
                {availableTeams.map((team) => {
                  const checked = selectedTeamIds.some((id) => Number(id) === Number(team.id));
                  return (
                    <label key={team.id} className={`tournament-team-chip${checked ? " is-selected" : ""}`}>
                      <input type="checkbox" checked={checked} onChange={() => toggleTeam(team.id)} />
                      <span>{team.name}</span>
                    </label>
                  );
                })}
              </div>
            ) : (
              <p className="vc-modal__muted">No active teams found in this club yet.</p>
            )}
            {tournamentType !== "bracket" && expectedPoolTeamCount !== selectedTeamCount ? (
              <p className="vc-modal__muted" style={{ marginTop: "0.75rem", color: "#b42318" }}>
                Pool setup expects {expectedPoolTeamCount || 0} teams, but {selectedTeamCount} are
                currently selected.
              </p>
            ) : null}
            {selectedTeams.length ? (
              <div className="tournament-selected-teams">
                {selectedTeams.map((team) => (
                  <span key={team.id} className="tournament-selected-team-pill">
                    {team.name}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <div className="tournament-form-card__actions">
            <button
              type="submit"
              className="vc-action-btn"
              disabled={createBusy || workspaceLoading || hasOngoingTournament}
            >
              {createBusy ? "Generating..." : "Create tournament"}
            </button>
          </div>
        </form>

        <section className="tournament-view-card">
          <div className="tournament-view-card__head">
            <div>
              <p className="teams-page-kicker" style={{ fontSize: "0.72rem", marginBottom: "0.2rem" }}>
                Tournament View
              </p>
              <h2>{displayedTournament ? displayedTournament.name : "No tournament yet"}</h2>
            </div>
            {displayedTournament ? (
              <div className="tournament-view-card__controls">
                <select value={roundFilter} onChange={(event) => setRoundFilter(event.target.value)}>
                  <option value="all">All rounds</option>
                  {roundOptions.map((option) => (
                    <option key={option.round_number} value={option.round_number}>
                      {option.round_label}
                    </option>
                  ))}
                </select>
                {currentTournament && !isViewingCurrentTournament ? (
                  <button type="button" className="tournament-history-btn" onClick={onViewCurrentTournament}>
                    View current
                  </button>
                ) : null}
                {isViewingCurrentTournament ? (
                  <button
                    type="button"
                    className="tournament-delete-btn"
                    onClick={onDeleteTournament}
                    disabled={deleteBusy}
                  >
                    {deleteBusy ? "Cancelling..." : "Delete tournament"}
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>

          {detailError ? <p className="schedule-feedback schedule-feedback--error">{detailError}</p> : null}

          {displayedTournament ? (
            <>
              {detailLoading ? <p className="vc-modal__muted">Loading tournament detail...</p> : null}

              <div className="tournament-summary-grid">
                <div className="tournament-summary-card">
                  <span>Format</span>
                  <strong>{displayedTournament.tournament_type_label}</strong>
                </div>
                <div className="tournament-summary-card">
                  <span>Status</span>
                  <strong>{displayedTournament.status_label}</strong>
                </div>
                <div className="tournament-summary-card">
                  <span>Teams</span>
                  <strong>{displayedTournament.number_of_teams}</strong>
                </div>
                {displayedTournament.tournament_type === "hybrid" ? (
                  <div className="tournament-summary-card">
                    <span>Qualifiers</span>
                    <strong>{displayedTournament.teams_qualifying_per_pool} per pool</strong>
                  </div>
                ) : null}
                <div className="tournament-summary-card">
                  <span>Scoring</span>
                  <strong>{displayedTournament.scoring_format}</strong>
                </div>
              </div>

              <div className="tournament-roster-card">
                <div className="tournament-roster-card__head">
                  <strong>Participating teams</strong>
                  <span>{displayedTournament.teams.length}</span>
                </div>
                <div className="tournament-selected-teams">
                  {displayedTournament.teams.map((team) => (
                    <span key={team.id} className="tournament-selected-team-pill">
                      {team.name}
                    </span>
                  ))}
                </div>
              </div>

              <div className="tournament-fixture-sections">
                {displayedTournament.pool_standings?.length ? (
                  <section className="tournament-fixture-section">
                    <div className="tournament-fixture-section__head">
                      <h3>Pool standings</h3>
                      <span>{displayedTournament.pool_standings.length} pools</span>
                    </div>
                    <div className="tournament-fixtures-table-wrap">
                      <table className="tournament-fixtures-table">
                        <thead>
                          <tr>
                            <th>Pool</th>
                            <th>Rank</th>
                            <th>Team</th>
                            <th>W</th>
                            <th>L</th>
                            <th>PF</th>
                            <th>PA</th>
                            <th>Diff</th>
                            <th>Qualified</th>
                          </tr>
                        </thead>
                        <tbody>
                          {displayedTournament.pool_standings.flatMap((pool) =>
                            pool.teams.map((team) => (
                              <tr key={`${pool.pool_id}-${team.team_id}`}>
                                <td>{pool.pool_name}</td>
                                <td>{team.rank}</td>
                                <td>{team.team_name}</td>
                                <td>{team.wins}</td>
                                <td>{team.losses}</td>
                                <td>{team.points_for}</td>
                                <td>{team.points_against}</td>
                                <td>{team.point_differential}</td>
                                <td>{team.qualified ? "Yes" : "-"}</td>
                              </tr>
                            )),
                          )}
                        </tbody>
                      </table>
                    </div>
                  </section>
                ) : null}

                {fixtureSections.map((section) => (
                  <section key={section.key} className="tournament-fixture-section">
                    <div className="tournament-fixture-section__head">
                      <h3>{section.label}</h3>
                      <span>{section.fixtures.length} matches</span>
                    </div>
                    <div className="tournament-fixtures-table-wrap">
                      <table className="tournament-fixtures-table">
                        <thead>
                          <tr>
                            <th>Round</th>
                            <th>Stage</th>
                            <th>Pool</th>
                            <th>Match</th>
                            <th>Winner</th>
                            <th>Date</th>
                            <th>Time</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {section.fixtures.map((fixture) => (
                            <tr key={fixture.id}>
                              <td>{fixture.round_label}</td>
                              <td>{fixture.stage_type_label}</td>
                              <td>{fixture.pool_name || "-"}</td>
                              <td>
                                {fixtureHomeLabel(fixture)} vs {fixtureAwayLabel(fixture)}
                              </td>
                              <td>{fixture.winner_name || "-"}</td>
                              <td>{fixture.scheduled_date || "TBD"}</td>
                              <td>{fixture.start_time || "TBD"}</td>
                              <td>
                                {fixture.display_status || "placeholder"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                ))}
              </div>
            </>
          ) : (
            <>
              <section className="schedule-empty-card" style={{ marginTop: "1rem" }}>
                <h2>No tournament yet</h2>
                <p>Create one from the form to generate fixtures and publish tournament matches into team events.</p>
              </section>
              {tournamentHistory.length ? (
                <div className="tournament-history-card" style={{ marginTop: "1rem" }}>
                  <div className="tournament-history-card__head">
                    <strong>Tournament history</strong>
                    <span>{tournamentHistory.length}</span>
                  </div>
                  <div className="tournament-history-list">
                    {tournamentHistory.map((tournament) => (
                      <button
                        key={tournament.id}
                        type="button"
                        className="tournament-history-item tournament-history-item--button"
                        onClick={() => onSelectTournament(tournament.id)}
                      >
                        <div className="tournament-history-item__head">
                          <strong>{tournament.name}</strong>
                          <span
                            className={`tournament-status-pill${
                              tournament.status === "cancelled" ? " is-cancelled" : ""
                            }`}
                          >
                            {tournament.status_label || tournament.status}
                          </span>
                        </div>
                        <span>
                          {tournament.tournament_type_label} {"\u2022"} {tournament.number_of_teams} teams
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          )}

          {displayedTournament && tournamentHistory.length ? (
            <div className="tournament-history-card">
              <div className="tournament-history-card__head">
                <strong>Recent tournaments</strong>
                <span>{tournamentHistory.length}</span>
              </div>
              <div className="tournament-history-list">
                {tournamentHistory.map((tournament) => (
                  <button
                    key={tournament.id}
                    type="button"
                    className={`tournament-history-item tournament-history-item--button${
                      Number(displayedTournament.id) === Number(tournament.id) ? " is-selected" : ""
                    }`}
                    onClick={() => onSelectTournament(tournament.id)}
                  >
                    <div className="tournament-history-item__head">
                      <strong>{tournament.name}</strong>
                      <span
                        className={`tournament-status-pill${
                          tournament.status === "cancelled" ? " is-cancelled" : ""
                        }`}
                      >
                        {tournament.status_label || tournament.status}
                      </span>
                    </div>
                    <span>
                      {tournament.tournament_type_label} {"\u2022"} {tournament.number_of_teams} teams
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </section>
      </section>
    </section>
  );
}
