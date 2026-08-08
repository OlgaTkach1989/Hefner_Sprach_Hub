import { useEffect, useMemo, useState } from "react";
import { useHref } from "react-router-dom";

import type { CourseLessonPlanItem, CourseModulePlanItem } from "../../types";

type Props = {
  courseTitle: string;
  modules: CourseModulePlanItem[];
  emptyMessage: string;
};

type LessonUiStatus = "active" | "locked" | "completed";
type LessonProgressSnapshot = {
  progressPercent: number;
  hasStarted: boolean;
  isCompleted: boolean;
};

type LessonUiModel = {
  lesson: CourseLessonPlanItem;
  lessonDisplayNumber: string;
  stepCount: number;
  status: LessonUiStatus;
  progressPercent: number;
  scheduleLabel: string;
};

type ModuleUiModel = {
  module: CourseModulePlanItem;
  moduleIndex: number;
  moduleLabel: string;
  moduleTitle: string;
  moduleMeta: string[];
  moduleStatus: LessonUiStatus;
  moduleProgressPercent: number;
  lessons: LessonUiModel[];
};

const lessonStorageKeyOf = (lessonId: number) => `learning-hub:learner-lesson:${lessonId}`;

const moduleKeyOf = (module: CourseModulePlanItem, moduleIndex: number) =>
  `module_${module.id ?? moduleIndex}_${module.sortOrder}`;

const splitModuleHeading = (value: string) => {
  const dividerIndex = value.indexOf(" - ");
  if (dividerIndex <= 0) {
    return { prefix: value, title: "" };
  }
  return {
    prefix: value.slice(0, dividerIndex),
    title: value.slice(dividerIndex + 3),
  };
};

const lessonStepCount = (lesson: CourseLessonPlanItem) =>
  lesson.interactiveLesson?.steps.length
  ?? lesson.sections.reduce((count, section) => count + section.items.length, 0);

const parseDateValue = (value?: string | null) => {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

const compactGroupLabel = (value?: string | null) => {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) return "";
  const parts = trimmed
    .split(" - ")
    .map((part) => part.trim())
    .filter(Boolean);
  return parts[parts.length - 1] || trimmed;
};

const formatShortDate = (value?: string | null) => {
  const parsed = parseDateValue(value);
  if (!parsed) return "";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(parsed);
};

const formatDurationShort = (startValue?: string | null, endValue?: string | null) => {
  const start = parseDateValue(startValue);
  const end = parseDateValue(endValue);
  if (!start || !end) return "";
  const diffMinutes = Math.max(0, Math.round((end.getTime() - start.getTime()) / 60000));
  if (diffMinutes <= 0) return "";
  const hours = Math.floor(diffMinutes / 60);
  const minutes = diffMinutes % 60;
  if (hours > 0 && minutes > 0) return `${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h`;
  return `${minutes}m`;
};

const formatLessonScheduleCompact = (lesson: CourseLessonPlanItem) => {
  const parts = [formatShortDate(lesson.startsAt), formatDurationShort(lesson.startsAt, lesson.endsAt)].filter(Boolean);
  return parts.join(" • ");
};

const formatModuleScheduleCompact = (module: CourseModulePlanItem) => {
  const startLabel = formatShortDate(module.startsAt);
  const endLabel = formatShortDate(module.endsAt);
  if (startLabel && endLabel && startLabel !== endLabel) {
    return `${startLabel} - ${endLabel}`;
  }
  return startLabel || endLabel;
};

const buildModuleLabel = (module: CourseModulePlanItem, moduleIndex: number) => {
  if (module.moduleType === "final_assessment") {
    return "Final assessment";
  }
  return `Module ${moduleIndex + 1}`;
};

