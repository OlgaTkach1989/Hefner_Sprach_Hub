import { useEffect, useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useParams } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { isAxiosError } from "axios"

import {
  fetchCourseBySlug,
  fetchPublicWorkspaceBySlug,
  fetchPublicWorkspaces,
  joinWorkspaceCourse,
} from "../api/onlineApi"
import { decorateCourseDetail, resolveCourseApiSlug } from "../config/courseAliases"
import { useUiPreferences } from "../context/UiPreferencesContext"
import { buildCourseSchema, buildFaqSchema } from "../seo/schemas"
import type { CourseCohort, CourseDetail } from "../types"
import "./CoursePage.css"

type CourseBlueprint = {
  label: string
  audience: string
  format: string
  duration: string
  level: string
  overview: string
  outcomes: string[]
  modules: Array<{
    title: string
    summary: string
  }>
  supportBlocks: Array<{
    title: string
    description: string
  }>
  faqFallback: Array<{
    question: string
    answer: string
  }>
}

const flowSteps = ["Theory", "Concept", "Video", "Quiz", "Practice", "Summary"]

type CourseJoinTarget = {
  itemId: number
  title: string
  joinEnabled: boolean
  isAccessible: boolean
  accessMessage: string
}

const courseBlueprintFor = (course: CourseDetail): CourseBlueprint => {
  const slug = `${course.route_slug ?? ""} ${course.slug} ${course.title}`.toLowerCase()

  if (slug.includes("data")) {
    return {
      label: "Data workflows track",
      audience: "Learners who already know Python basics and need reusable data handling patterns.",
      format: "Interactive lessons, guided walkthroughs, and reusable coding practice.",
      duration: "4-6 weeks",
      level: "Intermediate",
      overview:
        "This course turns Python into a practical data toolchain. Learners move from reading structured data to shaping repeatable workflows, checking quality, and preparing final outputs for review.",
      outcomes: [
        "Read, clean, and transform tabular data with a repeatable workflow.",
        "Build reusable scripts and functions for common data tasks.",
        "Validate output before submission with guided checks and AI support.",
      ],
      modules: [
        {
          title: "Data intake and structure",
          summary: "Open real datasets, inspect columns, and establish reliable input routines.",
        },
        {
          title: "Cleaning and transformation",
          summary: "Apply filtering, reshaping, and quality checks without breaking the workflow.",
        },
        {
          title: "Reusable reporting workflow",
          summary: "Package the final analysis into a delivery-ready script with checkpoints.",
        },
      ],
      supportBlocks: [
        {
          title: "Interactive coding practice",
          description: "Practice steps run inside the lesson flow with a code editor, checks, hints, and solution review.",
        },
        {
          title: "AI guidance",
          description: "Ask for debugging hints, clarification, and next-step guidance without leaving the course page.",
        },
        {
          title: "Session recordings",
          description: "Revisit walkthroughs and delivery checkpoints when learners need an asynchronous pass.",
        },
      ],
      faqFallback: [
        {
          question: "Do I need prior pandas experience?",
          answer: "No. The course assumes Python basics and introduces the data workflow step by step.",
        },
        {
          question: "How is progress reviewed?",
          answer: "Each lesson combines a short check, guided practice, and a final delivery checkpoint.",
        },
      ],
    }
  }

  if (slug.includes("web") || slug.includes("api")) {
    return {
      label: "Web and APIs track",
      audience: "Learners who want to move from scripts to backend logic, requests, and service design.",
      format: "Scenario-based lessons with API walkthroughs and applied coding tasks.",
      duration: "4-6 weeks",
      level: "Intermediate",
      overview:
        "This course introduces practical backend thinking: requests, routes, payloads, validation, and small service patterns. The flow stays hands-on so each theory block is tied to a concrete implementation step.",
      outcomes: [
        "Understand request-response patterns and API structure.",
        "Build small backend features with validation and readable responses.",
        "Use lesson practice to debug common integration errors before delivery.",
      ],
      modules: [
        {
          title: "HTTP and service basics",
          summary: "Understand routes, parameters, and response payloads through short backend examples.",
        },
        {
          title: "Validation and integration",
          summary: "Handle bad input, structure responses, and connect external data safely.",
        },
        {
          title: "Mini delivery workflow",
          summary: "Package a small endpoint with checks, documentation notes, and practical review.",
        },
      ],
      supportBlocks: [
        {
          title: "Code-first practice",
          description: "Learners write and test focused backend snippets directly in the lesson practice step.",
        },
        {
          title: "Walkthrough videos",
          description: "Short implementation walkthroughs explain why each backend decision matters.",
        },
        {
          title: "Review-ready output",
          description: "The final step frames each lesson around clean output and reviewability.",
        },
      ],
      faqFallback: [
        {
          question: "Is this a full framework course?",
          answer: "No. It is a practical foundation course focused on API logic, structure, and implementation habits.",
        },
        {
          question: "How much coding practice is included?",
          answer: "Every lesson includes a dedicated practice step with checks, hints, and AI assistance.",
        },
      ],
    }
  }

  if (slug.includes("testing") || slug.includes("automation")) {
    return {
      label: "Testing and automation track",
      audience: "Learners who need reliable delivery habits, validation, and repeatable automation routines.",
      format: "Compact lesson flow with checklists, validation tasks, and automation practice.",
      duration: "4-5 weeks",
      level: "Intermediate",
      overview:
        "The course focuses on dependable delivery: validating assumptions, writing checks, and creating automation steps that can be rerun without manual cleanup.",
      outcomes: [
        "Write tests and validation checks for common Python workflows.",
        "Use automation patterns that reduce manual repetition and delivery risk.",
        "Prepare clean, repeatable final output for review or handoff.",
      ],
      modules: [
        {
          title: "Validation mindset",
          summary: "Turn requirements into checks, expected outputs, and visible acceptance criteria.",
        },
        {
          title: "Testing workflow",
          summary: "Apply focused tests, debug failures, and document assumptions before release.",
        },
        {
          title: "Automation and repeatability",
          summary: "Package the final workflow into scripts that remain safe to rerun and review.",
        },
      ],
      supportBlocks: [
        {
          title: "Guided checkpoints",
          description: "Quiz and practice steps reinforce verification before the final output is accepted.",
        },
        {
          title: "AI debugging support",
          description: "Learners can ask for targeted hints when tests fail or output does not match expectations.",
        },
        {
          title: "Delivery discipline",
          description: "Lessons reinforce cleanup, repeatability, and clear handoff standards.",
        },
      ],
      faqFallback: [
        {
          question: "Is the focus manual testing or coding?",
          answer: "The course is coding-focused and uses testing as part of an automation-oriented workflow.",
        },
        {
          question: "Does each lesson include practice?",
          answer: "Yes. The practical step is part of the lesson flow and uses interactive code checks.",
        },
      ],
    }
  }

  return {
    label: "Core fundamentals track",
    audience: "New learners who need a structured introduction to Python, lesson flow, and hands-on delivery.",
    format: "Guided theory, concept walkthroughs, short quizzes, and interactive practice labs.",
    duration: "3-5 weeks",
    level: "Beginner",
    overview:
      "This course establishes the Python basics required for the rest of the academy catalog. Learners move through short theory blocks, concept examples, video walkthroughs, quick checks, and an interactive practice lab in every lesson.",
    outcomes: [
      "Read and write simple Python code with confidence.",
      "Understand variables, control flow, and function basics in a structured lesson sequence.",
      "Use AI-assisted practice to debug and complete delivery tasks independently.",
    ],
    modules: [
      {
        title: "Runtime setup and first syntax",
        summary: "Set up the environment, run the first script, and understand the basic execution flow.",
      },
      {
        title: "Core concepts and control flow",
        summary: "Move from isolated commands into variables, conditions, loops, and small reusable patterns.",
      },
      {
        title: "Applied practice and delivery",
        summary: "Combine theory and coding into final tasks that mirror the expected course workflow.",
      },
    ],
    supportBlocks: [
      {
        title: "Lesson-by-lesson flow",
        description: "Every lesson follows one consistent structure so learners always know what comes next.",
      },
      {
        title: "Interactive practice",
        description: "The practice step includes code editing, checking, hints, solutions, and AI support.",
      },
      {
        title: "Session recordings and materials",
        description: "Learners can revisit video explanations and read supporting materials after each lesson.",
      },
    ],
    faqFallback: [
      {
        question: "Do I need coding experience before starting?",
        answer: "No. This course is designed as the foundation entry point for new learners.",
      },
      {
        question: "How does each lesson work?",
        answer: "Each lesson follows one flow: theory, concept, video, quiz, practice, and summary.",
      },
    ],
  }
}

