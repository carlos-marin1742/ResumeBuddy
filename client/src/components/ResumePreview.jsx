import { useState, useEffect } from "react";
import "./ResumePreview.css";

function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

export default function ResumePreview({
  result,
  apiBase,
  onBack,
  onReset,
  onPreviewPDF,
  onEdit,
  jobDescription,
  selectedKeywords,
}) {
  const { summary, experiences, projects = [], skills_to_highlight, pdf_url, generated_at } = result;

  // ── Editable content state ────────────────────────────────────────────────
  const [editSummary, setEditSummary] = useState(summary);
  const [editExperiences, setEditExperiences] = useState(() => deepClone(experiences));
  const [editProjects, setEditProjects] = useState(() => deepClone(projects));
  const [atsState, setAtsState] = useState(result.ats);

  // ── Inline edit mode ──────────────────────────────────────────────────────
  const [summaryEditing, setSummaryEditing] = useState(false);
  const [editingBullet, setEditingBullet] = useState(null);

  // ── Regenerate panel state ────────────────────────────────────────────────
  // { type: "summary" | "exp" | "proj", key: company|name|null }
  const [regenPanel, setRegenPanel] = useState(null);
  const [regenFeedback, setRegenFeedback] = useState("");
  const [regenLoading, setRegenLoading] = useState(false);
  const [regenError, setRegenError] = useState(null);

  const scoreColor =
    atsState.overall_score >= 80 ? "score-high" :
    atsState.overall_score >= 60 ? "score-mid"  : "score-low";

  const coveragePct = Math.round(atsState.keyword_coverage * 100);

  // Sync edits upward to App
  useEffect(() => {
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

  // ── Inline edit handlers ──────────────────────────────────────────────────
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

  function isEditingBullet(type, key, index) {
    return editingBullet?.type === type &&
           editingBullet?.key === key &&
           editingBullet?.index === index;
  }

  // ── Regenerate handlers ───────────────────────────────────────────────────
  function openRegenPanel(type, key = null) {
    // Close inline edit if open
    setSummaryEditing(false);
    setEditingBullet(null);
    setRegenError(null);
    setRegenFeedback("");
    setRegenPanel({ type, key });
  }

  function closeRegenPanel() {
    setRegenPanel(null);
    setRegenFeedback("");
    setRegenError(null);
  }

  async function handleRegenerate() {
    setRegenLoading(true);
    setRegenError(null);

    const sectionMap = { summary: "summary", exp: "experience", proj: "project" };

    try {
      const res = await fetch(`${apiBase}/api/regenerate-section`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: result.session_id,
          section: sectionMap[regenPanel.type],
          target: regenPanel.key,
          feedback: regenFeedback,
          job_description: jobDescription,
          selected_keywords: selectedKeywords,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${res.status}`);
      }

      const data = await res.json();

      if (regenPanel.type === "summary") {
        setEditSummary(data.summary);
      } else if (regenPanel.type === "exp") {
        setEditExperiences((prev) => {
          const next = deepClone(prev);
          const exp = next.find((e) => e.company === regenPanel.key);
          if (exp && data.bullets) {
            exp.bullets = data.bullets.map((b) => ({
              original: b.original,
              tailored: b.tailored,
              keywords_injected: b.keywords_injected,
            }));
          }
          return next;
        });
      } else if (regenPanel.type === "proj") {
        setEditProjects((prev) => {
          const next = deepClone(prev);
          const proj = next.find((p) => p.name === regenPanel.key);
          if (proj && data.bullets) {
            proj.bullets = data.bullets.map((b) => ({
              original: b.original,
              tailored: b.tailored,
              keywords_injected: b.keywords_injected,
            }));
          }
          return next;
        });
      }

      setAtsState(data.ats);
      closeRegenPanel();
    } catch (e) {
      setRegenError(e.message);
    } finally {
      setRegenLoading(false);
    }
  }

  function handleDownload() {
    window.open(`${apiBase}${pdf_url}`, "_blank");
  }

  const regenPanelJSX = regenPanel ? (
    <div className="rp-regen-panel">
      <textarea
        className="rp-regen-textarea"
        placeholder='Optional: add instructions (e.g. "focus on leadership", "more technical")'
        value={regenFeedback}
        onChange={(e) => setRegenFeedback(e.target.value)}
        rows={2}
        disabled={regenLoading}
      />
      {regenError && <p className="rp-regen-error">{regenError}</p>}
      <div className="rp-regen-actions">
        <button className="btn btn-ghost btn-sm" onClick={closeRegenPanel} disabled={regenLoading}>
          Cancel
        </button>
        <button
          className="btn btn-primary btn-sm rp-regen-submit"
          onClick={handleRegenerate}
          disabled={regenLoading}
        >
          {regenLoading ? (
            <><span className="rp-spinner" /> Regenerating…</>
          ) : (
            "↺ Regenerate"
          )}
        </button>
      </div>
    </div>
  ) : null;

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
                <button
                  className="btn btn-ghost btn-sm rp-regen-btn"
                  onClick={() => regenPanel?.type === "summary" ? closeRegenPanel() : openRegenPanel("summary")}
                  title="Regenerate summary with AI"
                >
                  ↺ Regenerate
                </button>
                {!summaryEditing && (
                  <button
                    className="btn btn-ghost btn-sm rp-edit-btn"
                    onClick={() => { closeRegenPanel(); setSummaryEditing(true); }}
                    title="Edit summary"
                  >
                    ✎ Edit
                  </button>
                )}
                <span className="rp-badge tailored">Tailored</span>
              </div>
            </div>
            {regenPanel?.type === "summary" && regenPanelJSX}
            {summaryEditing ? (
              <textarea
                className="rp-edit-textarea"
                value={editSummary}
                onChange={(e) => setEditSummary(e.target.value)}
                onBlur={() => setSummaryEditing(false)}
                autoFocus
                rows={4}
              />
            ) : (
              <p
                className="rp-summary-text rp-editable"
                onClick={() => { closeRegenPanel(); setSummaryEditing(true); }}
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
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <button
                    className="btn btn-ghost btn-sm rp-regen-btn"
                    onClick={() =>
                      regenPanel?.type === "exp" && regenPanel?.key === exp.company
                        ? closeRegenPanel()
                        : openRegenPanel("exp", exp.company)
                    }
                    title="Regenerate bullets with AI"
                  >
                    ↺ Regenerate
                  </button>
                  <span className="rp-badge tailored">Tailored</span>
                </div>
              </div>
              {regenPanel?.type === "exp" && regenPanel?.key === exp.company && regenPanelJSX}
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
                          onBlur={() => setEditingBullet(null)}
                          autoFocus
                          rows={2}
                        />
                      ) : (
                        <p
                          className="rp-editable"
                          onClick={() => { closeRegenPanel(); setEditingBullet({ type: "exp", key: exp.company, index: i }); }}
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
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <button
                        className="btn btn-ghost btn-sm rp-regen-btn"
                        onClick={() =>
                          regenPanel?.type === "proj" && regenPanel?.key === proj.name
                            ? closeRegenPanel()
                            : openRegenPanel("proj", proj.name)
                        }
                        title="Regenerate bullets with AI"
                      >
                        ↺ Regenerate
                      </button>
                      <span className="rp-badge tailored">Tailored</span>
                    </div>
                  </div>
                  {regenPanel?.type === "proj" && regenPanel?.key === proj.name && regenPanelJSX}
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
                              onBlur={() => setEditingBullet(null)}
                              autoFocus
                              rows={2}
                            />
                          ) : (
                            <p
                              className="rp-editable"
                              onClick={() => { closeRegenPanel(); setEditingBullet({ type: "proj", key: proj.name, index: i }); }}
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
          <div className={`rp-score-card card ${scoreColor}`}>
            <p className="rp-score-label">ATS Score</p>
            <div className="rp-score-ring-wrap">
              <svg className="rp-score-ring" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="34" className="rp-ring-bg" />
                <circle
                  cx="40" cy="40" r="34"
                  className="rp-ring-fill"
                  strokeDasharray={`${2 * Math.PI * 34}`}
                  strokeDashoffset={`${2 * Math.PI * 34 * (1 - atsState.overall_score / 100)}`}
                />
              </svg>
              <span className="rp-score-num">{atsState.overall_score}</span>
            </div>
            <p className="rp-coverage">
              Keyword coverage: <strong>{coveragePct}%</strong>
            </p>
          </div>

          {atsState.matched_keywords.length > 0 && (
            <div className="rp-ats-card card">
              <p className="rp-ats-card-title match">✓ Matched keywords</p>
              <div className="rp-ats-chips">
                {atsState.matched_keywords.map((kw) => (
                  <span key={kw} className="rp-ats-chip match">{kw}</span>
                ))}
              </div>
            </div>
          )}

          {atsState.missing_keywords.length > 0 && (
            <div className="rp-ats-card card">
              <p className="rp-ats-card-title missing">✕ Still missing</p>
              <div className="rp-ats-chips">
                {atsState.missing_keywords.map((kw) => (
                  <span key={kw} className="rp-ats-chip missing">{kw}</span>
                ))}
              </div>
            </div>
          )}

          {atsState.suggestions.length > 0 && (
            <div className="rp-suggestions card">
              <p className="rp-suggestions-title">Suggestions</p>
              <ul className="rp-suggestions-list">
                {atsState.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}

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
