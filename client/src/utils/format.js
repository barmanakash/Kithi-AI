/** Turn any Axios/FastAPI error into a readable message. */
export function errorMessage(err, fallback = "Something went wrong") {
  if (!err) return fallback;
  if (err.code === "ECONNABORTED") {
    return "The request timed out. The local AI model may still be busy; try again shortly.";
  }
  if (!err.response) {
    return err.request
      ? "Cannot reach the Kithi server. Make sure the backend is running."
      : err.message || fallback;
  }
  const detail = err.response.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = Array.isArray(item.loc) ? item.loc.filter((p) => p !== "body").join(" > ") : "";
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .join("; ");
  }
  return `${fallback} (HTTP ${err.response.status})`;
}

/** The API returns UTC datetimes that may lack a timezone suffix; treat those as UTC. */
export function parseApiDate(value) {
  if (!value) return null;
  const str = String(value);
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(str);
  const date = new Date(hasZone ? str : `${str}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value) {
  const date = parseApiDate(value);
  return date ? date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "-";
}

export function formatDateTime(value) {
  const date = parseApiDate(value);
  return date
    ? date.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : "-";
}

export function formatBytes(bytes) {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** MUI palette key for a 0-100 score. */
export function scoreColor(value) {
  if (value >= 75) return "success";
  if (value >= 50) return "warning";
  return "error";
}

export function initials(name = "") {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

/** Readable labels for the backend's profile-completeness keys. */
export const COMPLETENESS_LABELS = {
  full_name: "Full name",
  headline: "Professional headline",
  summary: "Summary",
  phone: "Phone",
  location: "Location",
  experience: "Work experience",
  technical_skills: "Technical skills",
  education: "Education",
  preferred_locations: "Preferred locations",
  employment_preferences: "Employment preferences",
  links: "LinkedIn / GitHub / portfolio link",
};
