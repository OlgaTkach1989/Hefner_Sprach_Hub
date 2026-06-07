export type CourseBuilderSectionType = "introduction" | "main" | "conclusion";

export type CourseBuilderAssetType = "text" | "document" | "link" | "notebook";

export type CourseBuilderLanguage = "de" | "en";
export type CourseBuilderStructuredData = Record<string, unknown>;
export type CourseLifecycleStatus = "draft" | "in_review" | "approved" | "published" | "archived";

export type CourseReleaseReadinessCheck = {
  id: string;
  label: string;
  description: string;
  passed: boolean;
  required: boolean;
};

export type CourseReleaseReadiness = {
  checks: CourseReleaseReadinessCheck[];
  requiredChecksPassed: boolean;
  requiredFailedCount: number;
  optionalFailedCount: number;
  failedCheckIds: string[];
  isReadyForReview: boolean;
  isReadyForApproval: boolean;
  isReadyForPublish: boolean;
  statusLabel: string;
};

export type CourseVersionSummary = {
  id: number;
  versionNumber: number;
  lifecycleStatus: CourseLifecycleStatus;
  lifecycleLabel: string;
  source: string;
  changeSummary: string;
  createdAt: string;
  createdByEmail: string;
};

export type CourseGovernanceSummary = {
  lifecycleStatus: CourseLifecycleStatus;
  lifecycleLabel: string;
  isPubliclyVisible: boolean;
  statusChangedAt?: string | null;
  submittedForReviewAt?: string | null;
  approvedAt?: string | null;
  publishedAt?: string | null;
  archivedAt?: string | null;
  approvalsCount: number;
  versionsCount: number;
  latestVersion?: CourseVersionSummary | null;
  versionHistory?: CourseVersionSummary[];
  readiness: CourseReleaseReadiness;
  latestApproval?: {
    action: string;
    actionLabel: string;
    fromStatus: string;
    toStatus: string;
    note: string;
    createdAt: string;
    actorEmail: string;
  } | null;
};

export type CourseCompletionRule = {
  requiredCompletionPercent: number;
  requiredAttendancePercent: number;
  requiresAttestation: boolean;
};

export type CourseBuilderTemplateLessonSection = {
  sectionType: CourseBuilderSectionType;
  title: string;
  description: string;
  sortOrder: number;
  items: [];
};

export type CourseBuilderTemplateLesson = {
  title: string;
  description: string;
  sortOrder: number;
  sections: CourseBuilderTemplateLessonSection[];
};

export type CourseBuilderTemplateSummary = {
  id: number;
  slug: string;
  title: string;
  description: string;
  defaultLessonsCount: number;
  modules?: Array<{
    title: string;
    description: string;
    moduleType: "module" | "final_assessment";
    weekNumber?: number | null;
    sortOrder: number;
    isActive: boolean;
    lessons: CourseBuilderTemplateLesson[];
  }>;
  lessons: CourseBuilderTemplateLesson[];
};

export type CourseBuilderTemplateListResponse = {
  results: CourseBuilderTemplateSummary[];
};

export type CourseBuilderNotebookOption = {
  id: number;
  slug: string;
  name: string;
  contentKind: string;
  description: string;
  sourceUrl: string;
  courseId: number | null;
  courseSlug: string;
  supports_inline_lab: boolean;
};

export type CourseBuilderNotebookListResponse = {
  results: CourseBuilderNotebookOption[];
};

export type CourseBuilderLibraryItem = {
  id: number;
  sectionType: CourseBuilderSectionType;
  title: string;
  description: string;
  libraryGroup: string;
  assetType: CourseBuilderAssetType;
  language: CourseBuilderLanguage;
  bodyMarkdown: string;
  externalUrl: string;
  fileUrl: string;
  trainingContentId: number | null;
  trainingContentSlug: string;
  trainingContentName: string;
  audienceIds: number[];
  sortOrder: number;
  isActive: boolean;
};

export type CourseBuilderLibraryListResponse = {
  results: CourseBuilderLibraryItem[];
};

