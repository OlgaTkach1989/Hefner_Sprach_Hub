import { useEffect, useMemo, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";
import timeGridPlugin from "@fullcalendar/timegrid";

import {
  useEndOnlineAdminSessionMutation,
  useGetOnlineCohortDetailQuery,
  useGetOnlineCohortsQuery,
  useOpenOnlineAdminSessionMutation,
  useSyncOnlineAdminSessionAttendanceMutation,
} from "@/bll/online/online.service";
import type { OnlineCohortDetailSession } from "@/bll/online/online.type";
import cl from "./CuratorOnlineOperationsSection.module.scss";

const CALENDAR_TIME_ZONE = "Europe/Berlin";
const DEFAULT_CALENDAR_EVENT_DURATION_MS = 2 * 60 * 60 * 1000;
const MAX_REASONABLE_CALENDAR_EVENT_DURATION_MS = 12 * 60 * 60 * 1000;

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
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
  new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: CALENDAR_TIME_ZONE,
  }).format(value);

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

const resolveSessionVisualState = (
  session: OnlineCohortDetailSession,
  nextSessionAt?: string | null
) => {
  const currentTimestamp = getTimestamp(session.startsAt);
  const nextTimestamp = getTimestamp(nextSessionAt);
  if (currentTimestamp !== null && nextTimestamp !== null && currentTimestamp === nextTimestamp) {
    return "next";
  }
  if (session.isCompleted || session.status === "ended" || session.status === "canceled") {
    return "completed";
  }
  return "default";
};

