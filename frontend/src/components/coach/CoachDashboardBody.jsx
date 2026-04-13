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

  if (error) {
    return (
      <div className="vc-coach-dash-body">
        <p className="vc-modal__error" style={{ margin: 0 }}>
          {error}
        </p>
      </div>
    );
  }

  if (!dashboard) {
    return null;
  }

  const { kpis, attendance_vs_performance: avp, player_stats: playerStats, recent_feedback: recentFeedback } =
    dashboard;

  return (
    <div className="vc-coach-dash-body">
      <CoachSummaryRow kpi={kpis} />

      <div className="vc-dash-row vc-coach-dash-analytics-row">
        <div className="vc-panel vc-coach-dash-panel--chart">
          <CoachAttendancePerformanceChart series={avp} />
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