export type CourseBuilderLibraryItemUpsertInput = {
  sectionType: CourseBuilderSectionType;
  title: string;
  description: string;
  libraryGroup: string;
  assetType: CourseBuilderAssetType;
  language: CourseBuilderLanguage;
  bodyMarkdown: string;
  externalUrl: string;
  file?: File | null;
  trainingContentId?: number | null;
  audienceIds?: number[];
  sortOrder: number;
  isActive: boolean;
};

export type CourseBuilderSectionItem = {
  id?: number;
  sourceLibraryItemId?: number | null;
  title: string;
  description: string;
  assetType: CourseBuilderAssetType;
  activityType?: "video" | "text" | "quiz" | "assignment";
  language: CourseBuilderLanguage;
  bodyMarkdown: string;
  externalUrl: string;
  structuredData?: CourseBuilderStructuredData | null;
  trainingContent?: {
    id: number;
    slug: string;
    name: string;
    contentKind: string;
    sourceUrl: string;
  } | null;
  linkedTrainingContentId?: number | null;
  audienceIds?: number[];
  sortOrder: number;
  isActive: boolean;
};

export type CourseBuilderSection = {
  id?: number;
  sectionType: CourseBuilderSectionType;
  title: string;
  description: string;
  sortOrder: number;
  isActive: boolean;
  items: CourseBuilderSectionItem[];
};

export type CourseBuilderLesson = {
  id?: number;
  title: string;
  description: string;
  startsAt?: string | null;
  endsAt?: string | null;
  sortOrder: number;
  isActive: boolean;
  sections: CourseBuilderSection[];
};

export type CourseBuilderModuleType = "module" | "final_assessment";

export type CourseBuilderModule = {
  id?: number;
  title: string;
  description: string;
  moduleType: CourseBuilderModuleType;
  weekNumber?: number | null;
  startsAt?: string | null;
  endsAt?: string | null;
  sortOrder: number;
  isActive: boolean;
  lessons: CourseBuilderLesson[];
};

export type CourseBuilderCourse = {
  id?: number;
  slug: string;
  titleDe: string;
  titleEn: string;
  startsAt?: string | null;
  endsAt?: string | null;
  shortDescriptionDe: string;
  shortDescriptionEn: string;
  descriptionDe: string;
  descriptionEn: string;
  lessonsCount: number;
  trialAvailable: boolean;
  priceAmount: string;
  currency: string;
  isSubscription: boolean;
  isPublished: boolean;
  lifecycleStatus: CourseLifecycleStatus;
  providerType: "internal" | "linkedin_learning" | "coursera" | "udemy_business" | "external_custom";
  courseOrigin: "internal_authored" | "external_synced" | "external_manual";
  courseType: "text" | "video" | "audio" | "interactive" | "recording" | "live" | "blended" | "external";
  deliveryModel: "self_paced" | "cohort" | "instructor_led" | "hybrid";
  difficultyLevel: "foundation" | "beginner" | "intermediate" | "advanced" | "expert";
  confidentialityLevel: "public" | "internal" | "restricted" | "confidential" | "highly_confidential";
  knowledgeDomain: string;
  targetAudience: string;
  estimatedDurationMinutes: number;
  averageRating: string;
  ratingsCount: number;
  isMandatory: boolean;
  isRecommended: boolean;
  providerCourseId: string;
  externalUrl: string;
  tags: string[];
  skills: string[];
  metadataJson: Record<string, unknown>;
  customFields: Record<string, unknown>;
  requiredCompletionPercent: number;
  requiredAttendancePercent: number;
  requiresAttestation: boolean;
  heroImageUrl: string;
  seoTitleDe: string;
  seoTitleEn: string;
  seoDescriptionDe: string;
  seoDescriptionEn: string;
  geoCity: string;
  geoCountry: string;
  audienceIds: number[];
  instructorIds: number[];
  workspaceIds: number[];
  governance: CourseGovernanceSummary;
  completionRule: CourseCompletionRule;
  modules: CourseBuilderModule[];
  lessons: CourseBuilderLesson[];
  structureSummary: {
    modulesCount?: number;
    lessonsCount: number;
    itemsCount: number;
    notebookItemsCount: number;
    documentItemsCount: number;
    videoItemsCount?: number;
    quizItemsCount?: number;
    assignmentItemsCount?: number;
    finalAssessmentModulesCount?: number;
    hasStructuredOutline: boolean;
  };
};

