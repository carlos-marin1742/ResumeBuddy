import { useState, useEffect, useCallback } from "react";
import PDFPreview from "./PDFPreview";
import "./ResumeHistory.css";

const API = "http://127.0.0.1:8000";

const PROFILE_LABELS = {
  base_resume:    "Tech / AI",
  base_resume_cl: "Clinical",
  base_resume_ad: "Admin",
};

function ScoreBadge({ score }) {
  const tier =
    score >= 80 ? "score-high" :
    score >= 60 ? "score-mid"  : "score-low";
  return <span className={`rh-score-badge ${tier}`}>{score}</span>;
}

function EmptyState() {
  return (
    <div className="rh-empty">
      <div className="rh-empty-icon">📄</div>
      <p className="rh-empty-heading">No resumes yet</p>
      <p className="rh-empty-sub">
        Generate your first tailored resume and it will appear here.
      </p>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div className="rh-row rh-row-skeleton">
      <div className="rh-skeleton rh-sk-company" />
      <div className="rh-skeleton rh-sk-title" />
      <div className="rh-skeleton rh-sk-profile" />
      <div className="rh-skeleton rh-sk-date" />
      <div className="rh-skeleton rh-sk-score" />
      <div className="rh-skeleton rh-sk-actions" />
    </div>
  );
}

// ── Full-page detail view ──────────────────────────────────────────────────

