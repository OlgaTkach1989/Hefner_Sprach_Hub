export type TrainingCourseSummary = {
  id: number;
  slug: string;
  title_de: string;
  title_en: string;
};

export type TrainingAdminOverview = {
  courseId: number | null;
  coursesWithoutOwner: number;
  ownerAssignments: number;
  reviewerAssignments: number;
  instructorAssignments: number;
  contentItems: number;
  notebookItems: number;
  contentWithoutAssetClass: number;
  contentWithoutTopic: number;
  contentWithoutOwner: number;
  internalContentWithoutAudiencePolicy: number;
  notebookContentWithoutLabProfile: number;
};

export type TrainingAdminReportsOverview = {
  courseId: number | null;
  failedAuditEvents: number;
  deniedAuditEvents: number;
  failedSyncEvents: number;
  failedGraderJobs: number;
  unresolvedAiConversations: number;
  latestAuditFailureAt: string | null;
  latestSyncFailureAt: string | null;
  latestGraderFailureAt: string | null;
};

export type TrainingAdminAudience = {
  id: number;
  slug: string;
  name: string;
  short_label: string;
  description: string;
  audience_type: "general" | "demo_role";
  privilege_rank: number;
  is_internal: boolean;
  is_active: boolean;
  grantsCount: number;
  contentPoliciesCount: number;
};

export type TrainingAdminAssetClass = {
  id: number;
  slug: string;
  name: string;
  description: string;
};

export type TrainingAdminTopic = {
  id: number;
  slug: string;
  name: string;
  description: string;
  parent_slug?: string | null;
};

export type TrainingAdminAudienceWriteInput = {
  slug: string;
  name: string;
  short_label: string;
  description: string;
  audience_type: "general" | "demo_role";
  privilege_rank: number;
  is_internal: boolean;
  is_active: boolean;
};

export type TrainingAdminAudiencePatchInput = Partial<TrainingAdminAudienceWriteInput>;

export type TrainingAdminUserSummary = {
  id: number;
  email: string;
  username: string | null;
  fullName: string;
  isAdmin: boolean;
  isActive?: boolean;
};

export type TrainingAdminAuditEvent = {
  eventId: string;
  category: "content" | "entitlement" | "lab" | "grading" | "admin" | "ai";
  event_type: string;
  outcome: "succeeded" | "denied" | "failed";
  actorEmail: string;
  targetUserEmail: string;
  course: TrainingCourseSummary | null;
  contentSlug: string;
  submissionPublicId: string;
  request_method: string;
  request_path: string;
  metadata: Record<string, unknown>;
  createdAt: string;
};

export type TrainingAdminContentSyncEvent = {
  id: number;
  source: "directus" | "admin" | "command";
  eventType: "upsert" | "unpublish" | "reindex";
  status: "succeeded" | "failed";
  course: TrainingCourseSummary | null;
  contentSlug: string;
  externalSourceId: string;
  detail: string;
  payloadSummary: Record<string, unknown>;
  createdAt: string;
};

export type TrainingAdminGraderJob = {
  id: number;
  status: "queued" | "running" | "succeeded" | "failed";
  backend: "none" | "nbgrader" | "otter" | "custom";
  priority: number;
  attemptsCount: number;
  course: TrainingCourseSummary | null;
  contentSlug: string;
  contentName: string;
  studentEmail: string;
  submissionPublicId: string;
  availableAt: string;
  lockedAt: string | null;
  finishedAt: string | null;
  workerName: string;
  errorMessage: string;
};

export type TrainingCourseRole = "owner" | "reviewer" | "instructor";

export type TrainingAdminCourseRoleAssignment = {
  id: number;
  course: TrainingCourseSummary;
  user: TrainingAdminUserSummary;
  role: TrainingCourseRole;
  is_primary: boolean;
  response_sla_hours: number;
  created_at: string;
};

export type TrainingAdminCourseRoleAssignmentWriteInput = {
  user_id: number;
  course_id: number;
  role: TrainingCourseRole;
  is_primary: boolean;
  response_sla_hours: number;
};

export type TrainingAdminCourseRoleAssignmentPatchInput = {
  role?: TrainingCourseRole;
  is_primary?: boolean;
  response_sla_hours?: number;
};

export type TrainingGovernanceFlag =
  | "missing_asset_class"
  | "missing_topic"
  | "missing_owner"
  | "missing_audience_policy"
  | "missing_lab_profile"
  | "lab_profile_incomplete";

export type TrainingContentKind =
  | "article"
  | "video"
  | "notebook"
  | "faq"
  | "recording"
  | "exercise"
  | "dataset"
  | "link";

export type TrainingContentStatus = "draft" | "review" | "published" | "retired";

