export type TeacherWorkspaceProfile = {
  id: number;
  firstName: string;
  lastName: string;
  fullName: string;
  schoolEmail: string;
  privateEmail: string;
  phone: string | null;
  shortName: string;
  email: string;
};

export type TeacherWorkspaceSummary = {
  courses: number;
  cohorts: number;
  students: number;
  sessions: number;
  attendancePercent: number;
  nextSessionAt?: string | null;
};

export type TeacherWorkspaceCourse = {
  id: number;
  slug: string;
  titleDe: string;
  titleEn: string;
  descriptionDe: string;
  descriptionEn: string;
  studentsCount: number;
  cohortsCount: number;
  sessionsCount: number;
  attendancePercent: number;
  nearestSessionAt?: string | null;
  materialsCount: number;
  recordingsCount: number;
};

export type TeacherWorkspaceMaterial = {
  id: number | string;
  courseId: number;
  courseSlug: string;
  courseTitleDe: string;
  courseTitleEn: string;
  title: string;
  description: string;
  materialType: "resource" | "recording" | "condition";
  language: "de" | "en";
  linkUrl?: string | null;
  sortOrder: number;
};

export type TeacherWorkspaceLessonSectionItem = {
  id: number;
  title: string;
  description: string;
  assetType: "text" | "document" | "link" | "notebook";
  activityType: "video" | "text" | "quiz" | "assignment";
  language: "de" | "en";
  bodyMarkdown: string;
  externalUrl: string;
  fileUrl: string;
  sortOrder: number;
  trainingContent: {
    id: number;
    slug: string;
    name: string;
    contentKind: string;
    sourceUrl?: string | null;
  } | null;
  sourceLibraryItemId?: number | null;
};

export type TeacherWorkspaceLessonSection = {
  id: number;
  sectionType: "introduction" | "main" | "conclusion";
  title: string;
  description: string;
  sortOrder: number;
  items: TeacherWorkspaceLessonSectionItem[];
};

export type TeacherWorkspaceLesson = {
  id: number;
  title: string;
  description: string;
  sortOrder: number;
  moduleId?: number | null;
  moduleTitle?: string;
  moduleSortOrder?: number;
  moduleType?: "module" | "final_assessment";
  sessionId?: number | null;
  sessionTitle?: string;
  sessionStatus?: string;
  startsAt?: string | null;
  endsAt?: string | null;
  joinUrl?: string | null;
  recordingUrl?: string | null;
  groupCode?: string;
  groupName?: string;
  sections: TeacherWorkspaceLessonSection[];
};

export type TeacherWorkspaceCourseModule = {
  id?: number | null;
  title: string;
  description: string;
  moduleType: "module" | "final_assessment";
  weekNumber?: number | null;
  sortOrder: number;
  isActive: boolean;
  lessonsCount: number;
  itemsCount: number;
  startsAt?: string | null;
  endsAt?: string | null;
  groupCode?: string;
  groupName?: string;
  lessons: TeacherWorkspaceLesson[];
};

export type TeacherWorkspaceRecording = {
  id: number;
  title: string;
  courseId: number;
  courseSlug: string;
  courseTitleDe: string;
  courseTitleEn: string;
  groupCode: string;
  startsAt: string;
  recordingUrl?: string | null;
};

export type TeacherWorkspaceUpcomingSession = {
  id: number;
  title: string;
  groupCode: string;
  groupName: string;
  courseTitleDe: string;
  courseTitleEn: string;
  startsAt: string;
  endsAt: string;
  status: "scheduled" | "live" | "ended" | "canceled";
  joinUrl?: string | null;
};

export type TeacherWorkspaceResponse = {
  profile: TeacherWorkspaceProfile;
  summary: TeacherWorkspaceSummary;
  courses: TeacherWorkspaceCourse[];
  cohorts: Array<{
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
    status: string;
    isPublic: boolean;
    sessionsCount: number;
  }>;
  materials: TeacherWorkspaceMaterial[];
  lessonPlansByCourse: Record<number, TeacherWorkspaceLesson[]>;
  courseModulesByCourse: Record<number, TeacherWorkspaceCourseModule[]>;
  recordings: TeacherWorkspaceRecording[];
  upcomingSessions: TeacherWorkspaceUpcomingSession[];
};

export type UpdateTeacherWorkspaceProfileRequest = {
  firstName?: string;
  lastName?: string;
  privateEmail?: string;
  phone?: string;
};

export type TeacherFeedbackRequest = {
  subject: string;
  message: string;
  course_slug?: string;
};

export type TeacherFeedbackResponse = {
  id: number;
  subject: string;
  createdAt: string;
};
