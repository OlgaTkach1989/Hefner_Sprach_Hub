import { useEffect, useMemo, useRef, useState } from "react";
import { isAxiosError } from "axios";
import { Navigate, useHref, useLocation, useParams } from "react-router-dom";

import {
  askStudentLessonAi,
  fetchStudentLesson,
  saveStudentLessonProgress,
  submitStudentCourseAttestation,
} from "../api/onlineStudentApi";
import { InlineNotebookLessonPractice } from "../components/course/InlineNotebookLessonPractice";
import { LessonCodePractice } from "../components/course/LessonCodePractice";
import {
  formatScheduleValue,
  isDirectVideoUrl,
  renderLessonMarkdownBlocks,
  resolveVideoEmbedUrl,
} from "../components/course/courseDocumentUtils";
import { useAuth } from "../context/AuthContext";
import type {
  CourseLessonPlanItem,
  CourseLessonSectionItem,
  InteractiveLessonStep,
  StudentLessonAiAskResponse,
  StudentLessonDetailResponse,
} from "../types";
import "./LessonWorkspacePage.css";

type QuizResult = "correct" | "wrong";

const aiQuickPrompts = [
  {
    label: "Explain simply",
    promptType: "simple_summary",
    question: "Explain this lesson step in simple words.",
  },
  {
    label: "Key takeaways",
    promptType: "key_takeaways",
    question: "Give me the key takeaways from this lesson step.",
  },
  {
    label: "Main risks",
    promptType: "risks",
    question: "What mistakes should I avoid in this lesson step?",
  },
] as const;

const storageKeyOf = (lessonId: number) => `learning-hub:learner-lesson:${lessonId}`;

const findLessonItemById = (lesson: CourseLessonPlanItem, itemId?: number | null): CourseLessonSectionItem | null => {
  if (!itemId) return null;
  for (const section of lesson.sections) {
    const match = section.items.find((item) => item.id === itemId);
    if (match) {
      return match;
    }
  }
  return null;
};

const uniqueStepIds = (stepIds: string[], allowedStepIds: string[]) => {
  const allowedSet = new Set(allowedStepIds);
  return stepIds.filter((stepId, index) => allowedSet.has(stepId) && stepIds.indexOf(stepId) === index);
};

const mergeStepIds = (leftStepIds: string[], rightStepIds: string[], allowedStepIds: string[]) => {
  const requestedStepIds = new Set([...leftStepIds, ...rightStepIds]);
  return allowedStepIds.filter((stepId) => requestedStepIds.has(stepId));
};

const buildLoginRedirect = (pathname: string, search: string) =>
  `/login?next=${encodeURIComponent(`${pathname}${search}`)}`;

const completionLabelOf = (step: InteractiveLessonStep) => {
  if (step.kind === "video") return "Mark video as reviewed";
  if (step.kind === "practice") return "Mark practice as complete";
  if (step.kind === "summary") return "Finish lesson";
  return "Mark step complete";
};

const extractErrorDetail = (error: unknown, fallback: string) => {
  if (isAxiosError(error) && typeof error.response?.data?.detail === "string") {
    return error.response.data.detail;
  }
  return fallback;
};

const resolveQuizQuestions = (step: InteractiveLessonStep) => {
  if (!step.quiz) return [];
  if (step.quiz.questions && step.quiz.questions.length > 0) {
    return step.quiz.questions;
  }
  return [
    {
      id: `${step.id}-question`,
      prompt: step.quiz.prompt,
      options: step.quiz.options,
      successMessage: step.quiz.successMessage,
      errorMessage: step.quiz.errorMessage,
      explanationMarkdown: step.quiz.explanationMarkdown,
    },
  ];
};

const preferredCourseTitle = (payload: StudentLessonDetailResponse | null, preferredLanguage?: string) => {
  if (!payload) return "";
  if (preferredLanguage === "de") {
    return payload.course.titleDe || payload.course.titleEn;
  }
  return payload.course.titleEn || payload.course.titleDe;
};

