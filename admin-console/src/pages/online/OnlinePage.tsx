import { useEffect, useMemo, useState } from "react";

import {
  useGetOnlineCohortDetailQuery,
  useGetOnlineCohortsQuery,
  useGetOnlineCourseDetailQuery,
  useGetOnlineCoursesQuery,
  useUpdateOnlineSessionStatusMutation,
} from "@/bll/online/online.service";
import type { OnlineCourseCard, OnlineSessionStatus } from "@/bll/online/online.type";
import TrainingGovernancePanel from "./TrainingGovernancePanel";
import cl from "./OnlinePage.module.scss";

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

const formatPercent = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(value)) return "-";
  return `${Math.round(value)}%`;
};

const formatPrice = (value?: string | number | null, currency?: string) => {
  if (value === undefined || value === null || value === "") return "-";
  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) return `${value} ${currency ?? ""}`.trim();
  return `${numericValue.toFixed(2)} ${currency ?? ""}`.trim();
};

const sessionStatusOptions: Array<{ value: OnlineSessionStatus; label: string }> = [
  { value: "scheduled", label: "Scheduled" },
  { value: "live", label: "Live" },
  { value: "ended", label: "Ended" },
  { value: "canceled", label: "Canceled" },
];

type StudentSegment = "all" | "risk" | "stable";

const isRiskStudent = (attendancePercent?: number | null) =>
  attendancePercent !== undefined && attendancePercent !== null && attendancePercent < 60;

const resolveApiErrorMessage = (error: unknown, fallback: string) => {
  const data = (error as { data?: { detail?: string } | { status?: string } })?.data;
  if (data && "detail" in data && data.detail) return data.detail;
  if (data && "status" in data && data.status) return data.status;
  return fallback;
};

type OnlinePageProps = {
  compact?: boolean;
  showTrainingGovernance?: boolean;
};