const readLessonProgressSnapshot = (lesson: CourseLessonPlanItem): LessonProgressSnapshot => {
  const stepIds = lesson.interactiveLesson?.steps.map((step) => step.id) ?? [];
  const serverProgress = lesson.progress;
  if (stepIds.length === 0) {
    return {
      progressPercent: serverProgress?.progressPercent ?? 0,
      hasStarted: (serverProgress?.progressPercent ?? 0) > 0,
      isCompleted: Boolean(serverProgress?.completedAt || (serverProgress?.progressPercent ?? 0) >= 100),
    };
  }
  let localSnapshot: LessonProgressSnapshot = {
    progressPercent: 0,
    hasStarted: false,
    isCompleted: false,
  };
  if (typeof window !== "undefined") {
    const rawState = window.localStorage.getItem(lessonStorageKeyOf(lesson.id));
    if (rawState) {
      try {
        const parsed = JSON.parse(rawState) as {
          activeStepId?: string;
          completedStepIds?: string[];
        };
        const completedStepIds = Array.isArray(parsed.completedStepIds)
          ? [...new Set(parsed.completedStepIds.filter((stepId) => stepIds.includes(stepId)))]
          : [];
        const hasValidActiveStep = typeof parsed.activeStepId === "string" && stepIds.includes(parsed.activeStepId);
        const isCompleted = completedStepIds.length >= stepIds.length;
        const hasStarted = isCompleted || hasValidActiveStep || completedStepIds.length > 0;
        let progressPercent = stepIds.length > 0
          ? Math.round((completedStepIds.length / stepIds.length) * 100)
          : 0;

        if (!isCompleted && hasStarted) {
          progressPercent = Math.max(progressPercent, 12);
        }
        localSnapshot = {
          progressPercent: Math.max(0, Math.min(100, progressPercent)),
          hasStarted,
          isCompleted,
        };
      } catch {
        localSnapshot = {
          progressPercent: 0,
          hasStarted: false,
          isCompleted: false,
        };
      }
    }
  }

  const serverSnapshot: LessonProgressSnapshot = {
    progressPercent: Math.max(0, Math.min(100, serverProgress?.progressPercent ?? 0)),
    hasStarted: Boolean((serverProgress?.progressPercent ?? 0) > 0 || serverProgress?.activeStepId),
    isCompleted: Boolean(serverProgress?.completedAt || (serverProgress?.progressPercent ?? 0) >= 100),
  };

  return serverSnapshot.progressPercent >= localSnapshot.progressPercent ? serverSnapshot : localSnapshot;
};

const moduleProgressContribution = (status: LessonUiStatus, progressPercent: number) => {
  if (status === "completed") return 100;
  if (status === "active") return Math.max(progressPercent, 60);
  return 0;
};

const lessonActionLabel = (status: LessonUiStatus, hasStarted: boolean) => {
  if (status === "locked") return "Locked";
  if (status === "completed") return "Review Lesson";
  if (hasStarted) return "Continue Lesson";
  return "Start Lesson";
};

const lessonStatusLabel = (status: LessonUiStatus) => {
  if (status === "completed") return "Completed";
  if (status === "locked") return "Locked";
  return "Active";
};

const LessonAction = ({
  lesson,
  status,
  hasStarted,
}: {
  lesson: CourseLessonPlanItem;
  status: LessonUiStatus;
  hasStarted: boolean;
}) => {
  const lessonHref = useHref(`/lessons/${lesson.id}`);
  const actionLabel = lessonActionLabel(status, hasStarted);

  if (status === "locked") {
    return (
      <button
        type="button"
        className="dashboard-page__course-structure-action dashboard-page__course-structure-action--locked"
        disabled
      >
        {actionLabel}
      </button>
    );
  }

  return (
    <a
      href={lessonHref}
      target="_blank"
      rel="noreferrer"
      className="dashboard-page__course-structure-action dashboard-page__course-structure-action--primary"
      aria-label={`Open ${lesson.title} in a new tab`}
    >
      {actionLabel}
    </a>
  );
};

