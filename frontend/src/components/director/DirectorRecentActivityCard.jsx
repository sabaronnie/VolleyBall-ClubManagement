function toLocalDate(value) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) {
    return null;
  }
  return d;
}

function formatActivityTime(value) {
  const d = toLocalDate(value);
  if (!d) {
    return "";
  }
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const dayDiff = Math.round((today.getTime() - target.getTime()) / 86400000);
  if (dayDiff === 0) {
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
  if (dayDiff === 1) {
    return "Yesterday";
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

function toReadableAction(actionType) {
  const raw = String(actionType || "").trim();
  if (!raw) {
    return "did an action";
  }
  return raw
    .toLowerCase()
    .split("_")
    .join(" ");
}

function buildActivityLine(log) {
  const userName = log?.user_name || "A user";
  const actionPhrase = toReadableAction(log?.action_type);
  const entityLabel = String(log?.entity_type || "").trim().toLowerCase();
  if (entityLabel) {
    return `${userName} ${actionPhrase} (${entityLabel})`;
  }
  return `${userName} ${actionPhrase}`;
}

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
