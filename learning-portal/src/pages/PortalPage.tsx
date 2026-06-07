import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { isAxiosError } from "axios";
import { useTranslation } from "react-i18next";

import {
  buildPublicPortalCalendarUrl,
  fetchPublicPortal,
  fetchPublicPortalSessions,
  requestMagicLink,
} from "../api/onlineApi";
import { useUiPreferences } from "../context/UiPreferencesContext";
import type { PortalSession, PublicPortalResponse, PublicPortalSessionsResponse } from "../types";
import "./PortalPage.css";

const extractApiError = (error: unknown, fallback: string) => {
  if (!isAxiosError(error)) return fallback;
  const payload = error.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  if (typeof payload.token === "string") return payload.token;

  if (typeof payload === "object") {
    for (const value of Object.values(payload)) {
      if (Array.isArray(value) && typeof value[0] === "string") return value[0];
      if (typeof value === "string") return value;
    }
  }

  return fallback;
};

const formatDateTime = (value: string, locale: "de" | "en") => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(locale === "de" ? "de-DE" : "en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
};

const formatTokenExpiry = (value: string | undefined, locale: "de" | "en") => {
  if (!value) return "";
  return formatDateTime(value, locale);
};

const selectCourseTitle = (
  session: PortalSession,
  locale: "de" | "en",
) => (locale === "en" ? session.courseTitleEn : session.courseTitleDe);

