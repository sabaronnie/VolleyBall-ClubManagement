import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { fetchCurrentUser } from "./api";

describe("authenticated API requests", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    window.history.pushState({}, "", "/dashboard");
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("logs the user out when the backend reports an expired token", async () => {
    localStorage.setItem("netup.auth.token", "expired-token");
    localStorage.setItem("netup.auth.user", JSON.stringify({ email: "player@example.com" }));
    localStorage.setItem("netup.active.team", "12");

    globalThis.fetch.mockResolvedValue(
      new Response(JSON.stringify({ errors: { token: "Token has expired." } }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(fetchCurrentUser()).rejects.toThrow("Token has expired.");

    expect(localStorage.getItem("netup.auth.token")).toBeNull();
    expect(localStorage.getItem("netup.auth.user")).toBeNull();
    expect(localStorage.getItem("netup.active.team")).toBeNull();
    expect(sessionStorage.getItem("netup.auth.expired")).toBe("1");
    expect(window.location.pathname).toBe("/login");
  });

  it("logs the user out when the backend returns forbidden", async () => {
    localStorage.setItem("netup.auth.token", "valid-but-rejected-token");
    localStorage.setItem("netup.auth.user", JSON.stringify({ email: "player@example.com" }));
    localStorage.setItem("netup.active.team", "12");

    globalThis.fetch.mockResolvedValue(
      new Response(JSON.stringify({ errors: { permission: "Forbidden." } }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(fetchCurrentUser()).rejects.toThrow("Forbidden.");

    expect(localStorage.getItem("netup.auth.token")).toBeNull();
    expect(localStorage.getItem("netup.auth.user")).toBeNull();
    expect(localStorage.getItem("netup.active.team")).toBeNull();
    expect(sessionStorage.getItem("netup.auth.expired")).toBe("1");
    expect(window.location.pathname).toBe("/login");
  });
});
