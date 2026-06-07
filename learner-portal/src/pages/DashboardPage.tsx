import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { isAxiosError } from "axios";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";

import {
  createSupportMessage,
  fetchStudentDashboard,
  fetchSupportMessages,
  markStudentSessionJoin,
  updateStudentProfile,
} from "../api/onlineStudentApi";
import { AppsTab } from "../components/apps/AppsTab";
import { CourseStructureTree } from "../components/course/CourseStructureTree";
import { InformationTab } from "../components/information/InformationTab";
import { NotificationToast } from "../components/ui/NotificationToast";
import { useAuth } from "../context/AuthContext";
import { useUiPreferences } from "../context/UiPreferencesContext";
import type {
  DashboardResponse,
  Gender,
  StudentProfile,
  SupportMessage,
} from "../types";
import "./DashboardPage.css";

type DashboardTab =
  | "profile"
  | "course"
  | "calendar"
  | "materials"
  | "recordings"
  | "app"
  | "support"
  | "information";
type DashboardTabConfig = {
  id: DashboardTab;
  labelKey: string;
  icon: JSX.Element;
};

const SIDEBAR_STATE_KEY = "learning-hub.learner.sidebar-collapsed";

const ProfileIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 4a4 4 0 1 1 0 8 4 4 0 0 1 0-8Zm0 10c4.42 0 8 2.02 8 4.5V20H4v-1.5C4 16.02 7.58 14 12 14Z" />
  </svg>
);

const CourseIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M5 4h12a2 2 0 0 1 2 2v10.2a2 2 0 0 1-2 2H9l-4 2V6a2 2 0 0 1 2-2Zm2 3v1.5h8V7H7Zm0 4v1.5h8V11H7Z" />
  </svg>
);

const CalendarIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M7 2h2v2h6V2h2v2h2a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2V2Zm12 7H5v10h14V9Z" />
  </svg>
);

const RecordingsIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M5 5h10a2 2 0 0 1 2 2v1.4l3.14-1.88A1 1 0 0 1 22 7.38v9.24a1 1 0 0 1-1.86.86L17 15.6V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" />
  </svg>
);

const AppIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 4h7v7H4V4Zm9 0h7v7h-7V4ZM4 13h7v7H4v-7Zm9 0h7v7h-7v-7Z" />
  </svg>
);

const SupportIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 3a8 8 0 0 1 8 8c0 2.1-.8 3.9-2.14 5.3L19 21l-4.55-1.14A7.9 7.9 0 0 1 12 20a8 8 0 1 1 0-17Zm-2.2 6.3V11h1.7V9.3H9.8Zm2.7 0V11h1.7V9.3h-1.7Zm2.7 0V11H17V9.3h-1.8Z" />
  </svg>
);

const InformationIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20Zm-.8 5.6v1.8h1.6V7.6h-1.6Zm0 4v5h1.6v-5h-1.6Z" />
  </svg>
);

const LogoutIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M10 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5v-2H5V6h5V4Zm7.59 7-2.3-2.29L16.7 7.3 21.41 12l-4.7 4.7-1.42-1.41L17.59 13H9v-2h8.59Z" />
  </svg>
);

const SidebarToggleIcon = ({ collapsed }: { collapsed: boolean }) => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    {collapsed ? (
      <path d="M9.29 7.29 13.59 11.59 9.29 15.89 10.7 17.3 16.41 11.59 10.7 5.88 9.29 7.29Z" />
    ) : (
      <path d="M14.71 7.29 10.41 11.59 14.71 15.89 13.3 17.3 7.59 11.59 13.3 5.88 14.71 7.29Z" />
    )}
  </svg>
);

const tabConfig: DashboardTabConfig[] = [
  { id: "profile", labelKey: "tabProfile", icon: <ProfileIcon /> },
  { id: "course", labelKey: "tabCourse", icon: <CourseIcon /> },
  { id: "calendar", labelKey: "tabCalendar", icon: <CalendarIcon /> },
  // { id: "materials", labelKey: "tabMaterials" }, // Temporarily hidden until this area is redesigned.
  { id: "recordings", labelKey: "tabRecordings", icon: <RecordingsIcon /> },
  { id: "app", labelKey: "tabApp", icon: <AppIcon /> },
  { id: "support", labelKey: "tabSupport", icon: <SupportIcon /> },
  { id: "information", labelKey: "tabInformation", icon: <InformationIcon /> },
];

const MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024;
const DEFAULT_CALENDAR_EVENT_DURATION_MS = 2 * 60 * 60 * 1000;
const MAX_REASONABLE_CALENDAR_EVENT_DURATION_MS = 12 * 60 * 60 * 1000;

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
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

const isStudentSessionCompleted = (
  session: DashboardResponse["enrollments"][number]["sessions"][number],
): boolean => {
  if (session.is_completed) {
    return true;
  }

  const endsAt = getTimestamp(session.ends_at);
  const startsAt = getTimestamp(session.starts_at);
  const now = Date.now();

  if ((endsAt !== null && endsAt < now) || (endsAt === null && startsAt !== null && startsAt < now)) {
    return true;
  }

  return false;
};

const resolveStudentSessionVisualState = (
  session: DashboardResponse["enrollments"][number]["sessions"][number],
  nextSessionAt?: string | null
): SessionVisualState => {
  if (isSameMoment(session.starts_at, nextSessionAt)) {
    return "next";
  }

  if (isStudentSessionCompleted(session)) {
    return "completed";
  }

  return "default";
};

