import { useEffect, useState } from "react";
import "./ResumePicker.css";

export default function ResumePicker({ apiBase, onSelect }) {
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${apiBase}/api/resumes`)
      .then((r) => {
        if (!r.ok) throw new Error(`Server error ${r.status}`);
        return r.json();
      })
      .then((data) => setResumes(data.resumes))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [apiBase]);

  if (loading) {
    return (
      <div className="rpicker-page fade-up">
        <div className="rp-hero">
          <h1 className="rpicker-title">ResuméBuddy</h1>
          <p className="rp-sub">Loading your resume profiles…</p>
        </div>
        <div className="rp-loading"><span className="spinner" /></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rp-page fade-up">
        <div className="rp-hero">
          <h1 className="rp-title">ResuméBuddy</h1>
        </div>
        <div className="rp-error">⚠ {error}</div>
      </div>
    );
  }

  return (
    <div className="rp-page fade-up">
      <div className="rpicker-hero">
        <h1 className="rpicker-title">ResuméBuddy</h1>
        <p className="rp-sub">
          Choose the resume profile you want to tailor for this application.
        </p>
      </div>

      <div className="rp-grid">
        {resumes.map((resume) => (
          <button
            key={resume.id}
            className="rp-card card"
            onClick={() => onSelect(resume)}
          >
            <div className="rp-card-name">{resume.name}</div>
            {resume.target_roles.length > 0 && (
              <div className="rp-card-roles">
                {resume.target_roles.slice(0, 3).map((role) => (
                  <span key={role} className="rp-role-chip">{role}</span>
                ))}
              </div>
            )}
            {resume.last_updated && (
              <div className="rp-card-meta">Updated {resume.last_updated}</div>
            )}
            <div className="rp-card-arrow">→</div>
          </button>
        ))}
      </div>
    </div>
  );
}