function toLocalDate(value) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) {
    return null;
  }
  return d;
}

export function formatActivityTime(value) {
  const d = toLocalDate(value);
  if (!d) {
    return "";
  }
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const dayDiff = Math.round((today.getTime() - target.getTime()) / 86400000);
  if (dayDiff === 0) {
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
  if (dayDiff === 1) {
    return "Yesterday";
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function toReadableAction(actionType) {
  const raw = String(actionType || "").trim();
  if (!raw) {
    return "did an action";
  }
  return raw
    .toLowerCase()
    .split("_")
    .join(" ");
}

export function buildActivityLine(log) {
  const userName = log?.user_name || "A user";
  const actionPhrase = toReadableAction(log?.action_type);
  const entityLabel = String(log?.entity_type || "").trim().toLowerCase();
  if (entityLabel) {
    return `${userName} ${actionPhrase} (${entityLabel})`;
  }
  return `${userName} ${actionPhrase}`;
}