export type CourseBuilderCourseListResponse = {
  results: CourseBuilderCourse[];
};

export type CourseBuilderCourseUpsertInput = {
  templateId?: number | null;
  slug: string;
  titleDe: string;
  titleEn: string;
  startsAt?: string | null;
  endsAt?: string | null;
  shortDescriptionDe: string;
  shortDescriptionEn: string;
  descriptionDe: string;
  descriptionEn: string;
  trialAvailable: boolean;
  priceAmount: string;
  currency: string;
  isSubscription: boolean;
  isPublished: boolean;
  lifecycleStatus: CourseLifecycleStatus;
  providerType: "internal" | "linkedin_learning" | "coursera" | "udemy_business" | "external_custom";
  courseOrigin: "internal_authored" | "external_synced" | "external_manual";
  courseType: "text" | "video" | "audio" | "interactive" | "recording" | "live" | "blended" | "external";
  deliveryModel: "self_paced" | "cohort" | "instructor_led" | "hybrid";
  difficultyLevel: "foundation" | "beginner" | "intermediate" | "advanced" | "expert";
  confidentialityLevel: "public" | "internal" | "restricted" | "confidential" | "highly_confidential";
  knowledgeDomain: string;
  targetAudience: string;
  estimatedDurationMinutes: number;
  averageRating: string;
  ratingsCount: number;
  isMandatory: boolean;
  isRecommended: boolean;
  providerCourseId: string;
  externalUrl: string;
  tags: string[];
  skills: string[];
  metadataJson: Record<string, unknown>;
  customFields: Record<string, unknown>;
  requiredCompletionPercent: number;
  requiredAttendancePercent: number;
  requiresAttestation: boolean;
  heroImageUrl: string;
  seoTitleDe: string;
  seoTitleEn: string;
  seoDescriptionDe: string;
  seoDescriptionEn: string;
  geoCity: string;
  geoCountry: string;
  audienceIds?: number[];
  instructorIds?: number[];
  workspaceIds?: number[];
  modules?: CourseBuilderModule[];
  lessons?: CourseBuilderLesson[];
};

export type CourseBuilderImportInput = {
  source?: "coursera_json" | "generic_json";
  payload: Record<string, unknown>;
  slug?: string;
  titleDe?: string;
  titleEn?: string;
  startsAt?: string | null;
  endsAt?: string | null;
  shortDescriptionDe?: string;
  shortDescriptionEn?: string;
  descriptionDe?: string;
  descriptionEn?: string;
  trialAvailable?: boolean;
  priceAmount?: string;
  currency?: string;
  isSubscription?: boolean;
  isPublished?: boolean;
  lifecycleStatus?: CourseLifecycleStatus;
  providerType?: CourseBuilderCourse["providerType"];
  courseOrigin?: CourseBuilderCourse["courseOrigin"];
  courseType?: CourseBuilderCourse["courseType"];
  deliveryModel?: CourseBuilderCourse["deliveryModel"];
  difficultyLevel?: CourseBuilderCourse["difficultyLevel"];
  confidentialityLevel?: CourseBuilderCourse["confidentialityLevel"];
  knowledgeDomain?: string;
  targetAudience?: string;
  estimatedDurationMinutes?: number;
  averageRating?: string;
  ratingsCount?: number;
  isMandatory?: boolean;
  isRecommended?: boolean;
  providerCourseId?: string;
  externalUrl?: string;
  tags?: string[];
  skills?: string[];
  metadataJson?: Record<string, unknown>;
  customFields?: Record<string, unknown>;
  requiredCompletionPercent?: number;
  requiredAttendancePercent?: number;
  requiresAttestation?: boolean;
  heroImageUrl?: string;
  geoCity?: string;
  geoCountry?: string;
  audienceIds?: number[];
  instructorIds?: number[];
  workspaceIds?: number[];
};

