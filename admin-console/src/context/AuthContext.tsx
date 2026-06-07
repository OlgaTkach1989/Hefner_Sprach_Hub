import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { clearTokens } from "../api/authStorage";
import { fetchAdminMe, loginAdmin, logoutAdminSession } from "../api/staffAuthApi";
import type { StaffProfile } from "../types/auth";

type AuthContextValue = {
  profile: StaffProfile | null;
  isAuthenticated: boolean;
  isReady: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);
const configuredBasePath = (import.meta.env.VITE_ONLINE_ADMIN_BASE_PATH ?? "/").trim();
const normalizedBasePath = configuredBasePath === "/" ? "" : configuredBasePath.replace(/\/+$/, "");
const loginPath = `${normalizedBasePath}/login` || "/login";

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [profile, setProfile] = useState<StaffProfile | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const manualSessionRef = useRef(false);

  useEffect(() => {
    let isMounted = true;
    fetchAdminMe()
      .then((nextProfile) => {
        if (!isMounted) return;
        setProfile(nextProfile);
        setIsAuthenticated(true);
        manualSessionRef.current = true;
      })
      .catch(() => {
        if (!isMounted || manualSessionRef.current) return;
        clearTokens();
        setProfile(null);
        setIsAuthenticated(false);
      })
      .finally(() => {
        if (isMounted) {
          setIsReady(true);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      profile,
      isAuthenticated,
      isReady,
      login: async (identifier, password) => {
        const response = await loginAdmin(identifier, password);
        manualSessionRef.current = true;
        setProfile(response.profile);
        setIsAuthenticated(true);
        setIsReady(true);
      },
      logout: () => {
        manualSessionRef.current = false;
        clearTokens();
        void logoutAdminSession().catch(() => undefined);
        setProfile(null);
        setIsAuthenticated(false);
        window.location.assign(loginPath);
      },
    }),
    [isAuthenticated, isReady, profile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
};
