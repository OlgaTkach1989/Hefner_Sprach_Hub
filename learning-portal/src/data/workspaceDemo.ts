import type { WorkspaceKind, WorkspaceSectionKey } from "../types"

export const defaultSharedWorkspaceSlug = "academy-resources"

export const workspaceSectionMeta: Record<
  WorkspaceSectionKey,
  { title: string; groupDescription: (title: string) => string; sharedDescription: string }
> = {
  news: {
    title: "Updates",
    groupDescription: () => "Announcements, releases, and operational updates.",
    sharedDescription: "Hefner Sprach Hub announcements, release notes, and delivery updates.",
  },
  courses: {
    title: "Courses",
    groupDescription: (title) => `Browse courses for ${title}`,
    sharedDescription: "Open shared course collections.",
  },
  assignments: {
    title: "Practice Labs",
    groupDescription: () => "Open guided practice and coding assignments.",
    sharedDescription: "Hands-on practice and guided coding exercises.",
  },
  recordings: {
    title: "Session Recordings",
    groupDescription: () => "Watch recorded sessions and walkthroughs.",
    sharedDescription: "Recorded sessions and shared walkthroughs.",
  },
  materials: {
    title: "Learning Materials",
    groupDescription: () => "Open documents, articles, and reference materials.",
    sharedDescription: "Documents, articles, and reference materials.",
  },
}

export type AcademyNewsItem = {
  id: string
  category: string
  title: string
  summary: string
  date: string
  audience: string
  status: string
  bullets: string[]
}

export const academySharedNews: AcademyNewsItem[] = [
  {
    id: "academy-digest",
    category: "Weekly digest",
    title: "Programming tracks have been promoted into the shared academy library",
    summary:
      "The academy now exposes Python, automation, and programming practice content through the common resource space so learners can review the same baseline before joining group sessions.",
    date: "2026-04-07",
    audience: "All learners",
    status: "Pinned",
    bullets: [
      "Module 1 lesson presentations were refreshed for Python basics and runtime setup.",
      "Notebook practice now supports AI guidance, submission tracking, and rubric-based checking.",
      "Shared recordings were replaced with programming-oriented walkthroughs for asynchronous review.",
    ],
  },
  {
    id: "lab-release",
    category: "Platform update",
    title: "Interactive notebook workflow is available inside the lesson flow",
    summary:
      "Learners can now move from the lesson stream into JupyterLab without leaving the course structure, then return to submit the finished notebook and review feedback.",
    date: "2026-04-05",
    audience: "Students and instructors",
    status: "Live",
    bullets: [
      "Notebook launches are routed through the secured academy lab runtime.",
      "The same assignment can be reviewed by learners and instructors in their own workspaces.",
      "Submission status and grading stay attached to the lesson record.",
    ],
  },
  {
    id: "content-governance",
    category: "Content governance",
    title: "Presentation, recording, and notebook assets must stay aligned",
    summary:
      "Each lesson package should keep one current presentation, one current recording, and one linked notebook or assessment flow so learners always see the latest teaching set.",
    date: "2026-04-03",
    audience: "Instructors and staff",
    status: "Reminder",
    bullets: [
      "Retire duplicate lesson documents after publishing a refreshed presentation.",
      "Check that shared recordings still match the active lesson outcomes.",
      "Escalate broken notebook links on the same working day.",
    ],
  },
  {
    id: "upcoming-live",
    category: "Upcoming delivery",
    title: "Live coding clinics are opening across Python and automation modules",
    summary:
      "The next round of academy clinics focuses on debugging habits, data handling, and assignment review before the first graded checkpoints.",
    date: "2026-04-02",
    audience: "Enrolled learners",
    status: "Scheduled",
    bullets: [
      "Join the lesson presentation first to align on terminology and target outcomes.",
      "Use the notebook assignment only after reviewing the video walkthrough.",
      "Bring unresolved issues into the AI-assisted practice flow before escalation.",
    ],
  },
]

export const academySharedProgrammingRecordings = [
  {
    id: 9101,
    title: "Python runtime setup and first script walkthrough",
    description:
      "A programming-focused recording covering environment setup, terminal execution, and the first Python workflow expected in the academy starter modules.",
    date: "2026-04-06",
    duration: "24 min",
    thumbnailUrl: "https://img.youtube.com/vi/rfscVS0vtbw/hqdefault.jpg",
    videoUrl: "https://www.youtube.com/watch?v=rfscVS0vtbw",
    isAccessible: true,
    requiredAudienceLabels: [],
    requiredAudienceSlugs: [],
    accessMessage: "",
  },
  {
    id: 9102,
    title: "Variables, input/output, and debugging habits",
    description:
      "A short session focused on Python variables, console input/output, and the debugging routines learners should use before submitting notebook assignments.",
    date: "2026-04-04",
    duration: "18 min",
    thumbnailUrl: "https://img.youtube.com/vi/_uQrJ0TkZlc/hqdefault.jpg",
    videoUrl: "https://www.youtube.com/watch?v=_uQrJ0TkZlc",
    isAccessible: true,
    requiredAudienceLabels: [],
    requiredAudienceSlugs: [],
    accessMessage: "",
  },
  {
    id: 9103,
    title: "Functions, modular thinking, and code review basics",
    description:
      "A shared academy replay about writing reusable Python functions and preparing clean, reviewable solutions before the final module checkpoints.",
    date: "2026-04-01",
    duration: "31 min",
    thumbnailUrl: "https://img.youtube.com/vi/NSbOtYzIQI0/hqdefault.jpg",
    videoUrl: "https://www.youtube.com/watch?v=NSbOtYzIQI0",
    isAccessible: true,
    requiredAudienceLabels: [],
    requiredAudienceSlugs: [],
    accessMessage: "",
  },
]

export const buildWorkspaceLink = (slug: string) => `/spaces/${slug}`

export const buildLearningFormatLink = (
  section: WorkspaceSectionKey,
  workspaceSlug: string = defaultSharedWorkspaceSlug,
) => `${buildWorkspaceLink(workspaceSlug)}?section=${section}`

export const workspaceHeroBadge = (kind: WorkspaceKind) =>
  kind === "shared" ? "Learning Library" : "Team workspace"
