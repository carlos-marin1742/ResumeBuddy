import { useState } from "react";
import ResumePicker from "./components/ResumePicker";
import ResumeBuilder from "./components/ResumeBuilder";
import MasterResumePreview from "./components/MasterResumePreview";
import JDInput from "./components/JDInput";
import KeywordSelector from "./components/KeywordSelector";
import ResumePreview from "./components/ResumePreview";
import PDFPreview from "./components/PDFPreview";
import ResumeHistory from "./components/ResumeHistory";
import CoverLetterStep from "./components/CoverLetterStep";
import "./App.css";

// Use same-origin API paths. Vite proxies `/api` during development, while
// FastAPI serves both the API and built client in production.
const API = "";

// Steps:
//   0 = pick resume profile  (ResumePicker)
//   1 = enter JD + company   (JDInput)
//   2 = select keywords      (KeywordSelector)
//   3 = preview + download   (ResumePreview)
//  "history" = history view  (ResumeHistory)

export default function App() {
  const [step, setStep] = useState(0);
  const [resumeDraft, setResumeDraft] = useState(null);
  const [masterResumeId, setMasterResumeId] = useState(null);
  const [savedMasterResume, setSavedMasterResume] = useState(null);

  // Resume profile selected in step 0
  const [selectedResume, setSelectedResume] = useState(null);

  // Job details collected in step 1
  const [jobDescription, setJobDescription]   = useState("");
  const [company, setCompany]                 = useState("");
  const [jobTitle, setJobTitle]               = useState("");

  // Keyword extraction result (step 1 → 2)
  const [extractResult, setExtractResult]     = useState(null);
  const [selectedKeywords, setSelectedKeywords] = useState([]);

  // Generation result (step 2 → 3)
  const [generateResult, setGenerateResult]   = useState(null);

  // Inline edits made in ResumePreview (step 3), forwarded to PDFPreview (step 4)
  const [editedResumeData, setEditedResumeData] = useState(null);

  // Shared loading / error state
  const [loading, setLoading]                 = useState(false);
  const [error, setError]                     = useState(null);

  // ── Step 0 → 1: choose profile ──────────────────────────────────────────
  function handleResumeSelect(resume) {
    setSelectedResume(resume);
    setStep(1);
  }

  function handleCreateResume() {
    setResumeDraft(null);
    setMasterResumeId(null);
    setSavedMasterResume(null);
    setStep("create-resume");
  }

  // ── Step 1 → 2: extract keywords ────────────────────────────────────────
  async function handleExtract(jd, co, title) {
    // JDInput passes (jobDescription, company, jobTitle)
    setJobDescription(jd);
    setCompany(co);
    setJobTitle(title);
    setError(null);
    setLoading(true);

    try {
      const res = await fetch(`${API}/api/extract-keywords`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_description: jd,
          resume_id: selectedResume.id,
          master_resume_id: selectedResume.source === "master" ? selectedResume.id : null,
        }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setExtractResult(data);
      // Pre-select priority keywords (ats_weight === 10)
      const priority = data.keywords
        .filter((k) => k.ats_weight === 10)
        .map((k) => k.keyword);
      setSelectedKeywords(priority);
      setStep(2);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // ── Step 2 → 3: generate resume ─────────────────────────────────────────
  async function handleGenerate(keywords) {
    setSelectedKeywords(keywords);
    setError(null);
    setLoading(true);

    try {
      const res = await fetch(`${API}/api/generate-resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_description: jobDescription,
          selected_keywords: keywords,
          resume_id: selectedResume.id,
          master_resume_id: selectedResume.source === "master" ? selectedResume.id : null,
          company,
          job_title: jobTitle,
          extracted_keywords_count: extractResult?.keywords?.length ?? 0,
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

  // ── Step 3: track inline edits from ResumePreview ───────────────────────
  function handleEdit(patch) {
    setEditedResumeData(patch);
  }

  // ── Reset to start ───────────────────────────────────────────────────────
  function handleReset() {
    setStep(0);
    setSelectedResume(null);
    setJobDescription("");
    setCompany("");
    setJobTitle("");
    setExtractResult(null);
    setSelectedKeywords([]);
    setGenerateResult(null);
    setEditedResumeData(null);
    setError(null);
  }

  // ── History view ─────────────────────────────────────────────────────────
  if (step === "history") {
    return <ResumeHistory onBack={() => setStep(0)} />;
  }

  async function handleMasterResumeSave(draft) {
    const url = masterResumeId
      ? `${API}/api/master-resumes/${masterResumeId}`
      : `${API}/api/master-resumes`;
    const response = await fetch(url, {
      method: masterResumeId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume: draft }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || `Server error ${response.status}`);
    }
    setResumeDraft(data.resume);
    setMasterResumeId(data.id);
    setSavedMasterResume(data);
    setStep("master-preview");
    return data;
  }

  if (step === "create-resume") {
    return (
      <ResumeBuilder
        apiBase={API}
        initialDraft={resumeDraft}
        onBack={() => setStep(0)}
        onSave={handleMasterResumeSave}
      />
    );
  }

  if (step === "master-preview" && savedMasterResume) {
    return (
      <MasterResumePreview
        resume={savedMasterResume.resume}
        savedAt={savedMasterResume.updated_at}
        onBack={() => setStep(0)}
        onEdit={() => setStep("create-resume")}
      />
    );
  }

  // ── Step router ──────────────────────────────────────────────────────────
  return (
    <div className="app-root">
      {/* Global nav bar */}
      <nav className="app-nav">
        <span className="app-nav-brand">ResuméBuddy</span>
        <button
          className="app-nav-history-btn"
          onClick={() => setStep("history")}
        >
          History
        </button>
      </nav>

      {/* Step indicator (steps 0–3 only) */}
      {typeof step === "number" && (
        <div className="app-step-bar">
          {["Profile", "Job Details", "Keywords", "Resume", "PDF"].map((label, i) => (
            <div
              key={label}
              className={`app-step ${
                i < step ? "app-step-done" :
                i === step ? "app-step-active" : ""
              }`}
            >
              <span className="app-step-dot">{i < step ? "✓" : i + 1}</span>
              <span className="app-step-label">{label}</span>
              {i < 4 && <span className="app-step-rule" />}
            </div>
          ))}
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="app-error-banner">
          {error}
          <button className="app-error-dismiss" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Views */}
      {step === 0 && (
        <ResumePicker
          apiBase={API}
          onCreate={handleCreateResume}
          onSelect={handleResumeSelect}
        />
      )}

      {step === 1 && (
        <JDInput
          onSubmit={handleExtract}
          onBack={() => setStep(0)}
          loading={loading}
          initialCompany={company}
          initialJobTitle={jobTitle}
          initialJD={jobDescription}
        />
      )}

      {step === 2 && extractResult && (
        <KeywordSelector
          extractResult={extractResult}
          selected={selectedKeywords}
          onChange={setSelectedKeywords}
          onGenerate={() => handleGenerate(selectedKeywords)}
          onBack={() => setStep(1)}
          loading={loading}
        />
      )}

      {step === 3 && generateResult && (
        <ResumePreview
          result={generateResult}
          apiBase={API}
          onBack={() => setStep(2)}
          onReset={handleReset}
          onPreviewPDF={() => setStep(4)}
          onEdit={handleEdit}
          editedResumeData={editedResumeData}
          jobDescription={jobDescription}
          selectedKeywords={selectedKeywords}
        />
      )}

      {step === 4 && generateResult && (
        <PDFPreview
          sessionId={generateResult.session_id}
          resumeData={editedResumeData}
          apiBase={API}
          onBack={() => setStep(3)}
          onReset={handleReset}
          company={company}
          jobTitle={jobTitle}
          personName={generateResult.person_name}
          onCoverLetter={() => setStep(5)}
        />
      )}
      {step === 5 && generateResult && (
        <CoverLetterStep
          tailoredResume={editedResumeData}
          sessionId={generateResult.session_id}
          candidateName={generateResult.person_name}
          historyId={generateResult.history_id}
          jobDescription={jobDescription}
          company={company}
          jobTitle={jobTitle}
          selectedKeywords={selectedKeywords}
          onBack={() => setStep(4)}
        />
      )}
    </div>
  );
}