function HistoryDetail({ record, onBack }) {
  const [mode, setMode]           = useState("info"); // "info" | "preview"
  const [sessionId, setSessionId] = useState(null);
  const [restoring, setRestoring] = useState(false);
  const [error, setError]         = useState(null);

  async function handlePreview() {
    setRestoring(true);
    setError(null);
    try {
      const r = await fetch(`${API}/api/history/${record.id}/restore`, { method: "POST" });
      if (!r.ok) throw new Error(`Server error ${r.status}`);
      const data = await r.json();
      setSessionId(data.session_id);
      setMode("preview");
    } catch (e) {
      setError(e.message);
    } finally {
      setRestoring(false);
    }
  }

  if (mode === "preview" && sessionId) {
    return (
      <PDFPreview
        sessionId={sessionId}
        resumeData={null}
        apiBase={API}
        onBack={() => setMode("info")}
        onReset={null}
        topOffset={0}
        title={record.company}
      />
    );
  }

  const profileLabel = PROFILE_LABELS[record.profile] ?? record.profile;
  const date = new Date(record.created_at).toLocaleDateString("en-US", {
    month: "long", day: "numeric", year: "numeric",
  });

  const coveragePct = record.ats_keyword_coverage != null
    ? Math.round(record.ats_keyword_coverage * 100)
    : null;

  const selectedCount = record.selected_keywords?.length ?? 0;
  const matchedCount  = record.matched_keywords?.length ?? 0;

  return (
    <div className="rh-detail">
      <div className="rh-detail-topbar">
        <button className="rh-back-btn" onClick={onBack}>← Back to History</button>
      </div>

      <div className="rh-detail-head">
        <h1 className="rh-detail-company">{record.company}</h1>
        {record.job_title && <p className="rh-detail-role">{record.job_title}</p>}
        <p className="rh-detail-meta">
          <span>{date}</span>
          <span className="rh-detail-dot">·</span>
          <span className="rh-profile-chip">{profileLabel}</span>
        </p>
      </div>

      {/* ── Stats grid ── */}
      {record.ats_overall_score != null && (
        <div className="rh-stats-grid">
          <div className="rh-stat-card">
            <span className="rh-stat-label">ATS Score</span>
            <ScoreBadge score={record.ats_overall_score} />
          </div>
          {coveragePct != null && (
            <div className="rh-stat-card">
              <span className="rh-stat-label">Keyword Coverage</span>
              <span className="rh-stat-value">{coveragePct}%</span>
            </div>
          )}
          <div className="rh-stat-card">
            <span className="rh-stat-label">Keywords Selected</span>
            <span className="rh-stat-value">{selectedCount}</span>
          </div>
          <div className="rh-stat-card">
            <span className="rh-stat-label">Keywords Applied</span>
            <span className="rh-stat-value">{matchedCount}</span>
          </div>
        </div>
      )}

      {/* ── Selected keywords ── */}
      {selectedCount > 0 && (
        <div className="rh-detail-section">
          <p className="rh-detail-section-label">Keywords Selected ({selectedCount})</p>
          <div className="rh-kw-chips">
            {record.selected_keywords.map((kw) => (
              <span
                key={kw}
                className={`rh-kw-chip ${record.matched_keywords?.includes(kw) ? "rh-kw-matched" : "rh-kw-missing"}`}
              >
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Matched keywords ── */}
      {matchedCount > 0 && (
        <div className="rh-detail-section">
          <p className="rh-detail-section-label">Keywords Applied ({matchedCount})</p>
          <div className="rh-kw-chips">
            {record.matched_keywords.map((kw) => (
              <span key={kw} className="rh-kw-chip rh-kw-matched">{kw}</span>
            ))}
          </div>
        </div>
      )}

      {/* ── Job description ── */}
      {record.job_description && (
        <div className="rh-detail-section">
          <p className="rh-detail-section-label">Job Description</p>
          <p className="rh-detail-jd">{record.job_description}</p>
        </div>
      )}

      {error && <p className="rh-detail-error-msg">⚠ Could not load preview — {error}</p>}

      <div className="rh-detail-actions">
        <button
          className="btn btn-primary"
          onClick={handlePreview}
          disabled={restoring}
        >
          {restoring ? <><span className="spinner" /> Loading…</> : "Preview Resume"}
        </button>
        {record.pdf_path && (
          <a
            className="btn btn-secondary"
            href={`${API}/api/download-history/${record.id}`}
            target="_blank"
            rel="noreferrer"
          >
            ↓ Download PDF
          </a>
        )}
      </div>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

export default function ResumeHistory({ onBack }) {
  const [records, setRecords]         = useState([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState(null);
  const [detailRecord, setDetailRecord] = useState(null);
  const [deleting, setDeleting]       = useState(null);
  const [filterProfile, setFilterProfile] = useState("all");
  const [sortBy, setSortBy]           = useState("date");
  const [search, setSearch]           = useState("");

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/history`);
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();
      setRecords(data.records ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Remove this resume from history?")) return;
    setDeleting(id);
    try {
      const res = await fetch(`${API}/api/history/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`Delete failed (${res.status})`);
      setRecords(prev => prev.filter(r => r.id !== id));
      if (detailRecord?.id === id) setDetailRecord(null);
    } catch (err) {
      alert(`Could not delete: ${err.message}`);
    } finally {
      setDeleting(null);
    }
  };

  if (detailRecord) {
    return <HistoryDetail record={detailRecord} onBack={() => setDetailRecord(null)} />;
  }

  const q = search.trim().toLowerCase();
  const visible = records
    .filter(r => filterProfile === "all" || r.profile === filterProfile)
    .filter(r => !q || r.company.toLowerCase().includes(q) || r.job_title.toLowerCase().includes(q))
    .sort((a, b) => {
      if (sortBy === "score")   return (b.ats_overall_score ?? 0) - (a.ats_overall_score ?? 0);
      if (sortBy === "company") return a.company.localeCompare(b.company);
      return new Date(b.created_at) - new Date(a.created_at);
    });

  const profiles = [...new Set(records.map(r => r.profile))];

  return (
    <div className="rh-root">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="rh-header">
        <button className="rh-back-btn" onClick={onBack}>← Back</button>
        <div className="rh-header-text">
          <h1 className="rh-heading">Resume History</h1>
          <p className="rh-subheading">
            {q || filterProfile !== "all"
              ? `${visible.length} of ${records.length} resumes`
              : `${records.length} ${records.length === 1 ? "resume" : "resumes"} generated`}
          </p>
        </div>
      </header>

      {/* ── Controls ────────────────────────────────────────────────────── */}
      {records.length > 0 && (
        <div className="rh-controls">
          <div className="rh-search-wrap">
            <span className="rh-search-icon">⌕</span>
            <input
              className="rh-search"
              type="search"
              placeholder="Search company or role…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          <div className="rh-filter-group">
            <label className="rh-control-label">Profile</label>
            <select
              className="rh-select"
              value={filterProfile}
              onChange={e => setFilterProfile(e.target.value)}
            >
              <option value="all">All</option>
              {profiles.map(p => (
                <option key={p} value={p}>{PROFILE_LABELS[p] ?? p}</option>
              ))}
            </select>
          </div>

          <div className="rh-filter-group">
            <label className="rh-control-label">Sort by</label>
            <select
              className="rh-select"
              value={sortBy}
              onChange={e => setSortBy(e.target.value)}
            >
              <option value="date">Date</option>
              <option value="score">ATS Score</option>
              <option value="company">Company</option>
            </select>
          </div>
        </div>
      )}

      {/* ── Table ───────────────────────────────────────────────────────── */}
      <main className="rh-main">
        {error && (
          <div className="rh-error">
            Could not load history — {error}.{" "}
            <button className="rh-retry-btn" onClick={fetchHistory}>Retry</button>
          </div>
        )}

        {loading && !error && (
          <div className="rh-list">
            <div className="rh-list-header">
              <span>Company</span><span>Role</span><span>Profile</span>
              <span>Date</span><span>Score</span><span />
            </div>
            {[1,2,3].map(i => <SkeletonRow key={i} />)}
          </div>
        )}

        {!loading && !error && visible.length === 0 && records.length === 0 && <EmptyState />}

        {!loading && !error && visible.length === 0 && records.length > 0 && (
          <div className="rh-no-results">
            No resumes match <strong>&quot;{search}&quot;</strong>.
          </div>
        )}

        {!loading && !error && visible.length > 0 && (
          <div className="rh-list">
            <div className="rh-list-header">
              <span>Company</span><span>Role</span><span>Profile</span>
              <span>Date</span><span>Score</span><span>Keywords</span><span />
            </div>

            {visible.map(record => {
              const coveragePct = record.ats_keyword_coverage != null
                ? Math.round(record.ats_keyword_coverage * 100)
                : null;
              const selectedCount = record.selected_keywords?.length ?? 0;
              const matchedCount  = record.matched_keywords?.length ?? 0;

              return (
                <div
                  key={record.id}
                  className="rh-row"
                  onClick={() => setDetailRecord(record)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={e => e.key === "Enter" && setDetailRecord(record)}
                >
                  <span className="rh-cell rh-cell-company">{record.company}</span>
                  <span className="rh-cell rh-cell-title">{record.job_title}</span>
                  <span className="rh-cell">
                    <span className="rh-profile-chip">
                      {PROFILE_LABELS[record.profile] ?? record.profile}
                    </span>
                  </span>
                  <span className="rh-cell rh-cell-date">
                    {new Date(record.created_at).toLocaleDateString("en-US", {
                      month: "short", day: "numeric", year: "numeric",
                    })}
                  </span>
                  <span className="rh-cell rh-cell-score-col">
                    {record.ats_overall_score != null
                      ? <ScoreBadge score={record.ats_overall_score} />
                      : <span className="rh-cell-none">—</span>}
                    {coveragePct != null && (
                      <span className="rh-coverage-sub">{coveragePct}% coverage</span>
                    )}
                  </span>
                  <span className="rh-cell rh-cell-kw">
                    {selectedCount > 0 && (
                      <span className="rh-kw-stat">
                        <span className="rh-kw-stat-matched">{matchedCount}</span>
                        <span className="rh-kw-stat-sep">/</span>
                        <span className="rh-kw-stat-total">{selectedCount}</span>
                        <span className="rh-kw-stat-label"> kw</span>
                      </span>
                    )}
                  </span>
                  <span className="rh-cell rh-cell-actions">
                    <button
                      className="rh-delete-btn"
                      disabled={deleting === record.id}
                      onClick={e => handleDelete(record.id, e)}
                      aria-label="Delete"
                    >
                      {deleting === record.id ? "…" : "✕"}
                    </button>
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
