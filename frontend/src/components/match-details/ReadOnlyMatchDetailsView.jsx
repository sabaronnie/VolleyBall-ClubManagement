export default function ReadOnlyMatchDetailsView({ match, audienceLabel = "Team" }) {
  const common = match?.common || {};

  return (
    <section className="tournament-fixture-section">
      <div className="tournament-fixture-section__head">
        <h3>{audienceLabel} Match View</h3>
        <span>{common.match_status_label || common.match_status || "Scheduled"}</span>
      </div>
      <p>
        <strong>{common.team_a}</strong> vs <strong>{common.team_b}</strong>
      </p>
      <p>
        {common.date} {common.time} - {common.location || "TBD"}
      </p>
      <p>Opponent: {match?.opponent || common.team_b || "TBD"}</p>
      <p>Score: {common.score || "Not available yet"}</p>
      <p>Access: read-only</p>
    </section>
  );
}
