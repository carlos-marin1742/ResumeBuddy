import { useState, useEffect } from "react";
import "./ResumePreview.css";

// Deep clone helper
function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

export default function ResumePreview({ result, apiBase, onBack, onReset, onPreviewPDF, onEdit }) {
  const { summary, experiences, projects = [], skills_to_highlight, ats, pdf_url, generated_at } = result;

  // ── Local editable state ──────────────────────────────────────────────────
  const [editSummary, setEditSummary] = useState(summary);
  const [editExperiences, setEditExperiences] = useState(() => deepClone(experiences));
  const [editProjects, setEditProjects] = useState(() => deepClone(projects));

  // Editing mode flags
  const [summaryEditing, setSummaryEditing] = useState(false);
  const [editingBullet, setEditingBullet] = useState(null); // { type: "exp"|"proj", company/name, index }

  const scoreColor =
    ats.overall_score >= 80 ? "score-high" :
    ats.overall_score >= 60 ? "score-mid"  : "score-low";

  const coveragePct = Math.round(ats.keyword_coverage * 100);

  // Sync edits upward to App whenever anything changes
  useEffect(() => {
    // Build a minimal resume data patch with edited text
    // Backend uses tailored_summary, experience[].bullets[].text
    const patch = {
      tailored_summary: editSummary,
      experience: editExperiences.map((exp) => ({
        company: exp.company,
        title: exp.title,
        bullets: exp.bullets.map((b) => ({
          text: b.tailored,
          original: b.original,
          keywords_injected: b.keywords_injected,
        })),
      })),
      projects: editProjects.map((proj) => ({
        name: proj.name,
        bullets: proj.bullets.map((b) => ({
          text: b.tailored,
          original: b.original,
          keywords_injected: b.keywords_injected,
        })),
      })),
    };
    onEdit(patch);
  }, [editSummary, editExperiences, editProjects]);

  // ── Summary edit ──────────────────────────────────────────────────────────
  function handleSummaryClick() {
    setSummaryEditing(true);
  }
  function handleSummaryBlur() {
    setSummaryEditing(false);
  }

  // ── Bullet edit ───────────────────────────────────────────────────────────
  function handleBulletClick(type, key, index) {
    setEditingBullet({ type, key, index });
  }

  function handleBulletChange(type, key, index, value) {
    if (type === "exp") {
      setEditExperiences((prev) => {
        const next = deepClone(prev);
        const exp = next.find((e) => e.company === key);
        if (exp) exp.bullets[index].tailored = value;
        return next;
      });
    } else {
      setEditProjects((prev) => {
        const next = deepClone(prev);
        const proj = next.find((p) => p.name === key);
        if (proj) proj.bullets[index].tailored = value;
        return next;
      });
    }
  }

  function handleBulletBlur() {
    setEditingBullet(null);
  }

  function isEditingBullet(type, key, index) {
    return editingBullet?.type === type &&
           editingBullet?.key === key &&
           editingBullet?.index === index;
  }

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
            <button className="btn btn-secondary" onClick={handleDownload}>
              ↓ Download PDF
            </button>
            <button className="btn btn-primary" onClick={onPreviewPDF}>
              Preview &amp; Adjust →
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
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                {!summaryEditing && (
                  <button
                    className="btn btn-ghost btn-sm rp-edit-btn"
                    onClick={handleSummaryClick}
                    title="Edit summary"
                  >
                    ✎ Edit
                  </button>
                )}
                <span className="rp-badge tailored">Tailored</span>
              </div>
            </div>
            {summaryEditing ? (
              <textarea
                className="rp-edit-textarea"
                value={editSummary}
                onChange={(e) => setEditSummary(e.target.value)}
                onBlur={handleSummaryBlur}
                autoFocus
                rows={4}
              />
            ) : (
              <p
                className="rp-summary-text rp-editable"
                onClick={handleSummaryClick}
                title="Click to edit"
              >
                {editSummary}
              </p>
            )}
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
          {editExperiences.map((exp) => (
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
                      {isEditingBullet("exp", exp.company, i) ? (
                        <textarea
                          className="rp-edit-textarea"
                          value={b.tailored}
                          onChange={(e) => handleBulletChange("exp", exp.company, i, e.target.value)}
                          onBlur={handleBulletBlur}
                          autoFocus
                          rows={2}
                        />
                      ) : (
                        <p
                          className="rp-editable"
                          onClick={() => handleBulletClick("exp", exp.company, i)}
                          title="Click to edit"
                        >
                          {b.tailored}
                        </p>
                      )}
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

          {/* Project bullets */}
          {editProjects.length > 0 && (
            <>
              <div className="rp-section-divider"><span>Projects</span></div>
              {editProjects.map((proj) => (
                <section key={proj.name} className="rp-section card">
                  <div className="rp-section-header">
                    <div>
                      <span className="rp-section-title">{proj.name}</span>
                    </div>
                    <span className="rp-badge tailored">Tailored</span>
                  </div>
                  <div className="rp-bullets">
                    {proj.bullets.map((b, i) => (
                      <div key={i} className="rp-bullet">
                        <div className="rp-bullet-new">
                          <span className="rp-bullet-label">After</span>
                          {isEditingBullet("proj", proj.name, i) ? (
                            <textarea
                              className="rp-edit-textarea"
                              value={b.tailored}
                              onChange={(e) => handleBulletChange("proj", proj.name, i, e.target.value)}
                              onBlur={handleBulletBlur}
                              autoFocus
                              rows={2}
                            />
                          ) : (
                            <p
                              className="rp-editable"
                              onClick={() => handleBulletClick("proj", proj.name, i)}
                              title="Click to edit"
                            >
                              {b.tailored}
                            </p>
                          )}
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
            </>
          )}

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

          {/* Preview & Download */}
          <button className="btn btn-primary rp-download-btn" onClick={onPreviewPDF}>
            Preview &amp; Adjust →
          </button>
          <button className="btn btn-secondary rp-download-btn" onClick={handleDownload}>
            ↓ Download PDF
          </button>
        </aside>
      </div>
    </div>
  );
}