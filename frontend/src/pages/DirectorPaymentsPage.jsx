import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import {
  directorBulkEmailRenewalsDueToday,
  directorEmailOutstandingNoticeForFamily,
  directorEmailRenewalsDueTodayForFamily,
  directorRecordFeePayment,
  directorSendPaymentReminder,
  directorSendReceipt,
  downloadDirectorReceiptPdf,
  fetchCurrentUser,
  fetchDirectorPaymentRows,
  fetchDirectorRenewalsDueToday,
} from "../api";
import { navigate } from "../navigation";

const AUTH_TOKEN_KEY = "netup.auth.token";
const CLUB_STORAGE_KEY = "netup.director.payment.club_id";

function parseQuery() {
  const params = new URLSearchParams(window.location.search);
  const clubId = params.get("club_id");
  const status = params.get("status") || "";
  return { clubId: clubId ? Number(clubId) : null, status };
}

function money(cur, amount) {
  const n = Number(amount);
  if (Number.isNaN(n)) {
    return `${cur || "USD"} ${amount}`;
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency: cur || "USD" }).format(n);
}

function statusBadge(status) {
  if (status === "paid") {
    return <span className="vc-status-paid">Paid</span>;
  }
  if (status === "overdue") {
    return <span className="vc-status-overdue">Overdue</span>;
  }
  return <span className="vc-status-pending">Pending</span>;
}

