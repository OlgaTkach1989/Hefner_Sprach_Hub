export type TeacherOnlineCohortCard = {
  id: number;
  courseId: number;
  groupCode: string;
  groupName: string;
  courseSlug: string;
  courseTitleDe: string;
  courseTitleEn: string;
  teacherName: string;
  studentsCount: number;
  attendancePercent: number;
  nearestSessionAt: string | null;
};

export type TeacherOnlineCohortListResponse = {
  results: TeacherOnlineCohortCard[];
};

export type TeacherOnlineSession = {
  id: number;
  title: string;
  start: string;
  end: string;
  status: "scheduled" | "live" | "ended" | "canceled";
  isCompleted: boolean;
  joinUrl?: string | null;
  bookingCount: number;
  bookedStudents: {
    enrollmentId: number;
    fullName: string;
    email: string;
    bookedAt: string;
  }[];
};

export type TeacherAttendanceSummary = {
  present: number;
  absent: number;
  excused: number;
  unknown: number;
};

export type TeacherAttendanceSyncMode =
  | "manual_noop"
  | "manual_demo"
  | "graph"
  | "graph_not_configured_demo"
  | "graph_error_demo";

export type TeacherSessionSyncPayload = {
  sync: TeacherAttendanceSyncMode;
  studentsTotal?: number;
  attendanceRowsTotal?: number;
  attendanceSummary: TeacherAttendanceSummary;
};

export type TeacherOnlineStudent = {
  enrollmentId: number;
  fullName: string;
  email: string;
  status: string;
  attendancePercent: number;
};

export type TeacherOnlineCohortCalendar = {
  cohort: {
    id: number;
    groupCode: string;
    groupName: string;
    courseTitleDe: string;
    courseTitleEn: string;
  };
  attendancePercent: number;
  sessions: TeacherOnlineSession[];
  students: TeacherOnlineStudent[];
};

export type TeacherSessionActionResponse = {
  id: number;
  title: string;
  status: TeacherOnlineSession["status"];
  isCompleted: boolean;
  joinUrl?: string | null;
  startsAt: string;
  endsAt: string;
  cohortId?: number;
  cohortStatus?: string;
  sync?: TeacherSessionSyncPayload | null;
  syncError?: string;
  attendanceSyncedAt?: string | null;
};

export type TeacherAttendanceSyncResponse = {
  sessionId: number;
  status: TeacherOnlineSession["status"];
  sync: TeacherAttendanceSyncMode;
  studentsTotal?: number;
  attendanceRowsTotal?: number;
  attendanceSummary: TeacherAttendanceSummary;
  attendanceSyncedAt?: string | null;
};
