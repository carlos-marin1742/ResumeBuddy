import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import MasterResumePreview from "./MasterResumePreview";


const resume = {
  contact: {
    name: "Jamie Rivera",
    email: "jamie@example.com",
    phone: "312-555-0100",
    location: "Chicago, IL",
    linkedin: "https://linkedin.com/in/jamie",
    portfolio: "https://jamie.example.com",
  },
  targetRole: "Product Manager",
  summary: "Product leader focused on accessible software.",
  experience: [{
    company: "Example Co",
    title: "Product Manager",
    location: "Chicago, IL",
    startDate: "2022-01",
    endDate: "",
    highlights: "Led product discovery and delivery.\nImproved customer retention.",
  }],
  education: [{
    institution: "State University",
    degree: "BS",
    field: "Information Systems",
    graduationDate: "2021-05",
  }],
  skills: [
    { category: "Frontend", items: "React, TypeScript" },
    { category: "AI & LLMs", items: "Claude API, LangChain" },
  ],
  projects: [{
    name: "Accessibility Toolkit",
    technologies: "React",
    description: "Built an accessible component library.",
    links: [{ name: "GitHub", url: "https://github.com/jamie/toolkit" }],
  }],
  certifications: [{
    name: "Scrum Product Owner",
    issuer: "Scrum Alliance",
    date: "2023-03",
  }],
};


describe("MasterResumePreview", () => {
  it("renders the saved resume and its links", () => {
    render(
      <MasterResumePreview
        resume={resume}
        savedAt="2026-07-24T12:00:00Z"
        onBack={vi.fn()}
        onEdit={vi.fn()}
      />,
    );

    expect(screen.getByRole("main", { name: /jamie rivera's resume preview/i })).toBeInTheDocument();
    expect(screen.queryByText("Product Manager", { selector: ".mrp-role" })).not.toBeInTheDocument();
    expect(screen.getByText("Product leader focused on accessible software.")).toBeInTheDocument();
    expect(screen.getByText("Example Co · Chicago, IL")).toBeInTheDocument();
    expect(screen.getByText("Led product discovery and delivery.").tagName).toBe("LI");
    expect(screen.getByText("Improved customer retention.").tagName).toBe("LI");
    expect(screen.getByText("State University")).toBeInTheDocument();
    expect(screen.getByText("Scrum Product Owner")).toBeInTheDocument();
    expect(screen.getByText("Frontend:").tagName).toBe("STRONG");
    expect(screen.getByText("AI & LLMs:").tagName).toBe("STRONG");
    expect(screen.getByRole("link", { name: "GitHub" })).toHaveAttribute(
      "href",
      "https://github.com/jamie/toolkit",
    );
  });

  it("returns to editing", async () => {
    const onEdit = vi.fn();
    const user = userEvent.setup();
    render(
      <MasterResumePreview
        resume={resume}
        savedAt="2026-07-24T12:00:00Z"
        onBack={vi.fn()}
        onEdit={onEdit}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Edit resume" }));
    expect(onEdit).toHaveBeenCalledOnce();
  });
});
