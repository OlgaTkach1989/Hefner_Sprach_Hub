export type PocStepKind = "video" | "formula" | "notebook" | "scenario" | "aiQuiz"

export type PocStep = {
  kind: PocStepKind
  label: string
  description: string
}

export type PocModule = {
  title: string
  summary: string
  steps: PocStep[]
}

export type PocCourseBlueprint = {
  slug: string
  title: string
  summary: string
  audience: string
  focus: string
  modules: PocModule[]
}

export const pocRoleMatrix = [
  {
    role: "course_owner",
    label: "Course owner",
    responsibility: "Owns outcomes, scope, and go-live sign-off.",
  },
  {
    role: "knowledge_owner",
    label: "Knowledge owner",
    responsibility: "Maintains FAQ, formulas, and linked references.",
  },
  {
    role: "lab_owner",
    label: "Lab owner",
    responsibility: "Keeps notebook runtime, datasets, and graders stable.",
  },
  {
    role: "instructor",
    label: "Instructor",
    responsibility: "Runs cohort delivery, live support, and reviews.",
  },
] as const

export const pocRuntimePreset = {
  title: "Controlled Jupyter runtime",
  summary:
    "Single JupyterHub entry point with pinned internal packages, MathJax-ready notes, and reproducible notebook execution.",
  bullets: [
    "Internal analytics libraries are preinstalled and version-pinned.",
    "Network access is restricted unless a runtime exception is approved.",
    "Notebook submissions use the same runtime image as the teaching labs.",
    "Formula notes render inline so whiteboard content and notebook work stay aligned.",
  ],
}

export const pocCertificateRule = {
  title: "Certificate rule",
  summary:
    "Award the certificate only after all modules are completed, both notebook steps pass, the scenario is reviewed, and the AI quiz is finished.",
  bullets: [
    "1 video-step, 1 formula-step, 2 notebook-step, 1 scenario-step, 1 AI quiz-step per module.",
    "Attendance can remain a soft signal for the cohort run, but not replace assessment evidence.",
    "Completion should be evidence-based, not just video-complete.",
  ],
}

const buildModules = (topic: string): PocModule[] => [
  {
    title: "Module 1 · Orientation and shared language",
    summary: `Set up the ${topic.toLowerCase()} vocabulary, core data flow, and notebook runtime expectations.`,
    steps: [
      { kind: "video", label: "1 video-step", description: "Short lecture with whiteboard walkthrough." },
      { kind: "formula", label: "1 formula-step", description: "MathJax note with the key derivation." },
      { kind: "notebook", label: "2 notebook-step", description: "Guided starter notebook and submission notebook." },
      { kind: "scenario", label: "1 scenario-step", description: "Decision memo or evidence pack for the first case." },
      { kind: "aiQuiz", label: "1 AI quiz-step", description: "Cited AI check on terminology and process." },
    ],
  },
  {
    title: "Module 2 · Applied lab work",
    summary: `Move from explanation into the ${topic.toLowerCase()} notebook workflow and graded practice.`,
    steps: [
      { kind: "video", label: "1 video-step", description: "Focused explanation of the main workflow." },
      { kind: "formula", label: "1 formula-step", description: "Annotated equation or rule summary." },
      { kind: "notebook", label: "2 notebook-step", description: "One practice lab and one graded lab." },
      { kind: "scenario", label: "1 scenario-step", description: "Scenario with an evidence-backed recommendation." },
      { kind: "aiQuiz", label: "1 AI quiz-step", description: "AI coach checks the learner's understanding." },
    ],
  },
  {
    title: "Module 3 · Review and sign-off",
    summary: `Package the learning into a repeatable outcome with review, ownership, and completion evidence.`,
    steps: [
      { kind: "video", label: "1 video-step", description: "Recap lecture and implementation checklist." },
      { kind: "formula", label: "1 formula-step", description: "Formula reference card for the final review." },
      { kind: "notebook", label: "2 notebook-step", description: "One checkpoint lab and one final submission lab." },
      { kind: "scenario", label: "1 scenario-step", description: "Review memo with owner sign-off criteria." },
      { kind: "aiQuiz", label: "1 AI quiz-step", description: "Final AI quiz with evidence-linked citations." },
    ],
  },
]

export const pocProgramCourses: PocCourseBlueprint[] = [
  {
    slug: "cva-xva-fundamentals",
    title: "CVA / XVA Fundamentals",
    summary: "Exposure, valuation, and control workflow for practitioners who need a stable notebook and evidence trail.",
    audience: "Risk, quant, and model validation teams",
    focus: "CVA / XVA workflow",
    modules: buildModules("CVA / XVA"),
  },
  {
    slug: "secprod-foundations",
    title: "SecProd Foundations",
    summary: "Structured product lifecycle, pricing notes, and scenario-driven labs for internal analysts.",
    audience: "Product, structuring, and analytics teams",
    focus: "Structured products",
    modules: buildModules("Structured products"),
  },
  {
    slug: "model-risk-governance",
    title: "Model Risk Governance",
    summary: "Ownership, lab controls, and evidence-first review for regulated delivery teams.",
    audience: "Governance, compliance, and training owners",
    focus: "Governed learning delivery",
    modules: buildModules("Model risk governance"),
  },
]

export const pocHighlights = [
  "3 seeded courses",
  "3 modules per course",
  "6 step types per module",
  "1 runtime preset",
  "1 certificate rule",
] as const
