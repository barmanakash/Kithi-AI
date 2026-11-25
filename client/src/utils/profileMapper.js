/**
 * Converts between the backend candidate-profile shape and the editable form state.
 * The backend schema uses extra="forbid", so toPayload() only ever sends known fields
 * (never id / created_at / updated_at that come back from GET /profile).
 */

const text = (v) => (v == null ? "" : String(v));
const clean = (v) => {
  const t = text(v).trim();
  return t === "" ? null : t;
};
const toNumber = (v) => {
  if (v === "" || v == null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const toUrl = (v) => {
  const t = clean(v);
  if (!t) return null;
  return /^https?:\/\//i.test(t) ? t : `https://${t}`;
};

export const EMPLOYMENT_OPTIONS = [
  ["full_time", "Full-time"],
  ["part_time", "Part-time"],
  ["contract", "Contract"],
  ["internship", "Internship"],
  ["remote", "Remote"],
  ["hybrid", "Hybrid"],
  ["onsite", "On-site"],
];

export const blankExperience = () => ({
  company: "", title: "", location: "", start_date: "", end_date: "", current: false, description: "", achievements: "",
});
export const blankEducation = () => ({ institution: "", degree: "", field_of_study: "", start_year: "", end_year: "", grade: "" });
export const blankCertification = () => ({ name: "", issuer: "", year: "", url: "" });
export const blankProject = () => ({ name: "", description: "", technologies: [], url: "" });

export function toForm(profile = {}) {
  const sal = profile.salary_expectation || {};
  return {
    full_name: text(profile.full_name),
    headline: text(profile.headline),
    summary: text(profile.summary),
    phone: text(profile.phone),
    location: text(profile.location),
    experience: (profile.experience || []).map((e) => ({
      company: text(e.company),
      title: text(e.title),
      location: text(e.location),
      start_date: text(e.start_date),
      end_date: text(e.end_date),
      current: Boolean(e.current),
      description: text(e.description),
      achievements: (e.achievements || []).join("\n"),
    })),
    technical_skills: profile.technical_skills || [],
    soft_skills: profile.soft_skills || [],
    education: (profile.education || []).map((e) => ({
      institution: text(e.institution),
      degree: text(e.degree),
      field_of_study: text(e.field_of_study),
      start_year: text(e.start_year),
      end_year: text(e.end_year),
      grade: text(e.grade),
    })),
    certifications: (profile.certifications || []).map((c) => ({
      name: text(c.name),
      issuer: text(c.issuer),
      year: text(c.year),
      url: text(c.url),
    })),
    projects: (profile.projects || []).map((p) => ({
      name: text(p.name),
      description: text(p.description),
      technologies: p.technologies || [],
      url: text(p.url),
    })),
    salary: {
      min: text(sal.min_amount),
      max: text(sal.max_amount),
      currency: sal.currency || "INR",
      period: sal.period || "annual",
    },
    notice_period_days: text(profile.notice_period_days),
    preferred_locations: profile.preferred_locations || [],
    employment_preferences: profile.employment_preferences || [],
    linkedin_url: text(profile.linkedin_url),
    github_url: text(profile.github_url),
    portfolio_url: text(profile.portfolio_url),
  };
}

export function toPayload(f) {
  const min = toNumber(f.salary.min);
  const max = toNumber(f.salary.max);
  return {
    full_name: clean(f.full_name),
    headline: clean(f.headline),
    summary: clean(f.summary),
    phone: clean(f.phone),
    location: clean(f.location),
    experience: f.experience.map((e) => ({
      company: e.company.trim(),
      title: e.title.trim(),
      location: clean(e.location),
      start_date: clean(e.start_date),
      end_date: e.current ? null : clean(e.end_date),
      current: Boolean(e.current),
      description: e.description.trim(),
      achievements: e.achievements.split("\n").map((s) => s.trim()).filter(Boolean),
    })),
    technical_skills: f.technical_skills,
    soft_skills: f.soft_skills,
    education: f.education.map((e) => ({
      institution: e.institution.trim(),
      degree: e.degree.trim(),
      field_of_study: clean(e.field_of_study),
      start_year: toNumber(e.start_year),
      end_year: toNumber(e.end_year),
      grade: clean(e.grade),
    })),
    certifications: f.certifications.map((c) => ({
      name: c.name.trim(),
      issuer: clean(c.issuer),
      year: toNumber(c.year),
      url: toUrl(c.url),
    })),
    projects: f.projects.map((p) => ({
      name: p.name.trim(),
      description: p.description.trim(),
      technologies: p.technologies,
      url: toUrl(p.url),
    })),
    salary_expectation:
      min == null && max == null
        ? null
        : { min_amount: min, max_amount: max, currency: (f.salary.currency || "INR").trim().toUpperCase(), period: f.salary.period },
    notice_period_days: toNumber(f.notice_period_days),
    preferred_locations: f.preferred_locations,
    employment_preferences: f.employment_preferences,
    linkedin_url: toUrl(f.linkedin_url),
    github_url: toUrl(f.github_url),
    portfolio_url: toUrl(f.portfolio_url),
  };
}

const isValidUrl = (value) => {
  try {
    const u = new URL(value);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
};

const MONTH_RE = /^\d{4}-(0[1-9]|1[0-2])$/;

/** Returns a list of human-readable problems (empty when the form is valid). */
export function validateForm(f) {
  const errors = [];

  f.experience.forEach((e, i) => {
    const n = `Experience #${i + 1}`;
    if (!e.company.trim() || !e.title.trim()) errors.push(`${n}: company and job title are required.`);
    if (e.start_date && !MONTH_RE.test(e.start_date)) errors.push(`${n}: start date must be YYYY-MM.`);
    if (e.end_date && !e.current && !MONTH_RE.test(e.end_date)) errors.push(`${n}: end date must be YYYY-MM.`);
    if (e.start_date && e.end_date && !e.current && e.end_date < e.start_date) errors.push(`${n}: end date is before the start date.`);
  });

  f.education.forEach((e, i) => {
    const n = `Education #${i + 1}`;
    if (!e.institution.trim() || !e.degree.trim()) errors.push(`${n}: institution and degree are required.`);
    for (const key of ["start_year", "end_year"]) {
      const v = toNumber(e[key]);
      if (e[key] !== "" && (v == null || v < 1950 || v > 2100)) errors.push(`${n}: ${key.replace("_", " ")} must be between 1950 and 2100.`);
    }
    const s = toNumber(e.start_year);
    const en = toNumber(e.end_year);
    if (s != null && en != null && en < s) errors.push(`${n}: end year is before the start year.`);
  });

  f.certifications.forEach((c, i) => {
    const n = `Certification #${i + 1}`;
    if (!c.name.trim()) errors.push(`${n}: name is required.`);
    const y = toNumber(c.year);
    if (c.year !== "" && (y == null || y < 1950 || y > 2100)) errors.push(`${n}: year must be between 1950 and 2100.`);
    if (toUrl(c.url) && !isValidUrl(toUrl(c.url))) errors.push(`${n}: URL is not valid.`);
  });

  f.projects.forEach((p, i) => {
    const n = `Project #${i + 1}`;
    if (!p.name.trim()) errors.push(`${n}: name is required.`);
    if (toUrl(p.url) && !isValidUrl(toUrl(p.url))) errors.push(`${n}: URL is not valid.`);
  });

  const min = toNumber(f.salary.min);
  const max = toNumber(f.salary.max);
  if ((f.salary.min !== "" && (min == null || min < 0)) || (f.salary.max !== "" && (max == null || max < 0))) {
    errors.push("Salary expectation: amounts must be non-negative numbers.");
  } else if (min != null && max != null && min > max) {
    errors.push("Salary expectation: minimum is greater than maximum.");
  }
  if ((min != null || max != null) && !/^[A-Za-z]{3}$/.test((f.salary.currency || "").trim())) {
    errors.push("Salary expectation: currency must be a 3-letter code such as INR or USD.");
  }

  if (f.notice_period_days !== "") {
    const d = toNumber(f.notice_period_days);
    if (d == null || !Number.isInteger(d) || d < 0 || d > 365) errors.push("Notice period must be a whole number of days between 0 and 365.");
  }

  for (const [key, label] of [["linkedin_url", "LinkedIn"], ["github_url", "GitHub"], ["portfolio_url", "Portfolio"]]) {
    const url = toUrl(f[key]);
    if (url && !isValidUrl(url)) errors.push(`${label} URL is not valid.`);
  }

  return errors;
}
