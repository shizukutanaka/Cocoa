import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StarRating } from "./StarRating";

/**
 * Queried through ARIA roles rather than DOM structure, so these assertions
 * double as a guard on the component's accessibility: a screen-reader user
 * relies on exactly the roles and labels asserted here.
 */
describe("StarRating", () => {
  it("exposes a labelled radiogroup of five stars when interactive", () => {
    render(<StarRating value={3} onChange={() => {}} />);
    expect(screen.getByRole("radiogroup", { name: "評価を選択" })).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(5);
  });

  it("marks the selected star as checked and the others as unchecked", () => {
    render(<StarRating value={3} onChange={() => {}} />);
    const checked = screen.getAllByRole("radio").map((el) => el.getAttribute("aria-checked"));
    expect(checked).toEqual(["false", "false", "true", "false", "false"]);
  });

  it("reports the chosen star count when a user picks one", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<StarRating value={0} onChange={onChange} />);

    await user.click(screen.getAllByRole("radio")[4]);
    expect(onChange).toHaveBeenCalledWith(5);
  });

  it("is a non-interactive rating with a readable label when onChange is omitted", () => {
    render(<StarRating value={4} />);
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
    // Read-only ratings still announce their value.
    expect(screen.getByLabelText("評価 4 / 5")).toBeInTheDocument();
  });
});
