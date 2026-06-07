import { FormEvent, useEffect, useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { loginPublicStudent } from "../api/onlineApi"
import { resolveLearnerCabinetAccess } from "../utils/learnerCabinet"
import "./PublicSignInPage.css"

const PUBLIC_HOME_PATH = "/home"

export const PublicSignInPage = () => {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const siteUrl = (import.meta.env.VITE_PUBLIC_SITE_URL ?? "https://onlinelesson.serveftp.com").replace(/\/+$/, "")
  const apiBaseUrl = String(import.meta.env.VITE_ONLINE_API_BASE_URL ?? "http://localhost:1212/api/online").replace(/\/+$/, "")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorText, setErrorText] = useState("")

  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search])
  const microsoftLoginUrl = `${apiBaseUrl}/public/auth/microsoft/start/?${new URLSearchParams({
    next: PUBLIC_HOME_PATH,
    login: "/",
    role: "student",
  }).toString()}`

  useEffect(() => {
    let active = true

    const externalError = searchParams.get("error") || ""
    if (externalError) {
      setErrorText(externalError)
    }

    const bootstrap = async () => {
      try {
        const resolution = await resolveLearnerCabinetAccess()
        if (!active) return
        if (resolution.kind !== "sign_in") {
          navigate(PUBLIC_HOME_PATH, { replace: true })
          return
        }
      } catch {
        if (!active) return
      }
    }

    void bootstrap()
    return () => {
      active = false
    }
  }, [navigate, searchParams])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIsSubmitting(true)
    setErrorText("")

    try {
      await loginPublicStudent(email.trim(), password)
      navigate(PUBLIC_HOME_PATH, { replace: true })
    } catch {
      setErrorText(t("signInPageError"))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="public-sign-in-page">
      <Helmet>
        <title>{t("signInPageTitle")}</title>
        <meta name="robots" content="noindex, nofollow" />
        <link rel="canonical" href={`${siteUrl}/`} />
      </Helmet>

      <section className="public-sign-in-page__box">
        <p className="public-sign-in-page__eyebrow">{t("brand")}</p>
        <h1>{t("signInPageTitle")}</h1>
        <p className="public-sign-in-page__intro">{t("signInPageIntro")}</p>

        <form className="public-sign-in-page__form" onSubmit={submit}>
          <label className="public-sign-in-page__field">
            <span>{t("email")}</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              placeholder="name@company.com"
              required
            />
          </label>

          <label className="public-sign-in-page__field">
            <span>{t("password")}</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              placeholder={t("password")}
              required
            />
          </label>

          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? t("loading") : t("signInPageButton")}
          </button>
        </form>

        <div className="public-sign-in-page__divider">
          <span>{t("orLabel")}</span>
        </div>

        <button
          type="button"
          className="public-sign-in-page__sso-btn"
          disabled={isSubmitting}
          onClick={() => window.location.assign(microsoftLoginUrl)}
        >
          <span className="public-sign-in-page__sso-icon">M</span>
          <span>{t("signInPageMicrosoftButton")}</span>
        </button>

        <p className="public-sign-in-page__meta">{t("signInPageAccessNote")}</p>
        {errorText ? <p className="public-sign-in-page__error">{errorText}</p> : null}

        <div className="public-sign-in-page__actions">
          <Link to="/home#sections">{t("signInPageBrowseCourses")}</Link>
          <Link to="/home">{t("backHome")}</Link>
        </div>
      </section>
    </main>
  )
}
