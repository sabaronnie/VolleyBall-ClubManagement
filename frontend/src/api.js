const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");
const AUTH_TOKEN_KEY = "netup.auth.token";

function normalizeErrors(payload, fallbackMessage) {
  if (!payload || typeof payload !== "object") {
    return fallbackMessage;
  }

  if (payload.errors && typeof payload.errors === "object") {
    const messages = Object.values(payload.errors).flatMap((value) =>
      Array.isArray(value) ? value : [value],
    );
    return messages.filter(Boolean).join(" ");
  }

  if (typeof payload.message === "string" && payload.message.trim()) {
    return payload.message;
  }

  return fallbackMessage;
}

async function request(path, body) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Cannot reach backend. Make sure Django is running on port 8000.");
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new Error(normalizeErrors(payload, "Request failed. Please try again."));
  }

  return payload;
}

async function authenticatedGet(path) {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token || ""}`,
      },
    });
  } catch {
    throw new Error("Cannot reach backend. Make sure Django is running on port 8000.");
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new Error(normalizeErrors(payload, "Request failed. Please try again."));
  }

  return payload;
}

async function authenticatedJson(path, method, body) {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token || ""}`,
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Cannot reach backend. Make sure Django is running on port 8000.");
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new Error(normalizeErrors(payload, "Request failed. Please try again."));
  }

  return payload;
}

export async function loginWithPassword({ email, password }) {
  return request("/api/auth/login/", { email, password });
}

export async function requestPasswordReset({ email }) {
  return request("/api/auth/password-reset/request/", { email });
}

export async function confirmPasswordReset({ email, otp, new_password }) {
  return request("/api/auth/password-reset/confirm/", { email, otp, new_password });
}

export async function registerUser({ firstName, lastName, email, password, dateOfBirth }) {
  return request("/api/register/", {
    first_name: firstName,
    last_name: lastName,
    email,
    password,
    date_of_birth: dateOfBirth,
  });
}

export async function fetchCurrentUser() {
  return authenticatedGet("/api/auth/me/");
}

export async function fetchTeamSchedule(teamId) {
  return authenticatedGet(`/api/teams/${teamId}/schedule/`);
}

export async function saveTeamSchedule(teamId, entries) {
  return authenticatedJson(`/api/teams/${teamId}/schedule/`, "PUT", { entries });
}

export async function fetchTeamTrainingSessions(teamId) {
  return authenticatedGet(`/api/teams/${teamId}/training-sessions/`);
}

export async function createTeamTrainingSession(teamId, payload) {
  return authenticatedJson(`/api/teams/${teamId}/training-sessions/`, "POST", payload);
}

export async function updateTrainingSession(sessionId, payload) {
  return authenticatedJson(`/api/training-sessions/${sessionId}/`, "PUT", payload);
}

export async function cancelTrainingSession(sessionId) {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/training-sessions/${sessionId}/`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token || ""}`,
      },
    });
  } catch {
    throw new Error("Cannot reach backend. Make sure Django is running on port 8000.");
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new Error(normalizeErrors(payload, "Request failed. Please try again."));
  }

  return payload;
}

export async function clearTrainingSession(sessionId) {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/training-sessions/${sessionId}/clear/`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token || ""}`,
      },
    });
  } catch {
    throw new Error("Cannot reach backend. Make sure Django is running on port 8000.");
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new Error(normalizeErrors(payload, "Request failed. Please try again."));
  }

  return payload;
}

export async function confirmTrainingSession(sessionId, playerId) {
  return authenticatedJson(`/api/training-sessions/${sessionId}/confirm/`, "POST", {
    player_id: playerId,
  });
}

export async function fetchNotifications(teamId) {
  const query = teamId ? `?team_id=${encodeURIComponent(teamId)}` : "";
  return authenticatedGet(`/api/notifications/${query}`);
}

export async function markNotificationsRead() {
  return authenticatedJson("/api/notifications/read/", "POST", {});
}

export async function sendTeamNotification(payload) {
  return authenticatedJson("/api/notifications/send/", "POST", payload);
}

export async function fetchDirectorPendingUsers() {
  return authenticatedGet("/api/directors/pending-users/");
}

export async function directorVerifyUser(userId, body) {
  return authenticatedJson(`/api/directors/users/${userId}/verify/`, "POST", body || {});
}

export async function directorRejectUser(userId) {
  return authenticatedJson(`/api/directors/users/${userId}/reject/`, "POST", {});
}
