import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchMemberDashboard } from "../../api";
import { navigate } from "../../navigation";

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

export default function MemberPlayerDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [childFilter, setChildFilter] = useState(null);

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

  return (
    <div className="vc-member-dash">
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

      {!loading && !error && !focus ? (
        <>
          <p className="vc-modal__muted" style={{ margin: "0 0 1rem", lineHeight: 1.55, maxWidth: 640 }}>
            You are not on a player roster yet and have no linked players. The layout below stays available so
            you can see what will appear once your director assigns teams or approves parent linking.
          </p>
          <div className="vc-member-dash__top-row">
            <section className="vc-panel vc-panel--dashboard vc-member-card vc-member-card--profile">
              <h2 className="vc-member-card__title">Profile</h2>
              <p className="vc-modal__muted" style={{ margin: 0, lineHeight: 1.55 }}>
                No player profile to show yet. Join a team roster or complete parent linking to see name, team,
                and coach details here.
              </p>
            </section>
            <section className="vc-panel vc-panel--dashboard vc-member-card vc-member-card--payment">
              <h2 className="vc-member-card__title">Payment status</h2>
              <p className="vc-modal__muted" style={{ margin: "0 0 0.75rem", lineHeight: 1.55 }}>
                No payments available yet for a linked player account.
              </p>
              <button type="button" className="vc-member-btn vc-member-btn--primary" onClick={() => navigate("/my-fees")}>
                Open fees
              </button>
            </section>
          </div>
          <div className="vc-member-dash__mid-row">
            <section className="vc-panel vc-panel--dashboard vc-member-card vc-member-card--progress">
              <h2 className="vc-member-card__title">Progress</h2>
              <MemberProgressChart weeks={[]} />
            </section>
            <div className="vc-member-dash__side">
              <section className="vc-panel vc-panel--dashboard vc-member-card vc-member-card--compact">
                <h2 className="vc-member-card__title vc-member-card__title--sm">Club summary</h2>
                <p className="vc-modal__muted" style={{ margin: 0 }}>
                  No sessions available on your teams yet.
                </p>
              </section>
              <button
                type="button"
                className="vc-member-btn vc-member-btn--primary vc-member-btn--block"
                onClick={() => goWithTeam(qa.confirm_attendance_path || "/player/attendance", null)}
              >
                Confirm attendance
              </button>
              <button
                type="button"
                className="vc-panel vc-panel--dashboard vc-member-quick"
                onClick={() => {
                  window.dispatchEvent(new CustomEvent(qa.messages_event_name || "vc-open-notifications"));
                }}
              >
                <span className="vc-member-quick__title">Messages</span>
                {unread > 0 ? (
                  <span className="vc-member-quick__badge">{unread > 99 ? "99+" : unread}</span>
                ) : (
                  <span className="vc-modal__muted vc-member-quick__sub">Inbox</span>
                )}
              </button>
              <button
                type="button"
                className="vc-panel vc-panel--dashboard vc-member-quick"
                onClick={() => navigate(qa.development_progress_path || "/teams")}
              >
                <span className="vc-member-quick__title">Development progress</span>
                <span className="vc-modal__muted vc-member-quick__sub">Statistics &amp; trends</span>
              </button>
            </div>
          </div>
        </>
      ) : null}

      {!loading && !error && focus ? (
        <>
          <div className="vc-member-dash__top-row">
            <section className="vc-panel vc-panel--dashboard vc-member-card vc-member-card--profile">
              <h2 className="vc-member-card__title">Profile</h2>
              <div className="vc-member-profile">
                <div className="vc-member-profile__avatar" aria-hidden="true">
                  {[focus.first_name?.[0], focus.last_name?.[0]].filter(Boolean).join("").toUpperCase() || "?"}
                </div>
                <div className="vc-member-profile__body">
                  <div className="vc-member-profile__name">
                    {profile?.display_name || [focus.first_name, focus.last_name].filter(Boolean).join(" ") || focus.email}
                  </div>
                  {profile?.age_years != null ? (
                    <div className="vc-member-profile__meta">Age {profile.age_years}</div>
                  ) : (
                    <div className="vc-member-profile__meta vc-modal__muted">Age not on file</div>
                  )}
                  {profile?.team ? (
                    <div className="vc-member-profile__meta">
                      <strong>Team:</strong> {profile.team.name}
                      {profile.team.club_name ? ` · ${profile.team.club_name}` : ""}
                    </div>
                  ) : (
                    <div className="vc-member-profile__meta vc-modal__muted">No active team roster</div>
                  )}
                  {profile?.coach_display ? (
                    <div className="vc-member-profile__meta">
                      <strong>Coach:</strong> {profile.coach_display}
                    </div>
                  ) : (
                    <div className="vc-member-profile__meta vc-modal__muted">Coach not assigned</div>
                  )}
                </div>
              </div>
            </section>

            <section className="vc-panel vc-panel--dashboard vc-member-card vc-member-card--payment">
              <h2 className="vc-member-card__title">Payment status</h2>
              {payment ? (
                <>
                  <div className="vc-member-payment__due">
                    <span className="vc-member-payment__label">Amount due</span>
                    <span className="vc-member-payment__value">{money(payment.currency, payment.amount_due)}</span>
                  </div>
                  <div className="vc-member-payment__state">
                    <span className="vc-member-payment__label">Status</span>
                    <span
                      className={`vc-member-payment__badge vc-member-payment__badge--${payment.overall_status || "pending"}`}
                    >
                      {paymentStatusLabel(payment.overall_status)}
                    </span>
                  </div>
                  {payment.open_item_count > 0 ? (
                    <p className="vc-modal__muted vc-member-payment__hint">
                      {payment.open_item_count} open fee line{payment.open_item_count === 1 ? "" : "s"}.
                    </p>
                  ) : (
                    <p className="vc-modal__muted vc-member-payment__hint">No outstanding fee lines.</p>
                  )}
                  <button
                    type="button"
                    className="vc-member-btn vc-member-btn--primary"
                    onClick={() => navigate(payment.pay_path || "/my-fees")}
                  >
                    Make payment
                  </button>
                </>
              ) : null}
            </section>
          </div>

          <div className="vc-member-dash__mid-row">
            <section className="vc-panel vc-panel--dashboard vc-member-card vc-member-card--progress">
              <h2 className="vc-member-card__title">Progress</h2>
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
            </section>

            <div className="vc-member-dash__side">
              <section className="vc-panel vc-panel--dashboard vc-member-card vc-member-card--compact">
                <h2 className="vc-member-card__title vc-member-card__title--sm">Club summary</h2>
                {club ? (
                  <>
                    <p className="vc-member-club__line">
                      <strong>{club.title}</strong>
                    </p>
                    <p className="vc-member-club__line vc-modal__muted">
                      {club.date_display} · {club.start_time_display}
                      {club.session_type_label ? ` · ${club.session_type_label}` : ""}
                    </p>
                    {club.team_name ? (
                      <p className="vc-member-club__line vc-modal__muted">{club.team_name}</p>
                    ) : null}
                  </>
                ) : (
                  <p className="vc-modal__muted" style={{ margin: 0 }}>
                    No upcoming sessions on your teams.
                  </p>
                )}
              </section>

              <button
                type="button"
                className="vc-member-btn vc-member-btn--primary vc-member-btn--block"
                onClick={() => goWithTeam(qa.confirm_attendance_path || "/player/attendance", club?.team_id)}
              >
                Confirm attendance
              </button>

              <button
                type="button"
                className="vc-panel vc-panel--dashboard vc-member-quick"
                onClick={() => {
                  window.dispatchEvent(new CustomEvent(qa.messages_event_name || "vc-open-notifications"));
                }}
              >
                <span className="vc-member-quick__title">Messages</span>
                {unread > 0 ? (
                  <span className="vc-member-quick__badge">{unread > 99 ? "99+" : unread}</span>
                ) : (
                  <span className="vc-modal__muted vc-member-quick__sub">Inbox</span>
                )}
              </button>

              <button
                type="button"
                className="vc-panel vc-panel--dashboard vc-member-quick"
                onClick={() => navigate(qa.development_progress_path || "/teams")}
              >
                <span className="vc-member-quick__title">Development progress</span>
                <span className="vc-modal__muted vc-member-quick__sub">Statistics &amp; trends</span>
              </button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