export default function DirectorPaymentsPage() {
  const { clubId: initialClubId, status: initialStatus } = useMemo(parseQuery, []);
  const [ownedClubs, setOwnedClubs] = useState([]);
  const [clubId, setClubId] = useState(initialClubId);
  const [statusFilter, setStatusFilter] = useState(initialStatus);
  const [families, setFamilies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [actionKey, setActionKey] = useState("");
  const [payAmount, setPayAmount] = useState("");
  const [payRecordId, setPayRecordId] = useState(null);
  const [renewalsFamilies, setRenewalsFamilies] = useState([]);
  const [renewalsMeta, setRenewalsMeta] = useState(null);
  const [renewalsLoading, setRenewalsLoading] = useState(false);
  const [renewalsFeedback, setRenewalsFeedback] = useState(null);
  const [expandedBalance, setExpandedBalance] = useState(() => new Set());
  const [expandedRenewals, setExpandedRenewals] = useState(() => new Set());

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

  const loadRows = useCallback(async () => {
    if (!clubId) {
      setFamilies([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload = await fetchDirectorPaymentRows(clubId, statusFilter || undefined);
      setFamilies(payload.families || []);
    } catch (err) {
      setError(err.message || "Could not load payments.");
      setFamilies([]);
    } finally {
      setLoading(false);
    }
  }, [clubId, statusFilter]);

  const loadRenewals = useCallback(async () => {
    if (!clubId) {
      setRenewalsFamilies([]);
      setRenewalsMeta(null);
      return;
    }
    setRenewalsLoading(true);
    setRenewalsFeedback(null);
    try {
      const payload = await fetchDirectorRenewalsDueToday(clubId);
      setRenewalsMeta(payload.club || null);
      setRenewalsFamilies(payload.families || []);
    } catch {
      setRenewalsFamilies([]);
      setRenewalsMeta(null);
    } finally {
      setRenewalsLoading(false);
    }
  }, [clubId]);

  useEffect(() => {
    loadRows();
  }, [loadRows]);

  useEffect(() => {
    loadRenewals();
  }, [loadRenewals]);

  const setFilter = (next) => {
    setSuccessMessage("");
    setStatusFilter(next);
    const params = new URLSearchParams();
    if (clubId) {
      params.set("club_id", String(clubId));
    }
    if (next) {
      params.set("status", next);
    }
    navigate(`/director/payments?${params.toString()}`);
  };

  const onClubChange = (id) => {
    setSuccessMessage("");
    const n = Number(id);
    setClubId(n);
    sessionStorage.setItem(CLUB_STORAGE_KEY, String(n));
  };

  const toggleBalanceDetails = (playerId) => {
    setExpandedBalance((prev) => {
      const next = new Set(prev);
      if (next.has(playerId)) {
        next.delete(playerId);
      } else {
        next.add(playerId);
      }
      return next;
    });
  };

  const toggleRenewalDetails = (playerId) => {
    setExpandedRenewals((prev) => {
      const next = new Set(prev);
      if (next.has(playerId)) {
        next.delete(playerId);
      } else {
        next.add(playerId);
      }
      return next;
    });
  };

  const onRecordPayment = async () => {
    if (!clubId || !payRecordId) {
      return;
    }
    setActionKey(`pay-${payRecordId}`);
    setError("");
    try {
      await directorRecordFeePayment(clubId, payRecordId, { amount: payAmount });
      setPayRecordId(null);
      setPayAmount("");
      await loadRows();
      await loadRenewals();
    } catch (err) {
      setError(err.message || "Could not record payment.");
    } finally {
      setActionKey("");
    }
  };

  const onReminder = async (recordId) => {
    if (!clubId) {
      return;
    }
    let row = null;
    for (const fam of families) {
      row = fam.lines?.find((l) => Number(l.id) === Number(recordId));
      if (row) break;
    }
    if (row?.status === "paid") {
      setSuccessMessage("");
      setError("There is no balance left on that fee line, so a reminder is not sent.");
      return;
    }
    setActionKey(`rem-${recordId}`);
    setError("");
    setSuccessMessage("");
    try {
      await directorSendPaymentReminder(clubId, recordId);
      setSuccessMessage(
        `Payment reminder sent for fee #${recordId}. Recipients get an email with a PDF balance sheet attached.`,
      );
      await loadRows();
    } catch (err) {
      setError(err.message || "Reminder failed.");
    } finally {
      setActionKey("");
    }
  };

  const onReceipt = async (recordId) => {
    if (!clubId) {
      return;
    }
    let row = null;
    for (const fam of families) {
      row = fam.lines?.find((l) => Number(l.id) === Number(recordId));
      if (row) break;
    }
    if (!row || Number(row.amount_paid) <= 0) {
      setSuccessMessage("");
      setError(
        "Receipt email is only sent after at least one payment has been recorded for that line. Record a payment first.",
      );
      return;
    }
    setActionKey(`rec-${recordId}`);
    setError("");
    setSuccessMessage("");
    try {
      await directorSendReceipt(clubId, recordId);
      setSuccessMessage(
        `Receipt email sent for fee #${recordId}. The message includes a PDF receipt for the family's records.`,
      );
      await loadRows();
    } catch (err) {
      setError(err.message || "Receipt email failed.");
    } finally {
      setActionKey("");
    }
  };

  const onBulkRenewalEmail = async () => {
    if (!clubId) {
      return;
    }
    setActionKey("bulk-renew");
    setRenewalsFeedback(null);
    setError("");
    try {
      const out = await directorBulkEmailRenewalsDueToday(clubId);
      const skipped = (out.skipped || []).length;
      setRenewalsFeedback({
        tone: "success",
        text:
          `Sent ${out.emailed_count} due-today email${out.emailed_count === 1 ? "" : "s"}` +
          (skipped ? ` (${skipped} skipped — no address or send failed).` : "."),
      });
    } catch (err) {
      setRenewalsFeedback({
        tone: "error",
        text: err.message || "Bulk email could not be sent. Check your mail settings and try again.",
      });
    } finally {
      setActionKey("");
    }
  };

  const onEmailOutstandingFamily = async (playerId) => {
    if (!clubId) {
      return;
    }
    setActionKey(`email-out-${playerId}`);
    setError("");
    setSuccessMessage("");
    try {
      const out = await directorEmailOutstandingNoticeForFamily(clubId, playerId);
      if (out.emailed_count === 0) {
        setSuccessMessage("No outstanding balance to email for that family.");
      } else {
        const to = (out.sent_to || []).join(", ");
        setSuccessMessage(
          to ? `Balance notice emailed to ${to} (PDF attached).` : "Balance notice sent (PDF attached).",
        );
      }
    } catch (err) {
      setError(err.message || "Could not send balance email.");
    } finally {
      setActionKey("");
    }
  };

  const onEmailRenewalsFamily = async (playerId) => {
    if (!clubId) {
      return;
    }
    setActionKey(`email-renew-${playerId}`);
    setRenewalsFeedback(null);
    setError("");
    try {
      const out = await directorEmailRenewalsDueTodayForFamily(clubId, playerId);
      if (out.emailed_count === 0) {
        setRenewalsFeedback({
          tone: "success",
          text: "Nothing due today for that family — no email sent.",
        });
      } else {
        const to = (out.sent_to || []).join(", ");
        setRenewalsFeedback({
          tone: "success",
          text: to ? `Due-today notice emailed to ${to} (PDF attached).` : "Due-today notice sent (PDF attached).",
        });
      }
    } catch (err) {
      setRenewalsFeedback({
        tone: "error",
        text: err.message || "That email could not be sent. Check addresses and try again.",
      });
    } finally {
      setActionKey("");
    }
  };

  const onDownloadReceiptPdf = async (recordId) => {
    if (!clubId) {
      return;
    }
    let row = null;
    for (const fam of families) {
      row = fam.lines?.find((l) => Number(l.id) === Number(recordId));
      if (row) break;
    }
    if (!row || Number(row.amount_paid) <= 0) {
      setSuccessMessage("");
      setError("Download receipt PDF only after a payment has been recorded on that line.");
      return;
    }
    setActionKey(`pdf-${recordId}`);
    setError("");
    setSuccessMessage("");
    try {
      const blob = await downloadDirectorReceiptPdf(clubId, recordId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `receipt_fee_${recordId}.pdf`;
      a.rel = "noopener";
      a.style.display = "none";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 500);
      setSuccessMessage(`Receipt PDF downloaded for fee #${recordId}.`);
    } catch (err) {
      setError(err.message || "Could not download PDF.");
    } finally {
      setActionKey("");
    }
  };

  const actionBusy =
    actionKey === "bulk-renew" ||
    actionKey.startsWith("rem-") ||
    actionKey.startsWith("rec-") ||
    actionKey.startsWith("pdf-") ||
    actionKey.startsWith("pay-") ||
    actionKey.startsWith("email-out-") ||
    actionKey.startsWith("email-renew-");

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
      <p className="vc-director-kicker">Payments — all families</p>
      <div className="vc-director-card">
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center" }}>
          <button type="button" className="vc-director-back" onClick={() => navigate("/dashboard")}>
            ← Dashboard
          </button>
          <button type="button" className="vc-link-cyan" onClick={() => navigate("/director/users")}>
            Registration
          </button>
        </div>
        {successMessage ? <div className="vc-director-success">{successMessage}</div> : null}
        {error ? <div className="vc-director-error">{error}</div> : null}

        <div className="vc-pay-toolbar">
          {ownedClubs.length > 1 ? (
            <label className="vc-pay-toolbar__field">
              Club
              <select
                value={clubId || ""}
                onChange={(e) => onClubChange(e.target.value)}
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
          <label className="vc-pay-toolbar__field">
            Status
            <select
              value={statusFilter}
              onChange={(e) => setFilter(e.target.value)}
              className="vc-director-modal__select"
            >
              <option value="">All</option>
              <option value="pending">Pending</option>
              <option value="overdue">Overdue</option>
              <option value="paid">Paid</option>
            </select>
          </label>
          <button
            type="button"
            className="vc-link-cyan"
            disabled={!clubId}
            onClick={() => navigate(`/director/payments/logs?club_id=${clubId || ""}`)}
          >
            View payment logs
          </button>
        </div>

        <section className="vc-director-section">
          <h2 className="vc-panel-title">Due today (monthly renewals)</h2>
          <p className="vc-modal__muted" style={{ marginTop: 0 }}>
            Families with a balance on a fee line whose due date is today. New players get their first month scheduled
            automatically when they join a team.
            {renewalsMeta?.default_monthly_player_fee != null
              ? ` Club default monthly rate: ${money("USD", renewalsMeta.default_monthly_player_fee)} per player per team.`
              : ""}
          </p>
          {renewalsFeedback ? (
            <div
              className={renewalsFeedback.tone === "error" ? "vc-director-error" : "vc-director-success"}
              role="status"
            >
              {renewalsFeedback.text}
            </div>
          ) : null}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", marginBottom: "1rem" }}>
            <button
              type="button"
              className="vc-director-modal__btn"
              disabled={!clubId || actionKey === "bulk-renew" || renewalsFamilies.length === 0}
              onClick={() => onBulkRenewalEmail()}
            >
              {actionKey === "bulk-renew" ? "Sending…" : "Email all due today (receipt or notice)"}
            </button>
          </div>
          {renewalsLoading ? (
            <p className="vc-director-loading">Loading renewals…</p>
          ) : renewalsFamilies.length === 0 ? (
            <p className="vc-director-loading" style={{ color: "#6b7580" }}>
              No unpaid fee lines due today.
            </p>
          ) : (
            <div className="vc-director-table-wrap">
              <table className="vc-director-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Family</th>
                    <th>Lines due</th>
                    <th>Total remaining</th>
                    <th>Status</th>
                    <th>Email due</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {renewalsFamilies.map((fam) => (
                    <Fragment key={`rf-${fam.player_id}`}>
                      <tr>
                        <td>{fam.player_id}</td>
                        <td>{fam.family_label}</td>
                        <td>{fam.lines?.length ?? 0}</td>
                        <td>{money(fam.currency, fam.total_remaining)}</td>
                        <td>{statusBadge(fam.overall_status)}</td>
                        <td>
                          <button
                            type="button"
                            className="vc-du-action"
                            disabled={actionBusy || actionKey === `email-renew-${fam.player_id}`}
                            onClick={() => void onEmailRenewalsFamily(fam.player_id)}
                          >
                            {actionKey === `email-renew-${fam.player_id}` ? "…" : "Email due"}
                          </button>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="vc-du-action"
                            onClick={() => toggleRenewalDetails(fam.player_id)}
                          >
                            {expandedRenewals.has(fam.player_id) ? "Hide" : "Details"}
                          </button>
                        </td>
                      </tr>
                      {expandedRenewals.has(fam.player_id) ? (
                        <tr key={`rf-${fam.player_id}-detail`} className="vc-director-table__detail-row">
                          <td colSpan={7} style={{ padding: "0.75rem 1rem", background: "#f8fafc" }}>
                            <table className="vc-director-table" style={{ margin: 0 }}>
                              <thead>
                                <tr>
                                  <th>Description</th>
                                  <th>Remaining</th>
                                  <th>Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {(fam.lines || []).map((r) => (
                                  <tr key={r.id}>
                                    <td>{r.description}</td>
                                    <td>{money(r.currency, r.remaining)}</td>
                                    <td>{statusBadge(r.status)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="vc-director-section">
          <h2 className="vc-panel-title">Balances by family</h2>
          {loading ? (
            <p className="vc-director-loading">Loading…</p>
          ) : (
            <div className="vc-director-table-wrap">
              <table className="vc-director-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Family</th>
                    <th>Total remaining</th>
                    <th>Status</th>
                    <th>Email due</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {families.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ color: "#6b7580", fontWeight: 600 }}>
                        No fee records match this filter. Use payment schedules to post recurring fees, or adjust the
                        status filter.
                      </td>
                    </tr>
                  ) : (
                    families.map((fam) => (
                      <Fragment key={`bf-${fam.player_id}`}>
                        <tr>
                          <td>{fam.player_id}</td>
                          <td>{fam.family_label}</td>
                          <td>{money(fam.currency, fam.total_remaining)}</td>
                          <td>{statusBadge(fam.overall_status)}</td>
                          <td>
                            <button
                              type="button"
                              className="vc-du-action"
                              disabled={actionBusy || actionKey === `email-out-${fam.player_id}`}
                              onClick={() => void onEmailOutstandingFamily(fam.player_id)}
                            >
                              {actionKey === `email-out-${fam.player_id}` ? "…" : "Email due"}
                            </button>
                          </td>
                          <td>
                            <button
                              type="button"
                              className="vc-du-action"
                              onClick={() => toggleBalanceDetails(fam.player_id)}
                            >
                              {expandedBalance.has(fam.player_id) ? "Hide" : "Details"}
                            </button>
                          </td>
                        </tr>
                        {expandedBalance.has(fam.player_id) ? (
                          <tr key={`bf-${fam.player_id}-detail`} className="vc-director-table__detail-row">
                            <td colSpan={6} style={{ padding: "0.75rem 1rem", background: "#f8fafc" }}>
                              <p className="vc-modal__muted" style={{ margin: "0 0 0.5rem" }}>
                                Fee lines for this family (total{" "}
                                {money(fam.currency, fam.total_remaining)} matches the sum of remaining balances below).
                              </p>
                              <table className="vc-director-table" style={{ margin: 0 }}>
                                <thead>
                                  <tr>
                                    <th>Description</th>
                                    <th>Remaining</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {(fam.lines || []).map((r) => (
                                    <tr key={r.id}>
                                      <td>{r.description}</td>
                                      <td>{money(r.currency, r.remaining)}</td>
                                      <td>{statusBadge(r.status)}</td>
                                      <td>
                                        <button
                                          type="button"
                                          className="vc-du-action"
                                          disabled={actionBusy || r.status === "paid"}
                                          onClick={() => onReminder(r.id)}
                                        >
                                          Remind
                                        </button>
                                        <button
                                          type="button"
                                          className="vc-du-action"
                                          disabled={actionBusy || Number(r.amount_paid) <= 0}
                                          onClick={() => onReceipt(r.id)}
                                        >
                                          Receipt email
                                        </button>
                                        <button
                                          type="button"
                                          className="vc-du-action"
                                          disabled={actionBusy || Number(r.amount_paid) <= 0}
                                          onClick={() => void onDownloadReceiptPdf(r.id)}
                                        >
                                          {actionKey === `pdf-${r.id}` ? "…" : "PDF"}
                                        </button>
                                        <button
                                          type="button"
                                          className="vc-du-action"
                                          disabled={actionBusy || r.status === "paid"}
                                          onClick={() => {
                                            setPayRecordId(r.id);
                                            setPayAmount("");
                                            setError("");
                                          }}
                                        >
                                          Pay
                                        </button>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {payRecordId ? (
          <section className="vc-director-section vc-pay-inline-form">
            <h3 className="vc-panel-title" style={{ fontSize: "1rem" }}>
              Record payment for fee #{payRecordId}
            </h3>
            <div className="vc-pay-inline-grid">
              <input
                type="text"
                placeholder="Amount"
                value={payAmount}
                onChange={(e) => setPayAmount(e.target.value)}
                className="vc-director-modal__select"
              />
              <button type="button" className="vc-director-modal__btn" onClick={onRecordPayment}>
                Submit payment
              </button>
              <button
                type="button"
                className="vc-director-modal__btn vc-director-modal__btn--ghost"
                onClick={() => setPayRecordId(null)}
              >
                Cancel
              </button>
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}
