import { Link, useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { useEffect, useMemo, useRef, useState } from "react"

import { fetchPublicWorkspaceBySlug, fetchPublicWorkspaces } from "../../api/onlineApi"
import logo from "../../assets/logo.svg"
import themeIcon from "../../assets/theme-sun-moon.svg"
import userIcon from "../../assets/user-icon.svg"
import { useUiPreferences } from "../../context/UiPreferencesContext"
import type { WorkspaceOfficeDefinition } from "../../types"
import { resolveLearnerCabinetAccess } from "../../utils/learnerCabinet"
import styles from "./Header.module.css"

type HeaderWorkspaceMenu = {
  slug: string
  title: string
  subtitle: string
  courses: Array<{
    slug: string
    title: string
    description: string
  }>
}

export const Header = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [isSearchOpen, setIsSearchOpen] = useState(false)
  const [isCatalogLoading, setIsCatalogLoading] = useState(false)
  const [catalogError, setCatalogError] = useState("")
  const [catalogGroups, setCatalogGroups] = useState<HeaderWorkspaceMenu[]>([])
  const [cabinetMessage, setCabinetMessage] = useState("")
  const [isCabinetBusy, setIsCabinetBusy] = useState(false)
  const { t } = useTranslation()
  const { theme, toggleTheme } = useUiPreferences()
  const navigate = useNavigate()
  const appBasePath = import.meta.env.BASE_URL ?? "/"
  const searchMenuRef = useRef<HTMLDivElement | null>(null)
  const normalizedBasePath = appBasePath.endsWith("/") ? appBasePath.slice(0, -1) : appBasePath
  const homePath = `${normalizedBasePath || ""}/home`
  const homeHashLink = (hash: string) => `${homePath}${hash}`

  const closeMenu = () => {
    setIsMenuOpen(false)
    setIsSearchOpen(false)
  }

  useEffect(() => {
    if (!isSearchOpen || catalogGroups.length > 0) {
      return
    }

    let active = true
    setIsCatalogLoading(true)
    setCatalogError("")

    const loadCatalog = async () => {
      try {
        const summaries = await fetchPublicWorkspaces()
        const publicGroups = summaries
          .filter((workspace) => workspace.kind === "group" && workspace.showOnHomepage)
          .sort((left, right) => left.sortOrder - right.sortOrder)

        const details = await Promise.all(
          publicGroups.map(async (workspace) => {
            try {
              return await fetchPublicWorkspaceBySlug(workspace.slug)
            } catch {
              return null
            }
          }),
        )

        if (!active) return
        const nextCatalog = details
          .filter((workspace): workspace is WorkspaceOfficeDefinition => workspace !== null)
          .map((workspace) => {
            const uniqueCourses = new Map<string, { slug: string; title: string; description: string }>()
            for (const course of workspace.courses) {
              const slug = String(course.linkedCourseSlug || "").trim()
              if (!slug || uniqueCourses.has(slug)) continue
              uniqueCourses.set(slug, {
                slug,
                title: course.title,
                description: course.description,
              })
            }

            return {
              slug: workspace.slug,
              title: workspace.title,
              subtitle: workspace.subtitle || workspace.summary,
              courses: [...uniqueCourses.values()].slice(0, 6),
            }
          })

        setCatalogGroups(nextCatalog)
      } catch {
        if (!active) return
        setCatalogError(t("headerSearchError"))
      } finally {
        if (!active) return
        setIsCatalogLoading(false)
      }
    }

    void loadCatalog()
    return () => {
      active = false
    }
  }, [catalogGroups.length, isSearchOpen, t])

  useEffect(() => {
    if (!isSearchOpen) return

    const handlePointerDown = (event: MouseEvent) => {
      if (!searchMenuRef.current?.contains(event.target as Node)) {
        setIsSearchOpen(false)
      }
    }

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsSearchOpen(false)
      }
    }

    document.addEventListener("mousedown", handlePointerDown)
    document.addEventListener("keydown", handleEscape)
    return () => {
      document.removeEventListener("mousedown", handlePointerDown)
      document.removeEventListener("keydown", handleEscape)
    }
  }, [isSearchOpen])

  useEffect(() => {
    if (!cabinetMessage) return
    const timer = window.setTimeout(() => setCabinetMessage(""), 5000)
    return () => window.clearTimeout(timer)
  }, [cabinetMessage])

  const handleCabinetClick = async () => {
    if (isCabinetBusy) return

    setIsCabinetBusy(true)
    setCabinetMessage("")
    try {
      const resolution = await resolveLearnerCabinetAccess()
      if (resolution.kind === "dashboard") {
        window.location.assign(resolution.url)
        return
      }
      if (resolution.kind === "sign_in") {
        navigate(resolution.url)
        closeMenu()
        return
      }
      setCabinetMessage(resolution.message || t("headerCabinetBlocked"))
    } catch {
      setCabinetMessage(t("headerCabinetBlocked"))
    } finally {
      setIsCabinetBusy(false)
    }
  }

  const hasCatalogColumns = useMemo(() => catalogGroups.length > 0, [catalogGroups.length])

  return (
    <header
      className={`${styles.publicHeader} ${isMenuOpen ? styles.isOpen : ""}`}
    >
      <div className={styles.inner}>
        <div className={styles.brand}>
          <Link to="/home" className={styles.brandLink} onClick={closeMenu}>
            <img src={logo} className={styles.logo} alt="Logo" />
            <span>{t("brand")}</span>
          </Link>
        </div>

        <div
          className={`${styles.contentWrapper} ${isMenuOpen ? styles.active : ""}`}
        >
          <nav className={styles.nav} aria-label="Main navigation">
            <div className={styles.searchShell} ref={searchMenuRef}>
              <button
                type="button"
                className={`${styles.searchTrigger} ${isSearchOpen ? styles.searchTriggerActive : ""}`}
                onClick={() => setIsSearchOpen((current) => !current)}
                aria-expanded={isSearchOpen}
                aria-haspopup="dialog"
              >
                {t("navSearch")}
              </button>

              {isSearchOpen ? (
                <div className={styles.searchDropdown} role="dialog" aria-label={t("headerSearchTitle")}>
                  <div className={styles.searchDropdownHead}>
                    <div>
                      <p className={styles.searchDropdownEyebrow}>{t("navSearch")}</p>
                      <h2>{t("headerSearchTitle")}</h2>
                    </div>
                    <p>{t("headerSearchSubtitle")}</p>
                  </div>

                  {isCatalogLoading ? <p className={styles.searchState}>{t("headerSearchLoading")}</p> : null}
                  {catalogError ? <p className={`${styles.searchState} ${styles.searchStateError}`}>{catalogError}</p> : null}

                  {!isCatalogLoading && !catalogError && hasCatalogColumns ? (
                    <div className={styles.searchGrid}>
                      {catalogGroups.map((workspace) => (
                        <section key={workspace.slug} className={styles.searchColumn}>
                          <Link
                            to={`/spaces/${workspace.slug}`}
                            className={styles.searchColumnTitle}
                            onClick={closeMenu}
                          >
                            {workspace.title}
                          </Link>
                          <p className={styles.searchColumnSubtitle}>{workspace.subtitle}</p>
                          <div className={styles.searchLinks}>
                            {workspace.courses.map((course) => (
                              <Link
                                key={`${workspace.slug}-${course.slug}`}
                                to={`/course/${course.slug}`}
                                className={styles.searchCourseLink}
                                onClick={closeMenu}
                              >
                                {course.title}
                              </Link>
                            ))}
                          </div>
                          <Link
                            to={`/spaces/${workspace.slug}`}
                            className={styles.searchColumnAction}
                            onClick={closeMenu}
                          >
                            {t("headerSearchOpenArea")}
                          </Link>
                        </section>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
            <a
              href={homeHashLink("#sections")}
              className={styles.navLink}
              onClick={closeMenu}
            >
              {t("navOffices")}
            </a>
            <a
              href={homeHashLink("#resources")}
              className={styles.navLink}
              onClick={closeMenu}
            >
              {t("navResources")}
            </a>
            <a
              href={homeHashLink("#faq")}
              className={styles.navLink}
              onClick={closeMenu}
            >
              {t("navFaq")}
            </a>
          </nav>
        </div>
        <div className={styles.controlsButtons}>
          <button
            type="button"
            className={`${styles.chip} ${styles.chipTheme}`}
            onClick={toggleTheme}
            aria-label={
              theme === "light"
                ? "Switch to dark theme"
                : "Switch to light theme"
            }
            title={theme === "light" ? "Dark mode" : "Light mode"}
          >
            <img
              src={themeIcon}
              alt=""
              aria-hidden="true"
              className={styles.themeIcon}
            />
          </button>
          <button
            type="button"
            className={styles.chip}
            onClick={() => void handleCabinetClick()}
            aria-label={t("heroCabinetCta")}
            title={t("heroCabinetCta")}
            disabled={isCabinetBusy}
          >
            <img
              src={userIcon}
              alt="user Icon"
              aria-hidden="true"
              className={styles.icon}
            />
          </button>
        </div>
        <button
          className={styles.burger}
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          aria-label="Toggle menu"
        >
          {isMenuOpen ? "✕" : "☰"}
        </button>

        {cabinetMessage ? (
          <div className={styles.statusBanner}>
            <span>{cabinetMessage}</span>
            <button type="button" onClick={() => setCabinetMessage("")} aria-label="Dismiss message">
              ✕
            </button>
          </div>
        ) : null}
      </div>
    </header>
  )
}
