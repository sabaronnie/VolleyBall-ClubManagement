import { navigate } from "../../navigation";
import CoachActionButtons from "./CoachActionButtons";
import CoachAttendancePerformanceChart from "./CoachAttendancePerformanceChart";
import CoachPlayerStatsTable from "./CoachPlayerStatsTable";
import CoachRecentFeedbackCard from "./CoachRecentFeedbackCard";
import CoachSummaryRow from "./CoachSummaryRow";

export default function CoachDashboardBody({ dashboard, loading, error }) {
  if (loading) {
    return (
      <div className="vc-coach-dash-body" aria-busy="true">
        <p className="vc-modal__muted" style={{ margin: 0 }}>
          {"Loading coach dashboard\u2026"}
        </p>
      </div>
    );
  }

  const safe = dashboard && typeof dashboard === "object" ? dashboard : {};
  const kpis = safe.kpis;
  const avp = safe.attendance_vs_performance;
  const playerStats = safe.player_stats;
  const recentFeedback = safe.recent_feedback;
  const hasSkillMetrics = safe.has_skill_metrics;

  return (
    <div className="vc-coach-dash-body">
      {error ? (
        <p className="vc-modal__error" style={{ margin: "0 0 1rem" }}>
          {error}
        </p>
      ) : null}

      <CoachSummaryRow kpi={kpis} />

      <div className="vc-dash-row vc-coach-dash-analytics-row">
        <div className="vc-panel vc-coach-dash-panel--chart">
          <CoachAttendancePerformanceChart series={avp} hasSkillMetrics={hasSkillMetrics} />
        </div>
        <div className="vc-panel vc-coach-dash-panel--table">
          <CoachPlayerStatsTable rows={playerStats} />
        </div>
      </div>

      <CoachActionButtons
        onRecordMatchStats={() => navigate("/coach/attendance")}
        onUploadVideos={() => navigate("/teams")}
        onUploadPlans={() => navigate("/schedule")}
      />

      <CoachRecentFeedbackCard items={recentFeedback} />
    </div>
  );
}
