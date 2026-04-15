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

  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { message: text.slice(0, 280) };
    }
  }

  if (!response.ok) {
    const fromApi = normalizeErrors(payload, "");
    throw new Error(
      fromApi || `Request failed (HTTP ${response.status}). Response was not JSON — is Django running on port 8000?`,
    );
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

async function authenticatedDelete(path) {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
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

export async function verifyRegistrationOtp({ email, otp }) {
  return request("/api/register/verify/", { email, otp });
}

export async function submitContactForm({ name, email, role, message, phone }) {
  return request("/api/contact/", {
    name,
    email,
    role,
    message,
    phone: phone || "",
  });
}

export async function fetchCurrentUser() {
  return authenticatedGet("/api/auth/me/");
}

export async function updateUserEmergencyContact(userId, emergencyContact) {
  return authenticatedJson(`/api/users/${userId}/emergency-contact/`, "PATCH", {
    emergency_contact: emergencyContact,
  });
}

/** Create a club; creator becomes club director (see POST /api/clubs/create/). */
export async function createClub(body) {
  return authenticatedJson("/api/clubs/create/", "POST", body);
}

export async function fetchParentChildAttendanceHistory() {
  return authenticatedGet("/api/me/parent/child-attendance/");
}

export async function fetchMemberDashboard(forPlayerId) {
  const q =
    forPlayerId != null && String(forPlayerId).trim() !== ""
      ? `?for_player_id=${encodeURIComponent(String(forPlayerId))}`
      : "";
  return authenticatedGet(`/api/me/member-dashboard/${q}`);
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
  const body = playerId != null ? { player_id: playerId } : {};
  return authenticatedJson(`/api/training-sessions/${sessionId}/confirm/`, "POST", body);
}

export async function unconfirmTrainingSession(sessionId, playerId) {
  const body = playerId != null ? { player_id: playerId } : {};
  return authenticatedJson(`/api/training-sessions/${sessionId}/confirm/`, "DELETE", body);
}

export async function fetchCoachTrainingSessionAttendance(sessionId) {
  return authenticatedGet(`/api/training-sessions/${sessionId}/attendance/`);
}

export async function fetchTeamAttendanceAnalytics(teamId, params = {}) {
  const sp = new URLSearchParams();
  if (params.startDate) {
    sp.set("start_date", params.startDate);
  }
  if (params.endDate) {
    sp.set("end_date", params.endDate);
  }
  if (params.grouping) {
    sp.set("grouping", params.grouping);
  }
  if (params.lastNSessions != null && params.lastNSessions !== "") {
    sp.set("last_n_sessions", String(params.lastNSessions));
  }
  const q = sp.toString();
  const base = `/api/teams/${encodeURIComponent(String(teamId))}/attendance/trends/`;
  return authenticatedGet(q ? `${base}?${q}` : base);
}

/** EP-27: compact team roll-up (coach/director). */
export async function fetchTeamAttendanceSummary(teamId, params = {}) {
  const sp = new URLSearchParams();
  if (params.startDate) {
    sp.set("start_date", params.startDate);
  }
  if (params.endDate) {
    sp.set("end_date", params.endDate);
  }
  if (params.lastNSessions != null && params.lastNSessions !== "") {
    sp.set("last_n_sessions", String(params.lastNSessions));
  }
  const q = sp.toString();
  const base = `/api/teams/${encodeURIComponent(String(teamId))}/attendance/summary/`;
  return authenticatedGet(q ? `${base}?${q}` : base);
}

/** EP-27: per-player summary for a team (self, parent of player, or coach/director). */
export async function fetchPlayerTeamAttendanceSummary(teamId, playerId, params = {}) {
  const sp = new URLSearchParams();
  if (params.startDate) {
    sp.set("start_date", params.startDate);
  }
  if (params.endDate) {
    sp.set("end_date", params.endDate);
  }
  if (params.lastNSessions != null && params.lastNSessions !== "") {
    sp.set("last_n_sessions", String(params.lastNSessions));
  }
  const q = sp.toString();
  const base = `/api/teams/${encodeURIComponent(String(teamId))}/players/${encodeURIComponent(String(playerId))}/attendance/summary/`;
  return authenticatedGet(q ? `${base}?${q}` : base);
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

/** Attendance: only unconfirmed roster players; parents skipped for past/cancelled (cancelled rejected on server). */
export async function remindUnconfirmedTrainingSession(sessionId, audience) {
  return authenticatedJson(`/api/training-sessions/${sessionId}/remind-unconfirmed/`, "POST", {
    audience,
  });
}

export async function fetchDirectorPendingUsers() {
  return authenticatedGet("/api/directors/pending-users/");
}

export async function fetchDirectorUserDirectory(limit, options = {}) {
  const params = new URLSearchParams();
  if (limit) {
    params.set("limit", String(limit));
  }
  if (options.teamId != null && options.teamId !== "" && options.teamId !== "__all__") {
    params.set("team_id", String(options.teamId));
  }
  const q = params.toString() ? `?${params.toString()}` : "";
  return authenticatedGet(`/api/directors/users/directory/${q}`);
}

export async function directorSetUserAccountRole(userId, body) {
  return authenticatedJson(`/api/directors/users/${userId}/account-role/`, "POST", body);
}

export async function directorRemovePlayerFromTeam(userId, body) {
  return authenticatedJson(`/api/directors/users/${userId}/remove-player/`, "POST", body || {});
}

export async function directorVerifyUser(userId, body) {
  return authenticatedJson(`/api/directors/users/${userId}/verify/`, "POST", body || {});
}

export async function directorRejectUser(userId) {
  return authenticatedJson(`/api/directors/users/${userId}/reject/`, "POST", {});
}

export async function fetchDirectorPaymentOverview(clubId) {
  return authenticatedGet(`/api/clubs/${clubId}/director/payments/overview/`);
}

export async function fetchDirectorPaymentLookupPlayer(clubId, playerId) {
  const q = `?player_id=${encodeURIComponent(String(playerId))}`;
  return authenticatedGet(`/api/clubs/${clubId}/director/payments/lookup-player/${q}`);
}

export async function downloadDirectorReceiptPdf(clubId, recordId) {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  const path = `/api/clubs/${clubId}/director/payments/records/${recordId}/receipt.pdf/`;
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token || ""}` },
    });
  } catch {
    throw new Error("Cannot reach backend. Make sure Django is running on port 8000.");
  }
  if (!response.ok) {
    const ct = response.headers.get("Content-Type") || "";
    let msg = "Could not download receipt PDF.";
    if (ct.includes("application/json")) {
      try {
        const payload = await response.json();
        msg = normalizeErrors(payload, msg);
      } catch {
        /* ignore */
      }
    }
    throw new Error(msg);
  }
  let blob = await response.blob();
  if (!blob.type || blob.type === "application/octet-stream") {
    blob = new Blob([blob], { type: "application/pdf" });
  }
  return blob;
}

export async function fetchDirectorPaymentRows(clubId, status) {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return authenticatedGet(`/api/clubs/${clubId}/director/payments/rows/${q}`);
}

export async function fetchDirectorPaymentLogs(clubId, limit) {
  const q = limit ? `?limit=${encodeURIComponent(String(limit))}` : "";
  return authenticatedGet(`/api/clubs/${clubId}/director/payments/logs/${q}`);
}

export async function directorCreateFeeRecord(clubId, body) {
  return authenticatedJson(`/api/clubs/${clubId}/director/payments/records/`, "POST", body);
}

export async function directorRecordFeePayment(clubId, recordId, body) {
  return authenticatedJson(
    `/api/clubs/${clubId}/director/payments/records/${recordId}/payment/`,
    "POST",
    body,
  );
}

export async function directorSendPaymentReminder(clubId, recordId) {
  return authenticatedJson(
    `/api/clubs/${clubId}/director/payments/records/${recordId}/reminder/`,
    "POST",
    {},
  );
}

export async function directorSendReceipt(clubId, recordId) {
  return authenticatedJson(
    `/api/clubs/${clubId}/director/payments/records/${recordId}/receipt/`,
    "POST",
    {},
  );
}

export async function fetchDirectorRenewalsDueToday(clubId) {
  return authenticatedGet(`/api/clubs/${clubId}/director/payments/renewals-today/`);
}

export async function directorMaterializeMonthlyFees(clubId, body) {
  return authenticatedJson(
    `/api/clubs/${clubId}/director/payments/materialize-month/`,
    "POST",
    body || {},
  );
}

export async function directorBulkEmailRenewalsDueToday(clubId) {
  return authenticatedJson(
    `/api/clubs/${clubId}/director/payments/bulk-email-renewals-today/`,
    "POST",
    {},
  );
}

export async function directorEmailOutstandingNoticeForFamily(clubId, playerId) {
  return authenticatedJson(`/api/clubs/${clubId}/director/payments/outstanding-notice/`, "POST", {
    player_id: playerId,
  });
}

export async function directorEmailRenewalsDueTodayForFamily(clubId, playerId) {
  return authenticatedJson(`/api/clubs/${clubId}/director/payments/renewals-today/email-player/`, "POST", {
    player_id: playerId,
  });
}

export async function directorCreateTeam(clubId, body) {
  return authenticatedJson(`/api/clubs/${clubId}/teams/create/`, "POST", body);
}

export async function directorDeleteTeam(teamId) {
  return authenticatedDelete(`/api/teams/${teamId}/delete/`);
}

export async function directorDeleteClub(clubId) {
  return authenticatedDelete(`/api/clubs/${clubId}/delete/`);
}

export async function fetchTeamMembers(teamId) {
  return authenticatedGet(`/api/teams/${teamId}/members/`);
}

export async function fetchCoachTeamDashboard(teamId) {
  return authenticatedGet(`/api/teams/${teamId}/coach-dashboard/`);
}

export async function directorAddTeamMember(teamId, body) {
  return authenticatedJson(`/api/teams/${teamId}/members/add/`, "POST", body);
}

export async function directorRemoveTeamMember(teamId, userId) {
  return authenticatedJson(`/api/teams/${teamId}/members/${userId}/remove/`, "DELETE", {});
}

export async function inviteTeamMember(teamId, body) {
  return authenticatedJson(`/api/teams/${teamId}/invitations/`, "POST", body);
}

export async function fetchInvitationByCode(code) {
  return authenticatedGet(`/api/invitations/${encodeURIComponent(code)}/`);
}

export async function respondToInvitation(code, action) {
  return authenticatedJson(`/api/invitations/${encodeURIComponent(code)}/respond/`, "POST", { action });
}

export async function fetchTeamPlayerPayments(teamId) {
  return authenticatedGet(`/api/teams/${teamId}/payments/`);
}

export async function fetchPlayerTeamPayments(teamId) {
  return authenticatedGet(`/api/teams/${teamId}/player-payments/`);
}

export async function fetchMyFees() {
  return authenticatedGet(`/api/my-fees/`);
}

export async function recordSelfPayment(recordId, body) {
  return authenticatedJson(`/api/my-fees/${recordId}/pay/`, "POST", body);
}

export async function fetchPaymentSchedules(clubId) {
  return authenticatedGet(`/api/clubs/${clubId}/payment-schedules/`);
}

export async function createPaymentSchedule(clubId, body) {
  return authenticatedJson(`/api/clubs/${clubId}/payment-schedules/create/`, "POST", body);
}

export async function deactivatePaymentSchedule(clubId, scheduleId) {
  return authenticatedJson(
    `/api/clubs/${clubId}/payment-schedules/${scheduleId}/deactivate/`,
    "POST",
    {},
  );
}

export async function deletePaymentSchedule(clubId, scheduleId) {
  return authenticatedJson(
    `/api/clubs/${clubId}/payment-schedules/${scheduleId}/delete/`,
    "POST",
    {},
  );
}

export async function requestPlayerParentInvitation(email) {
  return authenticatedJson("/api/me/player-parent-invitations/", "POST", {
    email,
  });
}

export async function updatePlayerParentAccess(playerId, body) {
  return authenticatedJson(`/api/players/${playerId}/parent-management/`, "PATCH", body);
}

export async function fetchDirectorPendingParentLinks() {
  return authenticatedGet("/api/directors/parent-link-requests/");
}

export async function directorResolveParentLink(relationId, action) {
  return authenticatedJson(`/api/directors/parent-link-requests/${relationId}/`, "POST", { action });
}

export async function fetchPendingPlayerParentInvitations() {
  return authenticatedGet("/api/managers/player-parent-invitations/");
}

export async function resolvePlayerParentInvitation(invitationId, action) {
  return authenticatedJson(`/api/managers/player-parent-invitations/${invitationId}/`, "POST", { action });
}

export async function removeParentAssociation(playerId, parentId) {
  return authenticatedJson(`/api/players/${playerId}/parents/${parentId}/`, "DELETE", {});
}
