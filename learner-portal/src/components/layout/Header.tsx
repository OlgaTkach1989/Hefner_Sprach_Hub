import { useTranslation } from "react-i18next";

import { useAuth } from "../../context/AuthContext";
import { useUiPreferences } from "../../context/UiPreferencesContext";
import logo from "../../assets/hefner-sprach-hub-logo.jpeg";
import "./Header.css";

type Props = {
  onLogout?: () => void;
};

export const Header = ({ onLogout }: Props) => {
  const { t } = useTranslation();
  const { locale, setLocale, theme, toggleTheme } = useUiPreferences();
  const { profile } = useAuth();
  const publicUrl = String(import.meta.env.VITE_ONLINE_PUBLIC_URL ?? "").trim() || "/";

  const themeTitle = theme === "light" ? t("themeLight") : t("themeDark");

  return (
    <header className="student-header">
      <a href={publicUrl} className="student-header__brand-link" rel="noreferrer">
        <img src={logo} className="student-header__logo" alt="Hefner Sprach Hub" />
        <span className="student-header__brand">
          <strong>HEFNER SPRACH HUB</strong>
          <small>Deutsch A1</small>
        </span>
      </a>

      <div className="student-header__meta">
        {profile ? <span className="student-header__user">{profile.first_name + " " + profile.last_name}</span> : null}
        <button type="button" className="student-header__chip" onClick={() => setLocale(locale === "de" ? "en" : "de")}>
          {locale.toUpperCase()}
        </button>
        <button
          type="button"
          className="student-header__chip student-header__chip--theme"
          onClick={toggleTheme}
          aria-label={themeTitle}
          title={themeTitle}
        >
          {theme === "light" ? (
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 4a1 1 0 0 1 1 1v1.2a1 1 0 1 1-2 0V5a1 1 0 0 1 1-1Zm5.66 2.34a1 1 0 0 1 1.41 0l.84.85a1 1 0 1 1-1.41 1.41l-.85-.84a1 1 0 0 1 0-1.42ZM12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8Zm9 3a1 1 0 1 1 0 2h-1.2a1 1 0 0 1 0-2H21Zm-17.8 0a1 1 0 0 1 0 2H2a1 1 0 1 1 0-2h1.2Zm15.46 5.54a1 1 0 0 1 0 1.41l-.84.85a1 1 0 0 1-1.42-1.41l.85-.85a1 1 0 0 1 1.41 0ZM12 17.8a1 1 0 0 1 1 1V20a1 1 0 1 1-2 0v-1.2a1 1 0 0 1 1-1Zm-5.66-1.26a1 1 0 0 1 1.41 0l.85.85a1 1 0 0 1-1.41 1.41l-.85-.84a1 1 0 0 1 0-1.42Zm1.41-9.35a1 1 0 0 1 0 1.41l-.85.84A1 1 0 0 1 5.5 8.03l.84-.85a1 1 0 0 1 1.41 0Z" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M20.1 14.05A8.05 8.05 0 0 1 9.95 3.9a1 1 0 0 0-1.35-1.22A10 10 0 1 0 21.32 15.4a1 1 0 0 0-1.22-1.35Z" />
            </svg>
          )}
        </button>
        {onLogout ? (
          <button type="button" className="student-header__chip" onClick={onLogout}>
            {t("logout")}
          </button>
        ) : null}
      </div>
    </header>
  );
};
