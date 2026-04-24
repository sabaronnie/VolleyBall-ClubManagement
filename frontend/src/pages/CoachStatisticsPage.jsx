import { useEffect, useMemo, useState } from "react";
import { searchCoachPlayers } from "../api";
import { navigate } from "../navigation";

export default function CoachStatisticsPage({ coachedTeams = [], activeTeamId = "" }) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(false);

  const hasMultipleTeams = coachedTeams.length > 1;
  const defaultTeamValue = hasMultipleTeams ? "__all__" : String(coachedTeams[0]?.id || "");
  const selectedTeamValue = useMemo(() => {
    if (!coachedTeams.length) {
      return "";
    }
    if (String(activeTeamId) === "__all__" && hasMultipleTeams) {
      return "__all__";
    }
    const isActiveTeamCoached = coachedTeams.some((team) => String(team.id) === String(activeTeamId));
    if (isActiveTeamCoached) {
      return String(activeTeamId);
    }
    return defaultTeamValue;
  }, [activeTeamId, coachedTeams, defaultTeamValue, hasMultipleTeams]);

  useEffect(() => {
    setResults([]);
    setError("");
    setSearched(false);
  }, [selectedTeamValue]);

  const onSubmitSearch = async (event) => {
    event.preventDefault();
    const trimmedQuery = query.trim();
    setSearched(true);
    setError("");
    if (!trimmedQuery) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const payload = await searchCoachPlayers(trimmedQuery, {
        teamId: selectedTeamValue,
        limit: 25,
      });
      setResults(Array.isArray(payload?.results) ? payload.results : []);
    } catch (err) {
      setResults([]);
      setError(err.message || "Could not search players.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="teams-page-shell">
      <header className="teams-page-header">
        <div className="teams-page-heading">
          <p className="teams-page-kicker">Coaching</p>
          <h1>Statistics</h1>
          <p className="teams-page-subtitle">
            Search players in your coached teams and open their performance profile.
          </p>
        </div>
      </header>

      {!coachedTeams.length ? (
        <section className="schedule-empty-card">
          <h2>No coached teams</h2>
          <p>Only coaches and directors with team access can use the Statistics search flow.</p>
        </section>
      ) : (
        <section className="vc-panel">
          <h2 className="vc-panel-title" style={{ fontSize: "1.05rem" }}>Find a player</h2>
          <form onSubmit={onSubmitSearch} style={{ display: "grid", gap: "0.75rem", marginTop: "0.5rem" }}>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "0.6rem",
                width: "100%",
                maxWidth: "46rem",
                alignItems: "center",
              }}
            >
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by player name"
                className="vc-director-modal__select"
                style={{ minHeight: "2.65rem", flex: "1 1 24rem" }}
              />
              <button
                type="submit"
                className="team-card__button"
                disabled={loading}
                style={{ minWidth: "9.5rem", minHeight: "2.65rem", padding: "0.65rem 1.15rem" }}
              >
                {loading ? "Searching..." : "Search"}
              </button>
            </div>
          </form>

          {error ? <p className="vc-modal__error" style={{ marginTop: "0.9rem" }}>{error}</p> : null}
          {!error && searched && !loading && query.trim() && !results.length ? (
            <p className="vc-modal__muted" style={{ marginTop: "0.9rem" }}>No matching players were found.</p>
          ) : null}

          {results.length ? (
            <div style={{ overflowX: "auto", marginTop: "0.95rem" }}>
              <table className="vc-table" style={{ width: "100%" }}>
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Email</th>
                    <th>Team</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((row) => (
                    <tr key={`${row.team_id}-${row.player_id}`}>
                      <td>{row.player_name || "Player"}</td>
                      <td>{row.email || "—"}</td>
                      <td>{row.team_name || "—"}</td>
                      <td>
                        <button
                          type="button"
                          className="team-card__button team-card__button--ghost"
                          onClick={() =>
                            navigate(
                              `/coach/player-search?team=${encodeURIComponent(String(row.team_id))}&player=${encodeURIComponent(String(row.player_id))}`,
                            )
                          }
                        >
                          View Performance
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      )}
    </section>
  );
}
