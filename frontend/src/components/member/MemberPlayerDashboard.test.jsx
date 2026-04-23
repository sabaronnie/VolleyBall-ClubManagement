import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api";
import MemberPlayerDashboard from "./MemberPlayerDashboard";

vi.mock("../../navigation", () => ({
  navigate: vi.fn(),
}));

vi.mock("../../pages/MyFeesPage", () => ({
  default: function MockMyFeesPage() {
    return <div data-testid="embedded-fees">Embedded fees</div>;
  },
}));

const baseDashboardPayload = {
  viewer: {
    id: 50,
    email: "parent@example.com",
    first_name: "Pat",
    last_name: "Parent",
  },
  available_children: [
    {
      id: 7,
      email: "max@example.com",
      first_name: "Max",
      last_name: "Demo",
    },
  ],
  focus_player: {
    id: 7,
    email: "max@example.com",
    first_name: "Max",
    last_name: "Demo",
  },
  profile: {
    display_name: "Max Demo",
    team: {
      id: 11,
      name: "U16 Blue",
      club_id: 2,
      club_name: "NetUp",
    },
    coach_display: "Casey Coach",
  },
  payment: {
    currency: "USD",
    amount_due: 45,
    overall_status: "pending",
    open_item_count: 1,
    fee_lines: [],
  },
  progress: {
    team_id: 11,
    weeks: [],
    summary: {
      attack: null,
      defense: null,
      serve: null,
    },
    has_weekly_metrics: false,
  },
  club_summary: null,
  quick_actions: {
    confirm_attendance_path: "/parent/attendance",
    confirm_attendance_mode: "parent",
  },
  notifications: {
    unread_count: 0,
  },
  parent_access: {
    can_manage: false,
    max_parents: 2,
    linked_parents: [],
    pending_requests: [],
    minor_locked: true,
  },
  parent_permissions: {
    can_manage: true,
    policy: {
      is_parent_managed: true,
      can_self_confirm_attendance: true,
      can_self_make_payments: false,
      can_self_update_emergency_contact: false,
    },
  },
};

describe("MemberPlayerDashboard parent view", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the linked player name and updates parent permissions", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "fetchMemberDashboard").mockResolvedValue(baseDashboardPayload);
    vi.spyOn(api, "removeParentAssociation").mockResolvedValue({});
    vi.spyOn(api, "requestPlayerParentInvitation").mockResolvedValue({});
    vi.spyOn(api, "updatePlayerParentAccess").mockResolvedValue({
      message: "Parent-managed access updated successfully.",
      policy: {
        is_parent_managed: true,
        can_self_confirm_attendance: false,
        can_self_make_payments: false,
        can_self_update_emergency_contact: false,
      },
    });

    render(<MemberPlayerDashboard />);

    await waitFor(() => {
      expect(screen.getAllByText("Max Demo").length).toBeGreaterThan(0);
    });
    expect(screen.getByText("Parent dashboard")).toBeInTheDocument();
    expect(screen.getByText("Viewing U16 Blue")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /permissions/i }));

    expect(screen.getByText("Attendance confirmation")).toBeInTheDocument();
    expect(screen.queryByText("Absence reasons")).not.toBeInTheDocument();
    expect(screen.queryByText("Schedule confirmations")).not.toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Deny" })[0]);

    await waitFor(() => {
      expect(api.updatePlayerParentAccess).toHaveBeenCalledWith(7, {
        is_parent_managed: true,
        can_self_confirm_attendance: false,
      });
    });

    expect(screen.getByText(/updated successfully/i)).toBeInTheDocument();
  });

  it("shows a disclaimer instead of editable permissions for adult linked players", async () => {
    const user = userEvent.setup();
    const adultDashboardPayload = {
      ...baseDashboardPayload,
      focus_player: {
        ...baseDashboardPayload.focus_player,
        date_of_birth: "2000-03-10",
      },
      profile: {
        ...baseDashboardPayload.profile,
        age_years: 26,
      },
      parent_access: {
        ...baseDashboardPayload.parent_access,
        minor_locked: false,
      },
      parent_permissions: {
        can_manage: false,
        policy: null,
        reason: "adult_player",
        message:
          "This player is an adult now, so parent-managed permissions no longer apply and can no longer be modified.",
      },
    };
    vi.spyOn(api, "fetchMemberDashboard").mockResolvedValue(adultDashboardPayload);
    vi.spyOn(api, "removeParentAssociation").mockResolvedValue({});
    vi.spyOn(api, "requestPlayerParentInvitation").mockResolvedValue({});
    vi.spyOn(api, "updatePlayerParentAccess").mockResolvedValue({});

    render(<MemberPlayerDashboard />);

    await waitFor(() => {
      expect(screen.getAllByText("Max Demo").length).toBeGreaterThan(0);
    });

    await user.click(screen.getByRole("button", { name: /permissions/i }));

    expect(screen.getByText("Permissions are no longer editable.")).toBeInTheDocument();
    expect(screen.getAllByText(/adult now/i).length).toBeGreaterThan(0);
    expect(screen.queryByText("Attendance confirmation")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Deny" })).not.toBeInTheDocument();
    expect(api.updatePlayerParentAccess).not.toHaveBeenCalled();
  });
});
