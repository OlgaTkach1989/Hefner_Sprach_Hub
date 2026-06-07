import type {
  CourseBuilderCourse,
  CourseBuilderCourseUpsertInput,
  CourseBuilderDeliveryStatus,
  CourseBuilderLanguage,
  CourseBuilderLesson,
  CourseBuilderModule,
  CourseBuilderSection,
  CourseBuilderSectionItem,
  CourseBuilderSectionType,
  CourseBuilderTemplateSummary,
} from "@/bll/course-builder/courseBuilder.type";

export type CourseBuilderMode = "create" | "edit";

export type CourseBuilderTemplateDraft = {
  id: number;
  slug: string;
  title: string;
  description: string;
  defaultLessonsCount: number;
};

export type CourseBuilderLibraryDraft = {
  id?: number;
  sectionType: CourseBuilderSectionType;
  title: string;
  description: string;
  libraryGroup: string;
  assetType: "text" | "document" | "link" | "notebook";
  language: CourseBuilderLanguage;
  bodyMarkdown: string;
  externalUrl: string;
  file: File | null;
  trainingContentId: number | null;
  audienceIds: number[];
  sortOrder: number;
  isActive: boolean;
};

export const createBlankLibraryDraft = (sectionType: CourseBuilderSectionType = "main"): CourseBuilderLibraryDraft => ({
  sectionType,
  title: "",
  description: "",
  libraryGroup: "",
  assetType: "document",
  language: "en",
  bodyMarkdown: "",
  externalUrl: "",
  file: null,
  trainingContentId: null,
  audienceIds: [],
  sortOrder: 10,
  isActive: true,
});

export const libraryDraftFromItem = (
  item: {
    id?: number;
    sectionType: CourseBuilderSectionType;
    title: string;
    description: string;
    libraryGroup: string;
    assetType: "text" | "document" | "link" | "notebook";
    language: CourseBuilderLanguage;
    bodyMarkdown: string;
    externalUrl: string;
    trainingContentId: number | null;
    audienceIds?: number[];
    sortOrder: number;
    isActive: boolean;
  },
): CourseBuilderLibraryDraft => ({
  id: item.id,
  sectionType: item.sectionType,
  title: item.title,
  description: item.description,
  libraryGroup: item.libraryGroup,
  assetType: item.assetType,
  language: normalizeCourseLanguage(item.language),
  bodyMarkdown: item.bodyMarkdown,
  externalUrl: item.externalUrl,
  file: null,
  trainingContentId: item.trainingContentId,
  audienceIds: item.audienceIds ?? [],
  sortOrder: item.sortOrder,
  isActive: item.isActive,
});

export type CourseBuilderSectionItemDraft = CourseBuilderSectionItem & {
  clientId: string;
};

export type CourseBuilderSectionDraft = Omit<CourseBuilderSection, "items"> & {
  clientId: string;
  items: CourseBuilderSectionItemDraft[];
};

export type CourseBuilderModuleDraft = Omit<CourseBuilderModule, "lessons"> & {
  clientId: string;
};

export type CourseBuilderLessonDraft = Omit<CourseBuilderLesson, "sections"> & {
  clientId: string;
  moduleClientId: string;
  sections: CourseBuilderSectionDraft[];
};

export type CourseBuilderCourseDraft = Omit<CourseBuilderCourseUpsertInput, "lessons" | "modules"> & {
  modules: CourseBuilderModuleDraft[];
  lessons: CourseBuilderLessonDraft[];
};

export type CourseBuilderDeliveryDraft = {
  cohortId: number | null;
  groupCode: string;
  groupName: string;
  capacity: number;
  timezone: string;
  startDate: string;
  endDate: string;
  status: CourseBuilderDeliveryStatus;
  isPublic: boolean;
  curatorId: number | null;
};

export type CourseBuilderDeliverySessionDraft = {
  clientId: string;
  title: string;
  description: string;
  startsAt: string;
  endsAt: string;
};

export type CourseBuilderDeliverySessionsDraft = {
  sessionCount: number;
  firstStartsAt: string;
  durationMinutes: number;
  intervalDays: number;
  sessions: CourseBuilderDeliverySessionDraft[];
};

export type CourseBuilderLessonSessionSeedSource = {
  title: string;
  description: string;
  sections: Array<{
    sectionType: CourseBuilderSectionType;
    title: string;
    description: string;
    itemCount: number;
  }>;
};

