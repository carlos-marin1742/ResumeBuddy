import "./JDInput.css";

export default function JDInput({ value, onChange, onSubmit, loading }) {
  const wordCount = value.trim() ? value.trim().split(/\s+/).length : 0;
  const charCount = value.length;
  const canSubmit = wordCount >= 20 && charCount <= 20000 && !loading;

  function handleSubmit(e) {
    e.preventDefault();
    if (canSubmit) onSubmit(value);
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
        <div className="jdinput-field">
          <label className="jdinput-label" htmlFor="jd">
            Job Description
          </label>
          <textarea
            id="jd"
            className="jdinput-textarea"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Paste the full job description here — responsibilities, requirements, and all..."
            rows={16}
            disabled={loading}
          />
          <div className="jdinput-meta">
            <span className={wordCount < 20 && value ? "warn" : ""}>
              {wordCount} words{wordCount < 20 && value ? " — add more for better results" : ""}
            </span>
            <span className={charCount > 18000 ? "warn" : ""}>
              {charCount.toLocaleString()} / 20,000 chars
            </span>
          </div>
        </div>

        <div className="jdinput-actions">
          <p className="jdinput-hint">
            Tip: include the full posting, not just the requirements section.
          </p>
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