export type TrainingAccessScope = "public" | "authenticated" | "entitled";

export type TrainingContentGovernanceItem = {
  id: number;
  slug: string;
  name: string;
  content_kind: TrainingContentKind;
  status: TrainingContentStatus;
  access_scope: TrainingAccessScope;
  difficulty: string;
  course: TrainingCourseSummary | null;
  owner: TrainingAdminUserSummary | null;
  is_repeatable_on_demand: boolean;
  supports_inline_lab: boolean;
  assetClassCount: number;
  topicCount: number;
  audiencePolicyCount: number;
  hasLab: boolean;
  labReady: boolean;
  governanceFlags: TrainingGovernanceFlag[];
  updated_at: string;
};

export type TrainingAdminUserAudienceGrant = {
  id: number;
  user: TrainingAdminUserSummary;
  audience: TrainingAdminAudience;
  note: string;
  expires_at: string | null;
  isActive: boolean;
  created_at: string;
};

export type TrainingAdminUserAudienceGrantWriteInput = {
  user_id: number;
  audience_id: number;
  note: string;
  expires_at: string | null;
};

export type TrainingAdminUserAudienceGrantPatchInput = {
  note?: string;
  expires_at?: string | null;
};

export type TrainingAdminListResponse<TItem> = {
  results: TItem[];
};

export type TrainingNotebookCheckKind =
  | "code_contains"
  | "markdown_contains"
  | "forbidden_text"
  | "required_function"
  | "numeric_assignment";

export type TrainingAdminNotebookAssignmentHint = {
  id: number;
  title: string;
  body_markdown: string;
  availability_mode: "always" | "after_attempt" | "after_failure" | "after_score_below";
  min_attempt_number: number;
  max_score_percent: number;
  sort_order: number;
  is_active: boolean;
};

export type TrainingAdminNotebookAssignmentCheck = {
  id: string;
  label: string;
  kind: TrainingNotebookCheckKind;
  points: string;
  variable?: string;
  expected?: string;
  tolerance?: string;
  needle?: string;
  functionName?: string;
  successMessage?: string;
  failureMessage?: string;
  hintIds?: number[];
};

export type TrainingAdminNotebookAssignmentAnalytics = {
  learnersAttempted: number;
  totalSubmissions: number;
  passRatePercent: number;
  averageScorePercent: number | null;
  latestSubmissionAt: string | null;
  pendingJobs: number;
  failedJobs: number;
  averageAttemptsPerLearner: number;
  bestScorePercent: number | null;
  hintViews: number;
  gradeDistribution: {
    below50: number;
    from50to69: number;
    from70to84: number;
    from85to100: number;
  };
};

export type TrainingAdminNotebookAssignment = {
  id: number;
  slug: string;
  name: string;
  description: string;
  body_markdown: string;
  status: TrainingContentStatus;
  access_scope: TrainingAccessScope;
  difficulty: string;
  estimated_minutes: number;
  is_repeatable_on_demand: boolean;
  supports_inline_lab: boolean;
  course: TrainingCourseSummary | null;
  owner: TrainingAdminUserSummary | null;
  assetClassIds: number[];
  topicIds: number[];
  audienceIds: number[];
  labProfile: {
    assignmentCode: string;
    runtimeBackend: string;
    graderBackend: string;
    runtimeImage: string;
    notebookPath: string;
    launchPath: string;
    passThresholdPercent: number;
    maxAttempts: number;
    allowGpu: boolean;
    allowNetwork: boolean;
    maxSessionMinutes: number;
    isActive: boolean;
    graderConfig: {
      mode?: string;
      maxScore?: string;
      checks?: TrainingAdminNotebookAssignmentCheck[];
      [key: string]: unknown;
    };
  } | null;
  hints: TrainingAdminNotebookAssignmentHint[];
  analytics: TrainingAdminNotebookAssignmentAnalytics;
  builderLibraryItemId: number | null;
};

export type TrainingAdminNotebookAssignmentWriteInput = {
  slug: string;
  name: string;
  description: string;
  body_markdown: string;
  status: TrainingContentStatus;
  access_scope: TrainingAccessScope;
  difficulty: string;
  course_id: number | null;
  owner_id: number | null;
  estimated_minutes: number;
  is_repeatable_on_demand: boolean;
  supports_inline_lab: boolean;
  asset_class_ids: number[];
  topic_ids: number[];
  audience_ids: number[];
  lab: {
    runtimeBackend: string;
    graderBackend: string;
    runtimeImage: string;
    notebookPath: string;
    launchPath: string;
    assignmentCode: string;
    passThresholdPercent: number;
    maxAttempts: number;
    allowGpu: boolean;
    allowNetwork: boolean;
    maxSessionMinutes: number;
    isActive: boolean;
    graderConfig: {
      mode?: string;
      maxScore?: string;
      checks?: TrainingAdminNotebookAssignmentCheck[];
      [key: string]: unknown;
    };
  };
  hints: Array<{
    title: string;
    body_markdown: string;
    availability_mode: "always" | "after_attempt" | "after_failure" | "after_score_below";
    min_attempt_number: number;
    max_score_percent: number;
    sort_order: number;
    is_active: boolean;
  }>;
};

