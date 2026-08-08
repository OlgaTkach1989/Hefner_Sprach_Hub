export type Locale = "de" | "en";
export type ThemeMode = "light" | "dark";
export type Gender = "unspecified" | "female" | "male" | "diverse";

export interface LoginResponse {
  profile: StudentProfile;
}

export interface StudentProfile {
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  gender: Gender;
  avatar_url: string;
  preferred_language: Locale;
  is_trial_user: boolean;
}

export interface SessionItem {
  id: number;
  title: string;
  description: string;
  starts_at: string;
  ends_at: string;
  join_url?: string | null;
  recording_url?: string | null;
  is_completed: boolean;
  attendance_status: string;
  attended_seconds: number;
  booking_status?: "booked" | "canceled" | null;
  booked_at?: string | null;
}

export interface CourseMaterialItem {
  id: number | string;
  title: string;
  description: string;
  material_type: string;
  language: Locale;
  link_url?: string | null;
}

export interface CourseLessonSectionItem {
  id: number;
  title: string;
  description: string;
  assetType: "text" | "document" | "link" | "notebook";
  activityType: "video" | "text" | "quiz" | "assignment";
  language: Locale;
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
}

export interface CourseLessonSection {
  id: number;
  sectionType: "introduction" | "main" | "conclusion";
  title: string;
  description: string;
  sortOrder: number;
  items: CourseLessonSectionItem[];
}

export type InteractiveLessonStepKind = "theory" | "video" | "quiz" | "practice" | "summary";

export interface InteractiveLessonResourceLink {
  id: string;
  label: string;
  url: string;
  kind: "document" | "video" | "notebook" | "external";
}

export interface InteractiveLessonQuizOption {
  id: string;
  label: string;
  isCorrect: boolean;
}

export interface InteractiveLessonQuizQuestion {
  id: string;
  prompt: string;
  options: InteractiveLessonQuizOption[];
  successMessage: string;
  errorMessage: string;
  explanationMarkdown: string;
}

export interface InteractiveLessonQuizPayload {
  prompt: string;
  options: InteractiveLessonQuizOption[];
  questions?: InteractiveLessonQuizQuestion[];
  successMessage: string;
  errorMessage: string;
  explanationMarkdown: string;
}

export interface InteractiveLessonCodeGraderConfig {
  type: "python_variable_check";
  expected_variables?: Record<string, string | number | boolean>;
  required_functions?: string[];
  expected_stdout?: string;
}

export interface InteractiveLessonStep {
  id: string;
  kind: InteractiveLessonStepKind;
  title: string;
  eyebrow: string;
  description: string;
  contentMarkdown: string;
  sourceItemId?: number | null;
  videoUrl?: string;
  resourceLinks: InteractiveLessonResourceLink[];
  quiz?: InteractiveLessonQuizPayload | null;
  practiceMode?: "notebook" | "code_editor";
  starterCode?: string;
  hint?: string;
  solution?: string;
  grader?: InteractiveLessonCodeGraderConfig | null;
}

export interface InteractiveLessonPayload {
  courseTitle: string;
  moduleTitle: string;
  lessonTitle: string;
  estimatedMinutes: number;
  demoVariantKey: string;
  outcomes: string[];
  resources: InteractiveLessonResourceLink[];
  steps: InteractiveLessonStep[];
}

export interface CourseLessonPlanItem {
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
  sections: CourseLessonSection[];
  interactiveLesson?: InteractiveLessonPayload | null;
  progress?: {
    activeStepId: string;
    completedStepIds: string[];
    progressPercent: number;
    startedAt?: string | null;
    completedAt?: string | null;
    totalSteps: number;
  };
}

export interface CourseModulePlanItem {
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
  lessons: CourseLessonPlanItem[];
}

export interface CourseAudienceLabel {
  id: number;
  slug: string;
  name: string;
  shortLabel: string;
}

