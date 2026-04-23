import { goToContactPage, navigate } from "../navigation";

function BrandContent() {
  return (
    <span className="homepage-brand" aria-hidden="true">
      <span className="homepage-brand__wordmark">
        <h1>Net</h1>
        <h1>Up</h1>
      </span>
      <img src="/auth/logo-ball.png" alt="" />
    </span>
  );
}

export function buildWorkspaceTabs({
  showPlayerSessionsTab = false,
  showCoachAttendanceTab = false,
  showCoachStatisticsTab = false,
  showParentAttendanceTab = false,
}) {
  const tabs = [
    { id: "dashboard", label: "Dashboard", path: "/dashboard" },
    { id: "schedule", label: "Schedule", path: "/schedule" },
  ];

  if (showPlayerSessionsTab) {
    tabs.push({ id: "player-attendance", label: "My sessions", path: "/player/attendance" });
  }
  if (showCoachAttendanceTab) {
    tabs.push({ id: "coach-attendance", label: "Events", path: "/coach/attendance" });
  }
  if (showCoachStatisticsTab) {
    tabs.push({ id: "coach-statistics", label: "Statistics", path: "/coach/statistics" });
  }
  if (showParentAttendanceTab) {
    tabs.push({ id: "parent-attendance", label: "Family attendance", path: "/parent/attendance" });
  }

  return tabs;
}

export default function SiteNavbar({
  mode = "workspace",
  activeTab = null,
  tabs = [],
  teamSelector = null,
  actions = null,
}) {
  if (mode === "guest") {
    return (
      <header className="site-nav site-nav--guest">
        <div className="guest-nav-group">
          <div className="homepage-brand" aria-label="NetUp">
            <div className="homepage-brand__wordmark" aria-hidden="true">
              <h1>Net</h1>
              <h1>Up</h1>
            </div>
            <img src="/auth/logo-ball.png" alt="" />
          </div>
          <button
            className="action-button action-button--ghost"
            type="button"
            onClick={() => goToContactPage()}
          >
            Contact Us
          </button>
          <button className="action-button action-button--ghost" type="button" onClick={() => navigate("/register")}>
            Register
          </button>
          <button className="action-button" type="button" onClick={() => navigate("/login")}>
            Login
          </button>
        </div>
      </header>
    );
  }

  return (
    <header className="vc-dash-topbar vc-dash-topbar--shared">
      <div className="vc-dash-brand">
        <button
          type="button"
          className="vc-dash-logo vc-dash-logo--home vc-dash-logo--wordmark"
          onClick={() => navigate("/")}
          aria-label="Go to homepage"
        >
          <BrandContent />
        </button>
        <nav className="vc-dash-tabs" aria-label="Main">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`nav-link-button${activeTab === tab.id ? " is-current" : ""}`}
              onClick={() => navigate(tab.path)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>
      <div className="vc-dash-actions vc-dash-actions--spread" aria-label="Toolbar">
        {teamSelector}
        <button type="button" className="nav-link-button" onClick={() => goToContactPage()}>
          Contact Us
        </button>
        {actions}
      </div>
    </header>
  );
}
