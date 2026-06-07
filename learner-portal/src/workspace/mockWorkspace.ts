import type { DashboardResponse, LearningWorkspacePayload, LearningWorkspaceProgram, Locale } from "../types";

export interface WorkspaceFallbackSeed {
  preferredLanguage: Locale;
  learnerName: string;
  nextSessionAt?: string | null;
}

const sampleVideoUrl = "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4";

const makeStepId = (programSlug: string, moduleIndex: number, suffix: string) =>
  `${programSlug}-m${moduleIndex}-${suffix}`;

const makeResource = (label: string, url: string) => ({
  label,
  url,
  kind: "external" as const,
});

const buildRuntimePreset = (programSlug: string) => ({
  id: `${programSlug}-runtime`,
  name: "Python + Quant Toolkit",
  description: "Pinned image with internal packages and notebook launch policy.",
  runtimeImage: "registry.local/learning/python-quant:2026.03",
  launchPath: "/lab",
  packageSummary: ["numpy", "pandas", "scipy", "statsmodels", "matplotlib"],
  internalPackages: ["creditpy", "secprodpy"],
  allowNetwork: false,
  allowGpu: false,
});

const buildCertificateRule = (programSlug: string) => ({
  title: `${programSlug} completion rule`,
  description: "Complete the full path with lab and quiz evidence.",
  requiredCompletionPercent: 100,
  requiredNotebookPassPercent: 80,
  requiredAiQuizPassPercent: 80,
  requiresAttendance: true,
});

const buildOwners = (programSlug: string) => [
  { role: "course_owner" as const, name: `${programSlug} course owner`, email: "course-owner@example.com", responseSlaHours: 24 },
  { role: "knowledge_owner" as const, name: `${programSlug} knowledge owner`, email: "knowledge-owner@example.com", responseSlaHours: 12 },
  { role: "lab_owner" as const, name: `${programSlug} lab owner`, email: "lab-owner@example.com", responseSlaHours: 8 },
  { role: "instructor" as const, name: `${programSlug} instructor`, email: "instructor@example.com", responseSlaHours: 24 },
];

const buildModule = (
  programSlug: string,
  programTitle: string,
  moduleIndex: number,
  moduleTitle: string,
  moduleSummary: string,
  stepState: Array<"completed" | "available" | "in_progress" | "locked">,
) => {
  const moduleSlug = `${programSlug}-module-${moduleIndex}`;
  const stepNumber = (offset: number) => offset + 1;

  return {
    id: moduleSlug,
    slug: moduleSlug,
    title: moduleTitle,
    description: moduleSummary,
    sortOrder: moduleIndex,
    progressPercent: moduleIndex === 1 ? 78 : moduleIndex === 2 ? 52 : 33,
    stepCount: 6,
    steps: [
      {
        id: makeStepId(programSlug, moduleIndex, "video"),
        slug: makeStepId(programSlug, moduleIndex, "video"),
        kind: "video" as const,
        title: "Video briefing",
        description: `${programTitle} overview and the decision context for module ${stepNumber(moduleIndex - 1)}.`,
        sortOrder: 1,
        status: stepState[0],
        estimatedMinutes: 12,
        videoUrl: sampleVideoUrl,
        posterUrl: "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80",
        transcriptMarkdown: "Watch the briefing, then move to the formula and notebook steps.",
        resources: [makeResource("Module notes", "https://example.com/module-notes")],
      },
      {
        id: makeStepId(programSlug, moduleIndex, "formula"),
        slug: makeStepId(programSlug, moduleIndex, "formula"),
        kind: "formula" as const,
        title: "Formula checkpoint",
        description: "Key relationship used in the module calculation.",
        sortOrder: 2,
        status: stepState[1],
        estimatedMinutes: 8,
        formula: "Exposure = Gross position - Eligible collateral",
        explanationMarkdown: "Use the formula to normalize the portfolio view before running the lab.",
        referenceMarkdown: "This block is MathJax-ready and can be rendered as an equation panel.",
        resources: [makeResource("Reference sheet", "https://example.com/formula-sheet")],
      },
      {
        id: makeStepId(programSlug, moduleIndex, "notebook-a"),
        slug: makeStepId(programSlug, moduleIndex, "notebook-a"),
        kind: "notebook" as const,
        title: "Notebook lab A",
        description: "Open the exploratory notebook and inspect the baseline data.",
        sortOrder: 3,
        status: stepState[2],
        estimatedMinutes: 25,
        contentSlug: `${programSlug}-lab-${moduleIndex}-a`,
        notebookPath: `/labs/${programSlug}/module-${moduleIndex}/notebook-a.ipynb`,
        launchPath: "/lab",
        passThresholdPercent: 80,
        maxAttempts: 3,
        launchLabel: "Launch notebook",
        guidanceMarkdown: "Run the baseline cell, inspect outputs, then submit the artifact once the checks pass.",
        resources: [makeResource("Starter notebook", "https://example.com/starter-notebook")],
      },
      {
        id: makeStepId(programSlug, moduleIndex, "notebook-b"),
        slug: makeStepId(programSlug, moduleIndex, "notebook-b"),
        kind: "notebook" as const,
        title: "Notebook lab B",
        description: "Validate the result and compare against the expected curve.",
        sortOrder: 4,
        status: stepState[3],
        estimatedMinutes: 30,
        contentSlug: `${programSlug}-lab-${moduleIndex}-b`,
        notebookPath: `/labs/${programSlug}/module-${moduleIndex}/notebook-b.ipynb`,
        launchPath: "/lab",
        passThresholdPercent: 80,
        maxAttempts: 3,
        launchLabel: "Continue notebook",
        guidanceMarkdown: "Use this step to demonstrate reproducibility and final reporting.",
        resources: [makeResource("Validation notebook", "https://example.com/validation-notebook")],
      },
      {
        id: makeStepId(programSlug, moduleIndex, "scenario"),
        slug: makeStepId(programSlug, moduleIndex, "scenario"),
        kind: "scenario" as const,
        title: "Scenario decision",
        description: "Write the short decision note for the business reviewer.",
        sortOrder: 5,
        status: stepState[4],
        estimatedMinutes: 18,
        contextMarkdown: "A desk asks for a fast answer, but the underlying data is incomplete.",
        promptMarkdown: "State the decision, the assumptions, and the risk you would flag in the memo.",
        expectedOutcomeMarkdown: "A concise action plan with a defensible rationale and a follow-up list.",
        checklist: [
          "State the decision.",
          "List the assumptions.",
          "Call out the residual risk.",
          "Name the owner for follow-up.",
        ],
        resources: [makeResource("Decision memo template", "https://example.com/memo-template")],
      },
      {
        id: makeStepId(programSlug, moduleIndex, "ai-quiz"),
        slug: makeStepId(programSlug, moduleIndex, "ai-quiz"),
        kind: "ai_quiz" as const,
        title: "AI quiz checkpoint",
        description: "Use the AI quiz to confirm the main concepts and open follow-up prompts.",
        sortOrder: 6,
        status: stepState[5],
        estimatedMinutes: 10,
        contentSlug: `${programSlug}-quiz-${moduleIndex}`,
        questionCount: 4,
        promptType: "knowledge_check",
        guidanceMarkdown: "Generate the quiz after the lab, then use the feedback to close knowledge gaps.",
        resources: [makeResource("Quiz guide", "https://example.com/quiz-guide")],
      },
    ],
  };
};

