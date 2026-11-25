export const APPLICATION_STATUSES = [
  { value: "saved", label: "Saved", color: "default" },
  { value: "interested", label: "Interested", color: "info" },
  { value: "preparing", label: "Preparing", color: "info" },
  { value: "ready_for_review", label: "Ready for review", color: "warning" },
  { value: "applied", label: "Applied", color: "primary" },
  { value: "interview_scheduled", label: "Interview scheduled", color: "secondary" },
  { value: "interview_completed", label: "Interview completed", color: "secondary" },
  { value: "offer_received", label: "Offer received", color: "success" },
  { value: "rejected", label: "Rejected", color: "error" },
  { value: "withdrawn", label: "Withdrawn", color: "default" },
  { value: "no_response", label: "No response", color: "warning" },
];

const BY_VALUE = Object.fromEntries(APPLICATION_STATUSES.map((s) => [s.value, s]));

export const statusLabel = (value) => BY_VALUE[value]?.label || value;
export const statusColor = (value) => BY_VALUE[value]?.color || "default";

/** Scam-check concern levels (the backend never reports "fraud" or "safe"). */
export const SCAM_LEVELS = {
  high_concern: { label: "High concern", color: "error", severity: "error" },
  medium_concern: { label: "Medium concern", color: "warning", severity: "warning" },
  low_concern: { label: "Low concern", color: "info", severity: "info" },
  no_flags_found: { label: "No flags found", color: "success", severity: "success" },
};

export const MATCH_LABEL_COLORS = { strong: "success", good: "success", partial: "warning", weak: "error", unknown: "default" };

export const JOB_TYPES = [
  { value: "full_time", label: "Full time" },
  { value: "part_time", label: "Part time" },
  { value: "contract", label: "Contract" },
  { value: "internship", label: "Internship" },
];

/** Only allow http(s) links from third-party data to be opened. */
export const safeUrl = (url) => (typeof url === "string" && /^https?:\/\//i.test(url) ? url : null);
