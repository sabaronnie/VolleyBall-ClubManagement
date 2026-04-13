export default function DirectorSummaryRow({ loading, kpis, formatMoney, formatPercent }) {
  const items = [
    {
      label: "Registration",
      value:
        loading || !kpis
          ? "—"
          : `${Number(kpis.registration_player_count)} Player${Number(kpis.registration_player_count) === 1 ? "" : "s"}`,
    },
    {
      label: "Monthly Revenue",
      value: loading || !kpis ? "—" : formatMoney(kpis.monthly_revenue_currency, kpis.monthly_revenue),
    },
    {
      label: "Attendance Rate",
      value: loading || !kpis ? "—" : formatPercent(kpis.attendance_rate),
    },
    {
      label: "Outstanding Payments",
      value:
        loading || !kpis
          ? "—"
          : `${Number(kpis.outstanding_payer_count)} famil${Number(kpis.outstanding_payer_count) === 1 ? "y" : "ies"}`,
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
