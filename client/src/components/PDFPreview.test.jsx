import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import PDFPreview from "./PDFPreview";


function renderPreview(props = {}) {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
    ok: true,
    text: async () => "<html><body>Preview</body></html>",
  })));
  return render(
    <PDFPreview
      sessionId="session-1"
      apiBase="http://api.test"
      onBack={vi.fn()}
      {...props}
    />,
  );
}


describe("PDFPreview fitting status", () => {
  it("states when the generated PDF did not fit at the requested font size", () => {
    renderPreview({ pdfPageCount: 2, pdfFittedToOnePage: false });

    expect(screen.getByRole("status")).toHaveTextContent(
      "This resume is 2 pages. Spacing could not compress further at this font size.",
    );
  });

  it("shows no extra fitting statement when the PDF fit on one page", () => {
    renderPreview({ pdfPageCount: 1, pdfFittedToOnePage: true });

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("does not claim that the clipped preview is exactly one page", () => {
    renderPreview();

    expect(screen.getByText(/preview is clipped to the first page/i)).toBeInTheDocument();
    expect(screen.queryByText(/preview shows exactly one page/i)).not.toBeInTheDocument();
  });

  describe("slow and busy downloads", () => {
    const failures = [
      ["a busy server", () => Promise.resolve({ ok: false, status: 503 }), /server is busy.*try again in a moment/i],
      ["rate limiting", () => Promise.resolve({ ok: false, status: 429 }), /too many requests.*wait/i],
      ["a timeout", () => Promise.reject(Object.assign(new Error("aborted"), { name: "AbortError" })), /longer than expected/i],
    ];

    it.each(failures)("explains %s while rendering the PDF", async (_label, failure, message) => {
      vi.stubGlobal("fetch", vi.fn((url) => (
        String(url).includes("/api/download-custom")
          ? failure()
          : Promise.resolve({ ok: true, text: async () => "<html><body>Preview</body></html>" })
      )));
      render(<PDFPreview sessionId="session-1" apiBase="http://api.test" onBack={vi.fn()} />);

      await userEvent.click((await screen.findAllByRole("button", { name: /download pdf/i }))[0]);

      expect(await screen.findByText(message)).toBeInTheDocument();
    });
  });
});
