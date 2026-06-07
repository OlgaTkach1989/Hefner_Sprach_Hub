import { useEffect, useMemo, useState } from "react";
import { isAxiosError } from "axios";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { fetchLearningWorkspace, fetchStudentDashboard } from "../api/onlineStudentApi";
import { useAuth } from "../context/AuthContext";
import type {
  DashboardResponse,
  LearningWorkspaceFormulaStep,
  LearningWorkspaceModule,
  LearningWorkspacePayload,
  LearningWorkspaceProgram,
  LearningWorkspaceScenarioStep,
  LearningWorkspaceStep,
  LearningWorkspaceVideoStep,
} from "../types";
import { TrainingHubSection } from "../training/TrainingHubSection";
import { buildFallbackLearningWorkspace, deriveFallbackSeed } from "./mockWorkspace";
import "./LearningWorkspacePage.css";

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
};

const formatPercent = (value?: number | null) => (value === null || value === undefined ? "-" : `${value}%`);

const renderMarkdownLines = (value?: string | null) => {
  if (!value) return null;
  return value
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => (
      <p key={`${line}-${index}`}>{line}</p>
    ));
};

const getStepBadgeLabel = (status: LearningWorkspaceStep["status"]) => {
  if (status === "completed") return "Completed";
  if (status === "in_progress") return "In progress";
  if (status === "available") return "Available";
  return "Locked";
};

const getStepKindLabel = (kind: LearningWorkspaceStep["kind"]) => {
  if (kind === "video") return "Video";
  if (kind === "formula") return "Formula";
  if (kind === "scenario") return "Scenario";
  if (kind === "notebook") return "Notebook";
  return "AI quiz";
};

const getModuleProgressLabel = (module: LearningWorkspaceModule) =>
  `${module.progressPercent}% · ${module.stepCount} steps`;

const getProgramContextLabel = (program: LearningWorkspaceProgram) =>
  `${program.modules.length} modules · ${program.progressPercent}% complete`;

