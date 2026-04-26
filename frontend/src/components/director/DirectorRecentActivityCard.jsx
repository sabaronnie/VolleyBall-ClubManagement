import { buildActivityLine, formatActivityTime } from "../../utils/auditLogDisplay";

export default function DirectorRecentActivityCard({ loading = false, error = "", logs = [] }) {
  return (
    <section className="vc-panel vc-panel--dashboard vc-panel--director-white">
      <div className="vc-summary-head vc-summary-head--dashboard">
        <div>
          <p className="vc-dashboard-panel-head__eyebrow">Audit</p>
          <h2 className="vc-panel-title" style={{ margin: 0 }}>
            Recent Activity
          </h2>
        </div>
      </div>
      {loading ? <p className="vc-modal__muted">Loading recent activity...</p> : null}
      {!loading && error ? <p className="schedule-feedback schedule-feedback--error">{error}</p> : null}
      {!loading && !error && !logs.length ? <p className="vc-modal__muted">No recent activity</p> : null}
      {!loading && !error && logs.length ? (
        <ul className="vc-summary-list vc-summary-list--dashboard">
          {logs.map((log, index) => (
            <li key={`${log?.timestamp || "ts"}-${index}`}>
              <span>{buildActivityLine(log)}</span>
              <strong>{formatActivityTime(log?.timestamp)}</strong>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
