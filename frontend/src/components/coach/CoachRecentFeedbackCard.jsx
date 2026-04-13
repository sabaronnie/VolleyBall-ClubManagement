import { navigate } from "../../navigation";

export default function CoachRecentFeedbackCard({ items }) {
  const list = Array.isArray(items) ? items : [];

  return (
    <section className="vc-coach-dash-feedback" aria-labelledby="coach-recent-feedback-heading">
      <div className="vc-coach-dash-feedback__head">
        <h2 id="coach-recent-feedback-heading" className="vc-coach-dash-feedback__title">
          Recent Feedback
        </h2>
        <button type="button" className="vc-link-cyan vc-link-cyan--compact" onClick={() => navigate("/teams")}>
          Manage Teams
        </button>
      </div>
      {list.length === 0 ? (
        <p className="vc-modal__muted" style={{ margin: 0 }}>
          No feedback entries yet.
        </p>
      ) : (
        <ul className="vc-coach-dash-feedback__list">
          {list.map((row) => (
            <li key={row.id}>
              <strong>{row.player_name}</strong>
              {": "}
              {row.body}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
