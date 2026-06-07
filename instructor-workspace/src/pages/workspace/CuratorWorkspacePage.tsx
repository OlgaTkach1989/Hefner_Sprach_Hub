import { useEffect, useState, type FormEvent } from "react";
import { NavLink } from "react-router-dom";

import { getCsrfToken } from "@/api/authStorage";
import { useAuth } from "@/context/AuthContext";
import {
  useGetTeacherWorkspaceQuery,
  useSubmitTeacherFeedbackMutation,
} from "@/bll/workspace/workspace.service";
import type {
  TeacherWorkspaceCourse,
  TeacherWorkspaceCourseModule,
  TeacherWorkspaceLesson,
  TeacherWorkspaceLessonSectionItem,
  TeacherWorkspaceMaterial,
  TeacherWorkspaceRecording,
  TeacherWorkspaceResponse,
} from "@/bll/workspace/workspace.type";
import OnlinePage from "@/pages/Online/OnlinePage";
import { CuratorHomeSection } from "./CuratorHomeSection";
import { CuratorInformationSection } from "./CuratorInformationSection";
import { formatDateTime, formatPercent, resolveApiErrorMessage } from "./workspaceShared";
import "./CuratorWorkspacePage.css";

type WorkspaceSection = "home" | "documents" | "portfolio" | "online" | "calendar" | "information" | "feedback";

type WorkspacePageProps = {
  section: WorkspaceSection;
};

type NavItem = {
  id: WorkspaceSection;
  label: string;
  href: string;
  icon: JSX.Element;
};

const SIDEBAR_STATE_KEY = "learning-hub.instructor.sidebar-collapsed";

const HomeIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 4.2 4 10.4V20h5.4v-5.1h5.2V20H20v-9.6L12 4.2Z" />
  </svg>
);

const DocumentsIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M7 3h7l5 5v13H7V3Zm7 1.6V9h4.4L14 4.6ZM9 12h6v1.5H9V12Zm0 3h6v1.5H9V15Z" />
  </svg>
);

const PortfolioIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M5 6h14a2 2 0 0 1 2 2v9H3V8a2 2 0 0 1 2-2Zm3-3h8v2H8V3Zm-5 16h18v2H3v-2Z" />
  </svg>
);

const OnlineIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 5h16a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-6l-2 3-2-3H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Zm3 3v6h10V8H7Zm11 0h2v6h-2V8Z" />
  </svg>
);

const CalendarIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M7 2h2v3h6V2h2v3h3a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3V2Zm13 8H4v10h16V10ZM4 7v1h16V7H4Zm3 5h3v3H7v-3Zm5 0h3v3h-3v-3Z" />
  </svg>
);

const InformationIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20Zm-.75 6h1.5V6.5h-1.5V8Zm0 9h1.5v-6h-1.5v6Z" />
  </svg>
);

const FeedbackIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 4h16v11H7l-3 3V4Zm4 4v1.5h8V8H8Zm0 3v1.5h5V11H8Z" />
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

const SECTION_META: Record<WorkspaceSection, { title: string; subtitle: string }> = {
  home: {
    title: "Home",
    subtitle: "Review and update your instructor profile, contact details, and current teaching footprint from one place.",
  },
  documents: {
    title: "Courses",
    subtitle: "Review assigned course structure, open lesson materials, and generate lesson delivery documents.",
  },
  portfolio: {
    title: "Delivery",
    subtitle: "Review assigned courses, cohort footprint, and recording coverage across your teaching scope.",
  },
  online: {
    title: "Online",
    subtitle: "Open live sessions, end classes, and monitor attendance for the groups assigned to you.",
  },
  calendar: {
    title: "Calendar",
    subtitle: "Review scheduled sessions in the academy calendar and open the same schedule in Outlook Calendar.",
  },
  information: {
    title: "Information",
    subtitle: "Read academy rules, safety guidance, current updates, and working context for the instructor role.",
  },
  feedback: {
    title: "Feedback",
    subtitle: "Escalate blockers, request content updates, and send operational notes to the academy team.",
  },
};

const groupMaterials = (materials: TeacherWorkspaceMaterial[]) => {
  const resources: TeacherWorkspaceMaterial[] = [];
  const conditions: TeacherWorkspaceMaterial[] = [];
  const recordings: TeacherWorkspaceMaterial[] = [];

  materials.forEach((item) => {
    if (item.materialType === "recording") {
      recordings.push(item);
      return;
    }
    if (item.materialType === "condition") {
      conditions.push(item);
      return;
    }
    resources.push(item);
  });

  return { resources, conditions, recordings };
};

const MaterialsList = ({ items, emptyMessage }: { items: TeacherWorkspaceMaterial[]; emptyMessage: string }) => {
  if (items.length === 0) {
    return <p className="curator-workspace__empty-copy">{emptyMessage}</p>;
  }

  return (
    <div className="curator-workspace__list-grid">
      {items.map((item) => (
        <article key={item.id} className="curator-workspace__list-card">
          <span className="curator-workspace__badge">{item.materialType}</span>
          <h3>{item.title}</h3>
          <p>{item.description || "No description provided yet."}</p>
          <div className="curator-workspace__meta-stack">
            <span>{item.courseTitleEn || item.courseTitleDe}</span>
            <span>{item.language.toUpperCase()}</span>
          </div>
          {item.linkUrl ? (
            <a className="curator-workspace__inline-link" href={item.linkUrl} target="_blank" rel="noreferrer">
              Open document
            </a>
          ) : null}
        </article>
      ))}
    </div>
  );
};

const resolveTeacherLessonItemLink = (
  item: TeacherWorkspaceLesson["sections"][number]["items"][number]
) => item.externalUrl || item.fileUrl || item.trainingContent?.sourceUrl || "";

const teacherActivityLabel = (activityType?: "video" | "text" | "quiz" | "assignment") => {
  if (activityType === "video") return "Video";
  if (activityType === "quiz") return "Quiz";
  if (activityType === "assignment") return "Assignment";
  return "Text";
};

