import { useEffect, useState } from "react";
import "./ResumePicker.css";

export default function ResumePicker({ apiBase, onCreate, onSelect }) {
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
        <div className="rpicker-hero">
          <h1 className="rpicker-title">ResuméBuddy</h1>
          <p className="rpicker-sub">Loading your resume profiles…</p>
        </div>
        <div className="rpicker-loading"><span className="spinner" /></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rpicker-page fade-up">
        <div className="rpicker-hero">
          <h1 className="rpicker-title">ResuméBuddy</h1>
        </div>
        <div className="rpicker-error">⚠ {error}</div>
      </div>
    );
  }

  return (
    <div className="rpicker-page fade-up">
      <div className="rpicker-hero">
        <h1 className="rpicker-title">ResuméBuddy</h1>
        <p className="rpicker-sub">
          Choose the resume profile you want to tailor for this application.
        </p>
      </div>

      <button className="rpicker-create-btn" type="button" onClick={onCreate}>
        <span aria-hidden="true">+</span>
        Create a resume
      </button>

      <div className="rpicker-grid">
        {resumes.map((resume) => (
          <button
            key={resume.id}
            className="rpicker-card card"
            onClick={() => onSelect(resume)}
          >
            <div className="rpicker-card-name">{resume.name}</div>
            {resume.target_roles.length > 0 && (
              <div className="rpicker-card-roles">
                {resume.target_roles.slice(0, 3).map((role) => (
                  <span key={role} className="rpicker-role-chip">{role}</span>
                ))}
              </div>
            )}
            {resume.last_updated && (
              <div className="rpicker-card-meta">Updated {resume.last_updated}</div>
            )}
            <div className="rpicker-card-arrow">→</div>
          </button>
        ))}
      </div>
    </div>
  );
}