const DEFAULT_SECTION_ORDER: CourseBuilderSectionType[] = ["main"];
const DEFAULT_SECTION_TITLES: Record<CourseBuilderSectionType, string> = {
  introduction: "Introduction",
  main: "Main content",
  conclusion: "Conclusion",
};

const makeClientId = () => `cb-${Math.random().toString(36).slice(2, 10)}`;

const pad = (value: number) => String(value).padStart(2, "0");

const toLocalDateTimeInputValue = (value: Date): string =>
  `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`;

const parseLocalDateTime = (value: string): Date | null => {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

const preferEnglishCourseCopy = (englishValue?: string | null, fallbackValue?: string | null) => {
  if (typeof englishValue === "string" && englishValue.trim()) return englishValue;
  if (typeof fallbackValue === "string" && fallbackValue.trim()) return fallbackValue;
  return "";
};

export const normalizeCourseLanguage = (_value?: CourseBuilderLanguage | string | null): CourseBuilderLanguage => "en";

const groupCodeFromSlug = (slug: string) => {
  const normalized = slug.replace(/[^a-zA-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  return (normalized || "COURSE").slice(0, 72).toUpperCase();
};

const defaultLessonSections = (): CourseBuilderSectionDraft[] =>
  DEFAULT_SECTION_ORDER.map((sectionType, sectionIndex) => ({
    clientId: makeClientId(),
    id: undefined,
    sectionType,
    title: DEFAULT_SECTION_TITLES[sectionType],
    description: "",
    sortOrder: sectionIndex === 0 ? 10 : sectionIndex === 1 ? 20 : 30,
    isActive: true,
    items: [],
  }));

const mergeLessonSectionsIntoMain = (sections: CourseBuilderSection[]): CourseBuilderSectionDraft[] => {
  const orderedSections = [...sections].sort((left, right) => left.sortOrder - right.sortOrder);
  const mainSection = orderedSections.find((section) => section.sectionType === "main") ?? orderedSections[0];
  const mergedItems = orderedSections
    .flatMap((section) =>
      section.items.map((item) => ({
        item,
        sectionSortOrder: section.sortOrder,
      })),
    )
    .sort((left, right) => left.sectionSortOrder - right.sectionSortOrder || left.item.sortOrder - right.item.sortOrder);

  return [
    {
      clientId: makeClientId(),
      id: mainSection?.sectionType === "main" ? mainSection.id : undefined,
      sectionType: "main",
      title: mainSection?.title || DEFAULT_SECTION_TITLES.main,
      description: mainSection?.description || "",
      sortOrder: mainSection?.sortOrder || 10,
      isActive: mainSection?.isActive ?? true,
      items: mergedItems.map(({ item }, itemIndex) => ({
        clientId: makeClientId(),
        id: item.id,
        sourceLibraryItemId: item.sourceLibraryItemId ?? null,
        title: item.title,
        description: item.description,
        assetType: item.assetType,
        activityType: item.activityType,
        language: normalizeCourseLanguage(item.language),
        bodyMarkdown: item.bodyMarkdown,
        externalUrl: item.externalUrl,
        structuredData: item.structuredData ?? {},
        linkedTrainingContentId: item.trainingContent?.id ?? null,
        audienceIds: item.audienceIds ?? [],
        sortOrder: itemIndex + 1,
        isActive: item.isActive,
      })),
    },
  ];
};

export const createBlankCourseDraft = (): CourseBuilderCourseDraft => {
  const firstModuleClientId = makeClientId();
  return {
    templateId: null,
    slug: "",
    titleDe: "",
    titleEn: "",
    startsAt: null,
    endsAt: null,
    shortDescriptionDe: "",
    shortDescriptionEn: "",
    descriptionDe: "",
    descriptionEn: "",
    trialAvailable: false,
    priceAmount: "0.00",
    currency: "EUR",
    isSubscription: false,
    isPublished: false,
    lifecycleStatus: "draft",
    providerType: "internal",
    courseOrigin: "internal_authored",
    courseType: "interactive",
    deliveryModel: "cohort",
    difficultyLevel: "beginner",
    confidentialityLevel: "internal",
    knowledgeDomain: "",
    targetAudience: "",
    estimatedDurationMinutes: 0,
    averageRating: "0.00",
    ratingsCount: 0,
    isMandatory: false,
    isRecommended: true,
    providerCourseId: "",
    externalUrl: "",
    tags: [],
    skills: [],
    metadataJson: {},
    customFields: {},
    requiredCompletionPercent: 100,
    requiredAttendancePercent: 0,
    requiresAttestation: true,
    heroImageUrl: "",
    seoTitleDe: "",
    seoTitleEn: "",
    seoDescriptionDe: "",
    seoDescriptionEn: "",
    geoCity: "Berlin",
    geoCountry: "DE",
    audienceIds: [],
    instructorIds: [],
    workspaceIds: [],
    modules: [
      {
        clientId: firstModuleClientId,
        id: undefined,
        title: "Module 1 (Week 1)",
        description: "First learning module",
        moduleType: "module",
        weekNumber: 1,
        sortOrder: 10,
        isActive: true,
      },
    ],
    lessons: [1].map((lessonIndex) => ({
      clientId: makeClientId(),
      id: undefined,
      moduleClientId: firstModuleClientId,
      title: `Lesson ${lessonIndex}`,
      description: "",
      sortOrder: lessonIndex,
      isActive: true,
      sections: defaultLessonSections(),
    })),
  };
};

export const createBlankDeliveryDraft = (course?: Pick<CourseBuilderCourseDraft, "slug" | "titleEn" | "titleDe">): CourseBuilderDeliveryDraft => ({
  cohortId: null,
  groupCode: `${groupCodeFromSlug(course?.slug || "course")}_G1`,
  groupName: preferEnglishCourseCopy(course?.titleEn, course?.titleDe) || "New cohort",
  capacity: 20,
  timezone: "Europe/Berlin",
  startDate: "",
  endDate: "",
  status: "draft",
  isPublic: true,
  curatorId: null,
});

const defaultDeliveryStart = () => {
  const next = new Date();
  next.setDate(next.getDate() + 7);
  next.setHours(18, 0, 0, 0);
  return toLocalDateTimeInputValue(next);
};

export const createBlankDeliverySessionsDraft = (): CourseBuilderDeliverySessionsDraft => ({
  sessionCount: 1,
  firstStartsAt: defaultDeliveryStart(),
  durationMinutes: 120,
  intervalDays: 7,
  sessions: [],
});

type DeliverySessionSeedArgs = {
  lessonBlueprints: CourseBuilderLessonSessionSeedSource[];
  existingSessionsCount: number;
  sessionCount: number;
  firstStartsAt: string;
  durationMinutes: number;
  intervalDays: number;
};

const summarizeSectionForSession = (section: CourseBuilderLessonSessionSeedSource["sections"][number]) => {
  const sectionTitle = section.title.trim();
  const sectionDescription = section.description.trim();
  if (sectionDescription) {
    return `${sectionTitle}: ${sectionDescription}`;
  }
  if (section.itemCount > 0) {
    return `${sectionTitle}: ${section.itemCount} asset${section.itemCount === 1 ? "" : "s"}`;
  }
  return sectionTitle;
};

const buildSessionTitleFromLesson = (lesson: CourseBuilderLessonSessionSeedSource, slotIndex: number) => {
  const lessonTitle = lesson.title.trim();
  if (lessonTitle) return lessonTitle;
  const sectionTitle = lesson.sections.find((section) => section.title.trim())?.title.trim();
  return sectionTitle || `Lesson ${slotIndex}`;
};

const buildSessionDescriptionFromLesson = (lesson: CourseBuilderLessonSessionSeedSource) => {
  const lessonDescription = lesson.description.trim();
  const sectionSummary = lesson.sections
    .map(summarizeSectionForSession)
    .filter(Boolean)
    .join(" | ");
  if (lessonDescription && sectionSummary) {
    return `${lessonDescription} ${sectionSummary}`;
  }
  return lessonDescription || sectionSummary || "";
};

export const buildDeliverySessionDrafts = ({
  lessonBlueprints,
  existingSessionsCount,
  sessionCount,
  firstStartsAt,
  durationMinutes,
  intervalDays,
}: DeliverySessionSeedArgs): CourseBuilderDeliverySessionDraft[] => {
  const safeCount = Math.max(1, sessionCount || 1);
  const safeDurationMinutes = Math.max(15, durationMinutes || 120);
  const safeIntervalDays = Math.max(1, intervalDays || 7);
  const firstDate = parseLocalDateTime(firstStartsAt) ?? new Date();

  return Array.from({ length: safeCount }, (_value, index) => {
    const slotIndex = existingSessionsCount + index + 1;
    const startsAt = new Date(firstDate);
    startsAt.setDate(startsAt.getDate() + (index * safeIntervalDays));
    const endsAt = new Date(startsAt);
    endsAt.setMinutes(endsAt.getMinutes() + safeDurationMinutes);
    const lessonBlueprint = lessonBlueprints[index] ?? null;
    return {
      clientId: makeClientId(),
      title: lessonBlueprint ? buildSessionTitleFromLesson(lessonBlueprint, slotIndex) : `Lesson ${slotIndex}`,
      description: lessonBlueprint ? buildSessionDescriptionFromLesson(lessonBlueprint) : "",
      startsAt: toLocalDateTimeInputValue(startsAt),
      endsAt: toLocalDateTimeInputValue(endsAt),
    };
  });
};

export const courseDraftFromTemplate = (template: CourseBuilderTemplateSummary): CourseBuilderCourseDraft => {
  const base = createBlankCourseDraft();
  const templateModuleClientId = makeClientId();
  return {
    ...base,
    templateId: template.id,
    modules: [
      {
        clientId: templateModuleClientId,
        id: undefined,
        title: template.title || "Module 1 (Week 1)",
        description: template.description || "",
        moduleType: "module",
        weekNumber: 1,
        sortOrder: 10,
        isActive: true,
      },
    ],
    lessons: template.lessons.map((lesson, index) => ({
      clientId: makeClientId(),
      id: undefined,
      moduleClientId: templateModuleClientId,
      title: lesson.title || `Lesson ${index + 1}`,
      description: lesson.description || "",
      sortOrder: lesson.sortOrder || index + 1,
      isActive: true,
      sections: [
        {
          clientId: makeClientId(),
          id: undefined,
          sectionType: "main",
          title:
            lesson.sections.find((section) => section.sectionType === "main")?.title
            || lesson.sections[0]?.title
            || DEFAULT_SECTION_TITLES.main,
          description:
            lesson.sections.find((section) => section.sectionType === "main")?.description
            || lesson.sections[0]?.description
            || "",
          sortOrder: 10,
          isActive: true,
          items: [],
        },
      ],
    })),
  };
};

export const courseDraftFromCourse = (course: CourseBuilderCourse): CourseBuilderCourseDraft => {
  const moduleRows =
    (course.modules ?? []).length > 0
      ? (course.modules ?? [])
      : [
          {
            id: undefined,
            title: "Module 1 (Week 1)",
            description: "",
            moduleType: "module" as const,
            weekNumber: 1,
            sortOrder: 10,
            isActive: true,
            lessons: course.lessons,
          },
        ];

  const moduleClientIds = new Map<number | string, string>();
  const moduleDrafts = moduleRows.map((module, index) => {
    const clientId = makeClientId();
    moduleClientIds.set(module.id ?? `module-${index}`, clientId);
    return {
      clientId,
      id: module.id,
      title: module.title,
      description: module.description,
      moduleType: module.moduleType,
      weekNumber: module.weekNumber ?? null,
      sortOrder: module.sortOrder || (index + 1) * 10,
      isActive: module.isActive,
    };
  });

  const moduleClientByLessonId = new Map<number, string>();
  moduleRows.forEach((module, moduleIndex) => {
    const moduleClientId = moduleClientIds.get(module.id ?? `module-${moduleIndex}`);
    if (!moduleClientId) return;
    (module.lessons ?? []).forEach((lesson) => {
      if (lesson.id) moduleClientByLessonId.set(lesson.id, moduleClientId);
    });
  });

  return {
    templateId: null,
    slug: course.slug,
    titleDe: preferEnglishCourseCopy(course.titleEn, course.titleDe),
    titleEn: preferEnglishCourseCopy(course.titleEn, course.titleDe),
    shortDescriptionDe: preferEnglishCourseCopy(course.shortDescriptionEn, course.shortDescriptionDe),
    shortDescriptionEn: preferEnglishCourseCopy(course.shortDescriptionEn, course.shortDescriptionDe),
    descriptionDe: preferEnglishCourseCopy(course.descriptionEn, course.descriptionDe),
    descriptionEn: preferEnglishCourseCopy(course.descriptionEn, course.descriptionDe),
    startsAt: course.startsAt ?? null,
    endsAt: course.endsAt ?? null,
    trialAvailable: course.trialAvailable,
    priceAmount: course.priceAmount,
    currency: course.currency,
    isSubscription: course.isSubscription,
    isPublished: course.isPublished,
    lifecycleStatus: course.lifecycleStatus,
    providerType: course.providerType,
    courseOrigin: course.courseOrigin,
    courseType: course.courseType,
    deliveryModel: course.deliveryModel,
    difficultyLevel: course.difficultyLevel,
    confidentialityLevel: course.confidentialityLevel,
    knowledgeDomain: course.knowledgeDomain,
    targetAudience: course.targetAudience,
    estimatedDurationMinutes: course.estimatedDurationMinutes,
    averageRating: course.averageRating,
    ratingsCount: course.ratingsCount,
    isMandatory: course.isMandatory,
    isRecommended: course.isRecommended,
    providerCourseId: course.providerCourseId,
    externalUrl: course.externalUrl,
    tags: course.tags ?? [],
    skills: course.skills ?? [],
    metadataJson: course.metadataJson ?? {},
    customFields: course.customFields ?? {},
    requiredCompletionPercent: course.requiredCompletionPercent,
    requiredAttendancePercent: course.requiredAttendancePercent,
    requiresAttestation: course.requiresAttestation,
    heroImageUrl: course.heroImageUrl,
    seoTitleDe: preferEnglishCourseCopy(course.seoTitleEn, course.seoTitleDe),
    seoTitleEn: preferEnglishCourseCopy(course.seoTitleEn, course.seoTitleDe),
    seoDescriptionDe: preferEnglishCourseCopy(course.seoDescriptionEn, course.seoDescriptionDe),
    seoDescriptionEn: preferEnglishCourseCopy(course.seoDescriptionEn, course.seoDescriptionDe),
    geoCity: course.geoCity,
    geoCountry: course.geoCountry,
    audienceIds: course.audienceIds ?? [],
    instructorIds: course.instructorIds ?? [],
    workspaceIds: course.workspaceIds ?? [],
    modules: moduleDrafts,
    lessons: course.lessons.map((lesson, index) => ({
      clientId: makeClientId(),
      id: lesson.id,
      moduleClientId:
        (lesson.id ? moduleClientByLessonId.get(lesson.id) : undefined) || moduleDrafts[0]?.clientId || "",
      title: lesson.title,
      description: lesson.description,
      sortOrder: lesson.sortOrder || index + 1,
      isActive: lesson.isActive,
      sections: mergeLessonSectionsIntoMain(lesson.sections),
    })),
  };
};

export const serializeCourseDraft = (draft: CourseBuilderCourseDraft): CourseBuilderCourseUpsertInput => {
  const title = preferEnglishCourseCopy(draft.titleEn, draft.titleDe);
  const shortDescription = preferEnglishCourseCopy(draft.shortDescriptionEn, draft.shortDescriptionDe);
  const description = preferEnglishCourseCopy(draft.descriptionEn, draft.descriptionDe);
  const seoTitle = preferEnglishCourseCopy(draft.seoTitleEn, draft.seoTitleDe);
  const seoDescription = preferEnglishCourseCopy(draft.seoDescriptionEn, draft.seoDescriptionDe);

  return {
    templateId: draft.templateId,
    slug: draft.slug.trim().toLowerCase(),
    titleDe: title,
    titleEn: title,
    shortDescriptionDe: shortDescription,
    shortDescriptionEn: shortDescription,
    descriptionDe: description,
    descriptionEn: description,
    startsAt: draft.startsAt ?? null,
    endsAt: draft.endsAt ?? null,
    trialAvailable: draft.trialAvailable,
    priceAmount: draft.priceAmount,
    currency: draft.currency,
    isSubscription: draft.isSubscription,
    isPublished: draft.lifecycleStatus === "published",
    lifecycleStatus: draft.lifecycleStatus,
    providerType: draft.providerType,
    courseOrigin: draft.courseOrigin,
    courseType: draft.courseType,
    deliveryModel: draft.deliveryModel,
    difficultyLevel: draft.difficultyLevel,
    confidentialityLevel: draft.confidentialityLevel,
    knowledgeDomain: draft.knowledgeDomain,
    targetAudience: draft.targetAudience,
    estimatedDurationMinutes: draft.estimatedDurationMinutes,
    averageRating: draft.averageRating,
    ratingsCount: draft.ratingsCount,
    isMandatory: draft.isMandatory,
    isRecommended: draft.isRecommended,
    providerCourseId: draft.providerCourseId,
    externalUrl: draft.externalUrl,
    tags: draft.tags ?? [],
    skills: draft.skills ?? [],
    metadataJson: draft.metadataJson ?? {},
    customFields: draft.customFields ?? {},
    requiredCompletionPercent: draft.requiredCompletionPercent,
    requiredAttendancePercent: draft.requiredAttendancePercent,
    requiresAttestation: draft.requiresAttestation,
    heroImageUrl: draft.heroImageUrl,
    seoTitleDe: seoTitle,
    seoTitleEn: seoTitle,
    seoDescriptionDe: seoDescription,
    seoDescriptionEn: seoDescription,
    geoCity: draft.geoCity,
    geoCountry: draft.geoCountry,
    audienceIds: draft.audienceIds ?? [],
    instructorIds: draft.instructorIds ?? [],
    workspaceIds: draft.workspaceIds ?? [],
    modules: draft.modules.map((module, moduleIndex) => ({
      id: module.id,
      title: module.title,
      description: module.description,
      moduleType: module.moduleType,
      weekNumber: module.weekNumber ?? null,
      sortOrder: module.sortOrder || (moduleIndex + 1) * 10,
      isActive: module.isActive,
      lessons: draft.lessons
        .filter((lesson) => lesson.moduleClientId === module.clientId)
        .map((lesson, lessonIndex) => ({
          id: lesson.id,
          title: lesson.title,
          description: lesson.description,
          sortOrder: lesson.sortOrder || lessonIndex + 1,
          isActive: lesson.isActive,
          sections: lesson.sections.map((section) => ({
            id: section.id,
            sectionType: section.sectionType,
            title: section.title,
            description: section.description,
            sortOrder: section.sortOrder,
            isActive: section.isActive,
            items: section.items.map((item, itemIndex) => ({
              id: item.id,
              sourceLibraryItemId: item.sourceLibraryItemId ?? null,
              title: item.title,
              description: item.description,
              assetType: item.assetType,
              activityType: item.activityType,
              language: normalizeCourseLanguage(item.language),
              bodyMarkdown: item.bodyMarkdown,
              externalUrl: item.externalUrl,
              structuredData: item.structuredData ?? {},
              linkedTrainingContentId: item.linkedTrainingContentId ?? null,
              audienceIds: item.audienceIds ?? [],
              sortOrder: item.sortOrder || itemIndex + 1,
              isActive: item.isActive,
            })),
          })),
        })),
    })),
    lessons: draft.lessons.map((lesson, lessonIndex) => ({
      id: lesson.id,
      title: lesson.title,
      description: lesson.description,
      sortOrder: lesson.sortOrder || lessonIndex + 1,
      isActive: lesson.isActive,
      sections: lesson.sections.map((section) => ({
        id: section.id,
        sectionType: section.sectionType,
        title: section.title,
        description: section.description,
        sortOrder: section.sortOrder,
        isActive: section.isActive,
        items: section.items.map((item, itemIndex) => ({
          id: item.id,
          sourceLibraryItemId: item.sourceLibraryItemId ?? null,
          title: item.title,
          description: item.description,
          assetType: item.assetType,
          activityType: item.activityType,
          language: normalizeCourseLanguage(item.language),
          bodyMarkdown: item.bodyMarkdown,
          externalUrl: item.externalUrl,
          structuredData: item.structuredData ?? {},
          linkedTrainingContentId: item.linkedTrainingContentId ?? null,
          audienceIds: item.audienceIds ?? [],
          sortOrder: item.sortOrder || itemIndex + 1,
          isActive: item.isActive,
        })),
      })),
    })),
  };
};

export const templateSummaryToDraft = (template: CourseBuilderTemplateSummary): CourseBuilderTemplateDraft => ({
  id: template.id,
  slug: template.slug,
  title: template.title,
  description: template.description,
  defaultLessonsCount: template.defaultLessonsCount,
});