export const LessonWorkspacePage = () => {
  const { lessonId = "" } = useParams();
  const location = useLocation();
  const { isAuthenticated, logout, profile } = useAuth();
  const normalizedLessonId = Number(lessonId);
  const dashboardHref = useHref("/dashboard");

  const [payload, setPayload] = useState<StudentLessonDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeStepId, setActiveStepId] = useState("");
  const [completedStepIds, setCompletedStepIds] = useState<string[]>([]);
  const [quizSelections, setQuizSelections] = useState<Record<string, Record<string, string>>>({});
  const [quizResults, setQuizResults] = useState<Record<string, Record<string, QuizResult>>>({});
  const [aiQuestion, setAiQuestion] = useState("");
  const [aiResponse, setAiResponse] = useState<StudentLessonAiAskResponse | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState("");
  const [completion, setCompletion] = useState<StudentLessonDetailResponse["completion"] | null>(null);
  const [attestationName, setAttestationName] = useState("");
  const [attestationBusy, setAttestationBusy] = useState(false);
  const [attestationError, setAttestationError] = useState("");
  const shellRef = useRef<HTMLDivElement | null>(null);
  const pendingStepScrollRef = useRef(false);
  const progressInitializedRef = useRef(false);
  const lastSyncedProgressRef = useRef("");

  useEffect(() => {
    if (!isAuthenticated || !Number.isFinite(normalizedLessonId) || normalizedLessonId <= 0) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    const loadLesson = async () => {
      setLoading(true);
      setError("");
      try {
        const response = await fetchStudentLesson(normalizedLessonId);
        if (cancelled) return;
        setPayload(response);
        setCompletion(response.completion);
      } catch (loadError) {
        if (isAxiosError(loadError) && loadError.response?.status === 401) {
          logout();
          return;
        }
        if (cancelled) return;
        setError(extractErrorDetail(loadError, "Failed to load the lesson workspace."));
        setPayload(null);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadLesson();

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, logout, normalizedLessonId]);

  const lesson = payload?.lesson ?? null;
  const interactiveLesson = lesson?.interactiveLesson ?? null;
  const steps = interactiveLesson?.steps ?? [];
  const stepIds = useMemo(() => steps.map((step) => step.id), [steps]);
  const stepSignature = useMemo(() => stepIds.join("|"), [stepIds]);

  useEffect(() => {
    if (!lesson || typeof window === "undefined" || stepIds.length === 0) {
      progressInitializedRef.current = false;
      lastSyncedProgressRef.current = "";
      setActiveStepId("");
      setCompletedStepIds([]);
      setQuizSelections({});
      setQuizResults({});
      return;
    }

    const serverProgress = lesson.progress;
    const serverCompletedStepIds = uniqueStepIds(serverProgress?.completedStepIds ?? [], stepIds);
    let nextActiveStepId =
      (serverProgress?.activeStepId && stepIds.includes(serverProgress.activeStepId) ? serverProgress.activeStepId : "")
      || stepIds[0];
    let nextCompletedStepIds = serverCompletedStepIds;

    const rawState = window.localStorage.getItem(storageKeyOf(lesson.id));
    if (rawState) {
      try {
        const parsed = JSON.parse(rawState) as {
          activeStepId?: string;
          completedStepIds?: string[];
        };
        const localCompletedStepIds = uniqueStepIds(parsed.completedStepIds ?? [], stepIds);
        const serverHasNewerProgress = serverCompletedStepIds.some((stepId) => !localCompletedStepIds.includes(stepId));
        nextCompletedStepIds = mergeStepIds(serverCompletedStepIds, localCompletedStepIds, stepIds);
        if (!serverHasNewerProgress && parsed.activeStepId && stepIds.includes(parsed.activeStepId)) {
          nextActiveStepId = parsed.activeStepId;
        } else {
          nextActiveStepId =
            (serverProgress?.activeStepId && stepIds.includes(serverProgress.activeStepId) ? serverProgress.activeStepId : "")
            || stepIds.find((stepId) => !nextCompletedStepIds.includes(stepId))
            || stepIds[0];
        }
      } catch {
        nextActiveStepId =
          (serverProgress?.activeStepId && stepIds.includes(serverProgress.activeStepId) ? serverProgress.activeStepId : "")
          || stepIds[0];
        nextCompletedStepIds = serverCompletedStepIds;
      }
    }

    lastSyncedProgressRef.current = JSON.stringify({
      activeStepId: serverProgress?.activeStepId ?? "",
      completedStepIds: serverCompletedStepIds,
    });
    progressInitializedRef.current = true;
    setActiveStepId(nextActiveStepId);
    setCompletedStepIds(nextCompletedStepIds);
    setQuizSelections({});
    setQuizResults({});
    setAiQuestion("");
    setAiResponse(null);
    setAiError("");
    setAttestationError("");
  }, [lesson, stepIds, stepSignature]);

  useEffect(() => {
    if (!payload) return;
    setCompletion(payload.completion);
  }, [payload]);

  useEffect(() => {
    const defaultName = [profile?.first_name, profile?.last_name].map((value) => String(value ?? "").trim()).filter(Boolean).join(" ");
    setAttestationName(defaultName || profile?.email || "");
  }, [profile?.email, profile?.first_name, profile?.last_name]);

  useEffect(() => {
    if (!lesson || typeof window === "undefined" || stepIds.length === 0 || !activeStepId) {
      return;
    }

    window.localStorage.setItem(
      storageKeyOf(lesson.id),
      JSON.stringify({
        activeStepId,
        completedStepIds,
      }),
    );
  }, [activeStepId, completedStepIds, lesson, stepIds.length]);

  useEffect(() => {
    if (!lesson || !activeStepId || stepIds.length === 0 || !progressInitializedRef.current) {
      return;
    }
    const snapshot = JSON.stringify({
      activeStepId,
      completedStepIds,
    });
    if (snapshot === lastSyncedProgressRef.current) {
      return;
    }

    let cancelled = false;
    const syncProgress = async () => {
      try {
        const response = await saveStudentLessonProgress(lesson.id, {
          activeStepId,
          completedStepIds,
        });
        if (cancelled) return;
        lastSyncedProgressRef.current = snapshot;
        setCompletion(response.completion);
      } catch {
        // Keep the local lesson flow responsive; dashboard reload will retry.
      }
    };

    void syncProgress();
    return () => {
      cancelled = true;
    };
  }, [activeStepId, completedStepIds, lesson, stepIds]);

  useEffect(() => {
    setAiResponse(null);
    setAiError("");
  }, [activeStepId]);

  useEffect(() => {
    if (!pendingStepScrollRef.current || !activeStepId) {
      return;
    }
    pendingStepScrollRef.current = false;
    window.requestAnimationFrame(() => {
      const shellTop = shellRef.current?.getBoundingClientRect().top ?? 0;
      const targetTop = Math.max(window.scrollY + shellTop - 20, 0);
      window.scrollTo({ top: targetTop, behavior: "smooth" });
    });
  }, [activeStepId]);

  const activeStep = steps.find((step) => step.id === activeStepId) ?? steps[0] ?? null;
  const activePracticeItem = activeStep && lesson ? findLessonItemById(lesson, activeStep.sourceItemId) : null;
  const showSidebarAiAssistant = !(activeStep?.kind === "practice" && activePracticeItem);
  const progressPercent = steps.length ? Math.round((completedStepIds.length / steps.length) * 100) : 0;
  const activeStepIndex = steps.findIndex((step) => step.id === activeStep.id);
  const courseTitle = preferredCourseTitle(payload, profile?.preferred_language);
  const sessionSchedule = lesson?.startsAt
    ? formatScheduleValue(lesson.startsAt, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
    : "";
  const resetProgressLabel = progressPercent >= 100 ? "Repeat lesson" : "Reset progress";

  const markStepComplete = (stepId: string) => {
    const nextCompletedStepIds = completedStepIds.includes(stepId)
      ? completedStepIds
      : [...completedStepIds, stepId];
    setCompletedStepIds(nextCompletedStepIds);

    const currentIndex = stepIds.indexOf(stepId);
    const nextStepId =
      stepIds.slice(Math.max(currentIndex + 1, 0)).find((candidate) => !nextCompletedStepIds.includes(candidate))
      || stepIds.find((candidate) => !nextCompletedStepIds.includes(candidate))
      || stepId;
    pendingStepScrollRef.current = true;
    setActiveStepId(nextStepId);
  };

  const handleResetLesson = () => {
    if (!lesson || stepIds.length === 0 || typeof window === "undefined") {
      return;
    }

    window.localStorage.removeItem(storageKeyOf(lesson.id));
    setActiveStepId(stepIds[0] ?? "");
    setCompletedStepIds([]);
    setQuizSelections({});
    setQuizResults({});
    setAiQuestion("");
    setAiResponse(null);
    setAiError("");
    setAttestationError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleSubmitAttestation = async () => {
    if (!completion || !payload || !attestationName.trim()) {
      return;
    }
    setAttestationBusy(true);
    setAttestationError("");
    try {
      const response = await submitStudentCourseAttestation(payload.enrollmentId, {
        fullName: attestationName.trim(),
        agreed: true,
      });
      setCompletion(response.completion);
    } catch (requestError) {
      setAttestationError(extractErrorDetail(requestError, "Failed to submit attestation."));
    } finally {
      setAttestationBusy(false);
    }
  };

  const handleQuizCheck = (step: InteractiveLessonStep) => {
    if (!step.quiz) return;
    const questions = resolveQuizQuestions(step);
    const stepSelections = quizSelections[step.id] ?? {};
    if (questions.some((question) => !stepSelections[question.id])) {
      return;
    }

    const nextResults = questions.reduce<Record<string, QuizResult>>((accumulator, question) => {
      const selectedOptionId = stepSelections[question.id];
      const matchedOption = question.options.find((option) => option.id === selectedOptionId);
      accumulator[question.id] = matchedOption?.isCorrect ? "correct" : "wrong";
      return accumulator;
    }, {});

    setQuizResults((current) => ({ ...current, [step.id]: nextResults }));
    if (Object.values(nextResults).every((value) => value === "correct")) {
      markStepComplete(step.id);
    }
  };

  const handleAskAi = async (question: string, promptType = "ask") => {
    const normalizedQuestion = question.trim();
    if (!normalizedQuestion || !activeStep) {
      return;
    }

    setAiBusy(true);
    setAiError("");
    try {
      const response = await askStudentLessonAi(normalizedLessonId, {
        question: normalizedQuestion,
        stepId: activeStep.id,
        promptType,
      });
      setAiQuestion(normalizedQuestion);
      setAiResponse(response);
    } catch (requestError) {
      setAiError(extractErrorDetail(requestError, "AI assistant is temporarily unavailable."));
    } finally {
      setAiBusy(false);
    }
  };

  if (!isAuthenticated) {
    return <Navigate to={buildLoginRedirect(location.pathname, location.search)} replace />;
  }

  if (!Number.isFinite(normalizedLessonId) || normalizedLessonId <= 0) {
    return <main className="lesson-workspace lesson-workspace--state">Invalid lesson identifier.</main>;
  }

  if (loading) {
    return <main className="lesson-workspace lesson-workspace--state">Preparing lesson workspace...</main>;
  }

  if (!payload || !lesson || !interactiveLesson || steps.length === 0 || !activeStep) {
    return <main className="lesson-workspace lesson-workspace--state">{error || "Lesson data is not available."}</main>;
  }

  return (
    <>
      <div className="lesson-workspace__backdrop" aria-hidden="true">
        <div className="lesson-workspace__orb lesson-workspace__orb--left" />
        <div className="lesson-workspace__orb lesson-workspace__orb--right" />
        <div className="lesson-workspace__grid" />
      </div>

      <main className="lesson-workspace">
        <div ref={shellRef} className="lesson-workspace__shell">
          <a href={dashboardHref} className="lesson-workspace__back-link">
            Back to student workspace
          </a>

          <header className="lesson-workspace__hero">
            <div className="lesson-workspace__hero-top">
              <div>
                <div className="lesson-workspace__eyebrow">
                  {courseTitle || "Course"} / {payload.module.title || "Module"}
                </div>
                <h1>{lesson.title}</h1>
                <p className="lesson-workspace__hero-copy">
                  {lesson.description || "Structured lesson flow with theory, video, quiz, practice, and wrap-up."}
                </p>
              </div>
              <div className="lesson-workspace__hero-badge">
                <span>{payload.cohort.groupCode}</span>
                <strong>Student lesson</strong>
              </div>
            </div>

            <div className="lesson-workspace__hero-bottom">
              <div className="lesson-workspace__hero-stats">
                <article className="lesson-workspace__stat-card">
                  <span>Estimated time</span>
                  <strong>{interactiveLesson.estimatedMinutes} min</strong>
                </article>
                <article className="lesson-workspace__stat-card">
                  <span>Format</span>
                  <strong>Interactive lesson</strong>
                </article>
                <article className="lesson-workspace__stat-card">
                  <span>Schedule</span>
                  <strong>{sessionSchedule || "Self-paced"}</strong>
                </article>
              </div>

              <div className="lesson-workspace__hero-progress">
                <div className="lesson-workspace__hero-progress-head">
                  <button type="button" className="lesson-workspace__progress-reset" onClick={handleResetLesson}>
                    {resetProgressLabel}
                  </button>
                </div>
                <div className="lesson-workspace__progress-line">
                  <span>Lesson progress</span>
                  <strong>{progressPercent}%</strong>
                </div>
                <div className="lesson-workspace__progress-track" aria-hidden="true">
                  <div className="lesson-workspace__progress-fill" style={{ width: `${progressPercent}%` }} />
                </div>
              </div>
            </div>
          </header>

          <nav className="lesson-workspace__steps" aria-label="Lesson steps">
            {steps.map((step, index) => {
              const isActive = step.id === activeStep.id;
              const isComplete = completedStepIds.includes(step.id);
              const isConnectorActive = isComplete || activeStepIndex > index;
              return [
                <button
                  key={step.id}
                  type="button"
                  className={`lesson-workspace__step-chip ${isActive ? "is-active" : ""} ${isComplete ? "is-complete" : ""}`}
                  onClick={() => setActiveStepId(step.id)}
                >
                  <span className="lesson-workspace__step-index">{index + 1}</span>
                  <span className="lesson-workspace__step-copy">
                    <strong>{String(step.eyebrow || step.kind).toUpperCase()}</strong>
                  </span>
                </button>,
                index < steps.length - 1 ? (
                  <span
                    key={`${step.id}_connector`}
                    className={`lesson-workspace__step-connector ${isConnectorActive ? "is-active" : ""}`}
                    aria-hidden="true"
                  />
                ) : null,
              ];
            })}
          </nav>

          <div className="lesson-workspace__layout">
            <section className="lesson-workspace__lesson-card">
              <div className="lesson-workspace__lesson-card-head">
                <div>
                  <div className="lesson-workspace__eyebrow">{activeStep.eyebrow}</div>
                  <div className="lesson-workspace__active-line">
                    <h2>{activeStep.title}</h2>
                    <span className={`lesson-workspace__status-pill ${completedStepIds.includes(activeStep.id) ? "is-complete" : ""}`}>
                      {completedStepIds.includes(activeStep.id) ? "Completed" : "In progress"}
                    </span>
                  </div>
                  <p className="lesson-workspace__step-description">{activeStep.description}</p>
                </div>
              </div>

              {(activeStep.kind === "theory" || activeStep.kind === "summary") && activeStep.contentMarkdown ? (
                <div className="lesson-workspace__content-stack">
                  <div className="lesson-workspace__content-body">
                    {renderLessonMarkdownBlocks(activeStep.contentMarkdown, "lesson-workspace__markdown")}
                  </div>
                  <div className="lesson-workspace__action-row">
                    <button
                      type="button"
                      className="lesson-workspace__primary-button"
                      onClick={() => markStepComplete(activeStep.id)}
                      disabled={completedStepIds.includes(activeStep.id)}
                    >
                      {completedStepIds.includes(activeStep.id) ? "Completed" : completionLabelOf(activeStep)}
                    </button>
                  </div>
                </div>
              ) : null}

              {activeStep.kind === "video" ? (
                <div className="lesson-workspace__content-stack">
                  {activeStep.contentMarkdown ? (
                    <div className="lesson-workspace__content-body">
                      {renderLessonMarkdownBlocks(activeStep.contentMarkdown, "lesson-workspace__markdown")}
                    </div>
                  ) : null}

                  {activeStep.videoUrl ? (
                    isDirectVideoUrl(activeStep.videoUrl) ? (
                      <video className="lesson-workspace__video" controls preload="metadata" src={activeStep.videoUrl} />
                    ) : (
                      <iframe
                        className="lesson-workspace__video-frame"
                        src={resolveVideoEmbedUrl(activeStep.videoUrl)}
                        title={activeStep.title}
                        loading="lazy"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowFullScreen
                      />
                    )
                  ) : (
                    <p className="lesson-workspace__inline-note">Video is not attached to this lesson step yet.</p>
                  )}

                  <div className="lesson-workspace__action-row">
                    <button
                      type="button"
                      className="lesson-workspace__primary-button"
                      onClick={() => markStepComplete(activeStep.id)}
                      disabled={completedStepIds.includes(activeStep.id)}
                    >
                      {completedStepIds.includes(activeStep.id) ? "Completed" : completionLabelOf(activeStep)}
                    </button>
                  </div>
                </div>
              ) : null}

              {activeStep.kind === "quiz" && activeStep.quiz ? (
                <div className="lesson-workspace__content-stack">
                  {activeStep.contentMarkdown ? (
                    <div className="lesson-workspace__content-body">
                      {renderLessonMarkdownBlocks(activeStep.contentMarkdown, "lesson-workspace__markdown")}
                    </div>
                  ) : null}

                  <div className="lesson-workspace__quiz-stack">
                    {resolveQuizQuestions(activeStep).map((question, questionIndex) => {
                      const stepSelections = quizSelections[activeStep.id] ?? {};
                      const stepResults = quizResults[activeStep.id] ?? {};
                      return (
                        <article key={question.id} className="lesson-workspace__quiz-card">
                          <div className="lesson-workspace__quiz-card-head">
                            <span className="lesson-workspace__quiz-card-index">{questionIndex + 1}</span>
                            <strong className="lesson-workspace__quiz-question">{question.prompt}</strong>
                          </div>
                          <div className="lesson-workspace__quiz-list">
                            {question.options.map((option, optionIndex) => {
                              const isSelected = stepSelections[question.id] === option.id;
                              const result = stepResults[question.id];
                              const isCorrect = result === "correct" && option.isCorrect;
                              const isWrong = result === "wrong" && isSelected && !option.isCorrect;
                              const optionLabel = String.fromCharCode(65 + optionIndex);

                              return (
                                <button
                                  key={option.id}
                                  type="button"
                                  aria-pressed={isSelected}
                                  className={`lesson-workspace__quiz-option ${isSelected ? "is-selected" : ""} ${isCorrect ? "is-correct" : ""} ${isWrong ? "is-wrong" : ""}`}
                                  onClick={() => {
                                    setQuizSelections((current) => ({
                                      ...current,
                                      [activeStep.id]: {
                                        ...(current[activeStep.id] ?? {}),
                                        [question.id]: option.id,
                                      },
                                    }));
                                    setQuizResults((current) => ({
                                      ...current,
                                      [activeStep.id]: Object.fromEntries(
                                        Object.entries(current[activeStep.id] ?? {}).filter(([key]) => key !== question.id),
                                      ),
                                    }));
                                  }}
                                >
                                  <span className="lesson-workspace__quiz-index">{optionLabel}</span>
                                  <span>{option.label}</span>
                                </button>
                              );
                            })}
                          </div>

                          {stepResults[question.id] ? (
                            <div className={`lesson-workspace__feedback-card ${stepResults[question.id] === "correct" ? "is-success" : "is-warning"}`}>
                              <strong>
                                {stepResults[question.id] === "correct" ? question.successMessage : question.errorMessage}
                              </strong>
                              {question.explanationMarkdown ? (
                                <div className="lesson-workspace__feedback-copy">
                                  {renderLessonMarkdownBlocks(question.explanationMarkdown, "lesson-workspace__markdown")}
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                        </article>
                      );
                    })}
                  </div>

                  <div className="lesson-workspace__action-row">
                    <button
                      type="button"
                      className="lesson-workspace__primary-button"
                      onClick={() => handleQuizCheck(activeStep)}
                      disabled={
                        completedStepIds.includes(activeStep.id)
                        || resolveQuizQuestions(activeStep).some((question) => !(quizSelections[activeStep.id] ?? {})[question.id])
                      }
                    >
                      {completedStepIds.includes(activeStep.id) ? "Quiz completed" : "Check answers"}
                    </button>
                  </div>
                </div>
              ) : null}

              {activeStep.kind === "practice" ? (
                <div className="lesson-workspace__content-stack">
                  {activeStep.contentMarkdown ? (
                    <div className="lesson-workspace__content-body">
                      {renderLessonMarkdownBlocks(activeStep.contentMarkdown, "lesson-workspace__markdown")}
                    </div>
                  ) : null}

                  <div className="lesson-workspace__action-row">
                    <button
                      type="button"
                      className="lesson-workspace__primary-button"
                      onClick={() => markStepComplete(activeStep.id)}
                      disabled={completedStepIds.includes(activeStep.id)}
                    >
                      {completedStepIds.includes(activeStep.id) ? "Completed" : completionLabelOf(activeStep)}
                    </button>
                  </div>

                  {activeStep.practiceMode === "code_editor" && activeStep.starterCode ? (
                    <LessonCodePractice
                      key={activeStep.id}
                      lessonId={normalizedLessonId}
                      step={activeStep}
                      completed={completedStepIds.includes(activeStep.id)}
                      onPassed={() => markStepComplete(activeStep.id)}
                    />
                  ) : activePracticeItem ? (
                    <div className="lesson-workspace__practice-shell">
                      <InlineNotebookLessonPractice item={activePracticeItem} />
                    </div>
                  ) : (
                    <p className="lesson-workspace__inline-note">
                      Notebook runtime is not linked to this lesson step yet.
                    </p>
                  )}
                </div>
              ) : null}

              {activeStep.resourceLinks.length > 0 ? (
                <section className="lesson-workspace__step-resources">
                  <div className="lesson-workspace__eyebrow">Step resources</div>
                  <div className="lesson-workspace__resource-list">
                    {activeStep.resourceLinks.map((resource) => (
                      <a key={resource.id} href={resource.url} target="_blank" rel="noreferrer" className="lesson-workspace__resource-link">
                        <strong>{resource.label}</strong>
                        <span>{resource.kind}</span>
                      </a>
                    ))}
                  </div>
                </section>
              ) : null}
            </section>

            <aside className="lesson-workspace__sidebar">
              <section className="lesson-workspace__sidebar-card">
                <div className="lesson-workspace__eyebrow">Progress</div>
                <h3>{progressPercent}% complete</h3>
                <p>
                  {completedStepIds.length} of {steps.length} steps completed
                </p>
                <div className="lesson-workspace__progress-track" aria-hidden="true">
                  <div className="lesson-workspace__progress-fill" style={{ width: `${progressPercent}%` }} />
                </div>
              </section>

              {completion ? (
                <section className="lesson-workspace__sidebar-card">
                  <div className="lesson-workspace__eyebrow">Completion evidence</div>
                  <h3>{completion.statusLabel}</h3>
                  <p>
                    {completion.progressPercent}% course completion · {Math.round(completion.attendancePercent)}% attendance
                  </p>

                  <ul className="lesson-workspace__outcomes">
                    <li>
                      Rule: {completion.rule.requiredCompletionPercent}% completion / {completion.rule.requiredAttendancePercent}% attendance
                    </li>
                    <li>{completion.rule.requiresAttestation ? "Attestation required before evidence is issued." : "Attestation is optional for this course."}</li>
                  </ul>

                  {completion.evidence ? (
                    <div className="lesson-workspace__evidence-panel">
                      <strong>Evidence issued</strong>
                      <span>Code: {completion.evidence.evidenceCode.slice(0, 8).toUpperCase()}</span>
                      <span>Issued: {formatScheduleValue(completion.evidence.issuedAt, { day: "2-digit", month: "short", year: "numeric" })}</span>
                    </div>
                  ) : null}

                  {completion.status === "ready_for_attestation" ? (
                    <div className="lesson-workspace__attestation-form">
                      <label className="lesson-workspace__attestation-label">
                        Full name
                        <input
                          className="lesson-workspace__attestation-input"
                          value={attestationName}
                          onChange={(event) => setAttestationName(event.currentTarget.value)}
                          placeholder="Type your full name"
                        />
                      </label>
                      <button
                        type="button"
                        onClick={() => void handleSubmitAttestation()}
                        disabled={attestationBusy || !attestationName.trim()}
                        className="lesson-workspace__primary-button lesson-workspace__primary-button--wide"
                      >
                        {attestationBusy ? "Submitting..." : "Confirm completion"}
                      </button>
                      {attestationError ? <p className="lesson-workspace__inline-error">{attestationError}</p> : null}
                    </div>
                  ) : null}
                </section>
              ) : null}

              {showSidebarAiAssistant ? (
                <section className="lesson-workspace__sidebar-card">
                  <div className="lesson-workspace__eyebrow">AI assistant</div>
                  <h3>Ask about the current step</h3>
                  <p>Uses the same academy AI provider configured for the training stack.</p>

                  <div className="lesson-workspace__quick-prompts">
                    {aiQuickPrompts.map((prompt) => (
                      <button
                        key={prompt.label}
                        type="button"
                        className="lesson-workspace__secondary-button"
                        onClick={() => void handleAskAi(prompt.question, prompt.promptType)}
                        disabled={aiBusy}
                      >
                        {prompt.label}
                      </button>
                    ))}
                  </div>

                  <textarea
                    value={aiQuestion}
                    onChange={(event) => setAiQuestion(event.target.value)}
                    placeholder="Explain this step in simple words"
                    className="lesson-workspace__sidebar-input"
                  />

                  <button
                    type="button"
                    onClick={() => void handleAskAi(aiQuestion)}
                    disabled={aiBusy || !aiQuestion.trim()}
                    className="lesson-workspace__primary-button lesson-workspace__primary-button--wide"
                  >
                    {aiBusy ? "Asking..." : "Ask AI"}
                  </button>

                  {aiError ? <p className="lesson-workspace__inline-error">{aiError}</p> : null}

                  {aiResponse ? (
                    <div className="lesson-workspace__feedback-card lesson-workspace__feedback-card--ai">
                      <div className="lesson-workspace__feedback-head">
                        <strong>Answer</strong>
                        <span>
                          {aiResponse.provider} · {aiResponse.model}
                        </span>
                      </div>
                      <p>{aiResponse.answer}</p>
                      {aiResponse.followUpPrompts.length > 0 ? (
                        <div className="lesson-workspace__follow-up-list">
                          {aiResponse.followUpPrompts.map((prompt) => (
                            <button
                              key={prompt}
                              type="button"
                              className="lesson-workspace__follow-up-chip"
                              onClick={() => void handleAskAi(prompt)}
                              disabled={aiBusy}
                            >
                              {prompt}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </section>
              ) : null}

              <section className="lesson-workspace__sidebar-card">
                <div className="lesson-workspace__eyebrow">Resources</div>
                <h3>Lesson assets</h3>
                {interactiveLesson.outcomes.length > 0 ? (
                  <ul className="lesson-workspace__outcomes">
                    {interactiveLesson.outcomes.map((outcome) => (
                      <li key={outcome}>{outcome}</li>
                    ))}
                  </ul>
                ) : (
                  <p>No lesson outcomes are attached yet.</p>
                )}

                {interactiveLesson.resources.length > 0 ? (
                  <div className="lesson-workspace__resource-list lesson-workspace__resource-list--sidebar">
                    {interactiveLesson.resources.map((resource) => (
                      <a key={resource.id} href={resource.url} target="_blank" rel="noreferrer" className="lesson-workspace__resource-link">
                        <strong>{resource.label}</strong>
                        <span>{resource.kind}</span>
                      </a>
                    ))}
                  </div>
                ) : (
                  <p>No external lesson resources are attached yet.</p>
                )}
              </section>
            </aside>
          </div>
        </div>
      </main>
    </>
  );
};

export default LessonWorkspacePage;
