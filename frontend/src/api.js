const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");

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

export async function loginWithPassword({ email, password }) {
  return request("/api/auth/login/", { email, password });
}

export async function registerUser({ firstName, lastName, email, password }) {
  return request("/api/register/", {
    first_name: firstName,
    last_name: lastName,
    email,
    password,
  });
}