const renderStepContent = (step: LearningWorkspaceStep) => {
  if (step.kind === "video") {
    const videoStep = step as LearningWorkspaceVideoStep;
    return (
      <div className="learning-workspace__step-body">
        <div className="learning-workspace__media-shell">
          <video className="learning-workspace__video" controls playsInline preload="metadata" poster={videoStep.posterUrl ?? undefined}>
            <source src={videoStep.videoUrl} />
            Your browser does not support the video element.
          </video>
        </div>
        <div className="learning-workspace__note-grid">
          <article className="learning-workspace__note-card">
            <span>Duration</span>
            <strong>{step.estimatedMinutes ?? "-" } min</strong>
          </article>
          <article className="learning-workspace__note-card">
            <span>Resources</span>
            <strong>{step.resources.length}</strong>
          </article>
        </div>
        {renderMarkdownLines(videoStep.transcriptMarkdown)}
      </div>
    );
  }

  if (step.kind === "formula") {
    const formulaStep = step as LearningWorkspaceFormulaStep;
    return (
      <div className="learning-workspace__step-body">
        <article className="learning-workspace__formula-card">
          <p className="learning-workspace__formula-label">MathJax-ready formula</p>
          <pre className="learning-workspace__formula">{formulaStep.formula}</pre>
          {renderMarkdownLines(formulaStep.explanationMarkdown)}
        </article>
        {formulaStep.referenceMarkdown ? <article className="learning-workspace__callout">{renderMarkdownLines(formulaStep.referenceMarkdown)}</article> : null}
      </div>
    );
  }

  if (step.kind === "scenario") {
    const scenarioStep = step as LearningWorkspaceScenarioStep;
    return (
      <div className="learning-workspace__step-body">
        <article className="learning-workspace__scenario-card">
          <h3>Business context</h3>
          {renderMarkdownLines(scenarioStep.contextMarkdown)}
        </article>
        <article className="learning-workspace__scenario-card">
          <h3>Prompt</h3>
          {renderMarkdownLines(scenarioStep.promptMarkdown)}
        </article>
        <article className="learning-workspace__scenario-card">
          <h3>Expected outcome</h3>
          {renderMarkdownLines(scenarioStep.expectedOutcomeMarkdown)}
        </article>
        <article className="learning-workspace__scenario-card">
          <h3>Checklist</h3>
          <ul className="learning-workspace__checklist">
            {scenarioStep.checklist.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </div>
    );
  }

  if (step.kind === "notebook") {
    return (
      <div className="learning-workspace__step-body">
        <article className="learning-workspace__notebook-card">
          <h3>Notebook execution</h3>
          <p>{step.description}</p>
          <div className="learning-workspace__note-grid">
            <article className="learning-workspace__note-card">
              <span>Launch path</span>
              <strong>{step.launchPath}</strong>
            </article>
            <article className="learning-workspace__note-card">
              <span>Pass threshold</span>
              <strong>{step.passThresholdPercent}%</strong>
            </article>
            <article className="learning-workspace__note-card">
              <span>Attempts</span>
              <strong>{step.maxAttempts ?? "Unlimited"}</strong>
            </article>
            <article className="learning-workspace__note-card">
              <span>Notebook</span>
              <strong>{step.notebookPath}</strong>
            </article>
          </div>
          {step.guidanceMarkdown ? <div className="learning-workspace__callout">{renderMarkdownLines(step.guidanceMarkdown)}</div> : null}
        </article>
      </div>
    );
  }

  return (
    <div className="learning-workspace__step-body">
      <article className="learning-workspace__quiz-card">
        <h3>AI quiz checkpoint</h3>
        <p>{step.description}</p>
        <div className="learning-workspace__note-grid">
          <article className="learning-workspace__note-card">
            <span>Prompt type</span>
            <strong>{step.promptType}</strong>
          </article>
          <article className="learning-workspace__note-card">
            <span>Question count</span>
            <strong>{step.questionCount}</strong>
          </article>
          <article className="learning-workspace__note-card">
            <span>Training content</span>
            <strong>{step.contentSlug}</strong>
          </article>
        </div>
        {renderMarkdownLines(step.guidanceMarkdown)}
      </article>
    </div>
  );
};

export const LearningWorkspacePage = () => {
  const { programSlug = "poc" } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, logout } = useAuth();

  const [workspace, setWorkspace] = useState<LearningWorkspacePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedModuleSlug, setSelectedModuleSlug] = useState<string | null>(null);
  const [selectedStepSlug, setSelectedStepSlug] = useState<string | null>(null);
  const [dashboardSeed, setDashboardSeed] = useState<DashboardResponse | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadWorkspace = async () => {
      setLoading(true);
      setError("");

      try {
        const payload = await fetchLearningWorkspace(programSlug);
        if (cancelled) return;
        setWorkspace(payload);
        setDashboardSeed(null);
      } catch (error) {
        if (isAxiosError(error) && error.response?.status === 401) {
          logout();
          return;
        }

        try {
          const dashboard = await fetchStudentDashboard();
          if (cancelled) return;
          setDashboardSeed(dashboard);
          setWorkspace(buildFallbackLearningWorkspace(deriveFallbackSeed(dashboard), programSlug));
        } catch (fallbackError) {
          if (isAxiosError(fallbackError) && fallbackError.response?.status === 401) {
            logout();
            return;
          }

          if (cancelled) return;
          setDashboardSeed(null);
          setWorkspace(buildFallbackLearningWorkspace(deriveFallbackSeed(null), programSlug));
          setError("Loaded the local POC dataset because the backend workspace payload was unavailable.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadWorkspace();

    return () => {
      cancelled = true;
    };
  }, [logout, programSlug]);

  const currentProgram = useMemo(() => {
    if (!workspace) return null;
    return workspace.programs.find((program) => program.slug === programSlug)
      ?? workspace.programs.find((program) => program.slug === workspace.activeProgramSlug)
      ?? workspace.programs[0]
      ?? null;
  }, [programSlug, workspace]);

  useEffect(() => {
    if (!workspace || !currentProgram) return;

    if (currentProgram.slug !== programSlug) {
      navigate(`/learn/${currentProgram.slug}`, { replace: true });
      return;
    }

    setSelectedModuleSlug((current) => {
      if (current && currentProgram.modules.some((module) => module.slug === current)) {
        return current;
      }
      return currentProgram.modules[0]?.slug ?? null;
    });
  }, [currentProgram, navigate, programSlug, workspace]);

  const selectedModule = useMemo(() => {
    if (!currentProgram) return null;
    return currentProgram.modules.find((module) => module.slug === selectedModuleSlug)
      ?? currentProgram.modules[0]
      ?? null;
  }, [currentProgram, selectedModuleSlug]);

  useEffect(() => {
    if (!selectedModule) return;
    setSelectedStepSlug((current) => {
      if (current && selectedModule.steps.some((step) => step.slug === current)) {
        return current;
      }
      return selectedModule.steps[0]?.slug ?? null;
    });
  }, [selectedModule]);

  const selectedStep = useMemo(() => {
    if (!selectedModule) return null;
    return selectedModule.steps.find((step) => step.slug === selectedStepSlug)
      ?? selectedModule.steps[0]
      ?? null;
  }, [selectedModule, selectedStepSlug]);

  const currentStepIndex = useMemo(() => {
    if (!selectedModule || !selectedStep) return -1;
    return selectedModule.steps.findIndex((step) => step.slug === selectedStep.slug);
  }, [selectedModule, selectedStep]);

  const previousStep = currentStepIndex > 0 && selectedModule ? selectedModule.steps[currentStepIndex - 1] : null;
  const nextStep = selectedModule && currentStepIndex >= 0 && currentStepIndex < selectedModule.steps.length - 1
    ? selectedModule.steps[currentStepIndex + 1]
    : null;

  const canRenderHub = selectedStep?.kind === "notebook" || selectedStep?.kind === "ai_quiz";
  const preferredLanguage = workspace?.preferredLanguage ?? dashboardSeed?.profile.preferred_language ?? "en";

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (loading) {
    return <main className="learning-workspace learning-workspace--loading">Loading unified learning workspace...</main>;
  }

  if (!workspace || !currentProgram || !selectedModule || !selectedStep) {
    return <main className="learning-workspace learning-workspace--loading">{error || "No workspace data available."}</main>;
  }

  return (
    <main className="learning-workspace">
      <header className="learning-workspace__hero">
        <div className="learning-workspace__hero-copy">
          <p className="learning-workspace__eyebrow">Unified learning workspace</p>
          <h1>{currentProgram.title}</h1>
          <p className="learning-workspace__hero-subtitle">{currentProgram.subtitle}</p>
          <div className="learning-workspace__hero-metrics">
            <span>{getProgramContextLabel(currentProgram)}</span>
            <span>Next session: {formatDateTime(currentProgram.nextSessionAt)}</span>
            <span>Source: {workspace.source === "backend" ? "Backend payload" : "POC fallback"}</span>
          </div>
          {error ? <p className="learning-workspace__hero-warning">{error}</p> : null}
        </div>

        <div className="learning-workspace__hero-controls">
          {workspace.programs.map((program) => (
            <button
              key={program.slug}
              type="button"
              className={`learning-workspace__program-chip ${program.slug === currentProgram.slug ? "is-active" : ""}`}
              onClick={() => navigate(`/learn/${program.slug}`)}
            >
              <strong>{program.title}</strong>
              <span>{formatPercent(program.progressPercent)}</span>
            </button>
          ))}
        </div>
      </header>

      <div className="learning-workspace__shell">
        <aside className="learning-workspace__rail">
          <section className="learning-workspace__rail-card">
            <p className="learning-workspace__rail-label">Programs</p>
            <div className="learning-workspace__rail-list">
              {workspace.programs.map((program) => (
                <button
                  key={program.slug}
                  type="button"
                  className={`learning-workspace__program-card ${program.slug === currentProgram.slug ? "is-active" : ""}`}
                  onClick={() => navigate(`/learn/${program.slug}`)}
                >
                  <span>{program.title}</span>
                  <strong>{getProgramContextLabel(program)}</strong>
                  <small>{program.tags.join(" · ")}</small>
                </button>
              ))}
            </div>
          </section>

          <section className="learning-workspace__rail-card">
            <p className="learning-workspace__rail-label">Modules and steps</p>
            <div className="learning-workspace__module-list">
              {currentProgram.modules.map((module) => (
                <article key={module.slug} className={`learning-workspace__module-card ${module.slug === selectedModule.slug ? "is-active" : ""}`}>
                  <button
                    type="button"
                    className="learning-workspace__module-button"
                    onClick={() => {
                      setSelectedModuleSlug(module.slug);
                      setSelectedStepSlug(module.steps[0]?.slug ?? null);
                    }}
                  >
                    <span>{module.title}</span>
                    <strong>{getModuleProgressLabel(module)}</strong>
                    <small>{module.description}</small>
                  </button>
                  <div className="learning-workspace__step-list">
                    {module.steps.map((step) => (
                      <button
                        key={step.slug}
                        type="button"
                        className={`learning-workspace__step-link ${step.slug === selectedStep.slug ? "is-active" : ""}`}
                        onClick={() => {
                          setSelectedModuleSlug(module.slug);
                          setSelectedStepSlug(step.slug);
                        }}
                      >
                        <span>{step.title}</span>
                        <small>{getStepKindLabel(step.kind)} · {getStepBadgeLabel(step.status)}</small>
                      </button>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </section>
        </aside>

        <section className="learning-workspace__stage">
          <article className="learning-workspace__stage-card">
            <div className="learning-workspace__stage-header">
              <div>
                <p className="learning-workspace__rail-label">{selectedModule.title}</p>
                <h2>{selectedStep.title}</h2>
                <p className="learning-workspace__stage-subtitle">{selectedStep.description}</p>
              </div>
              <div className="learning-workspace__badge-stack">
                <span className={`learning-workspace__badge learning-workspace__badge--${selectedStep.kind}`}>{getStepKindLabel(selectedStep.kind)}</span>
                <span className={`learning-workspace__badge learning-workspace__badge--${selectedStep.status}`}>{getStepBadgeLabel(selectedStep.status)}</span>
                <span className="learning-workspace__badge learning-workspace__badge--muted">{selectedStep.estimatedMinutes ?? "-"} min</span>
              </div>
            </div>

            <div className="learning-workspace__stage-grid">
              <div className="learning-workspace__content-panel">
                {renderStepContent(selectedStep)}

                <div className="learning-workspace__resource-row">
                  {selectedStep.resources.map((resource) => (
                    <a key={`${selectedStep.slug}-${resource.label}`} href={resource.url} target="_blank" rel="noreferrer" className="learning-workspace__resource-chip">
                      {resource.label}
                    </a>
                  ))}
                </div>

                <div className="learning-workspace__navigation">
                  <button
                    type="button"
                    className="learning-workspace__nav-button"
                    onClick={() => previousStep && setSelectedStepSlug(previousStep.slug)}
                    disabled={!previousStep}
                  >
                    Previous step
                  </button>
                  <button
                    type="button"
                    className="learning-workspace__nav-button learning-workspace__nav-button--primary"
                    onClick={() => nextStep && setSelectedStepSlug(nextStep.slug)}
                    disabled={!nextStep}
                  >
                    Next step
                  </button>
                </div>

                {canRenderHub ? (
                  <section className="learning-workspace__hub-host">
                    <p className="learning-workspace__hub-label">Execution workspace</p>
                    <TrainingHubSection
                      key={selectedStep.contentSlug ?? selectedStep.slug}
                      preferredLanguage={preferredLanguage}
                      focusContentSlug={selectedStep.contentSlug ?? null}
                    />
                  </section>
                ) : null}
              </div>

              <aside className="learning-workspace__context-panel">
                <section className="learning-workspace__context-card">
                  <p className="learning-workspace__rail-label">Runtime preset</p>
                  <strong>{currentProgram.runtimePreset.name}</strong>
                  <span>{currentProgram.runtimePreset.runtimeImage}</span>
                  <p>{currentProgram.runtimePreset.description}</p>
                  <div className="learning-workspace__context-tags">
                    <span>{currentProgram.runtimePreset.allowNetwork ? "Network enabled" : "Network locked"}</span>
                    <span>{currentProgram.runtimePreset.allowGpu ? "GPU enabled" : "CPU only"}</span>
                    <span>Launch: {currentProgram.runtimePreset.launchPath}</span>
                  </div>
                  <div className="learning-workspace__context-tags">
                    {currentProgram.runtimePreset.internalPackages.map((pkg) => (
                      <span key={pkg}>{pkg}</span>
                    ))}
                  </div>
                </section>

                <section className="learning-workspace__context-card">
                  <p className="learning-workspace__rail-label">Certificate rule</p>
                  <strong>{currentProgram.certificateRule.title}</strong>
                  <p>{currentProgram.certificateRule.description}</p>
                  <div className="learning-workspace__context-tags">
                    <span>{currentProgram.certificateRule.requiredCompletionPercent}% completion</span>
                    <span>{currentProgram.certificateRule.requiredNotebookPassPercent}% notebook pass</span>
                    <span>{currentProgram.certificateRule.requiredAiQuizPassPercent}% AI quiz pass</span>
                    <span>{currentProgram.certificateRule.requiresAttendance ? "Attendance required" : "Attendance optional"}</span>
                  </div>
                </section>

                <section className="learning-workspace__context-card">
                  <p className="learning-workspace__rail-label">Owners and SLA</p>
                  <div className="learning-workspace__owner-list">
                    {currentProgram.owners.map((owner) => (
                      <article key={owner.role} className="learning-workspace__owner-card">
                        <strong>{owner.role.replace(/_/g, " ")}</strong>
                        <span>{owner.name}</span>
                        <small>{owner.email}</small>
                        <small>{owner.responseSlaHours}h SLA</small>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="learning-workspace__context-card">
                  <p className="learning-workspace__rail-label">Selected step</p>
                  <div className="learning-workspace__context-tags">
                    <span>{selectedStep.kind}</span>
                    <span>{selectedStep.status}</span>
                    <span>{selectedStep.contentSlug ?? "No content slug"}</span>
                  </div>
                  <p>{selectedStep.description}</p>
                </section>

                {workspace.supportUrl ? (
                  <section className="learning-workspace__context-card">
                    <p className="learning-workspace__rail-label">Support</p>
                    <a href={workspace.supportUrl} className="learning-workspace__support-link">
                      Contact support
                    </a>
                  </section>
                ) : null}
              </aside>
            </div>
          </article>
        </section>
      </div>
    </main>
  );
};
