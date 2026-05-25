import "./ResumePreview.css";

export default function ResumePreview({ result, apiBase, onBack, onReset }) {
  const { summary, experiences, skills_to_highlight, ats, pdf_url, generated_at } = result;

  const scoreColor =
    ats.overall_score >= 80 ? "score-high" :
    ats.overall_score >= 60 ? "score-mid"  : "score-low";

  const coveragePct = Math.round(ats.keyword_coverage * 100);

  function handleDownload() {
    window.open(`${apiBase}${pdf_url}`, "_blank");
  }

  return (
    <div className="rp-page fade-up">
      {/* ── Top bar ── */}
      <div className="rp-topbar">
        <div className="rp-topbar-inner">
          <div className="rp-topbar-left">
            <button className="btn btn-ghost btn-sm" onClick={onBack}>← Back</button>
            <span className="rp-generated">
              Generated {new Date(generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
          <div className="rp-topbar-right">
            <button className="btn btn-secondary btn-sm" onClick={onReset}>
              Start over
            </button>
            <button className="btn btn-primary" onClick={handleDownload}>
              ↓ Download PDF
            </button>
          </div>
        </div>
      </div>

      <div className="rp-layout">
        {/* ── Left: resume content preview ── */}
        <div className="rp-main">

          {/* Summary */}
          <section className="rp-section card">
            <div className="rp-section-header">
              <span className="rp-section-title">Summary</span>
              <span className="rp-badge tailored">Tailored</span>
            </div>
            <p className="rp-summary-text">{summary}</p>
          </section>

          {/* Skills */}
          {skills_to_highlight.length > 0 && (
            <section className="rp-section card">
              <div className="rp-section-header">
                <span className="rp-section-title">Skills to Highlight</span>
                <span className="rp-badge highlighted">Top picks</span>
              </div>
              <div className="rp-skill-chips">
                {skills_to_highlight.map((s) => (
                  <span key={s} className="rp-skill-chip">{s}</span>
                ))}
              </div>
            </section>
          )}

          {/* Experience bullets */}
          {experiences.map((exp) => (
            <section key={exp.company} className="rp-section card">
              <div className="rp-section-header">
                <div>
                  <span className="rp-section-title">{exp.title}</span>
                  <span className="rp-section-sub"> · {exp.company}</span>
                </div>
                <span className="rp-badge tailored">Tailored</span>
              </div>
              <div className="rp-bullets">
                {exp.bullets.map((b, i) => (
                  <div key={i} className="rp-bullet">
                    <div className="rp-bullet-new">
                      <span className="rp-bullet-label">After</span>
                      <p>{b.tailored}</p>
                      {b.keywords_injected.length > 0 && (
                        <div className="rp-injected">
                          {b.keywords_injected.map((kw) => (
                            <span key={kw} className="rp-injected-chip">{kw}</span>
                          ))}
                        </div>
                      )}
                    </div>
                    {b.original !== b.tailored && (
                      <div className="rp-bullet-old">
                        <span className="rp-bullet-label muted">Before</span>
                        <p>{b.original}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>

        {/* ── Right: ATS score sidebar ── */}
        <aside className="rp-sidebar">
          {/* Score card */}
          <div className={`rp-score-card card ${scoreColor}`}>
            <p className="rp-score-label">ATS Score</p>
            <div className="rp-score-ring-wrap">
              <svg className="rp-score-ring" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="34" className="rp-ring-bg" />
                <circle
                  cx="40" cy="40" r="34"
                  className="rp-ring-fill"
                  strokeDasharray={`${2 * Math.PI * 34}`}
                  strokeDashoffset={`${2 * Math.PI * 34 * (1 - ats.overall_score / 100)}`}
                />
              </svg>
              <span className="rp-score-num">{ats.overall_score}</span>
            </div>
            <p className="rp-coverage">
              Keyword coverage: <strong>{coveragePct}%</strong>
            </p>
          </div>

          {/* Matched keywords */}
          {ats.matched_keywords.length > 0 && (
            <div className="rp-ats-card card">
              <p className="rp-ats-card-title match">✓ Matched keywords</p>
              <div className="rp-ats-chips">
                {ats.matched_keywords.map((kw) => (
                  <span key={kw} className="rp-ats-chip match">{kw}</span>
                ))}
              </div>
            </div>
          )}

          {/* Missing keywords */}
          {ats.missing_keywords.length > 0 && (
            <div className="rp-ats-card card">
              <p className="rp-ats-card-title missing">✕ Still missing</p>
              <div className="rp-ats-chips">
                {ats.missing_keywords.map((kw) => (
                  <span key={kw} className="rp-ats-chip missing">{kw}</span>
                ))}
              </div>
            </div>
          )}

          {/* Suggestions */}
          {ats.suggestions.length > 0 && (
            <div className="rp-suggestions card">
              <p className="rp-suggestions-title">Suggestions</p>
              <ul className="rp-suggestions-list">
                {ats.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Download */}
          <button className="btn btn-primary rp-download-btn" onClick={handleDownload}>
            ↓ Download PDF
          </button>
        </aside>
      </div>
    </div>
  );
}