export const PortalPage = () => {
  const { t } = useTranslation();
  const { locale } = useUiPreferences();
  const siteUrl = import.meta.env.VITE_PUBLIC_SITE_URL ?? "http://localhost:5182";
  const [searchParams, setSearchParams] = useSearchParams();
  const token = (searchParams.get("token") ?? "").trim();

  const [email, setEmail] = useState("");
  const [courseSlug, setCourseSlug] = useState("");
  const [requestMessage, setRequestMessage] = useState("");
  const [requestError, setRequestError] = useState("");
  const [requesting, setRequesting] = useState(false);

  const [portal, setPortal] = useState<PublicPortalResponse | null>(null);
  const [sessions, setSessions] = useState<PublicPortalSessionsResponse | null>(null);
  const [loadingPortal, setLoadingPortal] = useState(false);
  const [portalError, setPortalError] = useState("");

  const calendarUrl = useMemo(() => (token ? buildPublicPortalCalendarUrl(token) : ""), [token]);

  const loadPortal = async (rawToken: string) => {
    if (!rawToken) return;
    setLoadingPortal(true);
    setPortalError("");

    try {
      const [portalResponse, sessionsResponse] = await Promise.all([
        fetchPublicPortal(rawToken),
        fetchPublicPortalSessions(rawToken),
      ]);
      setPortal(portalResponse);
      setSessions(sessionsResponse);
    } catch (error) {
      setPortal(null);
      setSessions(null);
      setPortalError(extractApiError(error, t("portalLoadError")));
    } finally {
      setLoadingPortal(false);
    }
  };

  useEffect(() => {
    if (!token) {
      setPortal(null);
      setSessions(null);
      setPortalError("");
      return;
    }
    void loadPortal(token);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const handleMagicLinkRequest = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!email.trim()) return;
    setRequesting(true);
    setRequestError("");
    setRequestMessage("");

    try {
      const response = await requestMagicLink({
        email: email.trim(),
        course_slug: courseSlug.trim() || undefined,
      });
      setRequestMessage(response.detail || t("portalMagicLinkRequested"));
    } catch (error) {
      setRequestError(extractApiError(error, t("portalMagicLinkRequestError")));
    } finally {
      setRequesting(false);
    }
  };

  const handleUseToken = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextToken = (new FormData(event.currentTarget).get("portalToken") as string | null)?.trim() ?? "";
    if (!nextToken) return;
    setSearchParams({ token: nextToken });
  };

  const resetPortalView = () => {
    setSearchParams({});
    setPortal(null);
    setSessions(null);
    setPortalError("");
  };

  return (
    <main className="portal-page">
      <Helmet>
        <title>{t("portalTitle")}</title>
        <meta name="robots" content="noindex, nofollow" />
        <link rel="canonical" href={`${siteUrl}/portal`} />
      </Helmet>

      <section className="portal-page__panel">
        <h1>{t("portalTitle")}</h1>
        <p>{t("portalSubtitle")}</p>

        {!token ? (
          <>
            <form className="portal-page__form" onSubmit={handleMagicLinkRequest}>
              <label className="portal-page__label">
                {t("email")}
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  autoComplete="email"
                  placeholder={t("email")}
                />
              </label>
              <label className="portal-page__label">
                {t("portalCourseSlugOptional")}
                <input
                  type="text"
                  value={courseSlug}
                  onChange={(event) => setCourseSlug(event.target.value)}
                  placeholder={t("portalCourseSlugOptional")}
                />
              </label>
              <button type="submit" disabled={requesting}>
                {requesting ? t("loading") : t("portalSendMagicLink")}
              </button>
            </form>
            {requestMessage ? <p className="portal-page__message">{requestMessage}</p> : null}
            {requestError ? <p className="portal-page__error">{requestError}</p> : null}

            <div className="portal-page__token-box">
              <h2>{t("portalHaveTokenTitle")}</h2>
              <form className="portal-page__form portal-page__form--inline" onSubmit={handleUseToken}>
                <input name="portalToken" type="text" placeholder={t("portalTokenPlaceholder")} required />
                <button type="submit">{t("portalOpenWithToken")}</button>
              </form>
            </div>
          </>
        ) : null}

        {token ? (
          <div className="portal-page__content">
            {loadingPortal ? <p>{t("loading")}</p> : null}
            {portalError ? <p className="portal-page__error">{portalError}</p> : null}
            {!loadingPortal && !portal ? (
              <div className="portal-page__actions">
                <button type="button" onClick={resetPortalView}>
                  {t("portalUseAnotherEmail")}
                </button>
              </div>
            ) : null}
            {portal && !loadingPortal ? (
              <>
                <div className="portal-page__meta">
                  <p>
                    {t("portalStudent")}: {portal.profile.first_name} {portal.profile.last_name}
                  </p>
                  <p>
                    {t("email")}: {portal.profile.email}
                  </p>
                  <p>
                    {t("portalTokenExpires")}: {formatTokenExpiry(portal.tokenExpiresAt, locale)}
                  </p>
                </div>

                <div className="portal-page__enrollments">
                  <h2>{t("portalEnrollmentsTitle")}</h2>
                  <ul>
                    {portal.enrollments.map((item) => (
                      <li key={item.enrollmentId}>
                        <strong>{locale === "en" ? item.course.titleEn : item.course.titleDe}</strong> ·{" "}
                        {item.cohort.groupName} ({item.cohort.groupCode})
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="portal-page__actions">
                  <a href={calendarUrl}>{t("portalDownloadCalendar")}</a>
                  <button type="button" onClick={resetPortalView}>
                    {t("portalUseAnotherEmail")}
                  </button>
                </div>

                <h2>{t("portalSessionsTitle")}</h2>
                {!sessions?.results.length ? <p>{t("portalNoSessions")}</p> : null}
                {sessions?.results.length ? (
                  <div className="portal-page__table-wrap">
                    <table className="portal-page__table">
                      <thead>
                        <tr>
                          <th>{t("portalTableCourse")}</th>
                          <th>{t("portalTableSession")}</th>
                          <th>{t("portalTableGroup")}</th>
                          <th>{t("portalTableStartsAt")}</th>
                          <th>{t("portalTableStatus")}</th>
                          <th>{t("portalTableJoin")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sessions.results.map((item) => (
                          <tr key={`${item.enrollmentId}-${item.id}`}>
                            <td>{selectCourseTitle(item, locale)}</td>
                            <td>{item.title}</td>
                            <td>{item.groupCode}</td>
                            <td>{formatDateTime(item.starts_at, locale)}</td>
                            <td>{item.status}</td>
                            <td>
                              {item.join_url ? (
                                <a href={item.join_url} target="_blank" rel="noreferrer">
                                  {t("portalJoinLesson")}
                                </a>
                              ) : (
                                "-"
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </>
            ) : null}
          </div>
        ) : null}

        <div className="portal-page__back">
          <Link to="/">{t("backHome")}</Link>
        </div>
      </section>
    </main>
  );
};
