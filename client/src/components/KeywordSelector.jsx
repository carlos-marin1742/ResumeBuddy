import "./KeywordSelector.css";

const CATEGORY_LABELS = {
  hard_skill:  "Hard Skills & Tools",
  soft_skill:  "Soft Skills",
  role_signal: "Role Signals",
};

export default function KeywordSelector({
  extractResult,
  selected,
  onChange,
  onBack,
  onGenerate,
  loading,
}) {
  const { keywords = [], role_level, gaps = [] } = extractResult;

  // Group keywords by category
  const grouped = keywords.reduce((acc, kw) => {
    const cat = kw.category || "hard_skill";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(kw);
    return acc;
  }, {});

  function toggle(keyword) {
    onChange(
      selected.includes(keyword)
        ? selected.filter((k) => k !== keyword)
        : [...selected, keyword]
    );
  }

  function selectAll() {
    onChange(keywords.map((k) => k.keyword));
  }

  function selectGaps() {
    onChange(keywords.filter((k) => !k.present_in_resume).map((k) => k.keyword));
  }

  function clearAll() {
    onChange([]);
  }

  const gapCount = gaps.length;
  const matchCount = keywords.filter((k) => k.present_in_resume).length;

  return (
    <div className="ks-page fade-up">
      {/* ── Summary bar ── */}
      <div className="ks-summary">
        <div className="ks-summary-inner">
          <div className="ks-stat">
            <span className="ks-stat-val">{keywords.length}</span>
            <span className="ks-stat-label">Keywords found</span>
          </div>
          <div className="ks-divider" />
          <div className="ks-stat">
            <span className="ks-stat-val match">{matchCount}</span>
            <span className="ks-stat-label">Already in your resume</span>
          </div>
          <div className="ks-divider" />
          <div className="ks-stat">
            <span className="ks-stat-val gap">{gapCount}</span>
            <span className="ks-stat-label">Gaps to address</span>
          </div>
          <div className="ks-divider" />
          <div className="ks-stat">
            <span className="ks-stat-val">{role_level}</span>
            <span className="ks-stat-label">Role level</span>
          </div>
        </div>
      </div>

      <div className="ks-layout">
        {/* ── Left: keyword groups ── */}
        <div className="ks-main">
          <div className="ks-toolbar">
            <h2 className="ks-heading">Select keywords to target</h2>
            <div className="ks-toolbar-actions">
              <button className="btn btn-ghost btn-sm" onClick={selectAll}>All</button>
              <button className="btn btn-ghost btn-sm" onClick={selectGaps}>Gaps only</button>
              <button className="btn btn-ghost btn-sm" onClick={clearAll}>Clear</button>
            </div>
          </div>

          {Object.entries(CATEGORY_LABELS).map(([cat, label]) => {
            const items = grouped[cat];
            if (!items || items.length === 0) return null;
            return (
              <div key={cat} className="ks-group card">
                <div className="ks-group-header">
                  <span className="ks-group-label">{label}</span>
                  <span className="ks-group-count">{items.length}</span>
                </div>
                <div className="ks-chips">
                  {items.map((kw) => {
                    const isSelected = selected.includes(kw.keyword);
                    const isGap = !kw.present_in_resume;
                    return (
                      <button
                        key={kw.keyword}
                        className={[
                          "ks-chip",
                          isSelected ? "selected" : "",
                          isGap ? "gap" : "match",
                        ].join(" ")}
                        onClick={() => toggle(kw.keyword)}
                        title={`ATS weight: ${kw.ats_weight}/10 · ${isGap ? "Not in your resume" : "Already in your resume"}`}
                      >
                        <span className="ks-chip-dot" />
                        {kw.keyword}
                        <span className="ks-chip-weight">{kw.ats_weight}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* ── Right: sidebar ── */}
        <aside className="ks-sidebar">
          <div className="ks-selection-card card">
            <div className="ks-selection-header">
              <span className="ks-selection-title">Selected</span>
              <span className="ks-selection-count">{selected.length}</span>
            </div>
            <div className="ks-selected-list">
              {selected.length === 0 ? (
                <p className="ks-empty">No keywords selected yet.</p>
              ) : (
                selected.map((kw) => (
                  <div key={kw} className="ks-selected-item">
                    <span>{kw}</span>
                    <button onClick={() => toggle(kw)} className="ks-remove">✕</button>
                  </div>
                ))
              )}
            </div>
          </div>

          {gapCount > 0 && (
            <div className="ks-gap-card card">
              <p className="ks-gap-title">⚠ {gapCount} gap{gapCount !== 1 ? "s" : ""} detected</p>
              <p className="ks-gap-body">
                These keywords appear in the JD but not in your base resume.
                Claude will weave them in naturally where your experience supports it.
              </p>
            </div>
          )}
        </aside>
      </div>

      {/* ── Footer actions ── */}
      <div className="ks-footer">
        <button className="btn btn-secondary" onClick={onBack} disabled={loading}>
          ← Back
        </button>
        <div className="ks-footer-right">
          <span className="ks-footer-hint">
            {selected.length} keyword{selected.length !== 1 ? "s" : ""} selected
          </span>
          <button
            className="btn btn-primary btn-lg"
            onClick={onGenerate}
            disabled={selected.length === 0 || loading}
          >
            {loading ? (
              <><span className="spinner" /> Generating resume…</>
            ) : (
              <>Generate Resume →</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}