import { useEffect } from "react";
import ClubWorkspaceLayout from "../components/ClubWorkspaceLayout";
import { navigate } from "../navigation";

const AUTH_TOKEN_KEY = "netup.auth.token";

export default function DashboardPage() {
  useEffect(() => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
      navigate("/login");
    }
  }, []);

  return (
    <ClubWorkspaceLayout activeTab="dashboard" trainingEnabled>
      <section className="vc-dash-kpi-card">
        <div className="vc-kpi">
          <span className="vc-kpi-icon" aria-hidden="true">
            👥
          </span>
          <div>
            <div className="vc-kpi-label">Registration</div>
            <div className="vc-kpi-value">—</div>
          </div>
        </div>
        <div className="vc-kpi">
          <span className="vc-kpi-icon" aria-hidden="true">
            💲
          </span>
          <div>
            <div className="vc-kpi-label">Monthly revenue</div>
            <div className="vc-kpi-value">—</div>
          </div>
        </div>
        <div className="vc-kpi">
          <span className="vc-kpi-icon" aria-hidden="true">
            📈
          </span>
          <div>
            <div className="vc-kpi-label">Attendance rate</div>
            <div className="vc-kpi-value">—</div>
          </div>
        </div>
        <div className="vc-kpi">
          <span className="vc-kpi-icon" aria-hidden="true">
            📋
          </span>
          <div>
            <div className="vc-kpi-label">Outstanding payments</div>
            <div className="vc-kpi-value">—</div>
          </div>
        </div>
      </section>

      <div className="vc-dash-row">
        <section className="vc-panel">
          <h2 className="vc-panel-title">Attendance trend (last 30 days)</h2>
          <div className="vc-chart-wrap">
            <p className="vc-modal__muted" style={{ margin: 0 }}>
              Connect reporting data to see attendance trends here.
            </p>
          </div>
        </section>

        <section className="vc-panel">
          <h2 className="vc-panel-title">Payments overview</h2>
          <table className="vc-table">
            <thead>
              <tr>
                <th>Family</th>
                <th>Paid</th>
                <th>Remaining</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={4} style={{ color: "#6b7580", fontWeight: 600 }}>
                  No payment rows loaded yet.
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>

      <div className="vc-actions-row">
        <button type="button" className="vc-action-btn" onClick={() => navigate("/director/users")}>
          <span>Manage registration</span>
          <span aria-hidden="true">›</span>
        </button>
        <button type="button" className="vc-action-btn" disabled>
          <span>Send payment reminder</span>
          <span aria-hidden="true">›</span>
        </button>
        <button type="button" className="vc-action-btn" disabled>
          <span>Generate receipt</span>
          <span aria-hidden="true">›</span>
        </button>
        <button type="button" className="vc-action-btn" disabled>
          <span>View logs</span>
          <span aria-hidden="true">›</span>
        </button>
      </div>

      <div className="vc-dash-bottom">
        <section className="vc-panel vc-roles-table">
          <h2 className="vc-panel-title">Roles and access</h2>
          <p className="vc-modal__muted" style={{ margin: 0 }}>
            Fine-grained permissions follow each user’s role in the club. Detailed matrices will appear when this
            section is wired to your organization settings.
          </p>
        </section>

        <section className="vc-panel">
          <div className="vc-summary-head">
            <h2 className="vc-panel-title" style={{ margin: 0 }}>
              Club summary
            </h2>
            <button type="button" className="vc-link-cyan" style={{ margin: 0 }} onClick={() => navigate("/teams")}>
              Manage teams
            </button>
          </div>
          <ul className="vc-summary-list">
            <li>
              <span>Average attendance</span>
              <strong>—</strong>
            </li>
            <li>
              <span>Best participating team</span>
              <strong>—</strong>
            </li>
            <li>
              <span>Low participation alert</span>
              <strong>—</strong>
            </li>
            <li>
              <span>Monthly profit</span>
              <strong>—</strong>
            </li>
          </ul>
        </section>
      </div>
    </ClubWorkspaceLayout>
  );
}
