import { NavLink } from "react-router-dom";
import { useMemo } from "react";

import { useGetOnlineCohortsQuery, useGetOnlineCoursesQuery } from "@/bll/online/online.service";
import OnlinePage from "@/pages/online/OnlinePage";
import { useAuth } from "@/context/AuthContext";
import { CuratorOnlineOperationsSection } from "./CuratorOnlineOperationsSection";
import "./CuratorWorkspacePage.css";

type WorkspaceSection = "home" | "documents" | "portfolio" | "online" | "information" | "feedback";

type WorkspacePageProps = {
  section: WorkspaceSection;
};

type NavItem = {
  id: WorkspaceSection;
  label: string;
  href: string;
  icon: JSX.Element;
};

const OverviewIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 4h7v7H4V4Zm9 0h7v4h-7V4ZM4 13h4v7H4v-7Zm6 0h10v7H10v-7Z" />
  </svg>
);

const DocumentIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M7 3h7l5 5v13H7V3Zm7 1.6V9h4.4L14 4.6ZM9 12h6v1.5H9V12Zm0 3h6v1.5H9V15Z" />
  </svg>
);

const PortfolioIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M5 6h14a2 2 0 0 1 2 2v9H3V8a2 2 0 0 1 2-2Zm3-3h8v2H8V3Zm-5 16h18v2H3v-2Z" />
  </svg>
);

const OnlineIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 5h16a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-6l-2 3-2-3H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Zm3 3v6h10V8H7Zm11 0h2v6h-2V8Z" />
  </svg>
);

const InfoIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20Zm-.75 6h1.5V6.5h-1.5V8Zm0 9h1.5v-6h-1.5v6Z" />
  </svg>
);

const FeedbackIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 4h16v11H7l-3 3V4Zm4 4v1.5h8V8H8Zm0 3v1.5h5V11H8Z" />
  </svg>
);

const SECTION_META: Record<WorkspaceSection, { title: string; subtitle: string }> = {
  home: {
    title: "Home",
    subtitle: "Personal workspace for day-to-day instructor operations, course supervision, and communication.",
  },
  documents: {
    title: "Documents",
    subtitle: "Operational guides, publishing policies, and reusable templates for your internal academy.",
  },
  portfolio: {
    title: "Portfolio",
    subtitle: "Course portfolio analytics, cohort health, and governance controls in one place.",
  },
  online: {
    title: "Online",
    subtitle: "Live session management for cohorts, attendance, and delivery flow.",
  },
  information: {
    title: "Information",
    subtitle: "Reference notes, integrations, and service touchpoints for instructors and coordinators.",
  },
  feedback: {
    title: "Feedback",
    subtitle: "Escalation routines, communication loops, and service feedback guidelines.",
  },
};

