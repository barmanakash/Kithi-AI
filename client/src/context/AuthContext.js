import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { setUnauthorizedHandler, tokenStore } from "../services/api";
import { authApi } from "../services/endpoints";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(Boolean(tokenStore.get()));

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  // Expired or invalid tokens detected by the API client end the session.
  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  // Restore the session on first load.
  useEffect(() => {
    if (!tokenStore.get()) {
      setInitializing(false);
      return;
    }
    authApi
      .me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setInitializing(false));
  }, []);

  const login = useCallback(async (email, password, remember = false) => {
    const token = await authApi.login({ email, password });
    tokenStore.set(token.access_token, remember);
    try {
      setUser(await authApi.me());
    } catch (err) {
      tokenStore.clear();
      throw err;
    }
  }, []);

  const register = useCallback(
    async ({ email, password, full_name }) => {
      await authApi.register({ email, password, full_name });
      await login(email, password, false);
    },
    [login]
  );

  const value = useMemo(
    () => ({ user, initializing, isAuthenticated: Boolean(user), login, register, logout }),
    [user, initializing, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
