import { useEffect, useState } from "react";
import {
  cancelTrainingSession,
  clearTrainingSession,
  confirmTrainingSession,
  createTeamTrainingSession,
  fetchCurrentUser,
  fetchNotifications,
  fetchTeamSchedule,
  fetchTeamTrainingSessions,
  markNotificationsRead,
  saveTeamSchedule,
  sendTeamNotification,
  updateTrainingSession,
} from "./api";
import ClubWorkspaceLayout, { ClubTeamSelect } from "./components/ClubWorkspaceLayout";
import { navigate } from "./navigation";
import DashboardPage from "./pages/DashboardPage";
import DirectorUserManagementPage from "./pages/DirectorUserManagementPage";
import LoginPage from "./pages/LoginPage";
import { ForgotPasswordPage, ResetPasswordPage } from "./pages/PasswordResetPages";
import RegisterPage from "./pages/RegisterPage";

const AUTH_TOKEN_KEY = "netup.auth.token";
const ACTIVE_TEAM_KEY = "netup.active.team";

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
  { name: "Mikasa", mark: "M" },
  { name: "Molten", mark: "MO" },
  { name: "Wilson", mark: "W" },
  { name: "Mizuno", mark: "MI" },
  { name: "ASICS", mark: "A" },
  { name: "adidas", mark: "ad" },
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

function formatCoachName(team) {
  if (team.coachNames?.length) {
    return team.coachNames.join(", ");
  }

  return "No coach assigned";
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

function buildChildTeamLabel(linkedChildren) {
  if (!linkedChildren?.length) {
    return "";
  }

  if (linkedChildren.length === 1) {
    return `${linkedChildren[0].firstName}'s team`;
  }

  return linkedChildren.map((child) => child.firstName).join(", ");
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

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function emptyTrainingDraft() {
  return {
    title: "",
    session_type: "training",
    scheduled_date: todayIsoDate(),
    start_time: "18:00",
    end_time: "19:30",
    location: "",
    opponent: "",
    match_type: "friendly",
    notes: "",
  };
}

function emptyManualNotificationDraft() {
  return {
    audience: "all",
    title: "",
    message: "",
  };
}

function formatTrainingDateLabel(dateValue) {
  if (!dateValue) {
    return "";
  }

  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(new Date(`${dateValue}T00:00:00`));
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
    }));
}

function mapTrainingSessionsToScheduleEntries(weekStartIso, sessions) {
  if (!weekStartIso) {
    return [];
  }

  const weekStartDate = new Date(`${weekStartIso}T00:00:00`);
  const weekEndDate = new Date(weekStartDate);
  weekEndDate.setDate(weekStartDate.getDate() + 6);

  return (sessions || [])
    .filter((session) => session.status !== "cancelled")
    .filter((session) => {
      const sessionDate = new Date(`${session.scheduled_date}T00:00:00`);
      return sessionDate >= weekStartDate && sessionDate <= weekEndDate;
    })
    .map((session) => {
      const sessionDate = new Date(`${session.scheduled_date}T00:00:00`);
      return {
        id: `training-${session.id}`,
        trainingSessionId: session.id,
        isTrainingSession: true,
        weekday: (sessionDate.getDay() + 6) % 7,
        activity_name: session.title,
        start_time: session.start_time,
        end_time: session.end_time,
        location: session.location || "",
      };
    });
}

