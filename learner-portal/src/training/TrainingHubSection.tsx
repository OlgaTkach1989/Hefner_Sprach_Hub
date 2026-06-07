import { useEffect, useMemo, useRef, useState } from "react";
import { isAxiosError } from "axios";
import { useTranslation } from "react-i18next";

import {
  askTrainingAi,
  fetchTrainingAiConversation,
  fetchTrainingContent,
  fetchTrainingContentDetail,
  fetchTrainingGradebook,
  fetchTrainingSubmissions,
  generateTrainingAiQuiz,
  launchTrainingLab,
  markTrainingHintViewed,
  submitTrainingAiQuiz,
  submitTrainingLab,
} from "./api";
import type { TrainingAiMessage, TrainingAiQuizAttempt, TrainingContentDetail, TrainingContentItem, TrainingGradebookEntry, TrainingLabSubmission } from "../types";
import { useAuth } from "../context/AuthContext";
import "./TrainingHubSection.css";

type Props = {
  preferredLanguage: "de" | "en";
  focusContentSlug?: string | null;
};

const actionPrompts = [
  ["trainingAiTakeaways", "key_takeaways", "trainingAiTakeawaysQuestion"],
  ["trainingAiSimpleSummary", "simple_summary", "trainingAiSimpleSummaryQuestion"],
  ["trainingAiRisks", "risks", "trainingAiRisksQuestion"],
  ["trainingAiExplainForJunior", "explain_for_junior", "trainingAiExplainForJuniorQuestion"],
] as const;

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
};