const buildProgram = (
  seed: WorkspaceFallbackSeed,
  programSlug: string,
  title: string,
  subtitle: string,
  description: string,
  progressPercent: number,
) : LearningWorkspaceProgram => {
  const modules = [
    buildModule(programSlug, title, 1, "Module 1: Orientation", "Core definitions, data shape, and the first notebook walk-through.", ["completed", "available", "available", "available", "available", "available"]),
    buildModule(programSlug, title, 2, "Module 2: Applied lab", "Use the same structure on a slightly more realistic case.", ["completed", "completed", "available", "available", "in_progress", "available"]),
    buildModule(programSlug, title, 3, "Module 3: Review and sign-off", "Close the loop with scenario work and the AI quiz.", ["available", "available", "locked", "locked", "locked", "locked"]),
  ];

  return {
    id: programSlug,
    slug: programSlug,
    title,
    subtitle,
    description,
    status: "active",
    progressPercent,
    nextSessionAt: seed.nextSessionAt ?? null,
    audience: ["Analysts", "Managers", "Operations"],
    tags: ["POC", "Notebook-first", "Governed learning"],
    owners: buildOwners(programSlug),
    runtimePreset: buildRuntimePreset(programSlug),
    certificateRule: buildCertificateRule(programSlug),
    modules,
  };
};

const buildProgramList = (seed: WorkspaceFallbackSeed) => {
  return [
    buildProgram(
      seed,
      "poc",
      "POC Core Risk Lab",
      "A single workspace for briefing, notebook execution, AI checks, and scenario sign-off.",
      "This is the primary POC workspace and the default route target.",
      64,
    ),
    buildProgram(
      seed,
      "market-data-workshop",
      "Market Data Workshop",
      "A course focused on formulas, reproducible notebooks, and guided checks.",
      "Built to show the same workspace pattern on a second course.",
      47,
    ),
    buildProgram(
      seed,
      "model-validation-studio",
      "Model Validation Studio",
      "A review-heavy course with scenario decisions and evidence-driven assessment.",
      "A third course to verify the UI scales to multiple programs.",
      39,
    ),
  ];
};

export const buildFallbackLearningWorkspace = (
  seed: WorkspaceFallbackSeed,
  requestedProgramSlug = "poc",
): LearningWorkspacePayload => {
  const programs = buildProgramList(seed);
  const activeProgramSlug = programs.some((program) => program.slug === requestedProgramSlug)
    ? requestedProgramSlug
    : programs[0].slug;

  return {
    source: "fallback",
    fetchedAt: new Date().toISOString(),
    preferredLanguage: seed.preferredLanguage,
    activeProgramSlug,
    supportUrl: "mailto:academy-support@example.com",
    programs,
  };
};

export const deriveFallbackSeed = (dashboard?: DashboardResponse | null): WorkspaceFallbackSeed => ({
  preferredLanguage: dashboard?.profile.preferred_language ?? "en",
  learnerName: `${dashboard?.profile.first_name ?? ""} ${dashboard?.profile.last_name ?? ""}`.trim() || dashboard?.profile.email || "Student",
  nextSessionAt: dashboard?.nextSessionAt ?? null,
});
