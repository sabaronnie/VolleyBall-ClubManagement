import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCurrentUser, fetchDirectorPaymentLogs } from "../api";
import { navigate } from "../navigation";

const AUTH_TOKEN_KEY = "netup.auth.token";
const CLUB_STORAGE_KEY = "netup.director.payment.club_id";

function parseClubId() {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("club_id");
  return raw ? Number(raw) : null;
}

export default function DirectorPaymentLogsPage() {
  const initialClubId = useMemo(parseClubId, []);
  const [ownedClubs, setOwnedClubs] = useState([]);
  const [clubId, setClubId] = useState(initialClubId);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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
        const clubs = me.owned_clubs || [];
        if (cancelled) {
          return;
        }
        setOwnedClubs(clubs);
        setClubId((current) => {
          if (current) {
            return current;
          }
          if (!clubs.length) {
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
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const loadLogs = useCallback(async () => {
    if (!clubId) {
      setLogs([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload = await fetchDirectorPaymentLogs(clubId, 200);
      setLogs(payload.logs || []);
    } catch (err) {
      setError(err.message || "Could not load logs.");
      setLogs([]);
    } finally {
      setLoading(false);
    }
  }, [clubId]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  if (!ownedClubs.length && !loading) {
    return (
      <div className="vc-director-page">
        <div className="vc-director-card">
          <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
            ← Return to Dashboard
          </button>
          <p className="vc-director-loading">You are not a club director, or you have no clubs yet.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="vc-director-page">
      <p className="vc-director-kicker">Payment activity log</p>
      <div className="vc-director-card">
        <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
          ← Return to Dashboard
        </button>
        <button
          type="button"
          className="vc-director-back"
          style={{ marginLeft: "0.5rem" }}
          onClick={() => navigate(`/director/payments?club_id=${clubId || ""}`)}
        >
          ← All payments
        </button>
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
                navigate(`/director/payments/logs?club_id=${n}`);
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
          {loading ? (
            <p className="vc-director-loading">Loading…</p>
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
                  {logs.length === 0 ? (
                    <tr>
                      <td colSpan={4} style={{ color: "#6b7580", fontWeight: 600 }}>
                        No activity logged yet for this club.
                      </td>
                    </tr>
                  ) : (
                    logs.map((log) => (
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
    </div>
  );
}
