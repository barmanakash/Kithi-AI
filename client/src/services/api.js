import axios from "axios";

const TOKEN_KEY = "kithi_token";

export const API_URL = (process.env.REACT_APP_API_URL || "http://localhost:8000/api").replace(/\/+$/, "");

/**
 * Token storage. By default the token lives in sessionStorage (cleared when the tab closes).
 * "Keep me signed in" stores it in localStorage instead.
 */
export const tokenStore = {
  get() {
    try {
      return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token, persist = false) {
    this.clear();
    try {
      (persist ? localStorage : sessionStorage).setItem(TOKEN_KEY, token);
    } catch {
      /* storage unavailable */
    }
  },
  clear() {
    try {
      sessionStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

let unauthorizedHandler = null;
export const setUnauthorizedHandler = (fn) => {
  unauthorizedHandler = fn;
};

const api = axios.create({ baseURL: API_URL, timeout: 30000 });

api.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const cfg = error.config || {};
    // A 401 on a normal request means the session expired. Requests that legitimately return 401
    // for a wrong password (login, change password, delete account) opt out with skipAuthRedirect.
    if (error.response?.status === 401 && !cfg.skipAuthRedirect && tokenStore.get()) {
      tokenStore.clear();
      if (unauthorizedHandler) unauthorizedHandler();
    }
    return Promise.reject(error);
  }
);

export default api;
