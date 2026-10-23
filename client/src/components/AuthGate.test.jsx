import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import AuthGate from "./AuthGate";

function stubAuthApi({ config }) {
  const fetchMock = vi.fn(async (url) => {
    if (url === "/api/auth/config") return config();
    return { ok: false, json: async () => ({ detail: "Authentication required." }) };
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const registrationRequested = (fetchMock) => fetchMock.mock.calls.some(([url]) => url === "/api/auth/register");

describe("AuthGate registration availability", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("offers registration when the server reports it open", async () => {
    stubAuthApi({ config: async () => ({ ok: true, json: async () => ({ registration_open: true }) }) });
    const user = userEvent.setup();
    render(<AuthGate><p>app</p></AuthGate>);

    await user.click(await screen.findByRole("button", { name: "Need an account? Register" }));

    expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();
  });

  it("hides the register toggle when registration is not open", async () => {
    stubAuthApi({ config: async () => ({ ok: true, json: async () => ({ registration_open: false }) }) });
    render(<AuthGate><p>app</p></AuthGate>);

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/auth/config", expect.anything()));
    expect(screen.queryByRole("button", { name: /register/i })).not.toBeInTheDocument();
  });

  it("hides the register toggle when the config request fails", async () => {
    stubAuthApi({ config: async () => { throw new Error("network down"); } });
    render(<AuthGate><p>app</p></AuthGate>);

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /register/i })).not.toBeInTheDocument();
  });

  it("hides the register toggle when the config response is an error status", async () => {
    stubAuthApi({ config: async () => ({ ok: false, json: async () => ({}) }) });
    render(<AuthGate><p>app</p></AuthGate>);

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /register/i })).not.toBeInTheDocument();
  });

  it("keeps sign-in working when registration is closed", async () => {
    const fetchMock = vi.fn(async (url) => {
      if (url === "/api/auth/config") return { ok: true, json: async () => ({ registration_open: false }) };
      if (url === "/api/auth/login") return { ok: true, json: async () => ({ detail: "Signed in." }) };
      return { ok: false, json: async () => ({}) };
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AuthGate><p>app</p></AuthGate>);

    await user.type(await screen.findByLabelText("Email"), "me@example.com");
    await user.type(screen.getByLabelText("Password"), "valid-password-123");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("app")).toBeInTheDocument();
    expect(registrationRequested(fetchMock)).toBe(false);
  });
});
