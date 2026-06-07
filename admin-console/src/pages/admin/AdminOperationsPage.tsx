import { Link } from "react-router-dom";
import { useMemo } from "react";

import { useGetOnlineCohortsQuery, useGetOnlineCoursesQuery } from "@/bll/online/online.service";
import {
  useGetTrainingAdminAiAnalyticsQuery,
  useGetTrainingAdminAiOverviewQuery,
  useGetTrainingAdminOverviewQuery,
} from "@/bll/training/training.service";
import shared from "./AdminPagesShared.module.css";
import { courseDisplayTitle, formatDateTime, formatPercent, formatRelativeHealth, sumValues } from "./adminPageUtils";

const AdminOperationsPage = () => {
  const { data: courseListData, isLoading: isCoursesLoading, isError: isCoursesError } = useGetOnlineCoursesQuery();
  const { data: cohortListData, isLoading: isCohortsLoading, isError: isCohortsError } = useGetOnlineCohortsQuery();
  const { data: governanceOverview } = useGetTrainingAdminOverviewQuery();
  const { data: aiOverview } = useGetTrainingAdminAiOverviewQuery();
  const { data: aiAnalytics } = useGetTrainingAdminAiAnalyticsQuery();

  const courses = useMemo(() => courseListData?.results ?? [], [courseListData]);
  const cohorts = useMemo(() => cohortListData?.results ?? [], [cohortListData]);

  const averageAttendance = useMemo(() => {
    if (courses.length === 0) return null;
    return sumValues(courses.map((course) => course.attendancePercent)) / courses.length;
  }, [courses]);
  const atRiskCourses = useMemo(
    () => [...courses].filter((course) => course.attendancePercent < 60).sort((left, right) => left.attendancePercent - right.attendancePercent),
    [courses],
  );
  const upcomingCohorts = useMemo(
    () =>
      [...cohorts]
        .filter((cohort) => Boolean(cohort.nearestSessionAt))
        .sort((left, right) => {
          const leftValue = left.nearestSessionAt ? new Date(left.nearestSessionAt).getTime() : Number.MAX_SAFE_INTEGER;
          const rightValue = right.nearestSessionAt ? new Date(right.nearestSessionAt).getTime() : Number.MAX_SAFE_INTEGER;
          return leftValue - rightValue;
        })
        .slice(0, 6),
    [cohorts],
  );
  const draftCourses = useMemo(() => courses.filter((course) => !course.isPublished).length, [courses]);
  const liveSessions = useMemo(
    () => sumValues(courses.map((course) => course.sessionsSummary.live)),
    [courses],
  );
  const canceledSessions = useMemo(
    () => sumValues(courses.map((course) => course.sessionsSummary.canceled)),
    [courses],
  );

  return (
    <div className={shared.page}>
      <section className={shared.hero}>
        <div className={shared.heroCopy}>
          <span className={shared.eyebrow}>Operational watch</span>
          <h1>Delivery, runtime, and exception monitoring</h1>
          <p>
            Operations aggregates the signals that usually cause production friction first: low-attendance courses,
            sync failures, stale knowledge indexes, draft content, and unresolved AI support backlog.
          </p>
        </div>
        <div className={shared.heroMeta}>
          <span>{formatPercent(averageAttendance)} attendance</span>
          <span>{liveSessions} live sessions</span>
          <span>{aiOverview?.unresolvedQueueCount ?? 0} unresolved AI items</span>
          <span>{aiAnalytics?.directusSyncFailedWindow ?? 0} sync failures</span>
        </div>
      </section>

      {isCoursesError || isCohortsError ? (
        <p className={shared.errorText}>Failed to load one or more operational data streams.</p>
      ) : null}

      <section className={shared.kpiGrid}>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>At-risk courses</span>
          <strong className={shared.kpiValue}>{atRiskCourses.length}</strong>
          <span className={shared.kpiMeta}>Courses below 60% attendance should be reviewed immediately.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Draft catalog</span>
          <strong className={shared.kpiValue}>{draftCourses}</strong>
          <span className={shared.kpiMeta}>Unpublished courses waiting for governance or content sign-off.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Runtime exceptions</span>
          <strong className={shared.kpiValue}>{aiAnalytics?.aiResponseFailuresWindow ?? "-"}</strong>
          <span className={shared.kpiMeta}>AI-response failures within the current monitoring window.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Canceled sessions</span>
          <strong className={shared.kpiValue}>{canceledSessions}</strong>
          <span className={shared.kpiMeta}>Canceled online sessions across all courses in the current snapshot.</span>
        </article>
      </section>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Delivery watchlist</h2>
              <p>These courses are most likely to need admin intervention first.</p>
            </div>
            <Link to="/courses" className={shared.linkPill}>
              Open courses
            </Link>
          </header>

          {isCoursesLoading ? <p className={shared.emptyText}>Loading delivery watchlist...</p> : null}
          <div className={shared.list}>
            {atRiskCourses.length === 0 && !isCoursesLoading ? (
              <p className={shared.emptyText}>No at-risk courses detected in the current snapshot.</p>
            ) : null}
            {atRiskCourses.slice(0, 5).map((course) => (
              <article key={course.id} className={shared.listItem}>
                <strong>{courseDisplayTitle(course)}</strong>
                <span>
                  {formatPercent(course.attendancePercent)} attendance · {course.studentsCount} students ·{" "}
                  {course.teachers.length > 0 ? course.teachers.join(", ") : "Teacher not assigned"}
                </span>
                <span>
                  Next session {formatDateTime(course.nearestSessionAt)} · Health {formatRelativeHealth(course.attendancePercent)}
                </span>
              </article>
            ))}
          </div>
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Knowledge runtime signals</h2>
              <p>Cross-system signals from AI, Directus, and the knowledge index.</p>
            </div>
            <Link to="/knowledge" className={shared.linkPill}>
              Open knowledge
            </Link>
          </header>
          <div className={shared.tableWrap}>
            <table className={shared.table}>
              <thead>
                <tr>
                  <th>Signal</th>
                  <th>Value</th>
                  <th>Interpretation</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>AI runtime mode</td>
                  <td>{aiAnalytics?.providerMode?.toUpperCase() ?? "-"}</td>
                  <td>Confirms whether the academy is using demo or external provider mode.</td>
                </tr>
                <tr>
                  <td>Directus sync failures</td>
                  <td>{aiAnalytics?.directusSyncFailedWindow ?? 0}</td>
                  <td>Any non-zero value should trigger a content-sync review.</td>
                </tr>
                <tr>
                  <td>Stale or unindexed content</td>
                  <td>
                    {aiAnalytics?.staleIndexedContentCount ?? 0} / {aiAnalytics?.unindexedPublishedItems ?? 0}
                  </td>
                  <td>Published content should be indexed before it becomes learner-facing.</td>
                </tr>
                <tr>
                  <td>Courses without owner</td>
                  <td>{governanceOverview?.coursesWithoutOwner ?? 0}</td>
                  <td>Ownership gaps weaken SLA for unresolved AI escalations.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Upcoming checkpoints</h2>
              <p>Nearest cohort sessions that deserve operational visibility.</p>
            </div>
          </header>
          {isCohortsLoading ? <p className={shared.emptyText}>Loading cohort checkpoints...</p> : null}
          <div className={shared.list}>
            {upcomingCohorts.length === 0 && !isCohortsLoading ? (
              <p className={shared.emptyText}>No upcoming cohort checkpoints found.</p>
            ) : null}
            {upcomingCohorts.map((cohort) => (
              <article key={cohort.id} className={shared.listItem}>
                <strong>
                  {cohort.groupCode} · {cohort.groupName}
                </strong>
                <span>
                  {cohort.courseTitleDe} · {cohort.teacherName} · {formatPercent(cohort.attendancePercent)} attendance
                </span>
                <span>Nearest session {formatDateTime(cohort.nearestSessionAt)}</span>
              </article>
            ))}
          </div>
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Next recommended moves</h2>
              <p>Use the operations view as triage, then jump directly into the working surface you need.</p>
            </div>
          </header>
          <div className={shared.linkGrid}>
            <Link to="/governance" className={shared.quickLink}>
              <strong>Resolve ownership and access gaps</strong>
              <span>Open Governance to fix owners, grants, and metadata before the next release cycle.</span>
            </Link>
            <Link to="/knowledge" className={shared.quickLink}>
              <strong>Review AI escalations</strong>
              <span>Open Knowledge & AI to route unresolved learner questions to the correct owner.</span>
            </Link>
            <Link to="/reports" className={shared.quickLink}>
              <strong>Audit exceptions and failures</strong>
              <span>Open Reports & Logs to inspect sync incidents, denied access, and grader failures.</span>
            </Link>
            <Link to="/courses" className={shared.quickLink}>
              <strong>Inspect course delivery</strong>
              <span>Open Courses to change session status, inspect students, and review cohort attendance.</span>
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
};

export default AdminOperationsPage;
