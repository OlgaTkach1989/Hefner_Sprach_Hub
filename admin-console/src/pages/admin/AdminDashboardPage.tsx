import { Link } from "react-router-dom";
import { useMemo } from "react";

import {
  useGetOnlineCohortsQuery,
  useGetOnlineCourseDetailQuery,
} from "@/bll/online/online.service";
import {
  useGetTrainingAdminAiOverviewQuery,
  useGetTrainingAdminOverviewQuery,
} from "@/bll/training/training.service";
import {
  pocCertificateRule,
  pocProgramCourses,
  pocRuntimePreset,
} from "../../data/pocProgram";
import shared from "./AdminPagesShared.module.css";
import { useAdminCourseScope } from "./useAdminCourseScope";
import { courseDisplayTitle, formatDateTime, formatPercent, formatRelativeHealth, sumValues } from "./adminPageUtils";

const AdminDashboardPage = () => {
  const {
    courses,
    isCoursesLoading,
    isCoursesError,
    selectedCourseId,
    selectedCourse,
    setSelectedCourseId,
  } = useAdminCourseScope();

  const { data: focusedCourseDetail } = useGetOnlineCourseDetailQuery(selectedCourseId as number, {
    skip: !selectedCourseId,
  });
  const { data: overview } = useGetTrainingAdminOverviewQuery(
    selectedCourseId ? { courseId: selectedCourseId } : undefined,
  );
  const { data: aiOverview } = useGetTrainingAdminAiOverviewQuery(
    selectedCourseId ? { courseId: selectedCourseId } : undefined,
  );
  const { data: cohortListData } = useGetOnlineCohortsQuery(selectedCourseId ? { courseId: selectedCourseId } : undefined);

  const totalStudents = useMemo(() => sumValues(courses.map((course) => course.studentsCount)), [courses]);
  const totalSessions = useMemo(
    () => sumValues(courses.map((course) => course.sessionsSummary.total)),
    [courses],
  );
  const averageAttendance = useMemo(() => {
    if (courses.length === 0) return null;
    return sumValues(courses.map((course) => course.attendancePercent)) / courses.length;
  }, [courses]);
  const unpublishedCourses = useMemo(() => courses.filter((course) => !course.isPublished).length, [courses]);
  const coursesWithoutTeachers = useMemo(
    () => courses.filter((course) => course.teachers.length === 0).length,
    [courses],
  );
  const attentionCourses = useMemo(
    () =>
      [...courses]
        .sort((left, right) => left.attendancePercent - right.attendancePercent)
        .slice(0, 4),
    [courses],
  );
  const selectedCourseCohorts = useMemo(
    () =>
      [...(focusedCourseDetail?.cohorts ?? [])]
        .sort((left, right) => {
          const leftValue = left.nearestSessionAt ? new Date(left.nearestSessionAt).getTime() : Number.MAX_SAFE_INTEGER;
          const rightValue = right.nearestSessionAt ? new Date(right.nearestSessionAt).getTime() : Number.MAX_SAFE_INTEGER;
          return leftValue - rightValue;
        })
        .slice(0, 4),
    [focusedCourseDetail],
  );
  const focusedCohortCount = cohortListData?.results.length ?? focusedCourseDetail?.cohorts.length ?? 0;
  const pocTotals = useMemo(() => {
    const modules = sumValues(pocProgramCourses.map((course) => course.modules.length));
    const steps = pocProgramCourses.reduce(
      (courseTotal, course) =>
        courseTotal + course.modules.reduce((moduleTotal, module) => moduleTotal + module.steps.length, 0),
      0,
    );
    return {
      courses: pocProgramCourses.length,
      modules,
      steps,
    };
  }, []);

  return (
    <div className={shared.page}>
      <section className={shared.hero}>
        <div className={shared.heroCopy}>
          <span className={shared.eyebrow}>Administrative overview</span>
          <h1>Admin Console</h1>
          <p>
            Track course performance, governance status, access usage, and AI support quality.
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
            <span>{courses.length} courses</span>
            <span>{totalStudents} learners</span>
            <span>{formatPercent(averageAttendance)} attendance</span>
            <span>{aiOverview?.unresolvedQueueCount ?? 0} unresolved AI items</span>
          </div>
        </div>
      </section>

      {isCoursesError ? <p className={shared.errorText}>Failed to load admin dashboard data.</p> : null}

      <section className={shared.panel}>
        <header className={shared.panelHeader}>
          <div>
            <h2>Programming catalog snapshot</h2>
            <p>
              Compact snapshot of the seeded Python catalog used in the platform: active course blueprints,
              shared runtime assumptions, and the completion contract used for delivery.
            </p>
          </div>
          <span className={shared.sectionHint}>Seeded catalog reference</span>
        </header>

        <div className={shared.kpiGrid}>
          <article className={shared.kpiCard}>
            <span className={shared.kpiLabel}>Seeded courses</span>
            <strong className={shared.kpiValue}>{pocTotals.courses}</strong>
            <span className={shared.kpiMeta}>Compact reference blueprints for the current programming catalog.</span>
          </article>
          <article className={shared.kpiCard}>
            <span className={shared.kpiLabel}>Modules</span>
            <strong className={shared.kpiValue}>{pocTotals.modules}</strong>
            <span className={shared.kpiMeta}>Delivery modules plus a final assessment path across the seeded courses.</span>
          </article>
          <article className={shared.kpiCard}>
            <span className={shared.kpiLabel}>Step count</span>
            <strong className={shared.kpiValue}>{pocTotals.steps}</strong>
            <span className={shared.kpiMeta}>Structured lesson flow coverage across theory, video, quiz, and practice.</span>
          </article>
          <article className={shared.kpiCard}>
            <span className={shared.kpiLabel}>Shared runtime rule</span>
            <strong className={shared.kpiValue}>Pinned</strong>
            <span className={shared.kpiMeta}>One runtime contract reused across practice and review.</span>
          </article>
        </div>

        <div className={shared.compactCatalogGrid}>
          {pocProgramCourses.map((blueprint) => (
            <article key={blueprint.slug} className={shared.compactCourseCard}>
              <div className={shared.tableCellStack}>
                <strong>{blueprint.title}</strong>
                <span>{blueprint.summary}</span>
                <span>{blueprint.audience}</span>
              </div>
              <div className={shared.compactTagRow}>
                <span>{blueprint.focus}</span>
                <span>{blueprint.modules.length} modules</span>
                <span>{blueprint.modules.reduce((sum, module) => sum + module.steps.length, 0)} steps</span>
              </div>

              <div className={shared.compactModuleList}>
                {blueprint.modules.map((module) => (
                  <span key={module.title} className={shared.compactModuleTag}>
                    {module.title}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>

        <div className={shared.compactInfoGrid}>
          <article className={shared.card}>
            <strong>{pocRuntimePreset.title}</strong>
            <p className={shared.muted}>{pocRuntimePreset.summary}</p>
            <ul className={shared.compactBulletList}>
              {pocRuntimePreset.bullets.map((bullet) => (
                <li key={bullet}>{bullet}</li>
              ))}
            </ul>
          </article>
          <article className={shared.card}>
            <strong>{pocCertificateRule.title}</strong>
            <p className={shared.muted}>{pocCertificateRule.summary}</p>
            <ul className={shared.compactBulletList}>
              {pocCertificateRule.bullets.map((bullet) => (
                <li key={bullet}>{bullet}</li>
              ))}
            </ul>
          </article>
        </div>
      </section>

      <section className={shared.kpiGrid}>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Published catalog</span>
          <strong className={shared.kpiValue}>{courses.length - unpublishedCourses}</strong>
          <span className={shared.kpiMeta}>{unpublishedCourses} draft or hidden courses still require review.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Delivery load</span>
          <strong className={shared.kpiValue}>{totalSessions}</strong>
          <span className={shared.kpiMeta}>Scheduled, live, ended, and canceled sessions across the academy.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Ownership gaps</span>
          <strong className={shared.kpiValue}>{overview?.coursesWithoutOwner ?? "-"}</strong>
          <span className={shared.kpiMeta}>Courses without a named owner should not reach production.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Teacher staffing</span>
          <strong className={shared.kpiValue}>{coursesWithoutTeachers}</strong>
          <span className={shared.kpiMeta}>Courses with no assigned teaching coverage.</span>
        </article>
      </section>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Selected course snapshot</h2>
              <p>
                {selectedCourse
                  ? `${courseDisplayTitle(selectedCourse)} is currently the active course scope for governance and knowledge review.`
                  : "Select a course to inspect its delivery and governance posture."}
              </p>
            </div>
            {selectedCourse ? <span className={shared.sectionHint}>{selectedCourse.slug}</span> : null}
          </header>

          {selectedCourse ? (
            <div className={shared.kpiGrid}>
              <article className={shared.kpiCard}>
                <span className={shared.kpiLabel}>Course health</span>
                <strong className={shared.kpiValue}>{formatRelativeHealth(selectedCourse.attendancePercent)}</strong>
                <span className={shared.kpiMeta}>
                  {formatPercent(selectedCourse.attendancePercent)} attendance across {selectedCourse.studentsCount} students.
                </span>
              </article>
              <article className={shared.kpiCard}>
                <span className={shared.kpiLabel}>Cohorts</span>
                <strong className={shared.kpiValue}>{focusedCohortCount}</strong>
                <span className={shared.kpiMeta}>
                  {selectedCourse.publicCohortsCount} public cohorts with repeatable-on-demand delivery.
                </span>
              </article>
              <article className={shared.kpiCard}>
                <span className={shared.kpiLabel}>Knowledge queue</span>
                <strong className={shared.kpiValue}>{aiOverview?.unresolvedQueueCount ?? "-"}</strong>
                <span className={shared.kpiMeta}>
                  {aiOverview?.faqCoveragePercent ?? 0}% FAQ coverage for current course content.
                </span>
              </article>
              <article className={shared.kpiCard}>
                <span className={shared.kpiLabel}>Governance flags</span>
                <strong className={shared.kpiValue}>
                  {(overview?.contentWithoutAssetClass ?? 0) +
                    (overview?.contentWithoutTopic ?? 0) +
                    (overview?.contentWithoutOwner ?? 0)}
                </strong>
                <span className={shared.kpiMeta}>Missing metadata and ownership signals for the selected course.</span>
              </article>
            </div>
          ) : (
            <p className={shared.emptyText}>No course scope is available yet.</p>
          )}
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Quick actions</h2>
              <p>Use these entry points to move from overview into the admin task you need next.</p>
            </div>
          </header>
          <div className={shared.linkGrid}>
            <Link to="/courses" className={shared.quickLink}>
              <strong>Courses and cohorts</strong>
              <span>Open the catalog-level operational view for sessions, learners, and delivery status.</span>
            </Link>
            <Link to="/curators" className={shared.quickLink}>
              <strong>Users and instructors</strong>
              <span>Grant instructor access, maintain profiles, and assign cohorts to accountable delivery owners.</span>
            </Link>
            <Link to="/governance" className={shared.quickLink}>
              <strong>Governance</strong>
              <span>Resolve ownership gaps, entitlement audiences, and content coverage issues.</span>
            </Link>
            <Link to="/knowledge" className={shared.quickLink}>
              <strong>Knowledge and AI</strong>
              <span>Inspect AI escalations, FAQ coverage, and knowledge-index freshness.</span>
            </Link>
            <Link to="/reports" className={shared.quickLink}>
              <strong>Reports and logs</strong>
              <span>Review audit failures, sync exceptions, and grader incidents before they impact delivery.</span>
            </Link>
            <Link to="/operations" className={shared.quickLink}>
              <strong>Operations</strong>
              <span>Track runtime pressure, sync signals, and academy-wide operational watchlists.</span>
            </Link>
          </div>
        </section>
      </div>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Courses needing attention</h2>
              <p>Lowest-attendance courses rise to the top so admins can address risk before delivery slips.</p>
            </div>
          </header>
          <div className={shared.list}>
            {attentionCourses.length === 0 ? <p className={shared.emptyText}>No course records available.</p> : null}
            {attentionCourses.map((course) => (
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
              <h2>Upcoming cohort checkpoints</h2>
              <p>Nearest delivery checkpoints for the currently selected course.</p>
            </div>
            {selectedCourse ? <span className={shared.sectionHint}>{courseDisplayTitle(selectedCourse)}</span> : null}
          </header>
          <div className={shared.list}>
            {selectedCourseCohorts.length === 0 ? (
              <p className={shared.emptyText}>No cohorts with upcoming sessions for the selected course.</p>
            ) : null}
            {selectedCourseCohorts.map((cohort) => (
              <article key={cohort.id} className={shared.listItem}>
                <strong>
                  {cohort.groupCode} · {cohort.groupName}
                </strong>
                <span>
                  {cohort.teacherName} · {cohort.studentsCount} students · {formatPercent(cohort.attendancePercent)} attendance
                </span>
                <span>Nearest session {formatDateTime(cohort.nearestSessionAt)}</span>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
};

export default AdminDashboardPage;
