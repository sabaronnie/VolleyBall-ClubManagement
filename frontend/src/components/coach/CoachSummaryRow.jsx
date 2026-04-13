function displayOrDash(value) {
  if (value === null || value === undefined || value === "") {
    return "\u2014";
  }
  return String(value);
}

export default function CoachSummaryRow({ kpi }) {
  if (!kpi) {
    return null;
  }

  const nextMatch =
    kpi.next_match && typeof kpi.next_match === "object"
      ? kpi.next_match.weekday_label || kpi.next_match.title
      : null;

  const items = [
    { label: "Players Today", value: displayOrDash(kpi.players_today) },
    { label: "Practice Time", value: displayOrDash(kpi.practice_time_display) },
    { label: "Next Match", value: displayOrDash(nextMatch) },
    { label: "Feedback Due", value: displayOrDash(kpi.feedback_due) },
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