function ScheduleEditor({ draftEntries, onChangeEntry, onAddEntry, onRemoveEntry, onSave, isSaving }) {
  return (
    <section className="schedule-editor-card">
      <div className="schedule-editor-card__top">
        <div>
          <p className="teams-page-kicker">Coach Controls</p>
          <h2>Edit Team Schedule</h2>
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

function WeeklyScheduleBoard({ weekStart, entries, onSelectEntry }) {
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

  return (
    <section className="weekly-schedule-card">
      <div className="weekly-schedule-card__header">
        <h2>Week of {getWeekLabel(weekStart)}</h2>
      </div>

      <div className="weekly-schedule-layout">
        <div className="weekly-schedule-times">
          {scheduleHours.map((hour) => (
            <div key={hour} className="weekly-schedule-times__slot">
              {formatHourLabel(hour)}
            </div>
          ))}
        </div>

        <div className="weekly-schedule-grid">
          {weekDays.map((day) => (
            <div key={day.iso} className="weekly-schedule-day">
              <header className="weekly-schedule-day__header">
                <span>{day.label}</span>
                <strong>{day.dayNumber}</strong>
              </header>

              <div className="weekly-schedule-day__track">
                {scheduleRows.map((hour) => (
                  <div key={`${day.iso}-${hour}`} className="weekly-schedule-day__hour-line" />
                ))}

                {entriesByWeekday[day.weekday]?.map((entry) => {
                  const startMinutes = parseTimeToMinutes(entry.start_time);
                  const endMinutes = parseTimeToMinutes(entry.end_time);
                  const clippedStartMinutes = Math.max(startMinutes, SCHEDULE_START_HOUR * 60);
                  const clippedEndMinutes = Math.min(endMinutes, SCHEDULE_END_HOUR * 60);
                  const minutesFromTop = clippedStartMinutes - SCHEDULE_START_HOUR * 60;
                  const durationMinutes = Math.max(clippedEndMinutes - clippedStartMinutes, 30);

                  return (
                    <article
                      key={entry.id}
                      className={`schedule-event${entry.isTrainingSession ? " schedule-event--interactive" : ""}`}
                      style={{
                        top: `${(minutesFromTop / 60) * SCHEDULE_HOUR_HEIGHT}px`,
                        height: `${(durationMinutes / 60) * SCHEDULE_HOUR_HEIGHT}px`,
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
                      {entry.location ? <em>{entry.location}</em> : null}
                    </article>
                  );
                })}

                {entriesByWeekday[day.weekday]?.length ? null : (
                  <p className="weekly-schedule-day__empty">No activity</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function TrainingManagerForm({
  draft,
  onChange,
  onSave,
  onReset,
  onCancelEdit,
  isSaving,
  editingSessionId,
}) {
  const isMatch = draft.session_type === "match";

  return (
    <section className="training-form-card">
      <div className="training-form-card__top">
        <div>
          <p className="teams-page-kicker">Session</p>
          <h3>{editingSessionId ? "Edit Session" : "Create Session"}</h3>
        </div>
        <div className="training-form-card__top-actions">
          {editingSessionId ? (
            <button
              type="button"
              className="team-card__button team-card__button--ghost"
              onClick={onCancelEdit}
            >
              Cancel
            </button>
          ) : null}
          <button
            type="button"
            className="team-card__button team-card__button--ghost"
            onClick={onReset}
          >
            New Session
          </button>
        </div>
      </div>

      <div className="session-type-switch" role="tablist" aria-label="Session type">
        <button
          type="button"
          className={`session-type-switch__button${!isMatch ? " is-active" : ""}`}
          onClick={() => {
            onChange("session_type", "training");
            onChange("opponent", "");
            onChange("match_type", "friendly");
          }}
        >
          Practice
        </button>
        <button
          type="button"
          className={`session-type-switch__button${isMatch ? " is-active" : ""}`}
          onClick={() => {
            onChange("session_type", "match");
            onChange("match_type", draft.match_type || "friendly");
          }}
        >
          Match
        </button>
      </div>

      <div className="training-form-grid">
        <input
          type="text"
          placeholder={isMatch ? "Match title" : "Practice title"}
          value={draft.title}
          onChange={(event) => onChange("title", event.target.value)}
        />
        <input
          type="date"
          value={draft.scheduled_date}
          onChange={(event) => onChange("scheduled_date", event.target.value)}
        />
        <input
          type="time"
          value={draft.start_time}
          onChange={(event) => onChange("start_time", event.target.value)}
        />
        <input
          type="time"
          value={draft.end_time}
          onChange={(event) => onChange("end_time", event.target.value)}
        />
        <input
          type="text"
          placeholder="Location"
          value={draft.location}
          onChange={(event) => onChange("location", event.target.value)}
        />
        {isMatch ? (
          <>
            <input
              type="text"
              placeholder="Opponent"
              value={draft.opponent}
              onChange={(event) => onChange("opponent", event.target.value)}
            />
            <select
              value={draft.match_type}
              onChange={(event) => onChange("match_type", event.target.value)}
            >
              <option value="friendly">Friendly</option>
              <option value="league">League</option>
              <option value="tournament">Tournament</option>
              <option value="scrimmage">Scrimmage</option>
            </select>
          </>
        ) : null}
        <textarea
          placeholder="Notes for the team"
          value={draft.notes}
          onChange={(event) => onChange("notes", event.target.value)}
        />
      </div>

      <div className="training-form-card__actions">
        <button type="button" className="team-card__button" onClick={onSave} disabled={isSaving}>
          {isSaving ? "Saving..." : editingSessionId ? "Save Changes" : "Create Session"}
        </button>
      </div>
    </section>
  );
}

function TrainingSessionList({
  sessions,
  canManageTraining,
  onEdit,
  onCancel,
  onClear,
  onConfirm,
  confirmingKey,
  hideCancelled,
  selectedChildId,
}) {
  const [expandedSessionIds, setExpandedSessionIds] = useState({});
  const visibleSessions = hideCancelled
    ? sessions.filter((session) => session.status !== "cancelled")
    : sessions;

  const toggleConfirmationDetails = (sessionId) => {
    setExpandedSessionIds((currentState) => ({
      ...currentState,
      [sessionId]: !currentState[sessionId],
    }));
  };

  if (!visibleSessions.length) {
    return (
      <section className="training-empty-state">
        <h3>No scheduled training</h3>
        <p>There are no scheduled training sessions for this team right now.</p>
      </section>
    );
  }

  return (
    <div className="training-session-list">
      {visibleSessions.map((session) => (
        <article key={session.id} className="training-session-card">
          <div className="training-session-card__top">
            <div>
              <div className="training-session-card__meta">
                <span>{session.session_type_label}</span>
                <span>{formatTrainingDateLabel(session.scheduled_date)}</span>
                <span>{session.start_time} - {session.end_time}</span>
              </div>
              <h3>{session.title}</h3>
              <p className="training-session-card__location">
                {session.location || "Location to be confirmed"}
              </p>
              {session.session_type === "match" && session.opponent ? (
                <p className="training-session-card__match-meta">
                  Opponent: {session.opponent}
                  {session.match_type_label ? ` | ${session.match_type_label}` : ""}
                </p>
              ) : null}
              {session.notes ? (
                <p className="training-session-card__notes">{session.notes}</p>
              ) : null}
            </div>

            <div className="training-session-card__status">
              <span
                className={`training-status-badge${
                  session.status === "cancelled" ? " training-status-badge--cancelled" : ""
                }`}
              >
                {session.status_label}
              </span>
            </div>
          </div>

          {canManageTraining ? (
            <div className="training-confirmation-summary">
              <span>Confirmed: {session.confirmed_count ?? 0}</span>
              <span>Not confirmed: {session.pending_count ?? 0}</span>
              <button
                type="button"
                className="training-summary-toggle"
                onClick={() => toggleConfirmationDetails(session.id)}
              >
                {expandedSessionIds[session.id] ? "Hide Confirmation" : "Show Confirmation"}
              </button>
            </div>
          ) : null}

          {canManageTraining ? (
            <div className="training-session-card__manager-actions">
              <button
                type="button"
                className="team-card__button team-card__button--ghost"
                onClick={() => onEdit(session)}
              >
                Edit
              </button>
              {session.can_cancel ? (
                <button
                  type="button"
                  className="training-cancel-button"
                  onClick={() => onCancel(session.id)}
                >
                  Cancel Session
                </button>
              ) : null}
              {session.status === "cancelled" ? (
                <button
                  type="button"
                  className="training-clear-button"
                  onClick={() => onClear(session.id)}
                >
                  Clear
                </button>
              ) : null}
            </div>
          ) : null}

          {!canManageTraining ? (
            <div className="training-confirmation-summary">
              <span>Confirmed: {session.confirmed_count ?? 0}</span>
              <span>Not confirmed: {session.pending_count ?? 0}</span>
              <button
                type="button"
                className="training-summary-toggle"
                onClick={() => toggleConfirmationDetails(session.id)}
              >
                {expandedSessionIds[session.id] ? "Hide Confirmation" : "Show Confirmation"}
              </button>
            </div>
          ) : null}

          {canManageTraining && expandedSessionIds[session.id] ? (
            <div className="training-attendance-table">
              <div className="training-attendance-table__header">
                <span>Player</span>
                <span>Status</span>
              </div>
              {session.player_confirmations.map((confirmation) => (
                <div key={`${session.id}-${confirmation.player_id}`} className="training-attendance-table__row">
                  <span>{confirmation.player_name}</span>
                  <strong>
                    {confirmation.is_confirmed
                      ? `Confirmed${confirmation.confirmed_by_name ? ` by ${confirmation.confirmed_by_name}` : ""}`
                      : "Not confirmed"}
                  </strong>
                </div>
              ))}
            </div>
          ) : null}

          {!canManageTraining && expandedSessionIds[session.id] ? (
            <div className="training-confirm-list">
              {session.player_confirmations
                .filter((confirmation) => {
                  if (selectedChildId && confirmation.player_id !== selectedChildId) {
                    return false;
                  }

                  return confirmation.can_confirm || confirmation.is_confirmed;
                })
                .map((confirmation) => {
                  const confirmKey = `${session.id}-${confirmation.player_id}`;
                  return (
                    <div key={confirmKey} className="training-confirm-list__item">
                      <div>
                        <strong>{confirmation.player_name}</strong>
                        <p>
                          {confirmation.is_confirmed
                            ? "Attendance confirmed"
                            : "Attendance not confirmed yet"}
                        </p>
                      </div>
                      {confirmation.can_confirm && !confirmation.is_confirmed ? (
                        <button
                          type="button"
                          className="team-card__button"
                          onClick={() => onConfirm(session.id, confirmation.player_id)}
                          disabled={confirmingKey === confirmKey}
                        >
                          {confirmingKey === confirmKey ? "Confirming..." : "Confirm"}
                        </button>
                      ) : null}
                    </div>
                  );
                })}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function TrainingPage({
  team,
  trainingState,
  onLoad,
  onDraftChange,
  onCreateOrUpdate,
  onEditSession,
  onResetDraft,
  onCancelEdit,
  onCancelSession,
  onClearSession,
  onConfirmSession,
  selectedChildId,
  onSelectChild,
}) {
  const state = trainingState || {};
  const sessions = state.sessions || [];
  const draft = state.draft || emptyTrainingDraft();

  return (
    <section className="teams-page-shell">
      <header className="teams-page-header">
        <div className="teams-page-heading">
          <p className="teams-page-kicker">Training</p>
          <h1>{team ? `${team.name} Sessions` : "Team Sessions"}</h1>
          <p className="teams-page-subtitle">
            {team?.canManageTraining
              ? "Create practice or match sessions, update details, and track confirmations for this team."
              : team
                ? `See the scheduled sessions for ${team.name}.`
                : "Choose a team to view its sessions."}
          </p>
          {team?.linkedChildren?.length > 1 ? (
            <div className="child-context-picker">
              <label htmlFor="training-child-select">Child</label>
              <select
                id="training-child-select"
                value={selectedChildId || ""}
                onChange={(event) => onSelectChild(event.target.value)}
              >
                {team.linkedChildren.map((child) => (
                  <option key={child.id} value={String(child.id)}>
                    {child.fullName}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
        </div>
      </header>

      <section className="team-training-panel">
      <div className="team-training-panel__header">
        <button
          type="button"
          className="team-card__button team-card__button--ghost"
          onClick={onLoad}
          disabled={Boolean(state.loading)}
        >
          {state.loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {state.error ? <p className="schedule-feedback schedule-feedback--error">{state.error}</p> : null}

      {team.canManageTraining ? (
        <TrainingManagerForm
          draft={draft}
          onChange={onDraftChange}
          onSave={onCreateOrUpdate}
          onReset={onResetDraft}
          onCancelEdit={onCancelEdit}
          isSaving={Boolean(state.saving)}
          editingSessionId={state.editingSessionId}
        />
      ) : null}

      <TrainingSessionList
        sessions={sessions}
        canManageTraining={Boolean(team?.canManageTraining)}
        onEdit={onEditSession}
        onCancel={onCancelSession}
        onClear={onClearSession}
        onConfirm={onConfirmSession}
        confirmingKey={state.confirmingKey}
        hideCancelled={!team?.canManageTraining}
        selectedChildId={selectedChildId}
      />
      </section>
    </section>
  );
}

function ScheduleTrainingSessions({ sessions, onEditSession }) {
  const visibleSessions = (sessions || []).filter((session) => session.status !== "cancelled");

  if (!visibleSessions.length) {
    return null;
  }

  return (
    <section className="schedule-training-card">
      <div className="schedule-training-card__top">
        <div>
          <p className="teams-page-kicker">Sessions</p>
          <h2>Edit Sessions</h2>
        </div>
      </div>

      <div className="schedule-training-list">
        {visibleSessions.map((session) => (
          <article key={session.id} className="schedule-training-item">
            <div>
              <strong>{session.title}</strong>
              <p>
                {formatTrainingDateLabel(session.scheduled_date)} · {session.start_time} - {session.end_time}
                {session.location ? ` · ${session.location}` : ""}
              </p>
            </div>

            <button
              type="button"
              className="team-card__button team-card__button--ghost"
              onClick={() => onEditSession(session)}
            >
              Edit In Training
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}

function NotificationBell({
  unreadCount,
  isOpen,
  onToggle,
  isLight,
  className = "",
}) {
  return (
    <button
      type="button"
      className={`notification-bell${isLight ? " notification-bell--light" : ""}${
        isOpen ? " is-open" : ""
      }${className ? ` ${className}` : ""}`}
      onClick={onToggle}
      aria-label="Notifications"
    >
      <span className="notification-bell__icon" aria-hidden="true">
        {"\u{1F514}"}
      </span>
      {unreadCount ? <span className="notification-bell__badge">{unreadCount}</span> : null}
    </button>
  );
}

function NotificationPanel({
  isOpen,
  notifications,
  sentNotifications,
  loading,
  error,
  canSend,
  manualDraft,
  onManualChange,
  onManualSend,
  isSendingManual,
}) {
  if (!isOpen) {
    return null;
  }

  const unreadNotifications = (notifications || []).filter((item) => !item.is_read);
  const readNotifications = (notifications || []).filter((item) => item.is_read);
  const sentItems = sentNotifications || [];
  const hasAnyNotifications =
    unreadNotifications.length || readNotifications.length || sentItems.length;

  return (
    <section className="notification-panel">
      <div className="notification-panel__header">
        <div>
          <p className="teams-page-kicker">Notifications</p>
          <h2>Inbox</h2>
        </div>
      </div>

      {canSend ? (
        <div className="notification-compose-card">
          <h3>Send Notification</h3>
          <div className="notification-compose-grid">
            <select
              value={manualDraft.audience}
              onChange={(event) => onManualChange("audience", event.target.value)}
            >
              <option value="all">Players and parents</option>
              <option value="players">Players only</option>
              <option value="parents">Parents only</option>
            </select>
            <input
              type="text"
              placeholder="Notification title"
              value={manualDraft.title}
              onChange={(event) => onManualChange("title", event.target.value)}
            />
            <textarea
              placeholder="Write your message"
              value={manualDraft.message}
              onChange={(event) => onManualChange("message", event.target.value)}
            />
          </div>
          <div className="notification-compose-card__actions">
            <button
              type="button"
              className="team-card__button"
              onClick={onManualSend}
              disabled={isSendingManual}
            >
              {isSendingManual ? "Sending..." : "Send Notification"}
            </button>
          </div>
        </div>
      ) : null}

      {loading ? <p className="notification-empty-state">Loading notifications...</p> : null}
      {error ? <p className="schedule-feedback schedule-feedback--error">{error}</p> : null}
      {!loading && !hasAnyNotifications ? (
        <p className="notification-empty-state">No notifications.</p>
      ) : null}

      {!loading && hasAnyNotifications ? (
        <div className="notification-list">
          {unreadNotifications.length ? (
            <>
              <div className="notification-divider">
                <span>New Messages</span>
              </div>
              {unreadNotifications.map((item) => (
                <article key={item.id} className="notification-item notification-item--new">
                  <strong>{item.title}</strong>
                  <p>{item.message}</p>
                  {item.team_name ? (
                    <span className="notification-item__meta">{item.team_name}</span>
                  ) : null}
                </article>
              ))}
            </>
          ) : null}

          {readNotifications.length ? (
            <>
              <div className="notification-divider">
                <span>Earlier</span>
              </div>
              {readNotifications.map((item) => (
                <article key={item.id} className="notification-item">
                  <strong>{item.title}</strong>
                  <p>{item.message}</p>
                  {item.team_name ? (
                    <span className="notification-item__meta">{item.team_name}</span>
                  ) : null}
                </article>
              ))}
            </>
          ) : null}

          {canSend && sentItems.length ? (
            <>
              <div className="notification-divider">
                <span>Sent Messages</span>
              </div>
              {sentItems.map((item) => (
                <article key={item.id} className="notification-item notification-item--sent">
                  <strong>{item.title}</strong>
                  <p>{item.message}</p>
                  <span className="notification-item__meta">
                    {item.team_name ? `${item.team_name} · ` : ""}
                    Sent to {item.recipient_count} recipient{item.recipient_count === 1 ? "" : "s"}
                  </span>
                </article>
              ))}
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function TeamsPage({ teams, activeTeamId, onSelectTeam, onOpenSchedule }) {
  return (
    <section className="teams-page-shell">
      <header className="teams-page-header">
        <div className="teams-page-heading">
          <p className="teams-page-kicker">Team Setup</p>
          <h1>Choose Your Team Space</h1>
          <p className="teams-page-subtitle">
            Pick the team you want to work in right now. We&apos;ll use that as the
            active team for upcoming team-specific features.
          </p>
        </div>
      </header>

      <section className="teams-grid">
        {teams.length ? (
          teams.map((team) => {
            const isActive = String(team.id) === String(activeTeamId);

            return (
              <article key={team.id} className={`team-card${isActive ? " team-card--active" : ""}`}>
                <div className="team-card__top">
                  <div>
                    <span className="team-card__label">{team.source}</span>
                    <h2>{team.name}</h2>
                    <p className="team-card__coach">Coach: {formatCoachName(team)}</p>
                    {team.linkedChildren?.length ? (
                      <p className="team-card__children">
                        Child{team.linkedChildren.length > 1 ? "ren" : ""}: {buildChildTeamLabel(team.linkedChildren)}
                      </p>
                    ) : null}
                  </div>
                  <div className="team-card__top-right">
                    {isActive ? <span className="team-card__badge">Active</span> : null}
                    <details className="team-card__details">
                      <summary>Details</summary>
                      <div className="team-card__details-panel">
                        <div className="team-card__detail-row">
                          <span>Players</span>
                          <strong>{team.playerCount ?? 0}</strong>
                        </div>
                        <div className="team-card__detail-row">
                          <span>Coaches</span>
                          <strong>{team.coachCount ?? 0}</strong>
                        </div>
                        <div className="team-card__detail-row">
                          <span>Captains</span>
                          <strong>
                            {team.captainNames?.length
                              ? team.captainNames.join(", ")
                              : "None assigned"}
                          </strong>
                        </div>
                      </div>
                    </details>
                  </div>
                </div>

                <div className="team-card__actions">
                  <button type="button" className="team-card__button" onClick={() => onSelectTeam(team)}>
                    {isActive ? "Selected Team" : "Select Team"}
                  </button>
                  <button
                    type="button"
                    className="team-card__button team-card__button--ghost"
                    onClick={() => onOpenSchedule(team)}
                  >
                    {team.canManageSchedule ? "Manage Schedule" : "View Schedule"}
                  </button>
                </div>
              </article>
            );
          })
        ) : (
          <article className="teams-empty-state">
            <h2>No teams linked yet</h2>
            <p>This account does not have any team memberships available right now.</p>
          </article>
        )}
      </section>
    </section>
  );
}

function App() {
  const pathname = usePathname();
  const [isAuthenticated, setIsAuthenticated] = useState(
    Boolean(localStorage.getItem(AUTH_TOKEN_KEY)),
  );
  const [teams, setTeams] = useState([]);
  const [activeTeamId, setActiveTeamId] = useState(() => localStorage.getItem(ACTIVE_TEAM_KEY) || "");
  const [schedulePayload, setSchedulePayload] = useState(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [scheduleError, setScheduleError] = useState("");
  const [draftEntries, setDraftEntries] = useState([]);
  const [isSavingSchedule, setIsSavingSchedule] = useState(false);
  const [trainingStateByTeam, setTrainingStateByTeam] = useState({});
  const [pendingTrainingEditId, setPendingTrainingEditId] = useState(null);
  const [selectedChildIdByTeam, setSelectedChildIdByTeam] = useState({});
  const [notifications, setNotifications] = useState([]);
  const [sentNotifications, setSentNotifications] = useState([]);
  const [notificationUnreadCount, setNotificationUnreadCount] = useState(0);
  const [isNotificationPanelOpen, setIsNotificationPanelOpen] = useState(false);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [notificationsError, setNotificationsError] = useState("");
  const [manualNotificationDraft, setManualNotificationDraft] = useState(emptyManualNotificationDraft());
  const [isSendingManualNotification, setIsSendingManualNotification] = useState(false);
  const [directorDashboardAllowed, setDirectorDashboardAllowed] = useState(null);
  const activeTeam = teams.find((team) => String(team.id) === String(activeTeamId)) || null;

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
        setTeams([]);
        setActiveTeamId("");
        setTrainingStateByTeam({});
        localStorage.removeItem(ACTIVE_TEAM_KEY);
        return;
      }

      try {
        const payload = await fetchCurrentUser();
        if (!isMounted) {
          return;
        }

        const allowed =
          typeof payload.is_director_or_staff === "boolean"
            ? payload.is_director_or_staff
            : (payload.owned_clubs || []).length > 0;
        setDirectorDashboardAllowed(Boolean(allowed));

        const relatedTeams = buildRelatedTeams(payload);
        setTeams(relatedTeams);
      } catch {
        if (!isMounted) {
          return;
        }
        setDirectorDashboardAllowed(false);
        setTeams([]);
        setActiveTeamId("");
        setTrainingStateByTeam({});
      }
    }

    loadTeams();

    return () => {
      isMounted = false;
    };
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) {
      setNotifications([]);
      setSentNotifications([]);
      setNotificationUnreadCount(0);
      setIsNotificationPanelOpen(false);
      setManualNotificationDraft(emptyManualNotificationDraft());
      return;
    }

    let isMounted = true;

    async function loadNotificationsSilently() {
      try {
        const payload = await fetchNotifications(activeTeamId);
        if (!isMounted) {
          return;
        }

        setNotifications(payload.items || []);
        setSentNotifications(payload.sent_items || []);
        setNotificationUnreadCount(payload.unread_count || 0);
      } catch {
        if (!isMounted) {
          return;
        }
        setNotifications([]);
        setSentNotifications([]);
        setNotificationUnreadCount(0);
      }
    }

    loadNotificationsSilently();

    return () => {
      isMounted = false;
    };
  }, [activeTeamId, isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    if (!teams.length) {
      setActiveTeamId("");
      localStorage.removeItem(ACTIVE_TEAM_KEY);
      return;
    }

    const hasValidSelectedTeam = teams.some((team) => String(team.id) === String(activeTeamId));

    if (!hasValidSelectedTeam) {
      const firstTeamId = String(teams[0].id);
      setActiveTeamId(firstTeamId);
      localStorage.setItem(ACTIVE_TEAM_KEY, firstTeamId);
    }
  }, [activeTeamId, isAuthenticated, teams]);

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
    if (pathname !== "/schedule" || !activeTeamId) {
      return;
    }

    let isMounted = true;

    async function loadSchedule() {
      setScheduleLoading(true);
      setScheduleError("");

      try {
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

    loadSchedule();

    return () => {
      isMounted = false;
    };
  }, [activeTeamId, pathname]);

  useEffect(() => {
    if (pathname !== "/training" || !activeTeamId) {
      return;
    }

    const existingState = trainingStateByTeam[String(activeTeamId)];
    if (existingState?.sessions || existingState?.loading) {
      return;
    }

    loadTrainingSessions(activeTeamId);
  }, [activeTeamId, pathname, trainingStateByTeam]);

  useEffect(() => {
    if (pathname !== "/training" || !activeTeamId || !pendingTrainingEditId) {
      return;
    }

    const activeTrainingState = trainingStateByTeam[String(activeTeamId)];
    if (!activeTrainingState || activeTrainingState.loading) {
      return;
    }

    const matchingSession = (activeTrainingState.sessions || []).find(
      (session) => session.id === pendingTrainingEditId,
    );

    if (matchingSession) {
      editTrainingSessionDraft(activeTeamId, matchingSession);
    }

    setPendingTrainingEditId(null);
  }, [activeTeamId, pathname, pendingTrainingEditId, trainingStateByTeam]);

  useEffect(() => {
    if (pathname !== "/schedule" || !activeTeamId) {
      return;
    }

    const existingState = trainingStateByTeam[String(activeTeamId)];
    if (existingState?.sessions || existingState?.loading) {
      return;
    }

    loadTrainingSessions(activeTeamId);
  }, [activeTeamId, pathname, trainingStateByTeam]);

  const setTeamTrainingState = (teamId, updater) => {
    const teamKey = String(teamId);
    setTrainingStateByTeam((currentState) => {
      const previousState = currentState[teamKey] || {
        sessions: [],
        draft: emptyTrainingDraft(),
        editingSessionId: null,
        loading: false,
        saving: false,
        error: "",
        confirmingKey: "",
      };
      const nextPartialState =
        typeof updater === "function" ? updater(previousState) : updater;

      return {
        ...currentState,
        [teamKey]: {
          ...previousState,
          ...nextPartialState,
        },
      };
    });
  };

  const selectedChildId = activeTeam?.linkedChildren?.length
    ? Number(selectedChildIdByTeam[String(activeTeamId)] || activeTeam.linkedChildren[0].id)
    : null;

  const loadNotifications = async ({ markRead = false } = {}) => {
    setNotificationsLoading(true);
    setNotificationsError("");

    try {
      const payload = await fetchNotifications(activeTeamId);
      setNotifications(payload.items || []);
      setSentNotifications(payload.sent_items || []);
      setNotificationUnreadCount(payload.unread_count || 0);

      if (markRead && (payload.unread_count || 0) > 0) {
        await markNotificationsRead();
        setNotifications((currentNotifications) =>
          currentNotifications.map((item) => ({ ...item, is_read: true })),
        );
        setNotificationUnreadCount(0);
      }
    } catch (error) {
      setNotificationsError(error.message || "Failed to load notifications.");
    } finally {
      setNotificationsLoading(false);
    }
  };

  const loadTrainingSessions = async (teamId) => {
    setTeamTrainingState(teamId, { loading: true, error: "" });

    try {
      const payload = await fetchTeamTrainingSessions(teamId);
      setTeamTrainingState(teamId, (previousState) => ({
        loading: false,
        error: "",
        sessions: payload.sessions || [],
        draft: previousState.draft || emptyTrainingDraft(),
      }));
    } catch (error) {
      setTeamTrainingState(teamId, {
        loading: false,
        error: error.message || "Failed to load training sessions.",
      });
    }
  };

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

  const toggleNotificationPanel = async () => {
    const nextIsOpen = !isNotificationPanelOpen;
    setIsNotificationPanelOpen(nextIsOpen);

    if (nextIsOpen) {
      await loadNotifications({ markRead: true });
    }
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
    if (!activeTeamId) {
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
      await loadNotifications();
    } catch (error) {
      setScheduleError(error.message || "Failed to save schedule.");
    } finally {
      setIsSavingSchedule(false);
    }
  };

  const updateTrainingDraft = (teamId, field, value) => {
    setTeamTrainingState(teamId, (previousState) => ({
      draft: {
        ...(previousState.draft || emptyTrainingDraft()),
        [field]:
          field === "session_type" && value === "match"
            ? value
            : field === "match_type" && !value
              ? "friendly"
              : value,
        ...(field === "session_type" && value === "match"
          ? {
              match_type: previousState.draft?.match_type || "friendly",
            }
          : {}),
      },
      error: "",
    }));
  };

  const resetTrainingDraft = (teamId) => {
    setTeamTrainingState(teamId, {
      draft: emptyTrainingDraft(),
      editingSessionId: null,
      error: "",
    });
  };

  const editTrainingSessionDraft = (teamId, session) => {
    setTeamTrainingState(teamId, {
      draft: {
        title: session.title,
        session_type: session.session_type,
        scheduled_date: session.scheduled_date,
        start_time: session.start_time,
        end_time: session.end_time,
        location: session.location || "",
        opponent: session.opponent || "",
        match_type: session.match_type || "friendly",
        notes: session.notes || "",
        notify_players: Boolean(session.notify_players),
        notify_parents: Boolean(session.notify_parents),
      },
      editingSessionId: session.id,
      error: "",
    });
  };

  const saveTrainingSession = async (teamId) => {
    const teamKey = String(teamId);
    const teamState = trainingStateByTeam[teamKey] || {};
    const draft = teamState.draft || emptyTrainingDraft();

    setTeamTrainingState(teamId, { saving: true, error: "" });

    try {
      const response = teamState.editingSessionId
        ? await updateTrainingSession(teamState.editingSessionId, draft)
        : await createTeamTrainingSession(teamId, draft);
      const savedSession = response.session;

      setTeamTrainingState(teamId, (previousState) => {
        const nextSessions = previousState.editingSessionId
          ? (previousState.sessions || []).map((session) =>
              session.id === savedSession.id ? savedSession : session,
            )
          : [...(previousState.sessions || []), savedSession].sort((left, right) => {
              const leftKey = `${left.scheduled_date} ${left.start_time}`;
              const rightKey = `${right.scheduled_date} ${right.start_time}`;
              return leftKey.localeCompare(rightKey);
            });

        return {
          saving: false,
          error: "",
          sessions: nextSessions,
          draft: emptyTrainingDraft(),
          editingSessionId: null,
        };
      });
    } catch (error) {
      setTeamTrainingState(teamId, {
        saving: false,
        error: error.message || "Failed to save training session.",
      });
    }
  };

  const handleCancelTrainingSession = async (teamId, sessionId) => {
    setTeamTrainingState(teamId, { error: "" });

    try {
      const response = await cancelTrainingSession(sessionId);
      const cancelledSession = response.session;

      setTeamTrainingState(teamId, (previousState) => ({
        sessions: (previousState.sessions || []).map((session) =>
          session.id === cancelledSession.id ? cancelledSession : session,
        ),
      }));
    } catch (error) {
      setTeamTrainingState(teamId, {
        error: error.message || "Failed to cancel training session.",
      });
    }
  };

  const handleClearTrainingSession = async (teamId, sessionId) => {
    setTeamTrainingState(teamId, { error: "" });

    try {
      await clearTrainingSession(sessionId);
      setTeamTrainingState(teamId, (previousState) => ({
        sessions: (previousState.sessions || []).filter((session) => session.id !== sessionId),
      }));
    } catch (error) {
      setTeamTrainingState(teamId, {
        error: error.message || "Failed to clear session.",
      });
    }
  };

  const updateManualNotificationDraft = (field, value) => {
    setManualNotificationDraft((currentDraft) => ({
      ...currentDraft,
      [field]: value,
    }));
  };

  const handleSendManualNotification = async () => {
    if (!activeTeamId) {
      return;
    }

    setIsSendingManualNotification(true);
    setNotificationsError("");

    try {
      await sendTeamNotification({
        team_id: Number(activeTeamId),
        audience: manualNotificationDraft.audience,
        title: manualNotificationDraft.title.trim(),
        message: manualNotificationDraft.message.trim(),
      });
      setManualNotificationDraft(emptyManualNotificationDraft());
      await loadNotifications();
    } catch (error) {
      setNotificationsError(error.message || "Failed to send notification.");
    } finally {
      setIsSendingManualNotification(false);
    }
  };

  const handleConfirmTrainingSession = async (teamId, sessionId, playerId) => {
    const confirmingKey = `${sessionId}-${playerId}`;
    setTeamTrainingState(teamId, { confirmingKey, error: "" });

    try {
      const response = await confirmTrainingSession(sessionId, playerId);
      const confirmedSession = response.session;

      setTeamTrainingState(teamId, (previousState) => ({
        confirmingKey: "",
        sessions: (previousState.sessions || []).map((session) =>
          session.id === confirmedSession.id ? confirmedSession : session,
        ),
      }));
    } catch (error) {
      setTeamTrainingState(teamId, {
        confirmingKey: "",
        error: error.message || "Failed to confirm training attendance.",
      });
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

  const handleScheduleEntrySelect = (entry) => {
    if (!entry?.isTrainingSession || !activeTeam?.canManageTraining) {
      return;
    }

    setPendingTrainingEditId(entry.trainingSessionId);
    navigate("/training");
  };

  const handleEditTrainingFromSchedule = (session) => {
    if (!session || !activeTeam?.canManageTraining) {
      return;
    }

    setPendingTrainingEditId(session.id);
    navigate("/training");
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

  if (pathname === "/dashboard") {
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
          <h1 style={{ fontSize: "1.25rem", marginBottom: "0.75rem" }}>Club director dashboard</h1>
          <p style={{ color: "#5c6570", lineHeight: 1.55 }}>
            The operations dashboard (registration overview, revenue summaries, and director tools) is only
            available to club directors and platform staff.
          </p>
          <button
            type="button"
            className="vc-action-btn"
            style={{ marginTop: "1.25rem" }}
            onClick={() => navigate("/teams")}
          >
            <span>Go to your teams</span>
            <span aria-hidden="true">›</span>
          </button>
        </div>
      );
    }
    return <DashboardPage />;
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
            onClick={() => navigate("/teams")}
          >
            <span>Go to your teams</span>
            <span aria-hidden="true">›</span>
          </button>
        </div>
      );
    }
    return <DirectorUserManagementPage />;
  }

  if (pathname === "/teams") {
    return (
      <ClubWorkspaceLayout
        activeTab="statistics"
        trainingEnabled={Boolean(activeTeam)}
        beforeIconActions={
          <ClubTeamSelect
            teams={teams}
            activeTeamId={activeTeamId}
            onChangeTeam={handleSelectTeam}
            selectId="teams-workspace-team"
          />
        }
        notificationsSlot={
          <>
            <NotificationBell
              unreadCount={notificationUnreadCount}
              isOpen={isNotificationPanelOpen}
              onToggle={toggleNotificationPanel}
              isLight
              className="notification-bell--vc-toolbar"
            />
            <NotificationPanel
              isOpen={isNotificationPanelOpen}
              notifications={notifications}
              sentNotifications={sentNotifications}
              loading={notificationsLoading}
              error={notificationsError}
              canSend={Boolean(activeTeam?.canManageTraining)}
              manualDraft={manualNotificationDraft}
              onManualChange={updateManualNotificationDraft}
              onManualSend={handleSendManualNotification}
              isSendingManual={isSendingManualNotification}
            />
          </>
        }
      >
        <TeamsPage
          teams={teams}
          activeTeamId={activeTeamId}
          onSelectTeam={handleSelectTeam}
          onOpenSchedule={openTeamSchedule}
        />
      </ClubWorkspaceLayout>
    );
  }

  if (pathname === "/schedule") {
    const canManageSchedule = Boolean(activeTeam?.canManageSchedule);
    const activeTrainingSessions = trainingStateByTeam[String(activeTeamId)]?.sessions || [];
    const trainingEntries = mapTrainingSessionsToScheduleEntries(
      schedulePayload?.week_start,
      activeTrainingSessions,
    );
    const scheduleEntries = [
      ...(canManageSchedule ? draftEntries : schedulePayload?.entries || []),
      ...trainingEntries,
    ];

    return (
      <ClubWorkspaceLayout
        activeTab="schedule"
        trainingEnabled={Boolean(activeTeam)}
        beforeIconActions={
          <ClubTeamSelect
            teams={teams}
            activeTeamId={activeTeamId}
            onChangeTeam={handleSelectTeam}
            selectId="schedule-workspace-team"
          />
        }
        notificationsSlot={
          <>
            <NotificationBell
              unreadCount={notificationUnreadCount}
              isOpen={isNotificationPanelOpen}
              onToggle={toggleNotificationPanel}
              isLight
              className="notification-bell--vc-toolbar"
            />
            <NotificationPanel
              isOpen={isNotificationPanelOpen}
              notifications={notifications}
              sentNotifications={sentNotifications}
              loading={notificationsLoading}
              error={notificationsError}
              canSend={Boolean(activeTeam?.canManageTraining)}
              manualDraft={manualNotificationDraft}
              onManualChange={updateManualNotificationDraft}
              onManualSend={handleSendManualNotification}
              isSendingManual={isSendingManualNotification}
            />
          </>
        }
      >
        <section className="teams-page-shell">
            <header className="teams-page-header">
              <div className="teams-page-heading">
                <p className="teams-page-kicker">Schedule</p>
                <h1>{activeTeam ? `${activeTeam.name} Schedule` : "Team Schedule"}</h1>
                <p className="teams-page-subtitle">
                  {activeTeam
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
                onSelectEntry={handleScheduleEntrySelect}
              />
            ) : (
              <section className="schedule-empty-card">
                <h2>No schedule</h2>
                <p>
                  {activeTeam
                    ? `There is no schedule for ${activeTeam.name} yet.`
                    : "There is no selected team schedule yet."}
                </p>
              </section>
            )}

            {canManageSchedule ? (
              <ScheduleTrainingSessions
                sessions={activeTrainingSessions}
                onEditSession={handleEditTrainingFromSchedule}
              />
            ) : null}

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

  if (pathname === "/training") {
    const activeTrainingState = trainingStateByTeam[String(activeTeamId)] || {};

    return (
      <ClubWorkspaceLayout
        activeTab="training"
        trainingEnabled={Boolean(activeTeam)}
        beforeIconActions={
          <ClubTeamSelect
            teams={teams}
            activeTeamId={activeTeamId}
            onChangeTeam={handleSelectTeam}
            selectId="training-workspace-team"
          />
        }
        notificationsSlot={
          <>
            <NotificationBell
              unreadCount={notificationUnreadCount}
              isOpen={isNotificationPanelOpen}
              onToggle={toggleNotificationPanel}
              isLight
              className="notification-bell--vc-toolbar"
            />
            <NotificationPanel
              isOpen={isNotificationPanelOpen}
              notifications={notifications}
              sentNotifications={sentNotifications}
              loading={notificationsLoading}
              error={notificationsError}
              canSend={Boolean(activeTeam?.canManageTraining)}
              manualDraft={manualNotificationDraft}
              onManualChange={updateManualNotificationDraft}
              onManualSend={handleSendManualNotification}
              isSendingManual={isSendingManualNotification}
            />
          </>
        }
      >
        {activeTeam ? (
            <TrainingPage
              team={activeTeam}
              trainingState={activeTrainingState}
              onLoad={() => loadTrainingSessions(activeTeam.id)}
              onDraftChange={(field, value) => updateTrainingDraft(activeTeam.id, field, value)}
              onCreateOrUpdate={() => saveTrainingSession(activeTeam.id)}
              onEditSession={(session) => editTrainingSessionDraft(activeTeam.id, session)}
              onResetDraft={() => resetTrainingDraft(activeTeam.id)}
              onCancelEdit={() => resetTrainingDraft(activeTeam.id)}
              onCancelSession={(sessionId) => handleCancelTrainingSession(activeTeam.id, sessionId)}
              onClearSession={(sessionId) => handleClearTrainingSession(activeTeam.id, sessionId)}
              onConfirmSession={(sessionId, playerId) =>
                handleConfirmTrainingSession(activeTeam.id, sessionId, playerId)
              }
              selectedChildId={selectedChildId}
              onSelectChild={handleSelectChildForActiveTeam}
            />
          ) : (
            <section className="schedule-empty-card">
              <h2>No team selected</h2>
              <p>Select a team first to view training sessions.</p>
            </section>
          )}
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
                <span className="brand-logo__mark" aria-hidden="true">
                  {brand.mark}
                </span>
                <span className="brand-logo__name">{brand.name}</span>
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
        trainingEnabled={Boolean(activeTeam)}
        beforeIconActions={
          <ClubTeamSelect
            teams={teams}
            activeTeamId={activeTeamId}
            onChangeTeam={handleSelectTeam}
            selectId="home-workspace-team"
          />
        }
        notificationsSlot={
          <>
            <NotificationBell
              unreadCount={notificationUnreadCount}
              isOpen={isNotificationPanelOpen}
              onToggle={toggleNotificationPanel}
              isLight
              className="notification-bell--vc-toolbar"
            />
            <NotificationPanel
              isOpen={isNotificationPanelOpen}
              notifications={notifications}
              sentNotifications={sentNotifications}
              loading={notificationsLoading}
              error={notificationsError}
              canSend={Boolean(activeTeam?.canManageTraining)}
              manualDraft={manualNotificationDraft}
              onManualChange={updateManualNotificationDraft}
              onManualSend={handleSendManualNotification}
              isSendingManual={isSendingManualNotification}
            />
          </>
        }
      >
        {renderHomepageMarketing({ withSiteNav: false })}
      </ClubWorkspaceLayout>
    );
  }

  return renderHomepageMarketing({ withSiteNav: true });
}

export default App;
