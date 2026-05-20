/**
 * build_resume_docx.js
 * --------------------
 * Reads a JSON resume from stdin, generates a full single-page .docx
 * with content filling the page top-to-bottom. No bottom whitespace.
 *
 * Usage:
 *   echo '<json>' | node build_resume_docx.js /path/to/output.docx
 */

"use strict";

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ExternalHyperlink, AlignmentType, BorderStyle, WidthType,
  LevelFormat, TabStopType, UnderlineType,
} = require("docx");

// ── Page & layout ──────────────────────────────────────────────────────────
const PAGE = {
  width: 12240, height: 15840,
  margin: { top: 500, bottom: 800, left: 700, right: 720 },
};
const CONTENT_WIDTH = 10820;

// ── Typography ─────────────────────────────────────────────────────────────
const FONT = "Times New Roman";
const SZ   = { name: 42, section: 24, title: 22, body: 20, contact: 18 };
const CLR  = { black: "000000" };

// ── Spacing ────────────────────────────────────────────────────────────────
// Calibrated empirically against LibreOffice rendering (ratio ~1.111×).
// line=260 + spacing below fill the page to the bottom margin with
// ~30 twips to spare — content reaches the bottom edge, no whitespace.
const LINE = 260;
const SP = {
  name:        { before: 4,   after: 40,  line: 244, lineRule: "auto" },
  contact:     { before: 10,  after: 56,  line: 244, lineRule: "auto" },
  section:     { before: 120, after: 100, line: LINE, lineRule: "auto" },
  jobTitle:    { before: 120, after: 55,  line: LINE, lineRule: "auto" },
  company:     { before: 0,   after: 58,  line: LINE, lineRule: "auto" },
  bulletFirst: { before: 36,  after: 0,   line: LINE, lineRule: "auto" },
  bulletMid:   { before: 4,   after: 0,   line: LINE, lineRule: "auto" },
  bulletLast:  { before: 0,   after: 58,  line: LINE, lineRule: "auto" },
  bulletOnly:  { before: 36,  after: 58,  line: LINE, lineRule: "auto" },
  bodyLast:    { before: 0,   after: 58,  line: LINE, lineRule: "auto" },
  certRow:     { before: 28,  after: 28,  line: LINE, lineRule: "auto" },
  certLast:    { before: 28,  after: 0,   line: LINE, lineRule: "auto" },
  tableCell:   { top: 28, bottom: 28 },
};

// ── Run factory ────────────────────────────────────────────────────────────
function R(text, size, opts = {}) {
  return new TextRun({
    text,
    font:      FONT,
    size,
    bold:      opts.bold    !== undefined ? opts.bold : true,
    italics:   opts.italics || false,
    color:     opts.color   || CLR.black,
    underline: opts.underline ? { type: UnderlineType.SINGLE } : undefined,
  });
}

function link(text, url, size) {
  return new ExternalHyperlink({
    link: url,
    children: [R(text, size, { underline: true })],
  });
}

// ── Section header ─────────────────────────────────────────────────────────
function sectionHeader(title) {
  return new Paragraph({
    border: {
      bottom: { style: BorderStyle.SINGLE, size: 6, color: CLR.black, space: 2 },
    },
    children: [R(title, SZ.section)],
    spacing:  SP.section,
    indent:   { left: 0 },
  });
}

// ── Bullets ────────────────────────────────────────────────────────────────
function bullet(text, pos) {
  const sp =
    pos === "first" ? SP.bulletFirst :
    pos === "last"  ? SP.bulletLast  :
    pos === "only"  ? SP.bulletOnly  :
                      SP.bulletMid;
  return new Paragraph({
    numbering: { reference: "resume-bullets", level: 0 },
    children:  [R(text, SZ.body)],
    spacing:   sp,
  });
}

function taggedBullets(texts) {
  if (!texts?.length) return [];
  if (texts.length === 1) return [bullet(texts[0], "only")];
  return texts.map((t, i) =>
    bullet(t, i === 0 ? "first" : i === texts.length - 1 ? "last" : "mid")
  );
}