export interface EnrollmentItem {
  enrollmentId: number;
  status: string;
  course: {
    slug: string;
    titleDe: string;
    titleEn: string;
    audienceIds: number[];
    audiences: CourseAudienceLabel[];
    lessonsCount: number;
  };
  cohort: {
    id: number;
    groupCode: string;
    groupName: string;
  };
  attendancePercent: number;
  nextSessionAt?: string | null;
  sessions: SessionItem[];
  materials: CourseMaterialItem[];
  lessonPlan: CourseLessonPlanItem[];
  completion: {
    status: "in_progress" | "ready_for_attestation" | "eligible" | "completed";
    statusLabel: string;
    progressPercent: number;
    completedLessons: number;
    startedLessons: number;
    totalLessons: number;
    attendancePercent: number;
    ruleReady: boolean;
    rule: {
      requiredCompletionPercent: number;
      requiredAttendancePercent: number;
      requiresAttestation: boolean;
    };
    attestation: {
      id: number;
      fullName: string;
      attestationText: string;
      confirmedAt: string;
    } | null;
    evidence: {
      id: number;
      status: string;
      evidenceCode: string;
      completionPercent: number;
      attendancePercent: number;
      issuedAt: string;
    } | null;
    requirements: {
      completionMet: boolean;
      attendanceMet: boolean;
      attestationMet: boolean;
    };
  };
  courseStructure?: {
    modules: CourseModulePlanItem[];
    finalAssessment?: CourseModulePlanItem | null;
  };
}

export interface DashboardResponse {
  profile: StudentProfile;
  nextSessionAt?: string | null;
  unreadSupportMessages: number;
  enrollments: EnrollmentItem[];
  learningContent?: TrainingContentItem[];
}

export interface StudentLessonDetailResponse {
  enrollmentId: number;
  course: {
    slug: string;
    titleDe: string;
    titleEn: string;
    audienceIds?: number[];
    audiences?: CourseAudienceLabel[];
  };
  cohort: {
    id: number;
    groupCode: string;
    groupName: string;
  };
  module: {
    id?: number | null;
    title: string;
    moduleType: "module" | "final_assessment" | string;
    weekNumber?: number | null;
  };
  lesson: CourseLessonPlanItem;
  completion: EnrollmentItem["completion"];
}

export interface StudentLessonAiAskResponse {
  answer: string;
  followUpPrompts: string[];
  provider: string;
  model: string;
  resolutionStatus: string;
}

export interface StudentLessonGraderCheck {
  name: string;
  passed: boolean;
  expected?: string;
  actual?: string;
}

export interface StudentLessonGraderResponse {
  status: "success" | "fail" | "error";
  message: string;
  checks: StudentLessonGraderCheck[];
}

export type LearningWorkspaceStepKind = "video" | "formula" | "scenario" | "notebook" | "ai_quiz";
export type LearningWorkspaceStepStatus = "locked" | "available" | "in_progress" | "completed";
export type LearningWorkspaceSource = "backend" | "fallback";
export type LearningWorkspaceOwnerRole = "course_owner" | "knowledge_owner" | "lab_owner" | "instructor";

export interface LearningWorkspaceResourceLink {
  label: string;
  url: string;
  kind?: "document" | "video" | "notebook" | "external";
  description?: string | null;
}

export interface LearningWorkspaceOwner {
  role: LearningWorkspaceOwnerRole;
  name: string;
  email?: string | null;
  responseSlaHours?: number | null;
}

export interface LearningWorkspaceRuntimePreset {
  id: string;
  name: string;
  description: string;
  runtimeImage: string;
  launchPath: string;
  packageSummary: string[];
  internalPackages: string[];
  allowNetwork: boolean;
  allowGpu: boolean;
}

export interface LearningWorkspaceCertificateRule {
  title: string;
  description: string;
  requiredCompletionPercent: number;
  requiredNotebookPassPercent: number;
  requiredAiQuizPassPercent: number;
  requiresAttendance: boolean;
}

export interface LearningWorkspaceStepBase {
  id: string;
  slug: string;
  kind: LearningWorkspaceStepKind;
  title: string;
  description: string;
  sortOrder: number;
  status: LearningWorkspaceStepStatus;
  estimatedMinutes?: number | null;
  contentSlug?: string | null;
  resources: LearningWorkspaceResourceLink[];
}

export interface LearningWorkspaceVideoStep extends LearningWorkspaceStepBase {
  kind: "video";
  videoUrl: string;
  posterUrl?: string | null;
  transcriptMarkdown?: string | null;
}

