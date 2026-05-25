import { useState } from "react";
import JDInput from "./components/JDInput";
import KeywordSelector from "./components/KeywordSelector";
import ResumePreview from "./components/ResumePreview.jsx";
import "./App.css";

const API = "http://127.0.0.1:8000";

// Steps: 0 = JD input, 1 = keyword selection, 2 = resume preview
export default function App() {
  const [step, setStep] = useState(0);

  // JD input
  const [jobDescription, setJobDescription] = useState("");

  // Keyword extraction result
  const [extractResult, setExtractResult] = useState(null);
  const [selectedKeywords, setSelectedKeywords] = useState([]);

  // Generation result
  const [generateResult, setGenerateResult] = useState(null);

  // Loading / error states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // ── Step 0 → 1: extract keywords ────────────────────────────────────────
  async function handleExtract(jd) {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/extract-keywords`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_description: jd }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setExtractResult(data);
      // Pre-select all priority keywords (ats_weight === 10)
      const priority = data.keywords
        .filter((k) => k.ats_weight === 10)
        .map((k) => k.keyword);
      setSelectedKeywords(priority);
      setStep(1);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // ── Step 1 → 2: generate resume ──────────────────────────────────────────
  async function handleGenerate() {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/generate-resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_description: jobDescription,
          selected_keywords: selectedKeywords,
        }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setGenerateResult(data);
      setStep(2);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // ── Back navigation ──────────────────────────────────────────────────────
  function handleBack() {
    setError(null);
    if (step === 2) { setStep(1); return; }
    if (step === 1) { setStep(0); setExtractResult(null); setSelectedKeywords([]); }
  }

  function handleReset() {
    setStep(0);
    setJobDescription("");
    setExtractResult(null);
    setSelectedKeywords([]);
    setGenerateResult(null);
    setError(null);
  }

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="app-header">
        <button className="wordmark" onClick={handleReset}>
          ResuméBuddy
        </button>
        <nav className="step-nav">
          {["Job Description", "Keywords", "Resume"].map((label, i) => (
            <div key={i} className={`step-pill ${i === step ? "active" : ""} ${i < step ? "done" : ""}`}>
              <span className="step-num">{i + 1}</span>
              <span className="step-label">{label}</span>
            </div>
          ))}
        </nav>
      </header>

      {/* ── Error banner ── */}
      {error && (
        <div className="error-banner">
          <span>⚠ {error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* ── Main content ── */}
      <main className="app-main">
        {step === 0 && (
          <JDInput
            value={jobDescription}
            onChange={setJobDescription}
            onSubmit={handleExtract}
            loading={loading}
          />
        )}
        {step === 1 && extractResult && (
          <KeywordSelector
            extractResult={extractResult}
            selected={selectedKeywords}
            onChange={setSelectedKeywords}
            onBack={handleBack}
            onGenerate={handleGenerate}
            loading={loading}
          />
        )}
        {step === 2 && generateResult && (
          <ResumePreview
            result={generateResult}
            apiBase={API}
            onBack={handleBack}
            onReset={handleReset}
          />
        )}
      </main>
    </div>
  );
}