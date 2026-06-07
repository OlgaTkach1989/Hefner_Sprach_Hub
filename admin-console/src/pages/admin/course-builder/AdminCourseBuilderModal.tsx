import { useEffect, useMemo, useState } from "react";

import {
  useCreateCourseBuilderSessionsMutation,
  useCreateCourseBuilderCourseMutation,
  useGenerateCourseBuilderLessonMutation,
  useImportCourseBuilderCourseMutation,
  useCreateCourseBuilderLibraryItemMutation,
  useDeleteCourseBuilderLibraryItemMutation,
  useGetCourseBuilderCourseQuery,
  useGetCourseBuilderLibraryQuery,
  useGetCourseBuilderNotebooksQuery,
  useGetCourseBuilderTemplatesQuery,
  useGenerateCourseBuilderLessonFromVideoMutation,
  useSaveCourseBuilderDeliveryAssignmentMutation,
  useUpdateCourseBuilderCourseMutation,
  useUpdateCourseBuilderLibraryItemMutation,
} from "@/bll/course-builder/courseBuilder.service";
import { useGetOnlineAdminCuratorsQuery, useGetOnlineAdminSessionsQuery, useGetOnlineCohortsQuery } from "@/bll/online/online.service";
import { useGetOnlineAdminWorkspacesQuery } from "@/bll/site/site.service";
import { useGetTrainingAdminAudiencesQuery } from "@/bll/training/training.service";
import type { CourseBuilderCourse, CourseBuilderSectionType } from "@/bll/course-builder/courseBuilder.type";
import type {
  CourseBuilderCourseDraft,
  CourseBuilderDeliveryDraft,
  CourseBuilderDeliverySessionDraft,
  CourseBuilderDeliverySessionsDraft,
  CourseBuilderLibraryDraft,
  CourseBuilderLessonDraft,
  CourseBuilderModuleDraft,
  CourseBuilderSectionDraft,
  CourseBuilderSectionItemDraft,
} from "./courseBuilderState";
import {
  buildDeliverySessionDrafts,
  createBlankCourseDraft,
  createBlankDeliveryDraft,
  createBlankDeliverySessionsDraft,
  createBlankLibraryDraft,
  courseDraftFromCourse,
  courseDraftFromTemplate,
  libraryDraftFromItem,
  normalizeCourseLanguage,
  serializeCourseDraft,
} from "./courseBuilderState";
import CourseBuilderBasicsPanel from "./CourseBuilderBasicsPanel";
import CourseBuilderDeliveryPanel from "./CourseBuilderDeliveryPanel";
import CourseBuilderLessonsPanel, { type LessonGeneratorDraft } from "./CourseBuilderLessonsPanel";
import CourseBuilderLibraryPanel from "./CourseBuilderLibraryPanel";
import CourseBuilderTemplatePanel from "./CourseBuilderTemplatePanel";
import CollapsibleSection from "./CollapsibleSection";
import type { ImportedLessonDocument } from "./lessonDocumentBlueprints";
import styles from "./AdminCourseBuilderModal.module.css";

type CourseBuilderMode = "create" | "edit";
type BuilderStep = "template" | "basics" | "lessons" | "library" | "review" | "delivery";

type Props = {
  isOpen: boolean;
  inline?: boolean;
  mode: CourseBuilderMode;
  courseId?: number | null;
  initialTemplateId?: number | null;
  initialStep?: BuilderStep;
  onClose: () => void;
  onSaved: (course: CourseBuilderCourse) => void;
};

const STEP_LABELS: Record<BuilderStep, { title: string; description: string }> = {
  template: {
    title: "Template",
    description: "Start from a reusable course skeleton.",
  },
  basics: {
    title: "Basics",
    description: "Edit the public identity and publishing fields.",
  },
  lessons: {
    title: "Lessons",
    description: "Shape the lesson list and section content.",
  },
  library: {
    title: "Library",
    description: "Create reusable items and notebook references.",
  },
  review: {
    title: "Review",
    description: "Check the resulting structure before saving.",
  },
  delivery: {
    title: "Delivery",
    description: "Create the initial cohort and assign an instructor.",
  },
};

const stepSectionId = (step: BuilderStep) => `course-builder-step-${step}`;

const errorMessageFrom = (error: unknown, fallback: string) => {
  if (!error || typeof error !== "object" || !("data" in error)) return fallback;
  const payload = (error as { data?: unknown }).data;
  if (!payload || typeof payload !== "object") return fallback;
  const objectPayload = payload as Record<string, unknown>;
  if (typeof objectPayload.detail === "string") return objectPayload.detail;
  if (typeof objectPayload.status === "string") return objectPayload.status;
  for (const value of Object.values(objectPayload)) {
    if (typeof value === "string") return value;
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
  }
  return fallback;
};

const cloneDraft = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

const makeClientId = (prefix: string) =>
  `${prefix}-${crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2, 10)}`;

const LESSON_SECTION_ORDER: CourseBuilderSectionType[] = ["main"];

const DEFAULT_SECTION_TITLES: Record<CourseBuilderSectionType, string> = {
  introduction: "Introduction",
  main: "Main content",
  conclusion: "Conclusion",
};

const buildBlankLessonSections = () =>
  LESSON_SECTION_ORDER.map((sectionType, sectionIndex) => ({
    clientId: makeClientId("section"),
    id: undefined,
    sectionType,
    title: DEFAULT_SECTION_TITLES[sectionType],
    description: "",
    sortOrder: sectionIndex === 0 ? 10 : sectionIndex === 1 ? 20 : 30,
    isActive: true,
    items: [],
  }));

const toDateInputValueFromIso = (value: string | null | undefined) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
};

const localDateTimeToIso = (value: string) => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toISOString();
};

const countDraftItems = (draft: CourseBuilderCourseDraft) => {
  let items = 0;
  let notebooks = 0;
  let documents = 0;
  for (const lesson of draft.lessons) {
    for (const section of lesson.sections) {
      for (const item of section.items) {
        items += 1;
        if (item.assetType === "notebook") notebooks += 1;
        if (item.assetType === "document") documents += 1;
      }
    }
  }
  return { modules: draft.modules.length, lessons: draft.lessons.length, items, notebooks, documents };
};

const buildLibrarySeed = (sectionType: CourseBuilderSectionType): CourseBuilderLibraryDraft =>
  createBlankLibraryDraft(sectionType);

