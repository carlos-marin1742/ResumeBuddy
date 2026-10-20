import { afterEach, describe, expect, it, vi } from "vitest";

import { FAILURE_MESSAGES, FETCH_TIMEOUTS_MS, fetchWithTimeout, statusMessage } from "./api";


function abortableFetch() {
  return vi.fn((url, { signal }) => new Promise((resolve, reject) => {
    signal.addEventListener("abort", () => {
      reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
    });
  }));
}


describe("api helpers", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps generation timeouts generous and in one place", () => {
    expect(FETCH_TIMEOUTS_MS).toEqual({ generate: 120_000, standard: 60_000 });
  });

  it("maps 503 and 429 to plain-language messages and leaves other statuses alone", () => {
    expect(statusMessage(503)).toBe(FAILURE_MESSAGES.busy);
    expect(statusMessage(429)).toBe(FAILURE_MESSAGES.rateLimited);
    expect(statusMessage(500)).toBeNull();
    expect(FAILURE_MESSAGES.busy).toMatch(/busy.*try again in a moment/i);
    expect(FAILURE_MESSAGES.rateLimited).toMatch(/too many requests.*wait/i);
  });

  it("aborts after the standard timeout and reports the slow-response message", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", abortableFetch());
    const outcome = fetchWithTimeout("/api/slow").catch((error) => error);

    await vi.advanceTimersByTimeAsync(FETCH_TIMEOUTS_MS.standard - 1);
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);

    const error = await outcome;
    expect(error.message).toBe(FAILURE_MESSAGES.timeout);
    expect(error.message).toMatch(/longer than expected/i);
  });

  it("honours a longer per-call timeout", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", abortableFetch());
    const outcome = fetchWithTimeout("/api/generate", {}, FETCH_TIMEOUTS_MS.generate).catch((e) => e);

    await vi.advanceTimersByTimeAsync(FETCH_TIMEOUTS_MS.standard + 1);
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(FETCH_TIMEOUTS_MS.generate);

    expect((await outcome).message).toBe(FAILURE_MESSAGES.timeout);
  });

  it("passes responses and non-timeout errors through unchanged", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce({ ok: true }).mockRejectedValueOnce(new Error("offline")));

    expect(await fetchWithTimeout("/api/ok")).toEqual({ ok: true });
    await expect(fetchWithTimeout("/api/down")).rejects.toThrow("offline");
  });
});
