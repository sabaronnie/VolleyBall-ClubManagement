import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchMemberDashboard } from "../../api";
import { navigate } from "../../navigation";
import MyFeesPage from "../../pages/MyFeesPage";

function money(cur, amount) {
  const n = Number(amount);
  if (Number.isNaN(n)) {
    return `${cur || "USD"} ${amount}`;
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency: cur || "USD" }).format(n);
}

function paymentStatusLabel(status) {
  if (status === "paid") return "Paid up";
  if (status === "overdue") return "Overdue";
  if (status === "pending") return "Payment due";
  return status || "—";
}

function goWithTeam(path, teamId) {
  if (teamId != null && teamId !== "") {
    window.dispatchEvent(new CustomEvent("netup-set-active-team", { detail: { teamId: String(teamId) } }));
  }
  navigate(path);
}

function openMessages(eventName) {
  window.dispatchEvent(new CustomEvent(eventName || "vc-open-notifications"));
}

function formatShortDate(dateValue) {
  if (!dateValue) {
    return "No session scheduled";
  }
  const parsed = new Date(`${dateValue}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return "No session scheduled";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(parsed);
}

function formatFeeDate(dateValue) {
  if (!dateValue) {
    return "—";
  }
  const parsed = new Date(`${dateValue}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return "—";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(parsed);
}

function formatNextSessionValue(club) {
  if (!club?.scheduled_date) {
    return "No session scheduled";
  }
  const dateLabel = formatShortDate(club.scheduled_date);
  return club.start_time_display ? `${dateLabel} · ${club.start_time_display}` : dateLabel;
}

function PlayerSummaryRow({ items }) {
  return (
    <section className="vc-dashboard-kpi-strip" aria-label="Player summary">
      <div className="vc-dashboard-kpi-strip__grid">
        {items.map((item) => (
          <div key={item.label} className="vc-dashboard-kpi-strip__cell">
            <div className="vc-dashboard-kpi-strip__label">{item.label}</div>
            <div className="vc-dashboard-kpi-strip__value vc-player-dash-summary__value">{item.value}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function MemberProgressChart({ weeks }) {
  const w = 480;
  const h = 200;
  const padT = 16;
  const padR = 16;
  const padB = 36;
  const padL = 40;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;

  const series = useMemo(() => {
    if (!weeks?.length) {
      return null;
    }
    const n = weeks.length;
    const xs = weeks.map((_, i) => (n === 1 ? innerW / 2 : (innerW * i) / (n - 1)));
    const scaleY = (v) => innerH - (Math.min(100, Math.max(0, v)) / 100) * innerH;
    const attack = weeks.map((row, i) => [padL + xs[i], padT + scaleY(row.attack)]);
    const defense = weeks.map((row, i) => [padL + xs[i], padT + scaleY(row.defense)]);
    const serve = weeks.map((row, i) => [padL + xs[i], padT + scaleY(row.serve)]);
    const toPoints = (pts) => pts.map((p) => p.join(",")).join(" ");
    return {
      attack: toPoints(attack),
      defense: toPoints(defense),
      serve: toPoints(serve),
      labels: weeks.map((row) => row.week_label),
      n,
    };
  }, [weeks, innerW, innerH, padT, padL]);

  if (!series) {
    return (
      <div className="vc-member-progress__empty">
        <p className="vc-modal__muted" style={{ margin: 0 }}>
          No attendance or progress data available yet. Weekly skill scores will appear here when your coach
          records them.
        </p>
      </div>
    );
  }

  return (
    <div className="vc-member-progress-chart">
      <svg viewBox={`0 0 ${w} ${h}`} className="vc-member-progress-chart__svg" aria-hidden="true">
        {[0, 25, 50, 75, 100].map((tick) => {
          const y = padT + innerH - (tick / 100) * innerH;
          return (
            <g key={tick}>
              <line x1={padL} y1={y} x2={padL + innerW} y2={y} className="vc-member-progress-chart__grid" />
              <text x={4} y={y + 4} className="vc-member-progress-chart__tick">
                {tick}
              </text>
            </g>
          );
        })}
        <polyline fill="none" stroke="#e74c3c" strokeWidth="2.5" points={series.attack} />
        <polyline fill="none" stroke="#2980b9" strokeWidth="2.5" points={series.defense} />
        <polyline fill="none" stroke="#27ae60" strokeWidth="2.5" points={series.serve} />
      </svg>
      <div className="vc-member-progress-chart__xlabels">
        {series.labels.map((lb) => (
          <span key={lb} className="vc-member-progress-chart__xlabel">
            {lb}
          </span>
        ))}
      </div>
      <ul className="vc-member-progress-chart__legend">
        <li>
          <span className="vc-member-progress-chart__swatch vc-member-progress-chart__swatch--attack" /> Attack
        </li>
        <li>
          <span className="vc-member-progress-chart__swatch vc-member-progress-chart__swatch--defense" /> Defense
        </li>
        <li>
          <span className="vc-member-progress-chart__swatch vc-member-progress-chart__swatch--serve" /> Serve
        </li>
      </ul>
    </div>
  );
}

function PlayerProgressPanel({ progress, focusName, teamName }) {
  return (
    <div className="vc-player-dash-chart">
      <div className="vc-dashboard-panel-head vc-player-dash-panel__head">
        <div>
          <p className="vc-dashboard-panel-head__eyebrow">Progress</p>
          <h2 className="vc-panel-title">Development Progress</h2>
          <p className="vc-player-dash-panel__sub">
            {focusName
              ? `Recent coach-recorded skill trends${teamName ? ` for ${teamName}` : ""}.`
              : "Progress trends appear here once a player is linked to your account."}
          </p>
        </div>
      </div>
      {progress?.summary && progress.has_weekly_metrics ? (
        <div className="vc-member-progress__summary">
          <div>
            <span className="vc-member-progress__sum-label">Attack</span>
            <span className="vc-member-progress__sum-val">{progress.summary.attack?.toFixed(1) ?? "—"}</span>
          </div>
          <div>
            <span className="vc-member-progress__sum-label">Defense</span>
            <span className="vc-member-progress__sum-val">{progress.summary.defense?.toFixed(1) ?? "—"}</span>
          </div>
          <div>
            <span className="vc-member-progress__sum-label">Serve</span>
            <span className="vc-member-progress__sum-val">{progress.summary.serve?.toFixed(1) ?? "—"}</span>
          </div>
        </div>
      ) : null}
      <MemberProgressChart weeks={progress?.weeks} />
    </div>
  );
}

function PlayerFeeTable({ payment }) {
  const lines = useMemo(() => {
    const list = Array.isArray(payment?.fee_lines) ? [...payment.fee_lines] : [];
    list.sort((a, b) => {
      const aOpen = a.status === "paid" ? 1 : 0;
      const bOpen = b.status === "paid" ? 1 : 0;
      if (aOpen !== bOpen) {
        return aOpen - bOpen;
      }
      return String(a.due_date || "").localeCompare(String(b.due_date || ""));
    });
    return list.slice(0, 6);
  }, [payment]);

  return (
    <div className="vc-coach-dash-stats-panel vc-player-dash-table-panel">
      <div className="vc-dashboard-panel-head vc-player-dash-panel__head">
        <div>
          <p className="vc-dashboard-panel-head__eyebrow">Finance</p>
          <h2 className="vc-panel-title">Fee Lines</h2>
          <p className="vc-player-dash-panel__sub">Recent balances and due dates for this player account.</p>
        </div>
      </div>
      <div className="vc-coach-dash-stats-panel__scroll">
        <table className="vc-table vc-coach-dash-stats-table vc-player-dash-fees-table">
          <thead>
            <tr>
              <th>Description</th>
              <th>Due Date</th>
              <th>Remaining</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {lines.length === 0 ? (
              <tr>
                <td colSpan={4} className="vc-modal__muted">
                  No fee lines available for this player yet.
                </td>
              </tr>
            ) : (
              lines.map((line) => (
                <tr key={line.id}>
                  <td>{line.description || "Team fee"}</td>
                  <td>{formatFeeDate(line.due_date)}</td>
                  <td>{money(line.currency, line.remaining)}</td>
                  <td>{paymentStatusLabel(line.status)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PlayerActionButtons({ actions }) {
  const visibleActions = actions.filter(Boolean);
  if (!visibleActions.length) {
    return null;
  }

  return (
    <div className="vc-player-dash-main-actions" role="group" aria-label="Player actions">
      {visibleActions.map((action) => (
        <button
          key={action.label}
          type="button"
          className="vc-director-actions-bar__btn"
          onClick={action.onClick}
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}

function PlayerDashboardDropdown({
  id,
  title,
  description,
  isOpen,
  onToggle,
  children,
}) {
  return (
    <section className={`vc-dashboard-dropdown${isOpen ? " is-open" : ""}`}>
      <button
        id={`${id}-trigger`}
        type="button"
        className="vc-dashboard-dropdown__trigger"
        aria-expanded={isOpen}
        aria-controls={`${id}-panel`}
        onClick={onToggle}
      >
        <span>
          <strong>{title}</strong>
          <small>{description}</small>
        </span>
        <span className="vc-dashboard-dropdown__caret" aria-hidden="true">
          {isOpen ? "−" : "+"}
        </span>
      </button>
      {isOpen ? (
        <div id={`${id}-panel`} className="vc-dashboard-dropdown__panel" role="region" aria-labelledby={`${id}-trigger`}>
          {children}
        </div>
      ) : null}
    </section>
  );
}

function PlayerOverviewCard({ focus, profile, payment, club, unread }) {
  return (
    <section className="vc-panel vc-panel--dashboard vc-panel--director-white vc-player-dash-overview" aria-labelledby="player-overview-heading">
      <div className="vc-dashboard-panel-head">
        <div>
          <p className="vc-dashboard-panel-head__eyebrow">Workspace</p>
          <h2 id="player-overview-heading" className="vc-panel-title">
            Player Overview
          </h2>
        </div>
      </div>
      {!focus ? (
        <p className="vc-modal__muted" style={{ margin: 0 }}>
          Join a team roster or link a child account to unlock schedule details, attendance actions, and progress updates here.
        </p>
      ) : (
        <ul className="vc-coach-dash-feedback__list">
          <li>
            <strong>Profile</strong>
            {`: ${profile?.display_name || [focus.first_name, focus.last_name].filter(Boolean).join(" ") || focus.email}`}
          </li>
          <li>
            <strong>Team</strong>
            {`: ${profile?.team?.name || "No active team roster"}`}
          </li>
          {profile?.coach_display ? (
            <li>
              <strong>Coach</strong>
              {`: ${profile.coach_display}`}
            </li>
          ) : null}
          <li>
            <strong>Upcoming session</strong>
            {`: ${
              club
                ? `${club.title} on ${club.date_display}${club.start_time_display ? ` at ${club.start_time_display}` : ""}${
                    club.location ? ` in ${club.location}` : ""
                  }`
                : "No upcoming session is scheduled right now."
            }`}
          </li>
          <li>
            <strong>Attendance</strong>
            {`: ${
              club?.needs_confirmation
                ? "Confirmation is still needed for the next session."
                : club
                  ? "You are up to date on the next scheduled session."
                  : "Attendance will appear here once a session is scheduled."
            }`}
          </li>
          <li>
            <strong>Payments</strong>
            {`: ${
              payment
                ? `${money(payment.currency, payment.amount_due)} due across ${payment.open_item_count} open fee line${
                    payment.open_item_count === 1 ? "" : "s"
                  }.`
                : "No payment data available."
            }`}
          </li>
          <li>
            <strong>Messages</strong>
            {`: ${unread > 0 ? `${unread} unread notification${unread === 1 ? "" : "s"}.` : "Inbox clear."}`}
          </li>
        </ul>
      )}
    </section>
  );
}

export default function MemberPlayerDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [childFilter, setChildFilter] = useState(null);
  const [feesDropdownOpen, setFeesDropdownOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await fetchMemberDashboard(childFilter);
      setData(payload);
    } catch (err) {
      setData(null);
      setError(err.message || "Could not load dashboard.");
    } finally {
      setLoading(false);
    }
  }, [childFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onRefresh = () => void load();
    window.addEventListener("vc-member-dashboard-refresh", onRefresh);
    return () => window.removeEventListener("vc-member-dashboard-refresh", onRefresh);
  }, [load]);

  const unread = data?.notifications?.unread_count ?? 0;
  const childrenOpts = data?.available_children || [];
  const resolvedChildSelect = String(childFilter ?? data?.focus_player?.id ?? childrenOpts[0]?.id ?? "");

  const onSelectChild = (e) => {
    const v = e.target.value;
    setChildFilter(v ? Number(v) : null);
  };

  const profile = data?.profile;
  const payment = data?.payment;
  const progress = data?.progress;
  const club = data?.club_summary;
  const qa = data?.quick_actions || {};
  const focus = data?.focus_player;
  const focusDisplayName =
    profile?.display_name || [focus?.first_name, focus?.last_name].filter(Boolean).join(" ").trim() || focus?.email || "";

  const summaryItems = useMemo(() => {
    if (!focus) {
      return [
        { label: "Roster Status", value: "Not linked yet" },
        { label: "Linked Players", value: String(childrenOpts.length || 0) },
        { label: "Fees Due", value: money("USD", 0) },
        { label: "Messages", value: unread > 0 ? `${unread} unread` : "Inbox clear" },
      ];
    }

    return [
      { label: "Active Team", value: profile?.team?.name || "No active team" },
      { label: "Next Session", value: formatNextSessionValue(club) },
      { label: "Fees Due", value: payment ? money(payment.currency, payment.amount_due) : money("USD", 0) },
      { label: "Messages", value: unread > 0 ? `${unread} unread` : "Inbox clear" },
    ];
  }, [club, childrenOpts.length, focus, payment, profile?.team?.name, unread]);

  const actionTeamId = profile?.team?.id || club?.team_id || null;
  const primaryActionButtons = useMemo(() => {
    const actions = [];

    if (actionTeamId) {
      actions.push({
        label: "Open Schedule",
        onClick: () => goWithTeam("/schedule", actionTeamId),
      });
    }

    if (focus) {
      actions.push({
        label: qa.confirm_attendance_mode === "parent" ? "Family Attendance" : "My Sessions",
        onClick: () => goWithTeam(qa.confirm_attendance_path || "/player/attendance", actionTeamId),
      });
    }

    return actions;
  }, [actionTeamId, focus, qa.confirm_attendance_mode, qa.confirm_attendance_path]);

  return (
    <div className="vc-coach-dash-body vc-player-dash-body">
      {childrenOpts.length > 1 ? (
        <div className="vc-member-dash__child-bar">
          <label className="vc-member-dash__child-label">
            Showing dashboard for
            <select
              className="vc-dash-team-select"
              value={resolvedChildSelect}
              onChange={onSelectChild}
              aria-label="Select linked player"
            >
              {childrenOpts.map((c) => (
                <option key={c.id} value={c.id}>
                  {[c.first_name, c.last_name].filter(Boolean).join(" ").trim() || c.email}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : null}

      {loading ? <p className="vc-modal__muted">Loading dashboard…</p> : null}
      {error ? <p className="vc-modal__error">{error}</p> : null}

      {!loading && !error ? (
        <>
          <PlayerSummaryRow items={summaryItems} />

          <div className="vc-dash-row vc-dash-row--dashboard">
            <div className="vc-panel vc-panel--dashboard vc-panel--director-white">
              <PlayerProgressPanel
                progress={progress}
                focusName={focusDisplayName}
                teamName={profile?.team?.name || club?.team_name || ""}
              />
            </div>
            <div className="vc-panel vc-panel--dashboard vc-panel--director-white">
              <PlayerFeeTable payment={payment} />
            </div>
          </div>

          <PlayerActionButtons actions={primaryActionButtons} />

          <PlayerDashboardDropdown
            id="player-dashboard-fees"
            title="My Fees"
            description="Open your fees and payments without leaving the dashboard."
            isOpen={feesDropdownOpen}
            onToggle={() => setFeesDropdownOpen((current) => !current)}
          >
            <MyFeesPage embedded />
          </PlayerDashboardDropdown>

          <PlayerOverviewCard
            focus={focus}
            profile={profile}
            payment={payment}
            club={club}
            unread={unread}
          />
        </>
      ) : null}
    </div>
  );
}