const formatCohortDate = (value: string | null) => {
  if (!value) return "Scheduling in progress"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}

const findNextCohort = (cohorts: CourseCohort[]) =>
  [...cohorts]
    .filter((cohort) => !!cohort.start_date)
    .sort((left, right) => {
      const leftTime = left.start_date ? new Date(left.start_date).getTime() : Number.MAX_SAFE_INTEGER
      const rightTime = right.start_date ? new Date(right.start_date).getTime() : Number.MAX_SAFE_INTEGER
      return leftTime - rightTime
    })[0] ?? null

const resolveCourseJoinTarget = async (courseSlugs: string[]): Promise<CourseJoinTarget | null> => {
  const normalizedSlugs = [...new Set(courseSlugs.map((slug) => slug.trim().toLowerCase()).filter(Boolean))]
  if (normalizedSlugs.length === 0) {
    return null
  }

  const summaries = await fetchPublicWorkspaces()
  const groupWorkspaces = summaries
    .filter((workspace) => workspace.kind === "group")
    .sort((left, right) => left.sortOrder - right.sortOrder)

  const details = await Promise.all(
    groupWorkspaces.map(async (workspace) => {
      try {
        return await fetchPublicWorkspaceBySlug(workspace.slug)
      } catch {
        return null
      }
    }),
  )

  const matches = details
    .flatMap((workspace) => workspace?.courses ?? [])
    .filter((item) => normalizedSlugs.includes(String(item.linkedCourseSlug || "").trim().toLowerCase()))
    .sort((left, right) => {
      const leftScore = (left.isAccessible ? 4 : 0) + (left.joinEnabled ? 2 : 0)
      const rightScore = (right.isAccessible ? 4 : 0) + (right.joinEnabled ? 2 : 0)
      return rightScore - leftScore
    })

  if (matches.length === 0) {
    return null
  }

  const best = matches[0]
  return {
    itemId: best.id,
    title: best.title,
    joinEnabled: best.joinEnabled,
    isAccessible: best.isAccessible,
    accessMessage: best.accessMessage,
  }
}

