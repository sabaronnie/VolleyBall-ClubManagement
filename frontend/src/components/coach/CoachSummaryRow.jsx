function displayCount(value) {
  if (value === null || value === undefined || value === "") {
    return "No data available";
  }
  const n = Number(value);
  if (Number.isNaN(n)) {
    return "No data available";
  }
  return String(n);
}

function displayOptionalSession(value, emptyLabel) {
  if (value === null || value === undefined || value === "") {
    return emptyLabel;
  }
  return String(value);
}

export default function CoachSummaryRow({ kpi }) {
  const safe = kpi && typeof kpi === "object" ? kpi : {};

  const nextMatch =
    safe.next_match && typeof safe.next_match === "object"
      ? safe.next_match.weekday_label || safe.next_match.title
      : null;

  const items = [
    { label: "Players Today", value: displayCount(safe.players_today) },
    {
      label: "Practice Time",
      value: displayOptionalSession(safe.practice_time_display, "No sessions available"),
    },
    {
      label: "Next Match",
      value: displayOptionalSession(nextMatch, "No match scheduled"),
    },
    { label: "Feedback Due", value: displayCount(safe.feedback_due) },
  ];

  return (
    <section className="vc-coach-dash-summary" aria-label="Coach summary">
      {items.map((item) => (
        <div key={item.label} className="vc-coach-dash-summary__cell">
          <div className="vc-kpi-label">{item.label}</div>
          <div className="vc-coach-dash-summary__value">{item.value}</div>
        </div>
      ))}
    </section>
  );
}
