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
    const resolvers = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise((resolve) => {
        resolvers.push(resolve);
      })),
    );
    const onSelect = vi.fn();
    const user = userEvent.setup();

    render(<ResumePicker apiBase="http://api.test" onSelect={onSelect} />);
    expect(screen.getByText(/loading your resume profiles/i)).toBeInTheDocument();

    resolvers[0]({
      ok: true,
      json: async () => ({ resumes: [profile] }),
    });
    resolvers[1]({
      ok: true,
      json: async () => ({ resumes: [] }),
    });

    const profileButton = await screen.findByRole("button", { name: /technology/i });
    expect(fetch).toHaveBeenCalledWith("http://api.test/api/resumes");
    expect(fetch).toHaveBeenCalledWith("http://api.test/api/master-resumes");
    expect(screen.getByText("Engineer")).toBeInTheDocument();
    expect(screen.queryByText("Hidden")).not.toBeInTheDocument();

    await user.click(profileButton);
    expect(onSelect).toHaveBeenCalledWith(profile);
  });

  it("shows and selects a saved master resume", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url) => Promise.resolve({
        ok: true,
        json: async () => (
          url.endsWith("/api/master-resumes")
            ? {
                resumes: [{
                  id: "master-1",
                  name: "Jamie Rivera",
                  title: "Product Resume",
                  updated_at: "2026-07-30T12:00:00Z",
                }],
              }
            : { resumes: [] }
        ),
      })),
    );
    const onSelect = vi.fn();
    const user = userEvent.setup();

    render(<ResumePicker apiBase="http://api.test" onSelect={onSelect} />);

    await user.click(await screen.findByRole("button", { name: "Select Product Resume" }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({
      id: "master-1",
      source: "master",
      name: "Product Resume",
    }));
  });

  it("confirms and deletes a saved master resume", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url, options) => {
        if (options?.method === "DELETE") {
          return Promise.resolve({
            ok: true,
            json: async () => ({ deleted: true, id: "master-1" }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => (
            url.endsWith("/api/master-resumes")
              ? {
                  resumes: [{
                    id: "master-1",
                    name: "Jamie Rivera",
                    title: "Product Resume",
                    updated_at: "2026-07-30T12:00:00Z",
                  }],
                }
              : { resumes: [] }
          ),
        });
      }),
    );
    const user = userEvent.setup();

    render(<ResumePicker apiBase="http://api.test" onSelect={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "Delete Product Resume" }));
    expect(screen.getByText("Delete this resume?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(fetch).toHaveBeenCalledWith(
      "http://api.test/api/master-resumes/master-1",
      { method: "DELETE" },
    );
    expect(screen.queryByText("Product Resume")).not.toBeInTheDocument();
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
