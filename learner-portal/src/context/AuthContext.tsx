import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { clearTokens } from "../api/authStorage";
import { fetchStudentMe, logoutStudentSession } from "../api/onlineStudentApi";
import type { StudentProfile } from "../types";

type AuthContextValue = {
  profile: StudentProfile | null;
  isAuthenticated: boolean;
  isReady: boolean;
  applyLogin: (profile: StudentProfile) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const manualSessionRef = useRef(false);

  useEffect(() => {
    let isMounted = true;

    fetchStudentMe()
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
      applyLogin: (nextProfile) => {
        manualSessionRef.current = true;
        setProfile(nextProfile);
        setIsAuthenticated(true);
        setIsReady(true);
      },
      logout: () => {
        manualSessionRef.current = false;
        clearTokens();
        void logoutStudentSession().catch(() => undefined);
        setProfile(null);
        setIsAuthenticated(false);
        setIsReady(true);
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
