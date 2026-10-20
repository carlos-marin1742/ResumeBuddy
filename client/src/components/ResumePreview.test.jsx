import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ResumePreview from "./ResumePreview";


function makeResult(overrides = {}) {
  return {
    summary: "Targeted summary",
    experiences: [],
    projects: [],
    skills_to_highlight: [],
    ats: {
      overall_score: 90,
      keyword_coverage: 0.8,
      matched_keywords: [],
      missing_keywords: [],
      suggestions: [],
    },
    generated_at: "2026-10-19T12:00:00Z",
    history_id: "history-123",
    pdf_url: null,
    ...overrides,
  };
}

function renderPreview(result) {
  return render(
    <ResumePreview
      result={result}
      apiBase="http://api.test"
      onBack={vi.fn()}
      onReset={vi.fn()}
      onPreviewPDF={vi.fn()}
      onEdit={vi.fn()}
      jobDescription="Build APIs"
      selectedKeywords={[]}
    />,
  );
}

describe("ResumePreview download button", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("falls back to the history download route while the PDF is pending", async () => {
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    renderPreview(makeResult({ pdf_url: null, history_id: "history-123" }));

    // The top bar and the sidebar each render a Download PDF button.
    await userEvent.click(screen.getAllByRole("button", { name: /download pdf/i })[0]);

    expect(open).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledWith("http://api.test/api/download-history/history-123", "_blank");
  });

  it("uses the generated pdf_url when the PDF is ready", async () => {
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    renderPreview(makeResult({ pdf_url: "/api/download/Candidate_Resume_ab12.pdf" }));

    await userEvent.click(screen.getAllByRole("button", { name: /download pdf/i })[0]);

    expect(open).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledWith("http://api.test/api/download/Candidate_Resume_ab12.pdf", "_blank");
  });
});
