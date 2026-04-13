import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchCurrentUser,
  fetchPlayerTeamPayments,
  fetchTeamSchedule,
  saveTeamSchedule,
} from "./api";
import ClubWorkspaceLayout, { ClubTeamSelect } from "./components/ClubWorkspaceLayout";
import { navigate } from "./navigation";
import DashboardPage from "./pages/DashboardPage";
import DirectorPaymentLogsPage from "./pages/DirectorPaymentLogsPage";
import DirectorPaymentsPage from "./pages/DirectorPaymentsPage";
import DirectorTeamSetupPage from "./pages/DirectorTeamSetupPage";
import DirectorUserManagementPage from "./pages/DirectorUserManagementPage";
import CoachPaymentsPage from "./pages/CoachPaymentsPage";
import LoginPage from "./pages/LoginPage";
import MemberHubPage from "./pages/MemberHubPage";
import MyFeesPage from "./pages/MyFeesPage";
import ParentAttendancePage from "./pages/ParentAttendancePage";
import PlayerAttendancePage from "./pages/PlayerAttendancePage";
import CoachSessionAttendancePage from "./pages/CoachSessionAttendancePage";
import TeamRosterPage from "./pages/TeamRosterPage";
import { ForgotPasswordPage, ResetPasswordPage } from "./pages/PasswordResetPages";
import RegisterPage from "./pages/RegisterPage";

const AUTH_TOKEN_KEY = "netup.auth.token";
const ACTIVE_TEAM_KEY = "netup.active.team";

const ALL_TEAMS_COLORS = ["#0d9488", "#2563eb", "#d97706", "#7c3aed", "#db2777", "#4d7c0f", "#0891b2", "#ea580c"];

const homepageImages = {
  hero: "/homepage/hero-volleyball.png",
  stripTop: "/homepage/strip-top.png",
  stripMiddle: "/homepage/strip-middle.png",
  stripBottom: "/homepage/strip-bottom.png",
};

const featureFeed = [
  {
    category: "Club Operations",
    title: "Create clubs and structure teams in minutes.",
    description:
      "Directors and coaches can launch club spaces, build squads, and keep responsibilities clear from day one.",
  },
  {
    category: "Roster Control",
    title: "Manage rosters with role-aware updates.",
    description:
      "Player assignments, coach roles, and captain changes stay organized in one shared workflow.",
  },
  {
    category: "Scheduling",
    title: "Keep practices, matches, and planning aligned.",
    description:
      "Teams can track activity and stay in sync around the rhythm of the season without scattered tools.",
  },
  {
    category: "Parent Access",
    title: "Give families connected, protected access.",
    description:
      "Parents can stay close to younger athletes while age-aware permissions protect the right self-service boundaries.",
  },
];

const platformStats = [
  {
    value: "4",
    label: "core user roles supported",
  },
  {
    value: "1",
    label: "shared workspace for the whole club",
  },
  {
    value: "24/7",
    label: "access to schedules, rosters, and updates",
  },
];

const trustBrands = [
  { name: "Mikasa", logo: "/assets/logos/mikasa.svg" },
  { name: "Molten", logo: "/assets/logos/molten.svg" },
  { name: "Wilson", logo: "/assets/logos/wilson.svg" },
  { name: "Mizuno", logo: "/assets/logos/mizuno.svg" },
  { name: "ASICS", logo: "/assets/logos/asics.svg" },
  { name: "adidas", logo: "/assets/logos/adidas.svg" },
];

const valueHighlights = [
  {
    title: "Less admin overhead",
    description:
      "Cut down on scattered messages and manual follow-ups by keeping the core club workflow in one place.",
  },
  {
    title: "Clearer team ownership",
    description:
      "Directors and coaches can see who belongs where, who is responsible for what, and what still needs attention.",
  },
  {
    title: "A better family experience",
    description:
      "Parents get visibility without clubs sacrificing structure, boundaries, or role-based access control.",
  },
];

const journeySteps = [
  {
    number: "01",
    title: "Launch your club space",
    description:
      "Set up your organization, create teams, and invite the right people without messy handoffs.",
  },
  {
    number: "02",
    title: "Keep everyone aligned",
    description:
      "Manage rosters, staff responsibilities, and day-to-day updates from one connected system.",
  },
  {
    number: "03",
    title: "Support families with confidence",
    description:
      "Give parents visibility and athletes the right level of access with age-aware controls built in.",
  },
];

const roleSpotlights = [
  {
    role: "Directors",
    title: "See the full club picture.",
    description:
      "Track teams, coaches, and memberships from a single operational view that helps the season stay organized.",
  },
  {
    role: "Coaches",
    title: "Work with cleaner rosters.",
    description:
      "Spend less time untangling lists and more time coaching with up-to-date team information.",
  },
  {
    role: "Players",
    title: "Stay connected to your team.",
    description:
      "Give athletes a clearer view of their role, their team space, and the structure around them.",
  },
  {
    role: "Parents",
    title: "Stay informed with confidence.",
    description:
      "Follow younger athletes through parent-linked access that keeps communication and visibility simple.",
  },
];

const faqs = [
  {
    question: "Who is NetUp for?",
    answer:
      "NetUp is designed for volleyball clubs that need one platform for directors, coaches, players, and parents to work together.",
  },
  {
    question: "Can parents and players use the same system?",
    answer:
      "Yes. Parent-linked access is part of the workflow, so families can stay informed while clubs keep the right boundaries in place.",
  },
  {
    question: "What makes it different from scattered tools?",
    answer:
      "Instead of splitting club operations across messages, spreadsheets, and separate apps, NetUp keeps the core workflow in one place.",
  },
];

const showcaseStrips = [
  {
    src: homepageImages.stripTop,
    alt: "Red and yellow volleyball above a blue court backdrop",
    className: "showcase-strip showcase-strip--top",
  },
  {
    src: homepageImages.stripMiddle,
    alt: "Blue and yellow volleyball over stadium seating",
    className: "showcase-strip showcase-strip--middle",
  },
  {
    src: homepageImages.stripBottom,
    alt: "White volleyball against a warm blurred background",
    className: "showcase-strip showcase-strip--bottom",
  },
];

const footerLinks = [
  { label: "Features", sectionId: "features" },
  { label: "Clubs", sectionId: "roles" },
  { label: "Teams", sectionId: "journey" },
  { label: "Parents", sectionId: "faq" },
  { label: "Contact", sectionId: "cta" },
];

