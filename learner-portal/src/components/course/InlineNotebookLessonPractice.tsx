import { useEffect, useMemo, useRef, useState } from "react";
import { isAxiosError } from "axios";

import {
  askTrainingAi,
  fetchTrainingAiConversation,
  fetchTrainingContentDetail,
  fetchTrainingGradebook,
  fetchTrainingSubmissions,
  generateTrainingAiQuiz,
  launchTrainingLab,
  markTrainingHintViewed,
  submitTrainingAiQuiz,
  submitTrainingLab,
  submitTrainingLabAnswer,
} from "../../training/api";
import type {
  CourseLessonSectionItem,
  TrainingAiMessage,
  TrainingAiQuizAttempt,
  TrainingContentDetail,
  TrainingGradebookEntry,
  TrainingLabSubmission,
} from "../../types";
import { renderLessonMarkdownBlocks } from "./courseDocumentUtils";

type Props = {
  item: CourseLessonSectionItem;
};

const actionPrompts = [
  { label: "Explain simply", promptType: "simple_summary", question: "Explain this notebook assignment in simple words." },
  { label: "Key takeaways", promptType: "key_takeaways", question: "Give me the 3 most important takeaways before I start coding." },
  { label: "Main risks", promptType: "risks", question: "What mistakes should I avoid in this notebook?" },
] as const;

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
};

const formatScore = (value?: string | number | null) => (value ?? "-");

const extractChecklistFromMarkdown = (markdown: string) =>
  markdown
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => /^(\d+\.|-)\s+/.test(line))
    .map((line) => line.replace(/^(\d+\.|-)\s+/, "").replace(/\*\*/g, "").trim());

const buildAnswerReviewPrompt = (answerDraft: string) =>
  [
    "Review this proposed learner answer for the notebook assignment.",
    "Check whether it includes the main metrics, the leakage note, and the non-advisory conclusion.",
    "Call out what is missing and how to improve it.",
    "",
    answerDraft.trim(),
  ].join("\n");

