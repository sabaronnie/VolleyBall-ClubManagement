import { navigate } from "../../navigation";

const NO_DATA = "No data available";

function fmtPct(v) {
  if (v == null || v === "") {
    return NO_DATA;
  }
  const n = Number(v);
  if (Number.isNaN(n)) {
    return NO_DATA;
  }
  return `${n.toFixed(1)}%`;
}

export default function DirectorClubSummaryCard({ loading, clubId, clubSummary, formatMoney }) {
  const best = clubSummary?.best_participating_team;
  const low = clubSummary?.low_participation;

  return (
    <section className="vc-panel vc-panel--dashboard vc-panel--director-white">
      <div className="vc-summary-head vc-summary-head--dashboard">
        <div>
          <p className="vc-dashboard-panel-head__eyebrow">Insights</p>
          <h2 className="vc-panel-title" style={{ margin: 0 }}>
            Club Summary
          </h2>
        </div>
        <button
          type="button"
          className="vc-link-cyan vc-link-cyan--compact"
          style={{ margin: 0 }}
          onClick={() => navigate("/director/teams")}
        >
          Manage Teams
        </button>
      </div>
      {loading ? (
        <p className="vc-modal__muted">Loading…</p>
      ) : !clubId ? (
        <p className="vc-modal__muted">Select a club to see summary metrics.</p>
      ) : (
        <ul className="vc-summary-list vc-summary-list--dashboard">
          <li>
            <span>Average Attendance</span>
            <strong>{fmtPct(clubSummary?.average_attendance_percent)}</strong>
          </li>
          <li>
            <span>Best Participating Team</span>
            <strong>
              {best?.team_name ? `${best.team_name} (${fmtPct(best.rate_percent)})` : NO_DATA}
            </strong>
          </li>
          <li>
            <span>Low Participation Alert</span>
            <strong style={{ textAlign: "right", maxWidth: "62%" }}>
              {low?.message || "No team flagged in the last 30 days."}
            </strong>
          </li>
          <li>
            <span>Monthly Profit</span>
            <strong>
              {clubSummary
                ? formatMoney(clubSummary.monthly_profit_currency, clubSummary.monthly_profit)
                : NO_DATA}
            </strong>
          </li>
        </ul>
      )}
    </section>
  );
}
