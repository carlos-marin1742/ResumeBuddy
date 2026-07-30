import { useEffect, useState } from "react";
import "./ResumePicker.css";

export default function ResumePicker({ apiBase, onCreate, onSelect }) {
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch(`${apiBase}/api/resumes`).then((response) => {
        if (response.status === 404) return { resumes: [] };
        if (!response.ok) throw new Error(`Server error ${response.status}`);
        return response.json();
      }),
      fetch(`${apiBase}/api/master-resumes`).then((response) => {
        if (!response.ok) throw new Error(`Server error ${response.status}`);
        return response.json();
      }),
    ])
      .then(([profiles, masters]) => {
        const savedResumes = masters.resumes.map((resume) => ({
          id: resume.id,
          source: "master",
          name: resume.title,
          target_roles: resume.name !== resume.title ? [resume.name] : [],
          last_updated: resume.updated_at
            ? new Date(resume.updated_at).toLocaleDateString()
            : "",
        }));
        setResumes([...savedResumes, ...profiles.resumes]);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [apiBase]);

  async function deleteResume(resume) {
    setDeletingId(resume.id);
    setError(null);
    try {
      const response = await fetch(`${apiBase}/api/master-resumes/${resume.id}`, {
        method: "DELETE",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Server error ${response.status}`);
      setResumes((current) => current.filter(
        (item) => !(item.source === "master" && item.id === resume.id),
      ));
      setConfirmDeleteId(null);
    } catch (deleteError) {
      setError(deleteError.message);
    } finally {
      setDeletingId(null);
    }
  }

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
          <div
            key={`${resume.source || "profile"}-${resume.id}`}
            className="rpicker-card card"
          >
            <button
              className="rpicker-card-select"
              type="button"
              aria-label={`Select ${resume.name}`}
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
            {resume.source === "master" && (
              confirmDeleteId === resume.id ? (
                <div className="rpicker-delete-confirm" role="group" aria-label={`Confirm deletion of ${resume.name}`}>
                  <span>Delete this resume?</span>
                  <button
                    className="rpicker-delete-yes"
                    type="button"
                    disabled={deletingId === resume.id}
                    onClick={() => deleteResume(resume)}
                  >
                    {deletingId === resume.id ? "Deleting…" : "Delete"}
                  </button>
                  <button
                    type="button"
                    disabled={deletingId === resume.id}
                    onClick={() => setConfirmDeleteId(null)}
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  className="rpicker-delete-btn"
                  type="button"
                  aria-label={`Delete ${resume.name}`}
                  onClick={() => setConfirmDeleteId(resume.id)}
                >
                  Delete
                </button>
              )
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
