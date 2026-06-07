import { useMemo, useState } from "react";

import { useGetTeacherWorkspaceQuery } from "@/bll/workspace/workspace.service";
import { formatDateTime } from "./workspaceShared";

type InformationTab = "rules" | "safety" | "news" | "about";

type InformationTabDefinition = {
  id: InformationTab;
  label: string;
};

const TABS: InformationTabDefinition[] = [
  { id: "rules", label: "Rules" },
  { id: "safety", label: "Safety" },
  { id: "news", label: "News" },
  { id: "about", label: "About" },
];

export const CuratorInformationSection = () => {
  const [activeTab, setActiveTab] = useState<InformationTab>("rules");
  const { data } = useGetTeacherWorkspaceQuery();

  const newsItems = useMemo(
    () => [
      `${data?.summary.courses ?? 0} courses are currently assigned to your instructor account.`,
      `${data?.summary.cohorts ?? 0} cohorts are linked to your current teaching scope.`,
      `${data?.materials.length ?? 0} active documents are available in your course delivery stack.`,
      data?.summary.nextSessionAt
        ? `Next scheduled live session: ${formatDateTime(data.summary.nextSessionAt)}.`
        : "No live session is currently scheduled in the upcoming queue.",
    ],
    [data],
  );

  return (
    <div className="curator-workspace__section-stack">
      <section className="curator-workspace__card">
        <div className="curator-workspace__panel-heading">
          <div>
            <span className="curator-workspace__eyebrow">Information centre</span>
            <h3>Operational guidance</h3>
          </div>
          <p>Reference policies, delivery rules, and current academy updates without leaving the instructor workspace.</p>
        </div>

        <div className="curator-workspace__tabs" role="tablist" aria-label="Information centre tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              className={`curator-workspace__tab ${activeTab === tab.id ? "curator-workspace__tab--active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "rules" ? (
          <div className="curator-workspace__info-grid">
            <article className="curator-workspace__info-card">
              <h4>Delivery standards</h4>
              <p>Start sessions on time, confirm the join link before the cohort enters, and keep the lesson agenda aligned with the published module plan.</p>
              <ul className="curator-workspace__bullet-list">
                <li>Open the live session from the Online tab rather than from external bookmarks.</li>
                <li>Use the assigned cohort only; do not mix students from different groups inside one live classroom.</li>
                <li>Close the session only after attendance sync or after confirming the manual follow-up plan.</li>
              </ul>
            </article>

            <article className="curator-workspace__info-card">
              <h4>Content handling</h4>
              <p>Documents, recordings, and notebook tasks must stay aligned with the assigned course scope and audience entitlements.</p>
              <ul className="curator-workspace__bullet-list">
                <li>Review materials before each cohort run and flag missing files through Feedback.</li>
                <li>Do not share internal-only material with external audiences or cohorts outside their entitlement group.</li>
                <li>Escalate outdated links, broken recordings, or incomplete notebooks on the same working day.</li>
              </ul>
            </article>
          </div>
        ) : null}

        {activeTab === "safety" ? (
          <div className="curator-workspace__info-grid">
            <article className="curator-workspace__info-card">
              <h4>Operational safety</h4>
              <p>Instructors are responsible for preserving confidentiality, access discipline, and classroom stability during live delivery.</p>
              <ul className="curator-workspace__bullet-list">
                <li>Use academy-managed accounts for all live delivery actions and course communication.</li>
                <li>Do not export student lists, attendance data, or course materials to unmanaged personal tools.</li>
                <li>Report suspicious access, missing join links, or unexpected attendees immediately.</li>
              </ul>
            </article>

            <article className="curator-workspace__info-card">
              <h4>Escalation path</h4>
              <p>If a delivery risk affects timing, confidentiality, or access, create a feedback ticket from this workspace and notify the academy operations owner.</p>
              <ul className="curator-workspace__bullet-list">
                <li>Critical live-session incident: escalate immediately.</li>
                <li>Content issue or broken material: escalate before the next learner-facing touchpoint.</li>
                <li>Profile data mismatch: update Home first, then confirm operational routing.</li>
              </ul>
            </article>
          </div>
        ) : null}

        {activeTab === "news" ? (
          <div className="curator-workspace__info-grid">
            <article className="curator-workspace__info-card">
              <h4>Current workspace snapshot</h4>
              <ul className="curator-workspace__bullet-list">
                {newsItems.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>

            <article className="curator-workspace__info-card">
              <h4>Recommended next checks</h4>
              <ul className="curator-workspace__bullet-list">
                <li>Review the next cohort in the Online tab and verify the session join link before delivery day.</li>
                <li>Open Courses to confirm that all learner-facing files are still present and current.</li>
                <li>Use Feedback for blockers that require academy operations or content-team action.</li>
              </ul>
            </article>
          </div>
        ) : null}

        {activeTab === "about" ? (
          <div className="curator-workspace__info-grid">
            <article className="curator-workspace__info-card">
              <h4>About the instructor workspace</h4>
              <p>This workspace is the dedicated operating surface for instructors who run assigned online cohorts, manage live-session readiness, and maintain teaching contact data.</p>
              <p>The focus is deliberate: course delivery, operational visibility, and controlled escalation are grouped in one English-only environment.</p>
            </article>

            <article className="curator-workspace__info-card">
              <h4>What belongs here</h4>
              <ul className="curator-workspace__bullet-list">
                <li>Personal instructor profile and delivery contact details.</li>
                <li>Assigned course and cohort view, with live operations under Online.</li>
                <li>Supporting courses, recordings, academy guidance, and feedback routing.</li>
              </ul>
            </article>
          </div>
        ) : null}
      </section>
    </div>
  );
};
