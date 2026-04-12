import { useCallback, useEffect, useState } from "react";
import {
  createPaymentSchedule,
  deactivatePaymentSchedule,
  deletePaymentSchedule,
  fetchPaymentSchedules,
  fetchTeamPlayerPayments,
  fetchCurrentUser,
} from "../api";
import { navigate } from "../navigation";

function money(cur, amount) {
  const n = Number(amount);
  if (Number.isNaN(n)) return `${cur || "USD"} ${amount}`;
  return new Intl.NumberFormat("en-US", { style: "currency", currency: cur || "USD" }).format(n);
}

function statusBadge(status) {
  if (status === "paid") return <span className="vc-status-paid">Paid</span>;
  if (status === "overdue") return <span className="vc-status-overdue">Overdue</span>;
  return <span className="vc-status-pending">Pending</span>;
}

const FREQ_OPTIONS = [
  { value: "once", label: "Once" },
  { value: "hourly", label: "Hourly" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
];

export default function CoachPaymentsPage({ team }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [isDirector, setIsDirector] = useState(false);
  const [clubId, setClubId] = useState(null);
  const [clubName, setClubName] = useState("");
  const [directorTeams, setDirectorTeams] = useState([]);
  const [schedules, setSchedules] = useState([]);

  const [freq, setFreq] = useState("monthly");
  const [scope, setScope] = useState("club");
  const [amount, setAmount] = useState("");
  const [desc, setDesc] = useState("");
  const [startDate, setStartDate] = useState("");
  const [targetTeamId, setTargetTeamId] = useState("");
  const [playerId, setPlayerId] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [deactivatingId, setDeactivatingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const teamId = team?.id && team.id !== "__all__" ? team.id : null;
  const teamName = team?.name || "";

  const loadRows = useCallback(async () => {
    if (!teamId) { setRows([]); setLoading(false); return; }
    setLoading(true); setError("");
    try {
      const data = await fetchTeamPlayerPayments(teamId);
      setRows(data.fee_rows || []);
    } catch (err) { setError(err.message || "Could not load payment data."); }
    finally { setLoading(false); }
  }, [teamId]);

  useEffect(() => { void loadRows(); }, [loadRows]);

  const loadSchedules = useCallback(async () => {
    if (!clubId) return;
    try {
      const s = await fetchPaymentSchedules(clubId);
      setSchedules(s.schedules || []);
    } catch {
      setSchedules([]);
    }
  }, [clubId]);

  useEffect(() => {
    (async () => {
      try {
        const me = await fetchCurrentUser();
        const dir = Boolean(me.is_director_or_staff);
        setIsDirector(dir);
        if (dir && me.owned_clubs?.length) {
          const c = me.owned_clubs[0];
          setClubId(c.id);
          setClubName(c.name);
          setDirectorTeams(me.director_teams || []);
        }
      } catch { /* ignore */ }
    })();
  }, []);

  useEffect(() => {
    if (clubId) void loadSchedules();
  }, [clubId, loadSchedules]);

  const handleCreate = async () => {
    if (!clubId) return;
    setCreateBusy(true); setError(""); setSuccess("");
    try {
      const body = {
        frequency: freq, scope, amount: Number(amount),
        description: desc.trim(), start_date: startDate,
      };
      if (scope === "team") {
        body.team_id = targetTeamId ? Number(targetTeamId) : teamId;
      }
      if (scope === "player") {
        body.player_id = Number(playerId);
      }
      const res = await createPaymentSchedule(clubId, body);
      setSuccess(res.message || "Schedule created.");
      setAmount(""); setDesc(""); setStartDate(""); setPlayerId(""); setTargetTeamId("");
      await loadSchedules();
      if (teamId) await loadRows();
    } catch (err) { setError(err.message || "Could not create schedule."); }
    finally { setCreateBusy(false); }
  };

  const paid = rows.filter((r) => r.status === "paid");
  const unpaid = rows.filter((r) => r.status !== "paid");
  const totalDue = unpaid.reduce((s, r) => s + Number(r.remaining || 0), 0);
  const cur = rows[0]?.currency || "USD";

  return (
    <section className="vc-coach-payments-page" style={{ padding: "2rem 1.75rem", width: "100%", maxWidth: "min(1180px, 100%)", margin: "0 auto", boxSizing: "border-box" }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center", marginBottom: "1.25rem" }}>
        <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
          ← Dashboard
        </button>
        <h1 style={{ fontSize: "1.3rem", margin: 0 }}>
          {teamId ? `${teamName} Payments` : "Payments"}
        </h1>
      </div>

      {success ? <div className="vc-director-success">{success}</div> : null}
      {error ? <div className="vc-director-error">{error}</div> : null}

      {!isDirector ? (
        <p
          className="vc-modal__muted"
          style={{ marginBottom: "1rem", padding: "0.75rem 1rem", background: "#f0f9ff", borderRadius: 8, lineHeight: 1.5 }}
        >
          You are viewing <strong>team fee records</strong> for the team selected above. This screen is for monitoring
          players&apos; balances, not for your own membership dues.
        </p>
      ) : null}

      {isDirector ? (
        <section className="vc-dash-kpi-card vc-dash-kpi-card--stack" style={{ marginBottom: "1.25rem" }}>
          <h2 style={{ fontSize: "1.1rem", margin: 0 }}>Create payment schedule</h2>
          <p style={{ color: "#5c6570", fontSize: "0.9rem", margin: "0 0 0.85rem", lineHeight: 1.5 }}>
            Set up a recurring or one-time payment. Choose who it applies to: every player
            in {clubName || "the club"}, a specific team, or a single player.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: "0.6rem" }}>
            <label style={{ display: "grid", gap: "0.2rem", fontSize: "0.85rem" }}>
              Frequency
              <select className="vc-director-modal__select" value={freq} onChange={(e) => setFreq(e.target.value)}>
                {FREQ_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </label>
            <label style={{ display: "grid", gap: "0.2rem", fontSize: "0.85rem" }}>
              Apply to
              <select className="vc-director-modal__select" value={scope} onChange={(e) => setScope(e.target.value)}>
                <option value="club">Everyone in the club</option>
                <option value="team">Everyone in a team</option>
                <option value="player">One player only</option>
              </select>
            </label>
            <label style={{ display: "grid", gap: "0.2rem", fontSize: "0.85rem" }}>
              Amount
              <input className="vc-director-modal__select" type="number" step="0.01" min="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="e.g. 50.00" />
            </label>
            <label style={{ display: "grid", gap: "0.2rem", fontSize: "0.85rem" }}>
              Start / due date
              <input className="vc-director-modal__select" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </label>
            {scope === "team" ? (
              <label style={{ display: "grid", gap: "0.2rem", fontSize: "0.85rem" }}>
                Team
                <select className="vc-director-modal__select" value={targetTeamId} onChange={(e) => setTargetTeamId(e.target.value)}>
                  <option value="">{teamId ? `Current (${teamName})` : "Select a team…"}</option>
                  {directorTeams.map((t) => (
                    <option key={t.id} value={String(t.id)}>{t.name}</option>
                  ))}
                </select>
              </label>
            ) : null}
            {scope === "player" ? (
              <label style={{ display: "grid", gap: "0.2rem", fontSize: "0.85rem" }}>
                Player user ID
                <input className="vc-director-modal__select" value={playerId} onChange={(e) => setPlayerId(e.target.value)} placeholder="User ID" />
              </label>
            ) : null}
            <label style={{ display: "grid", gap: "0.2rem", fontSize: "0.85rem", gridColumn: "1 / -1" }}>
              Description
              <input className="vc-director-modal__select" value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="e.g. Monthly training fee" />
            </label>
          </div>
          <button
            type="button" className="vc-director-modal__btn" style={{ marginTop: "0.85rem" }}
            disabled={createBusy || !amount || !desc.trim() || !startDate}
            onClick={handleCreate}
          >
            {createBusy ? "Creating…" : "Create payment schedule"}
          </button>
        </section>
      ) : null}

      {schedules.length ? (
        <section className="vc-dash-kpi-card vc-dash-kpi-card--stack" style={{ marginBottom: "1.25rem" }}>
          <h2 style={{ fontSize: "1.05rem", margin: 0 }}>Active payment schedules</h2>
          <p className="vc-modal__muted" style={{ margin: 0, lineHeight: 1.5 }}>
            Active schedules create charges. Deactivate one to stop new charges; then you can remove it from this list.
          </p>
          <div className="vc-payments-schedules-scroll">
            <table className="vc-table">
              <thead>
                <tr>
                  <th>Description</th>
                  <th>How often</th>
                  <th>Applies to</th>
                  <th>Amount</th>
                  <th>Start date</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {schedules.map((s) => (
                  <tr key={s.id}>
                    <td>{s.description}</td>
                    <td style={{ textTransform: "capitalize" }}>{s.frequency}</td>
                    <td>
                      {s.scope === "club" ? "Entire club" : s.scope === "team" ? (s.team_name || "Team") : (s.player_name || "Player")}
                    </td>
                    <td>{money(s.currency, s.amount)}</td>
                    <td>{s.start_date}</td>
                    <td>{s.is_active ? <span className="vc-status-pending">Active</span> : <span className="vc-modal__muted">Inactive</span>}</td>
                    <td>
                      {s.is_active ? (
                        <button
                          type="button"
                          className="vc-link-cyan"
                          style={{ margin: 0 }}
                          disabled={deactivatingId === s.id || deletingId === s.id || !clubId}
                          onClick={async () => {
                            setDeactivatingId(s.id);
                            setError("");
                            setSuccess("");
                            try {
                              const res = await deactivatePaymentSchedule(clubId, s.id);
                              setSuccess(res.message || "Schedule deactivated.");
                              await loadSchedules();
                            } catch (err) {
                              setError(err.message || "Could not deactivate schedule.");
                            } finally {
                              setDeactivatingId(null);
                            }
                          }}
                        >
                          {deactivatingId === s.id ? "Working…" : "Deactivate"}
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="vc-link-cyan"
                          style={{ margin: 0, color: "#b71c1c" }}
                          disabled={deletingId === s.id || deactivatingId === s.id || !clubId}
                          onClick={async () => {
                            if (!window.confirm("Remove this inactive schedule from the list? Past fee rows stay in billing history.")) {
                              return;
                            }
                            setDeletingId(s.id);
                            setError("");
                            setSuccess("");
                            try {
                              const res = await deletePaymentSchedule(clubId, s.id);
                              setSuccess(res.message || "Schedule removed.");
                              await loadSchedules();
                            } catch (err) {
                              setError(err.message || "Could not delete schedule.");
                            } finally {
                              setDeletingId(null);
                            }
                          }}
                        >
                          {deletingId === s.id ? "…" : "Delete"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {!teamId ? (
        <p className="vc-modal__muted" style={{ marginTop: "1rem" }}>
          Select a specific team from the dropdown above to see player fee records for that team.
        </p>
      ) : null}

      {teamId && loading ? <p className="vc-modal__muted">Loading fee records…</p> : null}

      {teamId && !loading ? (
        <>
          <div className="vc-dash-kpi-card" style={{ marginBottom: "1.25rem", display: "flex", gap: "2rem", flexWrap: "wrap" }}>
            <div><div className="vc-kpi-label">Outstanding</div><div className="vc-kpi-value">{money(cur, totalDue)}</div></div>
            <div><div className="vc-kpi-label">Unpaid</div><div className="vc-kpi-value">{unpaid.length}</div></div>
            <div><div className="vc-kpi-label">Paid</div><div className="vc-kpi-value">{paid.length}</div></div>
          </div>

          {rows.length ? (
            <section>
              <h2 style={{ fontSize: "1.05rem", marginBottom: "0.65rem" }}>Player fee records</h2>
              <div style={{ overflowX: "auto" }}>
                <table className="vc-table">
                  <thead><tr><th>Player</th><th>Description</th><th>Due</th><th>Paid</th><th>Remaining</th><th>Due date</th><th>Status</th></tr></thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.id}>
                        <td>{r.family_label}</td>
                        <td>{r.description}</td>
                        <td>{money(r.currency, r.amount_due)}</td>
                        <td>{money(r.currency, r.amount_paid)}</td>
                        <td>{money(r.currency, r.remaining)}</td>
                        <td>{r.due_date}</td>
                        <td>{statusBadge(r.status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : <p className="vc-modal__muted">No fee records for this team yet.</p>}
        </>
      ) : null}
    </section>
  );
}
