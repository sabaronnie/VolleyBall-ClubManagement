import { useEffect, useState } from "react";
import { fetchTeamStandings } from "../api";

function statToneClass(value) {
  if (value > 0) return "is-positive";
  if (value < 0) return "is-negative";
  return "is-neutral";
}

export default function TeamStandingsCard({
  activeTeamId = "",
  title = "Team Standings",
  eyebrow = "Rankings",
  emptySelectionMessage = "Select a team in the focus dropdown to load standings.",
}) {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!activeTeamId || activeTeamId === "__all__") {
      setPayload(null);
      setLoading(false);
      setError("");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");

    void fetchTeamStandings(activeTeamId)
      .then((data) => {
        if (!cancelled) {
          setPayload(data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setPayload(null);
          setError(err.message || "Could not load standings.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeTeamId]);

  const standings = payload?.standings || null;

  return (
    <section className="vc-panel vc-panel--dashboard vc-panel--director-white vc-team-standings-card">
      <div className="vc-dashboard-panel-head">
        <div>
          <p className="vc-dashboard-panel-head__eyebrow">{eyebrow}</p>
          <h2 className="vc-panel-title">{title}</h2>
        </div>
        {standings?.team_name ? <span className="vc-dashboard-inline-note">{standings.team_name}</span> : null}
      </div>

      {!activeTeamId || activeTeamId === "__all__" ? (
        <p className="vc-modal__muted" style={{ margin: 0 }}>{emptySelectionMessage}</p>
      ) : loading ? (
        <p className="vc-modal__muted" style={{ margin: 0 }}>Loading standings…</p>
      ) : error ? (
        <p className="vc-modal__error" style={{ margin: 0 }}>{error}</p>
      ) : standings ? (
        <>
          <div className="vc-team-standings-card__record">
            <div>
              <div className="vc-team-standings-card__record-label">Record</div>
              <div className="vc-team-standings-card__record-value">{standings.record_label}</div>
            </div>
            <div className="vc-team-standings-card__matches">
              {standings.matches_played} match{standings.matches_played === 1 ? "" : "es"} counted
            </div>
          </div>

          <div className="vc-team-standings-card__grid" role="list" aria-label="Standing metrics">
            <div className="vc-team-standings-card__stat" role="listitem">
              <span className="vc-team-standings-card__label">Wins</span>
              <strong>{standings.wins}</strong>
            </div>
            <div className="vc-team-standings-card__stat" role="listitem">
              <span className="vc-team-standings-card__label">Losses</span>
              <strong>{standings.losses}</strong>
            </div>
            <div className="vc-team-standings-card__stat" role="listitem">
              <span className="vc-team-standings-card__label">Points For</span>
              <strong>{standings.points_for}</strong>
            </div>
            <div className="vc-team-standings-card__stat" role="listitem">
              <span className="vc-team-standings-card__label">Points Against</span>
              <strong>{standings.points_against}</strong>
            </div>
            <div className={`vc-team-standings-card__stat ${statToneClass(standings.point_differential)}`} role="listitem">
              <span className="vc-team-standings-card__label">Point Differential</span>
              <strong>{standings.point_differential}</strong>
            </div>
          </div>

          <p className="vc-team-standings-card__note">{standings.note || "Completed matches only."}</p>
        </>
      ) : (
        <p className="vc-modal__muted" style={{ margin: 0 }}>No standings available yet.</p>
      )}
    </section>
  );
}