const AdminCourseBuilderModal = ({
  isOpen,
  inline,
  mode,
  courseId,
  initialTemplateId,
  initialStep,
  onClose,
  onSaved,
}: Props) => {
  const templateStepAvailable = mode === "create";
  const stepOrder: BuilderStep[] = templateStepAvailable
    ? ["template", "basics", "lessons", "library", "review", "delivery"]
    : ["basics", "lessons", "library", "review", "delivery"];
  const [activeStep, setActiveStep] = useState<BuilderStep>(initialStep ?? (templateStepAvailable ? "template" : "basics"));
  const [courseDraft, setCourseDraft] = useState<CourseBuilderCourseDraft>(createBlankCourseDraft());
  const [persistedCourseId, setPersistedCourseId] = useState<number | null>(mode === "edit" ? (courseId ?? null) : null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [selectedLibraryItemId, setSelectedLibraryItemId] = useState<number | null>(null);
  const [libraryDraft, setLibraryDraft] = useState<CourseBuilderLibraryDraft>(buildLibrarySeed("main"));
  const [deliveryDraft, setDeliveryDraft] = useState<CourseBuilderDeliveryDraft>(createBlankDeliveryDraft());
  const [deliverySessionsDraft, setDeliverySessionsDraft] = useState<CourseBuilderDeliverySessionsDraft>(
    createBlankDeliverySessionsDraft(),
  );
  const [builderError, setBuilderError] = useState<string | null>(null);
  const [builderMessage, setBuilderMessage] = useState<string | null>(null);
  const [deliveryError, setDeliveryError] = useState<string | null>(null);
  const [deliveryMessage, setDeliveryMessage] = useState<string | null>(null);
  const [deliverySessionsError, setDeliverySessionsError] = useState<string | null>(null);
  const [deliverySessionsMessage, setDeliverySessionsMessage] = useState<string | null>(null);
  const [importJsonDraft, setImportJsonDraft] = useState("");
  const effectiveCourseId = mode === "edit" ? (courseId ?? null) : persistedCourseId;
  const isPersistedCourse = Boolean(effectiveCourseId);
  const isVisible = isOpen || Boolean(inline);

  const {
    data: templateData,
    isLoading: isTemplatesLoading,
    isError: isTemplatesError,
  } = useGetCourseBuilderTemplatesQuery(undefined, { skip: !isVisible });
  const templates = useMemo(() => templateData?.results ?? [], [templateData]);

  const {
    data: libraryData,
    isLoading: isLibraryLoading,
    isError: isLibraryError,
  } = useGetCourseBuilderLibraryQuery(undefined, { skip: !isVisible });
  const libraryItems = useMemo(() => libraryData?.results ?? [], [libraryData]);

  const {
    data: notebookData,
    isLoading: isNotebooksLoading,
    isError: isNotebooksError,
  } = useGetCourseBuilderNotebooksQuery(effectiveCourseId ? { courseId: effectiveCourseId } : undefined, { skip: !isVisible });
  const notebookOptions = useMemo(() => notebookData?.results ?? [], [notebookData]);

  const {
    data: courseData,
  } = useGetCourseBuilderCourseQuery(effectiveCourseId as number, { skip: !isVisible || !effectiveCourseId });
  const governance = courseData?.governance ?? null;

  const {
    data: cohortsData,
    isLoading: isCohortsLoading,
    refetch: refetchCohorts,
  } = useGetOnlineCohortsQuery(effectiveCourseId ? { courseId: effectiveCourseId } : undefined, {
    skip: !isVisible || !effectiveCourseId,
  });
  const courseCohorts = useMemo(() => cohortsData?.results ?? [], [cohortsData]);

  const {
    data: cohortSessionsData,
    isLoading: isCohortSessionsLoading,
    refetch: refetchCohortSessions,
  } = useGetOnlineAdminSessionsQuery(deliveryDraft.cohortId ? { cohortId: deliveryDraft.cohortId } : undefined, {
    skip: !isVisible || !deliveryDraft.cohortId,
  });
  const cohortSessions = useMemo(() => cohortSessionsData?.results ?? [], [cohortSessionsData]);

  const {
    data: curatorsData,
    isLoading: isCuratorsLoading,
    refetch: refetchCurators,
  } = useGetOnlineAdminCuratorsQuery(undefined, { skip: !isVisible });
  const curators = useMemo(() => curatorsData?.results ?? [], [curatorsData]);
  const { data: audienceData } = useGetTrainingAdminAudiencesQuery(undefined, { skip: !isVisible });
  const audiences = useMemo(() => audienceData?.results ?? [], [audienceData]);
  const { data: workspaceData } = useGetOnlineAdminWorkspacesQuery(undefined, { skip: !isVisible });
  const workspaces = useMemo(() => workspaceData?.results ?? [], [workspaceData]);

  const [createCourseBuilderCourse, { isLoading: isCreatingCourse }] = useCreateCourseBuilderCourseMutation();
  const [importCourseBuilderCourse, { isLoading: isImportingCourse }] = useImportCourseBuilderCourseMutation();
  const [generateCourseBuilderLesson] = useGenerateCourseBuilderLessonMutation();
  const [generateCourseBuilderLessonFromVideo] = useGenerateCourseBuilderLessonFromVideoMutation();
  const [updateCourseBuilderCourse, { isLoading: isUpdatingCourse }] = useUpdateCourseBuilderCourseMutation();
  const [createLibraryItem, { isLoading: isCreatingLibraryItem }] = useCreateCourseBuilderLibraryItemMutation();
  const [updateLibraryItem, { isLoading: isUpdatingLibraryItem }] = useUpdateCourseBuilderLibraryItemMutation();
  const [deleteLibraryItem, { isLoading: isDeletingLibraryItem }] = useDeleteCourseBuilderLibraryItemMutation();
  const [saveCourseBuilderDeliveryAssignment, { isLoading: isSavingDelivery }] =
    useSaveCourseBuilderDeliveryAssignmentMutation();
  const [createCourseBuilderSessions, { isLoading: isCreatingDeliverySessions }] =
    useCreateCourseBuilderSessionsMutation();

  const isSavingCourse = isCreatingCourse || isUpdatingCourse || isImportingCourse;
  const isSavingLibraryItem = isCreatingLibraryItem || isUpdatingLibraryItem;
  const lessonBlueprints = useMemo(
    () =>
      [...courseDraft.lessons]
        .filter((lesson) => lesson.isActive)
        .sort((left, right) => left.sortOrder - right.sortOrder)
        .map((lesson) => ({
          title: lesson.title.trim(),
          description: lesson.description.trim(),
          sections: [...lesson.sections]
            .filter((section) => section.isActive)
            .sort((left, right) => left.sortOrder - right.sortOrder)
            .map((section) => ({
              sectionType: section.sectionType,
              title: section.title.trim(),
              description: section.description.trim(),
              itemCount: section.items.filter((item) => item.isActive).length,
            })),
        })),
    [courseDraft.lessons],
  );
  const remainingSessionSlots = Math.max(0, lessonBlueprints.length - cohortSessions.length);
  const sessionSeedResetKey = useMemo(() => {
    const lastSessionStart = cohortSessions.length ? cohortSessions[cohortSessions.length - 1]?.startsAt || "" : "";
    return JSON.stringify({
      cohortId: deliveryDraft.cohortId ?? 0,
      startDate: deliveryDraft.startDate || "",
      lessonTitles: lessonBlueprints.map((lesson) => lesson.title).join("|"),
      existingCount: cohortSessions.length,
      lastSessionStart,
      remainingSessionSlots,
    });
  }, [deliveryDraft.cohortId, deliveryDraft.startDate, lessonBlueprints, cohortSessions, remainingSessionSlots]);

  useEffect(() => {
    if (!isVisible) {
      setBuilderError(null);
      setBuilderMessage(null);
      setDeliveryError(null);
      setDeliveryMessage(null);
      setDeliverySessionsError(null);
      setDeliverySessionsMessage(null);
      return;
    }
    setBuilderError(null);
    setBuilderMessage(null);
    setDeliveryError(null);
    setDeliveryMessage(null);
    setDeliverySessionsError(null);
    setDeliverySessionsMessage(null);
    setSelectedLibraryItemId(null);
    setCourseDraft(createBlankCourseDraft());
    setPersistedCourseId(mode === "edit" ? (courseId ?? null) : null);
    setDeliveryDraft(createBlankDeliveryDraft());
    setDeliverySessionsDraft(createBlankDeliverySessionsDraft());
    setLibraryDraft(buildLibrarySeed("main"));
    setImportJsonDraft("");
    setActiveStep(initialStep ?? (templateStepAvailable ? "template" : "basics"));
    setSelectedTemplateId(initialTemplateId ?? null);
  }, [courseId, initialTemplateId, initialStep, isVisible, mode, templateStepAvailable]);

  useEffect(() => {
    if (!isVisible || mode !== "edit" || !courseData) return;
    setCourseDraft(courseDraftFromCourse(courseData));
  }, [courseData, isVisible, mode]);

  useEffect(() => {
    if (!isVisible) return;
    if (deliveryDraft.cohortId) return;
    setDeliveryDraft((current) => {
      const next = createBlankDeliveryDraft({
        slug: courseDraft.slug,
        titleDe: courseDraft.titleDe,
        titleEn: courseDraft.titleEn,
      });
      return {
        ...current,
        groupCode: current.groupCode || next.groupCode,
        groupName: current.groupName || next.groupName,
        timezone: current.timezone || next.timezone,
      };
    });
  }, [courseDraft.slug, courseDraft.titleDe, courseDraft.titleEn, deliveryDraft.cohortId, isVisible]);

  useEffect(() => {
    if (!isVisible) return;
    if (!deliveryDraft.cohortId) {
      setDeliverySessionsDraft(createBlankDeliverySessionsDraft());
      setDeliverySessionsError(null);
      setDeliverySessionsMessage(null);
      return;
    }

    const baseDraft = createBlankDeliverySessionsDraft();
    const lastSession = cohortSessions.length ? cohortSessions[cohortSessions.length - 1] : null;
    let firstStartsAt = baseDraft.firstStartsAt;
    if (lastSession?.startsAt) {
      const nextStart = new Date(lastSession.startsAt);
      if (!Number.isNaN(nextStart.getTime())) {
        nextStart.setDate(nextStart.getDate() + 7);
        firstStartsAt = toDateInputValueFromIso(nextStart.toISOString());
      }
    } else if (deliveryDraft.startDate) {
      firstStartsAt = `${deliveryDraft.startDate}T18:00`;
    }

    const sessionCount = Math.max(1, remainingSessionSlots > 0 ? Math.min(remainingSessionSlots, 3) : 1);
    setDeliverySessionsDraft({
      sessionCount,
      firstStartsAt,
      durationMinutes: baseDraft.durationMinutes,
      intervalDays: baseDraft.intervalDays,
      sessions:
        remainingSessionSlots > 0
          ? buildDeliverySessionDrafts({
              lessonBlueprints: lessonBlueprints.slice(cohortSessions.length),
              existingSessionsCount: cohortSessions.length,
              sessionCount,
              firstStartsAt,
              durationMinutes: baseDraft.durationMinutes,
              intervalDays: baseDraft.intervalDays,
            })
          : [],
    });
    setDeliverySessionsError(null);
    setDeliverySessionsMessage(null);
  }, [isVisible, sessionSeedResetKey]);

  useEffect(() => {
    if (!isVisible || mode !== "create") return;
    if (!selectedTemplateId) return;
    const template = templates.find((item) => item.id === selectedTemplateId);
    if (template) {
      setCourseDraft(courseDraftFromTemplate(template));
    }
  }, [isVisible, mode, selectedTemplateId, templates]);

  useEffect(() => {
    if (!isVisible) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isVisible, onClose, inline]);

  useEffect(() => {
    if (!isVisible || inline) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [isVisible, inline]);

  const patchDraft = (patch: Partial<CourseBuilderCourseDraft>) => {
    setCourseDraft((current) => ({ ...current, ...patch }));
  };

  const mutateDraft = (mutator: (next: CourseBuilderCourseDraft) => void) => {
    setCourseDraft((current) => {
      const next = cloneDraft(current);
      mutator(next);
      return next;
    });
  };

  const addModule = () => {
    mutateDraft((next) => {
      const moduleNumber = next.modules.length + 1;
      next.modules.push({
        clientId: makeClientId("module"),
        id: undefined,
        title: `Module ${moduleNumber} (Week ${moduleNumber})`,
        description: "",
        moduleType: "module",
        weekNumber: moduleNumber,
        sortOrder: moduleNumber * 10,
        isActive: true,
      });
    });
  };

  const removeModule = (moduleClientId: string) => {
    mutateDraft((next) => {
      if (next.modules.length <= 1) return;
      const fallbackModuleClientId = next.modules.find((module) => module.clientId !== moduleClientId)?.clientId;
      next.modules = next.modules.filter((module) => module.clientId !== moduleClientId);
      if (fallbackModuleClientId) {
        next.lessons = next.lessons.map((lesson) =>
          lesson.moduleClientId === moduleClientId
            ? { ...lesson, moduleClientId: fallbackModuleClientId }
            : lesson
        );
      }
    });
  };

  const patchModule = (moduleClientId: string, patch: Partial<CourseBuilderModuleDraft>) => {
    mutateDraft((next) => {
      const module = next.modules.find((item) => item.clientId === moduleClientId);
      if (!module) return;
      Object.assign(module, patch);
    });
  };

  const addLesson = () => {
    mutateDraft((next) => {
      const lessonNumber = next.lessons.length + 1;
      const fallbackModuleClientId = next.modules[0]?.clientId ?? "";
      next.lessons.push({
        clientId: makeClientId("lesson"),
        id: undefined,
        moduleClientId: fallbackModuleClientId,
        title: `Lesson ${lessonNumber}`,
        description: "",
        sortOrder: lessonNumber,
        isActive: true,
        sections: buildBlankLessonSections(),
      });
    });
  };

  const removeLesson = (lessonClientId: string) => {
    mutateDraft((next) => {
      if (next.lessons.length <= 1) return;
      next.lessons = next.lessons.filter((lesson) => lesson.clientId !== lessonClientId);
    });
  };

  const patchLesson = (lessonClientId: string, patch: Partial<CourseBuilderLessonDraft>) => {
    mutateDraft((next) => {
      const lesson = next.lessons.find((item) => item.clientId === lessonClientId);
      if (!lesson) return;
      Object.assign(lesson, patch);
    });
  };

  const patchSection = (lessonClientId: string, sectionType: CourseBuilderSectionType, patch: Partial<CourseBuilderSectionDraft>) => {
    mutateDraft((next) => {
      const lesson = next.lessons.find((item) => item.clientId === lessonClientId);
      if (!lesson) return;
      const section = lesson.sections.find((item) => item.sectionType === sectionType);
      if (!section) return;
      Object.assign(section, patch);
    });
  };

  const addSectionItem = (
    lessonClientId: string,
    sectionType: CourseBuilderSectionType,
    seed: Pick<CourseBuilderSectionItemDraft, "assetType"> & Partial<CourseBuilderSectionItemDraft>,
  ) => {
    mutateDraft((next) => {
      const lesson = next.lessons.find((item) => item.clientId === lessonClientId);
      if (!lesson) return;
      const section = lesson.sections.find((item) => item.sectionType === sectionType);
      if (!section) return;
      const assetType = seed.assetType;
      section.items.push({
        clientId: makeClientId("item"),
        id: undefined,
        sourceLibraryItemId: null,
        title: seed.title || `${assetType.charAt(0).toUpperCase()}${assetType.slice(1)} item`,
        description: seed.description || "",
        assetType,
        activityType: seed.activityType ?? (assetType === "notebook" ? "assignment" : "text"),
        language: normalizeCourseLanguage(seed.language),
        bodyMarkdown: seed.bodyMarkdown ?? "",
        externalUrl: seed.externalUrl ?? "",
        structuredData: seed.structuredData ?? {},
        linkedTrainingContentId: seed.linkedTrainingContentId ?? null,
        audienceIds: seed.audienceIds ?? [],
        sortOrder: section.items.length + 1,
        isActive: seed.isActive ?? true,
      });
    });
  };

  const removeSectionItem = (
    lessonClientId: string,
    sectionType: CourseBuilderSectionType,
    itemClientId: string,
  ) => {
    mutateDraft((next) => {
      const lesson = next.lessons.find((item) => item.clientId === lessonClientId);
      if (!lesson) return;
      const section = lesson.sections.find((item) => item.sectionType === sectionType);
      if (!section) return;
      section.items = section.items.filter((item) => item.clientId !== itemClientId);
    });
  };

  const patchSectionItem = (
    lessonClientId: string,
    sectionType: CourseBuilderSectionType,
    itemClientId: string,
    patch: Partial<CourseBuilderSectionItemDraft>,
  ) => {
    mutateDraft((next) => {
      const lesson = next.lessons.find((item) => item.clientId === lessonClientId);
      if (!lesson) return;
      const section = lesson.sections.find((item) => item.sectionType === sectionType);
      if (!section) return;
      const item = section.items.find((entry) => entry.clientId === itemClientId);
      if (!item) return;
      Object.assign(item, patch);
    });
  };

  const applyLibraryItemToSectionItem = (
    lessonClientId: string,
    sectionType: CourseBuilderSectionType,
    itemClientId: string,
    libraryItemId: number,
  ) => {
    const libraryItem = libraryItems.find((item) => item.id === libraryItemId);
    if (!libraryItem) return;
    patchSectionItem(lessonClientId, sectionType, itemClientId, {
      sourceLibraryItemId: libraryItem.id,
      title: libraryItem.title,
      description: libraryItem.description,
      assetType: libraryItem.assetType,
      language: normalizeCourseLanguage(libraryItem.language),
      bodyMarkdown: libraryItem.bodyMarkdown,
      externalUrl: libraryItem.externalUrl,
      structuredData: {},
      linkedTrainingContentId: libraryItem.trainingContentId,
      audienceIds: libraryItem.audienceIds ?? [],
    });
  };

  const replaceLessonDocument = (lessonClientId: string, document: ImportedLessonDocument) => {
    mutateDraft((next) => {
      const lesson = next.lessons.find((item) => item.clientId === lessonClientId);
      if (!lesson) return;

      if (document.title?.trim()) {
        lesson.title = document.title.trim();
      }
      if (document.description?.trim()) {
        lesson.description = document.description.trim();
      }

      const importedSections = [...document.sections].sort((left, right) => left.sortOrder - right.sortOrder);
      const importedMainSection = importedSections.find((section) => section.sectionType === "main") ?? importedSections[0];
      const existingMainSection = lesson.sections.find((entry) => entry.sectionType === "main");
      const mergedItems = importedSections
        .flatMap((section) =>
          section.items.map((item) => ({
            item,
            sectionSortOrder: section.sortOrder,
          })),
        )
        .sort((left, right) => left.sectionSortOrder - right.sectionSortOrder || left.item.sortOrder - right.item.sortOrder);

      lesson.sections = [
        {
          clientId: existingMainSection?.clientId ?? makeClientId("section"),
          id: existingMainSection?.id,
          sectionType: "main",
          title: importedMainSection?.title?.trim() || existingMainSection?.title || DEFAULT_SECTION_TITLES.main,
          description: importedMainSection?.description?.trim() || "",
          sortOrder: importedMainSection?.sortOrder || existingMainSection?.sortOrder || 10,
          isActive: importedMainSection?.isActive ?? existingMainSection?.isActive ?? true,
          items: mergedItems.map(({ item }, itemIndex) => ({
            clientId: makeClientId("item"),
            id: undefined,
            sourceLibraryItemId: item.sourceLibraryItemId ?? null,
            title: item.title,
            description: item.description,
            assetType: item.assetType,
            activityType: item.activityType ?? (item.assetType === "notebook" ? "assignment" : "text"),
            language: normalizeCourseLanguage(item.language),
            bodyMarkdown: item.bodyMarkdown,
            externalUrl: item.externalUrl,
            structuredData: item.structuredData ?? {},
            linkedTrainingContentId: item.linkedTrainingContentId ?? null,
            audienceIds: item.audienceIds ?? [],
            sortOrder: itemIndex + 1,
            isActive: item.isActive !== false,
          })),
        },
      ];
    });
  };

  const attachVideoAssetToGeneratedDocument = (
    document: ImportedLessonDocument,
    {
      videoUrl,
      videoDescription,
      sourceLibraryItemId,
    }: {
      videoUrl?: string;
      videoDescription?: string;
      sourceLibraryItemId?: number | null;
    },
  ): ImportedLessonDocument => {
    const nextDocument = cloneDraft(document);
    const mainSection = nextDocument.sections.find((section) => section.sectionType === "main");
    if (!mainSection) {
      return nextDocument;
    }

    const videoItem = mainSection.items.find((item) => item.activityType === "video");
    if (!videoItem) {
      mainSection.items.push({
        title: "Video walkthrough",
        description: videoDescription ?? "",
        assetType: "link",
        activityType: "video",
        language: normalizeCourseLanguage(mainSection.items[0]?.language),
        bodyMarkdown: videoDescription ? `## Video\n\n${videoDescription}` : "",
        externalUrl: videoUrl ?? "",
        sourceLibraryItemId: sourceLibraryItemId ?? null,
        linkedTrainingContentId: null,
        audienceIds: [],
        structuredData: {},
        sortOrder: mainSection.items.length + 1,
        isActive: true,
      });
      return nextDocument;
    }

    if (videoUrl) {
      videoItem.externalUrl = videoUrl;
    }
    if (sourceLibraryItemId) {
      videoItem.sourceLibraryItemId = sourceLibraryItemId;
    }
    if (videoDescription) {
      videoItem.description = videoDescription;
      if (!videoItem.bodyMarkdown.trim()) {
        videoItem.bodyMarkdown = `## Video\n\n${videoDescription}`;
      }
    }
    return nextDocument;
  };

  const generateLessonFromSource = async (lessonClientId: string, draft: LessonGeneratorDraft) => {
    const lesson = courseDraft.lessons.find((item) => item.clientId === lessonClientId);
    const module = courseDraft.modules.find((item) => item.clientId === lesson?.moduleClientId) ?? null;
    if (draft.videoFile) {
      const response = await generateCourseBuilderLessonFromVideo({
        title: lesson?.title || "Generated lesson",
        description: lesson?.description || "",
        videoFile: draft.videoFile,
        language: normalizeCourseLanguage(draft.language),
        courseTitle: courseDraft.titleEn || courseDraft.titleDe,
        moduleTitle: module?.title || "",
        videoUrl: draft.videoUrl,
        videoDescription: draft.videoDescription,
      }).unwrap();

      replaceLessonDocument(lessonClientId, response.document as ImportedLessonDocument);
      const generationLabel = response.meta.mode === "ai" ? `${response.meta.provider} / ${response.meta.model}` : response.meta.model;
      const transcriptionLabel = response.meta.transcriptionModel ? `, transcript: ${response.meta.transcriptionModel}` : "";
      return `Generated lesson flow from uploaded video (${generationLabel}${transcriptionLabel}). Review the steps and save the course when ready.`;
    }

    const response = await generateCourseBuilderLesson({
      title: lesson?.title || "Generated lesson",
      description: lesson?.description || "",
      sourceText: draft.sourceText,
      language: normalizeCourseLanguage(draft.language),
      courseTitle: courseDraft.titleEn || courseDraft.titleDe,
      moduleTitle: module?.title || "",
      videoUrl: draft.videoFile ? "" : draft.videoUrl,
      videoDescription: draft.videoDescription,
    }).unwrap();

    let document = response.document as ImportedLessonDocument;
    if (draft.videoUrl || draft.videoDescription) {
      document = attachVideoAssetToGeneratedDocument(document, {
        videoUrl: draft.videoUrl,
        videoDescription: draft.videoDescription,
      });
    }

    replaceLessonDocument(lessonClientId, document);
    const generationLabel = response.meta.mode === "ai" ? `${response.meta.provider} / ${response.meta.model}` : response.meta.model;
    return `Generated lesson flow (${generationLabel}). Review the steps and save the course when ready.`;
  };

  const openLibraryForm = (sectionType: CourseBuilderSectionType) => {
    scrollToStep("library");
    setSelectedLibraryItemId(null);
    setLibraryDraft(buildLibrarySeed(sectionType));
  };

  const selectLibraryItem = (itemId: number | null) => {
    setSelectedLibraryItemId(itemId);
    if (!itemId) {
      setLibraryDraft(buildLibrarySeed(libraryDraft.sectionType));
      return;
    }
    const item = libraryItems.find((candidate) => candidate.id === itemId);
    if (item) {
      setLibraryDraft(libraryDraftFromItem(item));
    }
  };

  const resetLibraryDraft = (sectionType?: CourseBuilderSectionType) => {
    setSelectedLibraryItemId(null);
    setLibraryDraft(buildLibrarySeed(sectionType ?? libraryDraft.sectionType));
  };

  const saveLibraryItem = async () => {
    setBuilderError(null);
    setBuilderMessage(null);
    try {
      if (selectedLibraryItemId) {
        const payload = {
          sectionType: libraryDraft.sectionType,
          title: libraryDraft.title,
          description: libraryDraft.description,
          libraryGroup: libraryDraft.libraryGroup,
          assetType: libraryDraft.assetType,
          language: normalizeCourseLanguage(libraryDraft.language),
          bodyMarkdown: libraryDraft.bodyMarkdown,
          externalUrl: libraryDraft.externalUrl,
          file: libraryDraft.file ?? undefined,
          trainingContentId: libraryDraft.trainingContentId,
          audienceIds: libraryDraft.audienceIds,
          sortOrder: libraryDraft.sortOrder,
          isActive: libraryDraft.isActive,
        };
        const result = await updateLibraryItem({ itemId: selectedLibraryItemId, body: payload }).unwrap();
        setSelectedLibraryItemId(result.id);
        setLibraryDraft(libraryDraftFromItem(result));
        setBuilderMessage("Library item updated.");
      } else {
        const result = await createLibraryItem({
          sectionType: libraryDraft.sectionType,
          title: libraryDraft.title,
          description: libraryDraft.description,
          libraryGroup: libraryDraft.libraryGroup,
          assetType: libraryDraft.assetType,
          language: normalizeCourseLanguage(libraryDraft.language),
          bodyMarkdown: libraryDraft.bodyMarkdown,
          externalUrl: libraryDraft.externalUrl,
          file: libraryDraft.file,
          trainingContentId: libraryDraft.trainingContentId,
          audienceIds: libraryDraft.audienceIds,
          sortOrder: libraryDraft.sortOrder,
          isActive: libraryDraft.isActive,
        }).unwrap();
        setSelectedLibraryItemId(result.id);
        setLibraryDraft(libraryDraftFromItem(result));
        setBuilderMessage("Library item created.");
      }
    } catch (error) {
      setBuilderError(errorMessageFrom(error, "Failed to save library item."));
    }
  };

  const deleteSelectedLibraryItem = async () => {
    if (!selectedLibraryItemId) return;
    if (!window.confirm("Delete this library item?")) return;
    setBuilderError(null);
    setBuilderMessage(null);
    try {
      await deleteLibraryItem(selectedLibraryItemId).unwrap();
      setSelectedLibraryItemId(null);
      setLibraryDraft(buildLibrarySeed(libraryDraft.sectionType));
      setBuilderMessage("Library item deleted.");
    } catch (error) {
      setBuilderError(errorMessageFrom(error, "Failed to delete library item."));
    }
  };

  const patchDeliveryDraft = (patch: Partial<CourseBuilderDeliveryDraft>) => {
    setDeliveryDraft((current) => ({ ...current, ...patch }));
  };

  const resetDeliveryDraft = () => {
    setDeliveryError(null);
    setDeliveryMessage(null);
    setDeliverySessionsError(null);
    setDeliverySessionsMessage(null);
    setDeliveryDraft(
      createBlankDeliveryDraft({
        slug: courseDraft.slug,
        titleDe: courseDraft.titleDe,
        titleEn: courseDraft.titleEn,
      }),
    );
  };

  const selectExistingCohort = (cohortId: number | null) => {
    if (cohortId === null) {
      resetDeliveryDraft();
      return;
    }
    const cohort = courseCohorts.find((item) => item.id === cohortId);
    if (!cohort) return;
    setDeliveryError(null);
    setDeliveryMessage(null);
    setDeliverySessionsError(null);
    setDeliverySessionsMessage(null);
    setDeliveryDraft({
      cohortId: cohort.id,
      groupCode: cohort.groupCode,
      groupName: cohort.groupName,
      capacity: cohort.capacity,
      timezone: cohort.timezone,
      startDate: cohort.startDate ? cohort.startDate.slice(0, 10) : "",
      endDate: cohort.endDate ? cohort.endDate.slice(0, 10) : "",
      status: cohort.status as CourseBuilderDeliveryDraft["status"],
      isPublic: cohort.isPublic,
      curatorId: cohort.teacherId ?? null,
    });
  };

  const patchDeliverySessionsDraft = (patch: Partial<CourseBuilderDeliverySessionsDraft>) => {
    setDeliverySessionsDraft((current) => ({ ...current, ...patch }));
  };

  const patchDeliverySessionItem = (clientId: string, patch: Partial<CourseBuilderDeliverySessionDraft>) => {
    setDeliverySessionsDraft((current) => ({
      ...current,
      sessions: current.sessions.map((session) => (session.clientId === clientId ? { ...session, ...patch } : session)),
    }));
  };

  const regenerateDeliverySessionPreview = () => {
    if (!deliveryDraft.cohortId) {
      setDeliverySessionsError("Create or select a cohort before generating sessions.");
      setDeliverySessionsMessage(null);
      return;
    }
    if (remainingSessionSlots <= 0) {
      setDeliverySessionsError("All lesson slots are already scheduled for this cohort.");
      setDeliverySessionsMessage(null);
      return;
    }

    const sessionCount = Math.min(Math.max(deliverySessionsDraft.sessionCount || 1, 1), remainingSessionSlots);
    const durationMinutes = Math.max(deliverySessionsDraft.durationMinutes || 120, 15);
    const intervalDays = Math.max(deliverySessionsDraft.intervalDays || 7, 1);
    const firstStartsAt = deliverySessionsDraft.firstStartsAt || createBlankDeliverySessionsDraft().firstStartsAt;

    setDeliverySessionsError(null);
    setDeliverySessionsMessage(null);
    setDeliverySessionsDraft((current) => ({
      ...current,
      sessionCount,
      firstStartsAt,
      durationMinutes,
      intervalDays,
      sessions: buildDeliverySessionDrafts({
        lessonBlueprints: lessonBlueprints.slice(cohortSessions.length),
        existingSessionsCount: cohortSessions.length,
        sessionCount,
        firstStartsAt,
        durationMinutes,
        intervalDays,
      }),
    }));
  };

  const saveDeliverySessions = async () => {
    if (!effectiveCourseId || !deliveryDraft.cohortId) {
      setDeliverySessionsError("Save or select a cohort before creating sessions.");
      setDeliverySessionsMessage(null);
      return;
    }
    if (deliverySessionsDraft.sessions.length === 0) {
      setDeliverySessionsError("Generate or enter at least one session before saving.");
      setDeliverySessionsMessage(null);
      return;
    }

    setDeliverySessionsError(null);
    setDeliverySessionsMessage(null);
    try {
      const response = await createCourseBuilderSessions({
        courseId: effectiveCourseId,
        body: {
          cohortId: deliveryDraft.cohortId,
          sessions: deliverySessionsDraft.sessions.map((session) => ({
            title: session.title,
            description: session.description,
            startsAt: localDateTimeToIso(session.startsAt),
            endsAt: localDateTimeToIso(session.endsAt),
          })),
        },
      }).unwrap();
      setDeliverySessionsMessage(
        response.createdCount === 1
          ? "Created 1 session for the selected cohort."
          : `Created ${response.createdCount} sessions for the selected cohort.`,
      );
      await Promise.all([refetchCohorts(), refetchCohortSessions()]);
    } catch (error) {
      setDeliverySessionsError(errorMessageFrom(error, "Failed to create delivery sessions."));
    }
  };

  const saveDeliveryAssignment = async () => {
    if (!effectiveCourseId) {
      setDeliveryError("Save the course before creating a delivery cohort.");
      setDeliveryMessage(null);
      return;
    }
    setDeliveryError(null);
    setDeliveryMessage(null);
    try {
      const response = await saveCourseBuilderDeliveryAssignment({
        courseId: effectiveCourseId,
        body: {
          cohortId: deliveryDraft.cohortId,
          groupCode: deliveryDraft.groupCode,
          groupName: deliveryDraft.groupName,
          capacity: deliveryDraft.capacity,
          timezone: deliveryDraft.timezone,
          startDate: deliveryDraft.startDate || null,
          endDate: deliveryDraft.endDate || null,
          status: deliveryDraft.status,
          isPublic: deliveryDraft.isPublic,
          curatorId: deliveryDraft.curatorId,
        },
      }).unwrap();

      setDeliveryDraft({
        cohortId: response.cohort.id,
        groupCode: response.cohort.groupCode,
        groupName: response.cohort.groupName,
        capacity: response.cohort.capacity,
        timezone: response.cohort.timezone,
        startDate: response.cohort.startDate ? response.cohort.startDate.slice(0, 10) : "",
        endDate: response.cohort.endDate ? response.cohort.endDate.slice(0, 10) : "",
        status: response.cohort.status as CourseBuilderDeliveryDraft["status"],
        isPublic: response.cohort.isPublic,
        curatorId: response.cohort.teacherId ?? null,
      });
      setDeliveryMessage(
        response.created
          ? "Delivery cohort created and linked to this course."
          : "Delivery cohort updated.",
      );
      await Promise.all([refetchCohorts(), refetchCurators()]);
      if (deliveryDraft.cohortId) {
        await refetchCohortSessions();
      }
    } catch (error) {
      setDeliveryError(errorMessageFrom(error, "Failed to save delivery assignment."));
    }
  };

  const saveCourse = async () => {
    setBuilderError(null);
    setBuilderMessage(null);
    try {
      const payload = serializeCourseDraft(courseDraft);
      const result =
        mode === "create" && !persistedCourseId
          ? await createCourseBuilderCourse(payload).unwrap()
          : await updateCourseBuilderCourse({ courseId: (effectiveCourseId as number), body: payload }).unwrap();
      if (result.id) {
        setPersistedCourseId(result.id);
      }
      setCourseDraft(courseDraftFromCourse(result));
      onSaved(result);
      setBuilderMessage(
        mode === "create" && !persistedCourseId
          ? "Course created successfully. Continue with delivery assignment."
          : "Course updated successfully.",
      );
      if (mode === "create" && !persistedCourseId) {
        scrollToStep("delivery");
      }
    } catch (error) {
      setBuilderError(errorMessageFrom(error, "Failed to save course."));
    }
  };

  const selectedTemplate = templates.find((item) => item.id === selectedTemplateId) ?? null;
  const stats = countDraftItems(courseDraft);
  const selectedLibraryItem = selectedLibraryItemId
    ? libraryItems.find((item) => item.id === selectedLibraryItemId) ?? null
    : null;
  const courseSaveLabel =
    mode === "create" && !persistedCourseId ? "Create course" : "Save course";
  const closeLabel = inline ? "Hide studio" : "Close";
  const curatorWorkspaceHref = deliveryDraft.cohortId ? `/teacher/online?cohortId=${deliveryDraft.cohortId}` : null;

  function scrollToStep(step: BuilderStep) {
    setActiveStep(step);
    if (!inline || typeof document === "undefined") return;
    window.requestAnimationFrame(() => {
      document.getElementById(stepSectionId(step))?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  const applyTemplate = (templateId: number) => {
    const template = templates.find((item) => item.id === templateId);
    if (!template) return;
    setSelectedTemplateId(template.id);
    setCourseDraft(courseDraftFromTemplate(template));
    scrollToStep("basics");
  };

  const importCourseFromJson = async () => {
    setBuilderError(null);
    setBuilderMessage(null);
    let parsedPayload: Record<string, unknown>;
    try {
      parsedPayload = JSON.parse(importJsonDraft) as Record<string, unknown>;
    } catch {
      setBuilderError("Invalid JSON. Paste a valid Coursera-like course payload.");
      return;
    }

    try {
      const imported = await importCourseBuilderCourse({
        source: "coursera_json",
        payload: parsedPayload,
      }).unwrap();
      if (imported.id) {
        setPersistedCourseId(imported.id);
      }
      setCourseDraft(courseDraftFromCourse(imported));
      onSaved(imported);
      setBuilderMessage("Course imported successfully. Review modules and continue with delivery setup.");
      scrollToStep("basics");
    } catch (error) {
      setBuilderError(errorMessageFrom(error, "Failed to import course JSON payload."));
    }
  };

  const renderStepContent = (step: BuilderStep) => {
    switch (step) {
      case "template":
        return (
          <>
            <CourseBuilderTemplatePanel
              templates={templates}
              selectedTemplateId={selectedTemplateId}
              onApplyTemplate={applyTemplate}
              onClearTemplate={() => {
                setSelectedTemplateId(null);
                setCourseDraft(createBlankCourseDraft());
              }}
              isLoading={isTemplatesLoading}
              isError={isTemplatesError}
            />
            <section className={styles.card}>
              <header className={styles.cardHeader}>
                <div>
                  <h3 className={styles.cardTitle}>Import course JSON</h3>
                  <p className={styles.cardText}>
                    Paste a Coursera-like course tree (`modules[]`, `lessons[]`, optional `finalAssessment`) and import it.
                  </p>
                </div>
                <div className={styles.row}>
                  <button
                    type="button"
                    className={styles.primaryButton}
                    onClick={() => void importCourseFromJson()}
                    disabled={isImportingCourse || !importJsonDraft.trim()}
                  >
                    {isImportingCourse ? "Importing..." : "Import JSON"}
                  </button>
                </div>
              </header>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>JSON payload</span>
                <textarea
                  className={styles.textarea}
                  value={importJsonDraft}
                  onChange={(event) => setImportJsonDraft(event.currentTarget.value)}
                  placeholder='{"title":"Sample course","modules":[{"title":"Module 1","lessons":[{"title":"Lesson 1","contentItems":[{"type":"video","title":"Intro","url":"https://..."}]}]}]}'
                />
              </label>
            </section>
          </>
        );
      case "basics":
        return (
          <CourseBuilderBasicsPanel
            draft={courseDraft}
            audiences={audiences}
            instructors={curators}
            workspaces={workspaces}
            onPatchDraft={patchDraft}
          />
        );
      case "lessons":
        return (
          <CourseBuilderLessonsPanel
            draft={courseDraft}
            libraryItems={libraryItems}
            notebookOptions={notebookOptions}
            audiences={audiences}
            onAddModule={addModule}
            onRemoveModule={removeModule}
            onPatchModule={patchModule}
            onAddLesson={addLesson}
            onRemoveLesson={removeLesson}
            onPatchLesson={patchLesson}
            onPatchSection={patchSection}
            onAddSectionItem={addSectionItem}
            onRemoveSectionItem={removeSectionItem}
            onPatchSectionItem={patchSectionItem}
            onApplyLibraryItemToSectionItem={applyLibraryItemToSectionItem}
            onOpenLibraryForm={openLibraryForm}
            onReplaceLessonDocument={replaceLessonDocument}
            onGenerateLesson={generateLessonFromSource}
          />
        );
      case "library":
        return (
          <CourseBuilderLibraryPanel
            draft={libraryDraft}
            items={libraryItems}
            notebooks={notebookOptions}
            audiences={audiences}
            selectedLibraryItemId={selectedLibraryItemId}
            onSelectLibraryItem={selectLibraryItem}
            onNewDraft={resetLibraryDraft}
            onPatchDraft={(patch) => setLibraryDraft((current) => ({ ...current, ...patch }))}
            onSave={saveLibraryItem}
            onDelete={deleteSelectedLibraryItem}
            isSaving={isSavingLibraryItem}
            isDeleting={isDeletingLibraryItem}
            isLoading={isLibraryLoading || isNotebooksLoading}
            isError={isLibraryError || isNotebooksError}
          />
        );
      case "review":
        return (
          <section className={styles.card}>
            <header className={styles.cardHeader}>
              <div>
                <h3 className={styles.cardTitle}>Review structure</h3>
                <p className={styles.cardText}>
                  Final summary before persistence. Ensure the lesson structure is complete and publication settings look correct.
                </p>
              </div>
              <span className={styles.statusNote}>
                {isPersistedCourse ? "Saved course" : "Draft mode"}
              </span>
            </header>

            <div className={styles.reviewGrid}>
              <article className={styles.reviewCard}>
                <span>Title</span>
                <strong>{courseDraft.titleEn || courseDraft.titleDe || "Untitled course"}</strong>
              </article>
              <article className={styles.reviewCard}>
                <span>Modules</span>
                <strong>{stats.modules}</strong>
              </article>
              <article className={styles.reviewCard}>
                <span>Lessons</span>
                <strong>{stats.lessons}</strong>
              </article>
              <article className={styles.reviewCard}>
                <span>Items</span>
                <strong>{stats.items}</strong>
              </article>
              <article className={styles.reviewCard}>
                <span>Notebooks</span>
                <strong>{stats.notebooks}</strong>
              </article>
            </div>

            <div className={styles.formGrid}>
              <article className={styles.reviewCard}>
                <span>Template</span>
                <strong>{selectedTemplate?.title || "No template selected"}</strong>
              </article>
              <article className={styles.reviewCard}>
                <span>Governance status</span>
                <strong>{courseDraft.lifecycleStatus.replace(/_/g, " ")}</strong>
              </article>
              <article className={styles.reviewCard}>
                <span>Visibility</span>
                <strong>{courseDraft.lifecycleStatus === "published" ? "Public" : "Private"}</strong>
              </article>
              <article className={styles.reviewCard}>
                <span>Completion rule</span>
                <strong>
                  {courseDraft.requiredCompletionPercent}% progress / {courseDraft.requiredAttendancePercent}% attendance
                </strong>
              </article>
              <article className={styles.reviewCard}>
                <span>Attestation</span>
                <strong>{courseDraft.requiresAttestation ? "Required" : "Optional"}</strong>
              </article>
            </div>

            <div className={styles.stack}>
              <header className={styles.cardHeader}>
                <div>
                  <h3 className={styles.cardTitle}>Release readiness</h3>
                  <p className={styles.cardText}>
                    Required checks must pass before the course can move into a publishable release.
                  </p>
                </div>
                <span className={styles.statusNote}>
                  {governance?.readiness.statusLabel ?? (isPersistedCourse ? "Loading" : "Save draft first")}
                </span>
              </header>

              {governance ? (
                <div className={styles.reviewGrid}>
                  {governance.readiness.checks.map((check) => (
                    <article key={check.id} className={styles.reviewCard}>
                      <span>{check.required ? "Required check" : "Advisory check"}</span>
                      <strong>{check.label}</strong>
                      <p className={check.passed ? styles.helperText : styles.emptyState}>
                        {check.passed ? "Ready" : "Needs action"} · {check.description}
                      </p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className={styles.emptyState}>
                  Save the course once to generate release checks and version tracking.
                </p>
              )}
            </div>

            <div className={styles.stack}>
              <header className={styles.cardHeader}>
                <div>
                  <h3 className={styles.cardTitle}>Version history</h3>
                  <p className={styles.cardText}>
                    Snapshots capture governed release points and change summaries for rollback-friendly operations.
                  </p>
                </div>
                <span className={styles.statusNote}>
                  {governance ? `${governance.versionsCount} snapshot(s)` : "No snapshots yet"}
                </span>
              </header>

              {governance?.versionHistory && governance.versionHistory.length > 0 ? (
                <div className={styles.reviewGrid}>
                  {governance.versionHistory.map((version) => (
                    <article key={version.id} className={styles.reviewCard}>
                      <span>{version.lifecycleLabel}</span>
                      <strong>v{version.versionNumber}</strong>
                      <p className={styles.helperText}>
                        {version.changeSummary || version.source || "Manual snapshot"}
                      </p>
                      <p className={styles.helperText}>
                        {version.createdByEmail || "System"} · {new Date(version.createdAt).toLocaleString()}
                      </p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className={styles.emptyState}>
                  {isPersistedCourse ? "No governed snapshots have been created yet." : "Save the course to start version history."}
                </p>
              )}
            </div>
          </section>
        );
      case "delivery":
        return (
          <CourseBuilderDeliveryPanel
            isPersistedCourse={isPersistedCourse}
            courseTitle={courseDraft.titleEn || courseDraft.titleDe}
            lessonCount={lessonBlueprints.length}
            cohorts={courseCohorts}
            curators={curators}
            draft={deliveryDraft}
            sessionDraft={deliverySessionsDraft}
            existingSessions={cohortSessions}
            remainingSessionSlots={remainingSessionSlots}
            isSaving={isSavingDelivery}
            isLoading={isCohortsLoading}
            isCuratorsLoading={isCuratorsLoading}
            isSessionsLoading={isCohortSessionsLoading}
            isSavingSessions={isCreatingDeliverySessions}
            curatorWorkspaceHref={curatorWorkspaceHref}
            hasCuratorAssigned={Boolean(deliveryDraft.curatorId)}
            error={deliveryError}
            message={deliveryMessage}
            sessionsError={deliverySessionsError}
            sessionsMessage={deliverySessionsMessage}
            onPatchDraft={patchDeliveryDraft}
            onSelectExistingCohort={selectExistingCohort}
            onResetDraft={resetDeliveryDraft}
            onSave={saveDeliveryAssignment}
            onPatchSessionDraft={patchDeliverySessionsDraft}
            onPatchSessionItem={patchDeliverySessionItem}
            onGenerateSessions={regenerateDeliverySessionPreview}
            onSaveSessions={saveDeliverySessions}
          />
        );
      default:
        return null;
    }
  };

  const renderStepSummary = (step: BuilderStep) => {
    switch (step) {
      case "template":
        return selectedTemplate ? <span className={styles.statusNote}>Selected: {selectedTemplate.title}</span> : null;
      case "basics":
        return <span className={styles.statusNote}>{stats.lessons} lessons</span>;
      case "lessons":
        return (
          <div className={styles.pillRow}>
            <span className={styles.miniPill}>{stats.modules} modules</span>
            <span className={styles.miniPill}>{stats.lessons} lessons</span>
            <span className={styles.miniPill}>{stats.items} blocks</span>
          </div>
        );
      case "library":
        return <span className={styles.statusNote}>{libraryItems.length} reusable items</span>;
      case "review":
        return <span className={styles.statusNote}>{isPersistedCourse ? "Saved course" : "Draft mode"}</span>;
      case "delivery":
        return <span className={styles.statusNote}>{courseCohorts.length} cohorts</span>;
      default:
        return null;
    }
  };

  if (!isVisible) {
    return null;
  }

  return (
    <div
      className={inline ? styles.inlineRoot : styles.overlay}
      role={inline ? undefined : "dialog"}
      aria-modal={inline ? undefined : true}
      aria-label="Course builder"
    >
      <div className={`${styles.shell} ${inline ? styles.inlineShell : ""}`}>
        <aside className={styles.sidebar}>
          <div className={styles.sidebarHeader}>
            <span className={styles.eyebrow}>Admin control plane</span>
            <h2 className={styles.title}>{mode === "create" ? "Create course" : "Edit course"}</h2>
            <p className={styles.subtitle}>
              Build course basics, lesson structure, reusable library items, and notebook-ready content from one place.
            </p>
          </div>

          <div className={styles.stepList}>
            {stepOrder.map((step) => {
              const active = activeStep === step;
              return (
                <button
                  key={step}
                  type="button"
                  className={`${styles.stepButton} ${active ? styles.stepButtonActive : ""}`}
                  onClick={() => scrollToStep(step)}
                >
                  <span className={styles.stepLabel}>{STEP_LABELS[step].title}</span>
                  <strong>{STEP_LABELS[step].description}</strong>
                  {step === "template" && selectedTemplate ? <span>Selected: {selectedTemplate.title}</span> : null}
                </button>
              );
            })}
          </div>

          <div className={styles.sidebarFooter}>
            <div className={styles.pillRow}>
              <span className={styles.pill}>{stats.modules} modules</span>
              <span className={styles.pill}>{stats.lessons} lessons</span>
              <span className={styles.pill}>{stats.items} items</span>
              <span className={styles.pill}>{stats.notebooks} notebooks</span>
            </div>
            <p className={styles.subtitle}>
              {selectedLibraryItem ? `Library item selected: ${selectedLibraryItem.title}` : "Use the library to keep lessons reusable."}
            </p>
          </div>
        </aside>

        <section className={styles.main}>
          <header className={styles.topbar}>
            <div className={styles.topbarCopy}>
              <span className={styles.eyebrow}>
                {isPersistedCourse ? courseDraft.slug || "Existing course" : "New course"}
              </span>
              <h2>{isPersistedCourse ? courseDraft.titleEn || courseDraft.titleDe || "Course builder" : "Course builder"}</h2>
              <p>
                {isPersistedCourse
                  ? "Refine structure, reusable assets, and delivery setup without leaving the admin workspace."
                  : "Start from a template or a blank course, then shape lessons and section assets."}
              </p>
            </div>

            <div className={styles.topbarActions}>
              <button type="button" className={styles.ghostButton} onClick={onClose}>
                {closeLabel}
              </button>
              <button
                type="button"
                className={styles.primaryButton}
                onClick={saveCourse}
                disabled={isSavingCourse}
              >
                {isSavingCourse ? "Saving..." : courseSaveLabel}
              </button>
            </div>
          </header>

          <div className={styles.content}>
            <div className={styles.contentInner}>
              {builderError ? <p className={styles.emptyState}>{builderError}</p> : null}
              {builderMessage ? <p className={styles.helperText}>{builderMessage}</p> : null}
              {inline
                ? stepOrder.map((step) => (
                    <CollapsibleSection
                      key={step}
                      id={stepSectionId(step)}
                      variant="step"
                      eyebrow={STEP_LABELS[step].title}
                      title={STEP_LABELS[step].title}
                      description={STEP_LABELS[step].description}
                      summary={renderStepSummary(step)}
                    >
                      {renderStepContent(step)}
                    </CollapsibleSection>
                  ))
                : (
                    <CollapsibleSection
                      variant="step"
                      eyebrow={STEP_LABELS[activeStep].title}
                      title={STEP_LABELS[activeStep].title}
                      description={STEP_LABELS[activeStep].description}
                      summary={renderStepSummary(activeStep)}
                    >
                      {renderStepContent(activeStep)}
                    </CollapsibleSection>
                  )}
            </div>
          </div>

          <footer className={styles.stickyFooter}>
            <div className={styles.stack}>
              <strong>{courseDraft.titleEn || courseDraft.titleDe || "Course builder draft"}</strong>
              <p className={styles.helperText}>Keep the structure modular. Each lesson uses one Main content section.</p>
            </div>
            <div className={styles.footerGroup}>
              {!inline ? (
                <>
                  <button
                    type="button"
                    className={styles.secondaryButton}
                    onClick={() => scrollToStep(stepOrder[Math.max(0, stepOrder.indexOf(activeStep) - 1)])}
                    disabled={stepOrder.indexOf(activeStep) === 0}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    className={styles.secondaryButton}
                    onClick={() => scrollToStep(stepOrder[Math.min(stepOrder.length - 1, stepOrder.indexOf(activeStep) + 1)])}
                    disabled={stepOrder.indexOf(activeStep) === stepOrder.length - 1}
                  >
                    Next
                  </button>
                </>
              ) : null}
              <button type="button" className={styles.primaryButton} disabled={isSavingCourse} onClick={saveCourse}>
                {isSavingCourse ? "Saving..." : courseSaveLabel}
              </button>
            </div>
          </footer>
        </section>
      </div>
    </div>
  );
};

export default AdminCourseBuilderModal;
