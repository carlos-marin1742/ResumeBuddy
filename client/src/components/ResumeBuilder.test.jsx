import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ResumeBuilder from "./ResumeBuilder";

// Shared with backend/services/test_master_resume_adapter.py's
// SKILL_ITEMS_FIXTURES. The two splitters are pinned together by this
// identical input/output list rather than shared code, since the boundary
// is JS/Python.
const SKILL_ITEMS_FIXTURES = [
  ["React, TypeScript, Vite", ["React", "TypeScript", "Vite"]],
  [
    "Microsoft Office (Word, Excel, Outlook)",
    ["Microsoft Office (Word, Excel, Outlook)"],
  ],
  [
    "Phlebotomy, adult and pediatric\nVenipuncture",
    ["Phlebotomy, adult and pediatric", "Venipuncture"],
  ],
  [
    "IV Insertion [peripheral, central], Wound Care",
    ["IV Insertion [peripheral, central]", "Wound Care"],
  ],
  ["Python,,SQL", ["Python", "SQL"]],
  ["  React ,  Vite  ", ["React", "Vite"]],
  [", ", []],
  ["", []],
];


describe("ResumeBuilder", () => {
  const importedDraft = {
    contact: {
      name: "Imported Person",
      email: "imported@example.com",
      phone: "",
      location: "",
      linkedin: "",
      portfolio: "",
    },
    targetRole: "Designer",
    summary: "Imported summary",
    experience: [{ company: "", title: "", location: "", startDate: "", endDate: "", highlights: "" }],
    education: [{ institution: "", degree: "", field: "", graduationDate: "" }],
    skills: [{ category: "Design", items: "Research" }],
    projects: [{ name: "", technologies: "", description: "", links: [] }],
    certifications: [{ name: "", issuer: "", date: "" }],
  };

  it("renders every requested resume section", () => {
    render(<ResumeBuilder onBack={vi.fn()} onSave={vi.fn()} />);

    [
      "1. Contact information",
      "2. Resume title",
      "3. Professional summary",
      "4. Work experience",
      "5. Education",
      "6. Skills",
      "7. Projects",
      "8. Certifications",
    ].forEach((heading) => {
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    });
  });

  it("adds another work experience and saves entered details", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<ResumeBuilder onBack={vi.fn()} onSave={onSave} />);

    await user.type(screen.getByLabelText("Full name"), "Jamie Rivera");
    await user.type(screen.getByLabelText("Email"), "jamie@example.com");
    await user.type(screen.getByLabelText("How should this resume appear in your resume list?"), "Product Manager");
    await user.click(screen.getByRole("button", { name: /add experience/i }));

    expect(screen.getByRole("heading", { name: "Experience 2" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      contact: expect.objectContaining({
        name: "Jamie Rivera",
        email: "jamie@example.com",
      }),
      targetRole: "Product Manager",
      experience: expect.any(Array),
    }));
    expect(screen.getByText("Resume saved.")).toBeInTheDocument();
  });

  it("adds and saves labeled skill categories", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<ResumeBuilder onBack={vi.fn()} onSave={onSave} />);

    await user.type(screen.getByLabelText("Full name"), "Jamie Rivera");
    await user.type(screen.getByLabelText("Email"), "jamie@example.com");
    await user.type(screen.getByLabelText("Category name"), "Frontend");
    await user.type(screen.getByLabelText("Skills"), "React, TypeScript");
    await user.click(screen.getByRole("button", { name: /add category/i }));

    const categoryInputs = screen.getAllByLabelText("Category name");
    const skillInputs = screen.getAllByLabelText("Skills");
    await user.type(categoryInputs[1], "AI & LLMs");
    await user.type(skillInputs[1], "Claude API, LangChain");
    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      skills: [
        { key: "frontend", category: "Frontend", items: ["React", "TypeScript"] },
        { key: "ai-llms", category: "AI & LLMs", items: ["Claude API", "LangChain"] },
      ],
    }));
  });

  it("keeps a parenthesized skill with internal commas as one item", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<ResumeBuilder onBack={vi.fn()} onSave={onSave} />);

    await user.type(screen.getByLabelText("Full name"), "Jamie Rivera");
    await user.type(screen.getByLabelText("Email"), "jamie@example.com");
    await user.type(screen.getByLabelText("Category name"), "Tools");
    await user.type(
      screen.getByLabelText("Skills"),
      "Microsoft Office (Word, Excel, Outlook), Slack",
    );
    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      skills: [
        {
          key: "tools",
          category: "Tools",
          items: ["Microsoft Office (Word, Excel, Outlook)", "Slack"],
        },
      ],
    }));
  });

  it("splits a newline-separated skill list on lines, keeping in-line commas literal", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<ResumeBuilder onBack={vi.fn()} onSave={onSave} />);

    await user.type(screen.getByLabelText("Full name"), "Jamie Rivera");
    await user.type(screen.getByLabelText("Email"), "jamie@example.com");
    await user.type(screen.getByLabelText("Category name"), "Clinical");
    await user.type(
      screen.getByLabelText("Skills"),
      "Phlebotomy, adult and pediatric{Enter}Venipuncture",
    );
    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      skills: [
        {
          key: "clinical",
          category: "Clinical",
          items: ["Phlebotomy, adult and pediatric", "Venipuncture"],
        },
      ],
    }));
  });

  it.each(SKILL_ITEMS_FIXTURES)(
    "splits %j into %j via splitSkillItems, matching the shared backend fixture",
    async (raw, expected) => {
      const onSave = vi.fn();
      const user = userEvent.setup();
      render(<ResumeBuilder onBack={vi.fn()} onSave={onSave} />);

      await user.type(screen.getByLabelText("Full name"), "Jamie Rivera");
      await user.type(screen.getByLabelText("Email"), "jamie@example.com");
      await user.type(screen.getByLabelText("Category name"), "Category");
      fireEvent.change(screen.getByLabelText("Skills"), { target: { value: raw } });
      await user.click(screen.getByRole("button", { name: "Save & preview" }));

      expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
        skills: [expect.objectContaining({ items: expected })],
      }));
    },
  );

  it("loads a draft whose skill items are already an array and re-saves it unchanged", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    const draft = {
      contact: { name: "Jamie Rivera", email: "jamie@example.com", phone: "", location: "", linkedin: "", portfolio: "" },
      targetRole: "",
      summary: "",
      experience: [{ company: "", title: "", location: "", startDate: "", endDate: "", highlights: "" }],
      education: [{ institution: "", degree: "", field: "", graduationDate: "" }],
      skills: [{ key: "frontend", category: "Frontend", items: ["React", "TypeScript"] }],
      projects: [{ name: "", technologies: "", description: "", links: [] }],
      certifications: [{ name: "", issuer: "", date: "" }],
    };
    render(<ResumeBuilder initialDraft={draft} onBack={vi.fn()} onSave={onSave} />);

    expect(screen.getByLabelText("Skills")).toHaveValue("React, TypeScript");

    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      skills: [{ key: "frontend", category: "Frontend", items: ["React", "TypeScript"] }],
    }));
  });

  it("keeps a group with a category but no items, and drops a fully empty group", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<ResumeBuilder onBack={vi.fn()} onSave={onSave} />);

    await user.type(screen.getByLabelText("Full name"), "Jamie Rivera");
    await user.type(screen.getByLabelText("Email"), "jamie@example.com");
    await user.type(screen.getByLabelText("Category name"), "Frontend");
    await user.click(screen.getByRole("button", { name: /add category/i }));
    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      skills: [{ key: "frontend", category: "Frontend", items: [] }],
    }));
  });

  it("assigns a key to every skill group and gives distinct keys to same-named categories", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<ResumeBuilder onBack={vi.fn()} onSave={onSave} />);

    await user.type(screen.getByLabelText("Full name"), "Jamie Rivera");
    await user.type(screen.getByLabelText("Email"), "jamie@example.com");
    await user.type(screen.getByLabelText("Category name"), "Frontend");
    await user.click(screen.getByRole("button", { name: /add category/i }));
    const categoryInputs = screen.getAllByLabelText("Category name");
    await user.type(categoryInputs[1], "Frontend");
    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    const [{ skills }] = onSave.mock.calls[0];
    expect(skills).toHaveLength(2);
    expect(skills[0].key).toBe("frontend");
    expect(skills[1].key).toBe("frontend-2");
    expect(skills[0].key).not.toBe(skills[1].key);
  });

  it("gives an empty-category skill group a usable key", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<ResumeBuilder onBack={vi.fn()} onSave={onSave} />);

    await user.type(screen.getByLabelText("Full name"), "Jamie Rivera");
    await user.type(screen.getByLabelText("Email"), "jamie@example.com");
    await user.type(screen.getByLabelText("Skills"), "React");
    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    const [{ skills }] = onSave.mock.calls[0];
    expect(skills).toEqual([{ key: expect.any(String), category: "", items: ["React"] }]);
    expect(skills[0].key.length).toBeGreaterThan(0);
  });

  it("keeps a skill category's key stable after the category is renamed", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<ResumeBuilder onBack={vi.fn()} onSave={onSave} />);

    await user.type(screen.getByLabelText("Full name"), "Jamie Rivera");
    await user.type(screen.getByLabelText("Email"), "jamie@example.com");
    await user.type(screen.getByLabelText("Category name"), "Frontend");
    await user.type(screen.getByLabelText("Skills"), "React");
    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    const firstKey = onSave.mock.calls[0][0].skills[0].key;
    expect(firstKey).toBe("frontend");

    await user.clear(screen.getByLabelText("Category name"));
    await user.type(screen.getByLabelText("Category name"), "Front-end Development");
    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    const secondCall = onSave.mock.calls[1][0];
    expect(secondCall.skills[0].category).toBe("Front-end Development");
    expect(secondCall.skills[0].key).toBe(firstKey);
  });

  it("does not save when required contact details are missing", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<ResumeBuilder onBack={vi.fn()} onSave={onSave} />);

    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Full name")).toBeRequired();
    expect(screen.getByLabelText("Email")).toBeRequired();
  });

  it("adds a named project link to the saved draft", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<ResumeBuilder onBack={vi.fn()} onSave={onSave} />);

    await user.type(screen.getByLabelText("Full name"), "Jamie Rivera");
    await user.type(screen.getByLabelText("Email"), "jamie@example.com");
    await user.click(screen.getByRole("button", { name: /add link/i }));
    await user.type(screen.getByLabelText("Link name"), "GitHub");
    await user.type(screen.getByLabelText("URL"), "https://github.com/jamie/project");
    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      projects: [
        expect.objectContaining({
          links: [{
            name: "GitHub",
            url: "https://github.com/jamie/project",
          }],
        }),
      ],
    }));
  });

  it("requires both a name and valid URL for an added project link", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<ResumeBuilder onBack={vi.fn()} onSave={onSave} />);

    await user.type(screen.getByLabelText("Full name"), "Jamie Rivera");
    await user.type(screen.getByLabelText("Email"), "jamie@example.com");
    await user.click(screen.getByRole("button", { name: /add link/i }));
    await user.type(screen.getByLabelText("Link name"), "GitHub");
    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByLabelText("URL")).toBeRequired();
  });

  it("imports a PDF into the editable form and waits for review before saving", async () => {
    const onSave = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        filename: "resume.pdf",
        draft: importedDraft,
        warnings: ["Review imported fields."],
      }),
    }));
    const user = userEvent.setup();
    render(<ResumeBuilder apiBase="http://api.test" onBack={vi.fn()} onSave={onSave} />);

    await user.upload(
      screen.getByLabelText(/upload resume/i),
      new File(["%PDF"], "resume.pdf", { type: "application/pdf" }),
    );

    expect(await screen.findByDisplayValue("Imported Person")).toBeInTheDocument();
    expect(screen.getByLabelText("How should this resume appear in your resume list?")).toHaveValue("Designer");
    expect(screen.getByText("resume.pdf was imported.")).toBeInTheDocument();
    expect(screen.getByText("Review imported fields.")).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
    expect(fetch).toHaveBeenCalledWith(
      "http://api.test/api/resumes/parse",
      expect.objectContaining({ method: "POST", body: expect.any(FormData) }),
    );

    await user.click(screen.getByRole("button", { name: "Save & preview" }));
    expect(onSave).toHaveBeenCalledWith({
      ...importedDraft,
      skills: [{ key: "design", category: "Design", items: ["Research"] }],
    });
  });

  it("shows a persistence error and keeps the editable resume", async () => {
    const user = userEvent.setup();
    render(
      <ResumeBuilder
        onBack={vi.fn()}
        onSave={vi.fn().mockRejectedValue(new Error("Could not save resume."))}
      />,
    );

    await user.type(screen.getByLabelText("Full name"), "Jamie Rivera");
    await user.type(screen.getByLabelText("Email"), "jamie@example.com");
    await user.click(screen.getByRole("button", { name: "Save & preview" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save resume.");
    expect(screen.getByLabelText("Full name")).toHaveValue("Jamie Rivera");
  });

  it("shows import errors without replacing the current draft", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 415,
      json: async () => ({ detail: "Upload a PDF or DOCX resume." }),
    }));
    const user = userEvent.setup();
    render(<ResumeBuilder apiBase="http://api.test" onBack={vi.fn()} onSave={vi.fn()} />);

    await user.type(screen.getByLabelText("Full name"), "Keep This Name");
    await user.upload(
      screen.getByLabelText(/upload resume/i),
      new File(["%PDF"], "resume.pdf", { type: "application/pdf" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Upload a PDF or DOCX resume.");
    expect(screen.getByLabelText("Full name")).toHaveValue("Keep This Name");
  });
});
