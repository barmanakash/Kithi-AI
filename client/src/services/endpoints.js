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
  sources: () => data(api.get("/jobs/sources")),
  discover: (body) => data(api.post("/jobs/discover", body, { timeout: 120000 })),
  add: (body) => data(api.post("/jobs", body)),
  list: (params) => data(api.get("/jobs", { params })),
  get: (id) => data(api.get(`/jobs/${id}`)),
  remove: (id) => data(api.delete(`/jobs/${id}`)),
};

export const matchesApi = {
  list: (params) => data(api.get("/job-matches", { params })),
  detail: (jobId) => data(api.get(`/job-matches/${jobId}`)),
  weights: () => data(api.get("/job-matches/weights")),
  saveWeights: (body) => data(api.put("/job-matches/weights", body)),
  recompute: () => data(api.post("/job-matches/recompute")),
  explain: (jobId) => data(api.post(`/job-matches/${jobId}/explain`, null, { timeout: AI_TIMEOUT })),
};

export const scamApi = {
  assess: (body) => data(api.post("/scam/assess", body)),
  list: () => data(api.get("/scam/assessments")),
  remove: (id) => data(api.delete(`/scam/assessments/${id}`)),
};

export const applicationsApi = {
  list: (params) => data(api.get("/applications", { params })),
  create: (body) => data(api.post("/applications", body)),
  fromJob: (jobId) => data(api.post(`/applications/from-job/${jobId}`)),
  update: (id, body) => data(api.put(`/applications/${id}`, body)),
  changeStatus: (id, status, note) => data(api.patch(`/applications/${id}/status`, { status, note: note || null })),
  remove: (id) => data(api.delete(`/applications/${id}`)),
  timeline: () => data(api.get("/applications/timeline")),
  qualityCheck: (id) => data(api.post(`/applications/${id}/quality-check`)),
};

export const dashboardApi = {
  stats: () => data(api.get("/dashboard/stats")),
  analytics: () => data(api.get("/dashboard/analytics")),
};

export const generateApi = {
  tailorResume: (body) => data(api.post("/generate/tailored-resume", body, { timeout: AI_TIMEOUT })),
  coverLetter: (body) => data(api.post("/generate/cover-letter", body, { timeout: AI_TIMEOUT })),
  improveBullets: (body) => data(api.post("/generate/improve-bullets", body, { timeout: AI_TIMEOUT })),
  list: (params) => data(api.get("/generate/versions", { params })),
  get: (id) => data(api.get(`/generate/versions/${id}`)),
  update: (id, body) => data(api.put(`/generate/versions/${id}`, body)),
  remove: (id) => data(api.delete(`/generate/versions/${id}`)),
  exportDocx: (id) => api.get(`/generate/versions/${id}/export`, { responseType: "blob", timeout: 60000 }).then((r) => r.data),
};
