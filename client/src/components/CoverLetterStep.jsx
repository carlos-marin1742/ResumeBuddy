import { useState } from "react";
import "./CoverLetterStep.css";

/**
 * CoverLetterStep
 * ---------------
 * Optional step 4. Generates a cover letter grounded in the tailored
 * resume output, with edit-in-place and copy-to-clipboard.
 *
 * Props:
 *   tailoredResume    - TailoredResume object from /api/generate-resume
 *   candidateName     - user's name from the generated resume
 *   jobDescription    - the JD text from step 0
 *   company           - company name from App state
 *   jobTitle          - job title from App state
 *   selectedKeywords  - keywords confirmed in KeywordSelector
 *   onBack            - () => void, return to ResumePreview
 */
export default function CoverLetterStep({
  tailoredResume,
  sessionId,
  candidateName,
  jobDescription,
  company,
  jobTitle,
  selectedKeywords,
  onBack,
}) {
  const [letter, setLetter] = useState("");
  const [wordCount, setWordCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const generate = async () => {
    setLoading(true);
    setError(null);
    setCopied(false);
    try {
      const res = await fetch("/api/generate-cover-letter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tailored_resume: tailoredResume || null,
          session_id: sessionId || null,
          candidate_name: candidateName || "",
          job_description: jobDescription,
          company: company || "",
          job_title: jobTitle || "",
          selected_keywords: selectedKeywords || [],
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `Request failed (${res.status})`);
      }
      const data = await res.json();
      setLetter(data.letter);
      setWordCount(data.word_count);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (e) => {
    const text = e.target.value;
    setLetter(text);
    setWordCount(text.trim() ? text.trim().split(/\s+/).length : 0);
    setCopied(false);
  };

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(letter);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Couldn't access clipboard. Select and copy manually.");
    }
  };

  return (
    <div className="cover-letter-step">
      <div className="cl-header">
        <h2>Cover Letter</h2>
        {company && jobTitle && (
          <p className="cl-context">
            {jobTitle} · {company}
          </p>
        )}
      </div>

      {!letter && !loading && (
        <div className="cl-empty">
          <p>
            Generate a cover letter grounded in your tailored resume —
            it will only reference accomplishments from the version you
            just built.
          </p>
          <button className="cl-btn cl-btn-primary" onClick={generate}>
            Generate Cover Letter
          </button>
        </div>
      )}

      {loading && (
        <div className="cl-loading">
          <div className="cl-spinner" />
          <p>Writing your cover letter…</p>
        </div>
      )}

      {error && <div className="cl-error">{error}</div>}

      {letter && !loading && (
        <>
          <div className="cl-toolbar">
            <span className={`cl-wordcount ${wordCount > 250 ? "over" : ""}`}>
              {wordCount} words
            </span>
            <div className="cl-actions">
              <button className="cl-btn" onClick={generate}>
                Regenerate
              </button>
              <button className="cl-btn cl-btn-primary" onClick={copyToClipboard}>
                {copied ? "Copied ✓" : "Copy to Clipboard"}
              </button>
            </div>
          </div>
          <textarea
            className="cl-textarea"
            value={letter}
            onChange={handleEdit}
            spellCheck="true"
          />
        </>
      )}

      <div className="cl-footer">
        <button className="cl-btn cl-btn-ghost" onClick={onBack}>
          ← Back to Resume
        </button>
      </div>
    </div>
  );
}