export type TrainingAdminNotebookUploadResponse = {
  contentSlug: string;
  notebookPath: string;
  storagePath: string;
  checksum: string;
  sizeBytes: number;
};

export type TrainingAiGovernanceStatus = "open" | "in_review" | "resolved" | "archived";

export type TrainingAiConversationStatus = "active" | "archived";

export type TrainingAiResolutionStatus = "resolved" | "partial" | "escalate";

export type TrainingAdminAiOverview = {
  courseId: number | null;
  aiConversations: number;
  distinctLearners: number;
  aiQuestions: number;
  resolvedResponses: number;
  partialResponses: number;
  escalatedResponses: number;
  unresolvedQueueCount: number;
  assignedQueueCount: number;
  resolvedConversations: number;
  archivedConversations: number;
  faqItems: number;
  contentItemsCoveredByFaq: number;
  faqCoveragePercent: number;
  indexedContentItems: number;
  indexedChunks: number;
  generatedQuizzes: number;
  completedQuizzes: number;
};

export type TrainingAdminAiAnalyticsTopContent = {
  contentId: number;
  slug: string;
  name: string;
  aiQuestions: number;
  unresolvedConversations: number;
  accessDeniedCount: number;
  latestQuestionAt: string | null;
};

export type TrainingAdminAiAnalytics = {
  courseId: number | null;
  aiQuestionsLast7Days: number;
  aiFailuresLast7Days: number;
  quizFailuresLast7Days: number;
  escalationsLast7Days: number;
  avgResolutionHours: number | null;
  publishedContentItems: number;
  directusManagedContentItems: number;
  directusItemsWithoutOwner: number;
  unindexedPublishedItems: number;
  staleIndexedPublishedItems: number;
  directusSyncFailuresLast7Days: number;
  lastDirectusSyncAt: string | null;
  lastKnowledgeRefreshAt: string | null;
  windowDays: number;
  providerMode: string;
  externalProviderConfigured: boolean;
  pgvectorEnabled: boolean;
  aiQuestionsWindow: number;
  aiResponseFailuresWindow: number;
  aiEscalationsWindow: number;
  quizSubmitFailuresWindow: number;
  contentAccessDeniedWindow: number;
  directusSyncAppliedWindow: number;
  directusSyncFailedWindow: number;
  unresolvedQueueCount: number;
  staleIndexedContentCount: number;
  latestIndexRebuildAt: string | null;
  latestIndexRebuildOutcome: string;
  latestDirectusSyncAt: string | null;
  latestDirectusSyncOutcome: string;
  topContentItems: TrainingAdminAiAnalyticsTopContent[];
};

export type TrainingAdminAiConversation = {
  publicId: string;
  title: string;
  governanceStatus: TrainingAiGovernanceStatus;
  conversationStatus: TrainingAiConversationStatus;
  lastActivityAt: string;
  createdAt: string;
  resolvedAt: string | null;
  resolutionNote: string;
  latestUserPrompt: string;
  latestResolutionStatus: TrainingAiResolutionStatus | null;
  latestAssistantBody: string;
  latestAssistantCreatedAt: string | null;
  recommendedOwnerId: number | null;
  recommendedOwnerSlaHours: number | null;
  userMessageCount: number;
  assistantMessageCount: number;
  learner: TrainingAdminUserSummary;
  assignedTo: TrainingAdminUserSummary | null;
  resolvedBy: TrainingAdminUserSummary | null;
  content: {
    id: number;
    slug: string;
    name: string;
    contentKind: TrainingContentKind;
    course: TrainingCourseSummary | null;
  } | null;
};

export type TrainingAdminAiConversationPatchInput = {
  governance_status?: TrainingAiGovernanceStatus;
  assigned_to_id?: number | null;
  resolution_note?: string;
};

export type TrainingAdminAiRebuildIndexInput = {
  course_id?: number | null;
  content_slug?: string;
};

export type TrainingAdminAiRebuildIndexResult = {
  rebuiltContentItems: number;
  rebuiltChunks: number;
  filters: {
    courseId?: number;
    contentSlug?: string;
  };
};
