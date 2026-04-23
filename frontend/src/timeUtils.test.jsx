import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { TimeSelect } from "./timeUtils";

function TimeSelectHarness({ initialValue = "18:30" }) {
  const [value, setValue] = React.useState(initialValue);
  return (
    <>
      <TimeSelect value={value} onChange={setValue} />
      <output aria-label="saved time">{value}</output>
    </>
  );
}

describe("TimeSelect", () => {
  afterEach(cleanup);

  it("uses typed 12-hour fields with a custom meridiem dropdown", async () => {
    const user = userEvent.setup();
    render(<TimeSelectHarness />);

    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.getByLabelText(/hour/i)).toHaveValue("6");
    expect(screen.getByLabelText(/minutes/i)).toHaveValue("30");
    expect(screen.getByRole("button", { name: "PM" })).toHaveAttribute("aria-haspopup", "listbox");

    await user.click(screen.getByRole("button", { name: "PM" }));
    await user.click(screen.getByRole("option", { name: "AM" }));
    expect(screen.getByLabelText(/saved time/i)).toHaveTextContent("06:30");

    await user.clear(screen.getByLabelText(/hour/i));
    await user.type(screen.getByLabelText(/hour/i), "12");
    expect(screen.getByLabelText(/saved time/i)).toHaveTextContent("00:30");

    await user.click(screen.getByRole("button", { name: "AM" }));
    await user.click(screen.getByRole("option", { name: "PM" }));
    expect(screen.getByLabelText(/saved time/i)).toHaveTextContent("12:30");
  });
});