const OnlinePage = ({ compact = false, showTrainingGovernance = true }: OnlinePageProps) => {
  const [query, setQuery] = useState("");
  const [studentQuery, setStudentQuery] = useState("");
  const [studentSegment, setStudentSegment] = useState<StudentSegment>("all");
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [selectedCohortId, setSelectedCohortId] = useState<number | null>(null);
  const trimmedQuery = useMemo(() => query.trim(), [query]);
  const trimmedStudentQuery = useMemo(() => studentQuery.trim().toLowerCase(), [studentQuery]);

  const {
    data: courseListData,
    isLoading: isCourseListLoading,
    isError: isCourseListError,
  } = useGetOnlineCoursesQuery(trimmedQuery || undefined);
  const courseCards = useMemo(() => courseListData?.results ?? [], [courseListData]);

  useEffect(() => {
    if (isCourseListLoading) return;
    if (courseCards.length === 0) {
      if (selectedCourseId !== null) setSelectedCourseId(null);
      return;
    }

    if (!selectedCourseId || !courseCards.some((course) => course.id === selectedCourseId)) {
      setSelectedCourseId(courseCards[0].id);
    }
  }, [courseCards, selectedCourseId, isCourseListLoading]);

  const selectedCourseCard = useMemo(
    () => courseCards.find((course) => course.id === selectedCourseId) ?? null,
    [courseCards, selectedCourseId]
  );

  const {
    data: courseDetailData,
    isLoading: isCourseDetailLoading,
    isError: isCourseDetailError,
    refetch: refetchCourseDetail,
  } = useGetOnlineCourseDetailQuery(selectedCourseId as number, { skip: !selectedCourseId });

  const cohortFilters = useMemo(() => {
    const params: { q?: string; courseId?: number } = {};
    if (trimmedQuery) params.q = trimmedQuery;
    if (selectedCourseId) params.courseId = selectedCourseId;
    return Object.keys(params).length > 0 ? params : undefined;
  }, [trimmedQuery, selectedCourseId]);

  const {
    data: cohortListData,
    isLoading: isCohortListLoading,
    isError: isCohortListError,
  } = useGetOnlineCohortsQuery(cohortFilters);
  const cohortCards = useMemo(() => cohortListData?.results ?? [], [cohortListData]);

  useEffect(() => {
    if (isCohortListLoading) return;
    if (cohortCards.length === 0) {
      if (selectedCohortId !== null) setSelectedCohortId(null);
      return;
    }

    if (!selectedCohortId || !cohortCards.some((cohort) => cohort.id === selectedCohortId)) {
      setSelectedCohortId(cohortCards[0].id);
    }
  }, [cohortCards, selectedCohortId, isCohortListLoading]);

  const {
    data: detailData,
    isLoading: isDetailLoading,
    isError: isDetailError,
    refetch: refetchDetail,
  } = useGetOnlineCohortDetailQuery(selectedCohortId as number, { skip: !selectedCohortId });
  const [updateSessionStatus] = useUpdateOnlineSessionStatusMutation();
  const [sessionActionError, setSessionActionError] = useState("");
  const [sessionUpdatingId, setSessionUpdatingId] = useState<number | null>(null);

  const selectedCohortCard = useMemo(
    () => cohortCards.find((cohort) => cohort.id === selectedCohortId) ?? null,
    [cohortCards, selectedCohortId]
  );

  const courseOverview = useMemo(() => {
    if (courseCards.length === 0) {
      return {
        courses: 0,
        students: 0,
        sessions: 0,
        avgAttendance: null as number | null,
      };
    }

    const students = courseCards.reduce((sum, course) => sum + course.studentsCount, 0);
    const sessions = courseCards.reduce((sum, course) => sum + course.sessionsSummary.total, 0);
    const avgAttendance =
      courseCards.reduce((sum, course) => sum + (Number.isFinite(course.attendancePercent) ? course.attendancePercent : 0), 0) /
      courseCards.length;

    return {
      courses: courseCards.length,
      students,
      sessions,
      avgAttendance,
    };
  }, [courseCards]);

  const courseTeachers = useMemo(() => {
    const teachers = courseDetailData?.teachers ?? selectedCourseCard?.teachers ?? [];
    return teachers.length > 0 ? teachers.join(", ") : "Not assigned";
  }, [courseDetailData, selectedCourseCard]);

  const selectedCourseSessionsSummary = useMemo(() => {
    return courseDetailData?.sessionsSummary ?? selectedCourseCard?.sessionsSummary ?? null;
  }, [courseDetailData, selectedCourseCard]);

  const selectedCourseLabel = useMemo(() => {
    if (!selectedCourseCard) return "No course selected";
    return `${selectedCourseCard.titleDe}${selectedCourseCard.titleEn ? ` (${selectedCourseCard.titleEn})` : ""}`;
  }, [selectedCourseCard]);

  const sessionsSummary = useMemo(() => {
    if (!detailData) {
      return {
        total: 0,
        completed: 0,
        planned: 0,
      };
    }

    const completed = detailData.sessions.filter((session) => session.isCompleted).length;

    return {
      total: detailData.sessions.length,
      completed,
      planned: detailData.sessions.length - completed,
    };
  }, [detailData]);

  const sessionStatusSummary = useMemo(() => {
    if (!detailData) {
      return {
        scheduled: 0,
        live: 0,
        ended: 0,
        canceled: 0,
      };
    }

    return detailData.sessions.reduce(
      (acc, item) => {
        acc[item.status] += 1;
        return acc;
      },
      { scheduled: 0, live: 0, ended: 0, canceled: 0 } as Record<OnlineSessionStatus, number>
    );
  }, [detailData]);

  const studentsSummary = useMemo(() => {
    if (!detailData) {
      return {
        risk: 0,
        stable: 0,
      };
    }

    let risk = 0;
    let stable = 0;

    detailData.students.forEach((student) => {
      if (isRiskStudent(student.attendancePercent)) {
        risk += 1;
      } else {
        stable += 1;
      }
    });

    return { risk, stable };
  }, [detailData]);

  const segmentedStudents = useMemo(() => {
    if (!detailData) return [];

    if (studentSegment === "risk") {
      return detailData.students.filter((student) => isRiskStudent(student.attendancePercent));
    }

    if (studentSegment === "stable") {
      return detailData.students.filter((student) => !isRiskStudent(student.attendancePercent));
    }

    return detailData.students;
  }, [detailData, studentSegment]);

  const filteredStudents = useMemo(() => {
    if (!trimmedStudentQuery) return segmentedStudents;

    return segmentedStudents.filter((student) => {
      const composite = `${student.fullName} ${student.email} ${student.status}`.toLowerCase();
      return composite.includes(trimmedStudentQuery);
    });
  }, [segmentedStudents, trimmedStudentQuery]);

  const nextPlannedSession = useMemo(() => {
    if (!detailData) return null;

    const now = Date.now();
    const candidates = detailData.sessions
      .filter((session) => session.status !== "canceled")
      .sort((a, b) => new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime());

    return candidates.find((session) => new Date(session.startsAt).getTime() >= now) ?? candidates[0] ?? null;
  }, [detailData]);

  const onSessionStatusChange = async (sessionId: number, nextStatus: OnlineSessionStatus) => {
    setSessionActionError("");
    setSessionUpdatingId(sessionId);
    try {
      await updateSessionStatus({ sessionId, status: nextStatus }).unwrap();
      await Promise.all([refetchDetail(), refetchCourseDetail()]);
    } catch (error) {
      setSessionActionError(resolveApiErrorMessage(error, "Failed to update session status."));
    } finally {
      setSessionUpdatingId(null);
    }
  };

  const renderCourseCard = (course: OnlineCourseCard) => (
    <button
      type="button"
      key={course.id}
      className={`${cl.courseCard} ${selectedCourseId === course.id ? cl.courseCardActive : ""}`}
      onClick={() => setSelectedCourseId(course.id)}
    >
      <div className={cl.cardHead}>
        <p className={cl.cardTitle}>{course.titleDe}</p>
        <span className={cl.codeBadge}>{course.slug}</span>
      </div>
      <p className={cl.cardCourse}>{course.titleEn || "No English title"}</p>
      <div className={cl.cardMeta}>
        <span>{course.cohortsCount} cohorts</span>
        <span>{course.studentsCount} students</span>
        <span>{course.sessionsSummary.total} sessions</span>
      </div>
      <p><strong>Teachers:</strong> {course.teachers.length > 0 ? course.teachers.join(", ") : "Not assigned"}</p>
      <p><strong>Price:</strong> {formatPrice(course.priceAmount, course.currency)}</p>
      <p><strong>Next session:</strong> {formatDateTime(course.nearestSessionAt)}</p>
    </button>
  );

  return (
    <section className={cl.root}>
      {!compact ? (
        <header className={cl.header}>
          <div className={cl.headingBlock}>
            <h1>Online Courses Dashboard</h1>
            <p>Course-first analytics for online catalog, cohorts, sessions and attendance.</p>
            <div className={cl.headerStats}>
              <span>{courseOverview.courses} courses</span>
              <span>{courseOverview.students} students</span>
              <span>{courseOverview.sessions} sessions</span>
              <span>Avg attendance {formatPercent(courseOverview.avgAttendance)}</span>
            </div>
          </div>
          <div className={cl.searchWrap}>
            <input
              value={query}
              onChange={(event) => setQuery(event.currentTarget.value)}
              className={cl.search}
              type="text"
              placeholder="Search by course, cohort, teacher"
            />
          </div>
        </header>
      ) : null}

      {compact ? (
        <section className={cl.courseSection}>
          <div className={cl.blockHead}>
            <h3>Catalog overview</h3>
            <span className={cl.sectionHint}>
              {courseOverview.courses} courses · {courseOverview.students} students · Avg attendance{" "}
              {formatPercent(courseOverview.avgAttendance)}
            </span>
          </div>
          <div className={cl.searchWrap}>
            <input
              value={query}
              onChange={(event) => setQuery(event.currentTarget.value)}
              className={cl.search}
              type="text"
              placeholder="Search by course, cohort, teacher"
            />
          </div>
        </section>
      ) : null}

      <section className={cl.courseSection}>
        <div className={cl.blockHead}>
          <h3>Courses</h3>
          <span className={cl.sectionHint}>{selectedCourseLabel}</span>
        </div>
        {isCourseListLoading ? <p>Loading courses...</p> : null}
        {isCourseListError ? <p className={cl.errorText}>Failed to load courses list.</p> : null}
        {!isCourseListLoading && courseCards.length === 0 ? <p>No online courses found.</p> : null}
        <div className={cl.courseGrid}>{courseCards.map(renderCourseCard)}</div>
      </section>

      <div className={cl.layout}>
        <aside className={cl.cardsColumn}>
          <div className={cl.columnTitle}>Cohorts</div>
          {isCohortListLoading ? <p>Loading cohorts...</p> : null}
          {isCohortListError ? <p className={cl.errorText}>Failed to load cohorts list.</p> : null}
          {!isCohortListLoading && cohortCards.length === 0 ? <p>No cohorts found for current course.</p> : null}
          {cohortCards.map((cohort) => (
            <button
              type="button"
              key={cohort.id}
              className={`${cl.card} ${selectedCohortId === cohort.id ? cl.cardActive : ""}`}
              onClick={() => setSelectedCohortId(cohort.id)}
            >
              <div className={cl.cardHead}>
                <p className={cl.cardTitle}>{cohort.groupName}</p>
                <span className={cl.codeBadge}>{cohort.groupCode}</span>
              </div>
              <p className={cl.cardCourse}>{cohort.courseTitleDe}</p>
              <div className={cl.cardMeta}>
                <span>{cohort.studentsCount} students</span>
                <span>{cohort.sessionsCount} sessions</span>
                <span>{formatPercent(cohort.attendancePercent)} attendance</span>
              </div>
              <p><strong>Teacher:</strong> {cohort.teacherName}</p>
              <p><strong>Status:</strong> {cohort.status}{cohort.isPublic ? " / public" : " / hidden"}</p>
              <p><strong>Nearest session:</strong> {formatDateTime(cohort.nearestSessionAt)}</p>
            </button>
          ))}
        </aside>

        <article className={cl.detailsColumn}>
          {!selectedCourseId ? <p>Select a course to view details.</p> : null}
          {selectedCourseId && isCourseDetailLoading ? <p>Loading course details...</p> : null}
          {selectedCourseId && isCourseDetailError ? <p className={cl.errorText}>Failed to load course details.</p> : null}

          {courseDetailData ? (
            <>
              <section className={cl.summaryCard}>
                <div className={cl.summaryTop}>
                  <div className={cl.summaryText}>
                    <h2>{courseDetailData.titleDe}</h2>
                    <p>
                      {courseDetailData.slug}
                      {courseDetailData.titleEn ? ` | ${courseDetailData.titleEn}` : ""}
                    </p>
                    <p>{courseDetailData.descriptionDe}</p>
                  </div>
                  <div className={cl.summaryPills}>
                    <span
                      className={`${cl.healthPill} ${
                        isRiskStudent(courseDetailData.attendancePercent) ? cl.healthRisk : cl.healthGood
                      }`}
                    >
                      Course health: {isRiskStudent(courseDetailData.attendancePercent) ? "Needs attention" : "Stable"}
                    </span>
                    <span className={cl.neutralPill}>
                      {courseDetailData.isPublished ? "Published" : "Unpublished"} / {courseDetailData.lessonsCount} lessons
                    </span>
                  </div>
                </div>
                <div className={cl.summaryFoot}>
                  <span>
                    Teachers: <strong>{courseTeachers}</strong>
                  </span>
                  <span>
                    Next session: <strong>{formatDateTime(courseDetailData.nearestSessionAt)}</strong>
                  </span>
                  <span>
                    Price: <strong>{formatPrice(courseDetailData.priceAmount, courseDetailData.currency)}</strong>
                  </span>
                </div>
              </section>

              <section className={cl.kpiGrid}>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Public Cohorts</span>
                  <strong>{courseDetailData.cohortsSummary.public}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Running / Open</span>
                  <strong>{courseDetailData.cohortsSummary.running} / {courseDetailData.cohortsSummary.open}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Students</span>
                  <strong>{courseDetailData.studentsCount}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Attendance</span>
                  <strong>{formatPercent(courseDetailData.attendancePercent)}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>All Sessions</span>
                  <strong>{selectedCourseSessionsSummary?.total ?? 0}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Completed / Planned</span>
                  <strong>{selectedCourseSessionsSummary?.completed ?? 0} / {selectedCourseSessionsSummary?.planned ?? 0}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Live Sessions</span>
                  <strong>{selectedCourseSessionsSummary?.live ?? 0}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Canceled Sessions</span>
                  <strong>{selectedCourseSessionsSummary?.canceled ?? 0}</strong>
                </div>
              </section>

              {showTrainingGovernance ? (
                <TrainingGovernancePanel
                  courseId={courseDetailData.id}
                  courseTitle={courseDetailData.titleDe}
                />
              ) : null}

              <section className={cl.block}>
                <div className={cl.blockHead}>
                  <h3>Course Cohorts</h3>
                </div>
                <div className={cl.tableWrap}>
                  <table className={cl.dataTable}>
                    <thead>
                      <tr>
                        <th>Cohort</th>
                        <th>Teacher</th>
                        <th>Status</th>
                        <th>Students</th>
                        <th>Sessions</th>
                        <th>Nearest Session</th>
                      </tr>
                    </thead>
                    <tbody>
                      {courseDetailData.cohorts.length === 0 ? (
                        <tr>
                          <td colSpan={6}>No cohorts in this course yet.</td>
                        </tr>
                      ) : null}
                      {courseDetailData.cohorts.map((cohort) => (
                        <tr
                          key={cohort.id}
                          className={selectedCohortId === cohort.id ? cl.rowActive : ""}
                        >
                          <td>
                            <button
                              type="button"
                              className={cl.tableAction}
                              onClick={() => setSelectedCohortId(cohort.id)}
                            >
                              {cohort.groupCode} - {cohort.groupName}
                            </button>
                          </td>
                          <td>{cohort.teacherName}</td>
                          <td>{cohort.status}{cohort.isPublic ? " / public" : " / hidden"}</td>
                          <td>{cohort.studentsCount}</td>
                          <td>{cohort.sessionsCount}</td>
                          <td>{formatDateTime(cohort.nearestSessionAt)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          ) : null}

          {!selectedCohortId ? <p>Select a cohort to view detailed attendance and session controls.</p> : null}
          {selectedCohortId && isDetailLoading ? <p>Loading cohort details...</p> : null}
          {selectedCohortId && isDetailError ? <p className={cl.errorText}>Failed to load cohort details.</p> : null}

          {detailData ? (
            <>
              <section className={cl.summaryCard}>
                <div className={cl.summaryTop}>
                  <div className={cl.summaryText}>
                    <h2>
                      {detailData.groupCode} - {detailData.groupName}
                    </h2>
                    <p>
                      Course: {detailData.courseTitleDe}
                      {detailData.courseTitleEn ? ` (${detailData.courseTitleEn})` : ""}
                    </p>
                  </div>
                  <div className={cl.summaryPills}>
                    <span
                      className={`${cl.healthPill} ${
                        isRiskStudent(detailData.attendancePercent) ? cl.healthRisk : cl.healthGood
                      }`}
                    >
                      Cohort health: {isRiskStudent(detailData.attendancePercent) ? "Needs attention" : "Stable"}
                    </span>
                    <span className={cl.neutralPill}>Total sessions: {sessionsSummary.total}</span>
                  </div>
                </div>
                <div className={cl.summaryFoot}>
                  <span>
                    Next planned session:{" "}
                    <strong>{formatDateTime(nextPlannedSession?.startsAt ?? detailData.nearestSessionAt)}</strong>
                  </span>
                  <span>
                    At-risk students: <strong>{studentsSummary.risk}</strong>
                  </span>
                </div>
              </section>

              <section className={cl.kpiGrid}>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Teacher</span>
                  <strong>{detailData.teacherName}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Students</span>
                  <strong>{detailData.studentsCount}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Attendance</span>
                  <strong>{formatPercent(detailData.attendancePercent)}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Nearest Session</span>
                  <strong>{formatDateTime(detailData.nearestSessionAt ?? selectedCohortCard?.nearestSessionAt)}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Completed Sessions</span>
                  <strong>{detailData.sessionsSummary?.completed ?? sessionsSummary.completed}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Planned Sessions</span>
                  <strong>{detailData.sessionsSummary?.planned ?? sessionsSummary.planned}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Live Sessions</span>
                  <strong>{sessionStatusSummary.live}</strong>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Canceled Sessions</span>
                  <strong>{sessionStatusSummary.canceled}</strong>
                </div>
              </section>

              <section className={cl.block}>
                <div className={cl.blockTitleRow}>
                  <h3>Sessions</h3>
                  <div className={cl.sessionLegend}>
                    <span className={`${cl.lifecyclePill} ${cl.lifecycleScheduled}`}>Scheduled {sessionStatusSummary.scheduled}</span>
                    <span className={`${cl.lifecyclePill} ${cl.lifecycleLive}`}>Live {sessionStatusSummary.live}</span>
                    <span className={`${cl.lifecyclePill} ${cl.lifecycleEnded}`}>Ended {sessionStatusSummary.ended}</span>
                    <span className={`${cl.lifecyclePill} ${cl.lifecycleCanceled}`}>Canceled {sessionStatusSummary.canceled}</span>
                  </div>
                </div>
                {sessionActionError ? <p className={cl.errorText}>{sessionActionError}</p> : null}
                <div className={cl.tableWrap}>
                  <table className={cl.dataTable}>
                    <thead>
                      <tr>
                        <th>Title</th>
                        <th>Time</th>
                        <th>Status</th>
                        <th>Lifecycle</th>
                        <th>Presence</th>
                        <th>Attendance Report</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detailData.sessions.length === 0 ? (
                        <tr>
                          <td colSpan={6}>No sessions in this group yet.</td>
                        </tr>
                      ) : null}
                      {detailData.sessions.map((session) => (
                        <tr key={session.id}>
                          <td>{session.title}</td>
                          <td>{formatDateTime(session.startsAt)}</td>
                          <td>
                            <span className={`${cl.statusPill} ${session.isCompleted ? cl.statusDone : cl.statusPlanned}`}>
                              {session.isCompleted ? "Completed" : "Planned"}
                            </span>
                          </td>
                          <td>
                            <select
                              className={cl.statusSelect}
                              value={session.status}
                              onChange={(event) =>
                                onSessionStatusChange(session.id, event.currentTarget.value as OnlineSessionStatus)
                              }
                              disabled={sessionUpdatingId === session.id}
                            >
                              {sessionStatusOptions.map((item) => (
                                <option key={item.value} value={item.value}>
                                  {item.label}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td>
                            {session.attendanceSummary.present} /{" "}
                            {session.attendanceSummary.present +
                              session.attendanceSummary.absent +
                              session.attendanceSummary.excused +
                              session.attendanceSummary.unknown}
                          </td>
                          <td>
                            <span className={cl.reportInline}>
                              <span>P:{session.attendanceSummary.present}</span>
                              <span>A:{session.attendanceSummary.absent}</span>
                              <span>E:{session.attendanceSummary.excused}</span>
                              <span>U:{session.attendanceSummary.unknown}</span>
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className={cl.block}>
                <div className={cl.blockHead}>
                  <h3>Students</h3>
                  <div className={cl.studentsTools}>
                    <div className={cl.segmentSwitch}>
                      <button
                        type="button"
                        className={`${cl.segmentBtn} ${studentSegment === "all" ? cl.segmentBtnActive : ""}`}
                        onClick={() => setStudentSegment("all")}
                      >
                        All ({detailData.students.length})
                      </button>
                      <button
                        type="button"
                        className={`${cl.segmentBtn} ${studentSegment === "risk" ? cl.segmentBtnActive : ""}`}
                        onClick={() => setStudentSegment("risk")}
                      >
                        At risk ({studentsSummary.risk})
                      </button>
                      <button
                        type="button"
                        className={`${cl.segmentBtn} ${studentSegment === "stable" ? cl.segmentBtnActive : ""}`}
                        onClick={() => setStudentSegment("stable")}
                      >
                        Stable ({studentsSummary.stable})
                      </button>
                    </div>
                    <input
                      value={studentQuery}
                      onChange={(event) => setStudentQuery(event.currentTarget.value)}
                      className={cl.searchSmall}
                      type="text"
                      placeholder="Find student"
                    />
                  </div>
                </div>
                <div className={cl.tableWrap}>
                  <table className={cl.dataTable}>
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Email</th>
                        <th>Status</th>
                        <th>Attendance %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredStudents.length === 0 ? (
                        <tr>
                          <td colSpan={4}>No students match your filter.</td>
                        </tr>
                      ) : null}
                      {filteredStudents.map((student) => (
                        <tr
                          key={student.enrollmentId}
                          className={isRiskStudent(student.attendancePercent) ? cl.rowRisk : ""}
                        >
                          <td>{student.fullName}</td>
                          <td>{student.email}</td>
                          <td>{student.status}</td>
                          <td>{formatPercent(student.attendancePercent)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          ) : null}
        </article>
      </div>
    </section>
  );
};

export default OnlinePage;