const HomeSection = () => {
  const { profile } = useAuth();
  const { data: courseListData } = useGetOnlineCoursesQuery();
  const { data: cohortListData } = useGetOnlineCohortsQuery();

  const courseCards = courseListData?.results ?? [];
  const cohortCards = cohortListData?.results ?? [];

  const overview = useMemo(() => {
    const students = courseCards.reduce((sum, item) => sum + item.studentsCount, 0);
    const sessions = courseCards.reduce((sum, item) => sum + item.sessionsSummary.total, 0);
    const attendance =
      courseCards.length > 0
        ? courseCards.reduce((sum, item) => sum + item.attendancePercent, 0) / courseCards.length
        : 0;

    const nearestCohort = [...cohortCards]
      .filter((item) => Boolean(item.nearestSessionAt))
      .sort((left, right) => {
        const leftTime = left.nearestSessionAt ? new Date(left.nearestSessionAt).getTime() : Number.MAX_SAFE_INTEGER;
        const rightTime = right.nearestSessionAt ? new Date(right.nearestSessionAt).getTime() : Number.MAX_SAFE_INTEGER;
        return leftTime - rightTime;
      })[0];

    return {
      students,
      sessions,
      attendance,
      nearestCohort,
    };
  }, [cohortCards, courseCards]);

  return (
    <div className="workspace-grid">
      <section className="workspace-card workspace-card--hero">
        <div className="workspace-card__eyebrow">Personal instructor workspace</div>
        <h2>{profile?.fullName ?? "Instructor"}</h2>
        <p className="workspace-card__lede">
          Coordinate delivery, track cohort health, and manage the internal academy from one structured workspace.
        </p>
        <div className="workspace-card__chips">
          <span>{courseCards.length} courses</span>
          <span>{cohortCards.length} cohorts</span>
          <span>{overview.students} learners</span>
        </div>
      </section>

      <section className="workspace-card">
        <div className="workspace-card__eyebrow">Profile</div>
        <h3>Instructor profile</h3>
        <dl className="workspace-definition-list">
          <div>
            <dt>Role</dt>
            <dd>{profile?.isSuperuser ? "Superuser instructor" : "Instructor"}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{profile?.email ?? "-"}</dd>
          </div>
          <div>
            <dt>Workspace</dt>
            <dd>Internal academy</dd>
          </div>
          <div>
            <dt>Access</dt>
            <dd>{profile?.isAdmin ? "Admin" : "Staff"}</dd>
          </div>
        </dl>
      </section>

      <section className="workspace-card">
        <div className="workspace-card__eyebrow">Operational KPIs</div>
        <h3>Current footprint</h3>
        <div className="workspace-metric-grid">
          <article>
            <span>Portfolio</span>
            <strong>{courseCards.length}</strong>
            <small>published courses</small>
          </article>
          <article>
            <span>Cohorts</span>
            <strong>{cohortCards.length}</strong>
            <small>active groups</small>
          </article>
          <article>
            <span>Sessions</span>
            <strong>{overview.sessions}</strong>
            <small>tracked sessions</small>
          </article>
          <article>
            <span>Attendance</span>
            <strong>{Math.round(overview.attendance || 0)}%</strong>
            <small>average presence</small>
          </article>
        </div>
      </section>

      <section className="workspace-card">
        <div className="workspace-card__eyebrow">Priority queue</div>
        <h3>Next coordination step</h3>
        {overview.nearestCohort ? (
          <div className="workspace-highlight">
            <strong>{overview.nearestCohort.groupCode}</strong>
            <p>{overview.nearestCohort.groupName}</p>
            <span>{overview.nearestCohort.courseTitleDe}</span>
          </div>
        ) : (
          <p className="workspace-empty-copy">No upcoming cohort session is scheduled yet.</p>
        )}
      </section>

      <section className="workspace-card workspace-card--span-2">
        <div className="workspace-card__eyebrow">Operating rhythm</div>
        <h3>Recommended daily flow</h3>
        <div className="workspace-process-grid">
          <article>
            <strong>Morning check</strong>
            <p>Review upcoming cohorts, session readiness, and unresolved governance items.</p>
          </article>
          <article>
            <strong>Delivery supervision</strong>
            <p>Open live sessions, verify join links, and monitor attendance drift during the day.</p>
          </article>
          <article>
            <strong>Content governance</strong>
            <p>Refresh portfolio metadata, training controls, and AI knowledge coverage for active courses.</p>
          </article>
        </div>
      </section>
    </div>
  );
};

const DocumentsSection = () => {
  const documents = [
    {
      title: "Attendance escalation policy",
      description: "Thresholds, escalation timing, and expected instructor actions for at-risk cohorts.",
      status: "Policy",
    },
    {
      title: "Course publishing checklist",
      description: "Pre-launch review for content, visibility, pricing, and cohort readiness.",
      status: "Checklist",
    },
    {
      title: "Notebook assignment review",
      description: "Operational notes for Jupyter launches, grader validation, and submission audit.",
      status: "Guide",
    },
    {
      title: "Directus content sync notes",
      description: "Practical checklist for content updates, metadata completeness, and index rebuilds.",
      status: "Runbook",
    },
  ];

  return (
    <div className="workspace-list-grid">
      {documents.map((item) => (
        <article key={item.title} className="workspace-list-card">
          <span className="workspace-list-card__badge">{item.status}</span>
          <h3>{item.title}</h3>
          <p>{item.description}</p>
        </article>
      ))}
    </div>
  );
};

