import "./MasterResumePreview.css";

function hasValues(item) {
  return Object.values(item).some((value) => (
    Array.isArray(value) ? value.length > 0 : Boolean(value)
  ));
}

function formatDate(value) {
  if (!value) return "";
  const [year, month] = value.split("-");
  if (!year || !month) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${year}-${month}-01T00:00:00Z`));
}

function dateRange(startDate, endDate) {
  if (!startDate && !endDate) return "";
  return `${formatDate(startDate)} – ${endDate ? formatDate(endDate) : "Present"}`;
}

export default function MasterResumePreview({ onBack, onEdit, resume, savedAt }) {
  const experience = resume.experience.filter(hasValues);
  const education = resume.education.filter(hasValues);
  const projects = resume.projects.filter(hasValues);
  const certifications = resume.certifications.filter(hasValues);
  const skillGroups = Array.isArray(resume.skills)
    ? resume.skills.filter(hasValues)
    : [];

  return (
    <div className="mrp-page fade-up">
      <div className="mrp-toolbar">
        <div>
          <button className="btn btn-ghost" type="button" onClick={onBack}>← Back to resumes</button>
          <span className="mrp-saved">Saved {new Date(savedAt).toLocaleString()}</span>
        </div>
        <button className="btn btn-primary" type="button" onClick={onEdit}>Edit resume</button>
      </div>

      <main className="mrp-paper" aria-label={`${resume.contact.name}'s resume preview`}>
        <header className="mrp-header">
          <h1>{resume.contact.name}</h1>
          {resume.targetRole && <p className="mrp-role">{resume.targetRole}</p>}
          <div className="mrp-contact">
            {resume.contact.location && <span>{resume.contact.location}</span>}
            {resume.contact.phone && <span>{resume.contact.phone}</span>}
            <a href={`mailto:${resume.contact.email}`}>{resume.contact.email}</a>
            {resume.contact.linkedin && <a href={resume.contact.linkedin} target="_blank" rel="noreferrer">LinkedIn</a>}
            {resume.contact.portfolio && <a href={resume.contact.portfolio} target="_blank" rel="noreferrer">Portfolio</a>}
          </div>
        </header>

        {resume.summary && (
          <section className="mrp-section">
            <h2>Professional Summary</h2>
            <p>{resume.summary}</p>
          </section>
        )}

        {(skillGroups.length > 0 || (typeof resume.skills === "string" && resume.skills)) && (
          <section className="mrp-section">
            <h2>Skills</h2>
            {skillGroups.length > 0 ? (
              <div className="mrp-skills">
                {skillGroups.map((skillGroup, index) => (
                  <p key={`${skillGroup.category}-${index}`}>
                    {skillGroup.category && <strong>{skillGroup.category}: </strong>}
                    {skillGroup.items}
                  </p>
                ))}
              </div>
            ) : (
              <p>{resume.skills}</p>
            )}
          </section>
        )}

        {experience.length > 0 && (
          <section className="mrp-section">
            <h2>Professional Experience</h2>
            {experience.map((item, index) => (
              <article className="mrp-entry" key={`${item.company}-${item.title}-${index}`}>
                <div className="mrp-entry-heading">
                  <div>
                    <h3>{item.title || item.company}</h3>
                    {item.title && item.company && <p>{item.company}{item.location ? ` · ${item.location}` : ""}</p>}
                  </div>
                  <span>{dateRange(item.startDate, item.endDate)}</span>
                </div>
                {item.highlights && <p className="mrp-highlights">{item.highlights}</p>}
              </article>
            ))}
          </section>
        )}

        {projects.length > 0 && (
          <section className="mrp-section">
            <h2>Projects</h2>
            {projects.map((project, index) => (
              <article className="mrp-entry" key={`${project.name}-${index}`}>
                <div className="mrp-project-heading">
                  <h3>{project.name || "Project"}</h3>
                  <div>
                    {project.links.map((link) => (
                      <a key={`${link.name}-${link.url}`} href={link.url} target="_blank" rel="noreferrer">{link.name}</a>
                    ))}
                  </div>
                </div>
                {project.technologies && <p className="mrp-technologies">{project.technologies}</p>}
                {project.description && <p className="mrp-highlights">{project.description}</p>}
              </article>
            ))}
          </section>
        )}

        {education.length > 0 && (
          <section className="mrp-section">
            <h2>Education</h2>
            {education.map((item, index) => (
              <article className="mrp-entry mrp-entry-heading" key={`${item.institution}-${index}`}>
                <div>
                  <h3>{item.institution}</h3>
                  <p>{[item.degree, item.field].filter(Boolean).join(", ")}</p>
                </div>
                <span>{formatDate(item.graduationDate)}</span>
              </article>
            ))}
          </section>
        )}

        {certifications.length > 0 && (
          <section className="mrp-section">
            <h2>Certifications</h2>
            {certifications.map((item, index) => (
              <article className="mrp-entry mrp-entry-heading" key={`${item.name}-${index}`}>
                <div>
                  <h3>{item.name}</h3>
                  {item.issuer && <p>{item.issuer}</p>}
                </div>
                <span>{formatDate(item.date)}</span>
              </article>
            ))}
          </section>
        )}
      </main>
    </div>
  );
}
