import { afterEach, describe, expect, it, vi } from "vitest";
import { CONTACT_PATH, goToContactPage, navigate } from "./navigation";

describe("navigation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState({}, "", "/");
  });

  it("goToContactPage navigates to contact path", () => {
    const pushState = vi.spyOn(window.history, "pushState");
    const dispatch = vi.spyOn(window, "dispatchEvent");
    goToContactPage();
    expect(pushState).toHaveBeenCalledWith({}, "", CONTACT_PATH);
    expect(dispatch.mock.calls.some((c) => c[0] instanceof PopStateEvent)).toBe(true);
  });

  it("navigate pushes path and dispatches popstate", () => {
    const pushState = vi.spyOn(window.history, "pushState");
    navigate("/login");
    expect(pushState).toHaveBeenCalledWith({}, "", "/login");
  });
});
