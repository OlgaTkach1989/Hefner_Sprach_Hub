export type PocStepKind = "video" | "document" | "notebook" | "quiz" | "assignment"

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
  title: "Controlled Python learning runtime",
  summary:
    "Single JupyterHub entry point with pinned Python packages, reproducible notebooks, and reusable briefing assets for every lesson.",
  bullets: [
    "Python, pandas, and notebook dependencies are preinstalled and version-pinned.",
    "Notebook submissions use the same runtime image as the learner-facing practice labs.",
    "PDF briefings and reading notes stay linked to the same lesson document as the coding task.",
    "The final project uses the same runtime and grading contract as the weekly notebook assignments.",
  ],
}

export const pocCertificateRule = {
  title: "Completion rule",
  summary:
    "Mark the course complete only after all modules are reviewed, notebook assignments pass, quizzes are finished, and the final project is submitted.",
  bullets: [
    "Every lesson keeps one guided document flow with video, briefing, reading, quiz, and notebook practice.",
    "Attendance is a support signal, but completion must come from submitted work and graded evidence.",
    "The final project or exam should stay reproducible and reviewable by another instructor.",
  ],
}

const buildModules = (topic: string): PocModule[] => [
  {
    title: "Module 1 · Foundations",
    summary: `Build the baseline ${topic.toLowerCase()} vocabulary, workflow, and first notebook habits.`,
    steps: [
      { kind: "video", label: "Lecture video", description: "Short guided explanation for the lesson objective." },
      { kind: "document", label: "Briefing PDF", description: "Downloadable slide-style summary for review." },
      { kind: "notebook", label: "Practice notebook", description: "Interactive coding task with JupyterLab handoff." },
      { kind: "quiz", label: "Quick quiz", description: "Short knowledge check for the current lesson." },
      { kind: "assignment", label: "Submission task", description: "Notebook or structured deliverable for review." },
    ],
  },
  {
    title: "Module 2 · Applied workflows",
    summary: `Move from explanation into reusable ${topic.toLowerCase()} coding and review workflows.`,
    steps: [
      { kind: "video", label: "Workflow video", description: "Focused delivery walkthrough for the main practice path." },
      { kind: "document", label: "Reference pack", description: "Checkpoint notes, references, and review criteria." },
      { kind: "notebook", label: "Graded notebook", description: "Guided assignment with grader-backed submission." },
      { kind: "quiz", label: "Checkpoint quiz", description: "Short quiz to confirm the workflow is understood." },
      { kind: "assignment", label: "Evidence task", description: "Reviewer-friendly output or reflection for the module." },
    ],
  },
  {
    title: "Module 3 · Review and delivery",
    summary: `Package the learning into a repeatable ${topic.toLowerCase()} outcome with clean reviewer handoff.`,
    steps: [
      { kind: "video", label: "Review video", description: "Recap of the end-to-end lesson and delivery checklist." },
      { kind: "document", label: "Delivery notes", description: "Final notes and release-style summary." },
      { kind: "notebook", label: "Checkpoint notebook", description: "Final interactive practice before sign-off." },
      { kind: "quiz", label: "Review quiz", description: "Small quiz to confirm the module is complete." },
      { kind: "assignment", label: "Module handoff", description: "Documented submission for instructor review." },
    ],
  },
  {
    title: "Final Project / Exam",
    summary: `Consolidate the ${topic.toLowerCase()} course into one reviewer-ready final artifact.`,
    steps: [
      { kind: "document", label: "Final brief", description: "Final project instructions and review criteria." },
      { kind: "notebook", label: "Capstone notebook", description: "Full notebook submission using the course runtime." },
      { kind: "assignment", label: "Handoff note", description: "Short written explanation of the final result and next steps." },
      { kind: "quiz", label: "Exit check", description: "Final confirmation quiz before completion." },
      { kind: "video", label: "Wrap-up video", description: "Short closing walkthrough for the final deliverable." },
    ],
  },
]

export const pocProgramCourses: PocCourseBlueprint[] = [
  {
    slug: "python-core-fundamentals",
    title: "Python Core Fundamentals",
    summary: "Programming foundations with guided lesson documents, notebook assignments, and a final project.",
    audience: "Interns, new joiners, and cross-functional learners",
    focus: "Python language foundations",
    modules: buildModules("Python foundations"),
  },
  {
    slug: "python-data-workflows",
    title: "Python Data Workflows",
    summary: "Data-centric Python course with notebook practice, reusable analysis patterns, and a final exam flow.",
    audience: "Analysts, delivery teams, and internal upskilling cohorts",
    focus: "Data handling and reproducible notebook delivery",
    modules: buildModules("Python data workflows"),
  },
]

export const pocHighlights = [
  "2 seeded courses",
  "3 modules + final exam per course",
  "guided lesson documents",
  "1 runtime preset",
  "1 certificate rule",
] as const
