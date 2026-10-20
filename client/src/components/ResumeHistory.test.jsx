import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ResumeHistory from "./ResumeHistory";


function makeRecord(overrides = {}) {
  return {
    id: "record-1",
    created_at: "2026-10-19T12:00:00Z",
    company: "Acme",
    job_title: "Engineer",
    profile: "base_resume",
    ats_overall_score: 90,
    ats_keyword_coverage: 0.8,
    selected_keywords: [],
    matched_keywords: [],
    extracted_keywords_count: 0,
    job_description: "Build APIs",
    has_pdf: true,
    cover_letter: null,
    ...overrides,
  };
}

async function openRecord(record) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ records: [record], total: 1 }),
  }));
  render(<ResumeHistory onBack={vi.fn()} />);
  await userEvent.click(await screen.findByRole("button", { name: /Acme/ }));
}

describe("ResumeHistory download button", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("offers the PDF download when the record has a rendered PDF", async () => {
    await openRecord(makeRecord({ has_pdf: true }));

    const link = await screen.findByRole("link", { name: /Download PDF/ });
    expect(link).toHaveAttribute("href", expect.stringMatching(/\/api\/download-history\/record-1$/));
  });

  it("hides the PDF download when the record has no rendered PDF", async () => {
    await openRecord(makeRecord({ has_pdf: false }));

    await screen.findByRole("button", { name: /Preview Resume/ });
    expect(screen.queryByRole("link", { name: /Download PDF/ })).not.toBeInTheDocument();
  });

  it("does not depend on a server path in the response", async () => {
    await openRecord(makeRecord({ has_pdf: true, pdf_path: undefined }));

    expect(await screen.findByRole("link", { name: /Download PDF/ })).toBeInTheDocument();
  });
});
