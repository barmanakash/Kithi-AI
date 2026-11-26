import api from "./api";

const data = (promise) => promise.then((r) => r.data);

// Local AI calls can take a while on modest hardware.
const AI_TIMEOUT = 300000;

export const healthApi = {
  get: () => data(api.get("/health")),
};

export const authApi = {
  register: (body) => data(api.post("/auth/register", body, { skipAuthRedirect: true })),
  login: (body) => data(api.post("/auth/login", body, { skipAuthRedirect: true })),
  me: () => data(api.get("/auth/me")),
  changePassword: (body) => data(api.post("/auth/change-password", body, { skipAuthRedirect: true })),
};

export const profileApi = {
  get: () => data(api.get("/profile")),
  save: (body) => data(api.put("/profile", body)),
  remove: () => data(api.delete("/profile")),
};

export const resumesApi = {
  list: () => data(api.get("/resumes")),
  get: (id) => data(api.get(`/resumes/${id}`)),
  upload: (file, onProgress) => {
    const form = new FormData();
    form.append("file", file);
    return data(
      api.post("/resumes/upload", form, {
        timeout: 120000,
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total));
        },
      })
    );
  },
  setPrimary: (id) => data(api.post(`/resumes/${id}/primary`)),
  remove: (id) => data(api.delete(`/resumes/${id}`)),
  analyze: (id) => data(api.post(`/resumes/${id}/analyze`, null, { timeout: AI_TIMEOUT })),
};

export const aiApi = {
  status: () => data(api.get("/ai/status")),
  ping: () => data(api.post("/ai/ping", null, { timeout: AI_TIMEOUT })),
};

export const accountApi = {
  exportData: () => data(api.get("/account/export")),
  remove: (body) => data(api.post("/account/delete", body, { skipAuthRedirect: true })),
};

export const jobsApi = {
  list: (params = {}) => data(api.get("/jobs", { params })),
  get: (id) => data(api.get(`/jobs/${id}`)),
  create: (body) => data(api.post("/jobs", body)),
  remove: (id) => data(api.delete(`/jobs/${id}`)),
  // Discovery calls external job boards, so allow extra time.
  discover: (body) => data(api.post("/jobs/discover", body, { timeout: 90000 })),
  rescore: (id) => data(api.post(`/jobs/${id}/score`)),
  rescoreAll: () => data(api.post("/jobs/rescore-all", null, { timeout: 120000 })),
  explain: (id) => data(api.post(`/jobs/${id}/explain`, null, { timeout: AI_TIMEOUT })),
};

export const matchesApi = {
  list: (params = {}) => data(api.get("/job-matches", { params })),
  getWeights: () => data(api.get("/job-matches/weights")),
  saveWeights: (body) => data(api.put("/job-matches/weights", body)),
};

export const scamApi = {
  assess: (body) => data(api.post("/scam/assess", body)),
  assessJob: (jobId) => data(api.post(`/scam/jobs/${jobId}`)),
  list: (params = {}) => data(api.get("/scam/assessments", { params })),
  remove: (id) => data(api.delete(`/scam/assessments/${id}`)),
};

// Resume Generation: tailored resumes, cover letters and bullet rewrites (server: /api/generate/*).
export const generateApi = {
  tailorResume: (body) => data(api.post("/generate/tailored-resume", body, { timeout: AI_TIMEOUT })),
  coverLetter: (body) => data(api.post("/generate/cover-letter", body, { timeout: AI_TIMEOUT })),
  improveBullets: (body) => data(api.post("/generate/improve-bullets", body, { timeout: AI_TIMEOUT })),
  list: (params = {}) => data(api.get("/generate/versions", { params })),
  get: (id) => data(api.get(`/generate/versions/${id}`)),
  update: (id, body) => data(api.put(`/generate/versions/${id}`, body)),
  remove: (id) => data(api.delete(`/generate/versions/${id}`)),
  // Returns a Blob (Word document).
  exportDocx: (id) => data(api.get(`/generate/versions/${id}/export`, { responseType: "blob" })),
};

// Applications tracking (server: /api/applications/*). Kithi never submits an application for the user.
export const applicationsApi = {
  list: (params = {}) => data(api.get("/applications", { params })),
  stats: () => data(api.get("/applications/stats")),
  get: (id) => data(api.get(`/applications/${id}`)),
  create: (body) => data(api.post("/applications", body)),
  fromJob: (jobId) => data(api.post(`/applications/from-job/${jobId}`)),
  update: (id, body) => data(api.put(`/applications/${id}`, body)),
  changeStatus: (id, status, extra = {}) => data(api.post(`/applications/${id}/status`, { status, ...extra })),
  remove: (id) => data(api.delete(`/applications/${id}`)),
  qualityCheck: (id) => data(api.post(`/applications/${id}/quality-check`)),
};

