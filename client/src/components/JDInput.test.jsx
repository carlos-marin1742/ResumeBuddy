import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import JDInput from "./JDInput";


const validDescription = Array.from({ length: 20 }, (_, index) => `word${index}`).join(" ");


describe("JDInput", () => {
  it("keeps submission disabled until the description reaches 20 words", async () => {
    const user = userEvent.setup();
    render(<JDInput onSubmit={vi.fn()} onBack={vi.fn()} loading={false} />);

    const submit = screen.getByRole("button", { name: /extract keywords/i });
    expect(submit).toBeDisabled();

    await user.type(
      screen.getByLabelText("Job Description"),
      Array.from({ length: 19 }, (_, index) => `word${index}`).join(" "),
    );
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText("Job Description"), " final");
    expect(submit).toBeEnabled();
  });

  it("submits the current description, company, and title", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <JDInput
        onSubmit={onSubmit}
        onBack={vi.fn()}
        loading={false}
        initialCompany="Example Co"
        initialJobTitle="Engineer"
        initialJD={validDescription}
      />,
    );

    await user.click(screen.getByRole("button", { name: /extract keywords/i }));

    expect(onSubmit).toHaveBeenCalledWith(
      validDescription,
      "Example Co",
      "Engineer",
    );
  });

  it("disables all controls while loading", () => {
    render(
      <JDInput
        onSubmit={vi.fn()}
        onBack={vi.fn()}
        loading
        initialJD={validDescription}
      />,
    );

    expect(screen.getByLabelText("Company")).toBeDisabled();
    expect(screen.getByLabelText("Job Title")).toBeDisabled();
    expect(screen.getByLabelText("Job Description")).toBeDisabled();
    expect(screen.getByRole("button", { name: /extracting keywords/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /back/i })).toBeDisabled();
  });

  it("rejects descriptions over the 20,000 character limit", () => {
    render(
      <JDInput
        onSubmit={vi.fn()}
        onBack={vi.fn()}
        loading={false}
        initialJD={`${"word ".repeat(4000)}x`}
      />,
    );

    expect(screen.getByRole("button", { name: /extract keywords/i })).toBeDisabled();
    expect(screen.getByText(/20,001 \/ 20,000 chars/)).toHaveClass("warn");
  });
});
