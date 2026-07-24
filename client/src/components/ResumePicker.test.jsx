import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ResumePicker from "./ResumePicker";


describe("ResumePicker", () => {
  it("shows loading, renders returned profiles, and selects a profile", async () => {
    const profile = {
      id: "base_resume",
      name: "Technology",
      target_roles: ["Engineer", "Developer", "Architect", "Hidden"],
      last_updated: "2026-07-01",
    };
    let resolveFetch;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise((resolve) => {
        resolveFetch = resolve;
      })),
    );
    const onSelect = vi.fn();
    const user = userEvent.setup();

    render(<ResumePicker apiBase="http://api.test" onSelect={onSelect} />);
    expect(screen.getByText(/loading your resume profiles/i)).toBeInTheDocument();

    resolveFetch({
      ok: true,
      json: async () => ({ resumes: [profile] }),
    });

    const profileButton = await screen.findByRole("button", { name: /technology/i });
    expect(fetch).toHaveBeenCalledWith("http://api.test/api/resumes");
    expect(screen.getByText("Engineer")).toBeInTheDocument();
    expect(screen.queryByText("Hidden")).not.toBeInTheDocument();

    await user.click(profileButton);
    expect(onSelect).toHaveBeenCalledWith(profile);
  });

  it("surfaces non-successful HTTP responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
      }),
    );

    render(<ResumePicker apiBase="http://api.test" onSelect={vi.fn()} />);

    expect(await screen.findByText(/server error 503/i)).toBeInTheDocument();
  });

  it("opens the create-resume flow from above the profile list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ resumes: [] }),
      }),
    );
    const onCreate = vi.fn();
    const user = userEvent.setup();

    render(
      <ResumePicker
        apiBase="http://api.test"
        onCreate={onCreate}
        onSelect={vi.fn()}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /create a resume/i }));
    expect(onCreate).toHaveBeenCalledOnce();
  });
});
