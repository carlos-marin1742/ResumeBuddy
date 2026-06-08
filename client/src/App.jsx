import { useState } from "react";
import ResumePicker from "./components/ResumePicker";
import JDInput from "./components/JDInput";
import KeywordSelector from "./components/KeywordSelector";
import ResumePreview from "./components/ResumePreview";
import PDFPreview from "./components/PDFPreview";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "";

// Steps: 0 = pick resume, 1 = JD input, 2 = keywords, 3 = result, 4 = PDF preview
export default function App() {
  const [step, setStep] = useState(0);

  const [selectedResume, setSelectedResume] = useState(null);
  const [jobDescription, setJobDescription] = useState("");
  const [extractResult, setExtractResult] = useState(null);
  const [selectedKeywords, setSelectedKeywords] = useState([]);
  const [generateResult, setGenerateResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // ── Step 0 → 1 ───────────────────────────────────────────────────────────
  function handleResumeSelect(resume) {
    setSelectedResume(resume);
    setStep(1);
  }

  // ── Step 1 → 2 ───────────────────────────────────────────────────────────
  async function handleExtract(jd) {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/extract-keywords`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_description: jd, resume_id: selectedResume.id }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setExtractResult(data);
      const priority = data.keywords.filter((k) => k.ats_weight === 10).map((k) => k.keyword);
      setSelectedKeywords(priority);
      setStep(2);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // ── Step 2 → 3 ───────────────────────────────────────────────────────────
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
          resume_id: selectedResume.id,
        }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setGenerateResult(data);
      setStep(3);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // ── Step 3 → 4 ───────────────────────────────────────────────────────────
  function handlePreviewPDF() {
    setStep(4);
  }

  // ── Back navigation ───────────────────────────────────────────────────────
  function handleBack() {
    setError(null);
    if (step === 4) { setStep(3); return; }
    if (step === 3) { setStep(2); return; }
    if (step === 2) { setStep(1); setExtractResult(null); setSelectedKeywords([]); return; }
    if (step === 1) { setStep(0); setSelectedResume(null); setJobDescription(""); }
  }

  function handleReset() {
    setStep(0);
    setSelectedResume(null);
    setJobDescription("");
    setExtractResult(null);
    setSelectedKeywords([]);
    setGenerateResult(null);
    setError(null);
  }

  const STEP_LABELS = ["Resume", "Job Description", "Keywords", "Result", "PDF Preview"];

  return (
    <div className="app">
      <header className="app-header">
        <button className="wordmark" onClick={handleReset}>ResuméBuddy</button>
        <nav className="step-nav">
          {STEP_LABELS.map((label, i) => (
            <div key={i} className={`step-pill ${i === step ? "active" : ""} ${i < step ? "done" : ""}`}>
              <span className="step-num">{i + 1}</span>
              <span className="step-label">{label}</span>
            </div>
          ))}
        </nav>
      </header>

      {error && (
        <div className="error-banner">
          <span>⚠ {error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <main className="app-main">
        {step === 0 && (
          <ResumePicker apiBase={API} onSelect={handleResumeSelect} />
        )}
        {step === 1 && (
          <JDInput
            value={jobDescription}
            onChange={setJobDescription}
            onSubmit={handleExtract}
            onBack={handleBack}
            loading={loading}
            resumeName={selectedResume?.name}
          />
        )}
        {step === 2 && extractResult && (
          <KeywordSelector
            extractResult={extractResult}
            selected={selectedKeywords}
            onChange={setSelectedKeywords}
            onBack={handleBack}
            onGenerate={handleGenerate}
            loading={loading}
          />
        )}
        {step === 3 && generateResult && (
          <ResumePreview
            result={generateResult}
            apiBase={API}
            onBack={handleBack}
            onReset={handleReset}
            onPreviewPDF={handlePreviewPDF}
          />
        )}
        {step === 4 && generateResult && (
          <PDFPreview
            sessionId={generateResult.session_id}
            apiBase={API}
            onBack={handleBack}
            onReset={handleReset}
          />
        )}
      </main>
    </div>
  );
}