export const InlineNotebookLessonPractice = ({ item }: Props) => {
  const contentSlug = item.trainingContent?.slug ?? "";
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  const [detail, setDetail] = useState<TrainingContentDetail | null>(null);
  const [gradebookEntry, setGradebookEntry] = useState<TrainingGradebookEntry | null>(null);
  const [submissions, setSubmissions] = useState<TrainingLabSubmission[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TrainingAiMessage[]>([]);
  const [quiz, setQuiz] = useState<TrainingAiQuizAttempt | null>(null);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});
  const [openedHintIds, setOpenedHintIds] = useState<number[]>([]);
  const [selectedNotebookFile, setSelectedNotebookFile] = useState<File | null>(null);
  const [aiQuestion, setAiQuestion] = useState("");
  const [answerDraft, setAnswerDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submittingAnswer, setSubmittingAnswer] = useState(false);
  const [askingAi, setAskingAi] = useState(false);
  const [quizBusy, setQuizBusy] = useState(false);
  const [error, setError] = useState("");

  const loadPracticeData = async () => {
    if (!contentSlug) {
      setLoading(false);
      setError("Notebook content is not linked to this lesson item yet.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const [detailData, gradebook, conversation, submissionData] = await Promise.all([
        fetchTrainingContentDetail(contentSlug),
        fetchTrainingGradebook(),
        fetchTrainingAiConversation(contentSlug),
        fetchTrainingSubmissions(contentSlug),
      ]);
      setDetail(detailData);
      setGradebookEntry(gradebook.find((entry) => entry.content.slug === contentSlug) ?? null);
      setConversationId(conversation.conversation?.publicId ?? null);
      setMessages(conversation.messages);
      setSubmissions(submissionData);
      setQuiz(null);
      setQuizAnswers({});
      setOpenedHintIds([]);
      setSelectedNotebookFile(null);
      if (uploadInputRef.current) {
        uploadInputRef.current.value = "";
      }
    } catch (loadError) {
      const detailMessage =
        isAxiosError(loadError) && typeof loadError.response?.data?.detail === "string"
          ? loadError.response.data.detail
          : "Failed to load notebook practice data.";
      setError(detailMessage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadPracticeData();
  }, [contentSlug]);

  const latestAssistant = useMemo(
    () => [...messages].reverse().find((message) => message.role === "assistant" && message.payload) ?? null,
    [messages],
  );
  const practiceChecklist = useMemo(() => extractChecklistFromMarkdown(detail?.bodyMarkdown ?? ""), [detail?.bodyMarkdown]);
  const labSummary = detail?.labSummary ?? null;
  const attemptsExhausted = Boolean(detail?.contentKind === "notebook" && labSummary?.attemptsRemaining === 0);

  const handleLaunch = async () => {
    if (!contentSlug) return;
    setLaunching(true);
    setError("");
    try {
      const contract = await launchTrainingLab(contentSlug);
      if (contract.launchUrl) {
        window.open(contract.launchUrl, "_blank", "noopener,noreferrer");
        return;
      }
      setError("Notebook runtime launch URL is not available.");
    } catch (launchError) {
      const detailMessage =
        isAxiosError(launchError) && typeof launchError.response?.data?.detail === "string"
          ? launchError.response.data.detail
          : "Failed to launch the notebook runtime.";
      setError(detailMessage);
    } finally {
      setLaunching(false);
    }
  };

  const handleSubmit = async () => {
    if (!contentSlug || !selectedNotebookFile) {
      setError("Choose a .ipynb file before submitting.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await submitTrainingLab(contentSlug, selectedNotebookFile);
      await loadPracticeData();
    } catch (submitError) {
      const detailMessage =
        isAxiosError(submitError) && typeof submitError.response?.data?.detail === "string"
          ? submitError.response.data.detail
          : "Failed to submit the notebook.";
      setError(detailMessage);
    } finally {
      setSubmitting(false);
    }
  };

  const handleAskAi = async (question: string, promptType = "ask") => {
    const normalizedQuestion = question.trim();
    if (!contentSlug || !normalizedQuestion) {
      setError("Enter a question for the AI assistant.");
      return;
    }
    setAskingAi(true);
    setError("");
    try {
      const result = await askTrainingAi({
        contentSlug,
        question: normalizedQuestion,
        promptType,
        conversationId: conversationId ?? undefined,
      });
      setConversationId(result.conversationId);
      setAiQuestion("");
      const refreshed = await fetchTrainingAiConversation(contentSlug);
      setMessages(refreshed.messages);
    } catch (aiError) {
      const detailMessage =
        isAxiosError(aiError) && typeof aiError.response?.data?.detail === "string"
          ? aiError.response.data.detail
          : "AI assistant is temporarily unavailable.";
      setError(detailMessage);
    } finally {
      setAskingAi(false);
    }
  };

  const handleReviewAnswer = async () => {
    if (!answerDraft.trim()) {
      setError("Paste your metrics and short conclusion before asking for a review.");
      return;
    }
    await handleAskAi(buildAnswerReviewPrompt(answerDraft), "answer_review");
  };

  const handleSubmitAnswer = async () => {
    if (!contentSlug || !answerDraft.trim()) {
      setError("Paste your metrics and short conclusion before submitting the answer.");
      return;
    }
    setSubmittingAnswer(true);
    setError("");
    try {
      await submitTrainingLabAnswer(contentSlug, answerDraft.trim());
      await loadPracticeData();
    } catch (submitError) {
      const detailMessage =
        isAxiosError(submitError) && typeof submitError.response?.data?.detail === "string"
          ? submitError.response.data.detail
          : "Failed to submit the text answer.";
      setError(detailMessage);
    } finally {
      setSubmittingAnswer(false);
    }
  };

  const handleGenerateQuiz = async () => {
    if (!contentSlug) return;
    setQuizBusy(true);
    setError("");
    try {
      const nextQuiz = await generateTrainingAiQuiz(contentSlug, conversationId ?? undefined, 4);
      setQuiz(nextQuiz);
      setQuizAnswers({});
    } catch (quizError) {
      const detailMessage =
        isAxiosError(quizError) && typeof quizError.response?.data?.detail === "string"
          ? quizError.response.data.detail
          : "Failed to generate the AI quiz.";
      setError(detailMessage);
    } finally {
      setQuizBusy(false);
    }
  };

  const handleSubmitQuiz = async () => {
    if (!quiz) return;
    setQuizBusy(true);
    setError("");
    try {
      const checkedQuiz = await submitTrainingAiQuiz(
        quiz.publicId,
        quiz.questions.map((question) => ({
          questionId: question.questionId,
          selectedOptionId: quizAnswers[question.questionId] ?? "",
        })),
      );
      setQuiz(checkedQuiz);
    } catch (quizError) {
      const detailMessage =
        isAxiosError(quizError) && typeof quizError.response?.data?.detail === "string"
          ? quizError.response.data.detail
          : "Failed to submit the AI quiz.";
      setError(detailMessage);
    } finally {
      setQuizBusy(false);
    }
  };

  const toggleHint = async (hintId: number) => {
    const isOpen = openedHintIds.includes(hintId);
    setOpenedHintIds((current) => (isOpen ? current.filter((currentId) => currentId !== hintId) : [...current, hintId]));
    if (isOpen || !contentSlug) return;
    try {
      await markTrainingHintViewed(contentSlug, hintId);
    } catch {
      // Hint view tracking is non-blocking for the lesson UI.
    }
  };

  if (loading) {
    return <div className="dashboard-page__lesson-training-state">Loading notebook practice...</div>;
  }

  if (!detail) {
    return <div className="dashboard-page__lesson-training-state dashboard-page__lesson-training-state--error">{error}</div>;
  }

  return (
    <section className="dashboard-page__lesson-training">
      <header className="dashboard-page__lesson-training-header">
        <div>
          <span className="dashboard-page__lesson-block-kicker">Interactive notebook</span>
          <h4>{detail.name}</h4>
          <p>{detail.description || item.description || "Notebook assignment linked to this lesson."}</p>
        </div>
        <div className="dashboard-page__lesson-training-actions">
          <button type="button" className="dashboard-page__lesson-action dashboard-page__lesson-action--primary" onClick={() => void handleLaunch()} disabled={launching}>
            {launching ? "Launching..." : "Open in JupyterLab"}
          </button>
          <button type="button" className="dashboard-page__lesson-action" onClick={() => void loadPracticeData()}>
            Refresh
          </button>
        </div>
      </header>

      <div className="dashboard-page__lesson-training-grid">
        <div className="dashboard-page__lesson-training-main">
          <article className="dashboard-page__lesson-training-card">
            <div className="dashboard-page__lesson-card-meta">
              <span>{detail.contentKind}</span>
              <span>{detail.difficulty}</span>
              <span>{detail.estimatedMinutes ? `${detail.estimatedMinutes} min` : "Self-paced"}</span>
              <span>{detail.isRepeatableOnDemand ? "Repeatable" : "Single-run"}</span>
            </div>
            <div className="dashboard-page__lesson-training-body">
              <p className="dashboard-page__lesson-training-compact-copy">
                {detail.description || item.description || "Notebook assignment linked to this lesson."}
              </p>
              {practiceChecklist.length ? (
                <ol className="dashboard-page__lesson-training-checklist">
                  {practiceChecklist.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              ) : (
                renderLessonMarkdownBlocks(detail.bodyMarkdown, "dashboard-page__lesson-training-body")
              )}
              <div className="dashboard-page__lesson-inline-note dashboard-page__lesson-inline-note--soft">
                For this demo, you can either upload the final `.ipynb` file or paste the notebook outputs and conclusion
                into <strong>AI assistant</strong> for a quick answer check.
              </div>
            </div>
          </article>

          <div className="dashboard-page__lesson-training-metrics">
            <article className="dashboard-page__lesson-training-metric">
              <span>Latest score</span>
              <strong>{formatScore(gradebookEntry?.latestScore)}</strong>
            </article>
            <article className="dashboard-page__lesson-training-metric">
              <span>Best score</span>
              <strong>{formatScore(gradebookEntry?.bestScore)}</strong>
            </article>
            <article className="dashboard-page__lesson-training-metric">
              <span>Attempts</span>
              <strong>{gradebookEntry?.attemptsCount ?? 0}</strong>
            </article>
            <article className="dashboard-page__lesson-training-metric">
              <span>Passed</span>
              <strong>{gradebookEntry?.passed == null ? "-" : gradebookEntry.passed ? "Yes" : "No"}</strong>
            </article>
          </div>

          {labSummary ? (
            <div className="dashboard-page__lesson-training-metrics dashboard-page__lesson-training-metrics--secondary">
              <article className="dashboard-page__lesson-training-metric dashboard-page__lesson-training-metric--wide">
                <span>Assignment code</span>
                <strong className="dashboard-page__lesson-training-metric-value dashboard-page__lesson-training-metric-value--code">
                  {labSummary.assignmentCode}
                </strong>
              </article>
              <article className="dashboard-page__lesson-training-metric">
                <span>Pass threshold</span>
                <strong className="dashboard-page__lesson-training-metric-value">{labSummary.passThresholdPercent}%</strong>
              </article>
              <article className="dashboard-page__lesson-training-metric">
                <span>Attempts remaining</span>
                <strong className="dashboard-page__lesson-training-metric-value">{labSummary.attemptsRemaining ?? "-"}</strong>
              </article>
              <article className="dashboard-page__lesson-training-metric">
                <span>Unlocked hints</span>
                <strong className="dashboard-page__lesson-training-metric-value">{labSummary.unlockedHintsCount}</strong>
              </article>
            </div>
          ) : null}

          <article className="dashboard-page__lesson-training-card">
            <div className="dashboard-page__lesson-training-card-header">
              <div>
                <h5>Full notebook upload</h5>
                <p>Optional for the full artifact-based grading path after you finish the lab in JupyterLab.</p>
              </div>
            </div>
            <label className="dashboard-page__lesson-upload-label" htmlFor={`lesson-notebook-upload-${detail.slug}`}>
              Notebook for grading
            </label>
            <input
              id={`lesson-notebook-upload-${detail.slug}`}
              ref={uploadInputRef}
              className="dashboard-page__lesson-upload-input"
              type="file"
              accept=".ipynb,application/x-ipynb+json,application/json"
              onChange={(event) => setSelectedNotebookFile(event.target.files?.[0] ?? null)}
            />
            <p className="dashboard-page__lesson-upload-hint">{selectedNotebookFile?.name || "No file selected yet."}</p>
            {attemptsExhausted ? (
              <p className="dashboard-page__lesson-inline-warning">
                All submission attempts are currently used. Ask an administrator to unlock more attempts if needed.
              </p>
            ) : null}
            <div className="dashboard-page__lesson-actions">
              <button
                type="button"
                className="dashboard-page__lesson-action dashboard-page__lesson-action--primary"
                onClick={() => void handleSubmit()}
                disabled={submitting || !selectedNotebookFile || attemptsExhausted}
              >
                {submitting ? "Submitting..." : "Submit notebook"}
              </button>
            </div>
          </article>

          {labSummary?.hints?.length ? (
            <article className="dashboard-page__lesson-training-card">
              <div className="dashboard-page__lesson-training-card-header">
                <div>
                  <h5>Hints</h5>
                  <p>Context-aware hints unlock as you work through the assignment.</p>
                </div>
                <span className="dashboard-page__lesson-inline-meta">Locked: {labSummary.lockedHintsCount}</span>
              </div>
              <div className="dashboard-page__lesson-hints">
                {labSummary.hints.map((hint) => {
                  const isOpen = openedHintIds.includes(hint.id);
                  return (
                    <article key={hint.id} className="dashboard-page__lesson-hint">
                      <div className="dashboard-page__lesson-hint-header">
                        <div>
                          <strong>{hint.title}</strong>
                          <p>{hint.isRecommended ? "Recommended after your latest attempt" : "Available hint"}</p>
                        </div>
                        <button type="button" className="dashboard-page__lesson-action" onClick={() => void toggleHint(hint.id)}>
                          {isOpen ? "Hide hint" : "Show hint"}
                        </button>
                      </div>
                      {isOpen ? (
                        <div className="dashboard-page__lesson-training-body">
                          {renderLessonMarkdownBlocks(hint.bodyMarkdown, "dashboard-page__lesson-training-body")}
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            </article>
          ) : null}

          {submissions.length ? (
            <article className="dashboard-page__lesson-training-card">
              <div className="dashboard-page__lesson-training-card-header">
                <div>
                  <h5>Attempts and reports</h5>
                  <p>Submission history for this notebook assignment.</p>
                </div>
              </div>
              <div className="dashboard-page__lesson-submissions">
                {submissions.map((submission) => (
                  <article key={submission.publicId} className="dashboard-page__lesson-submission">
                    <div className="dashboard-page__lesson-submission-header">
                      <div>
                        <strong>Attempt {submission.attemptNumber}</strong>
                        <p>
                          {submission.submissionMode === "text_answer"
                            ? submission.responseTextPreview || "Quick answer submission"
                            : submission.notebookArtifactFilename || submission.notebookPath}
                        </p>
                      </div>
                      <span className="dashboard-page__lesson-inline-meta">{submission.status}</span>
                    </div>
                    <div className="dashboard-page__lesson-submission-meta">
                      <span>Submitted: {formatDateTime(submission.submittedAt)}</span>
                      <span>Graded: {formatDateTime(submission.gradedAt)}</span>
                      <span>Score: {formatScore(submission.score)} / {formatScore(submission.maxScore)}</span>
                    </div>
                    {submission.feedbackMarkdown ? (
                      <div className="dashboard-page__lesson-training-body">
                        {renderLessonMarkdownBlocks(submission.feedbackMarkdown, "dashboard-page__lesson-training-body")}
                      </div>
                    ) : null}
                    <div className="dashboard-page__lesson-resource-actions">
                      {submission.feedbackReportUrl ? (
                        <a href={submission.feedbackReportUrl} target="_blank" rel="noreferrer">
                          Open feedback report
                        </a>
                      ) : null}
                      {submission.jsonReportUrl ? (
                        <a href={submission.jsonReportUrl} target="_blank" rel="noreferrer">
                          Open JSON report
                        </a>
                      ) : null}
                    </div>
                  </article>
                ))}
              </div>
            </article>
          ) : null}
        </div>

        <aside className="dashboard-page__lesson-training-sidebar">
          <article className="dashboard-page__lesson-training-card">
            <div className="dashboard-page__lesson-training-card-header">
              <div>
                <h5>AI assistant</h5>
                <p>Use AI for clarification, draft review, and a quick answer submission without leaving the lesson.</p>
              </div>
            </div>
            <div className="dashboard-page__lesson-inline-actions">
              {actionPrompts.map((action) => (
                <button
                  key={action.label}
                  type="button"
                  className="dashboard-page__lesson-action"
                  onClick={() => void handleAskAi(action.question, action.promptType)}
                  disabled={askingAi}
                >
                  {action.label}
                </button>
              ))}
            </div>
            <label className="dashboard-page__lesson-upload-label" htmlFor={`lesson-ai-${detail.slug}`}>
              Question about this lesson
            </label>
            <textarea
              id={`lesson-ai-${detail.slug}`}
              className="dashboard-page__lesson-ai-textarea"
              rows={5}
              value={aiQuestion}
              onChange={(event) => setAiQuestion(event.currentTarget.value)}
              placeholder="Ask about the assignment, formulas, expected output, or grading criteria."
            />
            <div className="dashboard-page__lesson-actions">
              <button
                type="button"
                className="dashboard-page__lesson-action dashboard-page__lesson-action--primary"
                onClick={() => void handleAskAi(aiQuestion)}
                disabled={askingAi}
              >
                {askingAi ? "Thinking..." : "Ask AI"}
              </button>
              <button type="button" className="dashboard-page__lesson-action" onClick={() => void handleGenerateQuiz()} disabled={quizBusy}>
                {quizBusy ? "Preparing..." : "Generate quiz"}
              </button>
            </div>

            <div className="dashboard-page__lesson-training-card dashboard-page__lesson-training-card--nested">
              <div className="dashboard-page__lesson-training-card-header">
                <div>
                  <h5>Quick answer</h5>
                  <p>Paste the key notebook outputs and your short conclusion here for a fast demo-grade path.</p>
                </div>
              </div>
              <textarea
                className="dashboard-page__lesson-ai-textarea"
                rows={6}
                value={answerDraft}
                onChange={(event) => setAnswerDraft(event.currentTarget.value)}
                placeholder={"Rows: 18\nBaseline MAE: 715.00\nRolling MAE: 1406.67\nNext forecast: 50066.67\n\nLeakage is a risk if future information reaches the features. This notebook is not investment advice."}
              />
              <div className="dashboard-page__lesson-actions">
                <button
                  type="button"
                  className="dashboard-page__lesson-action"
                  onClick={() => void handleReviewAnswer()}
                  disabled={askingAi || !answerDraft.trim()}
                >
                  {askingAi ? "Reviewing..." : "Review with AI"}
                </button>
                <button
                  type="button"
                  className="dashboard-page__lesson-action dashboard-page__lesson-action--primary"
                  onClick={() => void handleSubmitAnswer()}
                  disabled={submittingAnswer || !answerDraft.trim()}
                >
                  {submittingAnswer ? "Submitting..." : "Submit answer"}
                </button>
              </div>
            </div>

            {messages.length ? (
              <div className="dashboard-page__lesson-ai-feed">
                {messages.map((message) => (
                  <article
                    key={message.id}
                    className={`dashboard-page__lesson-message dashboard-page__lesson-message--${message.role}`}
                  >
                    <strong>{message.role === "assistant" ? "Assistant" : message.role === "user" ? "You" : "System"}</strong>
                    <p>{message.payload?.detailedAnswer || message.body}</p>
                    {message.payload?.followUpPrompts?.length ? (
                      <div className="dashboard-page__lesson-inline-actions">
                        {message.payload.followUpPrompts.slice(0, 3).map((prompt) => (
                          <button
                            key={prompt}
                            type="button"
                            className="dashboard-page__lesson-action"
                            onClick={() => void handleAskAi(prompt)}
                          >
                            {prompt}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : null}

            {!messages.length && latestAssistant == null ? (
              <p className="dashboard-page__lesson-empty-copy">No AI conversation yet. Use one of the quick prompts or ask your own question.</p>
            ) : null}
          </article>

          {quiz ? (
            <article className="dashboard-page__lesson-training-card">
              <div className="dashboard-page__lesson-training-card-header">
                <div>
                  <h5>AI quiz</h5>
                  <p>Quick checkpoint generated from the current assignment context.</p>
                </div>
              </div>
              <div className="dashboard-page__lesson-quiz">
                {quiz.questions.map((question) => (
                  <article key={question.questionId} className="dashboard-page__lesson-quiz-question">
                    <strong>{question.prompt}</strong>
                    <div className="dashboard-page__lesson-quiz-options">
                      {question.options.map((option) => {
                        const isSelected = quizAnswers[question.questionId] === option.id;
                        const isRevealed = quiz.status === "submitted";
                        const isCorrect = isRevealed && question.correctOptionId === option.id;
                        const isWrongSelection = isRevealed && isSelected && question.correctOptionId !== option.id;
                        return (
                          <label
                            key={option.id}
                            className={`dashboard-page__lesson-quiz-option ${isSelected ? "is-selected" : ""} ${isCorrect ? "is-correct" : ""} ${isWrongSelection ? "is-wrong" : ""}`}
                          >
                            <input
                              type="radio"
                              name={question.questionId}
                              checked={isSelected}
                              onChange={() =>
                                setQuizAnswers((current) => ({
                                  ...current,
                                  [question.questionId]: option.id,
                                }))
                              }
                              disabled={quiz.status === "submitted"}
                            />
                            <span>{option.label}</span>
                          </label>
                        );
                      })}
                    </div>
                    {quiz.status === "submitted" ? <p>{question.explanation}</p> : null}
                  </article>
                ))}
              </div>
              <div className="dashboard-page__lesson-actions">
                {quiz.status !== "submitted" ? (
                  <button
                    type="button"
                    className="dashboard-page__lesson-action dashboard-page__lesson-action--primary"
                    onClick={() => void handleSubmitQuiz()}
                    disabled={quizBusy}
                  >
                    {quizBusy ? "Checking..." : "Submit quiz"}
                  </button>
                ) : (
                  <div className="dashboard-page__lesson-inline-meta">
                    Score: {quiz.score ?? "-"} / {quiz.maxScore ?? "-"} · Correct answers: {quiz.correctAnswersCount}
                  </div>
                )}
              </div>
            </article>
          ) : null}
        </aside>
      </div>

      {error ? <p className="dashboard-page__lesson-inline-error">{error}</p> : null}
    </section>
  );
};

export default InlineNotebookLessonPractice;
