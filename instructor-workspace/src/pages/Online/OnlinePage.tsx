import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";

import {
  useEndTeacherSessionMutation,
  useGetTeacherOnlineCohortCalendarQuery,
  useGetTeacherOnlineCohortsQuery,
  useOpenTeacherSessionMutation,
  useSyncTeacherSessionAttendanceMutation,
} from "@/bll/online/online.service";
import { useGetTeacherWorkspaceQuery } from "@/bll/workspace/workspace.service";
import cl from "./OnlinePage.module.scss";

const CALENDAR_TIME_ZONE = "Europe/Berlin";
const DEFAULT_CALENDAR_EVENT_DURATION_MS = 2 * 60 * 60 * 1000;
const MAX_REASONABLE_CALENDAR_EVENT_DURATION_MS = 12 * 60 * 60 * 1000;

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("de-DE", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: CALENDAR_TIME_ZONE,
  }).format(date);
};

const getTimestamp = (value?: string | null) => {
  if (!value) return null;
  const parsed = new Date(value);
  const timestamp = parsed.getTime();
  return Number.isNaN(timestamp) ? null : timestamp;
};

const isSameMoment = (left?: string | null, right?: string | null) => {
  const leftTimestamp = getTimestamp(left);
  const rightTimestamp = getTimestamp(right);
  return leftTimestamp !== null && rightTimestamp !== null && leftTimestamp === rightTimestamp;
};

type SessionVisualState = "default" | "next" | "completed";

const resolveTeacherSessionVisualState = (
  session: { start: string; end: string; status: string; isCompleted: boolean },
  nextSessionAt?: string | null
): SessionVisualState => {
  if (isSameMoment(session.start, nextSessionAt)) {
    return "next";
  }

  if (
    session.isCompleted ||
    session.status === "ended" ||
    session.status === "canceled"
  ) {
    return "completed";
  }

  const endsAt = getTimestamp(session.end);
  const startsAt = getTimestamp(session.start);
  const now = Date.now();

  if (
    session.status !== "live" &&
    ((endsAt !== null && endsAt < now) ||
      (endsAt === null && startsAt !== null && startsAt < now))
  ) {
    return "completed";
  }

  return "default";
};

const formatPercent = (value: number) =>
  `${Number.isInteger(value) ? value : value.toFixed(1)}%`;

const formatStatusLabel = (value: string) =>
  value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());

const resolveApiErrorMessage = (error: unknown, fallback: string) => {
  const data = (error as { data?: { detail?: string } | { status?: string } })?.data;
  if (data && "detail" in data && data.detail) return data.detail;
  if (data && "status" in data && data.status) return data.status;
  return fallback;
};

const formatCalendarTime = (value: Date) =>
  new Intl.DateTimeFormat("de-DE", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: CALENDAR_TIME_ZONE,
  })
    .format(value)
    .replace(":", ".");

const formatCalendarEventTimeRange = (
  start?: Date | null,
  end?: Date | null
) => {
  if (!start) return "";
  const startLabel = formatCalendarTime(start);
  if (!end) return startLabel;
  return `${startLabel} - ${formatCalendarTime(end)}`;
};

const getCalendarEventRange = (startValue?: string, endValue?: string) => {
  const start = startValue ? new Date(startValue) : null;
  if (!start || Number.isNaN(start.getTime())) {
    return null;
  }

  const parsedEnd = endValue ? new Date(endValue) : null;
  const hasValidEnd =
    parsedEnd &&
    !Number.isNaN(parsedEnd.getTime()) &&
    parsedEnd.getTime() > start.getTime();
  const durationMs = hasValidEnd
    ? parsedEnd.getTime() - start.getTime()
    : DEFAULT_CALENDAR_EVENT_DURATION_MS;
  const safeEnd =
    !hasValidEnd || durationMs > MAX_REASONABLE_CALENDAR_EVENT_DURATION_MS
      ? new Date(start.getTime() + DEFAULT_CALENDAR_EVENT_DURATION_MS)
      : parsedEnd;

  return { start, end: safeEnd };
};

