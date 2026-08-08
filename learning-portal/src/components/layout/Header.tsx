import { Link } from "react-router-dom"

import logo from "../../assets/hefner-sprach-hub-logo.jpeg"
import { useUiPreferences } from "../../context/UiPreferencesContext"
import styles from "./Header.module.css"

export const Header = () => {
  const { locale, setLocale } = useUiPreferences()

  return (
    <header className={styles.publicHeader}>
      <div className={styles.inner}>
        <Link to="/" className={styles.brandLink}>
          <img src={logo} className={styles.logo} alt="Hefner Sprach Hub" />
          <span>
            <strong>HEFNER SPRACH HUB</strong>
          </span>
        </Link>

        <div className={styles.languageSwitch} aria-label="Language">
          <button
            type="button"
            className={locale === "de" ? styles.activeLanguage : ""}
            onClick={() => setLocale("de")}
            title="Deutsch"
          >
            DE
          </button>
          <i aria-hidden="true" />
          <button
            type="button"
            className={locale === "uk" ? styles.activeLanguage : ""}
            onClick={() => setLocale("uk")}
            title="Українська"
          >
            UK
          </button>
          <i aria-hidden="true" />
          <button
            type="button"
            className={locale === "ru" ? styles.activeLanguage : ""}
            onClick={() => setLocale("ru")}
            title="Русский"
          >
            RU
          </button>
        </div>
      </div>
    </header>
  )
}