export const CourseStructureTree = ({ courseTitle, modules, emptyMessage }: Props) => {
  const [expandedModules, setExpandedModules] = useState<Record<string, boolean>>({});
  const [lessonProgressMap, setLessonProgressMap] = useState<Record<number, LessonProgressSnapshot>>({});

  useEffect(() => {
    const syncProgress = () => {
      const nextProgressMap: Record<number, LessonProgressSnapshot> = {};
      for (const module of modules) {
        for (const lesson of module.lessons) {
          nextProgressMap[lesson.id] = readLessonProgressSnapshot(lesson);
        }
      }
      setLessonProgressMap(nextProgressMap);
    };

    syncProgress();

    window.addEventListener("focus", syncProgress);
    window.addEventListener("storage", syncProgress);
    return () => {
      window.removeEventListener("focus", syncProgress);
      window.removeEventListener("storage", syncProgress);
    };
  }, [modules]);

  const toggleModule = (key: string) => {
    setExpandedModules((current) => ({ ...current, [key]: !(current[key] ?? true) }));
  };

  const moduleModels = useMemo<ModuleUiModel[]>(() => {
    const rawModules = modules.map((module, moduleIndex) => {
      const moduleHeading = splitModuleHeading(module.title);
      const nextLessonIndex = module.lessons.findIndex((lesson) => !(lessonProgressMap[lesson.id]?.isCompleted ?? false));
      const moduleMeta = [
        formatModuleScheduleCompact(module),
        `${module.lessons.length} lesson${module.lessons.length === 1 ? "" : "s"}`,
        compactGroupLabel(module.groupName || module.groupCode),
      ].filter(Boolean);

      return {
        module,
        moduleIndex,
        moduleHeading,
        nextLessonIndex: nextLessonIndex >= 0 ? nextLessonIndex : module.lessons.length,
        hasStartedLesson: module.lessons.some((lesson) => lessonProgressMap[lesson.id]?.hasStarted),
        isCompleted: module.lessons.length > 0
          && module.lessons.every((lesson) => lessonProgressMap[lesson.id]?.isCompleted),
        moduleMeta,
      };
    });

    return rawModules.map((moduleEntry) => {
      const { module, moduleIndex, moduleHeading, nextLessonIndex, isCompleted, moduleMeta } = moduleEntry;
      const moduleStatus: LessonUiStatus = isCompleted ? "completed" : "active";

      const lessons = module.lessons.map((lesson, lessonIndex) => {
        const progressSnapshot = lessonProgressMap[lesson.id] ?? {
          progressPercent: 0,
          hasStarted: false,
          isCompleted: false,
        };
        let status: LessonUiStatus = "active";
        if (progressSnapshot.isCompleted || lessonIndex < nextLessonIndex) {
          status = "completed";
        } else if (progressSnapshot.hasStarted) {
          status = "active";
        }

        return {
          lesson,
          lessonDisplayNumber: `${moduleIndex + 1}.${lessonIndex + 1}`,
          stepCount: lessonStepCount(lesson),
          status,
          progressPercent: progressSnapshot.progressPercent,
          scheduleLabel: formatLessonScheduleCompact(lesson),
        };
      });

      const moduleProgressPercent = lessons.length > 0
        ? Math.round(
          lessons.reduce(
            (sum, lesson) => sum + moduleProgressContribution(lesson.status, lesson.progressPercent),
            0,
          ) / lessons.length,
        )
        : 0;

      return {
        module,
        moduleIndex,
        moduleLabel: buildModuleLabel(module, moduleIndex),
        moduleTitle: moduleHeading.title || module.title,
        moduleMeta,
        moduleStatus,
        moduleProgressPercent,
        lessons,
      };
    });
  }, [lessonProgressMap, modules]);

  if (modules.length === 0) {
    return <p className="dashboard-page__lesson-empty">{emptyMessage}</p>;
  }

  return (
    <div className="dashboard-page__lesson-plan" aria-label={`${courseTitle} course structure`}>
      <section className="dashboard-page__course-progress-card" aria-label="Course progress">
        <div>
          <h4 className="dashboard-page__lesson-plan-title">{courseTitle || "Deutsch A1 — Мій курс"}</h4>
          <p>
            Автор: Anna Hefner · Hefner Sprach Hub · {modules.length} Модулi ·{" "}
            {moduleModels.reduce((sum, moduleModel) => sum + moduleModel.lessons.length, 0)} Урокiв
          </p>
        </div>
      </section>
      {moduleModels.map((moduleModel) => {
        const moduleKey = moduleKeyOf(moduleModel.module, moduleModel.moduleIndex);
        const isModuleOpen = expandedModules[moduleKey] ?? true;
        const completedLessons = moduleModel.lessons.filter((lessonModel) => lessonModel.status === "completed").length;
        const totalLessons = moduleModel.lessons.length;

        return (
          <article
            key={moduleKey}
            className={`dashboard-page__course-structure-card dashboard-page__course-structure-card--${moduleModel.moduleStatus}`}
          >
            <button
              type="button"
              className="dashboard-page__course-structure-toggle"
              onClick={() => toggleModule(moduleKey)}
              aria-expanded={isModuleOpen}
            >
              <div className="dashboard-page__course-structure-header">
                <span className="dashboard-page__course-structure-number" aria-hidden="true">
                  {moduleModel.moduleStatus === "locked" ? "Lock" : moduleModel.moduleIndex + 1}
                </span>
                <div className="dashboard-page__course-structure-main">
                  <div className="dashboard-page__course-structure-topline">
                    <span className="dashboard-page__course-structure-kicker">
                      Modul {moduleModel.moduleIndex + 1} · Модуль {moduleModel.moduleIndex + 1}
                    </span>
                    {moduleModel.moduleStatus === "locked" ? (
                      <span className="dashboard-page__course-structure-week">Заблоковано</span>
                    ) : null}
                  </div>
                  <strong className="dashboard-page__course-structure-title">{moduleModel.moduleTitle}</strong>
                  <p className="dashboard-page__course-structure-summary">
                    {moduleModel.module.description || "Structured learning module"}
                  </p>
                  {moduleModel.moduleMeta.length > 0 ? (
                    <div className="dashboard-page__course-structure-meta">
                      {moduleModel.moduleMeta.map((value) => (
                        <span key={`${moduleKey}_${value}`} className="dashboard-page__course-structure-meta-item">
                          {value}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>

                <div className="dashboard-page__course-structure-side">
                  <strong>{completedLessons}/{totalLessons}</strong>
                  <span>урокiв</span>
                  <span
                    className={`dashboard-page__course-structure-chevron ${isModuleOpen ? "is-open" : ""}`}
                    aria-hidden="true"
                  >
                    v
                  </span>
                </div>
              </div>
            </button>

            {isModuleOpen ? (
              <div className="dashboard-page__course-structure-lessons">
                {moduleModel.lessons.map((lessonModel, lessonIndex) => (
                  <section key={lessonModel.lesson.id} className="dashboard-page__course-structure-lesson">
                    <span className={`dashboard-page__course-structure-lesson-number dashboard-page__course-structure-lesson-number--${lessonModel.status}`}>
                      {lessonModel.status === "locked" ? "Lock" : lessonIndex + 1}
                    </span>
                    <div className="dashboard-page__course-structure-lesson-main">
                      <div className="dashboard-page__course-structure-lesson-topline">
                        <span className="dashboard-page__course-structure-lesson-kicker">{lessonStatusLabel(lessonModel.status)}</span>
                      </div>
                      <strong className="dashboard-page__course-structure-lesson-title">{lessonModel.lesson.title}</strong>
                      <div className="dashboard-page__course-structure-lesson-meta">
                        {lessonModel.scheduleLabel ? (
                          <span className="dashboard-page__course-structure-lesson-meta-item">
                            {lessonModel.scheduleLabel}
                          </span>
                        ) : null}
                        <span className="dashboard-page__course-structure-lesson-meta-item">
                          {lessonModel.stepCount} step{lessonModel.stepCount === 1 ? "" : "s"}
                        </span>
                      </div>
                    </div>

                    <div className="dashboard-page__course-structure-lesson-side">
                      <LessonAction
                        lesson={lessonModel.lesson}
                        status={lessonModel.status}
                        hasStarted={lessonModel.progressPercent > 0}
                      />
                    </div>
                  </section>
                ))}
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
};

export default CourseStructureTree;
