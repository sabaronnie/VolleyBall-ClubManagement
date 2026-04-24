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
    vi.spyOn(api, "fetchCoachTeamDashboard");
    vi.spyOn(api, "fetchTeamStandings");
    vi.spyOn(api, "createClub");
    vi.mocked(api.fetchTeamStandings).mockResolvedValue({
      team: { id: 11, name: "Falcons" },
      standings: {
        team_id: 11,
        team_name: "Falcons",
        club_name: "My Club",
        matches_played: 0,
        wins: 0,
        losses: 0,
        points_for: 0,
        points_against: 0,
        point_differential: 0,
        record_label: "0-0",
        note: "Completed matches only.",
      },
    });
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

  it("renders team-scoped statistics cards for the coach workspace", async () => {
    vi.mocked(api.fetchCurrentUser).mockResolvedValue(
      baseMe({
        user: { id: 9, first_name: "Coach", last_name: "User", role: "coach" },
        coached_teams: [
          {
            id: 11,
            name: "Falcons",
            club_id: 7,
            club_name: "My Club",
            can_manage_training: true,
          },
        ],
      }),
    );
    vi.mocked(api.fetchDirectorPaymentOverview).mockResolvedValue(overviewPayload);
    vi.mocked(api.fetchCoachTeamDashboard).mockResolvedValue({
      team: { id: 11, name: "Falcons" },
      kpis: {
        players_today: 0,
        practice_time_display: null,
        practice_session_id: null,
        next_match: null,
        feedback_due: 0,
      },
      attendance_vs_performance: { labels: [], attendance: [], average_performance: [], categories: [] },
      player_stats: [],
      recent_feedback: [],
      workspace_overview: {
        kpis: {
          registration_player_count: 12,
          monthly_revenue: "480.00",
          monthly_revenue_currency: "USD",
          attendance_rate: 91.5,
          outstanding_payer_count: 3,
        },
        attendance_trend_30d: {
          calculation_summary: "summary",
          points: Array.from({ length: 30 }, (_, i) => ({
            date: `2026-04-${String(i + 1).padStart(2, "0")}`,
            rate_percent: i === 0 ? 90 : null,
            closed_slots: i === 0 ? 8 : 0,
            attended_slots: i === 0 ? 7 : 0,
          })),
        },
        payments_overview: [
          {
            player_id: 22,
            family_label: "Ava Player",
            total_paid: "60.00",
            total_remaining: "30.00",
            currency: "USD",
            status: "pending",
          },
        ],
        team_summary: {
          average_attendance_percent: 91.5,
          best_participating_team: { team_id: 11, team_name: "Falcons", rate_percent: 91.5 },
          low_participation: null,
          monthly_profit: "480.00",
          monthly_profit_currency: "USD",
        },
      },
    });

    render(<DashboardPage activeTeamId="11" />);

    await waitFor(() => {
      expect(api.fetchCoachTeamDashboard).toHaveBeenCalledWith(11);
    });
    expect(screen.getByRole("heading", { name: "Falcons" })).toBeInTheDocument();
    expect(screen.getByText("Registration")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Team Summary" })).toBeInTheDocument();
    expect(screen.getByText("Current Team")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Payments Overview" })).toBeInTheDocument();
  });
});
