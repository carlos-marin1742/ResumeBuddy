import { useState } from "react";
import "./ResumeBuilder.css";

const templates = {
  experience: { company: "", title: "", location: "", startDate: "", endDate: "", highlights: "" },
  education: { institution: "", degree: "", field: "", graduationDate: "" },
  projects: { name: "", technologies: "", description: "", links: [] },
  certifications: { name: "", issuer: "", date: "" },
};

const emptyDraft = {
  contact: { name: "", email: "", phone: "", location: "", linkedin: "", portfolio: "" },
  targetRole: "",
  summary: "",
  experience: [{ ...templates.experience }],
  education: [{ ...templates.education }],
  skills: "",
  projects: [{ ...templates.projects }],
  certifications: [{ ...templates.certifications }],
};

function RepeatingSection({ addLabel, children, items, name, number, onAdd, onRemove }) {
  const singular = name === "Work experience" ? "Experience" : name.replace(/s$/, "");
  const headingId = `rb-${name.toLowerCase().replaceAll(" ", "-")}`;

  return (
    <section className="rb-section" aria-labelledby={headingId}>
      <div className="rb-section-heading">
        <h2 id={headingId}>{number}. {name}</h2>
        <button className="rb-add-btn" type="button" onClick={onAdd}>+ {addLabel}</button>
      </div>
      {items.map((item, index) => (
        <div className="rb-entry" key={index}>
          <div className="rb-entry-heading">
            <h3>{singular} {index + 1}</h3>
            {items.length > 1 && (
              <button
                className="rb-remove-btn"
                type="button"
                onClick={() => onRemove(index)}
                aria-label={`Remove ${singular.toLowerCase()} ${index + 1}`}
              >
                Remove
              </button>
            )}
          </div>
          {children(item, index)}
        </div>
      ))}
    </section>
  );
}

