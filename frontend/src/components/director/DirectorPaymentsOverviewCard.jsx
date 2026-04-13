import { navigate } from "../../navigation";

function statusBadge(status) {
  if (status === "paid") {
    return <span className="vc-status-paid">Paid</span>;
  }
  if (status === "overdue") {
    return <span className="vc-status-overdue">Overdue</span>;
  }
  return <span className="vc-status-pending">Pending</span>;
}

export default function DirectorPaymentsOverviewCard({ loading, clubId, rows, formatMoney }) {
  const list = Array.isArray(rows) ? rows : [];

  return (
    <section className="vc-panel vc-panel--dashboard vc-panel--director-white">
      <div className="vc-dashboard-panel-head">
        <div>
          <p className="vc-dashboard-panel-head__eyebrow">Finance</p>
          <h2 className="vc-panel-title">Payments Overview</h2>
        </div>
        <button
          type="button"
          className="vc-link-cyan vc-link-cyan--compact"
          disabled={!clubId}
          onClick={() => navigate(`/director/payments?club_id=${clubId}`)}
        >
          View All
        </button>
      </div>
      {loading ? (
        <p className="vc-modal__muted">Loading payment data…</p>
      ) : !clubId ? (
        <p className="vc-modal__muted">Create a club as director to see fee tracking.</p>
      ) : (
        <div className="vc-dashboard-table-wrap">
          <table className="vc-table vc-table--dashboard">
            <thead>
              <tr>
                <th>Family</th>
                <th>Paid</th>
                <th>Remaining</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {list.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ color: "#6b7580", fontWeight: 600 }}>
                    No fee records yet for this club. Use Payments to add schedules and invoices.
                  </td>
                </tr>
              ) : (
                list.map((r) => (
                  <tr key={r.player_id}>
                    <td>{r.family_label}</td>
                    <td>{formatMoney(r.currency, r.total_paid)}</td>
                    <td>{formatMoney(r.currency, r.total_remaining)}</td>
                    <td>{statusBadge(r.status)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