function usePathname() {
  const [pathname, setPathname] = useState(window.location.pathname);

  useEffect(() => {
    const onPopState = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  return pathname;
}

function buildRelatedTeams(payload) {
  const teamsById = new Map();
  const attachChildToTeam = (existingTeam, child) => {
    const linkedChildren = existingTeam.linkedChildren || [];
    if (!linkedChildren.some((linkedChild) => linkedChild.id === child.user?.id)) {
      linkedChildren.push({
        id: child.user?.id,
        firstName: child.user?.first_name || "Child",
        lastName: child.user?.last_name || "",
        fullName:
          `${child.user?.first_name || ""} ${child.user?.last_name || ""}`.trim() || "Child",
      });
    }

    return {
      ...existingTeam,
      linkedChildren,
    };
  };

  (payload.director_teams || []).forEach((team) => {
    teamsById.set(team.id, {
      id: team.id,
      name: team.name,
      source: "Director",
      scheduleTier: "elevated",
      coachNames: team.coach_names || [],
      primaryCoachName: team.primary_coach_name || null,
      playerCount: team.player_count ?? null,
      coachCount: team.coach_count ?? null,
      captainNames: team.captain_names || [],
      captainCount: team.captain_count ?? null,
      canManageSchedule: Boolean(team.can_manage_schedule),
      canManageTraining: Boolean(team.can_manage_training),
      linkedChildren: [],
    });
  });

  (payload.coached_teams || []).forEach((team) => {
    teamsById.set(team.id, {
      id: team.id,
      name: team.name,
      source: "Coach",
      scheduleTier: "elevated",
      coachNames: team.coach_names || [],
      primaryCoachName: team.primary_coach_name || null,
      playerCount: team.player_count ?? null,
      coachCount: team.coach_count ?? null,
      captainNames: team.captain_names || [],
      captainCount: team.captain_count ?? null,
      canManageSchedule: Boolean(team.can_manage_schedule),
      canManageTraining: Boolean(team.can_manage_training),
      linkedChildren: [],
    });
  });

  (payload.player_teams || []).forEach((team) => {
    if (!teamsById.has(team.id)) {
      teamsById.set(team.id, {
        id: team.id,
        name: team.name,
        source: "Player",
        scheduleTier: "member",
        coachNames: team.coach_names || [],
        primaryCoachName: team.primary_coach_name || null,
        playerCount: team.player_count ?? null,
        coachCount: team.coach_count ?? null,
        captainNames: team.captain_names || [],
        captainCount: team.captain_count ?? null,
        canManageSchedule: Boolean(team.can_manage_schedule),
        canManageTraining: Boolean(team.can_manage_training),
        linkedChildren: [],
      });
    }
  });

  (payload.children || []).forEach((child) => {
    (child.teams || []).forEach((team) => {
      if (!teamsById.has(team.id)) {
        teamsById.set(team.id, attachChildToTeam({
          id: team.id,
          name: team.name,
          source: `${child.user?.first_name || "Child"}'s team`,
          scheduleTier: "member",
          coachNames: team.coach_names || [],
          primaryCoachName: team.primary_coach_name || null,
          playerCount: team.player_count ?? null,
          coachCount: team.coach_count ?? null,
          captainNames: team.captain_names || [],
          captainCount: team.captain_count ?? null,
          canManageSchedule: Boolean(team.can_manage_schedule),
          canManageTraining: Boolean(team.can_manage_training),
          linkedChildren: [],
        }, child));
      } else {
        teamsById.set(team.id, attachChildToTeam(teamsById.get(team.id), child));
      }
    });
  });

  return Array.from(teamsById.values());
}

function getWeekLabel(weekStartIso) {
  if (!weekStartIso) {
    return "";
  }

  const start = new Date(`${weekStartIso}T00:00:00`);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);

  const format = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  });

  return `${format.format(start)} - ${format.format(end)}`;
}

function buildWeekDays(weekStartIso) {
  if (!weekStartIso) {
    return [];
  }

  const start = new Date(`${weekStartIso}T00:00:00`);
  const weekdayFormatter = new Intl.DateTimeFormat("en-US", { weekday: "short" });
  const dayFormatter = new Intl.DateTimeFormat("en-US", { day: "numeric" });

  return Array.from({ length: 7 }, (_, index) => {
    const current = new Date(start);
    current.setDate(start.getDate() + index);
    return {
      weekday: index,
      label: weekdayFormatter.format(current).toUpperCase(),
      dayNumber: dayFormatter.format(current),
      iso: current.toISOString().slice(0, 10),
    };
  });
}

function emptyScheduleEntry() {
  return {
    weekday: "0",
    activity_name: "",
    start_time: "18:00",
    end_time: "19:30",
    location: "",
  };
}

const SCHEDULE_START_HOUR = 6;
const SCHEDULE_END_HOUR = 21;
const SCHEDULE_HOUR_HEIGHT = 64;

function parseTimeToMinutes(timeValue) {
  if (!timeValue || !timeValue.includes(":")) {
    return 0;
  }

  const [hours, minutes] = timeValue.split(":").map(Number);
  return hours * 60 + minutes;
}

function buildScheduleHours() {
  return Array.from(
    { length: SCHEDULE_END_HOUR - SCHEDULE_START_HOUR + 1 },
    (_, index) => SCHEDULE_START_HOUR + index,
  );
}

function buildScheduleRows() {
  return Array.from(
    { length: SCHEDULE_END_HOUR - SCHEDULE_START_HOUR },
    (_, index) => SCHEDULE_START_HOUR + index,
  );
}

function formatHourLabel(hour) {
  const suffix = hour >= 12 ? "PM" : "AM";
  const normalizedHour = hour % 12 || 12;
  return `${normalizedHour} ${suffix}`;
}

function normalizeScheduleEntries(entries) {
  return entries
    .filter((entry) => entry.activity_name?.trim() && entry.start_time && entry.end_time)
    .map((entry, index) => ({
      id: entry.id || `draft-${index}`,
      weekday: Number(entry.weekday),
      activity_name: entry.activity_name.trim(),
      start_time: entry.start_time,
      end_time: entry.end_time,
      location: entry.location || "",
      teamColor: entry.teamColor,
      teamName: entry.teamName,
      isTrainingSession: entry.isTrainingSession,
    }));
}

function scheduleIntervalsOverlap(startA, endA, startB, endB) {
  return startA < endB && endA > startB;
}

function clusterOverlappingScheduleEntries(dayEntries) {
  const n = dayEntries.length;
  if (!n) {
    return [];
  }
  const adj = Array.from({ length: n }, () => []);
  for (let i = 0; i < n; i += 1) {
    for (let j = i + 1; j < n; j += 1) {
      const a = dayEntries[i];
      const b = dayEntries[j];
      const as = parseTimeToMinutes(a.start_time);
      const ae = parseTimeToMinutes(a.end_time);
      const bs = parseTimeToMinutes(b.start_time);
      const be = parseTimeToMinutes(b.end_time);
      if (scheduleIntervalsOverlap(as, ae, bs, be)) {
        adj[i].push(j);
        adj[j].push(i);
      }
    }
  }
  const visited = new Set();
  const clusters = [];
  for (let i = 0; i < n; i += 1) {
    if (visited.has(i)) {
      continue;
    }
    const stack = [i];
    const indices = [];
    visited.add(i);
    while (stack.length) {
      const u = stack.pop();
      indices.push(u);
      for (const v of adj[u]) {
        if (!visited.has(v)) {
          visited.add(v);
          stack.push(v);
        }
      }
    }
    clusters.push(indices.map((idx) => dayEntries[idx]));
  }
  return clusters;
}

function layoutScheduleOverlapCluster(cluster) {
  const layout = new Map();
  if (!cluster.length) {
    return layout;
  }
  const sorted = [...cluster].sort(
    (a, b) => parseTimeToMinutes(a.start_time) - parseTimeToMinutes(b.start_time),
  );
  const active = [];
  let maxCols = 0;
  for (const e of sorted) {
    const start = parseTimeToMinutes(e.start_time);
    const end = parseTimeToMinutes(e.end_time);
    for (let i = active.length - 1; i >= 0; i -= 1) {
      if (active[i].end <= start) {
        active.splice(i, 1);
      }
    }
    const usedCols = new Set(active.map((row) => row.col));
    let col = 0;
    while (usedCols.has(col)) {
      col += 1;
    }
    active.push({ end, col });
    maxCols = Math.max(maxCols, active.length);
    layout.set(e.id, { col, maxCols: 0 });
  }
  for (const e of cluster) {
    const row = layout.get(e.id);
    if (row) {
      row.maxCols = maxCols;
    }
  }
  return layout;
}

function buildScheduleOverlapLayoutByEntryId(dayEntries) {
  const combined = new Map();
  if (!dayEntries?.length) {
    return combined;
  }
  for (const cluster of clusterOverlappingScheduleEntries(dayEntries)) {
    const partial = layoutScheduleOverlapCluster(cluster);
    partial.forEach((value, key) => combined.set(key, value));
  }
  return combined;
}

function scheduleEventHorizontalStyle(layout, entryId) {
  const slot = layout.get(entryId);
  const maxCols = slot?.maxCols ?? 1;
  const col = slot?.col ?? 0;
  if (maxCols <= 1) {
    return { left: "0.55rem", right: "0.55rem" };
  }
  const gapPx = 4;
  const slice = `(100% - 1.1rem - ${(maxCols - 1) * gapPx}px) / ${maxCols}`;
  return {
    left: `calc(0.55rem + ${col} * (${slice} + ${gapPx}px))`,
    width: `calc(${slice})`,
    right: "auto",
  };
}