// Overview metrics and analytics, computed server-side from your saved jobs and applications.
export const dashboardApi = {
  stats: () => data(api.get("/dashboard/stats")),
  analytics: () => data(api.get("/dashboard/analytics")),
};

// Recruiter contacts (server: /api/recruiters/*).
export const recruitersApi = {
  list: (params = {}) => data(api.get("/recruiters", { params })),
  get: (id) => data(api.get(`/recruiters/${id}`)),
  create: (body) => data(api.post("/recruiters", body)),
  update: (id, body) => data(api.put(`/recruiters/${id}`, body)),
  remove: (id) => data(api.delete(`/recruiters/${id}`)),
};

// Recruiter messages with a human approval gate: draft -> approved -> sent.
// Kithi never sends anything. "mailto" returns a link that opens YOUR email app, and is only available after approval.
export const recruiterMessagesApi = {
  list: (params = {}) => data(api.get("/recruiter-messages", { params })),
  get: (id) => data(api.get(`/recruiter-messages/${id}`)),
  generate: (body) => data(api.post("/recruiter-messages/generate", body, { timeout: AI_TIMEOUT })),
  edit: (id, body) => data(api.put(`/recruiter-messages/${id}`, body)),
  approve: (id) => data(api.post(`/recruiter-messages/${id}/approve`, { confirmed_by_user: true })),
  mailto: (id) => data(api.get(`/recruiter-messages/${id}/mailto`)),
  markSent: (id, note) => data(api.post(`/recruiter-messages/${id}/mark-sent`, { confirmed_by_user: true, note: note || null })),
  remove: (id) => data(api.delete(`/recruiter-messages/${id}`)),
};

// AI Career Coach: chat (LangGraph router), skill gaps, roadmaps, goals, skills, progress and GitHub analysis.
export const coachApi = {
  chat: (body) => data(api.post("/coach/chat", body, { timeout: AI_TIMEOUT })),
};

export const careerApi = {
  skillGaps: () => data(api.get("/career/skill-gaps")),
  createRoadmap: (body) => data(api.post("/career/roadmap", body, { timeout: AI_TIMEOUT })),
  plans: () => data(api.get("/career/plans")),
  updatePlanItem: (id, index, done) => data(api.patch(`/career/plans/${id}/items/${index}`, { done })),
  removePlan: (id) => data(api.delete(`/career/plans/${id}`)),
  createGoal: (body) => data(api.post("/career/goals", body)),
  saveSkill: (body) => data(api.post("/career/skills", body)),
  progress: () => data(api.get("/career/progress")),
  github: (username) => data(api.get("/career/github", { params: username ? { username } : {} })),
};

// Career Memory Engine: review, edit and delete what Kithi has stored about you.
export const memoryApi = {
  overview: () => data(api.get("/memory")),
  remove: (section, id) => data(api.delete(`/memory/${section}/${id}`)),
  edit: (section, id, body) => data(api.patch(`/memory/${section}/${id}`, body)),
};

// Interview Lab: generated questions, answer evaluation and feedback.
export const interviewsApi = {
  sessions: () => data(api.get("/interviews/sessions")),
  getSession: (id) => data(api.get(`/interviews/sessions/${id}`)),
  createSession: (body) => data(api.post("/interviews/sessions", body, { timeout: AI_TIMEOUT })),
  removeSession: (id) => data(api.delete(`/interviews/sessions/${id}`)),
  answer: (id, body) => data(api.post(`/interviews/sessions/${id}/answer`, body, { timeout: AI_TIMEOUT })),
  complete: (id) => data(api.post(`/interviews/sessions/${id}/complete`)),
};

// Salary Intelligence: estimator, saved offers, comparison and negotiation drafts.
export const salaryApi = {
  estimate: (body) => data(api.post("/salary/estimate", body)),
  offers: () => data(api.get("/salary/offers")),
  createOffer: (body) => data(api.post("/salary/offers", body)),
  removeOffer: (id) => data(api.delete(`/salary/offers/${id}`)),
  compare: (ids) => data(api.post("/salary/compare", { ids })),
  negotiation: (id, body) => data(api.post(`/salary/offers/${id}/negotiation-message`, body, { timeout: AI_TIMEOUT })),
};

// Job Search Recovery: read-only analysis of your own tracked data (server: GET /api/recovery).
export const recoveryApi = {
  get: () => data(api.get("/recovery")),
};
