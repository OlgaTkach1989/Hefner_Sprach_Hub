import { useMemo } from "react";
import { Link } from "react-router-dom";

import { useGetOnlineAdminEnterpriseSummaryQuery } from "@/bll/online/online.service";
import {
  useGetTrainingAdminAuditEventsQuery,
  useGetTrainingAdminContentSyncEventsQuery,
  useGetTrainingAdminGraderJobsQuery,
  useGetTrainingAdminReportsOverviewQuery,
} from "@/bll/training/training.service";
import shared from "./AdminPagesShared.module.css";
import styles from "./AdminReportsPage.module.css";
import { courseDisplayTitle, formatDateTime } from "./adminPageUtils";
import { useAdminCourseScope } from "./useAdminCourseScope";

const AdminReportsPage = () => {
  const {
    courses,
    isCoursesLoading,
    isCoursesError,
    selectedCourse,
    selectedCourseId,
    setSelectedCourseId,
  } = useAdminCourseScope();

  const overviewArgs = selectedCourseId ? { courseId: selectedCourseId } : undefined;
  const { data: enterpriseSummary, isLoading: isEnterpriseLoading, isError: isEnterpriseError } =
    useGetOnlineAdminEnterpriseSummaryQuery(overviewArgs);
  const { data: reportsOverview, isLoading: isOverviewLoading, isError: isOverviewError } =
    useGetTrainingAdminReportsOverviewQuery(overviewArgs);
  const { data: failedAuditData, isLoading: isFailedAuditLoading, isError: isFailedAuditError } =
    useGetTrainingAdminAuditEventsQuery(
      selectedCourseId ? { courseId: selectedCourseId, outcome: "failed", limit: 8 } : { outcome: "failed", limit: 8 }
    );
  const { data: deniedAuditData, isLoading: isDeniedAuditLoading, isError: isDeniedAuditError } =
    useGetTrainingAdminAuditEventsQuery(
      selectedCourseId ? { courseId: selectedCourseId, outcome: "denied", limit: 8 } : { outcome: "denied", limit: 8 }
    );
  const { data: failedSyncData, isLoading: isSyncLoading, isError: isSyncError } =
    useGetTrainingAdminContentSyncEventsQuery(
      selectedCourseId ? { courseId: selectedCourseId, status: "failed", limit: 8 } : { status: "failed", limit: 8 }
    );
  const { data: failedGraderData, isLoading: isGraderLoading, isError: isGraderError } =
    useGetTrainingAdminGraderJobsQuery(
      selectedCourseId ? { courseId: selectedCourseId, status: "failed", limit: 8 } : { status: "failed", limit: 8 }
    );

  const failedAudits = useMemo(() => failedAuditData?.results ?? [], [failedAuditData]);
  const deniedAudits = useMemo(() => deniedAuditData?.results ?? [], [deniedAuditData]);
  const failedSyncEvents = useMemo(() => failedSyncData?.results ?? [], [failedSyncData]);
  const failedGraderJobs = useMemo(() => failedGraderData?.results ?? [], [failedGraderData]);

  const hasError =
    isCoursesError || isEnterpriseError || isOverviewError || isFailedAuditError || isDeniedAuditError || isSyncError || isGraderError;
  const courseQuery = selectedCourseId ? `?courseId=${selectedCourseId}` : "";

  return (
    <div className={shared.page}>
      <section className={shared.hero}>
        <div className={shared.heroCopy}>
          <span className={shared.eyebrow}>Reports and logs</span>
          <h1>Audit failures, sync exceptions, and grader incidents</h1>
          <p>
            This section gives admins the evidence trail behind delivery problems: denied access, failed content syncs,
            grader runtime issues, and unresolved escalation pressure for the selected course scope.
          </p>
        </div>
        <div className={shared.toolbar}>
          <div className={shared.scopeControls}>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Select course</span>
              <select
                className={shared.select}
                value={selectedCourseId ?? ""}
                onChange={(event) => setSelectedCourseId(Number(event.currentTarget.value))}
                disabled={isCoursesLoading || courses.length === 0}
              >
                {courses.map((course) => (
                  <option key={course.id} value={course.id}>
                    {courseDisplayTitle(course)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className={shared.heroMeta}>
            <span>{selectedCourse ? courseDisplayTitle(selectedCourse, "Course scope unavailable") : "Course scope unavailable"}</span>
            <span>{enterpriseSummary?.learning.readyForAttestation ?? 0} attestation-ready learners</span>
            <span>{enterpriseSummary?.identity.readyProviders ?? 0} ready identity providers</span>
            <span>{reportsOverview?.failedAuditEvents ?? 0} failed audit events</span>
            <span>{reportsOverview?.failedSyncEvents ?? 0} sync failures</span>
            <span>{reportsOverview?.failedGraderJobs ?? 0} grader failures</span>
          </div>
        </div>
      </section>

      {hasError ? <p className={shared.errorText}>Failed to load one or more report streams for this view.</p> : null}

      <section className={shared.kpiGrid}>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Active learners</span>
          <strong className={shared.kpiValue}>
            {isEnterpriseLoading ? "..." : enterpriseSummary?.learning.activeEnrollments ?? 0}
          </strong>
          <span className={shared.kpiMeta}>Learners still moving through the course scope.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Evidence issued</span>
          <strong className={shared.kpiValue}>
            {isEnterpriseLoading ? "..." : enterpriseSummary?.learning.evidenceIssued ?? 0}
          </strong>
          <span className={shared.kpiMeta}>
            {enterpriseSummary?.compliance.evidenceCoveragePercent ?? 0}% evidence coverage across current enrollments.
          </span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Attestation queue</span>
          <strong className={shared.kpiValue}>
            {isEnterpriseLoading ? "..." : enterpriseSummary?.learning.readyForAttestation ?? 0}
          </strong>
          <span className={shared.kpiMeta}>Learners who finished the rule set but still need formal confirmation.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Publish blockers</span>
          <strong className={shared.kpiValue}>
            {isEnterpriseLoading ? "..." : enterpriseSummary?.compliance.publishBlockedCourses ?? 0}
          </strong>
          <span className={shared.kpiMeta}>Courses that still fail required release checks before publish.</span>
        </article>
      </section>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Identity and scoped access</h2>
              <p>SSO readiness, fallback login posture, and scoped accountability coverage for the selected course scope.</p>
            </div>
            <Link to={`/curators${courseQuery}`} className={shared.linkPill}>
              Open users & instructors
            </Link>
          </header>

          <div className={shared.kpiGrid}>
            <article className={shared.kpiCard}>
              <span className={shared.kpiLabel}>Ready identity providers</span>
              <strong className={shared.kpiValue}>{enterpriseSummary?.identity.readyProviders ?? 0}</strong>
              <span className={shared.kpiMeta}>
                {enterpriseSummary?.identity.enabledProviders ?? 0} enabled · {enterpriseSummary?.identity.linkedAccountsTotal ?? 0} linked accounts
              </span>
            </article>
            <article className={shared.kpiCard}>
              <span className={shared.kpiLabel}>Scoped managers</span>
              <strong className={shared.kpiValue}>{enterpriseSummary?.scopedAccess.managerAssignments ?? 0}</strong>
              <span className={shared.kpiMeta}>
                Delivery {enterpriseSummary?.scopedAccess.deliveryManagerAssignments ?? 0} · Compliance {enterpriseSummary?.scopedAccess.complianceManagerAssignments ?? 0}
              </span>
            </article>
            <article className={shared.kpiCard}>
              <span className={shared.kpiLabel}>Primary assignments</span>
              <strong className={shared.kpiValue}>{enterpriseSummary?.scopedAccess.primaryAssignments ?? 0}</strong>
              <span className={shared.kpiMeta}>Named primary contacts for scoped delivery and governance ownership.</span>
            </article>
          </div>

          <div className={shared.list}>
            {(enterpriseSummary?.identity.providers ?? []).map((provider) => (
              <article key={provider.id} className={shared.listItem}>
                <strong>{provider.displayName}</strong>
                <span>
                  {provider.providerLabel} · {provider.isEnabled ? "Enabled" : "Disabled"} ·{" "}
                  {provider.isReady ? "Ready" : provider.verificationLabel}
                </span>
                <span>
                  {provider.discoveryUrl || provider.authorizationUrl || provider.issuer || "No discovery endpoint configured."}
                </span>
              </article>
            ))}
            {enterpriseSummary && enterpriseSummary.identity.providers.length === 0 ? (
              <p className={shared.emptyText}>No identity providers are configured yet.</p>
            ) : null}
          </div>
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Manager and compliance queue</h2>
              <p>Focus learners and delivery issues that still need action instead of only raw failure streams.</p>
            </div>
          </header>
          <div className={shared.tableWrap}>
            <table className={shared.table}>
              <thead>
                <tr>
                  <th>Learner</th>
                  <th>Course</th>
                  <th>Progress</th>
                  <th>Attendance</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {enterpriseSummary?.atRiskLearners.length === 0 && !isEnterpriseLoading ? (
                  <tr>
                    <td colSpan={5}>
                      <p className={shared.emptyText}>No manager attention items for the selected scope.</p>
                    </td>
                  </tr>
                ) : null}
                {(enterpriseSummary?.atRiskLearners ?? []).map((item) => (
                  <tr key={item.enrollmentId}>
                    <td>
                      <div className={shared.tableCellStack}>
                        <strong>{item.fullName}</strong>
                        <span>{item.email}</span>
                      </div>
                    </td>
                    <td>
                      <div className={shared.tableCellStack}>
                        <strong>{item.courseTitle}</strong>
                        <span>{item.cohortLabel}</span>
                      </div>
                    </td>
                    <td>{item.progressPercent}%</td>
                    <td>{item.attendancePercent}%</td>
                    <td>{item.riskReasons.join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className={shared.kpiGrid}>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Failed audit events</span>
          <strong className={shared.kpiValue}>
            {isOverviewLoading ? "..." : reportsOverview?.failedAuditEvents ?? 0}
          </strong>
          <span className={shared.kpiMeta}>Failed requests, invalid transitions, and runtime issues captured by the API.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Denied access events</span>
          <strong className={shared.kpiValue}>
            {isOverviewLoading ? "..." : reportsOverview?.deniedAuditEvents ?? 0}
          </strong>
          <span className={shared.kpiMeta}>Signals that users or services tried to access content outside their policy.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Content sync failures</span>
          <strong className={shared.kpiValue}>
            {isOverviewLoading ? "..." : reportsOverview?.failedSyncEvents ?? 0}
          </strong>
          <span className={shared.kpiMeta}>Directus and content-index failures that block fresh learning material.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Failed grader jobs</span>
          <strong className={shared.kpiValue}>
            {isOverviewLoading ? "..." : reportsOverview?.failedGraderJobs ?? 0}
          </strong>
          <span className={shared.kpiMeta}>Practice grading runs that need manual retry or feedback review.</span>
        </article>
      </section>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Audit exception feed</h2>
              <p>Failed and denied API actions are separated so admins can distinguish product errors from policy blocks.</p>
            </div>
            <Link to={`/governance${courseQuery}`} className={shared.linkPill}>
              Open governance
            </Link>
          </header>

          <div className={styles.auditColumns}>
            <div className={styles.auditColumn}>
              <div className={styles.auditColumnHeader}>
                <strong>Failed actions</strong>
                <span className={shared.warnPill}>{reportsOverview?.failedAuditEvents ?? 0}</span>
              </div>
              {isFailedAuditLoading ? <p className={shared.emptyText}>Loading failed audit events...</p> : null}
              <div className={shared.list}>
                {failedAudits.length === 0 && !isFailedAuditLoading ? (
                  <p className={shared.emptyText}>No failed audit events for the current course scope.</p>
                ) : null}
                {failedAudits.map((event) => (
                  <article key={event.eventId} className={shared.listItem}>
                    <strong>{event.event_type}</strong>
                    <span>
                      {event.actorEmail || "Unknown actor"} · {event.contentSlug || event.request_path || "No path"}
                    </span>
                    <span>{formatDateTime(event.createdAt)}</span>
                  </article>
                ))}
              </div>
            </div>

            <div className={styles.auditColumn}>
              <div className={styles.auditColumnHeader}>
                <strong>Denied access</strong>
                <span className={shared.neutralPill}>{reportsOverview?.deniedAuditEvents ?? 0}</span>
              </div>
              {isDeniedAuditLoading ? <p className={shared.emptyText}>Loading denied audit events...</p> : null}
              <div className={shared.list}>
                {deniedAudits.length === 0 && !isDeniedAuditLoading ? (
                  <p className={shared.emptyText}>No denied access events for the current course scope.</p>
                ) : null}
                {deniedAudits.map((event) => (
                  <article key={event.eventId} className={shared.listItem}>
                    <strong>{event.event_type}</strong>
                    <span>
                      {event.actorEmail || "Unknown actor"} · {event.contentSlug || event.request_path || "No path"}
                    </span>
                    <span>{formatDateTime(event.createdAt)}</span>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Content sync failures</h2>
              <p>Directus integration failures should be resolved before the academy exposes stale content to learners.</p>
            </div>
            <Link to={`/knowledge${courseQuery}`} className={shared.linkPill}>
              Open knowledge
            </Link>
          </header>
          {isSyncLoading ? <p className={shared.emptyText}>Loading sync failure feed...</p> : null}
          <div className={shared.tableWrap}>
            <table className={shared.table}>
              <thead>
                <tr>
                  <th>Content</th>
                  <th>Source</th>
                  <th>Failure detail</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {failedSyncEvents.length === 0 && !isSyncLoading ? (
                  <tr>
                    <td colSpan={4}>
                      <p className={shared.emptyText}>No sync failures recorded for the selected course scope.</p>
                    </td>
                  </tr>
                ) : null}
                {failedSyncEvents.map((event) => (
                  <tr key={event.id}>
                    <td>
                      <div className={shared.tableCellStack}>
                        <strong>{event.contentSlug || "Unnamed item"}</strong>
                        <span>{event.course?.title_de ?? "Course not resolved"}</span>
                      </div>
                    </td>
                    <td>{event.source}</td>
                    <td>
                      <div className={shared.tableCellStack}>
                        <strong>{event.eventType}</strong>
                        <span>{event.detail || "No detail provided by the sync service."}</span>
                      </div>
                    </td>
                    <td>{formatDateTime(event.createdAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Grader incident queue</h2>
              <p>Failed grading jobs are the fastest way to identify broken practice templates or runtime regressions.</p>
            </div>
            <Link to={`/operations${courseQuery}`} className={shared.linkPill}>
              Open operations
            </Link>
          </header>
          {isGraderLoading ? <p className={shared.emptyText}>Loading grader incidents...</p> : null}
          <div className={shared.list}>
            {failedGraderJobs.length === 0 && !isGraderLoading ? (
              <p className={shared.emptyText}>No failed grader jobs for the selected course scope.</p>
            ) : null}
            {failedGraderJobs.map((job) => (
              <article key={job.id} className={shared.listItem}>
                <strong>{job.contentName}</strong>
                <span>
                  {job.studentEmail} · {job.backend} · worker {job.workerName || "unknown"}
                </span>
                <span>{job.errorMessage || "The grader did not return an explicit failure message."}</span>
                <span>{formatDateTime(job.finishedAt || job.lockedAt || job.availableAt)}</span>
              </article>
            ))}
          </div>
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Recommended next moves</h2>
              <p>Use the same course scope to jump from evidence into the appropriate remediation surface.</p>
            </div>
          </header>
          <div className={shared.linkGrid}>
            <Link to={`/curators${courseQuery}`} className={shared.quickLink}>
              <strong>Adjust ownership and reviewers</strong>
              <span>Move to Users & Instructors when the incident points to missing accountability or unresolved SLA gaps.</span>
            </Link>
            <Link to={`/governance${courseQuery}`} className={shared.quickLink}>
              <strong>Repair metadata and policy gaps</strong>
              <span>Use Governance when content lacks owners, audiences, or practice readiness controls.</span>
            </Link>
            <Link to={`/knowledge${courseQuery}`} className={shared.quickLink}>
              <strong>Rebuild the knowledge surface</strong>
              <span>Use Knowledge & AI when Directus sync or stale index problems block AI-assisted learning.</span>
            </Link>
          </div>

          <div className={styles.timelineCard}>
            <span className={shared.fieldLabel}>Latest failure markers</span>
            <div className={styles.timelineList}>
              <div>
                <strong>Audit</strong>
                <span>{formatDateTime(reportsOverview?.latestAuditFailureAt)}</span>
              </div>
              <div>
                <strong>Sync</strong>
                <span>{formatDateTime(reportsOverview?.latestSyncFailureAt)}</span>
              </div>
              <div>
                <strong>Grader</strong>
                <span>{formatDateTime(reportsOverview?.latestGraderFailureAt)}</span>
              </div>
              <div>
                <strong>AI backlog</strong>
                <span>{reportsOverview?.unresolvedAiConversations ?? 0} open conversations</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default AdminReportsPage;
