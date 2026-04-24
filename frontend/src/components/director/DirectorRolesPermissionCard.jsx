function cell(v) {
  if (v) {
    return (
      <td className="vc-yes" style={{ textAlign: "center" }}>
        Yes
      </td>
    );
  }
  return (
    <td className="vc-no" style={{ textAlign: "center" }}>
      No
    </td>
  );
}

export default function DirectorRolesPermissionCard({ loading, matrix }) {
  const rows = matrix?.rows || [];

  return (
    <section className="vc-panel vc-panel--dashboard vc-panel--director-white">
      <div className="vc-dashboard-panel-head">
        <div>
          <p className="vc-dashboard-panel-head__eyebrow">Access</p>
          <h2 className="vc-panel-title">Roles Permission</h2>
        </div>
      </div>
      {loading ? (
        <p className="vc-modal__muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="vc-modal__muted">No permission matrix loaded. Try refreshing the dashboard.</p>
      ) : (
        <div className="vc-dashboard-table-wrap">
          <table className="vc-table vc-table--dashboard" style={{ fontSize: "0.88rem" }}>
            <thead>
              <tr>
                <th>Action</th>
                <th>Coach</th>
                <th>Parents</th>
                <th>Player</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.action}>
                  <td>{row.action}</td>
                  {cell(row.coach)}
                  {cell(row.parents)}
                  {cell(row.player)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
