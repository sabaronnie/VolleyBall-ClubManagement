function TrendCell({ trend }) {
  if (trend === "up") {
    return <span aria-label="Trending up">▲</span>;
  }
  if (trend === "down") {
    return <span aria-label="Trending down">▼</span>;
  }
  return <span aria-label="Flat trend">{"\u2014"}</span>;
}

function formatServePct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "\u2014";
  }
  return `${Math.round(Number(value))}%`;
}

export default function CoachPlayerStatsTable({ rows }) {
  const list = Array.isArray(rows) ? rows : [];

  return (
    <div className="vc-coach-dash-stats-panel">
      <h2 className="vc-panel-title">Player Stats</h2>
      <div className="vc-coach-dash-stats-panel__scroll">
        <table className="vc-table vc-coach-dash-stats-table">
          <thead>
            <tr>
              <th>Player</th>
              <th>Spikes</th>
              <th>Blocks</th>
              <th>Serve %</th>
              <th>Trend</th>
            </tr>
          </thead>
          <tbody>
            {list.length === 0 ? (
              <tr>
                <td colSpan={5} className="vc-modal__muted">
                  No player stats recorded for this team.
                </td>
              </tr>
            ) : (
              list.map((r) => (
                <tr key={r.player_id}>
                  <td>{r.player_name}</td>
                  <td>{r.spikes}</td>
                  <td>{r.blocks}</td>
                  <td>{formatServePct(r.serve_percentage)}</td>
                  <td className="vc-coach-dash-stats-table__trend">
                    <TrendCell trend={r.trend} />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