type OnlinePageProps = {
  embedded?: boolean;
  calendarOnly?: boolean;
  showExternalCalendarLinks?: boolean;
};

const buildExternalCalendarUrl = (baseUrl: string, params: Record<string, string | undefined>) => {
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

const OnlinePage = ({ embedded = false, calendarOnly = false, showExternalCalendarLinks = false }: OnlinePageProps) => {
  const [search, setSearch] = useState("");
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [selectedCohortId, setSelectedCohortId] = useState<number | null>(null);
  const [studentSearch, setStudentSearch] = useState("");
  const [searchParams] = useSearchParams();

  const trimmedSearch = useMemo(() => search.trim(), [search]);
  const trimmedStudentSearch = useMemo(() => studentSearch.trim(), [studentSearch]);

  const { data: listData, isLoading: listLoading } = useGetTeacherOnlineCohortsQuery(trimmedSearch || undefined);
  const { data: workspaceData } = useGetTeacherWorkspaceQuery();
  const { data: calendarData, isLoading: detailLoading, refetch: refetchCalendar } = useGetTeacherOnlineCohortCalendarQuery(
    { cohortId: selectedCohortId as number, student: trimmedStudentSearch || undefined },
    { skip: !selectedCohortId }
  );
  const [openSession] = useOpenTeacherSessionMutation();
  const [endSession] = useEndTeacherSessionMutation();
  const [syncSessionAttendance] = useSyncTeacherSessionAttendanceMutation();
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [processingSessionId, setProcessingSessionId] = useState<number | null>(null);

  const cards = listData?.results ?? [];
  const courseOptions = useMemo(
    () =>
      Array.from(
        new Map(
          cards.map((item) => [
            item.courseId,
            {
              id: item.courseId,
              slug: item.courseSlug,
              title: item.courseTitleEn || item.courseTitleDe,
            },
          ])
        ).values()
      ),
    [cards]
  );
  const filteredCards = selectedCourseId ? cards.filter((item) => item.courseId === selectedCourseId) : cards;
  const requestedCohortId = Number(searchParams.get("cohortId") || "");
  const selectedCard = useMemo(
    () => cards.find((item) => item.id === selectedCohortId) ?? null,
    [cards, selectedCohortId]
  );
  const selectedCourseModules = useMemo(() => {
    if (!selectedCard || !workspaceData) return [];
    return workspaceData.courseModulesByCourse[selectedCard.courseId] ?? [];
  }, [selectedCard, workspaceData]);

  useEffect(() => {
    if (cards.length === 0) {
      if (selectedCohortId !== null) {
        setSelectedCohortId(null);
      }
      return;
    }

    if (selectedCourseId === null && courseOptions.length > 0) {
      setSelectedCourseId(courseOptions[0].id);
      return;
    }

    if (selectedCourseId !== null && !courseOptions.some((course) => course.id === selectedCourseId)) {
      setSelectedCourseId(courseOptions[0]?.id ?? null);
      return;
    }

    if (Number.isInteger(requestedCohortId) && requestedCohortId > 0) {
      const requestedExists = filteredCards.some((item) => item.id === requestedCohortId);
      if (requestedExists && selectedCohortId !== requestedCohortId) {
        setSelectedCohortId(requestedCohortId);
        return;
      }
    }

    const currentExists = selectedCohortId !== null && filteredCards.some((item) => item.id === selectedCohortId);
    if (!currentExists) {
      setSelectedCohortId(filteredCards[0]?.id ?? null);
    }
  }, [cards, courseOptions, filteredCards, requestedCohortId, selectedCohortId, selectedCourseId]);

  useEffect(() => {
    if (!selectedCard) return;
    if (selectedCourseId !== selectedCard.courseId) {
      setSelectedCourseId(selectedCard.courseId);
    }
  }, [selectedCard, selectedCourseId]);
  const events =
    calendarData?.sessions.flatMap((session) => {
      const range = getCalendarEventRange(session.start, session.end);
      if (!range) return [];

      return [
        {
          id: String(session.id),
          title: session.title,
          start: range.start,
          end: range.end,
          allDay: false,
        },
      ];
    }) ?? [];

  const outlookCalendarUrl = useMemo(
    () =>
      buildExternalCalendarUrl("https://outlook.office.com/calendar/view/week", {
        login_hint: workspaceData?.profile.schoolEmail || workspaceData?.profile.email,
        prompt: "select_account",
        auth: "2",
      }),
    [workspaceData?.profile.email, workspaceData?.profile.schoolEmail],
  );

  const handleOpenSession = async (sessionId: number) => {
    setActionMessage("");
    setActionError("");
    setProcessingSessionId(sessionId);
    try {
      const payload = await openSession(sessionId).unwrap();
      if (payload.joinUrl) {
        window.open(payload.joinUrl, "_blank", "noopener,noreferrer");
      }
      setActionMessage(`Session "${payload.title}" is open.`);
      await refetchCalendar();
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to open session."));
    } finally {
      setProcessingSessionId(null);
    }
  };

  const handleEndSession = async (sessionId: number) => {
    setActionMessage("");
    setActionError("");
    setProcessingSessionId(sessionId);
    try {
      const payload = await endSession(sessionId).unwrap();
      const summary = payload.sync?.attendanceSummary;
      if (summary) {
        setActionMessage(
          `Session "${payload.title}" ended. Sync completed: ${summary.present} present, ${summary.absent} absent.`
        );
      } else if (payload.syncError) {
        setActionMessage(`Session "${payload.title}" ended, but attendance sync failed: ${payload.syncError}`);
      } else {
        setActionMessage(`Session "${payload.title}" ended.`);
      }
      await refetchCalendar();
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to end session."));
    } finally {
      setProcessingSessionId(null);
    }
  };

  const handleSyncAttendance = async (sessionId: number) => {
    setActionMessage("");
    setActionError("");
    setProcessingSessionId(sessionId);
    try {
      const payload = await syncSessionAttendance(sessionId).unwrap();
      setActionMessage(
        `Attendance sync completed: ${payload.attendanceSummary.present} present, ${payload.attendanceSummary.absent} absent.`
      );
      await refetchCalendar();
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to sync attendance."));
    } finally {
      setProcessingSessionId(null);
    }
  };

  const calendarSection = calendarData ? (
    <section className={cl.panel}>
      {showExternalCalendarLinks ? (
        <div className={cl.calendarSwitcher} aria-label="Calendar source">
          <button type="button" className={`${cl.calendarSwitcherButton} ${cl.calendarSwitcherButtonActive}`}>
            Academy calendar
          </button>
          <a className={cl.calendarSwitcherButton} href={outlookCalendarUrl} target="_blank" rel="noreferrer">
            Outlook Calendar
          </a>
        </div>
      ) : null}
      <div className={cl.panelHeader}>
        <div>
          <span className={cl.sectionEyebrow}>Planning</span>
          <h3>Calendar</h3>
        </div>
        <p>
          Month, week, and day views follow the active application
          theme and keep session blocks readable.
        </p>
      </div>

      <div className={cl.calendarBlock}>
        <FullCalendar
          plugins={[
            dayGridPlugin,
            timeGridPlugin,
            interactionPlugin,
          ]}
          initialView="timeGridWeek"
          events={events}
          height="auto"
          timeZone={CALENDAR_TIME_ZONE}
          slotMinTime="09:00:00"
          slotMaxTime="22:00:00"
          scrollTime="09:00:00"
          slotLabelContent={(arg) => formatCalendarTime(arg.date)}
          eventTimeFormat={{
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
          }}
          eventContent={(arg) => {
            const timeText = formatCalendarEventTimeRange(
              arg.event.start,
              arg.event.end
            );
            return (
              <>
                {timeText ? (
                  <div className="fc-event-time">{timeText}</div>
                ) : null}
                <div className="fc-event-title">
                  {arg.event.title}
                </div>
              </>
            );
          }}
          headerToolbar={{
            left: "prev,next today",
            center: "title",
            right: "dayGridMonth,timeGridWeek,timeGridDay",
          }}
        />
      </div>
    </section>
  ) : null;

  const sessionActionsSection = calendarData ? (
    <section className={cl.panel}>
      <div className={cl.panelHeader}>
        <div>
          <span className={cl.sectionEyebrow}>Operations</span>
          <h3>Session actions</h3>
        </div>
        <p>
          Open live meetings or sync attendance directly from the
          planned session list.
        </p>
      </div>

      {actionError ? (
        <p className={`${cl.notice} ${cl.noticeError}`}>
          {actionError}
        </p>
      ) : null}
      {actionMessage ? (
        <p className={`${cl.notice} ${cl.noticeSuccess}`}>
          {actionMessage}
        </p>
      ) : null}

      <div className={cl.tableWrap}>
        <table>
          <thead>
            <tr>
              <th>Session</th>
              <th>Time</th>
              <th>Status</th>
              <th>Join link</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {calendarData.sessions.map((session) => {
              const visualState = resolveTeacherSessionVisualState(
                session,
                selectedCard?.nearestSessionAt
              );

              return (
              <tr
                key={session.id}
                className={`${cl.sessionRow} ${
                  visualState === "next"
                    ? cl.sessionRowNext
                    : visualState === "completed"
                      ? cl.sessionRowCompleted
                      : ""
                }`}
              >
                <td className={cl.primaryCell}>{session.title}</td>
                <td>{formatDateTime(session.start)}</td>
                <td>
                  <span
                    className={cl.statusBadge}
                    data-status={session.status}
                  >
                    {formatStatusLabel(session.status)}
                  </span>
                </td>
                <td>
                  {session.joinUrl ? (
                    <a
                      className={cl.inlineLink}
                      href={session.joinUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open link
                    </a>
                  ) : (
                    "-"
                  )}
                </td>
                <td className={cl.actionsCell}>
                  <button
                    type="button"
                    className={`${cl.primaryAction} ${
                      visualState === "next" ? cl.primaryActionNext : ""
                    }`}
                    onClick={() => handleOpenSession(session.id)}
                    disabled={
                      processingSessionId === session.id ||
                      session.status === "ended" ||
                      session.status === "canceled"
                    }
                  >
                    Open
                  </button>
                  <button
                    type="button"
                    className={cl.dangerAction}
                    onClick={() => handleEndSession(session.id)}
                    disabled={
                      processingSessionId === session.id ||
                      session.status !== "live"
                    }
                  >
                    End
                  </button>
                  <button
                    type="button"
                    className={cl.secondaryAction}
                    onClick={() => handleSyncAttendance(session.id)}
                    disabled={processingSessionId === session.id}
                  >
                    Sync
                  </button>
                </td>
              </tr>
              );
            })}
            {calendarData.sessions.length === 0 ? (
              <tr>
                <td colSpan={5}>No sessions in this group.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  ) : null;

  return (
    <div className={cl.pageWrapper}>
      <section className={cl.root}>
        {embedded ? null : (
          <header className={cl.header}>
            <div className={cl.headerCopy}>
              <span className={cl.kicker}>Teacher workspace</span>
              <h1>Online</h1>
              <p>
                {calendarOnly
                  ? "Review scheduled sessions from a single themed calendar view."
                  : "Review cohorts, upcoming sessions, and attendance from a single themed calendar view."}
              </p>
            </div>

            <div className={cl.searchWrap}>
              <label className={cl.searchLabel} htmlFor="online-cohort-search">
                Search groups
              </label>
              <input
                id="online-cohort-search"
                className={cl.search}
                type="text"
                value={search}
                onChange={(event) => setSearch(event.currentTarget.value)}
                placeholder="Search courses or groups"
              />
            </div>
          </header>
        )}

        {embedded ? (
          <div className={cl.searchWrap}>
            <label className={cl.searchLabel} htmlFor="online-cohort-search">
              Search groups
            </label>
            <input
              id="online-cohort-search"
              className={cl.search}
              type="text"
              value={search}
              onChange={(event) => setSearch(event.currentTarget.value)}
              placeholder="Search courses or groups"
            />
          </div>
        ) : null}

        <div className={cl.layout}>
            <aside className={cl.sidebar}>
              <section className={cl.courseSelector}>
                <div className={cl.sidebarHeader}>
                  <div>
                    <span className={cl.sidebarKicker}>Assigned courses</span>
                    <h2>Your courses</h2>
                  </div>
                  <span className={cl.sidebarBadge}>{courseOptions.length}</span>
                </div>

                <div className={cl.courseChips}>
                  {courseOptions.map((course) => (
                    <button
                      key={course.id}
                      type="button"
                      className={`${cl.courseChip} ${selectedCourseId === course.id ? cl.courseChipActive : ""}`}
                      onClick={() => {
                        setSelectedCourseId(course.id);
                        setSelectedCohortId(cards.find((item) => item.courseId === course.id)?.id ?? null);
                      }}
                    >
                      {course.title}
                    </button>
                  ))}
                </div>
              </section>

              <div className={cl.sidebarHeader}>
                <div>
                  <span className={cl.sidebarKicker}>Delivery groups</span>
                  <h2>Course cohorts</h2>
                </div>
                <span className={cl.sidebarBadge}>{filteredCards.length}</span>
              </div>

              <div className={cl.cards}>
                {listLoading ? (
                <div className={cl.emptyState}>
                  <strong>Loading groups...</strong>
                  <p>Assigned cohorts will appear here as soon as they load.</p>
                </div>
              ) : null}

              {!listLoading && filteredCards.length === 0 ? (
                <div className={cl.emptyState}>
                  <strong>No groups assigned.</strong>
                  <p>When cohorts are assigned to the selected course, they will appear here.</p>
                </div>
              ) : null}

              {filteredCards.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  className={`${cl.card} ${
                    selectedCohortId === item.id ? cl.cardActive : ""
                  }`}
                  onClick={() => setSelectedCohortId(item.id)}
                >
                  <div className={cl.cardTopRow}>
                    <p className={cl.cardTitle}>{item.groupName}</p>
                    <span className={cl.cardCode}>{item.groupCode}</span>
                  </div>
                  <p className={cl.cardSubtitle}>{item.courseTitleEn || item.courseTitleDe}</p>

                  <div className={cl.cardMetaGrid}>
                    <div className={cl.cardMetaItem}>
                      <span>Teacher</span>
                      <strong>{item.teacherName}</strong>
                    </div>
                    <div className={cl.cardMetaItem}>
                      <span>Students</span>
                      <strong>{item.studentsCount}</strong>
                    </div>
                    <div className={cl.cardMetaItem}>
                      <span>Attendance</span>
                      <strong>{formatPercent(item.attendancePercent)}</strong>
                    </div>
                    <div className={cl.cardMetaItem}>
                      <span>Nearest</span>
                      <strong>{formatDateTime(item.nearestSessionAt)}</strong>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </aside>

          <article className={cl.detailTop}>
            {!selectedCohortId ? (
              <div className={cl.emptyState}>
                <strong>Select a cohort.</strong>
                <p>
                  Pick a group on the left to open the calendar, session
                  actions, and the student roster.
                </p>
              </div>
            ) : null}

            {detailLoading ? (
              <div className={cl.emptyState}>
                <strong>Loading details...</strong>
                <p>Preparing sessions, students, and attendance data.</p>
              </div>
            ) : null}

            {calendarData ? (
              <>
                <section className={cl.hero}>
                  <div className={cl.heroCopy}>
                    <span className={cl.kicker}>Active cohort</span>
                    <h2>{calendarData.cohort.courseTitleEn || calendarData.cohort.courseTitleDe}</h2>
                    <p className={cl.heroMeta}>
                      {calendarData.cohort.groupCode} -{" "}
                      {calendarData.cohort.groupName}
                    </p>
                  </div>

                  <div className={cl.metricGrid}>
                    <article className={cl.metricCard}>
                      <span>Attendance</span>
                      <strong>{formatPercent(calendarData.attendancePercent)}</strong>
                    </article>
                    <article className={cl.metricCard}>
                      <span>Students</span>
                      <strong>{calendarData.students.length}</strong>
                    </article>
                    <article className={cl.metricCard}>
                      <span>Sessions</span>
                      <strong>{calendarData.sessions.length}</strong>
                    </article>
                    <article className={cl.metricCard}>
                      <span>Nearest start</span>
                      <strong>{formatDateTime(selectedCard?.nearestSessionAt)}</strong>
                    </article>
                  </div>
                </section>

                {selectedCourseModules.length > 0 ? (
                  <section className={cl.outlinePanel}>
                    <div className={cl.panelHeader}>
                      <div>
                        <span className={cl.sectionEyebrow}>Course outline</span>
                        <h3>Lessons linked to this course</h3>
                      </div>
                      <p>Use this quick outline to confirm what should be delivered in the selected course scope.</p>
                    </div>

                    <div className={cl.outlineGrid}>
                      {selectedCourseModules.map((module, moduleIndex) => (
                        <article key={`${module.id ?? moduleIndex}_${module.sortOrder}`} className={cl.outlineModule}>
                          <strong>{module.title}</strong>
                          <span>
                            {module.moduleType === "final_assessment"
                              ? "Final assessment"
                              : `Week ${module.weekNumber ?? moduleIndex + 1}`}
                          </span>
                          <div className={cl.outlineLessons}>
                            {module.lessons.map((lesson) => (
                              <p key={lesson.id}>
                                <strong>Lesson {lesson.sortOrder}:</strong> {lesson.title}
                              </p>
                            ))}
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>
                ) : null}
              </>
            ) : null}
          </article>
        </div>

        {calendarData ? (
          <div className={cl.fullWidthSections}>
            {calendarSection}
            {calendarOnly ? null : sessionActionsSection}

            {calendarOnly ? null : (
            <section className={cl.panel}>
              <div className={cl.studentsHeader}>
                <div>
                  <span className={cl.sectionEyebrow}>Roster</span>
                  <h3>Students</h3>
                </div>
                <div className={cl.compactSearchWrap}>
                  <label
                    className={cl.searchLabel}
                    htmlFor="learner-portal-search"
                  >
                    Search student
                  </label>
                  <input
                    id="learner-portal-search"
                    value={studentSearch}
                    onChange={(event) =>
                      setStudentSearch(event.currentTarget.value)
                    }
                    type="text"
                    placeholder="Search student"
                  />
                </div>
              </div>

              <div className={cl.tableWrap}>
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Status</th>
                      <th>Attendance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {calendarData.students.map((student) => (
                      <tr key={student.enrollmentId}>
                        <td className={cl.primaryCell}>{student.fullName}</td>
                        <td>{student.email}</td>
                        <td>
                          <span
                            className={cl.statusBadge}
                            data-status={student.status}
                          >
                            {formatStatusLabel(student.status)}
                          </span>
                        </td>
                        <td>{formatPercent(student.attendancePercent)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            )}
          </div>
        ) : null}
      </section>
    </div>
  );
};

export default OnlinePage;
