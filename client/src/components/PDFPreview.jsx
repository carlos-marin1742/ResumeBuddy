import { useState, useEffect, useRef, useCallback } from "react";
import "./PDFPreview.css";

const DEFAULTS = {
  font_size: 8.5,
  margin: 0.4,
  side_margin: 0.5,
  entry_spacing: 5.0,
  section_spacing: 6.0,
};

const SLIDER_CONFIG = [
  {
    key: "font_size",
    label: "Font Size",
    min: 7.5, max: 10, step: 0.1,
    format: (v) => `${v.toFixed(1)}pt`,
  },
  {
    key: "margin",
    label: "Top / Bottom Margins",
    min: 0.3, max: 0.6, step: 0.05,
    format: (v) => `${v.toFixed(2)}in`,
  },
  {
    key: "side_margin",
    label: "Left / Right Margins",
    min: 0.3, max: 0.8, step: 0.05,
    format: (v) => `${v.toFixed(2)}in`,
  },
  {
    key: "entry_spacing",
    label: "Entry Spacing",
    min: 0, max: 15, step: 0.5,
    format: (v) => `${v.toFixed(1)}pt`,
  },
  {
    key: "section_spacing",
    label: "Section Spacing",
    min: 0, max: 15, step: 0.5,
    format: (v) => `${v.toFixed(1)}pt`,
  },
];

export default function PDFPreview({ sessionId, apiBase, onBack, onReset }) {
  const [overrides, setOverrides] = useState(DEFAULTS);
  const [previewHtml, setPreviewHtml] = useState("");
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [error, setError] = useState(null);
  const debounceRef = useRef(null);
  const iframeRef = useRef(null);

  const fetchPreview = useCallback(async (currentOverrides) => {
    setLoadingPreview(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/api/preview-html`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          overrides: currentOverrides,
        }),
      });
      if (!res.ok) throw new Error(`Preview failed: ${res.status}`);
      const html = await res.text();
      setPreviewHtml(html);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingPreview(false);
    }
  }, [apiBase, sessionId]);

  useEffect(() => {
    fetchPreview(DEFAULTS);
  }, [fetchPreview]);

  useEffect(() => {
    if (!iframeRef.current || !previewHtml) return;
    const blob = new Blob([previewHtml], { type: "text/html" });
    const url  = URL.createObjectURL(blob);
    iframeRef.current.src = url;
    return () => URL.revokeObjectURL(url);
  }, [previewHtml]);

  function handleSlider(key, value) {
    const next = { ...overrides, [key]: parseFloat(value) };
    setOverrides(next);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchPreview(next), 350);
  }

  function handleReset() {
    setOverrides(DEFAULTS);
    fetchPreview(DEFAULTS);
  }

  async function handleDownload() {
    setDownloadingPdf(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/api/download-custom`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          overrides,
        }),
      });
      if (!res.ok) throw new Error(`Download failed: ${res.status}`);
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = "resume_custom.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    } finally {
      setDownloadingPdf(false);
    }
  }

  return (
    <div className="pp-page fade-up">
      {/* ── Top bar ── */}
      <div className="pp-topbar">
        <div className="pp-topbar-inner">
          <div className="pp-topbar-left">
            <button className="btn btn-ghost btn-sm" onClick={onBack}>← Back</button>
            <span className="pp-title">PDF Preview</span>
          </div>
          <div className="pp-topbar-right">
            <button className="btn btn-secondary btn-sm" onClick={onReset}>
              Start over
            </button>
            <button
              className="btn btn-primary"
              onClick={handleDownload}
              disabled={downloadingPdf || loadingPreview}
            >
              {downloadingPdf ? (
                <><span className="spinner" /> Generating…</>
              ) : (
                <>↓ Download PDF</>
              )}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="pp-error-banner">
          ⚠ {error}
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <div className="pp-layout">
        {/* ── Left: iframe preview ── */}
        <div className="pp-preview-wrap">
          {loadingPreview && (
            <div className="pp-preview-loading">
              <span className="spinner" /> Updating preview…
            </div>
          )}
          <iframe
            ref={iframeRef}
            className={`pp-iframe ${loadingPreview ? "pp-iframe--loading" : ""}`}
            title="Resume Preview"
          />
        </div>

        {/* ── Right: controls sidebar ── */}
        <aside className="pp-sidebar">
          <div className="pp-controls card">
            <div className="pp-controls-header">
              <span className="pp-controls-title">Adjust Layout</span>
              <button className="btn btn-ghost btn-sm" onClick={handleReset}>
                Reset
              </button>
            </div>

            {SLIDER_CONFIG.map(({ key, label, min, max, step, format }) => (
              <div key={key} className="pp-slider-group">
                <div className="pp-slider-label">
                  <span>{label}</span>
                  <span className="pp-slider-value">{format(overrides[key])}</span>
                </div>
                <input
                  type="range"
                  min={min}
                  max={max}
                  step={step}
                  value={overrides[key]}
                  onChange={(e) => handleSlider(key, e.target.value)}
                  className="pp-slider"
                />
                <div className="pp-slider-range">
                  <span>{format(min)}</span>
                  <span>{format(max)}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="pp-hint card">
            <p>Adjust sliders to fine-tune spacing and margins. The preview updates live. Download generates a PDF with your exact settings.</p>
          </div>

          <button
            className="btn btn-primary pp-download-btn"
            onClick={handleDownload}
            disabled={downloadingPdf || loadingPreview}
          >
            {downloadingPdf ? (
              <><span className="spinner" /> Generating…</>
            ) : (
              <>↓ Download Custom PDF</>
            )}
          </button>
        </aside>
      </div>
    </div>
  );
}