export interface LearningWorkspaceFormulaStep extends LearningWorkspaceStepBase {
  kind: "formula";
  formula: string;
  explanationMarkdown: string;
  referenceMarkdown?: string | null;
}

export interface LearningWorkspaceScenarioStep extends LearningWorkspaceStepBase {
  kind: "scenario";
  contextMarkdown: string;
  promptMarkdown: string;
  expectedOutcomeMarkdown: string;
  checklist: string[];
}

export interface LearningWorkspaceNotebookStep extends LearningWorkspaceStepBase {
  kind: "notebook";
  notebookPath: string;
  launchPath: string;
  passThresholdPercent: number;
  maxAttempts: number | null;
  launchLabel: string;
  guidanceMarkdown?: string | null;
}

export interface LearningWorkspaceAiQuizStep extends LearningWorkspaceStepBase {
  kind: "ai_quiz";
  contentSlug: string;
  questionCount: number;
  promptType: string;
  guidanceMarkdown: string;
}

export type LearningWorkspaceStep =
  | LearningWorkspaceVideoStep
  | LearningWorkspaceFormulaStep
  | LearningWorkspaceScenarioStep
  | LearningWorkspaceNotebookStep
  | LearningWorkspaceAiQuizStep;

export interface LearningWorkspaceModule {
  id: string;
  slug: string;
  title: string;
  description: string;
  sortOrder: number;
  progressPercent: number;
  stepCount: number;
  steps: LearningWorkspaceStep[];
}

export interface LearningWorkspaceProgram {
  id: string;
  slug: string;
  title: string;
  subtitle: string;
  description: string;
  status: "draft" | "active" | "completed";
  progressPercent: number;
  nextSessionAt?: string | null;
  audience: string[];
  tags: string[];
  owners: LearningWorkspaceOwner[];
  runtimePreset: LearningWorkspaceRuntimePreset;
  certificateRule: LearningWorkspaceCertificateRule;
  modules: LearningWorkspaceModule[];
}

export interface LearningWorkspacePayload {
  source: LearningWorkspaceSource;
  fetchedAt: string;
  preferredLanguage: Locale;
  activeProgramSlug: string;
  supportUrl?: string | null;
  programs: LearningWorkspaceProgram[];
}

