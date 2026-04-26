import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCurrentUser, fetchDirectorPaymentLogs, fetchRecentAuditLogs } from "../api";
import { navigate } from "../navigation";
import { toReadableAction } from "../utils/auditLogDisplay";

const AUTH_TOKEN_KEY = "netup.auth.token";
const CLUB_STORAGE_KEY = "netup.director.payment.club_id";

function parseClubId() {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("club_id");
  return raw ? Number(raw) : null;
}

export default function DirectorPaymentLogsPage({
  embedded = false,
  preferredClubId = null,
  onOpenPayments = null,
}) {
  const initialClubId = useMemo(parseClubId, []);
  const [ownedClubs, setOwnedClubs] = useState([]);
  const [viewerIsStaff, setViewerIsStaff] = useState(false);
  const [meReady, setMeReady] = useState(false);
  const [clubId, setClubId] = useState(initialClubId);
  /** Director payment log rows (full-page / payment-only view; not used when embedded in dashboard). */
  const [paymentLogs, setPaymentLogs] = useState([]);
  /** General audit log rows (dashboard embed — same family as “Recent Activity”). */
  const [activityLogs, setActivityLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [error, setError] = useState("");

  const canViewLogs =
    (Array.isArray(ownedClubs) && ownedClubs.length > 0) || viewerIsStaff;

  useEffect(() => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
      navigate("/login");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await fetchCurrentUser();
        if (cancelled) {
          return;
        }
        const clubs = me.owned_clubs || [];
        const staff = me.viewer_is_staff === true;
        setViewerIsStaff(staff);
        setOwnedClubs(clubs);
        setClubId((current) => {
          if (preferredClubId) {
            const n = Number(preferredClubId);
            if (clubs.some((c) => c.id === n)) {
              return n;
            }
            if (staff) {
              return n;
            }
          }
          if (current) {
            if (staff || clubs.some((c) => c.id === current)) {
              return current;
            }
          }
          if (!clubs.length) {
            if (staff) {
              if (initialClubId) {
                return initialClubId;
              }
            }
            return current;
          }
          const stored = sessionStorage.getItem(CLUB_STORAGE_KEY);
          const fromStore = stored ? Number(stored) : null;
          if (fromStore && clubs.some((c) => c.id === fromStore)) {
            return fromStore;
          }
          return clubs[0].id;
        });
      } catch {
        if (!cancelled) {
          setOwnedClubs([]);
          setViewerIsStaff(false);
        }
      } finally {
        if (!cancelled) {
          setMeReady(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [preferredClubId, initialClubId]);

  useEffect(() => {
    if (!preferredClubId) {
      return;
    }
    const n = Number(preferredClubId);
    if (ownedClubs.some((club) => club.id === n)) {
      setClubId(n);
    } else if (viewerIsStaff) {
      setClubId(n);
    }
  }, [preferredClubId, ownedClubs, viewerIsStaff]);

  const loadLogs = useCallback(async () => {
    if (!meReady) {
      return;
    }
    if (!canViewLogs || !clubId) {
      setPaymentLogs([]);
      setActivityLogs([]);
      setLogsLoading(false);
      return;
    }
    setLogsLoading(true);
    setError("");
    try {
      if (embedded) {
        setPaymentLogs([]);
        const payload = await fetchRecentAuditLogs(200, clubId);
        setActivityLogs(Array.isArray(payload.logs) ? payload.logs : []);
      } else {
        setActivityLogs([]);
        const payload = await fetchDirectorPaymentLogs(clubId, 200);
        setPaymentLogs(payload.logs || []);
      }
    } catch (err) {
      const msg = err.message || "Could not load logs.";
      const lower = String(msg).toLowerCase();
      if (
        lower.includes("only a director") ||
        lower.includes("authorization") ||
        lower.includes("forbidden")
      ) {
        setError("You do not have permission to view logs for this club.");
      } else {
        setError(msg);
      }
      setPaymentLogs([]);
      setActivityLogs([]);
    } finally {
      setLogsLoading(false);
    }
  }, [meReady, canViewLogs, clubId, embedded]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  if (!meReady) {
    return embedded ? (
      <div className="vc-director-card vc-director-card--embedded">
        <p className="vc-director-loading">Loading…</p>
      </div>
    ) : (
      <div className="vc-director-page">
        <div className="vc-director-card">
          <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
            ← Return to Dashboard
          </button>
          <p className="vc-director-loading">Loading…</p>
        </div>
      </div>
    );
  }

  if (!canViewLogs) {
    return embedded ? (
      <div className="vc-director-card vc-director-card--embedded">
        <p className="vc-director-loading">You do not have permission to view logs for this club.</p>
      </div>
    ) : (
      <div className="vc-director-page">
        <div className="vc-director-card">
          <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
            ← Return to Dashboard
          </button>
          <p className="vc-director-loading">You do not have permission to view logs for this club.</p>
        </div>
      </div>
    );
  }

  if (!clubId) {
    return embedded ? (
      <div className="vc-director-card vc-director-card--embedded">
        <p className="vc-director-loading">Select a club to view logs.</p>
      </div>
    ) : (
      <div className="vc-director-page">
        <div className="vc-director-card">
          <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
            ← Return to Dashboard
          </button>
          <p className="vc-director-loading">Select a club to view logs.</p>
        </div>
      </div>
    );
  }

  const cardContent = (
    <div className={`vc-director-card${embedded ? " vc-director-card--embedded" : ""}`}>
      {!embedded ? (
        <>
          <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
            ← Return to Dashboard
          </button>
          <button
            type="button"
            className="vc-director-back"
            style={{ marginLeft: "0.5rem" }}
            onClick={() => {
              if (onOpenPayments) {
                onOpenPayments();
                return;
              }
              navigate(`/director/payments?club_id=${clubId || ""}`);
            }}
          >
            ← All payments
          </button>
        </>
      ) : null}
        {error ? <div className="vc-director-error">{error}</div> : null}

        {ownedClubs.length > 1 ? (
          <label className="vc-pay-toolbar__field" style={{ marginTop: "1rem", display: "block" }}>
            Club
            <select
              value={clubId || ""}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  setClubId(n);
                  sessionStorage.setItem(CLUB_STORAGE_KEY, String(n));
                  if (!embedded) {
                    navigate(`/director/payments/logs?club_id=${n}`);
                  }
                }}
                className="vc-director-modal__select"
              >
              {ownedClubs.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <section className="vc-director-section">
          {logsLoading ? (
            <p className="vc-director-loading">Loading…</p>
          ) : embedded ? (
            <div className="vc-director-table-wrap">
              <table className="vc-director-table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>User</th>
                    <th>Action</th>
                    <th>Context</th>
                  </tr>
                </thead>
                <tbody>
                  {activityLogs.length === 0 ? (
                    <tr>
                      <td colSpan={4} style={{ color: "#6b7580", fontWeight: 600 }}>
                        No logs recorded yet.
                      </td>
                    </tr>
                  ) : (
                    activityLogs.map((log) => (
                      <tr key={log.id}>
                        <td>{new Date(log.timestamp).toLocaleString()}</td>
                        <td>{log.user_name || "—"}</td>
                        <td>{toReadableAction(log.action_type)}</td>
                        <td style={{ maxWidth: 360, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                          {String(log.entity_type || "").trim() || "—"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="vc-director-table-wrap">
              <table className="vc-director-table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Director</th>
                    <th>Action</th>
                    <th>Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {paymentLogs.length === 0 ? (
                    <tr>
                      <td colSpan={4} style={{ color: "#6b7580", fontWeight: 600 }}>
                        No logs recorded yet.
                      </td>
                    </tr>
                  ) : (
                    paymentLogs.map((log) => (
                      <tr key={log.id}>
                        <td>{new Date(log.created_at).toLocaleString()}</td>
                        <td>{log.actor.display_name}</td>
                        <td>{log.action_label}</td>
                        <td style={{ maxWidth: 420, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                          {log.detail}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
  );

  if (embedded) {
    return cardContent;
  }

  return (
    <div className="vc-director-page">
      <p className="vc-director-kicker">Payment activity log</p>
      {cardContent}
    </div>
  );
}
