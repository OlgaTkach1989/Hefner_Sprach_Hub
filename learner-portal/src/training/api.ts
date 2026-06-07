import axios, { AxiosHeaders, type AxiosError, type InternalAxiosRequestConfig } from "axios";

import { clearTokens, getCsrfToken } from "../api/authStorage";
import type {
  TrainingAiAskResult,
  TrainingAiConversationResponse,
  TrainingAiQuizAttempt,
  TrainingAssetClass,
  TrainingContentDetail,
  TrainingContentItem,
  TrainingContentReference,
  TrainingCourseSummary,
  TrainingGradebookEntry,
  TrainingLabSummary,
  TrainingLabSubmission,
  TrainingLaunchContract,
  TrainingNotebookHint,
  TrainingNotebookLabProfile,
  TrainingTopic,
} from "../types";

type ResultsResponse<T> = {
  results: T[];
};

type TrainingCourseSummaryDto = {
  id: number;
  slug: string;
  title_de: string;
  title_en: string;
};

type TrainingAssetClassDto = {
  id?: number;
  slug: string;
  name: string;
  description: string;
};

type TrainingTopicDto = {
  id?: number;
  slug: string;
  name: string;
  description: string;
  parent_slug?: string | null;
};

type TrainingNotebookLabProfileDto = {
  assignmentCode?: string;
  runtime_backend: string;
  grader_backend: string;
  runtime_image: string;
  notebook_path: string;
  launch_path: string;
  pass_threshold_percent?: number;
  max_attempts?: number;
  allow_gpu: boolean;
  allow_network: boolean;
  max_session_minutes: number | null;
  is_active: boolean;
};

type TrainingNotebookHintDto = {
  id: number;
  title: string;
  body_markdown: string;
  availabilityMode: "always" | "after_attempt" | "after_failure" | "after_score_below";
  minAttemptNumber: number;
  maxScorePercent: number;
  isRecommended: boolean;
};

type TrainingLabSummaryDto = {
  assignmentCode: string;
  passThresholdPercent: number;
  maxAttempts: number;
  attemptsRemaining: number | null;
  unlockedHintsCount: number;
  lockedHintsCount: number;
  hints: TrainingNotebookHintDto[];
  latestScorePercent: string | null;
  gradebook: {
    attemptsCount: number;
    latestScore: string | null;
    bestScore: string | null;
    maxScore: string | null;
    passed: boolean | null;
    completedAt: string | null;
  } | null;
};

type TrainingContentItemDto = {
  id: number;
  slug: string;
  name: string;
  description: string;
  content_kind: string;
  access_scope: string;
  difficulty: string;
  version_label: string;
  estimated_minutes: number | null;
  is_repeatable_on_demand: boolean;
  supports_inline_lab: boolean;
  source_url?: string | null;
  published_at?: string | null;
  course?: TrainingCourseSummaryDto | null;
  asset_classes: TrainingAssetClassDto[];
  topics: TrainingTopicDto[];
  lab: TrainingNotebookLabProfileDto | null;
};

type TrainingContentReferenceDto = {
  relation_type: string;
  slug: string;
  name: string;
  content_kind: string;
  note: string;
};

type TrainingContentDetailDto = TrainingContentItemDto & {
  body_markdown: string;
  cross_references: TrainingContentReferenceDto[];
  labSummary: TrainingLabSummaryDto | null;
};

type TrainingLabSubmissionDto = {
  public_id: string;
  attempt_number: number;
  status: string;
  submissionMode: string;
  grader_backend: string;
  graderStatus: string;
  notebook_path: string;
  hasNotebookArtifact: boolean;
  notebookArtifactFilename: string;
  hasResponseText: boolean;
  responseTextPreview: string;
  feedbackReportUrl: string | null;
  jsonReportUrl: string | null;
  feedback_markdown: string;
  feedback_payload: Record<string, unknown>;
  max_score: string | null;
  score: string | null;
  passed: boolean | null;
  submitted_at: string;
  graded_at: string | null;
  created_at: string;
  updated_at: string;
  content: TrainingCourseSummaryDto | null;
  contentSlug: string;
  contentName: string;
};

type TrainingGradebookEntryDto = {
  content: TrainingContentItemDto;
  attempts_count: number;
  latest_score: string | null;
  best_score: string | null;
  max_score: string | null;
  passed: boolean | null;
  completed_at: string | null;
  updated_at: string;
  latestSubmission: TrainingLabSubmissionDto | null;
  bestSubmissionId: string | null;
};

type TrainingAiCitationDto = {
  contentSlug: string;
  contentName: string;
  sectionTitle: string;
  citationLabel: string;
  quoteSnippet: string;
  sourceUrl?: string | null;
};

