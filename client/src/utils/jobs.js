export const SCAM_LEVELS = {
  no_flags_found: { label: "No flags found", color: "success" },
  low_concern: { label: "Low concern", color: "info" },
  medium_concern: { label: "Medium concern", color: "warning" },
  high_concern: { label: "High concern", color: "error" },
};

export const MATCH_LABELS = {
  strong: { label: "Strong match", color: "success" },
  good: { label: "Good match", color: "info" },
  partial: { label: "Partial match", color: "warning" },
  weak: { label: "Weak match", color: "error" },
  unknown: { label: "Not scored", color: "default" },
};

export const SOURCE_LABELS = {
  remotive: "Remotive",
  arbeitnow: "Arbeitnow",
  manual: "Added manually",
};

export const INJECTION_LABELS = {
  ignore_instructions: "tries to override AI instructions",
  disregard_instructions: "tries to override AI instructions",
  role_override: "tries to change the AI's role",
  prompt_exfiltration: "asks the AI to reveal hidden prompts",
  action_request: "asks to send personal data or applications",
  fake_system_message: "contains a fake system message",
};

export const WEIGHT_HELP = {
  skills: "How many of the job's required skills you have",
  experience: "Years of experience compared with what the job asks",
  responsibilities: "Overlap between the job's key terms and your experience",
  education: "Degree level compared with what the job mentions",
  location: "Job location against your preferred locations",
  preferences: "Employment type and work mode against your preferences",
};

/** Only plain http(s) links are ever rendered as hyperlinks (job data is untrusted). */
export const safeHref = (url) => (url && /^https?:\/\//i.test(url) ? url : null);