function ScheduleEditor({ draftEntries, onChangeEntry, onAddEntry, onRemoveEntry, onSave, isSaving }) {
  return (
    <section className="schedule-editor-card">
      <div className="schedule-editor-card__top">
        <div>
          <p className="teams-page-kicker" style={{ fontSize: "0.7rem", marginBottom: "0.15rem" }}>Coach Controls</p>
          <h2 style={{ fontSize: "1.1rem", margin: 0 }}>Edit Team Schedule</h2>
        </div>
        <button type="button" className="team-card__button team-card__button--ghost" onClick={onAddEntry}>
          Add Activity
        </button>
      </div>

      <div className="schedule-form-list">
        {draftEntries.map((entry, index) => (
          <div key={`draft-${index}`} className="schedule-form-row">
            <select
              value={entry.weekday}
              onChange={(event) => onChangeEntry(index, "weekday", event.target.value)}
            >
              <option value="0">Monday</option>
              <option value="1">Tuesday</option>
              <option value="2">Wednesday</option>
              <option value="3">Thursday</option>
              <option value="4">Friday</option>
              <option value="5">Saturday</option>
              <option value="6">Sunday</option>
            </select>
            <input
              type="text"
              placeholder="Activity name"
              value={entry.activity_name}
              onChange={(event) => onChangeEntry(index, "activity_name", event.target.value)}
            />
            <input
              type="time"
              value={entry.start_time}
              onChange={(event) => onChangeEntry(index, "start_time", event.target.value)}
            />
            <input
              type="time"
              value={entry.end_time}
              onChange={(event) => onChangeEntry(index, "end_time", event.target.value)}
            />
            <input
              type="text"
              placeholder="Location"
              value={entry.location}
              onChange={(event) => onChangeEntry(index, "location", event.target.value)}
            />
            <button type="button" className="schedule-form-row__remove" onClick={() => onRemoveEntry(index)}>
              Remove
            </button>
          </div>
        ))}
      </div>

      <div className="schedule-editor-card__actions">
        <button type="button" className="team-card__button" onClick={onSave} disabled={isSaving}>
          {isSaving ? "Saving..." : "Save Schedule"}
        </button>
      </div>
    </section>
  );
}

