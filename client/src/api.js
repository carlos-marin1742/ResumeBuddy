// Shared fetch timeouts and plain-language failure messages for the slow,
// paid, or PDF-rendering API calls.

export const FETCH_TIMEOUTS_MS = {
  generate: 120_000,
  standard: 60_000,
};

export const FAILURE_MESSAGES = {
  busy: "The server is busy. Please try again in a moment.",
  rateLimited: "Too many requests. Please wait a moment and try again.",
  timeout: "This is taking longer than expected. Please try again.",
};

export async function fetchWithTimeout(url, options = {}, timeoutMs = FETCH_TIMEOUTS_MS.standard) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (error) {
    if (error?.name === "AbortError") throw new Error(FAILURE_MESSAGES.timeout, { cause: error });
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

// Returns a plain-language message for statuses users can act on, else null.
export function statusMessage(status) {
  if (status === 503) return FAILURE_MESSAGES.busy;
  if (status === 429) return FAILURE_MESSAGES.rateLimited;
  return null;
}
