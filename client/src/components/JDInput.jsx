import { useState } from "react";
import "./JDInput.css";

export default function JDInput({
  onSubmit,
  onBack,
  loading,
  initialCompany = "",
  initialJobTitle = "",
  initialJD = "",
}) {
  const [jd, setJd] = useState(initialJD);
  const [company, setCompany] = useState(initialCompany);
  const [jobTitle, setJobTitle] = useState(initialJobTitle);

  const wordCount = jd.trim() ? jd.trim().split(/\s+/).length : 0;
  const charCount = jd.length;
  const canSubmit = wordCount >= 20 && charCount <= 20000 && !loading;

  function handleSubmit(e) {
    e.preventDefault();
    if (canSubmit) onSubmit(jd, company, jobTitle);
  }

  return (
    <div className="jdinput-page fade-up">
      <div className="jdinput-hero">
        <h1 className="jdinput-title">Paste the job description</h1>
        <p className="jdinput-sub">
          Claude will extract the keywords that matter most for ATS systems,
          then tailor your resume to match.
        </p>
      </div>

      <form className="jdinput-form card" onSubmit={handleSubmit}>
        <div className="jdinput-row">
          <div className="jdinput-field">
            <label className="jdinput-label" htmlFor="company">Company</label>
            <input
              id="company"
              className="jdinput-input"
              type="text"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="e.g. Acme Corp"
              disabled={loading}
            />
          </div>
          <div className="jdinput-field">
            <label className="jdinput-label" htmlFor="jobTitle">Job Title</label>
            <input
              id="jobTitle"
              className="jdinput-input"
              type="text"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              placeholder="e.g. Software Engineer"
              disabled={loading}
            />
          </div>
        </div>

        <div className="jdinput-field">
          <label className="jdinput-label" htmlFor="jd">Job Description</label>
          <textarea
            id="jd"
            className="jdinput-textarea"
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            placeholder="Paste the full job description here — responsibilities, requirements, and all..."
            rows={16}
            disabled={loading}
          />
          <div className="jdinput-meta">
            <span className={wordCount < 20 && jd ? "warn" : ""}>
              {wordCount} words{wordCount < 20 && jd ? " — add more for better results" : ""}
            </span>
            <span className={charCount > 18000 ? "warn" : ""}>
              {charCount.toLocaleString()} / 20,000 chars
            </span>
          </div>
        </div>

        <div className="jdinput-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onBack}
            disabled={loading}
          >
            ← Back
          </button>
          <button
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={!canSubmit}
          >
            {loading ? (
              <><span className="spinner" /> Extracting keywords…</>
            ) : (
              <>Extract Keywords →</>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