export const CuratorOnlineOperationsSection = () => {
  const [search, setSearch] = useState("");
  const [selectedCohortId, setSelectedCohortId] = useState<number | null>(null);
  const [studentSearch, setStudentSearch] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [processingSessionId, setProcessingSessionId] = useState<number | null>(null);

  const trimmedSearch = useMemo(() => search.trim(), [search]);
  const trimmedStudentSearch = useMemo(() => studentSearch.trim().toLowerCase(), [studentSearch]);

  const { data: cohortListData, isLoading: listLoading } = useGetOnlineCohortsQuery(
    trimmedSearch ? { q: trimmedSearch } : undefined
  );
  const cards = useMemo(() => cohortListData?.results ?? [], [cohortListData]);

  useEffect(() => {
    if (listLoading) return;
    if (cards.length === 0) {
      if (selectedCohortId !== null) setSelectedCohortId(null);
      return;
    }

    if (!selectedCohortId || !cards.some((item) => item.id === selectedCohortId)) {
      setSelectedCohortId(cards[0].id);
    }
  }, [cards, listLoading, selectedCohortId]);

  const { data: detailData, isLoading: detailLoading, refetch } = useGetOnlineCohortDetailQuery(
    selectedCohortId as number,
    { skip: !selectedCohortId }
  );

  const [openSession] = useOpenOnlineAdminSessionMutation();
  const [endSession] = useEndOnlineAdminSessionMutation();
  const [syncSessionAttendance] = useSyncOnlineAdminSessionAttendanceMutation();

  const selectedCard = useMemo(
    () => cards.find((item) => item.id === selectedCohortId) ?? null,
    [cards, selectedCohortId]
  );

  const filteredStudents = useMemo(() => {
    if (!detailData) return [];
    if (!trimmedStudentSearch) return detailData.students;

    return detailData.students.filter((student) =>
      `${student.fullName} ${student.email} ${student.status}`
        .toLowerCase()
        .includes(trimmedStudentSearch)
    );
  }, [detailData, trimmedStudentSearch]);

  const events =
    detailData?.sessions.flatMap((session) => {
      const range = getCalendarEventRange(session.startsAt, session.endsAt);
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

  const handleAction = async (
    sessionId: number,
    action: "open" | "end" | "sync"
  ) => {
    setActionMessage("");
    setActionError("");
    setProcessingSessionId(sessionId);

    try {
      if (action === "open") {
        const payload = await openSession(sessionId).unwrap();
        if (payload.joinUrl) {
          window.open(payload.joinUrl, "_blank", "noopener,noreferrer");
        }
        setActionMessage(`Session "${payload.title}" is open.`);
      }

      if (action === "end") {
        const payload = await endSession(sessionId).unwrap();
        const summary = payload.sync?.attendanceSummary;
        if (summary) {
          setActionMessage(
            `Session "${payload.title}" ended. Sync completed: ${summary.present} present, ${summary.absent} absent.`
          );
        } else {
          setActionMessage(`Session "${payload.title}" ended.`);
        }
      }

      if (action === "sync") {
        const payload = await syncSessionAttendance(sessionId).unwrap();
        setActionMessage(
          `Attendance sync completed: ${payload.attendanceSummary.present} present, ${payload.attendanceSummary.absent} absent.`
        );
      }

      await refetch();
    } catch (error) {
      setActionError(
        resolveApiErrorMessage(
          error,
          action === "sync" ? "Failed to sync attendance." : `Failed to ${action} session.`
        )
      );
    } finally {
      setProcessingSessionId(null);
    }
  };

  return (
    <section className={cl.root}>
      <header className={cl.header}>
        <div className={cl.headerCopy}>
          <span className={cl.kicker}>Instructor operations</span>
          <h2>Online</h2>
          <p>Manage live sessions, calendars, and attendance with the same operating flow as the teacher workspace.</p>
        </div>

        <div className={cl.searchWrap}>
          <label className={cl.searchLabel} htmlFor="curator-cohort-search">
            Search groups
          </label>
          <input
            id="curator-cohort-search"
            className={cl.search}
            type="text"
            value={search}
            onChange={(event) => setSearch(event.currentTarget.value)}
            placeholder="Search courses or cohorts"
          />
        </div>
      </header>

      <div className={cl.layout}>
        <aside className={cl.sidebar}>
          <div className={cl.sidebarHeader}>
            <div>
              <span className={cl.sectionEyebrow}>Active groups</span>
              <h3>Cohorts</h3>
            </div>
            <span className={cl.sidebarBadge}>{cards.length}</span>
          </div>

          <div className={cl.cards}>
            {listLoading ? (
              <div className={cl.emptyState}>
                <strong>Loading cohorts...</strong>
                <p>Assigned and published cohorts will appear here once the data is ready.</p>
              </div>
            ) : null}

            {!listLoading && cards.length === 0 ? (
              <div className={cl.emptyState}>
                <strong>No cohorts found.</strong>
                <p>Try another search or create a new course cohort in the catalog.</p>
              </div>
            ) : null}

            {cards.map((item) => (
              <button
                type="button"
                key={item.id}
                className={`${cl.card} ${selectedCohortId === item.id ? cl.cardActive : ""}`}
                onClick={() => setSelectedCohortId(item.id)}
              >
                <div className={cl.cardTopRow}>
                  <p className={cl.cardTitle}>{item.groupName}</p>
                  <span className={cl.cardCode}>{item.groupCode}</span>
                </div>
                <p className={cl.cardSubtitle}>{item.courseTitleDe}</p>
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

        <div className={cl.mainColumn}>
          {!selectedCohortId ? (
            <div className={cl.emptyState}>
              <strong>Select a cohort.</strong>
              <p>Choose a cohort to open the calendar, session actions, and student roster.</p>
            </div>
          ) : null}

          {detailLoading ? (
            <div className={cl.emptyState}>
              <strong>Loading details...</strong>
              <p>Preparing sessions, students, and attendance data.</p>
            </div>
          ) : null}

          {detailData ? (
            <>
              <section className={cl.hero}>
                <div className={cl.heroCopy}>
                  <span className={cl.kicker}>Selected cohort</span>
                  <h3>{detailData.courseTitleDe}</h3>
                  <p className={cl.heroMeta}>
                    {detailData.groupCode} · {detailData.groupName}
                  </p>
                </div>
                <div className={cl.metricGrid}>
                  <article className={cl.metricCard}>
                    <span>Attendance</span>
                    <strong>{formatPercent(detailData.attendancePercent)}</strong>
                  </article>
                  <article className={cl.metricCard}>
                    <span>Students</span>
                    <strong>{detailData.students.length}</strong>
                  </article>
                  <article className={cl.metricCard}>
                    <span>Sessions</span>
                    <strong>{detailData.sessions.length}</strong>
                  </article>
                  <article className={cl.metricCard}>
                    <span>Nearest start</span>
                    <strong>{formatDateTime(selectedCard?.nearestSessionAt)}</strong>
                  </article>
                </div>
              </section>

              <section className={cl.panel}>
                <div className={cl.panelHeader}>
                  <div>
                    <span className={cl.sectionEyebrow}>Planning</span>
                    <h3>Calendar</h3>
                  </div>
                  <p>Track the selected cohort in month, week, or day view.</p>
                </div>
                <div className={cl.calendarBlock}>
                  <FullCalendar
                    plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
                    initialView="timeGridWeek"
                    events={events}
                    height="auto"
                    timeZone={CALENDAR_TIME_ZONE}
                    slotMinTime="09:00:00"
                    slotMaxTime="22:00:00"
                    scrollTime="09:00:00"
                    slotLabelContent={(arg) => formatCalendarTime(arg.date)}
                    eventTimeFormat={{ hour: "2-digit", minute: "2-digit", hour12: false }}
                    headerToolbar={{
                      left: "prev,next today",
                      center: "title",
                      right: "dayGridMonth,timeGridWeek,timeGridDay",
                    }}
                  />
                </div>
              </section>

              <section className={cl.panel}>
                <div className={cl.panelHeader}>
                  <div>
                    <span className={cl.sectionEyebrow}>Operations</span>
                    <h3>Session actions</h3>
                  </div>
                  <p>Open, end, or sync attendance for the selected cohort sessions.</p>
                </div>

                {actionError ? <p className={`${cl.notice} ${cl.noticeError}`}>{actionError}</p> : null}
                {actionMessage ? <p className={`${cl.notice} ${cl.noticeSuccess}`}>{actionMessage}</p> : null}

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
                      {detailData.sessions.length === 0 ? (
                        <tr>
                          <td colSpan={5}>No sessions in this cohort.</td>
                        </tr>
                      ) : null}
                      {detailData.sessions.map((session) => {
                        const visualState = resolveSessionVisualState(session, selectedCard?.nearestSessionAt);

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
                            <td>{formatDateTime(session.startsAt)}</td>
                            <td>
                              <span className={cl.statusBadge} data-status={session.status}>
                                {formatStatusLabel(session.status)}
                              </span>
                            </td>
                            <td>
                              {session.joinUrl ? (
                                <a className={cl.inlineLink} href={session.joinUrl} target="_blank" rel="noreferrer">
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
                                onClick={() => void handleAction(session.id, "open")}
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
                                onClick={() => void handleAction(session.id, "end")}
                                disabled={processingSessionId === session.id || session.status !== "live"}
                              >
                                End
                              </button>
                              <button
                                type="button"
                                className={cl.secondaryAction}
                                onClick={() => void handleAction(session.id, "sync")}
                                disabled={processingSessionId === session.id}
                              >
                                Sync
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className={cl.panel}>
                <div className={cl.studentsHeader}>
                  <div>
                    <span className={cl.sectionEyebrow}>Roster</span>
                    <h3>Students</h3>
                  </div>
                  <div className={cl.compactSearchWrap}>
                    <label className={cl.searchLabel} htmlFor="curator-student-search">
                      Search student
                    </label>
                    <input
                      id="curator-student-search"
                      value={studentSearch}
                      onChange={(event) => setStudentSearch(event.currentTarget.value)}
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
                      {filteredStudents.length === 0 ? (
                        <tr>
                          <td colSpan={4}>No students match your filter.</td>
                        </tr>
                      ) : null}
                      {filteredStudents.map((student) => (
                        <tr key={student.enrollmentId}>
                          <td className={cl.primaryCell}>{student.fullName}</td>
                          <td>{student.email}</td>
                          <td>
                            <span className={cl.statusBadge} data-status={student.status}>
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
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
};
