import { navigate } from "../../navigation";

export default function DirectorActionButtons({ clubId }) {
  const q = clubId ? `?club_id=${clubId}` : "";
  const actions = [
    { label: "Manage Registration", onClick: () => navigate("/director/users"), disabled: false },
    {
      label: "Send Payment Reminder",
      onClick: () => navigate(`/director/payments${q}`),
      disabled: !clubId,
    },
    {
      label: "Generate Receipt",
      onClick: () => navigate(`/director/payments${q}`),
      disabled: !clubId,
    },
    {
      label: "View Logs",
      onClick: () => navigate(`/director/payments/logs${q}`),
      disabled: !clubId,
    },
  ];

  return (
    <section className="vc-director-actions-bar" aria-label="Director quick actions">
      {actions.map((a) => (
        <button
          key={a.label}
          type="button"
          className="vc-director-actions-bar__btn"
          disabled={a.disabled}
          onClick={a.onClick}
        >
          {a.label}
        </button>
      ))}
    </section>
  );
}
