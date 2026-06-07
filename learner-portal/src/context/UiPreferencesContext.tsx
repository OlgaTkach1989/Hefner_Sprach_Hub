import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { Locale, ThemeMode } from "../types";

type UiPreferencesContextValue = {
  locale: Locale;
  theme: ThemeMode;
  setLocale: (next: Locale) => void;
  toggleTheme: () => void;
};

const THEME_KEY = "online_student_theme";
const LOCALE_KEY = "online_student_locale";

const UiPreferencesContext = createContext<UiPreferencesContextValue | null>(null);

export const UiPreferencesProvider = ({ children }: { children: ReactNode }) => {
  const { i18n } = useTranslation();
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const raw = localStorage.getItem(THEME_KEY);
    return raw === "dark" ? "dark" : "light";
  });
  const [locale, setLocale] = useState<Locale>(() => {
    const raw = localStorage.getItem(LOCALE_KEY);
    return raw === "de" ? "de" : "en";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    i18n.changeLanguage(locale);
    document.documentElement.setAttribute("lang", locale);
    localStorage.setItem(LOCALE_KEY, locale);
  }, [i18n, locale]);

  const value = useMemo<UiPreferencesContextValue>(
    () => ({
      locale,
      theme,
      setLocale,
      toggleTheme: () => setTheme((prev) => (prev === "light" ? "dark" : "light"))
    }),
    [locale, theme]
  );

  return <UiPreferencesContext.Provider value={value}>{children}</UiPreferencesContext.Provider>;
};

export const useUiPreferences = () => {
  const context = useContext(UiPreferencesContext);
  if (!context) {
    throw new Error("useUiPreferences must be used inside UiPreferencesProvider");
  }
  return context;
};
