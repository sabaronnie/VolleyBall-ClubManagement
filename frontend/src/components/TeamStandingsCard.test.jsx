import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import TeamStandingsCard from "./TeamStandingsCard";

describe("TeamStandingsCard", () => {
  const standingsPayload = {
    team: { id: 11, name: "Falcons" },
    standings: {
      team_id: 11,
      team_name: "Falcons",
      club_name: "My Club",
      matches_played: 2,
      wins: 1,
      losses: 1,
      points_for: 43,
      points_against: 45,
      point_differential: -2,
      record_label: "1-1",
      note: "Completed matches only.",
    },
  };

  beforeEach(() => {
    vi.spyOn(api, "fetchTeamStandings").mockResolvedValue(standingsPayload);
    vi.spyOn(api, "downloadTeamStandingsPdf").mockResolvedValue(
      new Blob(["pdf"], { type: "application/pdf" }),
    );
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:standings"),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("shows the export action only when export is enabled", async () => {
    render(<TeamStandingsCard activeTeamId="11" />);

    await waitFor(() => {
      expect(screen.getByText("1-1")).toBeInTheDocument();
    });
    expect(screen.getByText(/wins - losses/i)).toBeInTheDocument();
    expect(screen.queryByText(/^wins$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^losses$/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /export pdf/i })).not.toBeInTheDocument();
  });

  it("downloads a standings PDF for coach and director contexts", async () => {
    const user = userEvent.setup();
    render(<TeamStandingsCard activeTeamId="11" canExport />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /export pdf/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /export pdf/i }));

    await waitFor(() => {
      expect(api.downloadTeamStandingsPdf).toHaveBeenCalledWith("11");
    });
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/standings pdf downloaded/i)).toBeInTheDocument();
  });
});