const deriveTeacherModulesFromLessonPlans = (
  lessonPlansByCourse: Record<number, TeacherWorkspaceLesson[]>
): Record<number, TeacherWorkspaceCourseModule[]> => {
  const result: Record<number, TeacherWorkspaceCourseModule[]> = {};
  Object.entries(lessonPlansByCourse).forEach(([courseId, lessons]) => {
    const moduleMap = new Map<string, TeacherWorkspaceCourseModule>();
    lessons.forEach((lesson, index) => {
      const title = lesson.moduleTitle || "Module 1 (Week 1)";
      const key = `${lesson.moduleId ?? "legacy"}:${title}`;
      if (!moduleMap.has(key)) {
        moduleMap.set(key, {
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
      const module = moduleMap.get(key);
      if (!module) return;
      module.lessons.push(lesson);
      module.lessonsCount += 1;
      module.itemsCount += lesson.sections.reduce((count, section) => count + section.items.length, 0);
    });
    result[Number(courseId)] = [...moduleMap.values()].sort((left, right) => left.sortOrder - right.sortOrder);
  });
  return result;
};

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const markdownToHtml = (body: string) => {
  const blocks = body
    .split(/\n\s*\n/g)
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks
    .map((block) => {
      if (/^#{1,6}\s/.test(block)) {
        const level = Math.min(block.match(/^#+/)?.[0].length ?? 1, 6);
        return `<h${level}>${escapeHtml(block.replace(/^#{1,6}\s+/, ""))}</h${level}>`;
      }

      const listRows = block
        .split("\n")
        .map((row) => row.trim())
        .filter(Boolean);

      if (listRows.length > 0 && listRows.every((row) => row.startsWith("- "))) {
        return `<ul>${listRows.map((row) => `<li>${escapeHtml(row.slice(2))}</li>`).join("")}</ul>`;
      }

      return `<p>${escapeHtml(block)}</p>`;
    })
    .join("");
};

const renderTeacherMarkdownBlocks = (body: string) => {
  const blocks = body
    .split(/\n\s*\n/g)
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks.map((block, index) => {
    if (/^#{1,6}\s/.test(block)) {
      return (
        <h4 key={`${block}_${index}`} className="curator-workspace__resource-heading">
          {block.replace(/^#{1,6}\s+/, "")}
        </h4>
      );
    }

    const listRows = block
      .split("\n")
      .map((row) => row.trim())
      .filter(Boolean);

    if (listRows.length > 0 && listRows.every((row) => row.startsWith("- "))) {
      return (
        <ul key={`${block}_${index}`} className="curator-workspace__resource-list">
          {listRows.map((row) => (
            <li key={row}>{row.slice(2)}</li>
          ))}
        </ul>
      );
    }

    return (
      <p key={`${block}_${index}`} className="curator-workspace__resource-copy">
        {block}
      </p>
    );
  });
};

const isTeacherPdfUrl = (value: string) => /\.pdf($|\?)/i.test(value);
const isTeacherDirectVideoUrl = (value: string) => /\.(mp4|webm|ogg)($|\?)/i.test(value);

const resolveTeacherVideoEmbedUrl = (value: string) => {
  if (!value) return "";
  const youtubeWatchMatch = value.match(/[?&]v=([^&]+)/);
  if (value.includes("youtube.com/watch") && youtubeWatchMatch?.[1]) {
    return `https://www.youtube.com/embed/${youtubeWatchMatch[1]}`;
  }
  const youtubeShortMatch = value.match(/youtu\.be\/([^?&]+)/);
  if (youtubeShortMatch?.[1]) {
    return `https://www.youtube.com/embed/${youtubeShortMatch[1]}`;
  }
  return value;
};

const teacherModuleKeyOf = (courseId: number, module: TeacherWorkspaceCourseModule, moduleIndex: number) =>
  `course_${courseId}_module_${module.id ?? moduleIndex}_${module.sortOrder}`;

const teacherLessonKeyOf = (moduleKey: string, lesson: TeacherWorkspaceLesson) => `${moduleKey}_lesson_${lesson.id}_${lesson.sortOrder}`;

const resolveTeacherTrainingBaseUrl = () => {
  const configuredBaseUrl = import.meta.env.VITE_ONLINE_API_BASE_URL ?? "/api/online";
  const normalized = configuredBaseUrl.replace(/\/+$/, "");
  if (normalized.endsWith("/online")) {
    return `${normalized.slice(0, -"/online".length)}/training`;
  }
  return `${normalized}/training`;
};

const formatTeacherScheduleValue = (value?: string | null, options?: Intl.DateTimeFormatOptions) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    ...options,
  }).format(parsed);
};

const formatTeacherLessonSchedule = (lesson: TeacherWorkspaceLesson) => {
  if (!lesson.startsAt) return "";
  const startLabel = formatTeacherScheduleValue(lesson.startsAt);
  const endLabel = formatTeacherScheduleValue(lesson.endsAt, { hour: "2-digit", minute: "2-digit" });
  const groupLabel = lesson.groupName || lesson.groupCode || "";
  const scheduleLabel = endLabel ? `${startLabel} - ${endLabel}` : startLabel;
  return groupLabel ? `${scheduleLabel} · ${groupLabel}` : scheduleLabel;
};

const formatTeacherModuleSchedule = (module: TeacherWorkspaceCourseModule) => {
  if (!module.startsAt) return "";
  const startDate = new Date(module.startsAt);
  const endDate = module.endsAt ? new Date(module.endsAt) : null;
  if (Number.isNaN(startDate.getTime())) return "";
  const startLabel = formatTeacherScheduleValue(module.startsAt);
  const endLabel =
    endDate && !Number.isNaN(endDate.getTime())
      ? formatTeacherScheduleValue(module.endsAt, {
          day: "2-digit",
          month: "short",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
      : "";
  const groupLabel = module.groupName || module.groupCode || "";
  const scheduleLabel = endLabel ? `${startLabel} - ${endLabel}` : startLabel;
  return groupLabel ? `${scheduleLabel} · ${groupLabel}` : scheduleLabel;
};

const parseTeacherDateValue = (value?: string | null) => {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

const compactTeacherGroupLabel = (value?: string | null) => {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) return "";
  const parts = trimmed
    .split(" - ")
    .map((part) => part.trim())
    .filter(Boolean);
  return parts[parts.length - 1] || trimmed;
};

const formatTeacherShortDate = (value?: string | null) => {
  const parsed = parseTeacherDateValue(value);
  if (!parsed) return "";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(parsed);
};

const formatTeacherDurationShort = (startValue?: string | null, endValue?: string | null) => {
  const start = parseTeacherDateValue(startValue);
  const end = parseTeacherDateValue(endValue);
  if (!start || !end) return "";
  const diffMinutes = Math.max(0, Math.round((end.getTime() - start.getTime()) / 60000));
  if (diffMinutes <= 0) return "";
  const hours = Math.floor(diffMinutes / 60);
  const minutes = diffMinutes % 60;
  if (hours > 0 && minutes > 0) return `${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h`;
  return `${minutes}m`;
};

const formatTeacherLessonScheduleCompact = (lesson: TeacherWorkspaceLesson) => {
  const parts = [
    formatTeacherShortDate(lesson.startsAt),
    formatTeacherDurationShort(lesson.startsAt, lesson.endsAt),
  ].filter(Boolean);
  return parts.join(" • ");
};

const formatTeacherModuleScheduleCompact = (module: TeacherWorkspaceCourseModule) => {
  const startLabel = formatTeacherShortDate(module.startsAt);
  const endLabel = formatTeacherShortDate(module.endsAt);
  if (startLabel && endLabel && startLabel !== endLabel) {
    return `${startLabel} - ${endLabel}`;
  }
  return startLabel || endLabel;
};

type TeacherDeliveryStatusTone = "active" | "scheduled" | "completed";

const resolveTeacherLessonDeliveryStatus = (
  lesson: TeacherWorkspaceLesson
): { tone: TeacherDeliveryStatusTone; label: string } => {
  const normalizedStatus = String(lesson.sessionStatus ?? "").trim().toLowerCase();
  if (normalizedStatus === "live") return { tone: "active", label: "Live" };
  if (normalizedStatus === "ended" || normalizedStatus === "completed") {
    return { tone: "completed", label: "Completed" };
  }
  if (normalizedStatus === "scheduled" || normalizedStatus === "planned") {
    return { tone: "scheduled", label: "Scheduled" };
  }

  const now = Date.now();
  const start = parseTeacherDateValue(lesson.startsAt);
  const end = parseTeacherDateValue(lesson.endsAt);
  if (start && start.getTime() > now) {
    return { tone: "scheduled", label: "Scheduled" };
  }
  if (end && end.getTime() < now) {
    return { tone: "completed", label: "Completed" };
  }
  return { tone: "active", label: "Active" };
};

const resolveTeacherModuleDeliveryStatus = (
  module: TeacherWorkspaceCourseModule
): { tone: TeacherDeliveryStatusTone; label: string } => {
  if (module.lessons.length === 0) {
    return module.isActive
      ? { tone: "active", label: "Active" }
      : { tone: "scheduled", label: "Prepared" };
  }

  const lessonStatuses = module.lessons.map((lesson) => resolveTeacherLessonDeliveryStatus(lesson).tone);
  if (lessonStatuses.every((status) => status === "completed")) {
    return { tone: "completed", label: "Completed" };
  }
  if (lessonStatuses.some((status) => status === "active")) {
    return { tone: "active", label: "Active" };
  }
  return { tone: "scheduled", label: "Prepared" };
};

type TeacherLessonResourceKind = "presentation" | "quiz" | "video" | "notebook";

type TeacherLessonResource = {
  key: string;
  kind: TeacherLessonResourceKind;
  title: string;
  subtitle: string;
  item?: TeacherWorkspaceLessonSectionItem | null;
};

type TeacherResourceModalState = {
  title: string;
  subtitle: string;
  embedUrl: string;
  externalUrl: string;
  directVideo: boolean;
  item: TeacherWorkspaceLessonSectionItem;
};

const splitTeacherModuleHeading = (value: string) => {
  const dividerIndex = value.indexOf(" - ");
  if (dividerIndex <= 0) {
    return { prefix: value, title: "" };
  }
  return {
    prefix: value.slice(0, dividerIndex),
    title: value.slice(dividerIndex + 3),
  };
};

const isTeacherNotebookLessonItem = (item: TeacherWorkspaceLessonSectionItem) =>
  Boolean(
    item.trainingContent
    || item.assetType === "notebook"
    || item.activityType === "assignment",
  );

const splitTeacherLessonItems = (lesson: TeacherWorkspaceLesson) => {
  const notes = lesson.sections.flatMap((section) =>
    section.items.filter((item) => item.activityType !== "video" && item.activityType !== "quiz" && !isTeacherNotebookLessonItem(item))
  );
  const quizzes = lesson.sections.flatMap((section) => section.items.filter((item) => item.activityType === "quiz"));
  const videos = lesson.sections.flatMap((section) => section.items.filter((item) => item.activityType === "video"));
  const practice = lesson.sections.flatMap((section) => section.items.filter((item) => isTeacherNotebookLessonItem(item)));
  return { notes, quizzes, videos, practice };
};

const buildTeacherLessonResources = (lesson: TeacherWorkspaceLesson): TeacherLessonResource[] => {
  const { notes, quizzes, videos, practice } = splitTeacherLessonItems(lesson);
  const resources: TeacherLessonResource[] = [];

  if (notes.length > 0) {
    resources.push({
      key: `${lesson.id}-presentation`,
      kind: "presentation",
      title: "Lesson presentation",
      subtitle: "Slide deck",
    });
  }

  const primaryQuiz = quizzes[0];
  if (primaryQuiz) {
    resources.push({
      key: `${lesson.id}-quiz`,
      kind: "quiz",
      title: "Quiz",
      subtitle: primaryQuiz.title || "Lesson knowledge check",
      item: primaryQuiz,
    });
  }

  const primaryVideo = videos[0];
  if (primaryVideo) {
    resources.push({
      key: `${lesson.id}-video`,
      kind: "video",
      title: "Video",
      subtitle: primaryVideo.title || "Lesson video",
      item: primaryVideo,
    });
  }

  const primaryPractice = practice.find((item) => item.trainingContent || item.assetType === "notebook") ?? practice[0];
  if (primaryPractice) {
    resources.push({
      key: `${lesson.id}-practice`,
      kind: "notebook",
      title: "Practical assignments. Notebook",
      subtitle: primaryPractice.title || "Interactive coding task",
      item: primaryPractice,
    });
  }

  return resources;
};

const TeacherPresentationIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M5 4h14a2 2 0 0 1 2 2v3H3V6a2 2 0 0 1 2-2Zm-2 7h8v9H5a2 2 0 0 1-2-2v-7Zm10 0h8v7a2 2 0 0 1-2 2h-6v-9Zm-7 2h3v5H6v-5Zm8 0h4v1.5h-4V13Zm0 3h4v1.5h-4V16Z" />
  </svg>
);

const TeacherVideoIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M5 5h10a2 2 0 0 1 2 2v1.6l3.2-1.9A1 1 0 0 1 22 7.55v8.9a1 1 0 0 1-1.8.85L17 15.4V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Zm0 2v10h10V7H5Z" />
  </svg>
);

const TeacherQuizIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20Zm-.2 5.5c-1.9 0-3.3 1.1-3.6 2.9h1.8c.2-.8.8-1.3 1.8-1.3 1 0 1.7.5 1.7 1.5 0 .8-.4 1.2-1.4 1.8-1.2.7-1.9 1.4-1.9 3v.3h1.7v-.2c0-1 .5-1.5 1.4-2 .9-.6 2-1.4 2-3 0-2-1.5-3-3.5-3Zm-.8 9.8v1.9h2v-1.9h-2Z" />
  </svg>
);

const TeacherNotebookIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M7 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm1.5 4v1.5h7V7h-7Zm0 4v1.5h7V11h-7Zm0 4v1.5H13V15H8.5Z" />
  </svg>
);

const TeacherLessonResourceIcon = ({ kind }: { kind: TeacherLessonResourceKind }) => {
  if (kind === "presentation") return <TeacherPresentationIcon />;
  if (kind === "quiz") return <TeacherQuizIcon />;
  if (kind === "video") return <TeacherVideoIcon />;
  return <TeacherNotebookIcon />;
};

const TeacherLessonResourceCard = ({
  resource,
  onOpen,
  statusLabel = "Open",
  isActive = false,
}: {
  resource: TeacherLessonResource;
  onOpen: () => void | Promise<void>;
  statusLabel?: string;
  isActive?: boolean;
}) => (
  <button
    type="button"
    className={`curator-workspace__lesson-item ${isActive ? "curator-workspace__lesson-item--active" : ""}`}
    onClick={() => void onOpen()}
  >
    <div className="curator-workspace__lesson-item-leading">
      <span className={`curator-workspace__lesson-item-icon curator-workspace__lesson-item-icon--${resource.kind}`} aria-hidden="true">
        <TeacherLessonResourceIcon kind={resource.kind} />
      </span>
      <div>
        <strong>{resource.title}</strong>
        <p>{resource.subtitle}</p>
      </div>
    </div>
    <span className="curator-workspace__lesson-open-link">{statusLabel}</span>
  </button>
);

const launchTeacherTrainingLab = async (contentSlug: string): Promise<{ launchUrl?: string | null }> => {
  const csrfToken = getCsrfToken();
  const response = await fetch(`${resolveTeacherTrainingBaseUrl()}/labs/${contentSlug}/launch/`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Online-Auth-Scope": "staff",
      ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
    },
    body: "{}",
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload?.detail === "string" ? payload.detail : "Failed to launch the notebook runtime.";
    throw new Error(detail);
  }
  return payload;
};

type TeacherTrainingContentDetail = {
  slug: string;
  name: string;
  description: string;
  body_markdown: string;
  content_kind: string;
  difficulty: string;
  estimated_minutes: number | null;
  is_repeatable_on_demand: boolean;
};

const fetchTeacherTrainingContentDetail = async (contentSlug: string): Promise<TeacherTrainingContentDetail> => {
  const csrfToken = getCsrfToken();
  const response = await fetch(`${resolveTeacherTrainingBaseUrl()}/content/${contentSlug}/`, {
    method: "GET",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Online-Auth-Scope": "staff",
      ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
    },
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload?.detail === "string" ? payload.detail : "Failed to load notebook briefing.";
    throw new Error(detail);
  }
  return payload as TeacherTrainingContentDetail;
};

const TeacherNotebookBriefingCard = ({
  item,
  onLaunchNotebook,
  launchingSlug,
}: {
  item: TeacherWorkspaceLesson["sections"][number]["items"][number];
  onLaunchNotebook: (contentSlug: string) => void;
  launchingSlug: string;
}) => {
  const contentSlug = item.trainingContent?.slug ?? "";
  const [detail, setDetail] = useState<TeacherTrainingContentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let active = true;

    if (!contentSlug) {
      setDetail(null);
      setLoading(false);
      setLoadError("");
      return () => {
        active = false;
      };
    }

    setLoading(true);
    setLoadError("");
    void fetchTeacherTrainingContentDetail(contentSlug)
      .then((response) => {
        if (active) setDetail(response);
      })
      .catch((error) => {
        if (!active) return;
        setDetail(null);
        setLoadError(error instanceof Error ? error.message : "Failed to load notebook briefing.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [contentSlug]);

  return (
    <article className="curator-workspace__lesson-notebook-card">
      <div className="curator-workspace__lesson-notebook-head">
        <div>
          <span className="curator-workspace__lesson-block-kicker">Notebook briefing</span>
          <h5>{item.title}</h5>
          <p>{item.description || "Hands-on task in Jupyter Notebook."}</p>
        </div>
        <span className="curator-workspace__lesson-notebook-kind">{detail?.content_kind || item.assetType}</span>
      </div>

      <div className="curator-workspace__lesson-notebook-meta">
        <span>{detail?.difficulty || "intermediate"}</span>
        <span>{detail?.estimated_minutes ? `${detail.estimated_minutes} min` : "Practice"}</span>
        <span>{detail?.is_repeatable_on_demand ? "Repeatable" : "Single run"}</span>
      </div>

      {detail?.description || item.bodyMarkdown ? (
        <div className="curator-workspace__lesson-notebook-copy">
          {detail?.description ? <p>{detail.description}</p> : null}
          {item.bodyMarkdown ? <div>{renderTeacherMarkdownBlocks(item.bodyMarkdown)}</div> : null}
        </div>
      ) : null}

      <div className="curator-workspace__lesson-notebook-actions">
        <button
          type="button"
          className="curator-workspace__secondary-action curator-workspace__secondary-action--primary"
          onClick={() => void onLaunchNotebook(contentSlug)}
          disabled={!contentSlug || launchingSlug === contentSlug}
        >
          {launchingSlug === contentSlug ? "Launching..." : "Open JupyterLab"}
        </button>
      </div>

      {loading ? <p className="curator-workspace__lesson-notebook-status">Loading notebook details...</p> : null}
      {loadError ? <p className="curator-workspace__error-copy">{loadError}</p> : null}
    </article>
  );
};

const buildTeacherLessonPresentationHtml = ({
  courseTitle,
  module,
  lesson,
}: {
  courseTitle: string;
  module: TeacherWorkspaceCourseModule;
  lesson: TeacherWorkspaceLesson;
}) => {
  const sectionMarkup = lesson.sections
    .map((section) => {
      const itemsMarkup = section.items
        .map((item) => {
          const itemLink = resolveTeacherLessonItemLink(item);
          const videoEmbedUrl = item.activityType === "video" ? resolveTeacherVideoEmbedUrl(itemLink) : "";
          const pdfUrl = item.assetType === "document" || isTeacherPdfUrl(itemLink) ? itemLink : "";
          const detailsMarkup = item.bodyMarkdown ? markdownToHtml(item.bodyMarkdown) : "";
          const notebookMeta = item.trainingContent
            ? `<div class="meta">${escapeHtml(item.trainingContent.name)} · ${escapeHtml(item.trainingContent.contentKind)}</div>`
            : "";
          const linkMarkup = itemLink
            ? `<a class="resource-link" href="${escapeHtml(itemLink)}" target="_blank" rel="noreferrer">Open resource</a>`
            : "";
          const mediaMarkup = videoEmbedUrl
            ? isTeacherDirectVideoUrl(videoEmbedUrl)
              ? `<video controls preload="metadata" src="${escapeHtml(videoEmbedUrl)}"></video>`
              : `<iframe src="${escapeHtml(videoEmbedUrl)}" title="${escapeHtml(item.title)}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>`
            : pdfUrl
              ? `<iframe src="${escapeHtml(pdfUrl)}" title="${escapeHtml(item.title)}" loading="lazy"></iframe>`
              : "";

          return `
            <article class="item">
              <div class="item-header">
                <div>
                  <span class="badge">${escapeHtml(teacherActivityLabel(item.activityType))}</span>
                  <h4>${escapeHtml(item.title)}</h4>
                </div>
              </div>
              ${item.description ? `<p class="description">${escapeHtml(item.description)}</p>` : ""}
              ${mediaMarkup}
              ${detailsMarkup}
              ${notebookMeta}
              ${linkMarkup}
            </article>
          `;
        })
        .join("");

      return `
        <section class="section">
          <div class="section-header">
            <span>${escapeHtml(section.title)}</span>
            <strong>${section.items.length} item(s)</strong>
          </div>
          ${section.description ? `<p class="description">${escapeHtml(section.description)}</p>` : ""}
          <div class="items">${itemsMarkup}</div>
        </section>
      `;
    })
    .join("");

  return `<!doctype html>
  <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>${escapeHtml(lesson.title)} | ${escapeHtml(courseTitle)}</title>
      <style>
        :root {
          color-scheme: light;
          --bg: #f4f7fa;
          --panel: #ffffff;
          --surface: #f7fafc;
          --border: rgba(96, 124, 146, 0.2);
          --text: #133047;
          --muted: #557086;
          --accent: #1b5f8c;
        }
        * { box-sizing: border-box; }
        body {
          margin: 0;
          font-family: "Segoe UI", system-ui, sans-serif;
          background: linear-gradient(180deg, #f2f6f9 0%, #eef3f7 100%);
          color: var(--text);
        }
        main {
          margin: 0 auto;
          max-width: 1080px;
          padding: 32px 20px 48px;
        }
        .hero {
          background: linear-gradient(180deg, #294d63 0%, #52758a 100%);
          border-radius: 28px;
          color: #f7f2e9;
          padding: 28px;
          box-shadow: 0 22px 40px rgba(19, 48, 71, 0.18);
        }
        .hero small {
          display: block;
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 0.18em;
          opacity: 0.78;
          text-transform: uppercase;
        }
        .hero h1 {
          margin: 12px 0 8px;
          font-size: 40px;
          line-height: 1.02;
        }
        .hero p {
          margin: 0;
          max-width: 720px;
          color: rgba(247, 242, 233, 0.88);
          line-height: 1.65;
        }
        .section {
          margin-top: 22px;
          background: var(--panel);
          border: 1px solid var(--border);
          border-radius: 24px;
          padding: 22px;
          box-shadow: 0 14px 30px rgba(19, 48, 71, 0.08);
        }
        .section-header {
          display: flex;
          justify-content: space-between;
          gap: 16px;
          align-items: center;
          margin-bottom: 12px;
        }
        .section-header span {
          color: var(--accent);
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 0.16em;
          text-transform: uppercase;
        }
        .description {
          margin: 0 0 14px;
          color: var(--muted);
          line-height: 1.7;
        }
        .items {
          display: grid;
          gap: 14px;
        }
        .item {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 20px;
          padding: 18px;
        }
        .item-header {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: flex-start;
        }
        .item h4 {
          margin: 10px 0 0;
          font-size: 22px;
          line-height: 1.15;
        }
        .badge {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          background: rgba(27, 95, 140, 0.1);
          border: 1px solid rgba(27, 95, 140, 0.18);
          color: var(--accent);
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.12em;
          padding: 7px 10px;
          text-transform: uppercase;
        }
        .item iframe, .item video {
          width: 100%;
          min-height: 380px;
          margin-top: 16px;
          border: 1px solid var(--border);
          border-radius: 18px;
          background: #e8eef4;
        }
        .item p, .item li {
          color: var(--muted);
          line-height: 1.75;
        }
        .resource-link {
          display: inline-flex;
          align-items: center;
          margin-top: 14px;
          color: var(--accent);
          font-weight: 700;
          text-decoration: none;
        }
        .meta {
          margin-top: 10px;
          color: var(--muted);
          font-size: 14px;
          font-weight: 600;
        }
      </style>
    </head>
    <body>
      <main>
        <section class="hero">
          <small>${escapeHtml(courseTitle)}</small>
          <h1>${escapeHtml(lesson.title)}</h1>
          <p>${escapeHtml(module.title)} · ${escapeHtml(lesson.description || "Structured lesson delivery package.")}</p>
        </section>
        ${sectionMarkup}
      </main>
    </body>
  </html>`;
};

const openTeacherBlobDocument = (html: string, fileName: string, download: boolean) => {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const objectUrl = URL.createObjectURL(blob);

  if (download) {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } else {
    window.open(objectUrl, "_blank", "noopener,noreferrer");
  }

  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
};

const StructuredLessonPlans = ({
  courses,
  courseModulesByCourse,
}: {
  courses: TeacherWorkspaceCourse[];
  courseModulesByCourse: Record<number, TeacherWorkspaceCourseModule[]>;
}) => {
  const [expandedCourses, setExpandedCourses] = useState<Record<number, boolean>>({});
  const [expandedModules, setExpandedModules] = useState<Record<string, boolean>>({});
  const [expandedLessons, setExpandedLessons] = useState<Record<string, boolean>>({});
  const [activeNotebookByLesson, setActiveNotebookByLesson] = useState<Record<number, string>>({});
  const [launchingSlug, setLaunchingSlug] = useState<string>("");
  const [launchErrorByLesson, setLaunchErrorByLesson] = useState<Record<number, string>>({});
  const [resourceErrorByLesson, setResourceErrorByLesson] = useState<Record<number, string>>({});
  const [resourceModal, setResourceModal] = useState<TeacherResourceModalState | null>(null);

  const coursesWithModules = courses
    .map((course) => ({
      course,
      modules: courseModulesByCourse[course.id] ?? [],
    }))
    .filter((entry) => entry.modules.length > 0);

  if (coursesWithModules.length === 0) {
    return <p className="curator-workspace__empty-copy">No structured lesson plans are assigned to your courses yet.</p>;
  }

  const toggleCourse = (courseId: number) => {
    setExpandedCourses((current) => ({ ...current, [courseId]: !(current[courseId] ?? true) }));
  };

  const toggleModule = (key: string) => {
    setExpandedModules((current) => ({ ...current, [key]: !(current[key] ?? true) }));
  };

  const toggleLesson = (key: string, defaultOpen: boolean) => {
    setExpandedLessons((current) => ({ ...current, [key]: !(current[key] ?? defaultOpen) }));
  };

  const openLessonDocument = (courseTitle: string, module: TeacherWorkspaceCourseModule, lesson: TeacherWorkspaceLesson, download: boolean) => {
    const html = buildTeacherLessonPresentationHtml({ courseTitle, module, lesson });
    const baseName = `${courseTitle}-${lesson.title}`.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    openTeacherBlobDocument(html, `${baseName || "lesson"}.html`, download);
  };

  const openTeacherPresentationResource = (
    courseTitle: string,
    module: TeacherWorkspaceCourseModule,
    lesson: TeacherWorkspaceLesson,
  ) => {
    const { notes } = splitTeacherLessonItems(lesson);
    const presentationLesson: TeacherWorkspaceLesson = {
      ...lesson,
      sections: [
        {
          id: -1,
          sectionType: "introduction",
          title: "Lesson presentation",
          description: "Slide-style teaching document for the current lesson.",
          sortOrder: 10,
          items: notes,
        },
      ],
    };
    const html = buildTeacherLessonPresentationHtml({ courseTitle, module, lesson: presentationLesson });
    const baseName = `${courseTitle}-${lesson.title}-presentation`.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    openTeacherBlobDocument(html, `${baseName || "lesson-presentation"}.html`, false);
  };

  const openTeacherQuizResource = (
    courseTitle: string,
    module: TeacherWorkspaceCourseModule,
    lesson: TeacherWorkspaceLesson,
    quizItem: TeacherWorkspaceLessonSectionItem,
  ) => {
    const quizLesson: TeacherWorkspaceLesson = {
      ...lesson,
      title: `${lesson.title} · Quiz`,
      description: "Knowledge check based on the lesson presentation and reading pack.",
      sections: [
        {
          id: -1,
          sectionType: "main",
          title: "Quiz",
          description: "Review questions for live teaching and learner follow-up.",
          sortOrder: 20,
          items: [quizItem],
        },
      ],
    };
    const html = buildTeacherLessonPresentationHtml({ courseTitle, module, lesson: quizLesson });
    const baseName = `${courseTitle}-${lesson.title}-quiz`.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    openTeacherBlobDocument(html, `${baseName || "lesson-quiz"}.html`, false);
  };

  const handleLaunchNotebook = async (lessonId: number, contentSlug: string) => {
    setLaunchErrorByLesson((current) => ({ ...current, [lessonId]: "" }));
    setLaunchingSlug(contentSlug);
    try {
      const contract = await launchTeacherTrainingLab(contentSlug);
      if (contract.launchUrl) {
        window.open(contract.launchUrl, "_blank", "noopener,noreferrer");
      } else {
        setLaunchErrorByLesson((current) => ({ ...current, [lessonId]: "Notebook runtime launch URL is not available." }));
      }
    } catch (error) {
      console.error("Failed to launch instructor notebook runtime", error);
      setLaunchErrorByLesson((current) => ({
        ...current,
        [lessonId]: error instanceof Error ? error.message : "Failed to launch the notebook runtime.",
      }));
    } finally {
      setLaunchingSlug("");
    }
  };

  const handleJoinLesson = (joinUrl: string) => {
    window.open(joinUrl, "_blank", "noopener,noreferrer");
  };

  const handleResourceOpen = (
    courseTitle: string,
    module: TeacherWorkspaceCourseModule,
    lesson: TeacherWorkspaceLesson,
    resource: TeacherLessonResource,
  ) => {
    setResourceErrorByLesson((current) => ({ ...current, [lesson.id]: "" }));

    if (resource.kind === "presentation") {
      openTeacherPresentationResource(courseTitle, module, lesson);
      return;
    }

    if (resource.kind === "quiz") {
      if (!resource.item) {
        setResourceErrorByLesson((current) => ({ ...current, [lesson.id]: "Quiz content is not attached yet." }));
        return;
      }
      openTeacherQuizResource(courseTitle, module, lesson, resource.item);
      return;
    }

    if (resource.kind === "video") {
      const resourceUrl = resource.item ? resolveTeacherLessonItemLink(resource.item) : "";
      if (!resourceUrl) {
        setResourceErrorByLesson((current) => ({ ...current, [lesson.id]: "Video resource is not linked yet." }));
        return;
      }
      setResourceModal({
        title: resource.title,
        subtitle: resource.item?.title || resource.subtitle,
        embedUrl: resolveTeacherVideoEmbedUrl(resourceUrl),
        externalUrl: resourceUrl,
        directVideo: isTeacherDirectVideoUrl(resourceUrl),
        item: resource.item!,
      });
      return;
    }

    if (resource.item?.trainingContent?.slug) {
      setActiveNotebookByLesson((current) => ({
        ...current,
        [lesson.id]: current[lesson.id] === resource.key ? "" : resource.key,
      }));
      return;
    }

    const fallbackUrl = resource.item ? resolveTeacherLessonItemLink(resource.item) : "";
    if (fallbackUrl) {
      window.open(fallbackUrl, "_blank", "noopener,noreferrer");
      return;
    }

    setResourceErrorByLesson((current) => ({ ...current, [lesson.id]: "Notebook runtime is not linked yet." }));
  };

  return (
    <>
      <div className="curator-workspace__section-stack">
        {coursesWithModules.map(({ course, modules }) => {
          const courseTitle = course.titleEn || course.titleDe;
          const isCourseOpen = expandedCourses[course.id] ?? true;

          return (
            <article key={course.id} className="curator-workspace__card curator-workspace__course-card">
              <button
                type="button"
                className="curator-workspace__course-toggle"
                onClick={() => toggleCourse(course.id)}
                aria-expanded={isCourseOpen}
              >
                <div className="curator-workspace__panel-heading curator-workspace__panel-heading--compact">
                  <div>
                    <span className="curator-workspace__eyebrow">Structured pathway</span>
                    <h3>{courseTitle}</h3>
                  </div>
                  <p>{modules.length} module(s) currently prepared for this course.</p>
                </div>
                <span className={`curator-workspace__tree-chevron ${isCourseOpen ? "is-open" : ""}`} aria-hidden="true">
                  ▾
                </span>
              </button>

              {isCourseOpen ? (
                <div className="curator-workspace__course-tree">
                  {modules.map((module, moduleIndex) => {
                    const moduleKey = teacherModuleKeyOf(course.id, module, moduleIndex);
                    const isModuleOpen = expandedModules[moduleKey] ?? true;
                    const moduleHeading = splitTeacherModuleHeading(module.title);

                    return (
                      <article key={moduleKey} className="curator-workspace__module-card">
                        <button
                          type="button"
                          className="curator-workspace__module-toggle"
                          onClick={() => toggleModule(moduleKey)}
                          aria-expanded={isModuleOpen}
                        >
                          <div className="curator-workspace__module-header">
                            <div>
                              <span className="curator-workspace__eyebrow">
                                {module.moduleType === "final_assessment" ? "Final assessment" : `Week ${module.weekNumber ?? moduleIndex + 1}`}
                              </span>
                              <h3 className="curator-workspace__module-title">
                                <span className="curator-workspace__module-prefix">{moduleHeading.prefix}</span>
                                {moduleHeading.title ? (
                                  <>
                                    {" - "}
                                    <span className="curator-workspace__module-emphasis">{moduleHeading.title}</span>
                                  </>
                                ) : null}
                              </h3>
                              <p>{module.description || `${module.lessonsCount} lesson(s)`}</p>
                              {formatTeacherModuleSchedule(module) ? (
                                <span className="curator-workspace__schedule-copy">{formatTeacherModuleSchedule(module)}</span>
                              ) : null}
                            </div>
                            <span className={`curator-workspace__tree-chevron ${isModuleOpen ? "is-open" : ""}`} aria-hidden="true">
                              ▾
                            </span>
                          </div>
                        </button>

                        {isModuleOpen ? (
                          <div className="curator-workspace__lesson-stack">
                            {module.lessons.map((lesson, lessonIndex) => {
                              const lessonKey = teacherLessonKeyOf(moduleKey, lesson);
                              const defaultOpen = lessonIndex === 0;
                              const isLessonOpen = expandedLessons[lessonKey] ?? defaultOpen;
                              const resources = buildTeacherLessonResources(lesson);
                              const lessonDisplayNumber = `${moduleIndex + 1}.${lessonIndex + 1}`;
                              const activeNotebookKey = activeNotebookByLesson[lesson.id] ?? "";
                              const activeNotebookItem =
                                activeNotebookKey
                                  ? resources.find((resource) => resource.key === activeNotebookKey)?.item ?? null
                                  : null;

                              return (
                                <section key={lesson.id} className="curator-workspace__lesson-card">
                                  <button
                                    type="button"
                                    className="curator-workspace__lesson-toggle"
                                    onClick={() => toggleLesson(lessonKey, defaultOpen)}
                                    aria-expanded={isLessonOpen}
                                  >
                                    <div className="curator-workspace__lesson-header">
                                      <div>
                                        <span className="curator-workspace__lesson-section-kicker">Lesson {lessonDisplayNumber}</span>
                                        <strong>{lesson.title}</strong>
                                        {formatTeacherLessonSchedule(lesson) ? (
                                          <span className="curator-workspace__schedule-copy curator-workspace__schedule-copy--lesson">
                                            {formatTeacherLessonSchedule(lesson)}
                                          </span>
                                        ) : null}
                                      </div>
                                      <div className="curator-workspace__lesson-header-meta">
                                        <span>{resources.length} item(s)</span>
                                        <span className={`curator-workspace__tree-chevron ${isLessonOpen ? "is-open" : ""}`} aria-hidden="true">
                                          ▾
                                        </span>
                                      </div>
                                    </div>
                                  </button>

                                  {isLessonOpen ? (
                                    <div className="curator-workspace__lesson-resource-list">
                                      {resources.length === 0 ? (
                                        <p className="curator-workspace__empty-copy">No resources are attached to this lesson yet.</p>
                                      ) : (
                                        resources.map((resource) => (
                                          <TeacherLessonResourceCard
                                            key={resource.key}
                                            resource={resource}
                                            isActive={resource.kind === "notebook" && activeNotebookKey === resource.key}
                                            statusLabel={
                                              resource.kind === "notebook"
                                                ? activeNotebookKey === resource.key
                                                  ? "Opened"
                                                  : "Start"
                                                : "Open"
                                            }
                                            onOpen={() => handleResourceOpen(courseTitle, module, lesson, resource)}
                                          />
                                        ))
                                      )}

                                      {activeNotebookItem ? (
                                        <div className="curator-workspace__lesson-inline-practice">
                                          <TeacherNotebookBriefingCard
                                            item={activeNotebookItem}
                                            onLaunchNotebook={(contentSlug) => void handleLaunchNotebook(lesson.id, contentSlug)}
                                            launchingSlug={launchingSlug}
                                          />
                                        </div>
                                      ) : null}

                                      {resourceErrorByLesson[lesson.id] ? (
                                        <p className="curator-workspace__error-copy">{resourceErrorByLesson[lesson.id]}</p>
                                      ) : null}
                                      {launchErrorByLesson[lesson.id] ? (
                                        <p className="curator-workspace__error-copy">{launchErrorByLesson[lesson.id]}</p>
                                      ) : null}

                                      <div className="curator-workspace__lesson-actions">
                                        {lesson.joinUrl ? (
                                          <button
                                            type="button"
                                            className="curator-workspace__secondary-action curator-workspace__secondary-action--primary"
                                            onClick={() => handleJoinLesson(lesson.joinUrl!)}
                                          >
                                            Start online lesson
                                          </button>
                                        ) : null}
                                        <button
                                          type="button"
                                          className="curator-workspace__secondary-action"
                                          onClick={() => openLessonDocument(courseTitle, module, lesson, false)}
                                        >
                                          Generate lesson
                                        </button>
                                        <button
                                          type="button"
                                          className="curator-workspace__secondary-action"
                                          onClick={() => openLessonDocument(courseTitle, module, lesson, true)}
                                        >
                                          Download lesson
                                        </button>
                                      </div>
                                    </div>
                                  ) : null}
                                </section>
                              );
                            })}
                          </div>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>

      {resourceModal ? (
        <div className="curator-workspace__resource-backdrop" onClick={() => setResourceModal(null)} role="presentation">
          <article className="curator-workspace__resource-modal" onClick={(event) => event.stopPropagation()}>
            <header className="curator-workspace__resource-header">
              <div>
                <span className="curator-workspace__resource-kicker">Internal video viewer</span>
                <h3>{resourceModal.title}</h3>
                <p>{resourceModal.subtitle}</p>
              </div>
              <button type="button" className="curator-workspace__resource-close" onClick={() => setResourceModal(null)}>
                Close
              </button>
            </header>
            <div className="curator-workspace__resource-body">
              <div className="curator-workspace__resource-badges">
                <span>Video</span>
                <span>Internal player</span>
                <span>External link available</span>
              </div>
              {resourceModal.item.description ? <p className="curator-workspace__resource-copy">{resourceModal.item.description}</p> : null}
              {resourceModal.item.bodyMarkdown ? (
                <div className="curator-workspace__resource-markdown">
                  {renderTeacherMarkdownBlocks(resourceModal.item.bodyMarkdown)}
                </div>
              ) : null}
              {resourceModal.directVideo ? (
                <video className="curator-workspace__resource-video" controls preload="metadata" src={resourceModal.embedUrl} />
              ) : (
                <iframe
                  className="curator-workspace__resource-frame"
                  src={resourceModal.embedUrl}
                  title={resourceModal.title}
                  loading="lazy"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                />
              )}
              <div className="curator-workspace__resource-actions">
                <a href={resourceModal.externalUrl} target="_blank" rel="noreferrer">
                  Open external link
                </a>
              </div>
            </div>
          </article>
        </div>
      ) : null}
    </>
  );
};

void StructuredLessonPlans;

const CuratorCourseDeliveryAccordion = ({
  courses,
  courseModulesByCourse,
  materials,
  cohorts,
}: {
  courses: TeacherWorkspaceCourse[];
  courseModulesByCourse: Record<number, TeacherWorkspaceCourseModule[]>;
  materials: TeacherWorkspaceMaterial[];
  cohorts: TeacherWorkspaceResponse["cohorts"];
}) => {
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [expandedModules, setExpandedModules] = useState<Record<string, boolean>>({});
  const [expandedLessons, setExpandedLessons] = useState<Record<string, boolean>>({});
  const [activeNotebookByLesson, setActiveNotebookByLesson] = useState<Record<number, string>>({});
  const [launchingSlug, setLaunchingSlug] = useState<string>("");
  const [launchErrorByLesson, setLaunchErrorByLesson] = useState<Record<number, string>>({});
  const [resourceErrorByLesson, setResourceErrorByLesson] = useState<Record<number, string>>({});
  const [resourceModal, setResourceModal] = useState<TeacherResourceModalState | null>(null);

  const coursesWithModules = courses
    .map((course) => ({
      course,
      modules: courseModulesByCourse[course.id] ?? [],
    }))
    .filter((entry) => entry.modules.length > 0);

  if (coursesWithModules.length === 0) {
    return <p className="curator-workspace__empty-copy">No structured lesson plans are assigned to your courses yet.</p>;
  }

  const toggleModule = (key: string) => {
    setExpandedModules((current) => ({ ...current, [key]: !(current[key] ?? true) }));
  };

  const toggleLesson = (key: string, defaultOpen: boolean) => {
    setExpandedLessons((current) => ({ ...current, [key]: !(current[key] ?? defaultOpen) }));
  };

  const openLessonDocument = (courseTitle: string, module: TeacherWorkspaceCourseModule, lesson: TeacherWorkspaceLesson, download: boolean) => {
    const html = buildTeacherLessonPresentationHtml({ courseTitle, module, lesson });
    const baseName = `${courseTitle}-${lesson.title}`.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    openTeacherBlobDocument(html, `${baseName || "lesson"}.html`, download);
  };

  const openTeacherPresentationResource = (
    courseTitle: string,
    module: TeacherWorkspaceCourseModule,
    lesson: TeacherWorkspaceLesson,
  ) => {
    const { notes } = splitTeacherLessonItems(lesson);
    const presentationLesson: TeacherWorkspaceLesson = {
      ...lesson,
      sections: [
        {
          id: -1,
          sectionType: "introduction",
          title: "Lesson presentation",
          description: "Slide-style teaching document for the current lesson.",
          sortOrder: 10,
          items: notes,
        },
      ],
    };
    const html = buildTeacherLessonPresentationHtml({ courseTitle, module, lesson: presentationLesson });
    const baseName = `${courseTitle}-${lesson.title}-presentation`.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    openTeacherBlobDocument(html, `${baseName || "lesson-presentation"}.html`, false);
  };

  const openTeacherQuizResource = (
    courseTitle: string,
    module: TeacherWorkspaceCourseModule,
    lesson: TeacherWorkspaceLesson,
    quizItem: TeacherWorkspaceLessonSectionItem,
  ) => {
    const quizLesson: TeacherWorkspaceLesson = {
      ...lesson,
      title: `${lesson.title} · Quiz`,
      description: "Knowledge check based on the lesson presentation and reading pack.",
      sections: [
        {
          id: -1,
          sectionType: "main",
          title: "Quiz",
          description: "Review questions for live teaching and learner follow-up.",
          sortOrder: 20,
          items: [quizItem],
        },
      ],
    };
    const html = buildTeacherLessonPresentationHtml({ courseTitle, module, lesson: quizLesson });
    const baseName = `${courseTitle}-${lesson.title}-quiz`.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    openTeacherBlobDocument(html, `${baseName || "lesson-quiz"}.html`, false);
  };

  const handleLaunchNotebook = async (lessonId: number, contentSlug: string) => {
    setLaunchErrorByLesson((current) => ({ ...current, [lessonId]: "" }));
    setLaunchingSlug(contentSlug);
    try {
      const contract = await launchTeacherTrainingLab(contentSlug);
      if (contract.launchUrl) {
        window.open(contract.launchUrl, "_blank", "noopener,noreferrer");
      } else {
        setLaunchErrorByLesson((current) => ({ ...current, [lessonId]: "Notebook runtime launch URL is not available." }));
      }
    } catch (error) {
      console.error("Failed to launch instructor notebook runtime", error);
      setLaunchErrorByLesson((current) => ({
        ...current,
        [lessonId]: error instanceof Error ? error.message : "Failed to launch the notebook runtime.",
      }));
    } finally {
      setLaunchingSlug("");
    }
  };

  const handleJoinLesson = (joinUrl: string) => {
    window.open(joinUrl, "_blank", "noopener,noreferrer");
  };

  const handleResourceOpen = (
    courseTitle: string,
    module: TeacherWorkspaceCourseModule,
    lesson: TeacherWorkspaceLesson,
    resource: TeacherLessonResource,
  ) => {
    setResourceErrorByLesson((current) => ({ ...current, [lesson.id]: "" }));

    if (resource.kind === "presentation") {
      openTeacherPresentationResource(courseTitle, module, lesson);
      return;
    }

    if (resource.kind === "quiz") {
      if (!resource.item) {
        setResourceErrorByLesson((current) => ({ ...current, [lesson.id]: "Quiz content is not attached yet." }));
        return;
      }
      openTeacherQuizResource(courseTitle, module, lesson, resource.item);
      return;
    }

    if (resource.kind === "video") {
      const resourceUrl = resource.item ? resolveTeacherLessonItemLink(resource.item) : "";
      if (!resourceUrl) {
        setResourceErrorByLesson((current) => ({ ...current, [lesson.id]: "Video resource is not linked yet." }));
        return;
      }
      setResourceModal({
        title: resource.title,
        subtitle: resource.item?.title || resource.subtitle,
        embedUrl: resolveTeacherVideoEmbedUrl(resourceUrl),
        externalUrl: resourceUrl,
        directVideo: isTeacherDirectVideoUrl(resourceUrl),
        item: resource.item!,
      });
      return;
    }

    if (resource.item?.trainingContent?.slug) {
      setActiveNotebookByLesson((current) => ({
        ...current,
        [lesson.id]: current[lesson.id] === resource.key ? "" : resource.key,
      }));
      return;
    }

    const fallbackUrl = resource.item ? resolveTeacherLessonItemLink(resource.item) : "";
    if (fallbackUrl) {
      window.open(fallbackUrl, "_blank", "noopener,noreferrer");
      return;
    }

    setResourceErrorByLesson((current) => ({ ...current, [lesson.id]: "Notebook runtime is not linked yet." }));
  };

  const renderCoursePanel = (course: TeacherWorkspaceCourse, modules: TeacherWorkspaceCourseModule[]) => {
    const courseTitle = course.titleEn || course.titleDe;
    const courseDescription = course.descriptionEn || course.descriptionDe || "Structured delivery track for assigned learners.";
    const courseMaterials = materials.filter((item) => item.courseId === course.id);
    const groupedCourseMaterials = groupMaterials(courseMaterials);
    const courseCohorts = cohorts.filter((cohort) => cohort.courseId === course.id);
    const lessonsCount = modules.reduce((sum, module) => sum + module.lessons.length, 0);
    const nextSessionLabel = formatDateTime(course.nearestSessionAt);

    return (
      <div className="curator-workspace__delivery-course-panel">
        <section className="curator-workspace__delivery-course-overview">
          <div className="curator-workspace__delivery-course-overview-main">
            <div className="curator-workspace__delivery-course-overview-topline">
              <span className="curator-workspace__delivery-course-kicker">Course workspace</span>
              <span className="curator-workspace__delivery-course-meta-pill">{modules.length} module(s)</span>
              <span className="curator-workspace__delivery-course-meta-pill">{lessonsCount} lesson(s)</span>
              {nextSessionLabel ? (
                <span className="curator-workspace__delivery-course-meta-pill">{nextSessionLabel}</span>
              ) : null}
            </div>
            <h3>{courseTitle}</h3>
            <p>{courseDescription}</p>
            <div className="curator-workspace__delivery-course-meta">
              <span>{course.studentsCount} learners</span>
              <span>{course.cohortsCount} cohorts</span>
              <span>{course.sessionsCount} sessions</span>
              <span>{formatPercent(course.attendancePercent)} attendance</span>
              <span>{course.materialsCount} materials</span>
              <span>{course.recordingsCount} recordings</span>
            </div>
            <div className="curator-workspace__delivery-course-actions">
              <a className="curator-workspace__secondary-action curator-workspace__secondary-action--primary" href="/teacher/online">
                Open live operations
              </a>
              <a className="curator-workspace__secondary-action" href="/teacher/home">
                View teaching summary
              </a>
            </div>
          </div>

          <aside className="curator-workspace__delivery-course-side">
            <div className="curator-workspace__delivery-stat-card">
              <span>Learners</span>
              <strong>{course.studentsCount}</strong>
            </div>
            <div className="curator-workspace__delivery-stat-card">
              <span>Cohorts</span>
              <strong>{courseCohorts.length || course.cohortsCount}</strong>
            </div>
            <div className="curator-workspace__delivery-stat-card">
              <span>Sessions</span>
              <strong>{course.sessionsCount}</strong>
            </div>
            <div className="curator-workspace__delivery-stat-card">
              <span>Attendance</span>
              <strong>{formatPercent(course.attendancePercent)}</strong>
            </div>
          </aside>
        </section>

          <section className="curator-workspace__delivery-card">
            <div className="curator-workspace__panel-heading curator-workspace__panel-heading--compact">
              <div>
                <span className="curator-workspace__eyebrow">Course structure</span>
                <h3>Modules, lessons, and teaching actions</h3>
            </div>
            <p>Use the same lesson-first structure as the learner view, with instructor controls for live delivery and lesson documents.</p>
          </div>

          <div className="curator-workspace__delivery-module-stack">
            {modules.map((module, moduleIndex) => {
              const moduleKey = teacherModuleKeyOf(course.id, module, moduleIndex);
              const isModuleOpen = expandedModules[moduleKey] ?? moduleIndex === 0;
              const moduleHeading = splitTeacherModuleHeading(module.title);
              const moduleStatus = resolveTeacherModuleDeliveryStatus(module);
              const moduleMeta = [
                formatTeacherModuleScheduleCompact(module),
                `${module.lessonsCount} lesson${module.lessonsCount === 1 ? "" : "s"}`,
                compactTeacherGroupLabel(module.groupName || module.groupCode),
              ].filter(Boolean);

              return (
                <article key={moduleKey} className="curator-workspace__delivery-module-card">
                  <button
                    type="button"
                    className="curator-workspace__delivery-module-toggle"
                    onClick={() => toggleModule(moduleKey)}
                    aria-expanded={isModuleOpen}
                  >
                    <div className="curator-workspace__delivery-module-main">
                      <div className="curator-workspace__delivery-module-topline">
                        <span className="curator-workspace__lesson-section-kicker">
                          {module.moduleType === "final_assessment" ? "Final assessment" : `Module ${moduleIndex + 1}`}
                        </span>
                        {module.weekNumber ? (
                          <span className="curator-workspace__delivery-chip">Week {module.weekNumber}</span>
                        ) : null}
                        <span className={`curator-workspace__delivery-status curator-workspace__delivery-status--${moduleStatus.tone}`}>
                          <span className="curator-workspace__delivery-status-dot" aria-hidden="true" />
                          {moduleStatus.label}
                        </span>
                      </div>
                      <strong className="curator-workspace__delivery-module-title">
                        <span className="curator-workspace__module-prefix">{moduleHeading.prefix}</span>
                        {moduleHeading.title ? (
                          <>
                            {" - "}
                            <span className="curator-workspace__module-emphasis">{moduleHeading.title}</span>
                          </>
                        ) : null}
                      </strong>
                      <p>{module.description || `${module.lessonsCount} lesson(s) prepared for this module.`}</p>
                      {moduleMeta.length > 0 ? (
                        <div className="curator-workspace__delivery-module-meta">
                          {moduleMeta.map((value) => (
                            <span key={`${moduleKey}_${value}`} className="curator-workspace__delivery-chip">
                              {value}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    <div className="curator-workspace__delivery-module-side">
                      <div className="curator-workspace__delivery-side-card">
                        <span>Lessons</span>
                        <strong>{module.lessonsCount}</strong>
                      </div>
                      <span className={`curator-workspace__tree-chevron ${isModuleOpen ? "is-open" : ""}`} aria-hidden="true">
                        ▾
                      </span>
                    </div>
                  </button>

                  {isModuleOpen ? (
                    <div className="curator-workspace__delivery-lesson-stack">
                      {module.lessons.map((lesson, lessonIndex) => {
                        const lessonKey = teacherLessonKeyOf(moduleKey, lesson);
                        const isLessonOpen = expandedLessons[lessonKey] ?? lessonIndex === 0;
                        const resources = buildTeacherLessonResources(lesson);
                        const lessonDisplayNumber = `${moduleIndex + 1}.${lessonIndex + 1}`;
                        const lessonStatus = resolveTeacherLessonDeliveryStatus(lesson);
                        const activeNotebookKey = activeNotebookByLesson[lesson.id] ?? "";
                        const activeNotebookItem =
                          activeNotebookKey
                            ? resources.find((resource) => resource.key === activeNotebookKey)?.item ?? null
                            : null;
                        const lessonMeta = [
                          formatTeacherLessonScheduleCompact(lesson),
                          `${resources.length} asset${resources.length === 1 ? "" : "s"}`,
                          compactTeacherGroupLabel(lesson.groupName || lesson.groupCode),
                        ].filter(Boolean);

                        return (
                          <section key={lesson.id} className="curator-workspace__delivery-lesson-card">
                            <div className="curator-workspace__delivery-lesson-summary">
                              <div className="curator-workspace__delivery-lesson-main">
                                <div className="curator-workspace__delivery-lesson-topline">
                                  <span className="curator-workspace__lesson-section-kicker">Lesson {lessonDisplayNumber}</span>
                                  <span className={`curator-workspace__delivery-status curator-workspace__delivery-status--${lessonStatus.tone}`}>
                                    <span className="curator-workspace__delivery-status-dot" aria-hidden="true" />
                                    {lessonStatus.label}
                                  </span>
                                </div>
                                <strong className="curator-workspace__delivery-lesson-title">{lesson.title}</strong>
                                {lessonMeta.length > 0 ? (
                                  <div className="curator-workspace__delivery-lesson-meta">
                                    {lessonMeta.map((value) => (
                                      <span key={`${lesson.id}_${value}`} className="curator-workspace__delivery-chip">
                                        {value}
                                      </span>
                                    ))}
                                  </div>
                                ) : null}
                              </div>

                              <div className="curator-workspace__delivery-lesson-side">
                                <div className="curator-workspace__lesson-actions">
                                  {lesson.joinUrl ? (
                                    <button
                                      type="button"
                                      className="curator-workspace__secondary-action curator-workspace__secondary-action--primary"
                                      onClick={() => handleJoinLesson(lesson.joinUrl!)}
                                    >
                                      Start online lesson
                                    </button>
                                  ) : null}
                                  <button
                                    type="button"
                                    className="curator-workspace__secondary-action"
                                    onClick={() => openLessonDocument(courseTitle, module, lesson, false)}
                                  >
                                    Generate lesson
                                  </button>
                                  <button
                                    type="button"
                                    className="curator-workspace__secondary-action"
                                    onClick={() => openLessonDocument(courseTitle, module, lesson, true)}
                                  >
                                    Download lesson
                                  </button>
                                </div>
                                <button
                                  type="button"
                                  className="curator-workspace__delivery-detail-toggle"
                                  onClick={() => toggleLesson(lessonKey, lessonIndex === 0)}
                                  aria-expanded={isLessonOpen}
                                >
                                  {isLessonOpen ? "Hide assets" : "Show assets"}
                                  <span className={`curator-workspace__tree-chevron ${isLessonOpen ? "is-open" : ""}`} aria-hidden="true">
                                    ▾
                                  </span>
                                </button>
                              </div>
                            </div>

                            {isLessonOpen ? (
                              <div className="curator-workspace__delivery-lesson-details">
                                {resources.length === 0 ? (
                                  <p className="curator-workspace__empty-copy">No resources are attached to this lesson yet.</p>
                                ) : (
                                  resources.map((resource) => (
                                    <TeacherLessonResourceCard
                                      key={resource.key}
                                      resource={resource}
                                      isActive={resource.kind === "notebook" && activeNotebookKey === resource.key}
                                      statusLabel={
                                        resource.kind === "notebook"
                                          ? activeNotebookKey === resource.key
                                            ? "Opened"
                                            : "Start"
                                          : "Open"
                                      }
                                      onOpen={() => handleResourceOpen(courseTitle, module, lesson, resource)}
                                    />
                                  ))
                                )}

                                {activeNotebookItem ? (
                                  <div className="curator-workspace__lesson-inline-practice">
                                    <TeacherNotebookBriefingCard
                                      item={activeNotebookItem}
                                      onLaunchNotebook={(contentSlug) => void handleLaunchNotebook(lesson.id, contentSlug)}
                                      launchingSlug={launchingSlug}
                                    />
                                  </div>
                                ) : null}

                                {resourceErrorByLesson[lesson.id] ? (
                                  <p className="curator-workspace__error-copy">{resourceErrorByLesson[lesson.id]}</p>
                                ) : null}
                                {launchErrorByLesson[lesson.id] ? (
                                  <p className="curator-workspace__error-copy">{launchErrorByLesson[lesson.id]}</p>
                                ) : null}
                              </div>
                            ) : null}
                          </section>
                        );
                      })}
                    </div>
                  ) : null}
                </article>
              );
              })}
            </div>
          </section>

          {courseCohorts.length > 0 ? (
            <section className="curator-workspace__delivery-card">
              <div className="curator-workspace__panel-heading curator-workspace__panel-heading--compact">
                <div>
                  <span className="curator-workspace__eyebrow">Student performance</span>
                  <h3>Assigned cohorts and learner visibility</h3>
                </div>
                <p>Open a cohort directly in Online to review attendance, students, and live session status.</p>
              </div>
              <div className="curator-workspace__delivery-cohort-grid">
                {courseCohorts.map((cohort) => (
                  <article key={cohort.id} className="curator-workspace__delivery-cohort-card">
                    <div>
                      <span className="curator-workspace__delivery-course-kicker">{cohort.groupCode}</span>
                      <strong>{cohort.groupName}</strong>
                    </div>
                    <div className="curator-workspace__delivery-course-meta">
                      <span>{cohort.studentsCount} learners</span>
                      <span>{formatPercent(cohort.attendancePercent)} attendance</span>
                      <span>{cohort.sessionsCount} sessions</span>
                    </div>
                    <a className="curator-workspace__secondary-action" href={`/teacher/online?cohortId=${cohort.id}`}>
                      View cohort reporting
                    </a>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

        {groupedCourseMaterials.resources.length > 0 ? (
          <section className="curator-workspace__delivery-card">
            <div className="curator-workspace__panel-heading curator-workspace__panel-heading--compact">
              <div>
                <span className="curator-workspace__eyebrow">Learning resources</span>
                <h3>Documents and reading packs</h3>
              </div>
              <p>Active learner-facing materials assigned to this course.</p>
            </div>
            <MaterialsList items={groupedCourseMaterials.resources} emptyMessage="No active learning resources are assigned yet." />
          </section>
        ) : null}

        {groupedCourseMaterials.conditions.length > 0 ? (
          <section className="curator-workspace__delivery-card">
            <div className="curator-workspace__panel-heading curator-workspace__panel-heading--compact">
              <div>
                <span className="curator-workspace__eyebrow">Operational documents</span>
                <h3>Conditions and delivery notes</h3>
              </div>
              <p>Internal instructions and supporting documents for the selected course.</p>
            </div>
            <MaterialsList items={groupedCourseMaterials.conditions} emptyMessage="No operational documents are currently linked." />
          </section>
        ) : null}
      </div>
    );
  };

  return (
    <>
      <div className="curator-workspace__delivery-stack">
        <div className="curator-workspace__delivery-course-list" aria-label="Assigned courses">
          {coursesWithModules.map(({ course, modules }) => {
            const courseTitle = course.titleEn || course.titleDe;
            const courseDescription = course.descriptionEn || course.descriptionDe || "Structured delivery track.";
            const lessonsCount = modules.reduce((sum, module) => sum + module.lessons.length, 0);
            const isCourseOpen = selectedCourseId === course.id;

            return (
              <article
                key={course.id}
                className={`curator-workspace__delivery-course-card ${isCourseOpen ? "is-open" : ""}`}
              >
                <button
                  type="button"
                  className="curator-workspace__delivery-course-toggle"
                  onClick={() => setSelectedCourseId((current) => (current === course.id ? null : course.id))}
                  aria-expanded={isCourseOpen}
                >
                  <div className="curator-workspace__delivery-course-toggle-main">
                    <span className="curator-workspace__eyebrow">Assigned course</span>
                    <strong>{courseTitle}</strong>
                    <p>{courseDescription}</p>
                    <div className="curator-workspace__delivery-course-meta">
                      <span>{modules.length} module(s)</span>
                      <span>{lessonsCount} lesson(s)</span>
                      <span>{course.studentsCount} learners</span>
                      <span>{formatPercent(course.attendancePercent)} attendance</span>
                    </div>
                  </div>

                  <div className="curator-workspace__delivery-course-toggle-side">
                    <span className="curator-workspace__delivery-course-state">
                      {isCourseOpen ? "Open" : "Closed"}
                    </span>
                    <span className={`curator-workspace__tree-chevron ${isCourseOpen ? "is-open" : ""}`} aria-hidden="true">
                      ▾
                    </span>
                  </div>
                </button>

                {isCourseOpen ? renderCoursePanel(course, modules) : null}
              </article>
            );
          })}
        </div>
      </div>

      {resourceModal ? (
        <div className="curator-workspace__resource-backdrop" onClick={() => setResourceModal(null)} role="presentation">
          <article className="curator-workspace__resource-modal" onClick={(event) => event.stopPropagation()}>
            <header className="curator-workspace__resource-header">
              <div>
                <span className="curator-workspace__resource-kicker">Internal video viewer</span>
                <h3>{resourceModal.title}</h3>
                <p>{resourceModal.subtitle}</p>
              </div>
              <button type="button" className="curator-workspace__resource-close" onClick={() => setResourceModal(null)}>
                Close
              </button>
            </header>
            <div className="curator-workspace__resource-body">
              <div className="curator-workspace__resource-badges">
                <span>Video</span>
                <span>Internal player</span>
                <span>External link available</span>
              </div>
              {resourceModal.item.description ? <p className="curator-workspace__resource-copy">{resourceModal.item.description}</p> : null}
              {resourceModal.item.bodyMarkdown ? (
                <div className="curator-workspace__resource-markdown">
                  {renderTeacherMarkdownBlocks(resourceModal.item.bodyMarkdown)}
                </div>
              ) : null}
              {resourceModal.directVideo ? (
                <video className="curator-workspace__resource-video" controls preload="metadata" src={resourceModal.embedUrl} />
              ) : (
                <iframe
                  className="curator-workspace__resource-frame"
                  src={resourceModal.embedUrl}
                  title={resourceModal.title}
                  loading="lazy"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                />
              )}
              <div className="curator-workspace__resource-actions">
                <a href={resourceModal.externalUrl} target="_blank" rel="noreferrer">
                  Open external link
                </a>
              </div>
            </div>
          </article>
        </div>
      ) : null}
    </>
  );
};

const DocumentsSection = () => {
  const { data, isLoading, isError } = useGetTeacherWorkspaceQuery();

  if (isLoading) {
    return <p className="curator-workspace__empty-copy">Loading assigned courses...</p>;
  }

  if (isError || !data) {
    return <p className="curator-workspace__error-copy">Failed to load assigned courses.</p>;
  }

  const modulesByCourse = Object.keys(data.courseModulesByCourse || {}).length
    ? data.courseModulesByCourse
    : deriveTeacherModulesFromLessonPlans(data.lessonPlansByCourse);

  return (
    <div className="curator-workspace__section-stack">
      <section className="curator-workspace__card">
        <div className="curator-workspace__panel-heading">
          <div>
            <span className="curator-workspace__eyebrow">Course structure</span>
            <h3>Courses, modules, lessons, and instructor actions</h3>
          </div>
          <p>Course-first delivery view: open one assigned course at a time, then manage lesson documents, live starts, notebook practice, and cohort visibility from the same workspace.</p>
        </div>
        <CuratorCourseDeliveryAccordion
          courses={data.courses}
          courseModulesByCourse={modulesByCourse}
          materials={data.materials}
          cohorts={data.cohorts}
        />
      </section>
    </div>
  );
};

const CourseCard = ({ course }: { course: TeacherWorkspaceCourse }) => (
  <article className="curator-workspace__list-card">
    <span className="curator-workspace__badge">{course.slug}</span>
    <h3>{course.titleEn || course.titleDe}</h3>
    <p>{course.descriptionEn || course.descriptionDe || "No description provided yet."}</p>
    <div className="curator-workspace__meta-grid">
      <div>
        <strong>{course.studentsCount}</strong>
        <span>Learners</span>
      </div>
      <div>
        <strong>{course.cohortsCount}</strong>
        <span>Cohorts</span>
      </div>
      <div>
        <strong>{course.sessionsCount}</strong>
        <span>Sessions</span>
      </div>
      <div>
        <strong>{formatPercent(course.attendancePercent)}</strong>
        <span>Attendance</span>
      </div>
    </div>
    <div className="curator-workspace__meta-stack">
      <span>{course.materialsCount} materials</span>
      <span>{course.recordingsCount} recordings</span>
      <span>Next session {formatDateTime(course.nearestSessionAt)}</span>
    </div>
  </article>
);

const RecordingRow = ({ recording }: { recording: TeacherWorkspaceRecording }) => (
  <article className="curator-workspace__row-card">
    <div>
      <strong>{recording.title}</strong>
      <p>{recording.courseTitleEn || recording.courseTitleDe}</p>
    </div>
    <div className="curator-workspace__row-meta">
      <span>{recording.groupCode}</span>
      <span>{formatDateTime(recording.startsAt)}</span>
      {recording.recordingUrl ? (
        <a className="curator-workspace__inline-link" href={recording.recordingUrl} target="_blank" rel="noreferrer">
          Open recording
        </a>
      ) : (
        <span>No link</span>
      )}
    </div>
  </article>
);

const PortfolioSection = () => {
  const { data, isLoading, isError } = useGetTeacherWorkspaceQuery();

  if (isLoading) {
    return <p className="curator-workspace__empty-copy">Loading delivery overview...</p>;
  }

  if (isError || !data) {
    return <p className="curator-workspace__error-copy">Failed to load delivery overview.</p>;
  }

  return (
    <div className="curator-workspace__section-stack">
      <section className="curator-workspace__card">
        <div className="curator-workspace__panel-heading">
          <div>
            <span className="curator-workspace__eyebrow">Assigned courses</span>
            <h3>Delivery overview</h3>
          </div>
          <p>All active courses currently attached to your teaching responsibility.</p>
        </div>
          <div className="curator-workspace__list-grid curator-workspace__list-grid--courses">
            {data.courses.length === 0 ? (
              <p className="curator-workspace__empty-copy">No courses are assigned to this instructor.</p>
            ) : null}
          {data.courses.map((course) => (
            <CourseCard key={course.id} course={course} />
          ))}
        </div>
      </section>

      <section className="curator-workspace__card">
        <div className="curator-workspace__panel-heading">
          <div>
            <span className="curator-workspace__eyebrow">Recent recordings</span>
            <h3>Recording library</h3>
          </div>
          <p>Recorded sessions currently linked to the same teaching scope.</p>
        </div>
        <div className="curator-workspace__row-stack">
          {data.recordings.length === 0 ? (
            <p className="curator-workspace__empty-copy">No recordings are currently linked to your teaching scope.</p>
          ) : null}
          {data.recordings.slice(0, 8).map((recording) => (
            <RecordingRow key={recording.id} recording={recording} />
          ))}
        </div>
      </section>
    </div>
  );
};

const FeedbackSection = () => {
  const { data, isLoading, isError } = useGetTeacherWorkspaceQuery();
  const [submitFeedback, submitState] = useSubmitTeacherFeedbackMutation();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [courseSlug, setCourseSlug] = useState("");
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  if (isLoading) {
    return <p className="curator-workspace__empty-copy">Loading feedback form...</p>;
  }

  if (isError || !data) {
    return <p className="curator-workspace__error-copy">Failed to load feedback form.</p>;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSuccess("");
    setError("");
    try {
      const response = await submitFeedback({
        subject: subject.trim(),
        message: message.trim(),
        course_slug: courseSlug || undefined,
      }).unwrap();
      setSuccess(`Feedback sent on ${formatDateTime(response.createdAt)}.`);
      setSubject("");
      setMessage("");
      setCourseSlug("");
    } catch (submitError) {
      setError(resolveApiErrorMessage(submitError, "Failed to send feedback."));
    }
  };

  return (
    <section className="curator-workspace__card">
      <div className="curator-workspace__panel-heading">
        <div>
          <span className="curator-workspace__eyebrow">Escalation</span>
          <h3>Send operational feedback</h3>
        </div>
        <p>Use this form for delivery blockers, content issues, or cross-team operational requests.</p>
      </div>
      <form className="curator-workspace__form" onSubmit={handleSubmit}>
        <label>
          <span>Course</span>
          <select value={courseSlug} onChange={(event) => setCourseSlug(event.currentTarget.value)}>
            <option value="">General academy topic</option>
            {data.courses.map((course) => (
              <option key={course.id} value={course.slug}>
                {course.titleEn || course.titleDe}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Subject</span>
          <input type="text" value={subject} onChange={(event) => setSubject(event.currentTarget.value)} />
        </label>
        <label>
          <span>Message</span>
          <textarea rows={7} value={message} onChange={(event) => setMessage(event.currentTarget.value)} />
        </label>
        {error ? <p className="curator-workspace__notice curator-workspace__notice--error">{error}</p> : null}
        {success ? <p className="curator-workspace__notice curator-workspace__notice--success">{success}</p> : null}
        <button type="submit" className="curator-workspace__primary-action" disabled={submitState.isLoading}>
          {submitState.isLoading ? "Sending..." : "Send feedback"}
        </button>
      </form>
    </section>
  );
};

export const CuratorWorkspacePage = ({ section }: WorkspacePageProps) => {
  const { logout, profile } = useAuth();
  const { data } = useGetTeacherWorkspaceQuery();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(SIDEBAR_STATE_KEY) === "1";
  });

  const navItems: NavItem[] = [
    { id: "home", label: "Home", href: "/home", icon: <HomeIcon /> },
    { id: "documents", label: "Courses", href: "/courses", icon: <DocumentsIcon /> },
    { id: "portfolio", label: "Delivery", href: "/delivery", icon: <PortfolioIcon /> },
    { id: "online", label: "Online", href: "/online", icon: <OnlineIcon /> },
    { id: "calendar", label: "Calendar", href: "/calendar", icon: <CalendarIcon /> },
    { id: "information", label: "Information", href: "/information", icon: <InformationIcon /> },
    { id: "feedback", label: "Feedback", href: "/feedback", icon: <FeedbackIcon /> },
  ];

  const sectionContent: Record<WorkspaceSection, JSX.Element> = {
    home: <CuratorHomeSection />,
    documents: <DocumentsSection />,
    portfolio: <PortfolioSection />,
    online: <OnlinePage embedded />,
    calendar: <OnlinePage embedded calendarOnly showExternalCalendarLinks />,
    information: <CuratorInformationSection />,
    feedback: <FeedbackSection />,
  };

  const sectionMeta = SECTION_META[section];
  const sidebarTitle = data?.profile.fullName || profile?.fullName || "Instructor";
  const sidebarEmail = data?.profile.schoolEmail || profile?.email || "";
  const avatarLetter = (data?.profile.firstName?.[0] || profile?.firstName?.[0] || sidebarTitle[0] || "C").toUpperCase();

  const handleToggleSidebar = () => {
    setIsSidebarCollapsed((current) => {
      const nextValue = !current;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(SIDEBAR_STATE_KEY, nextValue ? "1" : "0");
      }
      return nextValue;
    });
  };

  return (
    <main className="curator-workspace">
      <div className="curator-workspace__layout">
        <aside
          className={`curator-workspace__sidebar ${isSidebarCollapsed ? "curator-workspace__sidebar--collapsed" : ""}`}
        >
          <div className="curator-workspace__brand-block">
            <div className="curator-workspace__brand-copy">
              <p className="curator-workspace__brand-eyebrow">Internal academy</p>
              <strong className="curator-workspace__brand-title">Instructor Workspace</strong>
            </div>
            <button
              type="button"
              className="curator-workspace__sidebar-toggle"
              onClick={handleToggleSidebar}
              aria-label={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-pressed={isSidebarCollapsed}
              title={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              <SidebarToggleIcon collapsed={isSidebarCollapsed} />
            </button>
          </div>

          <div className="curator-workspace__profile-card" title={isSidebarCollapsed ? sidebarTitle : undefined}>
            <div className="curator-workspace__profile-avatar">
              <span>{avatarLetter}</span>
            </div>
            <div className="curator-workspace__profile-copy">
              <p>{sidebarTitle}</p>
              <span>{sidebarEmail}</span>
            </div>
          </div>

          <nav className="curator-workspace__nav" aria-label="Instructor workspace navigation">
            {navItems.map((item) => (
              <NavLink
                key={item.id}
                to={item.href}
                title={isSidebarCollapsed ? item.label : undefined}
                className={({ isActive }) =>
                  `curator-workspace__nav-link ${isActive ? "curator-workspace__nav-link--active" : ""}`
                }
              >
                <span className="curator-workspace__nav-icon">{item.icon}</span>
                <span className="curator-workspace__nav-label">{item.label}</span>
              </NavLink>
            ))}
            <button
              type="button"
              className="curator-workspace__logout"
              onClick={logout}
              title={isSidebarCollapsed ? "Sign out" : undefined}
            >
              <span className="curator-workspace__nav-icon">
                <LogoutIcon />
              </span>
              <span className="curator-workspace__logout-label">Sign out</span>
            </button>
          </nav>
        </aside>

        <section className="curator-workspace__content">
          <header className="curator-workspace__hero">
            <div className="curator-workspace__hero-copy">
              <h1>{sectionMeta.title}</h1>
              <p>{sectionMeta.subtitle}</p>
            </div>
            <div className="curator-workspace__hero-meta">
              <span>English only</span>
              <span>Instructor access</span>
            </div>
          </header>

          <section className="curator-workspace__panel">{sectionContent[section]}</section>
        </section>
      </div>
    </main>
  );
};
