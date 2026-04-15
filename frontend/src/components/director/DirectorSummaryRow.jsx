const NO_DATA = "No data available";

function registrationLabel(count) {
  if (!Number.isFinite(count)) {
    return NO_DATA;
  }
  const n = Math.trunc(count);
  return `${n} Player${n === 1 ? "" : "s"}`;
}

export default function DirectorSummaryRow({ loading, kpis, paymentSnapshot = null, formatMoney, formatPercent }) {
  const items = [
    {
      label: "Registration",
      value: loading ? "—" : !kpis ? NO_DATA : registrationLabel(Number(kpis.registration_player_count)),
    },
    {
      label: "Monthly Revenue",
      value: loading
        ? "—"
        : !kpis
          ? NO_DATA
          : kpis.monthly_revenue != null && kpis.monthly_revenue !== ""
            ? formatMoney(kpis.monthly_revenue_currency, kpis.monthly_revenue)
            : NO_DATA,
    },
    {
      label: "Attendance Rate",
      value: loading
        ? "—"
        : !kpis
          ? NO_DATA
          : kpis.attendance_rate == null || kpis.attendance_rate === ""
            ? NO_DATA
            : formatPercent(kpis.attendance_rate),
    },
    {
      label: "Outstanding Payments",
      value: loading
        ? "—"
        : paymentSnapshot && paymentSnapshot.outstandingTotal != null
          ? formatMoney(paymentSnapshot.currency, paymentSnapshot.outstandingTotal)
          : NO_DATA,
    },
  ];

  return (
    <section className="vc-dashboard-kpi-strip" aria-label="Key performance indicators">
      <div className="vc-dashboard-kpi-strip__grid">
        {items.map((item) => (
          <div key={item.label} className="vc-dashboard-kpi-strip__cell">
            <div className="vc-dashboard-kpi-strip__label">{item.label}</div>
            <div className="vc-dashboard-kpi-strip__value">{item.value}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
