import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import DashboardPage, { userHasAnyClubAffiliation } from "./DashboardPage";

const navigate = vi.fn();

vi.mock("../navigation", () => ({
  navigate: (path) => navigate(path),
}));

vi.mock("../components/ClubWorkspaceLayout", () => ({
  default: function MockClubWorkspaceLayout({ children }) {
    return <div data-testid="club-workspace-layout">{children}</div>;
  },
}));

function baseMe(overrides = {}) {
  return {
    user: { id: 1, first_name: "Test", last_name: "User", role: "director" },
    account_profile: { roles: [] },
    is_director_or_staff: false,
    viewer_is_staff: false,
    owned_clubs: [],
    director_teams: [],
    coached_teams: [],
    player_teams: [],
    children: [],
    pending_parent_links: [],
    ...overrides,
  };
}

const overviewPayload = {
  club: { id: 7, name: "My Club" },
  kpis: {
    registration_player_count: 0,
    monthly_revenue: "",
    monthly_revenue_currency: "USD",
    attendance_rate: "",
    outstanding_payer_count: 0,
  },
  payments_overview: [],
  roles_permission_matrix: [],
  club_summary: {},
  attendance_trend_30d: [],
};

describe("userHasAnyClubAffiliation", () => {
  it("is false for empty profile", () => {
    expect(userHasAnyClubAffiliation(null)).toBe(false);
    expect(userHasAnyClubAffiliation(baseMe())).toBe(false);
  });

  it("is true when user owns a club", () => {
    expect(
      userHasAnyClubAffiliation(
        baseMe({ owned_clubs: [{ id: 1, name: "C" }] }),
      ),
    ).toBe(true);
  });

  it("is true when user has a player team", () => {
    expect(
      userHasAnyClubAffiliation(
        baseMe({ player_teams: [{ id: 1, name: "T" }] }),
      ),
    ).toBe(true);
  });

  it("is true when a linked child has teams", () => {
    expect(
      userHasAnyClubAffiliation(
        baseMe({
          children: [{ user: { id: 2 }, teams: [{ id: 1, name: "Juniors" }] }],
        }),
      ),
    ).toBe(true);
  });
});

describe("DashboardPage create-club flow", () => {
  beforeEach(() => {
    localStorage.setItem("netup.auth.token", "test-token");
    vi.spyOn(api, "fetchCurrentUser");
    vi.spyOn(api, "fetchDirectorPaymentOverview");
    vi.spyOn(api, "createClub");
  });

  afterEach(() => {
    cleanup();
    localStorage.clear();
    sessionStorage.clear();
    navigate.mockClear();
    vi.restoreAllMocks();
  });

  it("shows onboarding when the user has no club or team affiliations", async () => {
    vi.mocked(api.fetchCurrentUser).mockResolvedValue(baseMe());
    vi.mocked(api.fetchDirectorPaymentOverview).mockResolvedValue(overviewPayload);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /no club yet/i })).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /^create a club$/i })).toBeInTheDocument();
    expect(screen.queryByText(/registration/i)).not.toBeInTheDocument();
  });

  it("does not show onboarding when the user has a player team", async () => {
    vi.mocked(api.fetchCurrentUser).mockResolvedValue(
      baseMe({ player_teams: [{ id: 1, name: "Team A", club_id: 1, club_name: "X" }] }),
    );
    vi.mocked(api.fetchDirectorPaymentOverview).mockResolvedValue(overviewPayload);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: /no club yet/i })).not.toBeInTheDocument();
    });
  });

  it("always shows a create-club card at the bottom of the director dashboard", async () => {
    vi.mocked(api.fetchCurrentUser).mockResolvedValue(
      baseMe({
        is_director_or_staff: true,
        owned_clubs: [{ id: 7, name: "My Club" }],
      }),
    );
    vi.mocked(api.fetchDirectorPaymentOverview).mockResolvedValue(overviewPayload);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "My Club" })).toBeInTheDocument();
    });

    expect(screen.getByRole("heading", { name: /create another club/i })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^create a club$/i }).length).toBeGreaterThan(0);
  });

  it("creates a club, refreshes profile, and shows the director hero for the new club", async () => {
    const user = userEvent.setup();
    let clubCreated = false;
    vi.mocked(api.fetchCurrentUser).mockImplementation(() => {
      if (!clubCreated) {
        return Promise.resolve(baseMe());
      }
      return Promise.resolve(
        baseMe({
          is_director_or_staff: true,
          owned_clubs: [{ id: 7, name: "My Club" }],
        }),
      );
    });
    vi.mocked(api.fetchDirectorPaymentOverview).mockResolvedValue(overviewPayload);
    vi.mocked(api.createClub).mockImplementation(async () => {
      clubCreated = true;
      return {
        message: "Club created successfully.",
        club: { id: 7, name: "My Club" },
        membership: { role: "club_director", user_id: 1 },
      };
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /no club yet/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /^create a club$/i }));
    expect(screen.getByRole("heading", { name: /create a club/i })).toBeInTheDocument();

    await user.type(screen.getByLabelText(/club name/i), "My Club");
    await user.type(screen.getByLabelText(/short name/i), "MC");
    await user.type(screen.getByLabelText(/contact email/i), "hello@myclub.com");
    await user.type(screen.getByLabelText(/contact phone/i), "+1 555 555 5555");
    await user.type(screen.getByLabelText(/country/i), "USA");
    await user.type(screen.getByLabelText(/^city/i), "Boston");
    await user.type(screen.getByLabelText(/address/i), "123 Main Street");
    await user.type(screen.getByLabelText(/founded year/i), "2020");
    await user.click(screen.getByRole("button", { name: /create club$/i }));

    await waitFor(() => {
      expect(api.createClub).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "My Club",
          short_name: "MC",
          contact_email: "hello@myclub.com",
          contact_phone: "+1 555 555 5555",
          country: "USA",
          city: "Boston",
          address: "123 Main Street",
          founded_year: 2020,
        }),
      );
    });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "My Club" })).toBeInTheDocument();
    });
    expect(screen.queryByRole("heading", { name: /no club yet/i })).not.toBeInTheDocument();
    expect(sessionStorage.getItem("netup.director.payment.club_id")).toBe("7");
  });
});
