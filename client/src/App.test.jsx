import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import App from "./App";


const validDescription = Array.from({ length: 20 }, (_, index) => `word${index}`).join(" ");


describe("App workflow", () => {
  it("moves from profile selection to keywords and preselects priority keywords", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            resumes: [{
              id: "base_resume",
              name: "Technology",
              target_roles: [],
              last_updated: "",
            }],
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
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
                ats_weight: 7,
                present_in_resume: false,
              },
            ],
            gaps: ["Docker"],
            role_level: "Mid",
          }),
        }),
    );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /technology/i }));
    await user.type(screen.getByLabelText("Company"), "Example Co");
    await user.type(screen.getByLabelText("Job Title"), "Engineer");
    await user.type(screen.getByLabelText("Job Description"), validDescription);
    await user.click(screen.getByRole("button", { name: /extract keywords/i }));

    expect(await screen.findByText("Select keywords to target")).toBeInTheDocument();
    expect(screen.getByText("1 keyword selected")).toBeInTheDocument();
    expect(fetch).toHaveBeenLastCalledWith(
      "http://127.0.0.1:8000/api/extract-keywords",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          job_description: validDescription,
          resume_id: "base_resume",
        }),
      }),
    );
  });

  it("keeps the job-details step and shows feedback when extraction fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            resumes: [{
              id: "base_resume",
              name: "Technology",
              target_roles: [],
              last_updated: "",
            }],
          }),
        })
        .mockResolvedValueOnce({ ok: false, status: 502 }),
    );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /technology/i }));
    await user.type(screen.getByLabelText("Job Description"), validDescription);
    await user.click(screen.getByRole("button", { name: /extract keywords/i }));

    expect(await screen.findByText("Server error 502")).toBeInTheDocument();
    expect(screen.getByLabelText("Job Description")).toHaveValue(validDescription);
  });
});