const InformationSection = () => {
  const blocks = [
    {
      title: "System touchpoints",
      lines: [
        "Public portal: course presentation and onboarding flow",
        "Student workspace: learning delivery, labs, and recordings",
        "Directus: content authoring and flows",
      ],
    },
    {
      title: "Operational rules",
      lines: [
        "Use the Online tab for live session lifecycle actions.",
        "Use the Portfolio tab for course analytics and governance.",
        "Use Directus for structured content changes before re-indexing knowledge.",
      ],
    },
    {
      title: "Response expectations",
      lines: [
        "Course owner review within SLA for unresolved AI questions.",
        "Attendance anomalies checked on the same working day.",
        "Publishing issues escalated before the next live session.",
      ],
    },
  ];

  return (
    <div className="workspace-list-grid">
      {blocks.map((item) => (
        <article key={item.title} className="workspace-list-card">
          <h3>{item.title}</h3>
          <ul className="workspace-bullet-list">
            {item.lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
};

const FeedbackSection = () => {
  const items = [
    {
      title: "Delivery feedback loop",
      description: "Collect live session issues, summarize actions, and pass ownership to the correct course owner.",
    },
    {
      title: "Learner escalation",
      description: "Escalate blockers around access, attendance, or notebook execution before the next learning window.",
    },
    {
      title: "Content improvement notes",
      description: "Document recurring questions and convert them into FAQ, KB entries, or updated lesson materials.",
    },
  ];

  return (
    <div className="workspace-list-grid">
      {items.map((item) => (
        <article key={item.title} className="workspace-list-card">
          <h3>{item.title}</h3>
          <p>{item.description}</p>
        </article>
      ))}
    </div>
  );
};

export const CuratorWorkspacePage = ({ section }: WorkspacePageProps) => {
  const { logout, profile } = useAuth();

  const navItems: NavItem[] = [
    { id: "home", label: "Home", href: "/home", icon: <OverviewIcon /> },
    { id: "documents", label: "Documents", href: "/documents", icon: <DocumentIcon /> },
    { id: "portfolio", label: "Portfolio", href: "/portfolio", icon: <PortfolioIcon /> },
    { id: "online", label: "Online", href: "/online", icon: <OnlineIcon /> },
    { id: "information", label: "Information", href: "/information", icon: <InfoIcon /> },
    { id: "feedback", label: "Feedback", href: "/feedback", icon: <FeedbackIcon /> },
  ];

  const sectionContent = {
    home: <HomeSection />,
    documents: <DocumentsSection />,
    portfolio: <OnlinePage compact />,
    online: <CuratorOnlineOperationsSection />,
    information: <InformationSection />,
    feedback: <FeedbackSection />,
  } satisfies Record<WorkspaceSection, JSX.Element>;

  const sectionMeta = SECTION_META[section];

  return (
    <main className="workspace-shell">
      <div className="workspace-shell__layout">
        <aside className="workspace-shell__sidebar">
          <div className="workspace-shell__brand-block">
            <p className="workspace-shell__brand-eyebrow">Internal academy</p>
            <strong className="workspace-shell__brand-title">Instructor Workspace</strong>
          </div>

          <div className="workspace-shell__profile-card">
            <div className="workspace-shell__profile-avatar">
              <span>{(profile?.firstName?.[0] ?? profile?.email?.[0] ?? "C").toUpperCase()}</span>
            </div>
            <div className="workspace-shell__profile-copy">
              <p>{profile?.fullName ?? "Instructor"}</p>
              <span>{profile?.email ?? ""}</span>
            </div>
          </div>

          <nav className="workspace-shell__nav" aria-label="Instructor workspace navigation">
            {navItems.map((item) => (
              <NavLink
                key={item.id}
                to={item.href}
                className={({ isActive }) =>
                  `workspace-shell__nav-link ${isActive ? "workspace-shell__nav-link--active" : ""}`
                }
              >
                <span className="workspace-shell__nav-icon">{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            ))}
            <button type="button" className="workspace-shell__logout" onClick={logout}>
              Sign out
            </button>
          </nav>
        </aside>

        <section className="workspace-shell__content">
          <header className="workspace-shell__hero">
            <div className="workspace-shell__hero-copy">
              <h1>{sectionMeta.title}</h1>
              <p>{sectionMeta.subtitle}</p>
            </div>
            <div className="workspace-shell__hero-meta">
              <span>English only</span>
              <span>{profile?.isSuperuser ? "Superuser" : "Instructor access"}</span>
            </div>
          </header>

          <section className="workspace-shell__panel">{sectionContent[section]}</section>
        </section>
      </div>
    </main>
  );
};