function WeeklyScheduleBoard({ weekStart, entries, onSelectEntry, legendTeams }) {
  const [hoverTip, setHoverTip] = useState(null);

  const weekDays = buildWeekDays(weekStart);
  const scheduleHours = buildScheduleHours();
  const scheduleRows = buildScheduleRows();
  const normalizedEntries = normalizeScheduleEntries(entries);
  const entriesByWeekday = normalizedEntries.reduce((accumulator, entry) => {
    const key = Number(entry.weekday);
    accumulator[key] = accumulator[key] || [];
    accumulator[key].push(entry);
    return accumulator;
  }, {});

  weekDays.forEach((day) => {
    entriesByWeekday[day.weekday] = (entriesByWeekday[day.weekday] || []).sort((left, right) =>
      left.start_time.localeCompare(right.start_time),
    );
  });

  const soleLegendColor = legendTeams?.length === 1 ? legendTeams[0].color : null;

  return (
    <section className="weekly-schedule-card">
      <div className="weekly-schedule-card__header">
        <h2>Week of {getWeekLabel(weekStart)}</h2>
      </div>

      {legendTeams?.length ? (
        <div
          aria-label="Team colors"
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "0.65rem",
            margin: "0.35rem 0 1rem",
            fontSize: "0.85rem",
            color: "#4a5563",
          }}
        >
          {legendTeams.map((row) => (
            <span key={row.id} style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
              <span
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: 3,
                  backgroundColor: row.color,
                  flexShrink: 0,
                }}
                aria-hidden="true"
              />
              {row.name}
            </span>
          ))}
        </div>
      ) : null}

      <div className="weekly-schedule-layout">
        <div className="weekly-schedule-times">
          {scheduleHours.map((hour) => (
            <div key={hour} className="weekly-schedule-times__slot">
              {formatHourLabel(hour)}
            </div>
          ))}
        </div>

        <div className="weekly-schedule-grid">
          {weekDays.map((day) => {
            const dayEntries = entriesByWeekday[day.weekday] || [];
            const overlapLayout = buildScheduleOverlapLayoutByEntryId(dayEntries);
            return (
            <div key={day.iso} className="weekly-schedule-day">
              <header
                className="weekly-schedule-day__header"
                style={soleLegendColor ? { borderTop: `3px solid ${soleLegendColor}` } : undefined}
              >
                <span>{day.label}</span>
                <strong style={soleLegendColor ? { color: soleLegendColor } : undefined}>{day.dayNumber}</strong>
              </header>

              <div className="weekly-schedule-day__track">
                {scheduleRows.map((hour) => (
                  <div key={`${day.iso}-${hour}`} className="weekly-schedule-day__hour-line" />
                ))}

                {dayEntries.map((entry) => {
                  const startMinutes = parseTimeToMinutes(entry.start_time);
                  const endMinutes = parseTimeToMinutes(entry.end_time);
                  const clippedStartMinutes = Math.max(startMinutes, SCHEDULE_START_HOUR * 60);
                  const clippedEndMinutes = Math.min(endMinutes, SCHEDULE_END_HOUR * 60);
                  const minutesFromTop = clippedStartMinutes - SCHEDULE_START_HOUR * 60;
                  const durationMinutes = Math.max(clippedEndMinutes - clippedStartMinutes, 30);
                  const hz = scheduleEventHorizontalStyle(overlapLayout, entry.id);
                  const entryKey = String(entry.id);
                  const isHoverTarget = hoverTip && String(hoverTip.entry?.id) === entryKey;

                  return (
                    <article
                      key={entry.id}
                      className={`schedule-event${entry.isTrainingSession ? " schedule-event--interactive" : ""}${
                        entry.teamColor ? " schedule-event--team-colored" : ""
                      }`}
                      style={{
                        top: `${(minutesFromTop / 60) * SCHEDULE_HOUR_HEIGHT}px`,
                        height: `${(durationMinutes / 60) * SCHEDULE_HOUR_HEIGHT}px`,
                        boxSizing: "border-box",
                        zIndex: isHoverTarget ? 12 : 2,
                        ...hz,
                        ...(entry.teamColor
                          ? {
                              "--event-team-bg": entry.teamColor,
                            }
                          : {}),
                      }}
                      onPointerEnter={(e) => {
                        setHoverTip({ entry, x: e.clientX + 12, y: e.clientY + 10 });
                      }}
                      onPointerMove={(e) => {
                        setHoverTip((prev) =>
                          prev && String(prev.entry?.id) === entryKey
                            ? { entry, x: e.clientX + 12, y: e.clientY + 10 }
                            : prev,
                        );
                      }}
                      onPointerLeave={() => {
                        setHoverTip((prev) => (prev && String(prev.entry?.id) === entryKey ? null : prev));
                      }}
                      onClick={() => {
                        if (onSelectEntry) {
                          onSelectEntry(entry);
                        }
                      }}
                    >
                      <span className="schedule-event__time">
                        {entry.start_time} - {entry.end_time}
                      </span>
                      <strong>{entry.activity_name}</strong>
                      {entry.teamName ? (
                        <span style={{ display: "block", fontSize: "0.72rem", opacity: 0.9 }}>{entry.teamName}</span>
                      ) : null}
                      {entry.location ? <em>{entry.location}</em> : null}
                    </article>
                  );
                })}

                {dayEntries.length ? null : (
                  <p className="weekly-schedule-day__empty">No activity</p>
                )}
              </div>
            </div>
            );
          })}
        </div>
      </div>

      {hoverTip ? (
        <div
          className="schedule-hover-popover"
          style={{
            position: "fixed",
            left: `${Math.min(
              Math.max(12, hoverTip.x),
              typeof window !== "undefined" ? window.innerWidth - 300 : hoverTip.x,
            )}px`,
            top: `${Math.min(
              hoverTip.y,
              typeof window !== "undefined" ? window.innerHeight - 220 : hoverTip.y,
            )}px`,
            zIndex: 10060,
          }}
          role="tooltip"
        >
          <div className="schedule-hover-popover__title">{hoverTip.entry.activity_name}</div>
          {hoverTip.entry.teamName ? (
            <div className="schedule-hover-popover__row">
              <span className="schedule-hover-popover__label">Team</span>
              <span>{hoverTip.entry.teamName}</span>
            </div>
          ) : null}
          <div className="schedule-hover-popover__row">
            <span className="schedule-hover-popover__label">Time</span>
            <span>
              {hoverTip.entry.start_time} – {hoverTip.entry.end_time}
            </span>
          </div>
          {hoverTip.entry.location ? (
            <div className="schedule-hover-popover__row">
              <span className="schedule-hover-popover__label">Location</span>
              <span>{hoverTip.entry.location}</span>
            </div>
          ) : null}
          {hoverTip.entry.isTrainingSession ? (
            <div className="schedule-hover-popover__muted">Training session (tap for details if available)</div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function SchedulePaymentEntries({ activeTeamId, teams }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!activeTeamId) {
      setRows([]);
      return;
    }
    setLoading(true);
    try {
      if (activeTeamId === "__all__") {
        if (!teams.length) {
          setRows([]);
          return;
        }
        const results = await Promise.all(teams.map((t) => fetchPlayerTeamPayments(t.id)));
        const merged = [];
        teams.forEach((team, i) => {
          const color = ALL_TEAMS_COLORS[i % ALL_TEAMS_COLORS.length];
          for (const r of results[i]?.fee_rows || []) {
            if (r.status === "paid") continue;
            merged.push({ ...r, _teamName: team.name, _teamColor: color });
          }
        });
        setRows(merged);
        return;
      }
      const data = await fetchPlayerTeamPayments(activeTeamId);
      setRows((data.fee_rows || []).filter((r) => r.status !== "paid"));
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [activeTeamId, teams]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!activeTeamId || loading || !rows.length) return null;

  const showTeam = activeTeamId === "__all__";

  return (
    <section className="schedule-payments-section" style={{ marginTop: "1.5rem", padding: "0 0.5rem" }}>
      <h2 style={{ fontSize: "1.05rem", marginBottom: "0.5rem" }}>Upcoming payments</h2>
      <div style={{ overflowX: "auto" }}>
        <table className="vc-table" style={{ fontSize: "0.9rem" }}>
          <thead>
            <tr>
              {showTeam ? <th>Team</th> : null}
              <th>Description</th>
              <th>Amount</th>
              <th>Due date</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r._teamName || ""}-${r.id}`}>
                {showTeam ? (
                  <td>
                    <span
                      style={{
                        display: "inline-block",
                        width: 10,
                        height: 10,
                        borderRadius: 2,
                        marginRight: 6,
                        verticalAlign: "middle",
                        backgroundColor: r._teamColor,
                      }}
                      aria-hidden="true"
                    />
                    {r._teamName}
                  </td>
                ) : null}
                <td>{r.description}</td>
                <td>
                  {r.currency} {r.remaining}
                </td>
                <td>{r.due_date}</td>
                <td>
                  {r.status === "overdue" ? (
                    <span className="vc-status-overdue">Overdue</span>
                  ) : (
                    <span className="vc-status-pending">Pending</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TeamsPage() {
  return (
    <section style={{ padding: "3rem 2rem", maxWidth: 640, margin: "0 auto", textAlign: "center" }}>
      <h1 style={{ fontSize: "1.5rem", marginBottom: "0.75rem" }}>Statistics</h1>
      <p style={{ color: "#5c6570", lineHeight: 1.55, maxWidth: 420, margin: "0 auto" }}>
        Team and player statistics will appear here in a future update.
        Use the team selector in the toolbar to pick your active team, then
        visit Schedule, Training, or Roster for team-specific views.
      </p>
    </section>
  );
}

function App() {
  const pathname = usePathname();
  const [isAuthenticated, setIsAuthenticated] = useState(
    Boolean(localStorage.getItem(AUTH_TOKEN_KEY)),
  );
  const [teams, setTeams] = useState([]);
  const [scheduleAccessElevated, setScheduleAccessElevated] = useState(false);
  const [activeTeamId, setActiveTeamId] = useState(() => localStorage.getItem(ACTIVE_TEAM_KEY) || "");
  const [schedulePayload, setSchedulePayload] = useState(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [scheduleError, setScheduleError] = useState("");
  const [draftEntries, setDraftEntries] = useState([]);
  const [isSavingSchedule, setIsSavingSchedule] = useState(false);
  const [selectedChildIdByTeam, setSelectedChildIdByTeam] = useState({});
  const [directorDashboardAllowed, setDirectorDashboardAllowed] = useState(null);
  const [viewerAccountRole, setViewerAccountRole] = useState(null);
  const [teamsRefreshKey, setTeamsRefreshKey] = useState(0);
  const scheduleTeams = useMemo(
    () => (scheduleAccessElevated ? teams : teams.filter((t) => t.scheduleTier === "member")),
    [teams, scheduleAccessElevated],
  );

  const playerTeamsOnly = useMemo(
    () => teams.filter((t) => t.source === "Player"),
    [teams],
  );

  const showPlayerSessionsTab = playerTeamsOnly.length > 0;

  const coachAttendanceTeams = useMemo(() => teams.filter((t) => t.canManageTraining), [teams]);
  const showCoachAttendanceTab = coachAttendanceTeams.length > 0;

  const activeTeam = useMemo(() => {
    if (String(activeTeamId) === "__all__" && teams.length > 0) {
      return {
        id: "__all__",
        name: "View all",
        canManageSchedule: false,
        canManageTraining: false,
        linkedChildren: [],
      };
    }
    return teams.find((team) => String(team.id) === String(activeTeamId)) || null;
  }, [activeTeamId, teams]);

  useEffect(() => {
    const onSetActiveTeam = (event) => {
      const raw = event?.detail?.teamId;
      if (raw == null || raw === "") {
        return;
      }
      const nextTeamId = String(raw);
      setActiveTeamId(nextTeamId);
      localStorage.setItem(ACTIVE_TEAM_KEY, nextTeamId);
    };
    window.addEventListener("netup-set-active-team", onSetActiveTeam);
    return () => window.removeEventListener("netup-set-active-team", onSetActiveTeam);
  }, []);

  useEffect(() => {
    if (pathname !== "/") {
      return undefined;
    }

    let observer = null;
    const timerId = requestAnimationFrame(() => {
      const revealElements = document.querySelectorAll(".reveal-on-scroll");

      if (!revealElements.length) {
        return;
      }

      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        revealElements.forEach((element) => {
          element.classList.add("is-visible");
        });
        return;
      }

      observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) {
              return;
            }

            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          });
        },
        {
          threshold: 0.15,
          rootMargin: "0px 0px -5% 0px",
        },
      );

      revealElements.forEach((element) => {
        observer.observe(element);
      });
    });

    return () => {
      cancelAnimationFrame(timerId);
      if (observer) {
        observer.disconnect();
      }
    };
  }, [pathname, isAuthenticated]);

  useEffect(() => {
    const updateAuthState = () => {
      setIsAuthenticated(Boolean(localStorage.getItem(AUTH_TOKEN_KEY)));
    };

    const onStorage = (event) => {
      if (!event.key || event.key === AUTH_TOKEN_KEY) {
        updateAuthState();
      }
    };

    window.addEventListener("storage", onStorage);
    window.addEventListener("auth-state-changed", updateAuthState);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("auth-state-changed", updateAuthState);
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function loadTeams() {
      if (!isAuthenticated) {
        setDirectorDashboardAllowed(null);
        setViewerAccountRole(null);
        setScheduleAccessElevated(false);
        setTeams([]);
        setActiveTeamId("");
        localStorage.removeItem(ACTIVE_TEAM_KEY);
        return;
      }

      try {
        const payload = await fetchCurrentUser();
        if (!isMounted) {
          return;
        }

        setViewerAccountRole(payload.user?.assigned_account_role || null);

        const owned = (payload.owned_clubs || []).length > 0;
        const flaggedDirector = payload.is_director_or_staff === true;
        setDirectorDashboardAllowed(flaggedDirector || owned);

        const elevated =
          (payload.director_teams || []).length > 0 || (payload.coached_teams || []).length > 0;
        setScheduleAccessElevated(Boolean(elevated));

        const relatedTeams = buildRelatedTeams(payload);
        setTeams(relatedTeams);
      } catch {
        if (!isMounted) {
          return;
        }
        setDirectorDashboardAllowed(false);
        setViewerAccountRole(null);
        setScheduleAccessElevated(false);
        setTeams([]);
        setActiveTeamId("");
      }
    }

    loadTeams();

    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, teamsRefreshKey]);

  useEffect(() => {
    const bump = () => setTeamsRefreshKey((k) => k + 1);
    window.addEventListener("netup-teams-changed", bump);
    return () => window.removeEventListener("netup-teams-changed", bump);
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    if (!teams.length) {
      setActiveTeamId("");
      localStorage.removeItem(ACTIVE_TEAM_KEY);
      return;
    }

    const hasValidSelectedTeam =
      (String(activeTeamId) === "__all__" && teams.length > 0) ||
      teams.some((team) => String(team.id) === String(activeTeamId));

    if (!hasValidSelectedTeam) {
      setActiveTeamId("");
      localStorage.removeItem(ACTIVE_TEAM_KEY);
    }
  }, [activeTeamId, isAuthenticated, teams]);

  useEffect(() => {
    if (pathname !== "/schedule" || !isAuthenticated) {
      return undefined;
    }
    if (String(activeTeamId) === "__all__" && scheduleTeams.length <= 1) {
      setActiveTeamId("");
      localStorage.removeItem(ACTIVE_TEAM_KEY);
      return undefined;
    }
    if (!activeTeamId) {
      return undefined;
    }
    if (String(activeTeamId) === "__all__") {
      return undefined;
    }
    const ok = scheduleTeams.some((t) => String(t.id) === String(activeTeamId));
    if (!ok) {
      setActiveTeamId("");
      localStorage.removeItem(ACTIVE_TEAM_KEY);
    }
    return undefined;
  }, [pathname, activeTeamId, scheduleTeams, isAuthenticated]);

  useEffect(() => {
    if (pathname !== "/player/attendance" && pathname !== "/player/attendance/") {
      return undefined;
    }
    if (!isAuthenticated || !playerTeamsOnly.length) {
      return undefined;
    }
    const ok = playerTeamsOnly.some((t) => String(t.id) === String(activeTeamId));
    if (!ok) {
      const nextId = String(playerTeamsOnly[0].id);
      setActiveTeamId(nextId);
      localStorage.setItem(ACTIVE_TEAM_KEY, nextId);
    }
    return undefined;
  }, [pathname, isAuthenticated, playerTeamsOnly, activeTeamId]);

  useEffect(() => {
    if (pathname !== "/coach/attendance" && pathname !== "/coach/attendance/") {
      return undefined;
    }
    if (!isAuthenticated || !coachAttendanceTeams.length) {
      return undefined;
    }
    const ok = coachAttendanceTeams.some((t) => String(t.id) === String(activeTeamId));
    if (!ok && coachAttendanceTeams[0]) {
      const nextId = String(coachAttendanceTeams[0].id);
      setActiveTeamId(nextId);
      localStorage.setItem(ACTIVE_TEAM_KEY, nextId);
    }
    return undefined;
  }, [pathname, isAuthenticated, coachAttendanceTeams, activeTeamId]);

  useEffect(() => {
    if (!teams.length) {
      setSelectedChildIdByTeam({});
      return;
    }

    setSelectedChildIdByTeam((currentState) => {
      const nextState = { ...currentState };

      teams.forEach((team) => {
        const teamKey = String(team.id);
        const childOptions = team.linkedChildren || [];
        if (!childOptions.length) {
          delete nextState[teamKey];
          return;
        }

        const currentChildId = String(nextState[teamKey] || "");
        const hasValidSelection = childOptions.some(
          (child) => String(child.id) === currentChildId,
        );

        if (!hasValidSelection) {
          nextState[teamKey] = String(childOptions[0].id);
        }
      });

      return nextState;
    });
  }, [teams]);

  useEffect(() => {
    if (pathname !== "/schedule") {
      return undefined;
    }
    if (!activeTeamId) {
      setSchedulePayload(null);
      setScheduleError("");
      setScheduleLoading(false);
      return undefined;
    }

    let isMounted = true;

    async function loadSchedule() {
      setScheduleLoading(true);
      setScheduleError("");

      try {
        if (String(activeTeamId) === "__all__") {
          if (!scheduleTeams.length) {
            if (!isMounted) return;
            setSchedulePayload(null);
            setDraftEntries([emptyScheduleEntry()]);
            return;
          }
          const payloads = await Promise.all(scheduleTeams.map((t) => fetchTeamSchedule(t.id)));
          if (!isMounted) return;
          const weekStart = payloads[0]?.week_start ?? null;
          const legend = scheduleTeams.map((t, i) => ({
            id: t.id,
            name: t.name,
            color: ALL_TEAMS_COLORS[i % ALL_TEAMS_COLORS.length],
          }));
          const mergedEntries = [];
          scheduleTeams.forEach((team, i) => {
            const color = legend[i].color;
            for (const e of payloads[i]?.entries || []) {
              mergedEntries.push({
                ...e,
                teamColor: color,
                teamName: team.name,
                id: `${team.id}-${e.id}`,
              });
            }
          });
          setSchedulePayload({ week_start: weekStart, entries: mergedEntries, legend });
          setDraftEntries([emptyScheduleEntry()]);
        } else {
          const payload = await fetchTeamSchedule(activeTeamId);
          if (!isMounted) {
            return;
          }

          setSchedulePayload(payload);
          setDraftEntries(
            payload.entries.length
              ? payload.entries.map((entry) => ({
                  weekday: String(entry.weekday),
                  activity_name: entry.activity_name,
                  start_time: entry.start_time,
                  end_time: entry.end_time,
                  location: entry.location || "",
                }))
              : [emptyScheduleEntry()],
          );
        }
      } catch (error) {
        if (!isMounted) {
          return;
        }
        setSchedulePayload(null);
        setScheduleError(error.message || "Failed to load schedule.");
      } finally {
        if (isMounted) {
          setScheduleLoading(false);
        }
      }
    }

    void loadSchedule();

    return () => {
      isMounted = false;
    };
  }, [activeTeamId, pathname, scheduleTeams]);

  const selectedChildId = activeTeam?.linkedChildren?.length
    ? Number(selectedChildIdByTeam[String(activeTeamId)] || activeTeam.linkedChildren[0].id)
    : null;

  const scrollToSection = (sectionId) => {
    const section = document.getElementById(sectionId);

    if (!section) {
      return;
    }

    section.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleSelectTeam = (team) => {
    const nextTeamId = String(team.id);
    setActiveTeamId(nextTeamId);
    localStorage.setItem(ACTIVE_TEAM_KEY, nextTeamId);
  };

  const openTeamSchedule = (team) => {
    handleSelectTeam(team);
    navigate("/schedule");
  };

  const updateDraftEntry = (index, field, value) => {
    setDraftEntries((currentEntries) =>
      currentEntries.map((entry, entryIndex) =>
        entryIndex === index ? { ...entry, [field]: value } : entry,
      ),
    );
  };

  const addDraftEntry = () => {
    setDraftEntries((currentEntries) => [...currentEntries, emptyScheduleEntry()]);
  };

  const removeDraftEntry = (index) => {
    setDraftEntries((currentEntries) => {
      const nextEntries = currentEntries.filter((_, entryIndex) => entryIndex !== index);
      return nextEntries.length ? nextEntries : [emptyScheduleEntry()];
    });
  };

  const handleSaveSchedule = async () => {
    if (!activeTeamId || String(activeTeamId) === "__all__") {
      return;
    }

    setIsSavingSchedule(true);
    setScheduleError("");

    try {
      const payload = await saveTeamSchedule(
        activeTeamId,
        draftEntries
          .filter((entry) => entry.activity_name.trim())
          .map((entry) => ({
            weekday: Number(entry.weekday),
            activity_name: entry.activity_name.trim(),
            start_time: entry.start_time,
            end_time: entry.end_time,
            location: entry.location.trim(),
          })),
      );
      setSchedulePayload(payload);
      setDraftEntries(
        payload.entries.length
          ? payload.entries.map((entry) => ({
              weekday: String(entry.weekday),
              activity_name: entry.activity_name,
              start_time: entry.start_time,
              end_time: entry.end_time,
              location: entry.location || "",
            }))
          : [emptyScheduleEntry()],
      );
    } catch (error) {
      setScheduleError(error.message || "Failed to save schedule.");
    } finally {
      setIsSavingSchedule(false);
    }
  };

  const handleSelectChildForActiveTeam = (childId) => {
    if (!activeTeamId) {
      return;
    }

    setSelectedChildIdByTeam((currentState) => ({
      ...currentState,
      [String(activeTeamId)]: String(childId),
    }));
  };

  if (pathname === "/login") {
    return <LoginPage />;
  }

  if (pathname === "/forgot-password") {
    return <ForgotPasswordPage />;
  }

  if (pathname === "/forgot-password/reset") {
    return <ResetPasswordPage />;
  }

  if (pathname === "/register") {
    return <RegisterPage />;
  }

  if (pathname === "/dashboard" || pathname === "/club" || pathname === "/club/") {
    if (!isAuthenticated) {
      return <LoginPage />;
    }
    if (directorDashboardAllowed === null) {
      return (
        <div className="vc-app vc-dashboard" style={{ padding: "3rem", textAlign: "center" }}>
          <p className="vc-modal__muted">Loading…</p>
        </div>
      );
    }
    if (directorDashboardAllowed) {
      return <DashboardPage />;
    }
    return <MemberHubPage />;
  }

  if (pathname === "/director/users") {
    if (!isAuthenticated) {
      return <LoginPage />;
    }
    if (directorDashboardAllowed === null) {
      return (
        <div className="vc-app vc-dashboard" style={{ padding: "3rem", textAlign: "center" }}>
          <p className="vc-modal__muted">Loading…</p>
        </div>
      );
    }
    if (!directorDashboardAllowed) {
      return (
        <div className="vc-app vc-dashboard" style={{ padding: "3rem", maxWidth: 520, margin: "0 auto" }}>
          <h1 style={{ fontSize: "1.25rem", marginBottom: "0.75rem" }}>Director tools</h1>
          <p style={{ color: "#5c6570", lineHeight: 1.55 }}>
            Pending account review is limited to club directors and platform staff.
          </p>
          <button
            type="button"
            className="vc-action-btn"
            style={{ marginTop: "1.25rem" }}
            onClick={() => navigate("/dashboard")}
          >
            <span>Back to dashboard</span>
            <span aria-hidden="true">›</span>
          </button>
        </div>
      );
    }
    return <DirectorUserManagementPage />;
  }

  if (pathname === "/director/teams" || pathname === "/director/teams/") {
    if (!isAuthenticated) {
      return <LoginPage />;
    }
    if (directorDashboardAllowed === null) {
      return (
        <div className="vc-app vc-dashboard" style={{ padding: "3rem", textAlign: "center" }}>
          <p className="vc-modal__muted">Loading…</p>
        </div>
      );
    }
    if (!directorDashboardAllowed) {
      return (
        <div className="vc-app vc-dashboard" style={{ padding: "3rem", maxWidth: 520, margin: "0 auto" }}>
          <h1 style={{ fontSize: "1.25rem", marginBottom: "0.75rem" }}>Director tools</h1>
          <p style={{ color: "#5c6570", lineHeight: 1.55 }}>
            Creating teams and roster is limited to club directors and platform staff.
          </p>
          <button
            type="button"
            className="vc-action-btn"
            style={{ marginTop: "1.25rem" }}
            onClick={() => navigate("/dashboard")}
          >
            <span>Back to dashboard</span>
            <span aria-hidden="true">›</span>
          </button>
        </div>
      );
    }
    return <DirectorTeamSetupPage />;
  }

  if (pathname === "/director/payments" || pathname === "/director/payments/") {
    if (!isAuthenticated) {
      return <LoginPage />;
    }
    if (directorDashboardAllowed === null) {
      return (
        <div className="vc-app vc-dashboard" style={{ padding: "3rem", textAlign: "center" }}>
          <p className="vc-modal__muted">Loading…</p>
        </div>
      );
    }
    if (!directorDashboardAllowed) {
      return (
        <div className="vc-app vc-dashboard" style={{ padding: "3rem", maxWidth: 520, margin: "0 auto" }}>
          <h1 style={{ fontSize: "1.25rem", marginBottom: "0.75rem" }}>Director tools</h1>
          <p style={{ color: "#5c6570", lineHeight: 1.55 }}>
            Payment management is only available to club directors and platform staff.
          </p>
          <button
            type="button"
            className="vc-action-btn"
            style={{ marginTop: "1.25rem" }}
            onClick={() => navigate("/dashboard")}
          >
            <span>Back to dashboard</span>
            <span aria-hidden="true">›</span>
          </button>
        </div>
      );
    }
    return <DirectorPaymentsPage />;
  }

  if (pathname === "/director/payments/logs" || pathname === "/director/payments/logs/") {
    if (!isAuthenticated) {
      return <LoginPage />;
    }
    if (directorDashboardAllowed === null) {
      return (
        <div className="vc-app vc-dashboard" style={{ padding: "3rem", textAlign: "center" }}>
          <p className="vc-modal__muted">Loading…</p>
        </div>
      );
    }
    if (!directorDashboardAllowed) {
      return (
        <div className="vc-app vc-dashboard" style={{ padding: "3rem", maxWidth: 520, margin: "0 auto" }}>
          <h1 style={{ fontSize: "1.25rem", marginBottom: "0.75rem" }}>Director tools</h1>
          <p style={{ color: "#5c6570", lineHeight: 1.55 }}>
            Payment logs are only available to club directors and platform staff.
          </p>
          <button
            type="button"
            className="vc-action-btn"
            style={{ marginTop: "1.25rem" }}
            onClick={() => navigate("/dashboard")}
          >
            <span>Back to dashboard</span>
            <span aria-hidden="true">›</span>
          </button>
        </div>
      );
    }
    return <DirectorPaymentLogsPage />;
  }

  if (pathname === "/parent/attendance" || pathname === "/parent/attendance/") {
    if (!isAuthenticated) {
      return <LoginPage />;
    }
    return (
      <ClubWorkspaceLayout
        activeTab="parent-attendance"
        viewerAccountRole={viewerAccountRole}
        showPlayerSessionsTab={showPlayerSessionsTab}
        showCoachAttendanceTab={showCoachAttendanceTab}
      >
        <ParentAttendancePage />
      </ClubWorkspaceLayout>
    );
  }

  if (pathname === "/coach/attendance" || pathname === "/coach/attendance/") {
    if (!isAuthenticated) {
      return <LoginPage />;
    }
    if (!showCoachAttendanceTab) {
      return (
        <ClubWorkspaceLayout
          activeTab=""
          viewerAccountRole={viewerAccountRole}
          showPlayerSessionsTab={showPlayerSessionsTab}
          showCoachAttendanceTab={showCoachAttendanceTab}
        >
          <section className="teams-page-shell" style={{ padding: "1.5rem" }}>
            <h1 style={{ fontSize: "1.2rem" }}>Session attendance</h1>
            <p className="vc-modal__muted" style={{ marginTop: "0.75rem" }}>
              Only coaches and club directors with training access can view per-session attendance planning.
            </p>
          </section>
        </ClubWorkspaceLayout>
      );
    }
    return (
      <ClubWorkspaceLayout
        activeTab="coach-attendance"
        viewerAccountRole={viewerAccountRole}
        showPlayerSessionsTab={showPlayerSessionsTab}
        showCoachAttendanceTab={showCoachAttendanceTab}
        beforeIconActions={
          <ClubTeamSelect
            teams={coachAttendanceTeams}
            activeTeamId={activeTeamId}
            onChangeTeam={handleSelectTeam}
            selectId="coach-attendance-team"
          />
        }
      >
        <CoachSessionAttendancePage activeTeam={activeTeam} />
      </ClubWorkspaceLayout>
    );
  }

  if (pathname === "/player/attendance" || pathname === "/player/attendance/") {
    if (!isAuthenticated) {
      return <LoginPage />;
    }
    if (!showPlayerSessionsTab) {
      return (
        <ClubWorkspaceLayout
          activeTab="player-attendance"
          viewerAccountRole={viewerAccountRole}
          showPlayerSessionsTab={showPlayerSessionsTab}
          showCoachAttendanceTab={showCoachAttendanceTab}
        >
          <section className="teams-page-shell" style={{ padding: "1.5rem" }}>
            <h1 style={{ fontSize: "1.2rem" }}>My sessions</h1>
            <p className="vc-modal__muted" style={{ marginTop: "0.75rem" }}>
              You are not on any roster as a player. When a director adds you as a player, you can confirm attendance
              for your team here.
            </p>
          </section>
        </ClubWorkspaceLayout>
      );
    }
    return (
      <ClubWorkspaceLayout
        activeTab="player-attendance"
        viewerAccountRole={viewerAccountRole}
        showPlayerSessionsTab={showPlayerSessionsTab}
        showCoachAttendanceTab={showCoachAttendanceTab}
        beforeIconActions={
          <ClubTeamSelect
            teams={playerTeamsOnly}
            activeTeamId={activeTeamId}
            onChangeTeam={handleSelectTeam}
            selectId="player-attendance-team"
          />
        }
      >
        <PlayerAttendancePage activeTeam={activeTeam} />
      </ClubWorkspaceLayout>
    );
  }

  if (pathname === "/teams") {
    return (
      <ClubWorkspaceLayout
        activeTab=""
        viewerAccountRole={viewerAccountRole}
        showPlayerSessionsTab={showPlayerSessionsTab}
        showCoachAttendanceTab={showCoachAttendanceTab}
        beforeIconActions={
          <ClubTeamSelect
            teams={teams}
            activeTeamId={activeTeamId}
            onChangeTeam={handleSelectTeam}
            selectId="teams-workspace-team"
          />
        }
      >
        <TeamsPage />
      </ClubWorkspaceLayout>
    );
  }

  if (pathname === "/roster" || pathname === "/roster/") {
    return (
      <ClubWorkspaceLayout
        activeTab=""
        viewerAccountRole={viewerAccountRole}
        showPlayerSessionsTab={showPlayerSessionsTab}
        showCoachAttendanceTab={showCoachAttendanceTab}
        beforeIconActions={
          <ClubTeamSelect
            teams={teams}
            activeTeamId={activeTeamId}
            onChangeTeam={handleSelectTeam}
            selectId="roster-workspace-team"
          />
        }
      >
        <TeamRosterPage team={activeTeam} />
      </ClubWorkspaceLayout>
    );
  }

  if (pathname === "/payments" || pathname === "/payments/") {
    if (!isAuthenticated) {
      return <LoginPage />;
    }
    return (
      <ClubWorkspaceLayout
        activeTab=""
        viewerAccountRole={viewerAccountRole}
        showPlayerSessionsTab={showPlayerSessionsTab}
        showCoachAttendanceTab={showCoachAttendanceTab}
        beforeIconActions={
          <ClubTeamSelect
            teams={teams}
            activeTeamId={activeTeamId}
            onChangeTeam={handleSelectTeam}
            selectId="payments-workspace-team"
          />
        }
      >
        {directorDashboardAllowed ||
        teams.some((t) => t.source === "Coach") ||
        activeTeam?.canManageSchedule ? (
          <CoachPaymentsPage team={activeTeam} />
        ) : (
          <MyFeesPage />
        )}
      </ClubWorkspaceLayout>
    );
  }

  if (pathname === "/my-fees" || pathname === "/my-fees/") {
    if (!isAuthenticated) {
      return <LoginPage />;
    }
    return (
      <ClubWorkspaceLayout
        activeTab=""
        viewerAccountRole={viewerAccountRole}
        showPlayerSessionsTab={showPlayerSessionsTab}
        showCoachAttendanceTab={showCoachAttendanceTab}
        beforeIconActions={
          <ClubTeamSelect
            teams={teams}
            activeTeamId={activeTeamId}
            onChangeTeam={handleSelectTeam}
            selectId="myfees-workspace-team"
          />
        }
      >
        <MyFeesPage />
      </ClubWorkspaceLayout>
    );
  }

  if (pathname === "/schedule") {
    const canManageSchedule = Boolean(activeTeam?.canManageSchedule);
    const scheduleEntries = canManageSchedule ? draftEntries : (schedulePayload?.entries || []);

    return (
      <ClubWorkspaceLayout
        activeTab="schedule"
        viewerAccountRole={viewerAccountRole}
        showPlayerSessionsTab={showPlayerSessionsTab}
        showCoachAttendanceTab={showCoachAttendanceTab}
        beforeIconActions={
          <ClubTeamSelect
            teams={scheduleTeams}
            activeTeamId={activeTeamId}
            onChangeTeam={handleSelectTeam}
            selectId="schedule-workspace-team"
            includeAllTeamsOption={scheduleTeams.length > 1}
          />
        }
      >
        <section className="teams-page-shell">
            <header className="teams-page-header">
              <div className="teams-page-heading">
                <p className="teams-page-kicker">Schedule</p>
                <h1>{activeTeam ? `${activeTeam.name} Schedule` : "Team Schedule"}</h1>
                <p className="teams-page-subtitle">
                  {activeTeam?.id === "__all__"
                    ? "Combined schedule for every team you are allowed to see. Colors match the legend."
                    : activeTeam
                      ? activeTeam.linkedChildren?.length && selectedChildId
                        ? `Schedule of ${
                            activeTeam.linkedChildren.find((child) => child.id === selectedChildId)?.fullName ||
                            activeTeam.name
                          } in ${activeTeam.name}.`
                        : `Schedule of ${activeTeam.name}.`
                      : "Choose a team to view its schedule."}
                </p>
                {activeTeam?.linkedChildren?.length > 1 ? (
                  <div className="child-context-picker">
                    <label htmlFor="schedule-child-select">Child</label>
                    <select
                      id="schedule-child-select"
                      value={selectedChildId || ""}
                      onChange={(event) => handleSelectChildForActiveTeam(event.target.value)}
                    >
                      {activeTeam.linkedChildren.map((child) => (
                        <option key={child.id} value={String(child.id)}>
                          {child.fullName}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : null}
              </div>
            </header>

            {scheduleError ? <p className="schedule-feedback schedule-feedback--error">{scheduleError}</p> : null}

            {scheduleLoading ? (
              <section className="schedule-empty-card">
                <h2>Loading schedule...</h2>
              </section>
            ) : scheduleEntries.length ? (
              <WeeklyScheduleBoard
                weekStart={schedulePayload?.week_start}
                entries={scheduleEntries}
                legendTeams={schedulePayload?.legend}
              />
            ) : (
              <section className="schedule-empty-card">
                <h2>No schedule</h2>
                <p>
                  {!scheduleTeams.length
                    ? "You are not assigned to a team yet, so there is no schedule to show. Ask your club to add you to a roster."
                    : activeTeam?.id === "__all__"
                      ? "No activities on any team schedule for this week yet."
                      : activeTeam
                        ? `There is no schedule for ${activeTeam.name} yet.`
                        : "Select your team above to view its schedule."}
                </p>
              </section>
            )}

            <SchedulePaymentEntries activeTeamId={activeTeamId} teams={scheduleTeams} />

            {canManageSchedule ? (
              <ScheduleEditor
                draftEntries={draftEntries}
                onChangeEntry={updateDraftEntry}
                onAddEntry={addDraftEntry}
                onRemoveEntry={removeDraftEntry}
                onSave={handleSaveSchedule}
                isSaving={isSavingSchedule}
              />
            ) : null}
        </section>
      </ClubWorkspaceLayout>
    );
  }

  const renderHomepageMarketing = ({ withSiteNav }) => (
    <div className={`homepage-shell${withSiteNav ? "" : " homepage-shell--in-workspace"}`}>
      <section id="home" className="hero-section">
        <div
          className="hero-backdrop"
          style={{ "--hero-image": `url(${homepageImages.hero})` }}
        />
        {withSiteNav ? (
          <header className="site-nav">
            <div className="nav-left">
              <span className="brand-mark">NetUp</span>
            </div>
            <div className="nav-right">
              <button
                className="action-button action-button--ghost"
                type="button"
                onClick={() => navigate("/register")}
              >
                Register
              </button>
              <button className="action-button" type="button" onClick={() => navigate("/login")}>
                Login
              </button>
            </div>
          </header>
        ) : null}

        <div className="hero-content">
          <div className="hero-copy reveal-on-scroll" data-reveal="left">
            <p className="eyebrow">Sports Team Management Platform</p>
            <h1>All Your Volleyball Club Operations In One Place</h1>
            <p className="hero-description">
              Bring directors, coaches, players, and parents onto one shared
              platform with role-aware access built for smooth club operations.
            </p>
          </div>

          <div className="hero-pills reveal-on-scroll" data-reveal="right" aria-hidden="true">
            <div className="hero-pill" style={{ "--reveal-delay": "80ms" }}>
              <span>Club creation</span>
              <strong>Faster setup</strong>
            </div>
            <div className="hero-pill" style={{ "--reveal-delay": "160ms" }}>
              <span>Team workflows</span>
              <strong>Cleaner rosters</strong>
            </div>
            <div className="hero-pill" style={{ "--reveal-delay": "240ms" }}>
              <span>Parent controls</span>
              <strong>Safer access</strong>
            </div>
          </div>
        </div>
      </section>

      <section id="about" className="content-section story-section">
        <div className="section-heading reveal-on-scroll" data-reveal="left">
          <h2>WHO WE ARE</h2>
          <div className="heading-line" />
        </div>

        <div className="story-grid">
          <div className="story-copy reveal-on-scroll" data-reveal="left">
            <p className="story-intro">
              NetUp is a volleyball operations platform built to help clubs feel
              more connected, more organized, and easier to run.
            </p>
            <p>
              We focus on the everyday work that keeps a club healthy: creating
              teams, managing roles, supporting families, and giving everyone a
              clearer place inside the same system.
            </p>

            <div className="story-stats">
              {platformStats.map((stat, index) => (
                <div
                  key={stat.label}
                  className="story-stat reveal-on-scroll"
                  data-reveal="up"
                  style={{ "--reveal-delay": `${index * 100}ms` }}
                >
                  <strong>{stat.value}</strong>
                  <span>{stat.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div id="features" className="story-cards">
            {featureFeed.map((item, index) => (
              <article
                key={item.title}
                className="feature-post reveal-on-scroll"
                data-reveal={index % 2 === 0 ? "up" : "right"}
                style={{ "--reveal-delay": `${index * 110}ms` }}
              >
                <div className="feature-post__meta">
                  <span>{item.category}</span>
                  <span>{`0${index + 1}`}</span>
                </div>
                <h3>{item.title}</h3>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="showcase-band">
        {showcaseStrips.map((strip, index) => (
          <figure
            key={strip.src}
            className="showcase-frame reveal-on-scroll"
            data-reveal={index === 1 ? "up" : index % 2 === 0 ? "left" : "right"}
            style={{ "--reveal-delay": `${index * 110}ms` }}
          >
            <img className={strip.className} src={strip.src} alt={strip.alt} />
          </figure>
        ))}
      </section>

      <section className="content-section value-section">
        <div className="section-heading reveal-on-scroll" data-reveal="left">
          <h2>WHY NETUP</h2>
          <div className="heading-line" />
        </div>

        <div className="value-grid">
          {valueHighlights.map((item, index) => (
            <article
              key={item.title}
              className="value-card reveal-on-scroll"
              data-reveal={index % 2 === 0 ? "up" : "right"}
              style={{ "--reveal-delay": `${index * 100}ms` }}
            >
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="content-section trust-section">
        <div className="trust-strip reveal-on-scroll" data-reveal="left">
          <span className="trust-strip__title">Trusted By</span>
          <div className="brand-logos" aria-label="Volleyball brands">
            {trustBrands.map((brand, index) => (
              <span
                key={brand.name}
                className="brand-logo reveal-on-scroll"
                data-reveal="up"
                style={{ "--reveal-delay": `${index * 70}ms` }}
              >
                <img
                  className="brand-logo__img"
                  src={brand.logo}
                  alt={brand.name}
                  loading="lazy"
                  decoding="async"
                />
              </span>
            ))}
          </div>
        </div>
      </section>

      <section id="journey" className="content-section journey-section">
        <div className="section-heading reveal-on-scroll" data-reveal="left">
          <h2>HOW IT WORKS</h2>
          <div className="heading-line" />
        </div>

        <div className="journey-grid">
          {journeySteps.map((step, index) => (
            <article
              key={step.title}
              className="journey-card reveal-on-scroll"
              data-reveal={index % 2 === 0 ? "up" : "right"}
              style={{ "--reveal-delay": `${index * 120}ms` }}
            >
              <span className="journey-card__number">{step.number}</span>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="roles" className="content-section role-section">
        <div className="section-heading reveal-on-scroll" data-reveal="left">
          <h2>FOR EVERY ROLE</h2>
          <div className="heading-line" />
        </div>

        <div className="role-grid">
          {roleSpotlights.map((item, index) => (
            <article
              key={item.role}
              className="role-card reveal-on-scroll"
              data-reveal={index % 2 === 0 ? "left" : "right"}
              style={{ "--reveal-delay": `${index * 90}ms` }}
            >
              <span className="role-card__label">{item.role}</span>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </article>
          ))}
        </div>

        <div
          id="cta"
          className="workspace-closing-banner reveal-on-scroll"
          data-reveal="up"
          style={{ "--closing-banner-image": `url(${homepageImages.hero})` }}
        >
          <p>Built for the full volleyball community</p>
          <h3>One place for clubs, teams, players, and parents to move together.</h3>
          <div className="closing-banner-actions">
            <button
              className="closing-button"
              type="button"
              onClick={() => scrollToSection("faq")}
            >
              Request a demo
            </button>
            <button
              className="closing-button closing-button--ghost"
              type="button"
              onClick={() => scrollToSection("features")}
            >
              Explore features
            </button>
          </div>
        </div>
      </section>

      <section id="faq" className="content-section faq-section">
        <div className="section-heading reveal-on-scroll" data-reveal="left">
          <h2>FAQ</h2>
          <div className="heading-line" />
        </div>

        <div className="faq-grid">
          {faqs.map((item, index) => (
            <article
              key={item.question}
              className="faq-card reveal-on-scroll"
              data-reveal={index % 2 === 0 ? "left" : "right"}
              style={{ "--reveal-delay": `${index * 100}ms` }}
            >
              <h3>{item.question}</h3>
              <p>{item.answer}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="page-footer">
        <div className="page-footer__content">
          <div>
            <span className="page-footer__brand">NetUp</span>
            <p className="page-footer__tagline">
              Club operations, team coordination, and family access in one shared
              platform.
            </p>
          </div>

          <nav className="page-footer__nav" aria-label="Footer">
            {footerLinks.map((item) => (
              <button
                key={item.label}
                type="button"
                className="footer-link"
                onClick={() => scrollToSection(item.sectionId)}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="page-footer__bottom">
          <span>Copyright 2026 NetUp. All rights reserved.</span>
          <span>Built for modern volleyball clubs</span>
        </div>
      </footer>
    </div>
  );

  if (pathname === "/" && isAuthenticated) {
    return (
      <ClubWorkspaceLayout
        activeTab="home"
        viewerAccountRole={viewerAccountRole}
        showPlayerSessionsTab={showPlayerSessionsTab}
        showCoachAttendanceTab={showCoachAttendanceTab}
        beforeIconActions={
          <ClubTeamSelect
            teams={teams}
            activeTeamId={activeTeamId}
            onChangeTeam={handleSelectTeam}
            selectId="home-workspace-team"
          />
        }
      >
        {renderHomepageMarketing({ withSiteNav: false })}
      </ClubWorkspaceLayout>
    );
  }

  return renderHomepageMarketing({ withSiteNav: true });
}

export default App;