export default function ResumeBuilder({ apiBase = "", initialDraft, onBack, onSave }) {
  const [draft, setDraft] = useState(() => initialDraft ?? emptyDraft);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState("");
  const [importResult, setImportResult] = useState(null);

  function updateContact(field, value) {
    setSaved(false);
    setDraft((current) => ({ ...current, contact: { ...current.contact, [field]: value } }));
  }

  function updateField(field, value) {
    setSaved(false);
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function updateList(section, index, field, value) {
    setSaved(false);
    setDraft((current) => ({
      ...current,
      [section]: current[section].map((item, itemIndex) => (
        itemIndex === index ? { ...item, [field]: value } : item
      )),
    }));
  }

  function addItem(section) {
    setSaved(false);
    setDraft((current) => ({
      ...current,
      [section]: [...current[section], { ...templates[section] }],
    }));
  }

  function removeItem(section, index) {
    setSaved(false);
    setDraft((current) => ({
      ...current,
      [section]: current[section].filter((_, itemIndex) => itemIndex !== index),
    }));
  }

  function addProjectLink(projectIndex) {
    setSaved(false);
    setDraft((current) => ({
      ...current,
      projects: current.projects.map((project, index) => (
        index === projectIndex
          ? { ...project, links: [...(project.links ?? []), { name: "", url: "" }] }
          : project
      )),
    }));
  }

  function updateProjectLink(projectIndex, linkIndex, field, value) {
    setSaved(false);
    setDraft((current) => ({
      ...current,
      projects: current.projects.map((project, index) => (
        index === projectIndex
          ? {
              ...project,
              links: (project.links ?? []).map((link, currentLinkIndex) => (
                currentLinkIndex === linkIndex ? { ...link, [field]: value } : link
              )),
            }
          : project
      )),
    }));
  }

  function removeProjectLink(projectIndex, linkIndex) {
    setSaved(false);
    setDraft((current) => ({
      ...current,
      projects: current.projects.map((project, index) => (
        index === projectIndex
          ? {
              ...project,
              links: (project.links ?? []).filter((_, currentLinkIndex) => currentLinkIndex !== linkIndex),
            }
          : project
      )),
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setSaveError("");
    try {
      await onSave(draft);
      setSaved(true);
    } catch (error) {
      setSaveError(error.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleImport(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setImportError("");
    setImporting(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${apiBase}/api/resumes/parse`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `Server error ${response.status}`);
      }
      setDraft(data.draft);
      setSaved(false);
      setImportResult({
        filename: data.filename,
        warnings: data.warnings ?? [],
      });
    } catch (error) {
      setImportError(error.message);
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="rb-page fade-up">
      <header className="rb-header">
        <button className="rb-back-btn" type="button" onClick={onBack}>← Back to resumes</button>
        <p className="rb-eyebrow">New resume</p>
        <h1>Create your resume</h1>
        <p>Add what you know now. You can return and refine each section.</p>
      </header>

      <section className="rb-import" aria-labelledby="rb-import-heading">
        <div>
          <h2 id="rb-import-heading">Already have a resume?</h2>
          <p>Upload a PDF or DOCX to fill in the form. Your file is parsed temporarily and is not stored.</p>
        </div>
        <label className={`btn btn-secondary rb-import-btn ${importing ? "rb-import-btn-disabled" : ""}`}>
          {importing ? "Parsing resume…" : "Upload resume"}
          <input
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            disabled={importing}
            onChange={handleImport}
          />
        </label>
      </section>

      {importError && (
        <div className="rb-import-message rb-import-error" role="alert">
          Could not import resume: {importError}
        </div>
      )}

      {importResult && (
        <div className="rb-import-message rb-import-success" role="status">
          <strong>{importResult.filename} was imported.</strong>
          <span>Review every field below before selecting Save &amp; preview.</span>
          {importResult.warnings.map((warning) => <span key={warning}>{warning}</span>)}
        </div>
      )}

      <form className="rb-form" onSubmit={handleSubmit}>
        <section className="rb-section" aria-labelledby="rb-contact">
          <h2 id="rb-contact">1. Contact information</h2>
          <div className="rb-field-grid">
            <label>Full name<input required autoComplete="name" value={draft.contact.name} onChange={(event) => updateContact("name", event.target.value)} /></label>
            <label>Email<input required type="email" autoComplete="email" value={draft.contact.email} onChange={(event) => updateContact("email", event.target.value)} /></label>
            <label>Phone<input type="tel" autoComplete="tel" value={draft.contact.phone} onChange={(event) => updateContact("phone", event.target.value)} /></label>
            <label>Location<input autoComplete="address-level2" value={draft.contact.location} onChange={(event) => updateContact("location", event.target.value)} /></label>
            <label>LinkedIn<input type="url" placeholder="https://linkedin.com/in/..." value={draft.contact.linkedin} onChange={(event) => updateContact("linkedin", event.target.value)} /></label>
            <label>Portfolio or website<input type="url" placeholder="https://..." value={draft.contact.portfolio} onChange={(event) => updateContact("portfolio", event.target.value)} /></label>
          </div>
        </section>

        <section className="rb-section" aria-labelledby="rb-target-role">
          <h2 id="rb-target-role">2. Target role</h2>
          <label>
            What kind of role are you looking for?
            <input value={draft.targetRole} onChange={(event) => updateField("targetRole", event.target.value)} placeholder="For example, Software Engineer" />
          </label>
        </section>

        <section className="rb-section" aria-labelledby="rb-summary">
          <h2 id="rb-summary">3. Professional summary</h2>
          <label>Summary<textarea rows="5" value={draft.summary} onChange={(event) => updateField("summary", event.target.value)} placeholder="Briefly describe your experience, strengths, and goals." /></label>
        </section>

        <RepeatingSection number="4" name="Work experience" addLabel="Add experience" items={draft.experience} onAdd={() => addItem("experience")} onRemove={(index) => removeItem("experience", index)}>
          {(_, index) => (
            <div className="rb-field-grid">
              <label>Company<input value={draft.experience[index].company} onChange={(event) => updateList("experience", index, "company", event.target.value)} /></label>
              <label>Job title<input value={draft.experience[index].title} onChange={(event) => updateList("experience", index, "title", event.target.value)} /></label>
              <label>Location<input value={draft.experience[index].location} onChange={(event) => updateList("experience", index, "location", event.target.value)} /></label>
              <label>Start date<input type="month" value={draft.experience[index].startDate} onChange={(event) => updateList("experience", index, "startDate", event.target.value)} /></label>
              <label>End date<input type="month" value={draft.experience[index].endDate} onChange={(event) => updateList("experience", index, "endDate", event.target.value)} /></label>
              <label className="rb-wide-field">Responsibilities and accomplishments<textarea rows="4" value={draft.experience[index].highlights} onChange={(event) => updateList("experience", index, "highlights", event.target.value)} /></label>
            </div>
          )}
        </RepeatingSection>

        <RepeatingSection number="5" name="Education" addLabel="Add education" items={draft.education} onAdd={() => addItem("education")} onRemove={(index) => removeItem("education", index)}>
          {(_, index) => (
            <div className="rb-field-grid">
              <label>Institution<input value={draft.education[index].institution} onChange={(event) => updateList("education", index, "institution", event.target.value)} /></label>
              <label>Degree<input value={draft.education[index].degree} onChange={(event) => updateList("education", index, "degree", event.target.value)} /></label>
              <label>Field of study<input value={draft.education[index].field} onChange={(event) => updateList("education", index, "field", event.target.value)} /></label>
              <label>Graduation date<input type="month" value={draft.education[index].graduationDate} onChange={(event) => updateList("education", index, "graduationDate", event.target.value)} /></label>
            </div>
          )}
        </RepeatingSection>

        <section className="rb-section" aria-labelledby="rb-skills">
          <h2 id="rb-skills">6. Skills</h2>
          <label>Skills<textarea rows="4" value={draft.skills} onChange={(event) => updateField("skills", event.target.value)} placeholder="List skills separated by commas." /></label>
        </section>

        <RepeatingSection number="7" name="Projects" addLabel="Add project" items={draft.projects} onAdd={() => addItem("projects")} onRemove={(index) => removeItem("projects", index)}>
          {(_, index) => (
            <div className="rb-field-grid">
              <label>Project name<input value={draft.projects[index].name} onChange={(event) => updateList("projects", index, "name", event.target.value)} /></label>
              <label>Technologies<input value={draft.projects[index].technologies} onChange={(event) => updateList("projects", index, "technologies", event.target.value)} /></label>
              <label className="rb-wide-field">Description<textarea rows="4" value={draft.projects[index].description} onChange={(event) => updateList("projects", index, "description", event.target.value)} /></label>
              <div className="rb-project-links rb-wide-field">
                <div className="rb-project-links-heading">
                  <div>
                    <h4>Links</h4>
                    <p>Add a label and destination, such as GitHub and its repository URL.</p>
                  </div>
                  <button className="rb-add-btn" type="button" onClick={() => addProjectLink(index)}>+ Add link</button>
                </div>
                {(draft.projects[index].links ?? []).map((link, linkIndex) => (
                  <div className="rb-link-row" key={linkIndex}>
                    <label>
                      Link name
                      <input
                        required
                        placeholder="GitHub"
                        value={link.name}
                        onChange={(event) => updateProjectLink(index, linkIndex, "name", event.target.value)}
                      />
                    </label>
                    <label>
                      URL
                      <input
                        required
                        type="url"
                        placeholder="https://github.com/..."
                        value={link.url}
                        onChange={(event) => updateProjectLink(index, linkIndex, "url", event.target.value)}
                      />
                    </label>
                    <button
                      className="rb-remove-btn rb-remove-link-btn"
                      type="button"
                      onClick={() => removeProjectLink(index, linkIndex)}
                      aria-label={`Remove project link ${linkIndex + 1}`}
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </RepeatingSection>

        <RepeatingSection number="8" name="Certifications" addLabel="Add certification" items={draft.certifications} onAdd={() => addItem("certifications")} onRemove={(index) => removeItem("certifications", index)}>
          {(_, index) => (
            <div className="rb-field-grid">
              <label>Certification name<input value={draft.certifications[index].name} onChange={(event) => updateList("certifications", index, "name", event.target.value)} /></label>
              <label>Issuing organization<input value={draft.certifications[index].issuer} onChange={(event) => updateList("certifications", index, "issuer", event.target.value)} /></label>
              <label>Date earned<input type="month" value={draft.certifications[index].date} onChange={(event) => updateList("certifications", index, "date", event.target.value)} /></label>
            </div>
          )}
        </RepeatingSection>

        <div className="rb-actions">
          <div>
            <p className="rb-save-note">{saved ? "Resume saved." : "Only your name and email are required to save."}</p>
            {saveError && <p className="rb-save-error" role="alert">{saveError}</p>}
          </div>
          <button className="btn btn-primary" type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save & preview"}
          </button>
        </div>
      </form>
    </div>
  );
}