type TrainingAiResponsePayloadDto = {
  shortAnswer: string;
  detailedAnswer: string;
  citations: TrainingAiCitationDto[];
  followUpPrompts: string[];
  resolutionStatus: string;
  needsEscalation: boolean;
  escalation?: {
    targetRole: string;
    responseSlaHours: number;
    courseSlug?: string;
    message: string;
  } | null;
  provider: string;
  model: string;
};

type TrainingAiMessageDto = {
  id: number;
  role: "user" | "assistant" | "system";
  promptType: string;
  body: string;
  payload: TrainingAiResponsePayloadDto | null;
  citations: TrainingAiCitationDto[];
  resolutionStatus: string;
  createdAt: string;
};

type TrainingAiConversationDto = {
  publicId: string;
  title: string;
  status: string;
  contentSlug?: string | null;
  contentName?: string | null;
  lastActivityAt: string;
};

type TrainingAiConversationResponseDto = {
  conversation: TrainingAiConversationDto | null;
  messages: TrainingAiMessageDto[];
};

type TrainingAiAskRequest = {
  contentSlug: string;
  question: string;
  promptType?: string;
  conversationId?: string;
};

type TrainingAiQuizAttemptDto = {
  publicId: string;
  status: string;
  title: string;
  contentSlug: string;
  contentName: string;
  score: number | null;
  maxScore: number | null;
  correctAnswersCount: number;
  submittedAt: string | null;
  questions: Array<{
    questionId: string;
    prompt: string;
    options: Array<{ id: string; label: string }>;
    explanation: string;
    selectedOptionId?: string;
    correctOptionId?: string;
    isCorrect?: boolean;
  }>;
};

const resolveTrainingBaseUrl = () => {
  const configuredBaseUrl = import.meta.env.VITE_ONLINE_API_BASE_URL ?? "http://localhost:1212/api/online";
  const normalized = configuredBaseUrl.replace(/\/+$/, "");

  if (normalized.endsWith("/online")) {
    return `${normalized.slice(0, -"/online".length)}/training`;
  }

  return `${normalized}/training`;
};

