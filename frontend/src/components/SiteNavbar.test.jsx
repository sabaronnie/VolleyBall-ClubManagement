import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import SiteNavbar, { buildWorkspaceTabs } from "./SiteNavbar";

const goToContactPage = vi.fn();
const navigate = vi.fn();

vi.mock("../navigation", () => ({
  CONTACT_PATH: "/contact",
  goToContactPage: () => goToContactPage(),
  navigate: (path) => navigate(path),
}));

describe("SiteNavbar", () => {
  afterEach(() => {
    cleanup();
    goToContactPage.mockClear();
    navigate.mockClear();
  });

  it("guest mode shows Contact Us and calls goToContactPage", async () => {
    const user = userEvent.setup();
    render(<SiteNavbar mode="guest" />);
    const contact = screen.getByRole("button", { name: /contact us/i });
    expect(contact).toBeTruthy();
    await user.click(contact);
    expect(goToContactPage).toHaveBeenCalledTimes(1);
  });

  it("workspace mode shows Contact Us and calls goToContactPage", async () => {
    const user = userEvent.setup();
    render(
      <SiteNavbar
        mode="workspace"
        activeTab="dashboard"
        tabs={[{ id: "dashboard", label: "Dashboard", path: "/dashboard" }]}
        actions={<span data-testid="extra">x</span>}
      />,
    );
    const buttons = screen.getAllByRole("button", { name: /contact us/i });
    expect(buttons.length).toBe(1);
    await user.click(buttons[0]);
    expect(goToContactPage).toHaveBeenCalledTimes(1);
  });

  it("labels the coach attendance tab as Events", () => {
    expect(buildWorkspaceTabs({ showCoachAttendanceTab: true })).toContainEqual({
      id: "coach-attendance",
      label: "Events",
      path: "/coach/attendance",
    });
  });
});
