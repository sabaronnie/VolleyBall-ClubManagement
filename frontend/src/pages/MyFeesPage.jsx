import { useCallback, useEffect, useState } from "react";
import { fetchMyFees, recordSelfPayment } from "../api";
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

function FeeRow({ fee, onPaySuccess }) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("in_person");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const remaining = Number(fee.remaining || 0);

  const handlePay = async () => {
    const val = Number(amount);
    if (!amount || Number.isNaN(val) || val <= 0 || val > remaining) {
      setError(`Enter an amount between 0.01 and ${remaining.toFixed(2)}.`);
      return;
    }
    setBusy(true); setError("");
    try {
      await recordSelfPayment(fee.id, { amount: val, method, note });
      setOpen(false); setAmount(""); setNote("");
      onPaySuccess();
    } catch (err) { setError(err.message || "Payment failed."); }
    finally { setBusy(false); }
  };

  return (
    <>
      <tr>
        <td>{fee.description}</td>
        <td>{fee.team_name || "\u2014"}</td>
        <td>{money(fee.currency, fee.amount_due)}</td>
        <td>{money(fee.currency, fee.amount_paid)}</td>
        <td>{money(fee.currency, fee.remaining)}</td>
        <td>{fee.due_date}</td>
        <td>{statusBadge(fee.status)}</td>
        <td>
          {fee.status !== "paid" ? (
            <button type="button" className="vc-director-modal__btn" style={{ padding: "0.3rem 0.7rem", fontSize: "0.85rem" }} onClick={() => setOpen((o) => !o)}>
              {open ? "Cancel" : "Pay"}
            </button>
          ) : null}
        </td>
      </tr>
      {open ? (
        <tr>
          <td colSpan={8}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "flex-end", padding: "0.5rem 0" }}>
              <label style={{ display: "grid", gap: "0.2rem", fontSize: "0.85rem" }}>
                Amount
                <input className="vc-director-modal__select" type="number" step="0.01" min="0.01" max={remaining} value={amount} placeholder={remaining.toFixed(2)} onChange={(e) => setAmount(e.target.value)} style={{ width: 120 }} />
              </label>
              <label style={{ display: "grid", gap: "0.2rem", fontSize: "0.85rem" }}>
                Method
                <select className="vc-director-modal__select" value={method} onChange={(e) => setMethod(e.target.value)}>
                  <option value="in_person">In person</option>
                  <option value="online">Online / transfer</option>
                </select>
              </label>
              <label style={{ display: "grid", gap: "0.2rem", fontSize: "0.85rem", flex: "1 1 140px" }}>
                Note (optional)
                <input className="vc-director-modal__select" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. cash, Venmo" />
              </label>
              <button type="button" className="vc-director-modal__btn" disabled={busy} onClick={handlePay} style={{ alignSelf: "flex-end" }}>
                {busy ? "Processing\u2026" : "Confirm payment"}
              </button>
            </div>
            {error ? <div className="vc-director-error" style={{ marginTop: "0.3rem" }}>{error}</div> : null}
          </td>
        </tr>
      ) : null}
    </>
  );
}

export default function MyFeesPage() {
  const [ownFees, setOwnFees] = useState([]);
  const [childrenFees, setChildrenFees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const data = await fetchMyFees();
      setOwnFees(data.own_fees || []);
      setChildrenFees(data.children_fees || []);
    } catch (err) { setError(err.message || "Could not load fees."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handlePaySuccess = () => { setSuccess("Payment recorded."); void load(); };

  const ownUnpaid = ownFees.filter((f) => f.status !== "paid");
  const childUnpaid = childrenFees.filter((f) => f.status !== "paid");
  const cur = ownFees[0]?.currency || childrenFees[0]?.currency || "USD";
  const totalOwn = ownUnpaid.reduce((s, r) => s + Number(r.remaining || 0), 0);
  const totalChild = childUnpaid.reduce((s, r) => s + Number(r.remaining || 0), 0);

  const renderTable = (title, rows) => {
    if (!rows.length) return null;
    return (
      <section style={{ marginBottom: "1.5rem" }}>
        <h2 style={{ fontSize: "1.1rem", marginBottom: "0.65rem" }}>{title}</h2>
        <div style={{ overflowX: "auto" }}>
          <table className="vc-table">
            <thead><tr><th>Description</th><th>Team</th><th>Due</th><th>Paid</th><th>Remaining</th><th>Due date</th><th>Status</th><th></th></tr></thead>
            <tbody>{rows.map((fee) => <FeeRow key={fee.id} fee={fee} onPaySuccess={handlePaySuccess} />)}</tbody>
          </table>
        </div>
      </section>
    );
  };

  return (
    <section style={{ padding: "2rem 1.75rem", maxWidth: 940, margin: "0 auto" }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center", marginBottom: "1.25rem" }}>
        <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>← Dashboard</button>
        <h1 style={{ fontSize: "1.3rem", margin: 0 }}>My Fees & Payments</h1>
      </div>

      {success ? <div className="vc-director-success">{success}</div> : null}
      {error ? <div className="vc-director-error">{error}</div> : null}
      {loading ? <p className="vc-modal__muted">Loading…</p> : null}

      {!loading && !error ? (
        <>
          <div className="vc-dash-kpi-card" style={{ marginBottom: "1.25rem", display: "flex", gap: "2rem", flexWrap: "wrap" }}>
            {ownFees.length || !childrenFees.length ? (
              <div><div className="vc-kpi-label">My outstanding</div><div className="vc-kpi-value">{money(cur, totalOwn)}</div></div>
            ) : null}
            {childrenFees.length ? (
              <div><div className="vc-kpi-label">Children outstanding</div><div className="vc-kpi-value">{money(cur, totalChild)}</div></div>
            ) : null}
          </div>

          {renderTable("Your fees", ownFees)}
          {renderTable("Children's fees", childrenFees)}

          {!ownFees.length && !childrenFees.length ? (
            <p className="vc-modal__muted">No fee records found on your account.</p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
