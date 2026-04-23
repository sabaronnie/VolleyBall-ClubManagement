export default function CoachActionButtons({
  onRecordMatchStats,
  onUploadVideos,
  onUploadPlans,
}) {
  return (
    <div className="vc-coach-dash-main-actions" role="group" aria-label="Coach actions">
      <button type="button" className="vc-coach-dash-main-actions__btn" onClick={onRecordMatchStats}>
        Record Match Stats
      </button>
      <button type="button" className="vc-coach-dash-main-actions__btn" onClick={onUploadVideos}>
        Upload Videos
      </button>
      <button type="button" className="vc-coach-dash-main-actions__btn" onClick={onUploadPlans}>
        Upload Plans
      </button>
    </div>
  );
}
