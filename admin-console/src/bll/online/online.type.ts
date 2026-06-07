export type OnlineCohortCard = {
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

export type OnlineCohortListResponse = {
  results: OnlineCohortCard[];
};

export type OnlineCourseSessionsSummary = {
  total: number;
  completed: number;
  planned: number;
  live: number;
  canceled: number;
};

export type OnlineCourseAudience = {
  id: number;
  slug: string;
  name: string;
  shortLabel: string;
};

export type OnlineCourseLifecycleStatus = "draft" | "in_review" | "approved" | "published" | "archived";

export type OnlineCourseReleaseReadinessCheck = {
  id: string;
  label: string;
  description: string;
  passed: boolean;
  required: boolean;
};

export type OnlineCourseReleaseReadiness = {
  checks: OnlineCourseReleaseReadinessCheck[];
  requiredChecksPassed: boolean;
  requiredFailedCount: number;
  optionalFailedCount: number;
  failedCheckIds: string[];
  isReadyForReview: boolean;
  isReadyForApproval: boolean;
  isReadyForPublish: boolean;
  statusLabel: string;
};

export type OnlineCourseVersionSummary = {
  id: number;
  versionNumber: number;
  lifecycleStatus: OnlineCourseLifecycleStatus;
  lifecycleLabel: string;
  source: string;
  changeSummary: string;
  createdAt: string;
  createdByEmail: string;
};

export type OnlineCourseGovernance = {
  lifecycleStatus: OnlineCourseLifecycleStatus;
  lifecycleLabel: string;
  isPubliclyVisible: boolean;
  statusChangedAt?: string | null;
  submittedForReviewAt?: string | null;
  approvedAt?: string | null;
  publishedAt?: string | null;
  archivedAt?: string | null;
  approvalsCount: number;
  versionsCount: number;
  latestVersion?: OnlineCourseVersionSummary | null;
  versionHistory?: OnlineCourseVersionSummary[];
  readiness: OnlineCourseReleaseReadiness;
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

export type OnlineCourseCard = {
  id: number;
  slug: string;
  titleDe: string;
  titleEn: string;
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
  audienceIds: number[];
  audiences: OnlineCourseAudience[];
  lessonsCount: number;
  isPublished: boolean;
  lifecycleStatus: OnlineCourseLifecycleStatus;
  trialAvailable: boolean;
  priceAmount: string | number;
  currency: string;
  cohortsCount: number;
  publicCohortsCount: number;
  studentsCount: number;
  attendancePercent: number;
  nearestSessionAt: string | null;
  teachers: string[];
  governance: OnlineCourseGovernance;
  sessionsSummary: OnlineCourseSessionsSummary;
};

export type OnlineCourseListResponse = {
  results: OnlineCourseCard[];
};

export type OnlineCohortDetailSession = {
  id: number;
  title: string;
  startsAt: string;
  endsAt: string;
  status: "scheduled" | "live" | "ended" | "canceled";
  isCompleted: boolean;
  joinUrl?: string | null;
  attendanceSummary: {
    present: number;
    absent: number;
    excused: number;
    unknown: number;
  };
};

export type OnlineCohortDetailStudent = {
  enrollmentId: number;
  fullName: string;
  email: string;
  status: string;
  attendancePercent: number;
};

export type OnlineCohortDetail = {
  id: number;
  teacherId?: number | null;
  groupCode: string;
  groupName: string;
  courseSlug: string;
  courseTitleDe: string;
  courseTitleEn: string;
  teacherName: string;
  studentsCount: number;
  attendancePercent: number;
  nearestSessionAt?: string | null;
  sessionsSummary?: {
    total: number;
    completed: number;
    planned: number;
  };
  sessions: OnlineCohortDetailSession[];
  students: OnlineCohortDetailStudent[];
};

export type OnlineSessionStatus = OnlineCohortDetailSession["status"];

export type OnlineSessionStatusUpdateResponse = {
  id: number;
  title?: string;
  status: OnlineSessionStatus;
  isCompleted: boolean;
  cohortId: number;
  cohortStatus: string;
  joinUrl?: string | null;
  attendanceSyncedAt?: string | null;
  syncError?: string | null;
  sync?: {
    sync: string;
    studentsTotal: number;
    attendanceRowsTotal: number;
    attendanceSummary: {
      present: number;
      absent: number;
      excused: number;
      unknown: number;
    };
  } | null;
};

export type OnlineAdminAttendanceSyncResponse = {
  sessionId: number;
  status: OnlineSessionStatus;
  sync: string;
  studentsTotal: number;
  attendanceRowsTotal: number;
  attendanceSummary: {
    present: number;
    absent: number;
    excused: number;
    unknown: number;
  };
  attendanceSyncedAt?: string | null;
};

export type OnlineAdminSessionRow = {
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
  status: OnlineSessionStatus;
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
};

export type OnlineAdminSessionListResponse = {
  results: OnlineAdminSessionRow[];
};

export type OnlineIdentityProviderSummary = {
  id: number;
  slug: string;
  displayName: string;
  providerType: "local_password" | "google_oidc" | "microsoft_oidc";
  providerLabel: string;
  issuer: string;
  discoveryUrl: string;
  authorizationUrl: string;
  tokenUrl: string;
  jwksUrl: string;
  redirectUri: string;
  tenantId: string;
  clientId: string;
  scopes: string[];
  claimMap: Record<string, unknown>;
  isEnabled: boolean;
  isSso: boolean;
  isDefault: boolean;
  isReady: boolean;
  verificationStatus: "draft" | "ready" | "error";
  verificationLabel: string;
  verificationMessage: string;
  lastVerifiedAt: string | null;
};

export type OnlineAdminScopeAssignment = {
  id: number;
  role: "manager" | "delivery_manager" | "compliance_manager" | "review_manager";
  roleLabel: string;
  scopeType: "academy" | "course" | "cohort";
  scopeTypeLabel: string;
  scopeLabel: string;
  scopeKey: string;
  note: string;
  isPrimary: boolean;
  isActive: boolean;
  createdAt: string;
  createdByEmail: string;
  user: {
    id: number;
    email: string;
    fullName: string;
    isActive: boolean;
  };
  course: {
    id: number;
    slug: string;
    titleDe: string;
    titleEn: string;
  } | null;
  cohort: {
    id: number;
    groupCode: string;
    groupName: string;
    courseId: number;
    courseTitleDe: string;
    courseTitleEn: string;
  } | null;
};

export type OnlineAdminScopeAssignmentListResponse = {
  results: OnlineAdminScopeAssignment[];
};

export type OnlineAdminScopeAssignmentWriteInput = {
  userId: number;
  role: OnlineAdminScopeAssignment["role"];
  scopeType: OnlineAdminScopeAssignment["scopeType"];
  courseId?: number | null;
  cohortId?: number | null;
  note?: string;
  isPrimary?: boolean;
  isActive?: boolean;
};

export type OnlineAdminScopeAssignmentPatchInput = {
  note?: string;
  isPrimary?: boolean;
  isActive?: boolean;
};

export type OnlineAdminEnterpriseAtRiskLearner = {
  enrollmentId: number;
  fullName: string;
  email: string;
  courseId: number;
  courseTitle: string;
  cohortId: number;
  cohortLabel: string;
  progressPercent: number;
  attendancePercent: number;
  completionStatus: string;
  completionStatusLabel: string;
  evidenceIssued: boolean;
  attestationRequired: boolean;
  riskReasons: string[];
};

export type OnlineAdminEnterpriseSummary = {
  courseId: number | null;
  identity: {
    totalProviders: number;
    enabledProviders: number;
    readyProviders: number;
    defaultProvider: OnlineIdentityProviderSummary | null;
    linkedAccountsTotal: number;
    googleClientConfigured: boolean;
    graphClientConfigured: boolean;
    providers: OnlineIdentityProviderSummary[];
  };
  scopedAccess: {
    activeAssignments: number;
    primaryAssignments: number;
    managerAssignments: number;
    deliveryManagerAssignments: number;
    complianceManagerAssignments: number;
    reviewManagerAssignments: number;
    recentAssignments: OnlineAdminScopeAssignment[];
  };
  learning: {
    activeEnrollments: number;
    completedEnrollments: number;
    readyForAttestation: number;
    evidenceIssued: number;
    attendanceAlerts: number;
    overdueEnrollments: number;
    averageProgressPercent: number;
  };
  delivery: {
    liveSessions: number;
    upcomingSessions7d: number;
    unsyncedAttendanceSessions: number;
    sessionsWithoutRecording: number;
    lowAttendanceCohorts: number;
  };
  compliance: {
    pendingReviewCourses: number;
    approvedNotPublishedCourses: number;
    publishBlockedCourses: number;
    auditEvents30d: number;
    evidenceCoveragePercent: number;
  };
  atRiskLearners: OnlineAdminEnterpriseAtRiskLearner[];
};

export type OnlineAdminSessionBulkAction = "open" | "end" | "sync";

export type OnlineAdminSessionBulkActionInput = {
  action: OnlineAdminSessionBulkAction;
  sessionIds: number[];
};

export type OnlineAdminSessionBulkActionResult = {
  sessionId: number;
  action: OnlineAdminSessionBulkAction;
  ok: boolean;
  error: string | null;
  session: OnlineSessionStatusUpdateResponse | null;
};

export type OnlineAdminSessionBulkActionResponse = {
  action: OnlineAdminSessionBulkAction;
  processedCount: number;
  succeededCount: number;
  failedCount: number;
  results: OnlineAdminSessionBulkActionResult[];
};

export type OnlineCourseDetailSession = {
  id: number;
  title: string;
  groupCode: string;
  groupName: string;
  startsAt: string;
  endsAt: string;
  status: OnlineSessionStatus;
  isCompleted: boolean;
  attendanceSummary: {
    present: number;
    absent: number;
    excused: number;
    unknown: number;
  };
};

export type OnlineCourseDetail = OnlineCourseCard & {
  descriptionDe: string;
  descriptionEn: string;
  metadataJson?: Record<string, unknown>;
  customFields?: Record<string, unknown>;
  cohortsSummary: {
    total: number;
    public: number;
    running: number;
    open: number;
    finished: number;
    draft: number;
  };
  cohorts: OnlineCohortCard[];
  modules?: Array<{
    id?: number | null;
    title: string;
    description: string;
    moduleType: "module" | "final_assessment";
    weekNumber?: number | null;
    sortOrder: number;
    isActive: boolean;
    lessonsCount: number;
    itemsCount: number;
  }>;
  sessions: OnlineCourseDetailSession[];
};

export type OnlineAdminCuratorProfileMini = {
  schoolEmail: string;
  privateEmail: string;
  phone: string;
  shortName: string;
};

export type OnlineAdminStudentProfileMini = {
  id: number;
  employeeId: string;
  department: string;
  teamName: string;
  officeLocation: string;
  jobTitle: string;
  managerName: string;
  phone: string;
  employmentStatus: "active" | "on_leave" | "contractor" | "inactive";
  hiredAt: string | null;
};

export type OnlineAdminInstructorProfileMini = {
  id: number;
  department: string;
  jobTitle: string;
  bio: string;
  expertiseAreas: string[];
  spokenLanguages: string[];
  canAuthor: boolean;
  canReview: boolean;
  canPublish: boolean;
  canGenerateWithAi: boolean;
  canManageAssessments: boolean;
  customFields: Record<string, unknown>;
};

export type OnlineAdminUserSummary = {
  id: number;
  email: string;
  username: string | null;
  firstName: string;
  lastName: string;
  fullName: string;
  isActive: boolean;
  isAdmin: boolean;
  isSuperuser: boolean;
  isStudent: boolean;
  isCurator: boolean;
  curatorId: number | null;
  assignedCohortsCount: number;
  assignedCoursesCount: number;
  curatorProfile: OnlineAdminCuratorProfileMini | null;
  studentProfile: OnlineAdminStudentProfileMini | null;
};

export type OnlineAdminUserListResponse = {
  results: OnlineAdminUserSummary[];
};

export type OnlineAdminCuratorSummary = {
  id: number;
  userId: number;
  email: string;
  username: string | null;
  isActive: boolean;
  isAdmin: boolean;
  firstName: string;
  lastName: string;
  fullName: string;
  schoolEmail: string;
  privateEmail: string;
  phone: string;
  shortName: string;
  assignedCohortsCount: number;
  assignedCoursesCount: number;
  assignedCohorts: OnlineCohortCard[];
  instructorProfile: OnlineAdminInstructorProfileMini | null;
};

export type OnlineAdminCuratorListResponse = {
  results: OnlineAdminCuratorSummary[];
};

export type OnlineAdminCuratorCreateInput = {
  userId: number;
  firstName: string;
  lastName: string;
  schoolEmail: string;
  privateEmail: string;
  phone: string;
  shortName: string;
};

export type OnlineAdminCuratorUpdateInput = Partial<Omit<OnlineAdminCuratorCreateInput, "userId">>;

export type OnlineAdminCuratorOnboardingInput = {
  email: string;
  temporaryPassword: string;
  firstName: string;
  lastName: string;
  schoolEmail: string;
  privateEmail: string;
  phone: string;
  shortName: string;
};

export type OnlineAdminUserStatusInput = {
  isActive: boolean;
};

export type OnlineAdminUserTemporaryPasswordInput = {
  temporaryPassword: string;
};

export type OnlineAdminCohortCuratorAssignmentInput = {
  curatorId: number | null;
};

export type OnlineAdminCohortCuratorAssignmentResponse = {
  cohort: OnlineCohortCard;
  curator: OnlineAdminCuratorSummary | null;
};

export type OnlineAdminCatalogSearchArgs = {
  q?: string;
  confidentialityLevel?: OnlineCourseCard["confidentialityLevel"] | "";
  providerType?: OnlineCourseCard["providerType"] | "";
  courseType?: OnlineCourseCard["courseType"] | "";
  difficultyLevel?: OnlineCourseCard["difficultyLevel"] | "";
  knowledgeDomain?: string;
  ratingMin?: number;
};

export type OnlineAdminCatalogSearchCourseHit = {
  id: number;
  title: string;
  slug: string;
  providerType: OnlineCourseCard["providerType"];
  courseType: OnlineCourseCard["courseType"];
  confidentialityLevel: OnlineCourseCard["confidentialityLevel"];
  knowledgeDomain: string;
  estimatedDurationMinutes: number;
  averageRating: string;
  targetAudience: string;
  tags: string[];
  skills: string[];
};

export type OnlineAdminCatalogSearchStudentHit = {
  id: number;
  fullName: string;
  email: string;
  department: string;
  teamName: string;
  jobTitle: string;
  employmentStatus: string;
};

export type OnlineAdminCatalogSearchInstructorHit = {
  id: number;
  fullName: string;
  schoolEmail: string;
  department: string;
  jobTitle: string;
  expertiseAreas: string[];
  canAuthor: boolean;
  canPublish: boolean;
};

export type OnlineAdminCatalogSearchProgramHit = {
  id: number;
  title: string;
  slug: string;
  assignmentMode: "manual" | "role_based" | "ai_recommended" | "hybrid";
  targetAudience: string;
  assignmentsCount: number;
};

export type OnlineAdminCatalogSearchKnowledgeHit = {
  id: number;
  title: string;
  sourceTitle: string;
  documentType: "pdf" | "docx" | "markdown" | "html" | "transcript" | "link";
  language: string;
  isActive: boolean;
  linkedCourseId: number | null;
};

export type OnlineAdminCatalogSearchResponse = {
  courses: OnlineAdminCatalogSearchCourseHit[];
  students: OnlineAdminCatalogSearchStudentHit[];
  instructors: OnlineAdminCatalogSearchInstructorHit[];
  programs: OnlineAdminCatalogSearchProgramHit[];
  knowledgeDocuments: OnlineAdminCatalogSearchKnowledgeHit[];
};

export type OnlineAdminCatalogAttributeDefinition = {
  id: number;
  slug: string;
  entityType: "course" | "student" | "instructor" | "program" | "knowledge";
  label: string;
  helpText: string;
  dataType:
    | "text"
    | "long_text"
    | "number"
    | "decimal"
    | "boolean"
    | "date"
    | "datetime"
    | "single_select"
    | "multi_select"
    | "json";
  options: unknown[];
  defaultValue: unknown;
  isRequired: boolean;
  isFilterable: boolean;
  isSearchable: boolean;
  isActive: boolean;
  sortOrder: number;
  valuesCount: number;
};

export type OnlineAdminCatalogAttributeDefinitionListResponse = {
  results: OnlineAdminCatalogAttributeDefinition[];
};

export type OnlineAdminCatalogAttributeDefinitionWriteInput = {
  slug: string;
  entityType: OnlineAdminCatalogAttributeDefinition["entityType"];
  label: string;
  helpText?: string;
  dataType: OnlineAdminCatalogAttributeDefinition["dataType"];
  options?: unknown[];
  defaultValue?: unknown;
  isRequired?: boolean;
  isFilterable?: boolean;
  isSearchable?: boolean;
  isActive?: boolean;
  sortOrder?: number;
};

export type OnlineAdminCatalogAttributeValue = {
  id: number;
  definitionId: number;
  entityType: OnlineAdminCatalogAttributeDefinition["entityType"];
  objectId: number;
  valueJson: unknown;
  updatedAt: string;
};

export type OnlineAdminCatalogAttributeValueListResponse = {
  results: OnlineAdminCatalogAttributeValue[];
};

export type OnlineAdminCatalogAttributeValueWriteInput = {
  definitionId: number;
  entityType: OnlineAdminCatalogAttributeDefinition["entityType"];
  objectId: number;
  valueJson?: unknown;
};

export type OnlineAdminStudentProfile = {
  id: number;
  email: string;
  firstName: string;
  lastName: string;
  employeeId: string;
  department: string;
  teamName: string;
  officeLocation: string;
  jobTitle: string;
  managerName: string;
  phone: string;
  preferredLanguage: string;
  employmentStatus: "active" | "on_leave" | "contractor" | "inactive";
  hiredAt: string | null;
  customFields: Record<string, unknown>;
  activeEnrollmentsCount: number;
};

export type OnlineAdminStudentProfileListResponse = {
  results: OnlineAdminStudentProfile[];
};

export type OnlineAdminStudentProfilePatchInput = Partial<
  Pick<
    OnlineAdminStudentProfile,
    | "firstName"
    | "lastName"
    | "employeeId"
    | "department"
    | "teamName"
    | "officeLocation"
    | "jobTitle"
    | "managerName"
    | "phone"
    | "preferredLanguage"
    | "employmentStatus"
    | "hiredAt"
    | "customFields"
  >
>;

export type OnlineAdminInstructorProfile = {
  id: number;
  teacherId: number;
  fullName: string;
  schoolEmail: string;
  department: string;
  jobTitle: string;
  bio: string;
  expertiseAreas: string[];
  spokenLanguages: string[];
  canAuthor: boolean;
  canReview: boolean;
  canPublish: boolean;
  canGenerateWithAi: boolean;
  canManageAssessments: boolean;
  customFields: Record<string, unknown>;
};

export type OnlineAdminInstructorProfileListResponse = {
  results: OnlineAdminInstructorProfile[];
};

export type OnlineAdminInstructorProfileWriteInput = {
  teacherId?: number;
  department?: string;
  jobTitle?: string;
  bio?: string;
  expertiseAreas?: string[];
  spokenLanguages?: string[];
  canAuthor?: boolean;
  canReview?: boolean;
  canPublish?: boolean;
  canGenerateWithAi?: boolean;
  canManageAssessments?: boolean;
  customFields?: Record<string, unknown>;
};

export type OnlineAdminExternalCatalogProvider = {
  id: number;
  slug: string;
  displayName: string;
  providerType: "linkedin_learning" | "coursera" | "udemy_business" | "custom";
  importMode: "api" | "file" | "manual";
  baseUrl: string;
  apiBaseUrl: string;
  metadataSchema: Record<string, unknown>;
  isEnabled: boolean;
  syncStatus: "draft" | "ready" | "error";
  verificationMessage: string;
  lastSyncAt: string | null;
};

export type OnlineAdminExternalCatalogProviderListResponse = {
  results: OnlineAdminExternalCatalogProvider[];
};

export type OnlineAdminExternalCatalogProviderWriteInput = {
  slug: string;
  displayName: string;
  providerType: OnlineAdminExternalCatalogProvider["providerType"];
  importMode: OnlineAdminExternalCatalogProvider["importMode"];
  baseUrl?: string;
  apiBaseUrl?: string;
  metadataSchema?: Record<string, unknown>;
  isEnabled?: boolean;
  syncStatus?: OnlineAdminExternalCatalogProvider["syncStatus"];
  verificationMessage?: string;
};

export type OnlineAdminLearningProgramCourseItem = {
  id: number;
  courseId: number;
  courseTitle: string;
  sortOrder: number;
  isRequired: boolean;
  unlockRule: "immediate" | "after_previous" | "after_percent";
  minCompletionPercent: number;
  note: string;
};

export type OnlineAdminLearningProgram = {
  id: number;
  slug: string;
  title: string;
  description: string;
  targetAudience: string;
  assignmentMode: "manual" | "role_based" | "ai_recommended" | "hybrid";
  recommendationPrompt: string;
  isActive: boolean;
  createdByEmail: string | null;
  programCourses: OnlineAdminLearningProgramCourseItem[];
  assignmentsCount: number;
};

export type OnlineAdminLearningProgramListResponse = {
  results: OnlineAdminLearningProgram[];
};

export type OnlineAdminLearningProgramWriteInput = {
  slug: string;
  title: string;
  description?: string;
  targetAudience?: string;
  assignmentMode: OnlineAdminLearningProgram["assignmentMode"];
  recommendationPrompt?: string;
  isActive?: boolean;
  programCourses?: Array<{
    id?: number;
    courseId: number;
    sortOrder?: number;
    isRequired?: boolean;
    unlockRule?: OnlineAdminLearningProgramCourseItem["unlockRule"];
    minCompletionPercent?: number;
    note?: string;
  }>;
};

export type OnlineAdminStudentProgramAssignment = {
  id: number;
  profileId: number;
  programId: number;
  programTitle: string;
  source: "manual" | "standard_set" | "ai_recommendation";
  sourceLabel: string;
  status: "active" | "completed" | "paused";
  statusLabel: string;
  aiReason: string;
  assignedByEmail: string | null;
  startedAt: string;
  completedAt: string | null;
};

export type OnlineAdminStudentProgramAssignmentListResponse = {
  results: OnlineAdminStudentProgramAssignment[];
};

export type OnlineAdminStudentProgramAssignmentWriteInput = {
  profileId: number;
  programId: number;
  source?: OnlineAdminStudentProgramAssignment["source"];
  status?: OnlineAdminStudentProgramAssignment["status"];
  aiReason?: string;
  completedAt?: string | null;
};

export type OnlineAdminKnowledgeSource = {
  id: number;
  slug: string;
  title: string;
  description: string;
  sourceType:
    | "upload"
    | "url"
    | "sharepoint"
    | "confluence"
    | "notion"
    | "video_transcript"
    | "audio_transcript"
    | "external_kb";
  externalUrl: string;
  ownerEmail: string | null;
  linkedCourseId: number | null;
  linkedCourseTitle: string | null;
  isActive: boolean;
  isIndexed: boolean;
  lastIngestedAt: string | null;
  metadataJson: Record<string, unknown>;
};

export type OnlineAdminKnowledgeSourceListResponse = {
  results: OnlineAdminKnowledgeSource[];
};

export type OnlineAdminKnowledgeSourceWriteInput = {
  slug: string;
  title: string;
  description?: string;
  sourceType: OnlineAdminKnowledgeSource["sourceType"];
  externalUrl?: string;
  ownerId?: number | null;
  linkedCourseId?: number | null;
  isActive?: boolean;
  isIndexed?: boolean;
  metadataJson?: Record<string, unknown>;
};

export type OnlineAdminKnowledgeDocument = {
  id: number;
  sourceId: number;
  sourceTitle: string;
  title: string;
  description: string;
  documentType: "pdf" | "docx" | "markdown" | "html" | "transcript" | "link";
  language: string;
  externalUrl: string;
  fileAssetId: number | null;
  chunkCount: number;
  isActive: boolean;
  indexedAt: string | null;
  metadataJson: Record<string, unknown>;
};

export type OnlineAdminKnowledgeDocumentListResponse = {
  results: OnlineAdminKnowledgeDocument[];
};

export type OnlineAdminKnowledgeDocumentWriteInput = {
  sourceId: number;
  title: string;
  description?: string;
  documentType: OnlineAdminKnowledgeDocument["documentType"];
  language?: string;
  externalUrl?: string;
  fileAssetId?: number | null;
  bodyMarkdown?: string;
  transcriptText?: string;
  isActive?: boolean;
  metadataJson?: Record<string, unknown>;
};
