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

export default function DirectorClubSummaryCard({
  loading,
  clubId,
  clubSummary,
  paymentSnapshot = null,
  formatMoney,
  onManageTeams = null,
  title = "Club Summary",
  manageLabel = "Manage Teams",
  emptySelectionMessage = "Select a club to see summary metrics.",
  averageLabel = "Average Attendance",
  bestLabel = "Best Participating Team",
  lowLabel = "Low Participation Alert",
  lowFallbackMessage = "No team flagged in the last 30 days.",
  profitLabel = "Monthly Profit",
}) {
  const best = clubSummary?.best_participating_team;
  const low = clubSummary?.low_participation;
  const paymentSummaryLabel = paymentSnapshot?.label || "Outstanding / Unpaid / Paid";
  const handleManageTeams = () => {
    if (onManageTeams) {
      onManageTeams();
      return;
    }
    navigate("/director/teams");
  };

  return (
    <section className="vc-panel vc-panel--dashboard vc-panel--director-white">
      <div className="vc-summary-head vc-summary-head--dashboard">
        <div>
          <p className="vc-dashboard-panel-head__eyebrow">Insights</p>
          <h2 className="vc-panel-title" style={{ margin: 0 }}>
            {title}
          </h2>
        </div>
        <button
          type="button"
          className="vc-link-cyan vc-link-cyan--compact"
          style={{ margin: 0 }}
          onClick={handleManageTeams}
        >
          {manageLabel}
        </button>
      </div>
      {loading ? (
        <p className="vc-modal__muted">Loading…</p>
      ) : !clubId ? (
        <p className="vc-modal__muted">{emptySelectionMessage}</p>
      ) : (
        <ul className="vc-summary-list vc-summary-list--dashboard">
          <li>
            <span>{averageLabel}</span>
            <strong>{fmtPct(clubSummary?.average_attendance_percent)}</strong>
          </li>
          <li>
            <span>{bestLabel}</span>
            <strong>
              {best?.team_name ? `${best.team_name} (${fmtPct(best.rate_percent)})` : NO_DATA}
            </strong>
          </li>
          <li>
            <span>{lowLabel}</span>
            <strong style={{ textAlign: "right", maxWidth: "62%" }}>
              {low?.message || lowFallbackMessage}
            </strong>
          </li>
          <li>
            <span>{profitLabel}</span>
            <strong>
              {clubSummary
                ? formatMoney(clubSummary.monthly_profit_currency, clubSummary.monthly_profit)
                : NO_DATA}
            </strong>
          </li>
          {paymentSnapshot ? (
            <li>
              <span>{paymentSummaryLabel}</span>
              <strong style={{ textAlign: "right" }}>
                {`${formatMoney(paymentSnapshot.currency, paymentSnapshot.outstandingTotal)} / ${paymentSnapshot.unpaidCount} / ${paymentSnapshot.paidCount}`}
              </strong>
            </li>
          ) : null}
        </ul>
      )}
    </section>
  );
}
