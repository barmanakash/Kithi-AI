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
