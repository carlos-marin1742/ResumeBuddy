import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import KeywordSelector from "./KeywordSelector";


const extractResult = {
  role_level: "Senior",
  gaps: ["Docker"],
  keywords: [
    {
      keyword: "Python",
      category: "hard_skill",
      ats_weight: 10,
      present_in_resume: true,
    },
    {
      keyword: "Docker",
      category: "hard_skill",
      ats_weight: 8,
      present_in_resume: false,
    },
    {
      keyword: "Leadership",
      category: "soft_skill",
      ats_weight: 4,
      present_in_resume: false,
    },
  ],
};


function renderSelector(overrides = {}) {
  const props = {
    extractResult,
    selected: [],
    onChange: vi.fn(),
    onBack: vi.fn(),
    onGenerate: vi.fn(),
    loading: false,
    ...overrides,
  };
  render(<KeywordSelector {...props} />);
  return props;
}


describe("KeywordSelector", () => {
  it("adds an unselected keyword without dropping existing selections", async () => {
    const user = userEvent.setup();
    const props = renderSelector({ selected: ["Python"] });

    await user.click(screen.getByRole("button", { name: /docker8/i }));

    expect(props.onChange).toHaveBeenCalledWith(["Python", "Docker"]);
  });

  it("selects only keywords missing from the resume", async () => {
    const user = userEvent.setup();
    const props = renderSelector();

    await user.click(screen.getByRole("button", { name: "Gaps only" }));

    expect(props.onChange).toHaveBeenCalledWith(["Docker", "Leadership"]);
  });

  it("supports select-all and clear actions", async () => {
    const user = userEvent.setup();
    const props = renderSelector({ selected: ["Python"] });

    await user.click(screen.getByRole("button", { name: "All" }));
    expect(props.onChange).toHaveBeenLastCalledWith([
      "Python",
      "Docker",
      "Leadership",
    ]);

    await user.click(screen.getByRole("button", { name: "Clear" }));
    expect(props.onChange).toHaveBeenLastCalledWith([]);
  });

  it("requires a selection before generation and locks actions while loading", () => {
    const { rerender } = render(
      <KeywordSelector
        extractResult={extractResult}
        selected={[]}
        onChange={vi.fn()}
        onBack={vi.fn()}
        onGenerate={vi.fn()}
        loading={false}
      />,
    );

    expect(screen.getByRole("button", { name: /generate resume/i })).toBeDisabled();

    rerender(
      <KeywordSelector
        extractResult={extractResult}
        selected={["Python"]}
        onChange={vi.fn()}
        onBack={vi.fn()}
        onGenerate={vi.fn()}
        loading
      />,
    );

    expect(screen.getByRole("button", { name: /generating resume/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /back/i })).toBeDisabled();
  });
});