const formatScore = (value?: string | number | null) => (value ?? "-");
const resolveCourseTitle = (item: TrainingContentItem, language: "de" | "en") => item.course ? (language === "en" ? item.course.titleEn : item.course.titleDe) : item.name;
const renderBody = (body: string) => body.split(/\n\s*\n/g).map((block) => block.trim()).filter(Boolean).map((block, index) => /^#{1,6}\s/.test(block) ? <h5 key={index} className="training-hub__section-title">{block.replace(/^#{1,6}\s+/, "")}</h5> : <p key={index} className="training-hub__body-copy">{block}</p>);
const resolveSubmissionLabel = (status: string) => status === "graded" ? "trainingSubmissionGraded" : status === "failed" ? "trainingSubmissionFailed" : status === "running" ? "trainingSubmissionRunning" : "trainingSubmissionQueued";

export const TrainingHubSection = ({ preferredLanguage, focusContentSlug }: Props) => {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  const [items, setItems] = useState<TrainingContentItem[]>([]);
  const [detail, setDetail] = useState<TrainingContentDetail | null>(null);
  const [gradebook, setGradebook] = useState<TrainingGradebookEntry[]>([]);
  const [submissions, setSubmissions] = useState<TrainingLabSubmission[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [launchingSlug, setLaunchingSlug] = useState<string | null>(null);
  const [selectedNotebookFile, setSelectedNotebookFile] = useState<File | null>(null);
  const [openedHintIds, setOpenedHintIds] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [aiError, setAiError] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [aiMessages, setAiMessages] = useState<TrainingAiMessage[]>([]);
  const [aiQuestion, setAiQuestion] = useState("");
  const [askingAi, setAskingAi] = useState(false);
  const [quizBusy, setQuizBusy] = useState(false);
  const [quiz, setQuiz] = useState<TrainingAiQuizAttempt | null>(null);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});

  const focusItem = useMemo(
    () => items.find((item) => item.slug === focusContentSlug) ?? null,
    [focusContentSlug, items],
  );
  const selectedItem = useMemo(() => items.find((item) => item.slug === selectedSlug) ?? null, [items, selectedSlug]);
  const selectedGradebook = useMemo(() => gradebook.find((entry) => entry.content.slug === selectedSlug) ?? null, [gradebook, selectedSlug]);
  const latestAssistant = useMemo(() => [...aiMessages].reverse().find((message) => message.role === "assistant" && message.payload) ?? null, [aiMessages]);
  const labSummary = detail?.labSummary ?? null;
  const attemptsExhausted = Boolean(selectedItem?.contentKind === "notebook" && labSummary?.attemptsRemaining === 0);
  const summary = useMemo(() => ({
    total: items.length,
    repeatable: items.filter((item) => item.isRepeatableOnDemand).length,
    labs: items.filter((item) => item.contentKind === "notebook").length,
  }), [items]);
  const prioritizedCourseSlug = selectedItem?.course?.slug ?? focusItem?.course?.slug ?? null;
  const prioritizedItems = useMemo(() => {
    return [...items].sort((left, right) => {
      const leftPriority = prioritizedCourseSlug && left.course?.slug === prioritizedCourseSlug ? 0 : 1;
      const rightPriority = prioritizedCourseSlug && right.course?.slug === prioritizedCourseSlug ? 0 : 1;
      if (leftPriority !== rightPriority) {
        return leftPriority - rightPriority;
      }
      const leftCourse = resolveCourseTitle(left, preferredLanguage);
      const rightCourse = resolveCourseTitle(right, preferredLanguage);
      const courseOrder = leftCourse.localeCompare(rightCourse);
      if (courseOrder !== 0) {
        return courseOrder;
      }
      return left.name.localeCompare(right.name);
    });
  }, [items, preferredLanguage, prioritizedCourseSlug]);
  const currentCourseItems = useMemo(
    () => prioritizedCourseSlug
      ? prioritizedItems.filter((item) => item.course?.slug === prioritizedCourseSlug)
      : prioritizedItems,
    [prioritizedCourseSlug, prioritizedItems],
  );
  const extraPracticeItems = useMemo(
    () => prioritizedCourseSlug
      ? prioritizedItems.filter((item) => item.course?.slug !== prioritizedCourseSlug)
      : [],
    [prioritizedCourseSlug, prioritizedItems],
  );
  const workflowSteps = useMemo(
    () => [
      { title: t("trainingWorkflowReviewTitle"), body: t("trainingWorkflowReviewBody") },
      { title: t("trainingWorkflowLaunchTitle"), body: t("trainingWorkflowLaunchBody") },
      { title: t("trainingWorkflowCodeTitle"), body: t("trainingWorkflowCodeBody") },
      { title: t("trainingWorkflowSubmitTitle"), body: t("trainingWorkflowSubmitBody") },
    ],
    [t],
  );

  const handleAuthError = (err: unknown) => {
    if (isAxiosError(err) && err.response?.status === 401) {
      logout();
      return true;
    }
    return false;
  };

  const loadRoot = async (nextSlug?: string | null) => {
    setRefreshing(true);
    setError("");
    try {
      const contentData = await fetchTrainingContent();
      setItems(contentData);
      const candidateSlug = nextSlug ?? focusContentSlug ?? selectedSlug ?? contentData[0]?.slug ?? null;
      setSelectedSlug(candidateSlug && contentData.some((item) => item.slug === candidateSlug) ? candidateSlug : contentData[0]?.slug ?? null);
      try {
        const gradebookData = await fetchTrainingGradebook();
        setGradebook(gradebookData);
      } catch (gradebookError) {
        if (!handleAuthError(gradebookError)) {
          setGradebook([]);
        }
      }
    } catch (err) {
      if (!handleAuthError(err)) setError(t("trainingLoadError"));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const loadSelected = async (slug: string, item: TrainingContentItem) => {
    setDetailLoading(true);
    setAiError("");
    try {
      const [detailData, conversationData, submissionData] = await Promise.all([
        fetchTrainingContentDetail(slug),
        fetchTrainingAiConversation(slug),
        item.contentKind === "notebook" ? fetchTrainingSubmissions(slug) : Promise.resolve([]),
      ]);
      setDetail(detailData);
      setConversationId(conversationData.conversation?.publicId ?? null);
      setAiMessages(conversationData.messages);
      setSubmissions(submissionData);
      setQuiz(null);
      setQuizAnswers({});
      setSelectedNotebookFile(null);
      setOpenedHintIds([]);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
    } catch (err) {
      if (!handleAuthError(err)) setAiError(t("trainingDetailLoadError"));
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => { void loadRoot(focusContentSlug); }, []);
  useEffect(() => {
    if (!focusContentSlug) return;
    if (!items.some((item) => item.slug === focusContentSlug)) return;
    setSelectedSlug(focusContentSlug);
  }, [focusContentSlug, items]);
  useEffect(() => {
    if (!selectedSlug) return;
    const item = items.find((entry) => entry.slug === selectedSlug);
    if (item) void loadSelected(selectedSlug, item);
  }, [items, selectedSlug]);

  const handleLaunch = async () => {
    if (!selectedItem) return;
    setLaunchingSlug(selectedItem.slug);
    try {
      const contract = await launchTrainingLab(selectedItem.slug);
      if (contract.launchUrl) window.open(contract.launchUrl, "_blank", "noopener,noreferrer");
      else setAiError(t("trainingLaunchError"));
    } catch (err) {
      if (!handleAuthError(err)) setAiError(t("trainingLaunchError"));
    } finally {
      setLaunchingSlug(null);
    }
  };

  const handleNotebookSubmit = async () => {
    if (!selectedItem?.lab?.notebookPath || !selectedNotebookFile) {
      setAiError(t("trainingSelectNotebookFile"));
      return;
    }
    setSubmitting(true);
    try {
      await submitTrainingLab(selectedItem.slug, selectedNotebookFile);
      await loadRoot(selectedItem.slug);
      await loadSelected(selectedItem.slug, selectedItem);
    } catch (err) {
      if (!handleAuthError(err)) {
        const detailText = isAxiosError(err) ? err.response?.data?.detail : "";
        setAiError(typeof detailText === "string" && detailText ? detailText : t("trainingSubmitError"));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleAskAi = async (question: string, promptType = "ask") => {
    if (!detail) return;
    const normalizedQuestion = question.trim();
    if (!normalizedQuestion) {
      setAiError(t("trainingAiQuestionRequired"));
      return;
    }
    setAskingAi(true);
    setAiError("");
    try {
      const result = await askTrainingAi({ contentSlug: detail.slug, question: normalizedQuestion, promptType, conversationId: conversationId ?? undefined });
      setConversationId(result.conversationId);
      setAiQuestion("");
      const refreshed = await fetchTrainingAiConversation(detail.slug);
      setAiMessages(refreshed.messages);
    } catch (err) {
      if (!handleAuthError(err)) {
        const detailText = isAxiosError(err) ? err.response?.data?.detail : "";
        setAiError(typeof detailText === "string" && detailText ? detailText : t("trainingAiAskError"));
      }
    } finally {
      setAskingAi(false);
    }
  };

  const handleGenerateQuiz = async () => {
    if (!detail) return;
    setQuizBusy(true);
    try {
      const nextQuiz = await generateTrainingAiQuiz(detail.slug, conversationId ?? undefined, 4);
      setQuiz(nextQuiz);
      setQuizAnswers({});
    } catch (err) {
      if (!handleAuthError(err)) setAiError(t("trainingAiQuizGenerateError"));
    } finally {
      setQuizBusy(false);
    }
  };

  const handleSubmitQuiz = async () => {
    if (!quiz) return;
    setQuizBusy(true);
    try {
      const checkedQuiz = await submitTrainingAiQuiz(quiz.publicId, quiz.questions.map((question) => ({ questionId: question.questionId, selectedOptionId: quizAnswers[question.questionId] ?? "" })));
      setQuiz(checkedQuiz);
    } catch (err) {
      if (!handleAuthError(err)) setAiError(t("trainingAiQuizSubmitError"));
    } finally {
      setQuizBusy(false);
    }
  };

  const toggleHint = async (hintId: number) => {
    const isOpen = openedHintIds.includes(hintId);
    setOpenedHintIds((current) => (isOpen ? current.filter((item) => item !== hintId) : [...current, hintId]));
    if (isOpen || !detail) return;
    try {
      await markTrainingHintViewed(detail.slug, hintId);
    } catch (err) {
      if (!handleAuthError(err)) setAiError(t("trainingHintViewError"));
    }
  };

  if (loading) return <div className="training-hub training-hub--loading">{t("loading")}</div>;

  return (
    <section className="training-hub" aria-label={t("tabTraining")}>
      <header className="training-hub__hero">
        <div>
          <p className="training-hub__eyebrow">{t("tabTraining")}</p>
          <h3>{t("trainingTitle")}</h3>
          <p className="training-hub__lead">{t("trainingIntro")}</p>
        </div>
        <button type="button" className="training-hub__refresh" onClick={() => void loadRoot(focusContentSlug ?? selectedSlug)} disabled={refreshing}>{refreshing ? t("loading") : t("trainingRefresh")}</button>
      </header>

      <div className="training-hub__summary">
        <article className="training-hub__stat"><span>{t("trainingAvailableModules")}</span><strong>{summary.total}</strong></article>
        <article className="training-hub__stat"><span>{t("trainingRepeatableCount")}</span><strong>{summary.repeatable}</strong></article>
        <article className="training-hub__stat"><span>{t("trainingAvailableLabs")}</span><strong>{summary.labs}</strong></article>
      </div>

      {error ? <p className="training-hub__error">{error}</p> : null}
      {aiError ? <p className="training-hub__error">{aiError}</p> : null}

      <section className="training-hub__workflow">
        <div className="training-hub__workflow-copy">
          <p className="training-hub__eyebrow">{t("trainingWorkflowTitle")}</p>
          <h4>{t("trainingWorkflowTitle")}</h4>
          <p>{t("trainingWorkflowIntro")}</p>
        </div>
        <div className="training-hub__workflow-steps">
          {workflowSteps.map((step, index) => (
            <article key={step.title} className="training-hub__workflow-step">
              <span className="training-hub__workflow-step-number">0{index + 1}</span>
              <strong>{step.title}</strong>
              <p>{step.body}</p>
            </article>
          ))}
        </div>
      </section>

      <div className="training-hub__grid">
        <aside className="training-hub__list">
          <div className="training-hub__list-head">
            <h4>{t("trainingAssignmentsTitle")}</h4>
            <p>{t("trainingAssignmentsIntro")}</p>
          </div>
          <div className="training-hub__list-scroll">
            {items.length === 0 ? <p>{t("trainingNoContent")}</p> : null}

            {currentCourseItems.length ? (
              <div className="training-hub__list-group">
                {prioritizedCourseSlug ? <p className="training-hub__list-label">{t("trainingCurrentCourseLabel")}</p> : null}
                {currentCourseItems.map((item) => {
                  const itemGradebook = gradebook.find((entry) => entry.content.slug === item.slug);
                  return (
                    <button key={item.slug} type="button" className={`training-hub__card ${selectedSlug === item.slug ? "is-active" : ""}`} onClick={() => setSelectedSlug(item.slug)}>
                      <span className="training-hub__card-label">{resolveCourseTitle(item, preferredLanguage)}</span>
                      <strong>{item.name}</strong>
                      <div className="training-hub__card-meta">
                        <span>{item.contentKind}</span>
                        <span>{item.difficulty}</span>
                        <span>{item.estimatedMinutes ? `${item.estimatedMinutes} min` : t("noData")}</span>
                      </div>
                      <span>{itemGradebook?.bestScore ? `${t("trainingBestScore")}: ${formatScore(itemGradebook.bestScore)}` : t("trainingNoGradebook")}</span>
                    </button>
                  );
                })}
              </div>
            ) : null}

            {extraPracticeItems.length ? (
              <div className="training-hub__list-group">
                <p className="training-hub__list-label">{t("trainingOtherLabsLabel")}</p>
                {extraPracticeItems.map((item) => {
                  const itemGradebook = gradebook.find((entry) => entry.content.slug === item.slug);
                  return (
                    <button key={item.slug} type="button" className={`training-hub__card ${selectedSlug === item.slug ? "is-active" : ""}`} onClick={() => setSelectedSlug(item.slug)}>
                      <span className="training-hub__card-label">{resolveCourseTitle(item, preferredLanguage)}</span>
                      <strong>{item.name}</strong>
                      <div className="training-hub__card-meta">
                        <span>{item.contentKind}</span>
                        <span>{item.difficulty}</span>
                        <span>{item.estimatedMinutes ? `${item.estimatedMinutes} min` : t("noData")}</span>
                      </div>
                      <span>{itemGradebook?.bestScore ? `${t("trainingBestScore")}: ${formatScore(itemGradebook.bestScore)}` : t("trainingNoGradebook")}</span>
                    </button>
                  );
                })}
              </div>
            ) : null}
          </div>
        </aside>

        <div className="training-hub__detail">
          {selectedItem && detail ? (
            <article className="training-hub__detail-card">
              <div className="training-hub__detail-header">
                <div className="training-hub__detail-copy">
                  <p className="training-hub__eyebrow">{resolveCourseTitle(selectedItem, preferredLanguage)}</p>
                  <h4>{detail.name}</h4>
                  <p>{detail.description || t("noData")}</p>
                </div>
                <div className="training-hub__detail-actions">
                  {selectedItem.contentKind === "notebook" ? <button type="button" className="training-hub__primary" onClick={() => void handleLaunch()} disabled={launchingSlug === selectedItem.slug}>{launchingSlug === selectedItem.slug ? t("loading") : t("trainingLaunchLab")}</button> : null}
                  <button type="button" className="training-hub__secondary" onClick={() => setAiQuestion(t("trainingAiDefaultQuestion"))}>{t("trainingAiAskButton")}</button>
                </div>
              </div>

              {selectedItem.contentKind === "notebook" ? (
                <div className="training-hub__callout">
                  <strong>{t("trainingCodeRunsTitle")}</strong>
                  <p>{t("trainingCodeRunsBody")}</p>
                </div>
              ) : null}

              <div className="training-hub__detail-layout">
                <div className="training-hub__content-panel">
                  <div className="training-hub__meta">
                    <span>{detail.contentKind}</span>
                    <span>{detail.difficulty}</span>
                    <span>{detail.estimatedMinutes ? `${detail.estimatedMinutes} min` : t("noData")}</span>
                    <span>{detail.isRepeatableOnDemand ? t("trainingRepeatable") : t("trainingSingleRun")}</span>
                  </div>
                  <div className="training-hub__section-headline">
                    <h5>{t("trainingAssignmentBriefTitle")}</h5>
                  </div>
                  {detailLoading ? <p>{t("loading")}</p> : <div className="training-hub__body">{renderBody(detail.bodyMarkdown)}</div>}
                  {detail.crossReferences.length ? <div className="training-hub__reference-list">{detail.crossReferences.map((reference) => <button key={`${reference.relationType}-${reference.slug}`} type="button" className="training-hub__reference-chip" onClick={() => setSelectedSlug(reference.slug)}>{reference.name}</button>)}</div> : null}

                  {selectedItem.contentKind === "notebook" ? (
                    <>
                      <div className="training-hub__summary-cards">
                        <article><span>{t("trainingLatestScore")}</span><strong>{formatScore(selectedGradebook?.latestScore)}</strong></article>
                        <article><span>{t("trainingBestScore")}</span><strong>{formatScore(selectedGradebook?.bestScore)}</strong></article>
                        <article><span>{t("trainingAttempts")}</span><strong>{selectedGradebook?.attemptsCount ?? 0}</strong></article>
                        <article><span>{t("trainingPassed")}</span><strong>{selectedGradebook?.passed == null ? "-" : selectedGradebook.passed ? t("yes") : t("no")}</strong></article>
                      </div>
                      {labSummary ? (
                        <div className="training-hub__lab-insights">
                          <article className="training-hub__lab-insight"><span>{t("trainingAssignmentCode")}</span><strong>{labSummary.assignmentCode}</strong></article>
                          <article className="training-hub__lab-insight"><span>{t("trainingPassThreshold")}</span><strong>{labSummary.passThresholdPercent}%</strong></article>
                          <article className="training-hub__lab-insight"><span>{t("trainingAttemptsRemaining")}</span><strong>{labSummary.attemptsRemaining ?? "-"}</strong></article>
                          <article className="training-hub__lab-insight"><span>{t("trainingUnlockedHints")}</span><strong>{labSummary.unlockedHintsCount}</strong></article>
                        </div>
                      ) : null}
                      <div className="training-hub__upload">
                        <div className="training-hub__section-headline">
                          <h5>{t("trainingSubmissionTitle")}</h5>
                        </div>
                        <p className="training-hub__panel-copy">{t("trainingSubmissionHelp")}</p>
                        <label className="training-hub__upload-label" htmlFor={`training-upload-${selectedItem.slug}`}>{t("trainingSelectedNotebook")}</label>
                        <input id={`training-upload-${selectedItem.slug}`} ref={uploadInputRef} className="training-hub__upload-input" type="file" accept=".ipynb,application/x-ipynb+json,application/json" onChange={(event) => setSelectedNotebookFile(event.target.files?.[0] ?? null)} />
                        <p className="training-hub__upload-hint">{selectedNotebookFile?.name || t("trainingNoNotebookSelected")}</p>
                        {attemptsExhausted ? <p className="training-hub__warning">{t("trainingAttemptsExhausted")}</p> : null}
                        <button type="button" className="training-hub__secondary training-hub__submit-button" onClick={() => void handleNotebookSubmit()} disabled={submitting || !selectedNotebookFile || attemptsExhausted}>{submitting ? t("loading") : t("trainingSubmitLab")}</button>
                      </div>
                      {labSummary ? (
                        <div className="training-hub__history">
                          <div className="training-hub__section-headline">
                            <h5>{t("trainingHintsTitle")}</h5>
                            <span>{t("trainingLockedHints")}: {labSummary.lockedHintsCount}</span>
                          </div>
                          {labSummary.hints.length === 0 ? <p>{t("trainingNoHints")}</p> : null}
                          {labSummary.hints.map((hint) => {
                            const isOpen = openedHintIds.includes(hint.id);
                            return (
                              <article key={hint.id} className={`training-hub__hint ${hint.isRecommended ? "is-recommended" : ""}`}>
                                <div className="training-hub__hint-header">
                                  <div>
                                    <strong>{hint.title}</strong>
                                    <span>{hint.isRecommended ? t("trainingRecommendedHint") : t("trainingHintAvailable")}</span>
                                  </div>
                                  <button type="button" className="training-hub__reference-chip" onClick={() => void toggleHint(hint.id)}>
                                    {isOpen ? t("trainingHideHint") : t("trainingShowHint")}
                                  </button>
                                </div>
                                {isOpen ? <div className="training-hub__body">{renderBody(hint.bodyMarkdown)}</div> : null}
                              </article>
                            );
                          })}
                        </div>
                      ) : null}
                      <div className="training-hub__history">
                        <div className="training-hub__section-headline">
                          <h5>{t("trainingAttemptsHistory")}</h5>
                        </div>
                        {submissions.length === 0 ? <p>{t("trainingNoSubmissions")}</p> : null}
                        {submissions.map((submission) => {
                          const highlights = Array.isArray(submission.feedbackPayload?.feedbackHighlights) ? submission.feedbackPayload.feedbackHighlights as string[] : [];
                          const tests = Array.isArray(submission.feedbackPayload?.tests) ? submission.feedbackPayload.tests as Array<Record<string, unknown>> : [];
                          return (
                            <article key={submission.publicId} className="training-hub__submission">
                              <div>
                                <strong>{submission.attemptNumber}. {t(resolveSubmissionLabel(submission.status))}</strong>
                                <p>{submission.notebookArtifactFilename || submission.notebookPath}</p>
                              </div>
                              <div className="training-hub__submission-meta">
                                <span>{t("trainingSubmittedAt")}: {formatDateTime(submission.submittedAt)}</span>
                                <span>{t("trainingGradedAt")}: {formatDateTime(submission.gradedAt)}</span>
                                <span>{t("trainingScore")}: {formatScore(submission.score)} / {formatScore(submission.maxScore)}</span>
                              </div>
                              {submission.feedbackMarkdown ? <p className="training-hub__feedback">{submission.feedbackMarkdown}</p> : null}
                              {highlights.length ? <div className="training-hub__highlight-list">{highlights.map((highlight) => <span key={highlight} className="training-hub__highlight-chip">{highlight}</span>)}</div> : null}
                              {tests.length ? (
                                <div className="training-hub__tests">
                                  {tests.map((test, index) => (
                                    <div key={`${submission.publicId}-${index}`} className="training-hub__test-item">
                                      <strong>{String(test.label || `Check ${index + 1}`)}</strong>
                                      <span>{String(test.passed ? t("yes") : t("no"))}</span>
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                              {(submission.feedbackReportUrl || submission.jsonReportUrl) ? (
                                <div className="training-hub__submission-links">
                                  {submission.feedbackReportUrl ? <a href={submission.feedbackReportUrl} target="_blank" rel="noreferrer" className="training-hub__reference-chip">{t("trainingFeedbackReport")}</a> : null}
                                  {submission.jsonReportUrl ? <a href={submission.jsonReportUrl} target="_blank" rel="noreferrer" className="training-hub__reference-chip">{t("trainingJsonReport")}</a> : null}
                                </div>
                              ) : null}
                            </article>
                          );
                        })}
                      </div>
                    </>
                  ) : null}
                </div>

                <aside className="training-hub__ai-panel">
                  <h5>{t("trainingAiTitle")}</h5>
                  <p>{t("trainingAiIntro")}</p>
                  <div className="training-hub__reference-list">
                    {actionPrompts.map(([labelKey, promptType, questionKey]) => <button key={labelKey} type="button" className="training-hub__reference-chip" onClick={() => void handleAskAi(t(questionKey), promptType)} disabled={askingAi}>{t(labelKey)}</button>)}
                  </div>
                  <label className="training-hub__upload-label" htmlFor="training-ai-question">{t("trainingAiQuestionLabel")}</label>
                  <textarea id="training-ai-question" className="training-hub__textarea" value={aiQuestion} placeholder={t("trainingAiPlaceholder")} onChange={(event) => setAiQuestion(event.target.value)} />
                  <div className="training-hub__ai-toolbar">
                    <button type="button" className="training-hub__primary" onClick={() => void handleAskAi(aiQuestion, "ask")} disabled={askingAi}>{askingAi ? t("loading") : t("trainingAiAskButton")}</button>
                    <button type="button" className="training-hub__secondary" onClick={() => void handleGenerateQuiz()} disabled={quizBusy}>{quizBusy ? t("loading") : t("trainingAiGenerateQuiz")}</button>
                  </div>
                  <div className="training-hub__ai-feed">
                    {aiMessages.length === 0 ? <p>{t("trainingAiNoMessages")}</p> : null}
                    {aiMessages.map((message) => (
                      <article key={message.id} className={`training-hub__message training-hub__message--${message.role}`}>
                        <span className="training-hub__message-role">
                          {message.role === "assistant" ? t("trainingAiAssistantLabel") : t("trainingAiStudentLabel")}
                        </span>
                        <p>{message.role === "assistant" && message.payload ? message.payload.shortAnswer : message.body}</p>
                        {message.role === "assistant" && message.payload ? (
                          <>
                            <div className="training-hub__assistant-detail">
                              {message.payload.detailedAnswer.split("\n").map((part, index) => (
                                <p key={`${message.id}-${index}`}>{part}</p>
                              ))}
                            </div>
                            {message.payload.citations.length ? (
                              <div className="training-hub__citations">
                                {message.payload.citations.map((citation, index) => (
                                  <button
                                    key={`${citation.contentSlug}-${index}`}
                                    type="button"
                                    className="training-hub__citation"
                                    onClick={() => setSelectedSlug(citation.contentSlug)}
                                  >
                                    <strong>{citation.citationLabel || citation.contentName}</strong>
                                    <span>{citation.quoteSnippet}</span>
                                  </button>
                                ))}
                              </div>
                            ) : null}
                            {message.payload.needsEscalation && message.payload.escalation ? (
                              <p className="training-hub__escalation">{message.payload.escalation.message}</p>
                            ) : null}
                          </>
                        ) : null}
                      </article>
                    ))}
                  </div>
                  {latestAssistant?.payload?.followUpPrompts?.length ? (
                    <div className="training-hub__follow-ups">
                      <h6>{t("trainingAiFollowUps")}</h6>
                      <div className="training-hub__reference-list">
                        {latestAssistant.payload.followUpPrompts.map((prompt) => (
                          <button key={prompt} type="button" className="training-hub__reference-chip" onClick={() => void handleAskAi(prompt, "ask")}>
                            {prompt}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {quiz ? (
                    <div className="training-hub__quiz">
                      <h6>{quiz.title}</h6>
                      {quiz.questions.map((question) => (
                        <article key={question.questionId} className="training-hub__quiz-question">
                          <strong>{question.prompt}</strong>
                          <div className="training-hub__quiz-options">
                            {question.options.map((option) => {
                              const checked = (quizAnswers[question.questionId] ?? question.selectedOptionId ?? "") === option.id;
                              const completed = quiz.status === "completed";
                              const correct = completed && question.correctOptionId === option.id;
                              const wrong = completed && checked && question.correctOptionId !== option.id;
                              return (
                                <label key={option.id} className={`training-hub__quiz-option ${correct ? "is-correct" : ""} ${wrong ? "is-wrong" : ""}`}>
                                  <input
                                    type="radio"
                                    name={question.questionId}
                                    checked={checked}
                                    onChange={() => setQuizAnswers((prev) => ({ ...prev, [question.questionId]: option.id }))}
                                    disabled={completed}
                                  />
                                  <span>{option.label}</span>
                                </label>
                              );
                            })}
                          </div>
                          {quiz.status === "completed" ? (
                            <p className="training-hub__quiz-explanation">{question.explanation}</p>
                          ) : null}
                        </article>
                      ))}
                      <div className="training-hub__ai-toolbar">
                        {quiz.status === "completed" ? (
                          <p className="training-hub__quiz-result">
                            {t("trainingAiQuizResult")}: {formatScore(quiz.score)} / {formatScore(quiz.maxScore)}
                          </p>
                        ) : (
                          <button type="button" className="training-hub__primary" onClick={() => void handleSubmitQuiz()} disabled={quizBusy}>
                            {quizBusy ? t("loading") : t("trainingAiSubmitQuiz")}
                          </button>
                        )}
                      </div>
                    </div>
                  ) : null}
                </aside>
              </div>
            </article>
          ) : <article className="training-hub__detail-card"><p>{detailLoading ? t("loading") : t("trainingNoContent")}</p></article>}
        </div>
      </div>
    </section>
  );
};