const getCalendarEventRange = (startsAt?: string, endsAt?: string) => {
  const start = startsAt ? new Date(startsAt) : null;
  if (!start || Number.isNaN(start.getTime())) {
    return null;
  }

  const parsedEnd = endsAt ? new Date(endsAt) : null;
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

const extractErrorMessage = (error: unknown, fallback: string) => {
  if (!isAxiosError(error)) return fallback;

  const responseData = error.response?.data;
  if (!responseData) return fallback;
  if (typeof responseData === "string") return responseData;
  if (typeof responseData.detail === "string") return responseData.detail;

  if (typeof responseData === "object") {
    for (const value of Object.values(responseData)) {
      if (Array.isArray(value) && typeof value[0] === "string") return value[0];
      if (typeof value === "string") return value;
    }
  }
  return fallback;
};

const normalizePhoneInput = (raw: string) => {
  const value = raw.trim();

  let cleaned = value.replace(/[^\d+]/g, "");

  if (cleaned.startsWith("+")) {
    cleaned = "+" + cleaned.slice(1).replace(/\+/g, "");
  } else {
    cleaned = cleaned.replace(/\+/g, "");
  }

  const plus = cleaned.startsWith("+") ? "+" : "";
  const digits = cleaned.replace(/\D/g, "").slice(0, 15);

  return plus + digits;
};

const lessonSectionLabel = (sectionType: "introduction" | "main" | "conclusion") => {
  if (sectionType === "introduction") return "Introduction";
  if (sectionType === "main") return "Main content";
  return "Conclusion";
};

const courseAudienceBadgeClass = (slug: string) => {
  if (slug === "external-users") return "dashboard-page__role-badge--guest";
  if (slug === "interns-new-grads") return "dashboard-page__role-badge--student";
  if (slug === "lateral-transfers") return "dashboard-page__role-badge--instructor";
  return "dashboard-page__role-badge--admin";
};

const completionStatusClass = (
  status: DashboardResponse["enrollments"][number]["completion"]["status"],
) => {
  if (status === "completed") return "dashboard-page__completion-status--completed";
  if (status === "ready_for_attestation") return "dashboard-page__completion-status--ready";
  return "dashboard-page__completion-status--progress";
};

const isDashboardTab = (value: string | null): value is DashboardTab =>
  Boolean(value && tabConfig.some((tab) => tab.id === value));

const deriveModulesFromLessonPlan = (
  lessonPlan: DashboardResponse["enrollments"][number]["lessonPlan"]
) => {
  const grouped = new Map<
    string,
    {
      id?: number | null;
      title: string;
      description: string;
      moduleType: "module" | "final_assessment";
      weekNumber?: number | null;
      sortOrder: number;
      isActive: boolean;
      lessonsCount: number;
      itemsCount: number;
      lessons: DashboardResponse["enrollments"][number]["lessonPlan"];
    }
  >();
  lessonPlan.forEach((lesson, index) => {
    const title = lesson.moduleTitle || "Module 1 (Week 1)";
    const key = `${lesson.moduleId ?? "legacy"}:${title}`;
    if (!grouped.has(key)) {
      grouped.set(key, {
        id: lesson.moduleId ?? null,
        title,
        description: "",
        moduleType: lesson.moduleType ?? "module",
        weekNumber: null,
        sortOrder: lesson.moduleSortOrder ?? (index + 1) * 10,
        isActive: true,
        lessonsCount: 0,
        itemsCount: 0,
        lessons: [],
      });
    }
    const entry = grouped.get(key);
    if (!entry) return;
    entry.lessons.push(lesson);
    entry.lessonsCount += 1;
    entry.itemsCount += lesson.sections.reduce((count, section) => count + section.items.length, 0);
  });
  return [...grouped.values()].sort((left, right) => left.sortOrder - right.sortOrder);
};

const resolveLessonItemLink = (
  item: DashboardResponse["enrollments"][number]["lessonPlan"][number]["sections"][number]["items"][number]
) => {
  return item.externalUrl || item.fileUrl || item.trainingContent?.sourceUrl || "";
};

const resolveHighlightedSession = (
  sessions: DashboardResponse["enrollments"][number]["sessions"],
  nextSessionAt?: string | null,
) => {
  if (sessions.length === 0) return null;
  return (
    sessions.find((session) => isSameMoment(session.starts_at, nextSessionAt))
    ?? sessions.find((session) => !isStudentSessionCompleted(session))
    ?? sessions[0]
  );
};

const enrollmentCourseTitle = (
  enrollment: DashboardResponse["enrollments"][number],
  preferredLanguage: StudentProfile["preferred_language"],
) => (preferredLanguage === "en" ? enrollment.course.titleEn : enrollment.course.titleDe);

export const DashboardPage = () => {
  const { t } = useTranslation();
  const { isAuthenticated, logout } = useAuth();
  const { locale, setLocale, theme, toggleTheme } = useUiPreferences();
  const initialSearchParams = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
  const requestedTab = initialSearchParams?.get("tab") ?? null;
  const initialTab: DashboardTab =
    requestedTab === "training" ? "course" : isDashboardTab(requestedTab) ? requestedTab : "profile";
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [supportMessages, setSupportMessages] = useState<SupportMessage[]>([]);
  const [activeTab, setActiveTab] = useState<DashboardTab>(initialTab);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(SIDEBAR_STATE_KEY) === "true";
  });
  const [selectedEnrollmentId, setSelectedEnrollmentId] = useState<number | null>(null);
  const [expandedSessionsByEnrollment, setExpandedSessionsByEnrollment] = useState<Record<number, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [messageDraft, setMessageDraft] = useState("");
  const [messageError, setMessageError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [phoneDraft, setPhoneDraft] = useState("");
  const [genderDraft, setGenderDraft] = useState<Gender>("unspecified");
  const [isPhoneEditing, setIsPhoneEditing] = useState(false);
  const [isProfileSaving, setIsProfileSaving] = useState(false);
  const [isAvatarUploading, setIsAvatarUploading] = useState(false);
  const [joiningSessionId, setJoiningSessionId] = useState<number | null>(null);
  const [avatarPreview, setAvatarPreview] = useState(
    "/images/default-avatar.png"
  );
  const [toast, setToast] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const avatarInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    const loadDashboard = async () => {
      setLoading(true);
      setLoadError("");
      try {
        const dashboardData = await fetchStudentDashboard();
        setDashboard(dashboardData);

        try {
          const supportData = await fetchSupportMessages();
          setSupportMessages(supportData);
        } catch {
          // Support messages are optional for first render; do not fail whole dashboard.
          setSupportMessages([]);
        }
      } catch (error) {
        if (isAxiosError(error) && error.response?.status === 401) {
          logout();
          return;
        }
        setDashboard(null);
        setLoadError(t("dashboardLoadError"));
      } finally {
        setLoading(false);
      }
    };

    void loadDashboard();
  }, [isAuthenticated, logout, t]);

  useEffect(() => {
    if (!dashboard) return;
    setPhoneDraft(dashboard.profile.phone ?? "");
    setGenderDraft((dashboard.profile.gender ?? "unspecified") as Gender);
    setAvatarPreview(
      dashboard.profile.avatar_url || "/images/default-avatar.png"
    );
    setIsPhoneEditing(false);
  }, [
    dashboard?.profile.phone,
    dashboard?.profile.gender,
    dashboard?.profile.avatar_url,
    dashboard,
  ]);

  useEffect(() => {
    if (!dashboard?.enrollments.length) {
      setSelectedEnrollmentId(null);
      return;
    }

    setSelectedEnrollmentId((current) => (
      current && dashboard.enrollments.some((enrollment) => enrollment.enrollmentId === current)
        ? current
        : null
    ));
  }, [dashboard]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth > 767) {
        setIsMobileMenuOpen(false);
      }
    };

    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(SIDEBAR_STATE_KEY, String(isSidebarCollapsed));
  }, [isSidebarCollapsed]);

  const applyProfileUpdate = (profile: StudentProfile) => {
    setDashboard((prev) => (prev ? { ...prev, profile } : prev));
    setPhoneDraft(profile.phone ?? "");
    setGenderDraft((profile.gender ?? "unspecified") as Gender);
    setAvatarPreview(profile.avatar_url || "/images/default-avatar.png");
  };

  const calendarEvents = useMemo(() => {
    if (!dashboard) return [];
    const preferredLanguage = dashboard.profile.preferred_language;
    const courseLabel = (
      course: DashboardResponse["enrollments"][number]["course"]
    ) => (preferredLanguage === "en" ? course.titleEn : course.titleDe);

    return dashboard.enrollments.flatMap((enrollment) =>
      enrollment.sessions.flatMap((session) => {
        const range = getCalendarEventRange(
          session.starts_at,
          session.ends_at
        );
        if (!range) return [];

        return [
          {
            id: String(session.id),
            title: `${courseLabel(enrollment.course)}: ${session.title}`,
            start: range.start,
            end: range.end,
            allDay: false,
            backgroundColor: session.is_completed ? "#3d6b57" : "#164a61",
            borderColor: session.is_completed ? "#3d6b57" : "#164a61",
          },
        ];
      })
    );
  }, [dashboard]);

  const microsoftCalendarUrl = useMemo(
    () =>
      buildExternalCalendarUrl("https://outlook.office.com/calendar/view/week", {
        login_hint: dashboard?.profile.email,
        prompt: "select_account",
        auth: "2",
      }),
    [dashboard?.profile.email],
  );

  const recordings = useMemo(() => {
    if (!dashboard) return [];
    const preferredLanguage = dashboard.profile.preferred_language;
    const courseLabel = (
      course: DashboardResponse["enrollments"][number]["course"]
    ) => (preferredLanguage === "en" ? course.titleEn : course.titleDe);

    return dashboard.enrollments.flatMap((enrollment) =>
      enrollment.sessions
        .filter((session) => session.recording_url)
        .map((session) => ({
          id: session.id,
          title: session.title,
          recordingUrl: session.recording_url ?? "",
          courseName: courseLabel(enrollment.course),
        }))
    );
  }, [dashboard]);

  const additionalMaterials = useMemo(() => {
    if (!dashboard) return [];
    const preferredLanguage = dashboard.profile.preferred_language;
    const courseLabel = (
      course: DashboardResponse["enrollments"][number]["course"]
    ) => (preferredLanguage === "en" ? course.titleEn : course.titleDe);

    return dashboard.enrollments
      .flatMap((enrollment) =>
        enrollment.materials.map((material) => ({
          ...material,
          courseName: courseLabel(enrollment.course),
        }))
      )
      .filter((material) => material.material_type !== "condition");
  }, [dashboard]);

  const conditionMaterials = useMemo(() => {
    if (!dashboard) return [];
    const preferredLanguage = dashboard.profile.preferred_language;
    const courseLabel = (
      course: DashboardResponse["enrollments"][number]["course"]
    ) => (preferredLanguage === "en" ? course.titleEn : course.titleDe);

    return dashboard.enrollments
      .flatMap((enrollment) =>
        enrollment.materials.map((material) => ({
          ...material,
          courseName: courseLabel(enrollment.course),
        }))
      )
      .filter((material) => material.material_type === "condition");
  }, [dashboard]);

  const activeTabTitle = useMemo(() => {
    const active = tabConfig.find((tab) => tab.id === activeTab);
    return active ? t(active.labelKey) : t("tabProfile");
  }, [activeTab, t]);

  const isProfileDirty = Boolean(
    dashboard &&
      (phoneDraft !== (dashboard.profile.phone ?? "") ||
        genderDraft !== (dashboard.profile.gender ?? "unspecified"))
  );

  const saveProfile = async () => {
    if (!dashboard || !isProfileDirty) return;

    setIsProfileSaving(true);
    try {
      const updatedProfile = await updateStudentProfile({
        phone: normalizePhoneInput(phoneDraft),
        gender: genderDraft,
      });
      applyProfileUpdate(updatedProfile);
      setToast({ type: "success", message: t("profileUpdateSuccess") });
    } catch (error) {
      setToast({
        type: "error",
        message: extractErrorMessage(error, t("profileUpdateError")),
      });
    } finally {
      setIsProfileSaving(false);
    }
  };

  const openAvatarPicker = () => {
    avatarInputRef.current?.click();
  };

  const onAvatarSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      setToast({ type: "error", message: t("avatarUnsupportedType") });
      event.target.value = "";
      return;
    }

    if (file.size > MAX_AVATAR_SIZE_BYTES) {
      setToast({ type: "error", message: t("avatarFileTooLarge") });
      event.target.value = "";
      return;
    }

    const previousAvatar = avatarPreview;
    const localPreviewUrl = URL.createObjectURL(file);
    setAvatarPreview(localPreviewUrl);

    setIsAvatarUploading(true);
    try {
      const updatedProfile = await updateStudentProfile({ avatar: file });
      applyProfileUpdate(updatedProfile);
      setToast({ type: "success", message: t("avatarUploadSuccess") });
    } catch (error) {
      setAvatarPreview(previousAvatar || "/images/default-avatar.png");
      setToast({
        type: "error",
        message: extractErrorMessage(error, t("avatarUploadError")),
      });
    } finally {
      URL.revokeObjectURL(localPreviewUrl);
      setIsAvatarUploading(false);
      if (avatarInputRef.current) avatarInputRef.current.value = "";
    }
  };

  const sendSupport = async () => {
    if (!messageDraft.trim()) return;
    try {
      const enrollmentId = dashboard?.enrollments[0]?.enrollmentId;
      const message = await createSupportMessage(messageDraft, enrollmentId);
      setSupportMessages((prev) => [message, ...prev]);
      setMessageDraft("");
      setMessageError("");
    } catch (error) {
      setMessageError(extractErrorMessage(error, t("supportError")));
    }
  };

  const handleJoinSession = async (session: {
    id: number;
    join_url?: string | null;
  }) => {
    if (!session.join_url) return;
    setJoiningSessionId(session.id);
    try {
      await markStudentSessionJoin(session.id);
    } catch (error) {
      setToast({
        type: "error",
        message: extractErrorMessage(error, t("joinTrackError")),
      });
    } finally {
      setJoiningSessionId(null);
      window.open(session.join_url, "_blank", "noopener,noreferrer");
    }
  };

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (loading) {
    return (
      <main className="dashboard-page">
        <p>{t("loading")}</p>
      </main>
    );
  }

  if (!dashboard) {
    return (
      <main className="dashboard-page">
        <p>{loadError || t("noData")}</p>
      </main>
    );
  }

  const primaryEnrollment = dashboard.enrollments[0];
  const selectedEnrollment = dashboard.enrollments.find(
    (enrollment) => enrollment.enrollmentId === selectedEnrollmentId,
  ) ?? null;
  const heroEnrollment = activeTab === "course"
    ? selectedEnrollment
    : primaryEnrollment;
  const primaryCourseTitle = heroEnrollment
    ? enrollmentCourseTitle(heroEnrollment, dashboard.profile.preferred_language)
    : "-";
  const heroSubtitle = activeTab === "course"
    ? (
      heroEnrollment
        ? `${primaryCourseTitle} · ${t("group")}: ${heroEnrollment.cohort.groupCode}`
        : "Select a course to view sessions, structure, and completion details."
    )
    : heroEnrollment
      ? `${primaryCourseTitle} · ${t("group")}: ${heroEnrollment.cohort.groupCode}`
      : dashboard.profile.email;

  return (
    <main className="dashboard-page">
      <div className="dashboard-page__layout">
        <aside className={`dashboard-page__sidebar ${isSidebarCollapsed ? "dashboard-page__sidebar--collapsed" : ""}`}>
          <div className="dashboard-page__brand-block">
            <div className="dashboard-page__brand-copy">
              <p className="dashboard-page__brand-eyebrow">{t("brand")}</p>
              <strong className="dashboard-page__brand-title">{t("studentWorkspace")}</strong>
            </div>
            <button
              type="button"
              className="dashboard-page__sidebar-toggle"
              onClick={() => setIsSidebarCollapsed((current) => !current)}
              aria-label={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              <SidebarToggleIcon collapsed={isSidebarCollapsed} />
            </button>
          </div>

          <div className="dashboard-page__student-card">
            <div className="dashboard-page__avatar-box">
              <img
                src={avatarPreview || "/images/default-avatar.png"}
                alt=""
                className="dashboard-page__avatar"
              />
              <button
                type="button"
                className="dashboard-page__avatar-upload"
                onClick={openAvatarPicker}
                aria-label={t("avatarUpload")}
                disabled={isAvatarUploading}
              >
                {isAvatarUploading ? "..." : "+"}
              </button>
              <input
                ref={avatarInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="dashboard-page__avatar-input"
                onChange={onAvatarSelected}
              />
            </div>

            <div className="dashboard-page__student-name">
              <p>{dashboard.profile.last_name || "-"}</p>
              <p>{dashboard.profile.first_name || dashboard.profile.email}</p>
            </div>
          </div>

          <nav
            className="dashboard-page__tabs"
            role="tablist"
            aria-label="Student cabinet sections"
          >
            {tabConfig.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={activeTab === tab.id ? "active" : ""}
                aria-label={t(tab.labelKey)}
                title={t(tab.labelKey)}
              >
                <span className="dashboard-page__tab-icon" aria-hidden="true">
                  {tab.icon}
                </span>
                <span className="dashboard-page__tab-label">{t(tab.labelKey)}</span>
              </button>
            ))}
            <button
              type="button"
              className="dashboard-page__sidebar-logout"
              onClick={logout}
              aria-label={t("logout")}
              title={t("logout")}
            >
              <span className="dashboard-page__tab-icon" aria-hidden="true">
                <LogoutIcon />
              </span>
              <span className="dashboard-page__tab-label">{t("logout")}</span>
            </button>
          </nav>

          <button
            type="button"
            className="dashboard-page__menu-toggle"
            onClick={() => setIsMobileMenuOpen((prev) => !prev)}
            aria-label="Toggle menu"
          >
            {isMobileMenuOpen ? "×" : "☰"}
          </button>
        </aside>

        <section className="dashboard-page__content">
          <header className="dashboard-page__hero">
            <div className="dashboard-page__hero-copy">
              <h1>{activeTabTitle}</h1>
              <p className="dashboard-page__hero-subtitle">{heroSubtitle}</p>
            </div>
            <div className="dashboard-page__hero-controls">
              <select
                className="dashboard-page__language-select"
                value={locale}
                onChange={(event) =>
                  setLocale(event.target.value as "de" | "en")
                }
                aria-label={t("profileLanguage")}
              >
                <option value="de">De</option>
                <option value="en">En</option>
              </select>
              <button
                type="button"
                className="dashboard-page__hero-chip dashboard-page__hero-chip--theme"
                onClick={toggleTheme}
                aria-label={
                  theme === "light" ? t("themeLight") : t("themeDark")
                }
              >
                {theme === "light" ? (
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 4a1 1 0 0 1 1 1v1.2a1 1 0 1 1-2 0V5a1 1 0 0 1 1-1Zm5.66 2.34a1 1 0 0 1 1.41 0l.84.85a1 1 0 1 1-1.41 1.41l-.85-.84a1 1 0 0 1 0-1.42ZM12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8Zm9 3a1 1 0 1 1 0 2h-1.2a1 1 0 0 1 0-2H21Zm-17.8 0a1 1 0 0 1 0 2H2a1 1 0 1 1 0-2h1.2Zm15.46 5.54a1 1 0 0 1 0 1.41l-.84.85a1 1 0 0 1-1.42-1.41l.85-.85a1 1 0 0 1 1.41 0ZM12 17.8a1 1 0 0 1 1 1V20a1 1 0 1 1-2 0v-1.2a1 1 0 0 1 1-1Zm-5.66-1.26a1 1 0 0 1 1.41 0l.85.85a1 1 0 0 1-1.41 1.41l-.85-.84a1 1 0 0 1 0-1.42Zm1.41-9.35a1 1 0 0 1 0 1.41l-.85.84A1 1 0 0 1 5.5 8.03l.84-.85a1 1 0 0 1 1.41 0Z" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M20.1 14.05A8.05 8.05 0 0 1 9.95 3.9a1 1 0 0 0-1.35-1.22A10 10 0 1 0 21.32 15.4a1 1 0 0 0-1.22-1.35Z" />
                  </svg>
                )}
              </button>
            </div>
          </header>

          <section className="dashboard-page__panel">
            {activeTab === "profile" ? (
              <section className="dashboard-page__section">
                <div className="dashboard-page__course-line">
                  <strong>{primaryCourseTitle}</strong>
                  {primaryEnrollment ? (
                    <span>
                      {t("group")}: {primaryEnrollment.cohort.groupCode}
                    </span>
                  ) : null}
                </div>

                <h2>{t("tabProfile")}</h2>

                <div className="dashboard-page__field-list">
                  <article className="dashboard-page__field-row">
                    <p className="dashboard-page__field-label">
                      {t("profileLastName")}
                    </p>
                    <p className="dashboard-page__field-value">
                      {dashboard.profile.last_name || "-"}
                    </p>
                  </article>
                  <article className="dashboard-page__field-row">
                    <p className="dashboard-page__field-label">
                      {t("profileFirstName")}
                    </p>
                    <p className="dashboard-page__field-value">
                      {dashboard.profile.first_name || "-"}
                    </p>
                  </article>
                  <article className="dashboard-page__field-row">
                    <p className="dashboard-page__field-label">
                      {t("profileEmail")}
                    </p>
                    <p className="dashboard-page__field-value">
                      {dashboard.profile.email}
                    </p>
                  </article>
                  <article className="dashboard-page__field-row dashboard-page__field-row--editable">
                    <p className="dashboard-page__field-label">
                      {t("profilePhone")}
                    </p>
                    <div className="dashboard-page__editable-field">
                      {isPhoneEditing ? (
                        <input
                          className="dashboard-page__field-input"
                          value={phoneDraft}
                          onChange={(event) =>
                            setPhoneDraft(
                              normalizePhoneInput(event.target.value)
                            )
                          }
                          placeholder={t("profilePhone")}
                          autoFocus
                          onBlur={() => setIsPhoneEditing(false)}
                          inputMode="tel"
                          autoComplete="tel"
                          aria-label={t("profilePhone")}
                        />
                      ) : (
                        <p className="dashboard-page__field-value">
                          {phoneDraft || "-"}
                        </p>
                      )}
                      <button
                        type="button"
                        className="dashboard-page__edit-icon"
                        aria-label={`Edit ${t("profilePhone")}`}
                        onClick={() => setIsPhoneEditing(true)}
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path d="m4 15.5 9.7-9.7a2.1 2.1 0 0 1 3 0l1.5 1.5a2.1 2.1 0 0 1 0 3L8.5 20H4v-4.5Zm2 2h1.7l8.9-8.9-1.7-1.7L6 15.8v1.7Z" />
                        </svg>
                      </button>
                    </div>
                  </article>
                  <article className="dashboard-page__field-row dashboard-page__field-row--editable">
                    <p className="dashboard-page__field-label">
                      {t("profileGender")}
                    </p>

                    <div className="dashboard-page__editable-field">
                      <select
                        className="dashboard-page__field-select"
                        value={genderDraft}
                        onChange={(event) =>
                          setGenderDraft(event.target.value as Gender)
                        }
                        aria-label={t("profileGender")}
                      >
                        <option value="unspecified">
                          {t("genderUnspecified")}
                        </option>
                        <option value="female">{t("genderFemale")}</option>
                        <option value="male">{t("genderMale")}</option>
                        <option value="diverse">{t("genderDiverse")}</option>
                      </select>
                    </div>
                  </article>

                  <article className="dashboard-page__field-row">
                    <p className="dashboard-page__field-label">
                      {t("profileLanguage")}
                    </p>
                    <p className="dashboard-page__field-value">
                      {dashboard.profile.preferred_language.toUpperCase()}
                    </p>
                  </article>
                  <article className="dashboard-page__field-row">
                    <p className="dashboard-page__field-label">
                      {t("nextSession")}
                    </p>
                    <p className="dashboard-page__field-value">
                      {formatDateTime(dashboard.nextSessionAt)}
                    </p>
                  </article>
                </div>

                <div className="dashboard-page__profile-actions">
                  <button
                    type="button"
                    onClick={saveProfile}
                    disabled={!isProfileDirty || isProfileSaving}
                  >
                    {isProfileSaving ? t("profileSaving") : t("profileSave")}
                  </button>
                </div>
              </section>
            ) : null}

            {activeTab === "course" ? (
              <section className="dashboard-page__section">
                <h2>{t("tabCourse")}</h2>
                <div className="dashboard-page__course-accordion">
                  {dashboard.enrollments.map((enrollment) => {
                    const courseTitle = enrollmentCourseTitle(
                      enrollment,
                      dashboard.profile.preferred_language,
                    );
                    const courseModules =
                      enrollment.courseStructure?.modules?.length
                        ? enrollment.courseStructure.modules
                        : deriveModulesFromLessonPlan(enrollment.lessonPlan);
                    const lessonsCount = courseModules.reduce(
                      (sum, module) => sum + module.lessons.length,
                      0,
                    );
                    const isSessionsExpanded = expandedSessionsByEnrollment[enrollment.enrollmentId] ?? false;
                    const highlightedSession = resolveHighlightedSession(enrollment.sessions, enrollment.nextSessionAt);
                    const isSelected =
                      enrollment.enrollmentId === selectedEnrollment?.enrollmentId;
                    return (
                    <article
                      key={enrollment.enrollmentId}
                      className={`dashboard-page__course-accordion-item ${isSelected ? "is-open" : ""}`}
                    >
                        <button
                          type="button"
                          className="dashboard-page__course-accordion-trigger"
                          onClick={() =>
                            setSelectedEnrollmentId((current) => (
                              current === enrollment.enrollmentId ? null : enrollment.enrollmentId
                            ))
                          }
                          aria-expanded={isSelected}
                        >
                        <div className="dashboard-page__course-accordion-main">
                          <strong className="dashboard-page__course-accordion-title">
                            {courseTitle}
                          </strong>
                          <div className="dashboard-page__course-accordion-meta">
                            <span className="dashboard-page__course-accordion-meta-item">
                              {t("group")}: {enrollment.cohort.groupCode}
                            </span>
                            <span className="dashboard-page__course-accordion-meta-item">
                              {lessonsCount} lesson{lessonsCount === 1 ? "" : "s"}
                            </span>
                            <span className="dashboard-page__course-accordion-meta-item">
                              {enrollment.completion.progressPercent}% complete
                            </span>
                          </div>
                        </div>

                        <div className="dashboard-page__course-accordion-side">
                          <span
                            className={`dashboard-page__course-structure-status dashboard-page__course-structure-status--${
                              enrollment.completion.status === "completed"
                                ? "completed"
                                : enrollment.status === "active"
                                  ? "active"
                                  : "locked"
                            }`}
                          >
                            <span className="dashboard-page__course-structure-status-dot" aria-hidden="true" />
                            {enrollment.status}
                          </span>
                          <span
                            className={`dashboard-page__course-accordion-chevron ${isSelected ? "is-open" : ""}`}
                            aria-hidden="true"
                          >
                            ▾
                          </span>
                        </div>
                      </button>

                      {isSelected ? (
                        <div className="dashboard-page__course-accordion-panel">
                      <h3>{courseTitle}</h3>
                      {enrollment.course.audiences?.length ? (
                        <div className="dashboard-page__role-badges">
                          {(enrollment.course.audiences ?? []).map((audience) => (
                            <span
                              key={audience.id}
                              className={`dashboard-page__role-badge ${courseAudienceBadgeClass(audience.slug)}`}
                            >
                              {audience.shortLabel || audience.name}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      <div className="dashboard-page__course-detail-meta">
                        <span>
                          <strong>{t("group")}:</strong> {enrollment.cohort.groupCode} - {enrollment.cohort.groupName}
                        </span>
                        <span>
                          <strong>{t("attendance")}:</strong> {enrollment.attendancePercent}%
                        </span>
                        <span>
                          <strong>{t("status")}:</strong> {enrollment.status}
                        </span>
                        <span>
                          <strong>{t("nextSession")}:</strong> {formatDateTime(enrollment.nextSessionAt)}
                        </span>
                      </div>

                      <section className="dashboard-page__completion-box">
                        <div className="dashboard-page__completion-head">
                          <span>Completion evidence</span>
                          <strong className={`dashboard-page__completion-status ${completionStatusClass(enrollment.completion.status)}`}>
                            {enrollment.completion.statusLabel}
                          </strong>
                        </div>
                        <div className="dashboard-page__completion-metrics">
                          <span>{enrollment.completion.progressPercent}% course progress</span>
                          <span>{Math.round(enrollment.completion.attendancePercent)}% attendance</span>
                          <span>
                            Rule: {enrollment.completion.rule.requiredCompletionPercent}% / {enrollment.completion.rule.requiredAttendancePercent}%
                          </span>
                        </div>
                        <div className="dashboard-page__completion-meta">
                          <span>
                            Attestation: {enrollment.completion.attestation ? `signed by ${enrollment.completion.attestation.fullName}` : enrollment.completion.rule.requiresAttestation ? "pending" : "optional"}
                          </span>
                          {enrollment.completion.evidence ? (
                            <span>Evidence code: {enrollment.completion.evidence.evidenceCode.slice(0, 8).toUpperCase()}</span>
                          ) : (
                            <span>
                              {enrollment.completion.status === "ready_for_attestation"
                                ? "Open the final lesson summary to confirm completion."
                                : "Continue lessons to unlock course evidence."}
                            </span>
                          )}
                        </div>
                      </section>

                      <div className="dashboard-page__sessions">
                        <div className="dashboard-page__sessions-head">
                          <h4>{t("sessions")}</h4>
                          <button
                            type="button"
                            className="dashboard-page__sessions-toggle"
                            onClick={() =>
                              setExpandedSessionsByEnrollment((current) => ({
                                ...current,
                                [enrollment.enrollmentId]: !isSessionsExpanded,
                              }))
                            }
                            aria-expanded={isSessionsExpanded}
                          >
                            <span>{isSessionsExpanded ? "Show next only" : "Show all sessions"}</span>
                            <span className={`dashboard-page__lesson-chevron ${isSessionsExpanded ? "is-open" : ""}`} aria-hidden="true">
                              ▾
                            </span>
                          </button>
                        </div>

                        {!isSessionsExpanded && highlightedSession ? (() => {
                          const visualState = resolveStudentSessionVisualState(highlightedSession, enrollment.nextSessionAt);
                          const isCompletedForUi = isStudentSessionCompleted(highlightedSession);
                          const showRecordingLink = isCompletedForUi && !!highlightedSession.recording_url;
                          const showJoinButton = !isCompletedForUi && !!highlightedSession.join_url;

                          return (
                            <article
                              className={`dashboard-page__session-summary dashboard-page__session-summary--${visualState}`}
                            >
                              <div className="dashboard-page__session-summary-copy">
                                <span className="dashboard-page__field-label">Next highlighted session</span>
                                <strong>{highlightedSession.title}</strong>
                                <p>{formatDateTime(highlightedSession.starts_at)}</p>
                              </div>
                              <div className="dashboard-page__session-summary-meta">
                                <span
                                  className={`dashboard-page__status-chip ${
                                    isCompletedForUi
                                      ? "dashboard-page__status-chip--completed"
                                      : "dashboard-page__status-chip--planned"
                                  }`}
                                >
                                  {isCompletedForUi ? t("sessionCompleted") : t("sessionPlanned")}
                                </span>
                                {showRecordingLink ? (
                                  <a
                                    href={highlightedSession.recording_url ?? undefined}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    {t("openRecording")}
                                  </a>
                                ) : null}
                                {showJoinButton ? (
                                  <button
                                    type="button"
                                    className={`dashboard-page__table-link-button ${
                                      visualState === "next" ? "dashboard-page__table-link-button--next" : ""
                                    }`}
                                    onClick={() => void handleJoinSession(highlightedSession)}
                                    disabled={joiningSessionId === highlightedSession.id}
                                  >
                                    {joiningSessionId === highlightedSession.id ? t("loading") : t("openJoin")}
                                  </button>
                                ) : null}
                              </div>
                            </article>
                          );
                        })() : null}

                        {isSessionsExpanded ? (
                          <div className="dashboard-page__table-wrap">
                            <table className="dashboard-page__table">
                              <thead>
                                <tr>
                                  <th>{t("sessionTime")}</th>
                                  <th>{t("sessionDescription")}</th>
                                  <th>{t("status")}</th>
                                  <th>{t("sessionAction")}</th>
                                </tr>
                              </thead>
                              <tbody>
                                {enrollment.sessions.map((session) => {
                                  const visualState = resolveStudentSessionVisualState(
                                    session,
                                    enrollment.nextSessionAt
                                  );
                                  const isCompletedForUi = isStudentSessionCompleted(session);
                                  const showRecordingLink =
                                    isCompletedForUi && !!session.recording_url;
                                  const showJoinButton =
                                    !isCompletedForUi && !!session.join_url;

                                  return (
                                  <tr
                                    key={session.id}
                                    className={`dashboard-page__session-row dashboard-page__session-row--${visualState}`}
                                  >
                                    <td>{formatDateTime(session.starts_at)}</td>
                                    <td>{session.title}</td>
                                    <td>
                                      <span
                                        className={`dashboard-page__status-chip ${
                                          isCompletedForUi
                                            ? "dashboard-page__status-chip--completed"
                                            : "dashboard-page__status-chip--planned"
                                        }`}
                                      >
                                        {isCompletedForUi
                                          ? t("sessionCompleted")
                                          : t("sessionPlanned")}
                                      </span>
                                    </td>
                                    <td>
                                      {showRecordingLink ? (
                                        <a
                                          href={session.recording_url ?? undefined}
                                          target="_blank"
                                          rel="noreferrer"
                                        >
                                          {t("openRecording")}
                                        </a>
                                      ) : null}
                                      {showJoinButton ? (
                                        <button
                                          type="button"
                                          className={`dashboard-page__table-link-button ${
                                            visualState === "next"
                                              ? "dashboard-page__table-link-button--next"
                                              : ""
                                          }`}
                                          onClick={() => void handleJoinSession(session)}
                                          disabled={joiningSessionId === session.id}
                                        >
                                          {joiningSessionId === session.id
                                            ? t("loading")
                                            : t("openJoin")}
                                        </button>
                                      ) : null}
                                      {(isCompletedForUi &&
                                        !session.recording_url) ||
                                      (!isCompletedForUi && !session.join_url)
                                        ? "-"
                                        : null}
                                    </td>
                                  </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        ) : null}
                      </div>

                      <CourseStructureTree
                        courseTitle={
                          courseTitle
                        }
                        modules={courseModules}
                        emptyMessage="This course does not have a structured module outline yet."
                      />
                        </div>
                      ) : null}
                    </article>
                    );
                  })}
                </div>
              </section>
            ) : null}

            {activeTab === "calendar" ? (
              <section className="dashboard-page__section">
                <div className="dashboard-page__calendar-switcher" aria-label={t("tabCalendar")}>
                  <button type="button" className="dashboard-page__calendar-switcher-button dashboard-page__calendar-switcher-button--active">
                    {t("calendarInternal")}
                  </button>
                  <a
                    className="dashboard-page__calendar-switcher-button"
                    href={microsoftCalendarUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t("calendarMicrosoft")}
                  </a>
                </div>
                <h2>{t("tabCalendar")}</h2>
                <FullCalendar
                  plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
                  initialView="timeGridWeek"
                  events={calendarEvents}
                  height="auto"
                  timeZone="Europe/Berlin"
                  slotMinTime="09:00:00"
                  slotMaxTime="22:00:00"
                  scrollTime="09:00:00"
                  locale={dashboard.profile.preferred_language}
                  headerToolbar={{
                    left: "prev,next today",
                    center: "title",
                    right: "dayGridMonth,timeGridWeek,timeGridDay",
                  }}
                />
              </section>
            ) : null}

            {activeTab === "materials" ? (
              <section className="dashboard-page__section">
                <h2>{t("tabMaterials")}</h2>

                <div className="dashboard-page__lesson-plan">
                  <h3>Structured modules</h3>
                  {dashboard.enrollments.every((enrollment) => enrollment.lessonPlan.length === 0) ? (
                    <p>{t("noData")}</p>
                  ) : null}
                  {dashboard.enrollments.map((enrollment) => (
                    <article key={`materials_${enrollment.enrollmentId}`} className="dashboard-page__lesson-card">
                      <header className="dashboard-page__lesson-card-header">
                        <div>
                          <strong>
                            {dashboard.profile.preferred_language === "en"
                              ? enrollment.course.titleEn
                              : enrollment.course.titleDe}
                          </strong>
                          <p>
                            {t("group")}: {enrollment.cohort.groupCode}
                          </p>
                        </div>
                        <span>{enrollment.lessonPlan.length} lessons</span>
                      </header>
                      {enrollment.lessonPlan.length === 0 ? (
                        <p className="dashboard-page__lesson-empty">
                          This course does not have a structured module library yet.
                        </p>
                      ) : null}
                      <div className="dashboard-page__lesson-sections">
                        {enrollment.lessonPlan.map((lesson) => (
                          <section key={lesson.id} className="dashboard-page__lesson-section">
                            <div className="dashboard-page__lesson-section-header">
                              <strong>{lesson.title}</strong>
                              <span>{lesson.sections.reduce((count, section) => count + section.items.length, 0)} assets</span>
                            </div>
                            <div className="dashboard-page__lesson-items">
                              {lesson.sections.flatMap((section) =>
                                section.items.map((item) => {
                                  const itemLink = resolveLessonItemLink(item);
                                  return (
                                    <article key={`${section.id}_${item.id}`} className="dashboard-page__lesson-item">
                                      <div>
                                        <strong>{item.title}</strong>
                                        <p>{section.title || lessonSectionLabel(section.sectionType)}</p>
                                      </div>
                                      <div className="dashboard-page__lesson-item-meta">
                                        <span>{item.assetType}</span>
                                        {itemLink ? (
                                          <a href={itemLink} target="_blank" rel="noreferrer">
                                            Open
                                          </a>
                                        ) : null}
                                      </div>
                                    </article>
                                  );
                                })
                              )}
                            </div>
                          </section>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>

                <h3>{t("additionalMaterials")}</h3>
                <div className="dashboard-page__list">
                  {additionalMaterials.length === 0 ? (
                    <p>{t("noData")}</p>
                  ) : null}
                  {additionalMaterials.map((material) => (
                    <article
                      key={`${material.id}_${material.courseName}`}
                      className="dashboard-page__list-item"
                    >
                      <h3>{material.title}</h3>
                      <p>{material.courseName}</p>
                      <p>{material.description}</p>
                      {material.link_url ? (
                        <a
                          href={material.link_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {t("openResource")}
                        </a>
                      ) : null}
                    </article>
                  ))}
                </div>

                <h3>{t("courseConditions")}</h3>
                <div className="dashboard-page__list">
                  {conditionMaterials.length === 0 ? (
                    <p>{t("noData")}</p>
                  ) : null}
                  {conditionMaterials.map((material) => (
                    <article
                      key={`${material.id}_${material.courseName}_condition`}
                      className="dashboard-page__list-item"
                    >
                      <h3>{material.title}</h3>
                      <p>{material.courseName}</p>
                      <p>{material.description}</p>
                      {material.link_url ? (
                        <a
                          href={material.link_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {t("openResource")}
                        </a>
                      ) : null}
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            {activeTab === "recordings" ? (
              <section className="dashboard-page__section">
                <h2>{t("tabRecordings")}</h2>
                <div className="dashboard-page__list">
                  {recordings.length === 0 ? <p>{t("noData")}</p> : null}
                  {recordings.map((recording) => (
                    <article
                      key={recording.id}
                      className="dashboard-page__list-item"
                    >
                      <h3>{recording.title}</h3>
                      <p>{recording.courseName}</p>
                      <a
                        href={recording.recordingUrl}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {t("openRecording")}
                      </a>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            {activeTab === "app" ? (
              <section className="dashboard-page__section">
                <AppsTab email={dashboard.profile.email} />
              </section>
            ) : null}

            {activeTab === "support" ? (
              <section className="dashboard-page__section">
                <h2>{t("tabSupport")}</h2>
                <div className="dashboard-page__support-box">
                  <div className="dashboard-page__support-list">
                    {supportMessages.map((item) => (
                      <article
                        className="dashboard-page__support-item"
                        key={item.id}
                      >
                        <p>{item.message}</p>
                        <span>{item.sender_type}</span>
                      </article>
                    ))}
                  </div>
                  <textarea
                    rows={3}
                    value={messageDraft}
                    onChange={(event) => setMessageDraft(event.target.value)}
                    placeholder={t("supportPlaceholder")}
                  />
                  <button type="button" onClick={sendSupport}>
                    {t("send")}
                  </button>
                  {messageError ? (
                    <p className="dashboard-page__error">{messageError}</p>
                  ) : null}
                </div>
              </section>
            ) : null}

            {activeTab === "information" ? (
              <section className="dashboard-page__section">
                <h2>{t("tabInformation")}</h2>
                <InformationTab />
              </section>
            ) : null}
          </section>
        </section>
      </div>

      {isMobileMenuOpen ? (
        <div className="dashboard-page__mobile-overlay">
          <div className="dashboard-page__mobile-menu">
            {tabConfig.map((tab) => (
              <button
                key={`mobile_${tab.id}`}
                type="button"
                className={`dashboard-page__mobile-link ${
                  activeTab === tab.id ? "active" : ""
                }`}
                onClick={() => {
                  setActiveTab(tab.id);
                  setIsMobileMenuOpen(false);
                }}
              >
                {t(tab.labelKey)}
              </button>
            ))}
            <button
              type="button"
              className="dashboard-page__mobile-link dashboard-page__mobile-link--logout"
              onClick={logout}
            >
              {t("logout")}
            </button>
          </div>
        </div>
      ) : null}

      {toast ? (
        <NotificationToast
          type={toast.type}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      ) : null}
    </main>
  );
};
