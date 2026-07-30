import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ResumeBuilder from "./ResumeBuilder";


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
        { category: "Frontend", items: "React, TypeScript" },
        { category: "AI & LLMs", items: "Claude API, LangChain" },
      ],
    }));
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
    expect(onSave).toHaveBeenCalledWith(importedDraft);
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
