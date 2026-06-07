import type { CourseDetail, CourseSummary } from "../types"
import { publicAsset } from "../utils/publicAsset"

export const TRIAL_ROUTE_SLUG = "trial-group-lesson"
const MASTERCLASS_API_SLUG = "webinar-masterclass-live-recording"
const MASTERCLASS_SHOWCASE_SLUG = "new-online-course-2026"
const SHOWCASE_COURSE_SLUGS = new Set([
  TRIAL_ROUTE_SLUG,
  MASTERCLASS_API_SLUG,
  MASTERCLASS_SHOWCASE_SLUG,
])
const CATALOG_SHOWCASE_PREFERENCE = [
  MASTERCLASS_SHOWCASE_SLUG,
  MASTERCLASS_API_SLUG,
  TRIAL_ROUTE_SLUG,
]

const normalizeHeroImageUrl = (heroImageUrl?: string | null) => {
  if (!heroImageUrl) return heroImageUrl

  const tryNormalizeFromPath = (rawPath: string) => {
    const normalizedPath = rawPath.replace(/\\/g, "/")
    const match = normalizedPath.match(/\/learning-portal\/(images\/.+)$/)
    if (match?.[1]) {
      return publicAsset(match[1])
    }
    if (normalizedPath.startsWith("images/")) {
      return publicAsset(normalizedPath)
    }
    if (normalizedPath.startsWith("/images/")) {
      return publicAsset(normalizedPath.slice(1))
    }
    return heroImageUrl
  }

  if (/^https?:\/\//i.test(heroImageUrl)) {
    try {
      const parsed = new URL(heroImageUrl)
      return tryNormalizeFromPath(parsed.pathname)
    } catch {
      return heroImageUrl
    }
  }

  return tryNormalizeFromPath(heroImageUrl)
}

export const resolveCourseApiSlug = (routeSlug?: string) =>
  routeSlug === TRIAL_ROUTE_SLUG ? MASTERCLASS_API_SLUG : routeSlug

export const resolveCourseRouteSlug = (courseSlug: string) =>
  courseSlug === MASTERCLASS_API_SLUG ? TRIAL_ROUTE_SLUG : courseSlug

export const shouldUseShowcaseCoursePage = (
  routeSlug?: string | null,
  courseSlug?: string | null,
) => [routeSlug, courseSlug].some((value) => !!value && SHOWCASE_COURSE_SLUGS.has(value))

export const decorateCourseSummary = (course: CourseSummary): CourseSummary => ({
  ...course,
  route_slug: resolveCourseRouteSlug(course.slug),
  hero_image_url: normalizeHeroImageUrl(course.hero_image_url),
})

export const decorateCourseDetail = (
  course: CourseDetail,
  routeSlug?: string,
): CourseDetail => ({
  ...course,
  route_slug: routeSlug ?? resolveCourseRouteSlug(course.slug),
  hero_image_url: normalizeHeroImageUrl(course.hero_image_url),
})

export const buildCatalogCourses = (courses: CourseSummary[]): CourseSummary[] =>
  {
    const courseSlugs = new Set(courses.map((course) => course.slug))
    const preferredShowcaseSlug = CATALOG_SHOWCASE_PREFERENCE.find((slug) =>
      courseSlugs.has(slug),
    )

    return courses
      .filter((course) => {
        if (!SHOWCASE_COURSE_SLUGS.has(course.slug)) return true
        return course.slug === preferredShowcaseSlug
      })
      .map(decorateCourseSummary)
  }