// ── Date formatter ─────────────────────────────────────────────────────────
function fmtDate(d) {
  if (!d || d === "present") return "Present";
  const [y, m] = d.split("-");
  const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${MON[parseInt(m, 10) - 1]} ${y}`;
}

// ── Contact header ─────────────────────────────────────────────────────────
function buildHeader(contact) {
  const sep   = () => R("  |  ", SZ.contact);
  const parts = [];

  if (contact.location) parts.push(R(contact.location, SZ.contact));
  if (contact.phone)    { if (parts.length) parts.push(sep()); parts.push(R(contact.phone, SZ.contact)); }
  if (contact.email)    { if (parts.length) parts.push(sep()); parts.push(link(contact.email, `mailto:${contact.email}`, SZ.contact)); }
  for (const { label, url } of [
    { label: "Portfolio", url: contact.portfolio },
    { label: "GitHub",    url: contact.github    },
    { label: "LinkedIn",  url: contact.linkedin  },
  ].filter(l => l.url)) {
    if (parts.length) parts.push(sep());
    parts.push(link(label, url, SZ.contact));
  }

  return [
    new Paragraph({ children: [R(contact.name || "", SZ.name)], spacing: SP.name,    indent: { left: 4279 } }),
    new Paragraph({ children: parts,                             spacing: SP.contact, indent: { left: 2020 } }),
  ];
}

// ── Summary ────────────────────────────────────────────────────────────────
function buildSummary(text) {
  if (!text) return [];
  return [
    sectionHeader("SUMMARY"),
    new Paragraph({ children: [R(text, SZ.body)], spacing: SP.bodyLast, indent: { left: 0 } }),
  ];
}

// ── Skills ─────────────────────────────────────────────────────────────────
const NB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const NO_BORDERS = { top: NB, bottom: NB, left: NB, right: NB, insideH: NB, insideV: NB };

const SKILL_LABELS = {
  languages: "Languages", ai_ml: "AI / ML", backend: "Backend",
  frontend: "Frontend", databases_cloud: "Data & Cloud", tools: "Tools",
};

function buildSkills(skills, skillsOrder, skillsToHighlight = []) {
  if (!skills) return [];
  const order = skillsOrder || Object.keys(SKILL_LABELS);
  const hlSet  = new Set(skillsToHighlight.map(s => s.toLowerCase()));
  const COL1 = 1600, COL2 = CONTENT_WIDTH - COL1;

  const rows = order
    .filter(cat => skills[cat]?.length)
    .map(cat => new TableRow({ children: [
      new TableCell({
        width: { size: COL1, type: WidthType.DXA }, borders: NO_BORDERS,
        margins: SP.tableCell,
        children: [new Paragraph({
          children: [R(SKILL_LABELS[cat] || cat, SZ.body)],
          spacing:  { line: LINE, lineRule: "auto" },
        })],
      }),
      new TableCell({
        width: { size: COL2, type: WidthType.DXA }, borders: NO_BORDERS,
        margins: SP.tableCell,
        children: [new Paragraph({
          children: skills[cat].flatMap((skill, idx) => [
            ...(idx > 0 ? [R(", ", SZ.body, { bold: false })] : []),
            R(skill, SZ.body, { bold: hlSet.has(skill.toLowerCase()) }),
          ]),
          spacing: { line: LINE, lineRule: "auto" },
        })],
      }),
    ]}));

  if (!rows.length) return [];
  return [
    sectionHeader("SKILLS"),
    new Table({
      width: { size: CONTENT_WIDTH, type: WidthType.DXA },
      columnWidths: [COL1, COL2],
      borders: NO_BORDERS,
      rows,
    }),
  ];
}

// ── Experience ─────────────────────────────────────────────────────────────
function buildExperienceEntry(exp) {
  const titlePara = new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_WIDTH }],
    children: [
      R(exp.title || "", SZ.title),
      R("\t", SZ.title),
      R(`${fmtDate(exp.start_date)} – ${fmtDate(exp.end_date)}`, SZ.contact, { italics: true }),
    ],
    spacing: SP.jobTitle, indent: { left: 0 },
  });

  const companyParts = [R(exp.company || "", SZ.body, { italics: true })];
  if (exp.location) companyParts.push(R(`  ·  ${exp.location}`, SZ.contact, { italics: true }));

  const texts = (exp.bullets || []).map(b =>
    typeof b === "string" ? b : b.text || b.tailored || ""
  );
  return [
    titlePara,
    new Paragraph({ children: companyParts, spacing: SP.company, indent: { left: 0 } }),
    ...taggedBullets(texts),
  ];
}

function buildExperience(experience) {
  if (!experience?.length) return [];
  return [sectionHeader("EXPERIENCE"), ...experience.flatMap(buildExperienceEntry)];
}

// ── Projects ───────────────────────────────────────────────────────────────
function buildProjectEntry(project) {
  const techStr   = (project.tech_stack || []).join(" · ");
  const nameParts = project.links?.github
    ? [link(project.name || "Project", project.links.github, SZ.title)]
    : [R(project.name || "Project", SZ.title)];
  if (project.links?.preview) {
    nameParts.push(R("  ·  ", SZ.contact));
    nameParts.push(link("Live Demo", project.links.preview, SZ.contact));
  }
  const texts = (project.bullets || []).map(b =>
    typeof b === "string" ? b : b.text || ""
  );
  return [
    new Paragraph({
      tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_WIDTH }],
      children: [...nameParts, R("\t", SZ.title), R(techStr, SZ.contact, { italics: true })],
      spacing: SP.jobTitle, indent: { left: 0 },
    }),
    ...taggedBullets(texts),
  ];
}

function buildProjects(projects) {
  if (!projects?.length) return [];
  return [sectionHeader("PROJECTS"), ...projects.flatMap(buildProjectEntry)];
}

// ── Education ──────────────────────────────────────────────────────────────
function buildEducation(education) {
  if (!education?.length) return [];
  return [
    sectionHeader("EDUCATION"),
    ...education.map(edu => new Paragraph({
      tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_WIDTH }],
      children: [
        R(`${edu.degree} in ${edu.field}`, SZ.body),
        R("  ·  ", SZ.contact),
        R(edu.institution, SZ.body, { italics: true }),
        R("\t", SZ.body),
        R(edu.graduation_date ? edu.graduation_date.split("-")[0] : "", SZ.contact),
      ],
      spacing: SP.bodyLast, indent: { left: 0 },
    })),
  ];
}

// ── Certifications ─────────────────────────────────────────────────────────
function buildCertifications(certs) {
  if (!certs?.length) return [];
  return [
    sectionHeader("CERTIFICATIONS"),
    ...certs.map((cert, idx) => new Paragraph({
      tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_WIDTH }],
      children: [
        R(cert.name, SZ.body),
        R("  ·  ", SZ.contact),
        R(`${cert.issuer}${cert.type ? " — " + cert.type : ""}`, SZ.contact, { italics: true }),
        R("\t", SZ.body),
        R(cert.date ? cert.date.split("-")[0] : "", SZ.contact),
      ],
      spacing: idx === certs.length - 1 ? SP.certLast : SP.certRow,
      indent:  { left: 0 },
    })),
  ];
}

// ── Document assembly ──────────────────────────────────────────────────────
function buildDocument(resume) {
  const {
    contact = {}, tailored_summary, summary,
    skills = {}, experience = [], projects = [],
    education = [], certifications = [],
    ats_config = {}, skills_to_highlight = [],
  } = resume;

  const summaryText =
    tailored_summary ||
    (typeof summary === "string" ? summary : summary?.default) || "";

  return new Document({
    numbering: {
      config: [{
        reference: "resume-bullets",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "\u2022",
          alignment: AlignmentType.LEFT,
          style: {
            paragraph: { indent: { left: 300, hanging: 157 } },
            run: { font: FONT, size: SZ.body },
          },
        }],
      }],
    },
    styles: {
      default: { document: { run: { font: FONT, size: SZ.body, color: CLR.black } } },
    },
    sections: [{
      properties: {
        page: {
          size:   { width: PAGE.width, height: PAGE.height },
          margin: PAGE.margin,
        },
      },
      children: [
        ...buildHeader(contact),
        ...buildSummary(summaryText),
        ...buildSkills(skills, ats_config.skills_order, skills_to_highlight),
        ...buildExperience(experience),
        ...buildProjects(projects),
        ...buildEducation(education),
        ...buildCertifications(certifications),
      ],
    }],
  });
}

// ── Entry point ────────────────────────────────────────────────────────────
async function main() {
  const outputPath = process.argv[2];
  if (!outputPath) { console.error("Usage: node build_resume_docx.js <output.docx>"); process.exit(1); }

  let rawJson = "";
  process.stdin.setEncoding("utf8");
  for await (const chunk of process.stdin) rawJson += chunk;

  let resume;
  try { resume = JSON.parse(rawJson); }
  catch (e) { console.error("Failed to parse resume JSON:", e.message); process.exit(1); }

  const buffer = await Packer.toBuffer(buildDocument(resume));
  fs.writeFileSync(outputPath, buffer);
  console.log(`Written: ${outputPath}`);
}

main().catch(err => { console.error(err); process.exit(1); });