const trainingApiClient = axios.create({
  baseURL: resolveTrainingBaseUrl(),
  timeout: 15000,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

const refreshClient = axios.create({
  baseURL: String(import.meta.env.VITE_ONLINE_API_BASE_URL ?? "http://localhost:1212/api/online").replace(/\/+$/, ""),
  timeout: 15000,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

type RetriableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
};

const applyCsrfHeader = (config: InternalAxiosRequestConfig) => {
  const headers = AxiosHeaders.from(config.headers ?? {});
  headers.set("X-Online-Auth-Scope", "student");
  const csrfToken = getCsrfToken();
  const method = String(config.method ?? "get").toUpperCase();
  if (csrfToken && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    headers.set("X-CSRFToken", csrfToken);
  }
  config.headers = headers;
  return config;
};

let refreshPromise: Promise<void> | null = null;

trainingApiClient.interceptors.request.use((config) => {
  config.withCredentials = true;
  return applyCsrfHeader(config);
});

refreshClient.interceptors.request.use((config) => {
  config.withCredentials = true;
  return applyCsrfHeader(config);
});

trainingApiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableRequestConfig | undefined;
    const requestUrl = String(config?.url ?? "");
    if (
      error.response?.status !== 401 ||
      !config ||
      config._retry ||
      requestUrl.includes("/public/auth/refresh/")
    ) {
      throw error;
    }

    config._retry = true;

    if (!refreshPromise) {
      refreshPromise = refreshClient
        .post("/public/auth/refresh/", {})
        .then(() => undefined)
        .catch((refreshError) => {
          clearTokens();
          throw refreshError;
        })
        .finally(() => {
          refreshPromise = null;
        });
    }

    await refreshPromise;
    config.withCredentials = true;
    applyCsrfHeader(config);
    return trainingApiClient(config);
  },
);

const mapCourseSummary = (item: TrainingCourseSummaryDto): TrainingCourseSummary => ({
  id: item.id,
  slug: item.slug,
  titleDe: item.title_de,
  titleEn: item.title_en,
});

const mapAssetClass = (item: TrainingAssetClassDto): TrainingAssetClass => ({
  slug: item.slug,
  name: item.name,
  description: item.description,
});

const mapTopic = (item: TrainingTopicDto): TrainingTopic => ({
  slug: item.slug,
  name: item.name,
  description: item.description,
  parentSlug: item.parent_slug ?? null,
});

const mapLabProfile = (item: TrainingNotebookLabProfileDto): TrainingNotebookLabProfile => ({
  assignmentCode: item.assignmentCode,
  runtimeBackend: item.runtime_backend,
  graderBackend: item.grader_backend,
  runtimeImage: item.runtime_image,
  notebookPath: item.notebook_path,
  launchPath: item.launch_path,
  passThresholdPercent: item.pass_threshold_percent,
  maxAttempts: item.max_attempts,
  allowGpu: item.allow_gpu,
  allowNetwork: item.allow_network,
  maxSessionMinutes: item.max_session_minutes,
  isActive: item.is_active,
});

const mapTrainingNotebookHint = (item: TrainingNotebookHintDto): TrainingNotebookHint => ({
  id: item.id,
  title: item.title,
  bodyMarkdown: item.body_markdown,
  availabilityMode: item.availabilityMode,
  minAttemptNumber: item.minAttemptNumber,
  maxScorePercent: item.maxScorePercent,
  isRecommended: item.isRecommended,
});

const mapTrainingLabSummary = (item: TrainingLabSummaryDto): TrainingLabSummary => ({
  assignmentCode: item.assignmentCode,
  passThresholdPercent: item.passThresholdPercent,
  maxAttempts: item.maxAttempts,
  attemptsRemaining: item.attemptsRemaining,
  unlockedHintsCount: item.unlockedHintsCount,
  lockedHintsCount: item.lockedHintsCount,
  hints: item.hints.map(mapTrainingNotebookHint),
  latestScorePercent: item.latestScorePercent,
  gradebook: item.gradebook,
});

const mapCrossReference = (item: TrainingContentReferenceDto): TrainingContentReference => ({
  relationType: item.relation_type,
  slug: item.slug,
  name: item.name,
  contentKind: item.content_kind,
  note: item.note,
});

const mapTrainingContentItem = (item: TrainingContentItemDto): TrainingContentItem => ({
  id: item.id,
  slug: item.slug,
  name: item.name,
  description: item.description,
  contentKind: item.content_kind,
  accessScope: item.access_scope,
  difficulty: item.difficulty,
  versionLabel: item.version_label,
  estimatedMinutes: item.estimated_minutes,
  isRepeatableOnDemand: item.is_repeatable_on_demand,
  supportsInlineLab: item.supports_inline_lab,
  sourceUrl: item.source_url ?? null,
  publishedAt: item.published_at ?? null,
  course: item.course ? mapCourseSummary(item.course) : null,
  assetClasses: item.asset_classes.map(mapAssetClass),
  topics: item.topics.map(mapTopic),
  lab: item.lab ? mapLabProfile(item.lab) : null,
});

const mapTrainingContentDetail = (item: TrainingContentDetailDto): TrainingContentDetail => ({
  ...mapTrainingContentItem(item),
  bodyMarkdown: item.body_markdown,
  crossReferences: item.cross_references.map(mapCrossReference),
  labSummary: item.labSummary ? mapTrainingLabSummary(item.labSummary) : null,
});

const mapTrainingLabSubmission = (item: TrainingLabSubmissionDto): TrainingLabSubmission => ({
  publicId: item.public_id,
  attemptNumber: item.attempt_number,
  status: item.status,
  submissionMode: item.submissionMode,
  graderBackend: item.grader_backend,
  graderStatus: item.graderStatus,
  notebookPath: item.notebook_path,
  hasNotebookArtifact: item.hasNotebookArtifact,
  notebookArtifactFilename: item.notebookArtifactFilename,
  hasResponseText: item.hasResponseText,
  responseTextPreview: item.responseTextPreview,
  feedbackReportUrl: item.feedbackReportUrl ?? null,
  jsonReportUrl: item.jsonReportUrl ?? null,
  feedbackMarkdown: item.feedback_markdown,
  feedbackPayload: item.feedback_payload,
  maxScore: item.max_score,
  score: item.score,
  passed: item.passed,
  submittedAt: item.submitted_at,
  gradedAt: item.graded_at,
  createdAt: item.created_at,
  updatedAt: item.updated_at,
  content: item.content ? mapCourseSummary(item.content) : null,
  contentSlug: item.contentSlug,
  contentName: item.contentName,
});

const mapTrainingGradebookEntry = (item: TrainingGradebookEntryDto): TrainingGradebookEntry => ({
  content: mapTrainingContentItem(item.content),
  attemptsCount: item.attempts_count,
  latestScore: item.latest_score,
  bestScore: item.best_score,
  maxScore: item.max_score,
  passed: item.passed,
  completedAt: item.completed_at,
  updatedAt: item.updated_at,
  latestSubmission: item.latestSubmission ? mapTrainingLabSubmission(item.latestSubmission) : null,
  bestSubmissionId: item.bestSubmissionId,
});

const mapTrainingAiQuizAttempt = (item: TrainingAiQuizAttemptDto): TrainingAiQuizAttempt => ({
  publicId: item.publicId,
  status: item.status,
  title: item.title,
  contentSlug: item.contentSlug,
  contentName: item.contentName,
  score: item.score,
  maxScore: item.maxScore,
  correctAnswersCount: item.correctAnswersCount,
  submittedAt: item.submittedAt,
  questions: item.questions,
});

export const fetchTrainingContent = async (): Promise<TrainingContentItem[]> => {
  const response = await trainingApiClient.get<ResultsResponse<TrainingContentItemDto>>("/content/");
  return response.data.results.map(mapTrainingContentItem);
};

export const fetchTrainingContentDetail = async (contentSlug: string): Promise<TrainingContentDetail> => {
  const response = await trainingApiClient.get<TrainingContentDetailDto>(`/content/${contentSlug}/`);
  return mapTrainingContentDetail(response.data);
};

export const fetchTrainingGradebook = async (): Promise<TrainingGradebookEntry[]> => {
  const response = await trainingApiClient.get<ResultsResponse<TrainingGradebookEntryDto>>("/gradebook/");
  return response.data.results.map(mapTrainingGradebookEntry);
};

export const fetchTrainingSubmissions = async (contentSlug: string): Promise<TrainingLabSubmission[]> => {
  const response = await trainingApiClient.get<ResultsResponse<TrainingLabSubmissionDto>>(
    `/labs/${contentSlug}/submissions/`,
  );
  return response.data.results.map(mapTrainingLabSubmission);
};

export const launchTrainingLab = async (contentSlug: string): Promise<TrainingLaunchContract> => {
  const response = await trainingApiClient.post<TrainingLaunchContract>("/labs/" + contentSlug + "/launch/", {});
  return response.data;
};

export const submitTrainingLab = async (
  contentSlug: string,
  notebookFile: File,
): Promise<TrainingLabSubmission> => {
  const formData = new FormData();
  formData.append("notebook", notebookFile);
  const response = await trainingApiClient.post<TrainingLabSubmissionDto>(
    `/labs/${contentSlug}/submissions/`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );
  return mapTrainingLabSubmission(response.data);
};

export const submitTrainingLabAnswer = async (
  contentSlug: string,
  answerText: string,
): Promise<TrainingLabSubmission> => {
  const response = await trainingApiClient.post<TrainingLabSubmissionDto>(
    `/labs/${contentSlug}/submissions/`,
    {
      answerText,
    },
  );
  return mapTrainingLabSubmission(response.data);
};

export const markTrainingHintViewed = async (contentSlug: string, hintId: number): Promise<void> => {
  await trainingApiClient.post(`/labs/${contentSlug}/hints/${hintId}/view/`, {});
};

export const fetchTrainingAiConversation = async (contentSlug: string): Promise<TrainingAiConversationResponse> => {
  const response = await trainingApiClient.get<TrainingAiConversationResponseDto>("/ai/conversation/", {
    params: {
      content: contentSlug,
    },
  });
  return {
    conversation: response.data.conversation
      ? {
          ...response.data.conversation,
          contentSlug: response.data.conversation.contentSlug ?? null,
          contentName: response.data.conversation.contentName ?? null,
        }
      : null,
    messages: response.data.messages.map((message) => ({
      ...message,
      payload: message.payload
        ? {
            ...message.payload,
            escalation: message.payload.escalation ?? null,
            citations: message.payload.citations.map((citation) => ({
              ...citation,
              sourceUrl: citation.sourceUrl ?? null,
            })),
          }
        : null,
      citations: message.citations.map((citation) => ({
        ...citation,
        sourceUrl: citation.sourceUrl ?? null,
      })),
    })),
  };
};

export const askTrainingAi = async (payload: TrainingAiAskRequest): Promise<TrainingAiAskResult> => {
  const response = await trainingApiClient.post<TrainingAiAskResult>("/ai/ask/", payload);
  return response.data;
};

export const generateTrainingAiQuiz = async (
  contentSlug: string,
  conversationId?: string,
  questionCount = 4,
): Promise<TrainingAiQuizAttempt> => {
  const response = await trainingApiClient.post<TrainingAiQuizAttemptDto>("/ai/quizzes/generate/", {
    contentSlug,
    conversationId,
    questionCount,
  });
  return mapTrainingAiQuizAttempt(response.data);
};

export const submitTrainingAiQuiz = async (
  quizPublicId: string,
  answers: Array<{ questionId: string; selectedOptionId: string }>,
): Promise<TrainingAiQuizAttempt> => {
  const response = await trainingApiClient.post<TrainingAiQuizAttemptDto>(
    `/ai/quizzes/${quizPublicId}/submit/`,
    {
      answers,
    },
  );
  return mapTrainingAiQuizAttempt(response.data);
};
