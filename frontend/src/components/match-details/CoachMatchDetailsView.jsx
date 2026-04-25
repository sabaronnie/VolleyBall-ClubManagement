export default function CoachMatchDetailsView({ match, onSaveResult }) {
  const common = match?.common || {};
  const canEdit = Boolean(match?.permissions?.can_edit_result);

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!canEdit || typeof onSaveResult !== "function") return;
    const formData = new FormData(event.currentTarget);
    onSaveResult({
      team_score: Number(formData.get("team_score") || 0),
      opponent_score: Number(formData.get("opponent_score") || 0),
      notes: String(formData.get("notes") || "").trim(),
    });
  };

  return (
    <section className="tournament-fixture-section">
      <div className="tournament-fixture-section__head">
        <h3>Coach Match View</h3>
        <span>{common.match_status_label || common.match_status || "Scheduled"}</span>
      </div>
      <p>
        <strong>{common.team_a}</strong> vs <strong>{common.team_b}</strong>
      </p>
      <p>
        {common.date} {common.time} - {common.location || "TBD"}
      </p>
      <p>Score: {common.score || "Not recorded yet"}</p>

      <form onSubmit={handleSubmit} className="tournament-form-grid" style={{ marginTop: "0.8rem" }}>
        <label>
          <span>Your team score</span>
          <input name="team_score" type="number" min="0" disabled={!canEdit} />
        </label>
        <label>
          <span>Opponent score</span>
          <input name="opponent_score" type="number" min="0" disabled={!canEdit} />
        </label>
        <label className="tournament-form-grid__full">
          <span>Notes (optional)</span>
          <input name="notes" disabled={!canEdit} />
        </label>
        <div className="tournament-form-card__actions">
          <button type="submit" className="vc-action-btn" disabled={!canEdit}>
            Save match result
          </button>
        </div>
      </form>
    </section>
  );
}