export type CourseBuilderGeneratedLessonItem = {
  title: string;
  description: string;
  assetType: CourseBuilderAssetType;
  activityType?: "video" | "text" | "quiz" | "assignment";
  language: CourseBuilderLanguage;
  bodyMarkdown: string;
  externalUrl: string;
  sourceLibraryItemId?: number | null;
  linkedTrainingContentId?: number | null;
  audienceIds?: number[];
  structuredData?: CourseBuilderStructuredData | null;
  sortOrder: number;
  isActive: boolean;
};

export type CourseBuilderGeneratedLessonSection = {
  sectionType: CourseBuilderSectionType;
  title: string;
  description: string;
  sortOrder: number;
  isActive: boolean;
  items: CourseBuilderGeneratedLessonItem[];
};

export type CourseBuilderGeneratedLessonDocument = {
  title?: string;
  description?: string;
  sections: CourseBuilderGeneratedLessonSection[];
};

export type CourseBuilderLessonGenerationInput = {
  title: string;
  description?: string;
  sourceText: string;
  language?: CourseBuilderLanguage;
  courseTitle?: string;
  moduleTitle?: string;
  videoUrl?: string;
  videoDescription?: string;
};

export type CourseBuilderVideoLessonGenerationInput = Omit<CourseBuilderLessonGenerationInput, "sourceText"> & {
  videoFile: File;
};

export type CourseBuilderLessonGenerationResponse = {
  document: CourseBuilderGeneratedLessonDocument;
  meta: {
    mode: string;
    provider: string;
    model: string;
    orchestrator?: string;
    fallbackReason?: string;
    source?: string;
    transcriptionProvider?: string;
    transcriptionModel?: string;
    transcriptCharacters?: number;
    videoLibraryItemId?: number;
  };
  transcriptText?: string;
};

export type CourseBuilderDeliveryStatus = "draft" | "open" | "running" | "finished";

export type CourseBuilderDeliveryAssignmentInput = {
  cohortId?: number | null;
  groupCode?: string;
  groupName?: string;
  capacity?: number;
  timezone?: string;
  startDate?: string | null;
  endDate?: string | null;
  status?: CourseBuilderDeliveryStatus;
  isPublic?: boolean;
  curatorId?: number | null;
};

export type CourseBuilderDeliveryAssignmentResponse = {
  created: boolean;
  courseId: number;
  courseSlug: string;
  cohort: {
    id: number;
    courseId: number;
    teacherId?: number | null;
    groupCode: string;
    groupName: string;
    capacity: number;
    timezone: string;
    startDate?: string | null;
    endDate?: string | null;
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
  };
  curator: {
    id: number;
    fullName: string;
    email: string;
    assignedCohortsCount: number;
    assignedCoursesCount: number;
  } | null;
};

export type CourseBuilderSessionSeedInput = {
  title?: string;
  description?: string;
  startsAt: string;
  endsAt: string;
};

export type CourseBuilderSessionSeedResponse = {
  courseId: number;
  courseSlug: string;
  cohort: {
    id: number;
    courseId: number;
    teacherId?: number | null;
    groupCode: string;
    groupName: string;
    capacity: number;
    timezone: string;
    startDate?: string | null;
    endDate?: string | null;
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
  };
  createdCount: number;
  remainingSlots: number;
  sessions: Array<{
    id: number;
    courseId: number;
    courseSlug: string;
    courseTitleDe: string;
    courseTitleEn: string;
    cohortId: number;
    cohortStatus: string;
    groupCode: string;
    groupName: string;
    teacherId?: number | null;
    teacherName: string;
    title: string;
    startsAt: string;
    endsAt: string;
    status: string;
    isCompleted: boolean;
    joinUrl?: string | null;
    recordingUrl?: string | null;
    attendanceSyncedAt?: string | null;
    attendanceSummary: {
      present: number;
      absent: number;
      excused: number;
      unknown: number;
    };
  }>;
};
