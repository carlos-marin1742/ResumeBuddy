import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import App from "./App";


const validDescription = Array.from({ length: 20 }, (_, index) => `word${index}`).join(" ");


describe("App workflow", () => {
  it("persists a created resume and opens its preview", async () => {
    const savedResume = {
      contact: {
        name: "Jamie Rivera",
        email: "jamie@example.com",
        phone: "",
        location: "",
        linkedin: "",
        portfolio: "",
      },
      targetRole: "",
      summary: "",
      experience: [{ company: "", title: "", location: "", startDate: "", endDate: "", highlights: "" }],
      education: [{ institution: "", degree: "", field: "", graduationDate: "" }],
      skills: [{ category: "", items: "" }],
      projects: [{ name: "", technologies: "", description: "", links: [] }],
      certifications: [{ name: "", issuer: "", date: "" }],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ email: "jamie@example.com" }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ resumes: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ resumes: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 201,
          json: async () => ({
            id: "master-123",
            created_at: "2026-07-24T12:00:00Z",
            updated_at: "2026-07-24T12:00:00Z",
            resume: savedResume,
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ status: "seeded", term_count: 2 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            id: "master-123",
            created_at: "2026-07-24T12:00:00Z",
            updated_at: "2026-07-24T12:30:00Z",
            resume: {
              ...savedResume,
              contact: { ...savedResume.contact, name: "Jamie R. Rivera" },
            },
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ status: "skipped-unchanged" }),
        }),
    );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /create a resume/i }));
    await user.type(screen.getByLabelText("Full name"), "Jamie Rivera");
    await user.type(screen.getByLabelText("Email"), "jamie@example.com");
    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    expect(await screen.findByRole("main", { name: /jamie rivera's resume preview/i })).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/master-resumes",
      expect.objectContaining({ method: "POST", body: expect.stringContaining('"targetJobTitle":""') }),
    );
    expect(fetch).toHaveBeenCalledWith("/api/master-resumes/master-123/seed-dictionary", { method: "POST" });

    await user.click(screen.getByRole("button", { name: "Edit resume" }));
    expect(screen.getByLabelText("Full name")).toHaveValue("Jamie Rivera");

    await user.clear(screen.getByLabelText("Full name"));
    await user.type(screen.getByLabelText("Full name"), "Jamie R. Rivera");
    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    expect(await screen.findByRole("main", { name: /jamie r\. rivera's resume preview/i })).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/master-resumes/master-123",
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("opens the resume builder from the profile screen and returns", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ resumes: [] }),
      }),
    );
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /create a resume/i }));
    expect(screen.getByRole("heading", { name: "Create your resume" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /back to resumes/i }));
    expect(await screen.findByRole("button", { name: /create a resume/i })).toBeInTheDocument();
  });

  it("moves from profile selection to keywords and preselects priority keywords", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ email: "jamie@example.com" }),
        })
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
          json: async () => ({ resumes: [] }),
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
      "/api/extract-keywords",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          job_description: validDescription,
          resume_id: "base_resume",
          master_resume_id: null,
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
          json: async () => ({ email: "jamie@example.com" }),
        })
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
          json: async () => ({ resumes: [] }),
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

  describe("slow and busy responses", () => {
    const keywords = {
      keywords: [{ keyword: "Python", category: "hard_skill", ats_weight: 10, present_in_resume: true }],
      gaps: [],
      role_level: "Mid",
    };

    function routedFetch(overrides) {
      return vi.fn(async (url) => {
        const path = String(url);
        for (const [fragment, handler] of Object.entries(overrides)) {
          if (path.includes(fragment)) return handler();
        }
        if (path.includes("/api/auth")) return { ok: true, json: async () => ({ email: "jamie@example.com" }) };
        if (path.endsWith("/api/resumes")) {
          return {
            ok: true,
            json: async () => ({ resumes: [{ id: "base_resume", name: "Technology", target_roles: [], last_updated: "" }] }),
          };
        }
        if (path.endsWith("/api/master-resumes")) return { ok: true, json: async () => ({ resumes: [] }) };
        throw new Error(`unexpected request ${path}`);
      });
    }

    const failures = [
      ["a busy server", () => ({ ok: false, status: 503 }), /server is busy.*try again in a moment/i],
      ["rate limiting", () => ({ ok: false, status: 429 }), /too many requests.*wait/i],
      ["a timeout", () => { throw Object.assign(new Error("aborted"), { name: "AbortError" }); }, /longer than expected/i],
    ];

    async function openKeywordStep(user) {
      await user.click(await screen.findByRole("button", { name: /technology/i }));
      await user.type(screen.getByLabelText("Job Description"), validDescription);
      await user.click(screen.getByRole("button", { name: /extract keywords/i }));
      await screen.findByText("Select keywords to target");
    }

    it.each(failures)("explains %s while extracting keywords", async (_label, failure, message) => {
      vi.stubGlobal("fetch", routedFetch({ "/api/extract-keywords": failure }));
      const user = userEvent.setup();
      render(<App />);

      await user.click(await screen.findByRole("button", { name: /technology/i }));
      await user.type(screen.getByLabelText("Job Description"), validDescription);
      await user.click(screen.getByRole("button", { name: /extract keywords/i }));

      expect(await screen.findByText(message)).toBeInTheDocument();
      expect(screen.getByLabelText("Job Description")).toHaveValue(validDescription);
    });

    it.each(failures)("explains %s while generating the resume", async (_label, failure, message) => {
      vi.stubGlobal("fetch", routedFetch({
        "/api/extract-keywords": () => ({ ok: true, json: async () => keywords }),
        "/api/generate-resume": failure,
      }));
      const user = userEvent.setup();
      render(<App />);
      await openKeywordStep(user);

      await user.click(screen.getByRole("button", { name: /generate resume/i }));

      expect(await screen.findByText(message)).toBeInTheDocument();
      expect(screen.getByText("Select keywords to target")).toBeInTheDocument();
    });
  });
});