export const CoursePage = () => {
  const { slug } = useParams<{ slug: string }>()
  const { t } = useTranslation()
  const { locale } = useUiPreferences()
  const [course, setCourse] = useState<CourseDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [isJoining, setIsJoining] = useState(false)
  const [isJoined, setIsJoined] = useState(false)
  const [joinFeedback, setJoinFeedback] = useState("")
  const [joinFeedbackTone, setJoinFeedbackTone] = useState<"success" | "error" | null>(null)
  const siteUrl = import.meta.env.VITE_PUBLIC_SITE_URL ?? "http://localhost:5182"
  const routeSlug = course?.route_slug ?? slug

  useEffect(() => {
    if (!slug) return
    setLoading(true)
    fetchCourseBySlug(resolveCourseApiSlug(slug) ?? slug, locale)
      .then((data) => setCourse(decorateCourseDetail(data, slug)))
      .catch(() => setCourse(null))
      .finally(() => setLoading(false))
  }, [slug, locale])

  const faqSchema = useMemo(() => {
    if (!course) return null
    return buildFaqSchema(course)
  }, [course])

  const courseSchema = useMemo(() => {
    if (!course) return null
    return buildCourseSchema(siteUrl, course, locale)
  }, [siteUrl, course, locale])

  const blueprint = useMemo(() => (course ? courseBlueprintFor(course) : null), [course])
  const nextCohort = useMemo(() => (course ? findNextCohort(course.cohorts) : null), [course])
  const joinSlugs = useMemo(
    () => [...new Set([routeSlug, course?.slug].filter((value): value is string => Boolean(value)))],
    [course?.slug, routeSlug],
  )
  const faqItems = useMemo(() => {
    if (!course || !blueprint) return []
    if (course.faq_items.length > 0) {
      return course.faq_items.map((item) => ({
        question: item.question,
        answer: item.answer,
      }))
    }
    return blueprint.faqFallback
  }, [blueprint, course])

  useEffect(() => {
    setIsJoining(false)
    setIsJoined(false)
    setJoinFeedback("")
    setJoinFeedbackTone(null)
  }, [slug])

  const handleJoin = async () => {
    if (!course || isJoining || isJoined) {
      return
    }

    setIsJoining(true)
    setJoinFeedback("")
    setJoinFeedbackTone(null)

    try {
      const joinTarget = await resolveCourseJoinTarget(joinSlugs)
      if (!joinTarget) {
        setJoinFeedbackTone("error")
        setJoinFeedback("This demo course is not linked to a joinable workspace item yet.")
        return
      }
      if (!joinTarget.isAccessible) {
        setJoinFeedbackTone("error")
        setJoinFeedback(
          joinTarget.accessMessage || "Your current role does not allow access to this course.",
        )
        return
      }
      if (!joinTarget.joinEnabled) {
        setJoinFeedbackTone("error")
        setJoinFeedback("This course is visible in the demo but not open for joining yet.")
        return
      }

      const response = await joinWorkspaceCourse(joinTarget.itemId)
      setIsJoined(true)
      setJoinFeedbackTone("success")
      setJoinFeedback(
        response.alreadyJoined
          ? `Already linked to ${response.courseTitle}. Open your student workspace to continue.`
          : `Joined ${response.courseTitle}. It is now available in your student workspace.`,
      )
    } catch (error: unknown) {
      if (isAxiosError(error) && [401, 403].includes(error.response?.status ?? 0)) {
        window.location.assign("/")
        return
      }
      const detail = isAxiosError(error) ? error.response?.data?.detail : undefined
      setJoinFeedbackTone("error")
      setJoinFeedback(detail || "Unable to join this course right now.")
    } finally {
      setIsJoining(false)
    }
  }

  if (loading) {
    return (
      <main className="course-page">
        <p>{t("loading")}</p>
      </main>
    )
  }

  if (!course || !blueprint) {
    return (
      <main className="course-page">
        <p>{t("noCourse")}</p>
        <Link to="/">{t("backHome")}</Link>
      </main>
    )
  }

  return (
    <main className="course-page">
      <Helmet>
        <title>{course.seo_title}</title>
        <meta name="description" content={course.seo_description} />
        <meta property="og:title" content={course.seo_title} />
        <meta property="og:description" content={course.seo_description} />
        <meta property="og:url" content={`${siteUrl}/course/${routeSlug}`} />
        <meta property="og:type" content="article" />
        <link rel="canonical" href={`${siteUrl}/course/${routeSlug}`} />
        <link rel="alternate" hrefLang="en" href={`${siteUrl}/course/${routeSlug}`} />
        <link rel="alternate" hrefLang="x-default" href={`${siteUrl}/course/${routeSlug}`} />
        {courseSchema ? <script type="application/ld+json">{JSON.stringify(courseSchema)}</script> : null}
        {faqSchema ? <script type="application/ld+json">{JSON.stringify(faqSchema)}</script> : null}
      </Helmet>

      <section className="course-page__hero">
        <div className="course-page__hero-copy">
          <p className="course-page__eyebrow">Course overview</p>
          <h1>{course.title}</h1>
          <p className="course-page__lead">{course.short_description}</p>
          <p className="course-page__summary">{course.description || blueprint.overview}</p>

          <div className="course-page__chip-row">
            <span className="course-page__chip">{blueprint.label}</span>
            <span className="course-page__chip">
              {course.lessons_count} {t("lessonsLabel")}
            </span>
            <span className="course-page__chip">{course.geo_city || "Berlin"}</span>
          </div>

          <div className="course-page__actions">
            <button
              type="button"
              className="course-page__action course-page__action--primary"
              onClick={() => void handleJoin()}
              disabled={isJoining || isJoined}
            >
              {isJoined ? "Joined" : isJoining ? "Joining..." : "Join"}
            </button>
            <Link to="/home#sections" className="course-page__action course-page__action--secondary">
              Browse learning areas
            </Link>
          </div>
          {joinFeedback ? (
            <p
              className={`course-page__join-feedback ${joinFeedbackTone === "success" ? "course-page__join-feedback--success" : "course-page__join-feedback--error"}`}
            >
              {joinFeedback}
            </p>
          ) : null}
        </div>

        <div className="course-page__hero-rail">
          {course.hero_image_url ? (
            <div className="course-page__hero-visual">
              <img src={course.hero_image_url} alt={course.title} className="course-page__hero-image" />
              <div className="course-page__hero-visual-badge">
                <span>Interactive lesson flow</span>
                <strong>{blueprint.label}</strong>
              </div>
            </div>
          ) : null}

          <aside className="course-page__hero-card">
            <div className="course-page__stat">
              <span>Format</span>
              <strong>{blueprint.format}</strong>
            </div>
            <div className="course-page__stat">
              <span>Duration</span>
              <strong>{blueprint.duration}</strong>
            </div>
            <div className="course-page__stat">
              <span>Level</span>
              <strong>{blueprint.level}</strong>
            </div>
            <div className="course-page__stat">
              <span>Audience</span>
              <strong>{blueprint.audience}</strong>
            </div>
            <div className="course-page__stat">
              <span>Next cohort</span>
              <strong>{nextCohort ? formatCohortDate(nextCohort.start_date) : "Starts after enrollment"}</strong>
            </div>
            <div className="course-page__stat">
              <span>Access</span>
              <strong>Demo join enabled</strong>
            </div>
          </aside>
        </div>
      </section>

      <section className="course-page__grid course-page__grid--two">
        <article className="course-page__panel">
          <div className="course-page__section-head">
            <div>
              <p className="course-page__eyebrow">Outcomes</p>
              <h2>What learners will be able to do</h2>
            </div>
          </div>
          <ul className="course-page__bullet-list">
            {blueprint.outcomes.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>

        <article className="course-page__panel">
          <div className="course-page__section-head">
            <div>
              <p className="course-page__eyebrow">Support</p>
              <h2>How the course is delivered</h2>
            </div>
          </div>
          <div className="course-page__support-grid">
            {blueprint.supportBlocks.map((block) => (
              <article key={block.title} className="course-page__support-card">
                <strong>{block.title}</strong>
                <p>{block.description}</p>
              </article>
            ))}
          </div>
        </article>
      </section>

      <section className="course-page__panel">
        <div className="course-page__section-head">
          <div>
            <p className="course-page__eyebrow">Course flow</p>
            <h2>What each learner moves through</h2>
          </div>
          <span className="course-page__pill">Theory to practice</span>
        </div>

        <div className="course-page__module-list">
          {blueprint.modules.map((module) => (
            <article key={module.title} className="course-page__module-card">
              <div className="course-page__module-copy">
                <strong>{module.title}</strong>
                <p>{module.summary}</p>
              </div>
              <div className="course-page__step-grid">
                {flowSteps.map((step) => (
                  <span key={`${module.title}-${step}`} className="course-page__step-pill">
                    {step}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="course-page__grid course-page__grid--two">
        <article className="course-page__panel">
          <div className="course-page__section-head">
            <div>
              <p className="course-page__eyebrow">Cohorts and access</p>
              <h2>Planning and enrollment</h2>
            </div>
          </div>

          {course.cohorts.length > 0 ? (
            <div className="course-page__cohort-list">
              {course.cohorts.slice(0, 3).map((cohort) => (
                <article key={cohort.id} className="course-page__cohort-card">
                  <strong>{cohort.name}</strong>
                  <span>{cohort.group_code}</span>
                  <p>Starts: {formatCohortDate(cohort.start_date)}</p>
                  <p>Status: {cohort.status}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="course-page__muted">
              Cohort planning opens after the course is ordered. Learners receive access details and start timing with their enrollment confirmation.
            </p>
          )}
        </article>

        <article className="course-page__panel">
          <div className="course-page__section-head">
            <div>
              <p className="course-page__eyebrow">FAQ</p>
              <h2>Before you order the course</h2>
            </div>
          </div>
          <div className="course-page__faq-list">
            {faqItems.map((item) => (
              <article key={item.question} className="course-page__faq-card">
                <strong>{item.question}</strong>
                <p>{item.answer}</p>
              </article>
            ))}
          </div>
          <div className="course-page__helper-links">
            <Link to="/sign-in">Corporate sign in</Link>
            <Link to="/home#sections">Browse teams and topics</Link>
            <Link to="/spaces/academy-resources?section=recordings">Open session recordings</Link>
          </div>
        </article>
      </section>
    </main>
  )
}