export interface SupportMessage {
  id: number;
  sender_type: "student" | "support";
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface TrainingCourseSummary {
  id: number;
  slug: string;
  titleDe: string;
  titleEn: string;
}

export interface TrainingAssetClass {
  id?: number;
  slug: string;
  name: string;
  description: string;
}

export interface TrainingTopic {
  id?: number;
  slug: string;
  name: string;
  description: string;
  parentSlug?: string | null;
}

export interface TrainingNotebookLabProfile {
  assignmentCode?: string;
  runtimeBackend: string;
  graderBackend: string;
  runtimeImage: string;
  notebookPath: string;
  launchPath: string;
  passThresholdPercent?: number;
  maxAttempts?: number;
  allowGpu: boolean;
  allowNetwork: boolean;
  maxSessionMinutes: number | null;
  isActive: boolean;
}

export interface TrainingNotebookHint {
  id: number;
  title: string;
  bodyMarkdown: string;
  availabilityMode: "always" | "after_attempt" | "after_failure" | "after_score_below";
  minAttemptNumber: number;
  maxScorePercent: number;
  isRecommended: boolean;
}

export interface TrainingLabSummary {
  assignmentCode: string;
  passThresholdPercent: number;
  maxAttempts: number;
  attemptsRemaining: number | null;
  unlockedHintsCount: number;
  lockedHintsCount: number;
  hints: TrainingNotebookHint[];
  latestScorePercent: string | null;
  gradebook: {
    attemptsCount: number;
    latestScore: string | null;
    bestScore: string | null;
    maxScore: string | null;
    passed: boolean | null;
    completedAt: string | null;
  } | null;
}

export interface TrainingContentItem {
  id: number;
  slug: string;
  name: string;
  description: string;
  contentKind: string;
  accessScope: string;
  difficulty: string;
  versionLabel: string;
  estimatedMinutes: number | null;
  isRepeatableOnDemand: boolean;
  supportsInlineLab: boolean;
  sourceUrl: string | null;
  publishedAt: string | null;
  course: TrainingCourseSummary | null;
  assetClasses: TrainingAssetClass[];
  topics: TrainingTopic[];
  lab: TrainingNotebookLabProfile | null;
}

export interface TrainingContentReference {
  relationType: string;
  slug: string;
  name: string;
  contentKind: string;
  note: string;
}

export interface TrainingContentDetail extends TrainingContentItem {
  bodyMarkdown: string;
  crossReferences: TrainingContentReference[];
  labSummary: TrainingLabSummary | null;
}

export interface TrainingLaunchContract {
  tokenId: string;
  launchToken: string;
  launchUrl: string | null;
  expiresAt: string;
  runtime: {
    baseUrl: string;
    backend: string;
    graderBackend: string;
    launchPath: string;
    maxSessionMinutes: number | null;
  };
  content: {
    id: number;
    slug: string;
    name: string;
    courseId: number | null;
  };
}

export interface TrainingLabSubmission {
  publicId: string;
  attemptNumber: number;
  status: string;
  submissionMode: string;
  graderBackend: string;
  graderStatus: string;
  notebookPath: string;
  hasNotebookArtifact: boolean;
  notebookArtifactFilename: string;
  hasResponseText: boolean;
  responseTextPreview: string;
  feedbackReportUrl: string | null;
  jsonReportUrl: string | null;
  feedbackMarkdown: string;
  feedbackPayload: Record<string, unknown>;
  maxScore: string | null;
  score: string | null;
  passed: boolean | null;
  submittedAt: string;
  gradedAt: string | null;
  createdAt: string;
  updatedAt: string;
  content: TrainingCourseSummary | null;
  contentSlug: string;
  contentName: string;
}

export interface TrainingGradebookEntry {
  content: TrainingContentItem;
  attemptsCount: number;
  latestScore: string | null;
  bestScore: string | null;
  maxScore: string | null;
  passed: boolean | null;
  completedAt: string | null;
  updatedAt: string;
  latestSubmission: TrainingLabSubmission | null;
  bestSubmissionId: string | null;
}

export interface TrainingAiCitation {
  contentSlug: string;
  contentName: string;
  sectionTitle: string;
  citationLabel: string;
  quoteSnippet: string;
  sourceUrl: string | null;
}

export interface TrainingAiEscalation {
  targetRole: string;
  responseSlaHours: number;
  courseSlug?: string;
  message: string;
}

export interface TrainingAiResponsePayload {
  shortAnswer: string;
  detailedAnswer: string;
  citations: TrainingAiCitation[];
  followUpPrompts: string[];
  resolutionStatus: string;
  needsEscalation: boolean;
  escalation: TrainingAiEscalation | null;
  provider: string;
  model: string;
}

export interface TrainingAiConversationMeta {
  publicId: string;
  title: string;
  status: string;
  contentSlug: string | null;
  contentName: string | null;
  lastActivityAt: string;
}

export interface TrainingAiMessage {
  id: number;
  role: "user" | "assistant" | "system";
  promptType: string;
  body: string;
  payload: TrainingAiResponsePayload | null;
  citations: TrainingAiCitation[];
  resolutionStatus: string;
  createdAt: string;
}

export interface TrainingAiConversationResponse {
  conversation: TrainingAiConversationMeta | null;
  messages: TrainingAiMessage[];
}

export interface TrainingAiAskResult {
  conversationId: string;
  assistantMessageId: number;
  response: TrainingAiResponsePayload;
}

export interface TrainingAiQuizQuestion {
  questionId: string;
  prompt: string;
  options: Array<{
    id: string;
    label: string;
  }>;
  explanation: string;
  selectedOptionId?: string;
  correctOptionId?: string;
  isCorrect?: boolean;
}

export interface TrainingAiQuizAttempt {
  publicId: string;
  status: string;
  title: string;
  contentSlug: string;
  contentName: string;
  score: number | null;
  maxScore: number | null;
  correctAnswersCount: number;
  submittedAt: string | null;
  questions: TrainingAiQuizQuestion[];
}
