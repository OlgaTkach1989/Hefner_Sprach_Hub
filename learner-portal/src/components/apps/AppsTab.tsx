import { useMemo, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import "./AppsTab.css";

type AppsTabProps = {
  email: string;
};

type ExternalAppCard = {
  id: "teams" | "outlookCalendar" | "jupyterNotebook";
  title: string;
  description: string;
  href: string;
  details: string;
  icon: ReactNode;
};

const buildExternalUrl = (baseUrl: string, params: Record<string, string | undefined>) => {
  try {
    const url = new URL(baseUrl);
    Object.entries(params).forEach(([key, value]) => {
      if (value) {
        url.searchParams.set(key, value);
      }
    });
    return url.toString();
  } catch {
    return baseUrl;
  }
};

const TeamsIcon = () => (
  <svg viewBox="0 0 48 48" aria-hidden="true">
    <rect x="7" y="13" width="18" height="22" rx="3.6" fill="#4B53BC" />
    <rect x="18" y="10" width="17" height="28" rx="4" fill="#6264A7" />
    <circle cx="37.2" cy="18" r="4.8" fill="#7B83EB" />
    <path d="M32 27.2c0-3 2.43-5.45 5.45-5.45S42.9 24.2 42.9 27.2v5.4H32v-5.4Z" fill="#7B83EB" />
    <path d="M13.4 18.2h12.3v3.2h-4.35V31h-3.55v-9.6H13.4v-3.2Z" fill="#FFFFFF" />
  </svg>
);

const OutlookIcon = () => (
  <svg viewBox="0 0 48 48" aria-hidden="true">
    <rect x="8" y="13" width="15" height="22" rx="3.4" fill="#0F6CBD" />
    <rect x="19" y="10" width="21" height="28" rx="4" fill="#1976D2" />
    <path d="M22 17.2h15a2 2 0 0 1 2 2v9.6a2 2 0 0 1-2 2H22Z" fill="#42A5F5" />
    <path d="M22 18.5 30 24l9-5.5" fill="none" stroke="#FFFFFF" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.1" />
    <path d="M14.9 19.1c-3.3 0-5.7 2.25-5.7 5.9s2.4 5.9 5.7 5.9 5.7-2.25 5.7-5.9-2.4-5.9-5.7-5.9Zm0 2.85c1.5 0 2.5 1.16 2.5 3.05 0 1.91-1 3.1-2.5 3.1s-2.5-1.19-2.5-3.1c0-1.89 1-3.05 2.5-3.05Z" fill="#FFFFFF" />
  </svg>
);

const JupyterIcon = () => (
  <svg viewBox="0 0 48 48" aria-hidden="true">
    <circle cx="24" cy="24" r="6.2" fill="#F37626" />
    <path d="M11.2 15.4c2.7-4.2 7.4-6.7 12.8-6.7s10.1 2.5 12.8 6.7" fill="none" stroke="#616161" strokeLinecap="round" strokeWidth="3" />
    <path d="M36.8 32.6c-2.7 4.2-7.4 6.7-12.8 6.7s-10.1-2.5-12.8-6.7" fill="none" stroke="#616161" strokeLinecap="round" strokeWidth="3" />
    <circle cx="10.3" cy="12.1" r="2.7" fill="#F37626" />
    <circle cx="38.2" cy="14.8" r="2.1" fill="#9E9E9E" />
    <circle cx="39.1" cy="35.2" r="2.8" fill="#F37626" />
  </svg>
);

export const AppsTab = ({ email }: AppsTabProps) => {
  const { t } = useTranslation();

  const teamsBaseUrl =
    String(import.meta.env.VITE_TEAMS_URL ?? "").trim() || "https://teams.microsoft.com/v2/";
  const outlookBaseUrl =
    String(import.meta.env.VITE_OUTLOOK_CALENDAR_URL ?? "").trim() || "https://outlook.office.com/calendar/view/week";
  const jupyterBaseUrl =
    String(import.meta.env.VITE_JUPYTER_URL ?? "").trim() || "/lab/";

  const cards = useMemo<ExternalAppCard[]>(
    () => [
      {
        id: "teams",
        title: t("appTeamsTitle"),
        description: t("appTeamsDescription"),
        details: t("appTeamsDetails"),
        href: buildExternalUrl(teamsBaseUrl, {
          login_hint: email,
          prompt: "select_account",
        }),
        icon: <TeamsIcon />,
      },
      {
        id: "outlookCalendar",
        title: t("appOutlookTitle"),
        description: t("appOutlookDescription"),
        details: t("appOutlookDetails"),
        href: buildExternalUrl(outlookBaseUrl, {
          login_hint: email,
          prompt: "select_account",
          auth: "2",
        }),
        icon: <OutlookIcon />,
      },
      {
        id: "jupyterNotebook",
        title: t("appPlannerTitle"),
        description: t("appPlannerDescription"),
        details: t("appPlannerDetails"),
        href: buildExternalUrl(jupyterBaseUrl, {
          login_hint: email,
          prompt: "select_account",
        }),
        icon: <JupyterIcon />,
      },
    ],
    [email, jupyterBaseUrl, outlookBaseUrl, t, teamsBaseUrl],
  );

  return (
    <section className="apps-tab" aria-label={t("tabApp")}>
      <header className="apps-tab__hero">
        <div>
          <p className="apps-tab__eyebrow">{t("tabApp")}</p>
          <h2>{t("appTitle")}</h2>
          <p className="apps-tab__lead">{t("appIntro")}</p>
        </div>
        <div className="apps-tab__identity">
          <span>{t("appAccessLabel")}</span>
          <strong>{email || t("appAccessFallback")}</strong>
        </div>
      </header>

      <div className="apps-tab__grid">
        {cards.map((card) => (
          <article key={card.id} className="apps-tab__card">
            <div className="apps-tab__icon-wrap">{card.icon}</div>
            <div className="apps-tab__card-copy">
              <h3>{card.title}</h3>
              <p>{card.description}</p>
              <span>{card.details}</span>
            </div>
            <a href={card.href} target="_blank" rel="noreferrer" className="apps-tab__action">
              {t("appOpen")}
            </a>
          </article>
        ))}
      </div>

      <div className="apps-tab__notes">
        <article className="apps-tab__note-card">
          <h3>{t("appWorkflowTitle")}</h3>
          <ol className="apps-tab__steps">
            <li>{t("appWorkflowStep1")}</li>
            <li>{t("appWorkflowStep2")}</li>
            <li>{t("appWorkflowStep3")}</li>
          </ol>
        </article>

        <article className="apps-tab__note-card">
          <h3>{t("appSupportTitle")}</h3>
          <p>{t("appSupportBody")}</p>
        </article>
      </div>
    </section>
  );
};
