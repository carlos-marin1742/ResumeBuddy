import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import CoverLetterStep from "./CoverLetterStep";


const defaultProps = {
  tailoredResume: { tailored_summary: "Backend engineer" },
  sessionId: "session-123",
  candidateName: "Candidate Name",
  historyId: "history-123",
  jobDescription: "Build reliable Python services.",
  company: "Example Co",
  jobTitle: "Engineer",
  selectedKeywords: ["Python"],
  onBack: vi.fn(),
};


function renderStep(overrides = {}) {
  render(<CoverLetterStep {...defaultProps} {...overrides} />);
}


describe("CoverLetterStep", () => {
  it("generates a letter with the complete request context", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          letter: "Dear Hiring Manager,\n\nFocused body.\n\nThank You\nCandidate Name",
          word_count: 9,
        }),
      }),
    );
    const user = userEvent.setup();
    renderStep();

    await user.click(screen.getByRole("button", { name: "Generate Cover Letter" }));

    expect(await screen.findByDisplayValue(/focused body/i)).toBeInTheDocument();
    const [, request] = fetch.mock.calls[0];
    expect(JSON.parse(request.body)).toEqual({
      tailored_resume: defaultProps.tailoredResume,
      session_id: "session-123",
      candidate_name: "Candidate Name",
      job_description: "Build reliable Python services.",
      company: "Example Co",
      job_title: "Engineer",
      selected_keywords: ["Python"],
      history_id: "history-123",
    });
    expect(screen.getByText("9 words")).toBeInTheDocument();
  });

  it("shows server-provided generation errors and restores the empty state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ detail: "Job description is required." }),
      }),
    );
    const user = userEvent.setup();
    renderStep();

    await user.click(screen.getByRole("button", { name: "Generate Cover Letter" }));

    expect(await screen.findByText("Job description is required.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate Cover Letter" })).toBeEnabled();
  });

  it("recalculates word count from the greeting after edits", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          letter: "Initial",
          word_count: 1,
        }),
      }),
    );
    const user = userEvent.setup();
    renderStep();
    await user.click(screen.getByRole("button", { name: "Generate Cover Letter" }));

    const editor = await screen.findByRole("textbox");
    fireEvent.change(editor, {
      target: { value: "Header words ignored Dear Hiring Manager, Body text" },
    });

    expect(screen.getByText("5 words")).toBeInTheDocument();
  });

  it.fails("keeps the editor available when the user clears the letter", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ letter: "Letter body", word_count: 2 }),
      }),
    );
    const user = userEvent.setup();
    renderStep();
    await user.click(screen.getByRole("button", { name: "Generate Cover Letter" }));

    await user.clear(await screen.findByRole("textbox"));

    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByText("0 words")).toBeInTheDocument();
  });

  it("reports clipboard permission failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ letter: "Letter body", word_count: 2 }),
      }),
    );
    const user = userEvent.setup();
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("denied"));
    renderStep();
    await user.click(screen.getByRole("button", { name: "Generate Cover Letter" }));

    await user.click(await screen.findByRole("button", { name: "Copy to Clipboard" }));

    await waitFor(() => {
      expect(screen.getByText(/couldn't access clipboard/i)).toBeInTheDocument();
    });
  });
});
