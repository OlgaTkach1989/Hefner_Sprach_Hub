import { useMemo, useState } from "react";

import "./InformationTab.css";

type InformationSectionKey = "standards" | "security" | "academy" | "guide";

type GuideCard = {
  title: string;
  subtitle: string;
  points: string[];
};

const GUIDE_CARDS: GuideCard[] = [
  {
    title: "Home and profile",
    subtitle: "Keep your identity and contact data current.",
    points: [
      "Review your personal details regularly and keep your contact information accurate.",
      "Use your academy-managed identity across all connected tools and learning spaces.",
      "If profile information looks incorrect, raise it through Support rather than creating duplicates."
    ]
  },
  {
    title: "My Courses",
    subtitle: "Follow the module, lesson, and content-item structure.",
    points: [
      "Open modules and lessons to review the exact order of videos, readings, quizzes, PDFs, and notebook assignments.",
      "Use Generate lesson when you need a full lesson package in one scrollable presentation view.",
      "Use Download lesson when you need an offline lesson handout or a shareable review package."
    ]
  },
  {
    title: "Calendar and live delivery",
    subtitle: "Track scheduled sessions and repeatable learning touchpoints.",
    points: [
      "Use the calendar to confirm session timing, join links, and upcoming learning events.",
      "Open recordings only from trusted links inside the academy environment.",
      "Treat live sessions, recordings, and notebook assignments as one connected learning flow."
    ]
  },
  {
    title: "Connected apps and support",
    subtitle: "Use communication and planning tools in a controlled way.",
    points: [
      "Use Teams for meetings and cohort communication, Outlook Calendar for scheduled sessions, and Jupyter Notebook for practical work.",
      "Open external tools with the same corporate identity used for the academy workspace.",
      "Use Support when you hit an access issue, missing content item, or delivery blocker."
    ]
  }
];

export const InformationTab = () => {
  const [activeSection, setActiveSection] = useState<InformationSectionKey>("standards");

  const sectionButtons: Array<{ key: InformationSectionKey; label: string }> = useMemo(
    () => [
      { key: "standards", label: "Standards" },
      { key: "security", label: "Security" },
      { key: "academy", label: "Academy" },
      { key: "guide", label: "Platform Guide" }
    ],
    []
  );

  return (
    <section className="information-tab">
      <div className="information-tab__buttons" role="tablist" aria-label="Information sections">
        {sectionButtons.map((button) => (
          <button
            key={button.key}
            type="button"
            role="tab"
            aria-selected={activeSection === button.key}
            className={activeSection === button.key ? "active" : ""}
            onClick={() => setActiveSection(button.key)}
          >
            {button.label}
          </button>
        ))}
      </div>

      {activeSection === "standards" ? (
        <div className="information-tab__content">
          <h2>Learning and delivery standards</h2>
          <p>
            This academy workspace is built for structured internal learning. Every course should follow a clear path:
            modules, lessons, and content items that can be repeated on demand and tracked over time.
          </p>

          <h3>What is expected from learners</h3>
          <ul>
            <li>Follow the published module order instead of skipping directly to advanced content.</li>
            <li>Complete required readings, quizzes, notebook tasks, and lesson conclusions before moving on.</li>
            <li>Use the same account identity across courses, live sessions, and connected workplace apps.</li>
          </ul>

          <h3>Content discipline</h3>
          <ul>
            <li>Use only the materials surfaced inside the academy platform or approved linked tools.</li>
            <li>Do not redistribute internal documents, recordings, notebook tasks, or solution files outside the permitted audience.</li>
            <li>Report broken files, missing lesson items, or outdated content through Support.</li>
          </ul>

          <h3>Operational rhythm</h3>
          <ul>
            <li>Use My Courses to understand the lesson path before joining a live or recorded session.</li>
            <li>Use Calendar and App tools to stay aligned with invitations, deadlines, and cohort communication.</li>
            <li>Return to generated lesson documents when you need a compact review flow for one lesson.</li>
          </ul>
        </div>
      ) : null}

      {activeSection === "security" ? (
        <div className="information-tab__content">
          <h2>Security and access discipline</h2>
          <p>
            The platform may contain internal learning assets, recordings, model notes, and notebook assignments. Access
            must remain aligned with your role and current learning scope.
          </p>

          <h3>Account protection</h3>
          <ul>
            <li>Use academy-managed credentials only and avoid sharing session links, passwords, or downloaded files.</li>
            <li>Always sign in with the same corporate identity across the academy, Teams, Outlook Calendar, and Jupyter Notebook.</li>
            <li>Sign out from shared devices and avoid storing sensitive documents in unmanaged personal tools.</li>
          </ul>

          <h3>Data handling</h3>
          <ul>
            <li>Do not move internal documents, notebooks, or learner records into public cloud storage or personal mailboxes.</li>
            <li>Export lesson documents only when needed for approved working purposes.</li>
            <li>Escalate suspicious access, missing permissions, or unexpected content visibility immediately.</li>
          </ul>

          <h3>Safe platform usage</h3>
          <ul>
            <li>Open notebook assignments only from trusted lesson items inside the academy.</li>
            <li>Use the Support area when a tool opens the wrong account, a link is broken, or content appears out of scope.</li>
            <li>Treat recordings, PDFs, and generated lesson packages as controlled academy resources.</li>
          </ul>
        </div>
      ) : null}

      {activeSection === "academy" ? (
        <div className="information-tab__content">
          <h2>Internal academy overview</h2>
          <p>
            The internal academy combines repeatable materials, live delivery, notebook-based practice, and cross-team
            knowledge sharing in one system. It is designed for operational training, onboarding, and specialist upskilling.
          </p>

          <h3>How the academy is structured</h3>
          <ul>
            <li>Public entry spaces guide learners into course groups, shared learning formats, and role-appropriate content.</li>
            <li>Student Workspace focuses on personal progress, structured course navigation, recordings, apps, and support.</li>
            <li>Instructor Workspace focuses on assigned courses, lesson visibility, live-session operations, and delivery oversight.</li>
            <li>Admin Workspace manages course structure, cohorts, governance, entitlements, knowledge assets, and operations.</li>
          </ul>

          <h3>Core learning model</h3>
          <ul>
            <li>Courses are broken into modules, lessons, and typed content items such as video, text, PDF, quiz, and notebook assignment.</li>
            <li>Notebook tasks connect to the lab runtime and grading workflow for practical work.</li>
            <li>Lesson packages can be generated as a compact review document for revision, delivery, or handover.</li>
          </ul>

          <h3>Support model</h3>
          <ul>
            <li>Course owners and instructors maintain delivery quality and learning readiness.</li>
            <li>Support channels are used for access issues, missing materials, broken links, and content escalation.</li>
            <li>Connected workplace apps extend communication and planning without replacing the academy record of truth.</li>
          </ul>
        </div>
      ) : null}

      {activeSection === "guide" ? (
        <div className="information-tab__content">
          <h2>Platform guide</h2>
          <p>
            Use this workspace as the main operating surface for your learning path. The sections below summarize the
            expected workflow inside the internal academy.
          </p>

          {GUIDE_CARDS.map((card) => (
            <article className="information-tab__tutorial-card" key={card.title}>
              <h3>{card.title}</h3>
              <p className="information-tab__tutorial-subtitle">{card.subtitle}</p>
              <ul>
                {card.points.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
};
