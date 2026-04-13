import { useCallback, useEffect, useRef, useState } from "react";
import { fetchNotifications, markNotificationsRead } from "../api";
import { BellIcon } from "./AppIcons";
import { navigate } from "../navigation";

const AUTH_TOKEN_KEY = "netup.auth.token";

function followCoachAttendancePath(fullPath) {
  if (!fullPath || typeof fullPath !== "string") {
    return;
  }
  const qIndex = fullPath.indexOf("?");
  const search = qIndex >= 0 ? fullPath.slice(qIndex + 1) : "";
  const params = new URLSearchParams(search);
  const team = params.get("team");
  if (team) {
    const tid = Number(team);
    if (Number.isFinite(tid) && tid > 0) {
      window.dispatchEvent(new CustomEvent("netup-set-active-team", { detail: { teamId: tid } }));
    }
  }
  navigate(fullPath.startsWith("/") ? fullPath : `/${fullPath}`);
}

export default function NotificationBell({ teamId = null }) {
  const wrapRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [markBusy, setMarkBusy] = useState(false);

  const load = useCallback(async () => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
      setPayload(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await fetchNotifications(teamId || undefined);
      setPayload(data);
    } catch (err) {
      setError(err.message || "Could not load notifications.");
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    void load();
    const onAuth = () => void load();
    window.addEventListener("auth-state-changed", onAuth);
    return () => window.removeEventListener("auth-state-changed", onAuth);
  }, [load]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    void load();
    const onPointerDown = (event) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open, load]);

  const unreadCount = payload?.unread_count ?? 0;
  const items = payload?.items || [];

  const onMarkAllRead = async () => {
    setMarkBusy(true);
    setError("");
    try {
      await markNotificationsRead();
      await load();
    } catch (err) {
      setError(err.message || "Could not mark notifications read.");
    } finally {
      setMarkBusy(false);
    }
  };

  if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
    return null;
  }

  return (
    <div className="nav-notification-stack" ref={wrapRef}>
      <button
        type="button"
        className={`notification-bell notification-bell--light${open ? " is-open" : ""}`}
        aria-label="Notifications"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="notification-bell__icon" aria-hidden="true">
          <BellIcon />
        </span>
        {unreadCount > 0 ? (
          <span className="notification-bell__badge" aria-hidden="true">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        ) : null}
      </button>
      {open ? (
        <div className="notification-panel" role="dialog" aria-label="Notifications">
          <div className="notification-panel__header">
            <h2>Notifications</h2>
          </div>
          {error ? <p className="schedule-feedback schedule-feedback--error">{error}</p> : null}
          {loading ? <p className="notification-empty-state">Loading…</p> : null}
          {!loading && items.length === 0 ? (
            <p className="notification-empty-state">No notifications yet.</p>
          ) : null}
          {!loading && items.length > 0 ? (
            <ul className="notification-list" style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {items.map((item) => (
                <li
                  key={item.id}
                  className={`notification-item${item.is_read ? "" : " notification-item--new"}`}
                >
                  <strong>{item.title}</strong>
                  <p>{item.message}</p>
                  {item.team_name ? (
                    <span className="notification-item__meta">{item.team_name}</span>
                  ) : null}
                  {item.category === "attendance_incomplete" && item.coach_attendance_path ? (
                    <div style={{ marginTop: "0.65rem" }}>
                      <button
                        type="button"
                        className="vc-action-btn"
                        style={{ fontSize: "0.88rem", padding: "0.45rem 0.85rem" }}
                        onClick={() => {
                          followCoachAttendancePath(item.coach_attendance_path);
                          setOpen(false);
                        }}
                      >
                        Open team attendance
                      </button>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
          <div style={{ marginTop: "1rem", display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
            <button
              type="button"
              className="vc-dash-icon-btn"
              style={{ fontSize: "0.85rem" }}
              disabled={markBusy || unreadCount === 0}
              onClick={() => void onMarkAllRead()}
            >
              Mark all read
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
