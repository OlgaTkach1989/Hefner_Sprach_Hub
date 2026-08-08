export type LessonProgress = {
  completedAt: string
  score?: number
  total?: number
}

export type CourseProgress = Record<string, LessonProgress>

const progressKey = (courseSlug: string) => `hefner-course-progress:${courseSlug}`

export const getCourseProgress = (courseSlug: string): CourseProgress => {
  if (typeof window === "undefined") return {}

  try {
    const rawProgress = window.localStorage.getItem(progressKey(courseSlug))
    return rawProgress ? JSON.parse(rawProgress) as CourseProgress : {}
  } catch {
    return {}
  }
}

export const saveLessonProgress = (courseSlug: string, lessonNumber: number, progress: Omit<LessonProgress, "completedAt"> = {}) => {
  if (typeof window === "undefined") return

  const currentProgress = getCourseProgress(courseSlug)
  const nextProgress: CourseProgress = {
    ...currentProgress,
    [String(lessonNumber)]: {
      ...progress,
      completedAt: new Date().toISOString(),
    },
  }

  window.localStorage.setItem(progressKey(courseSlug), JSON.stringify(nextProgress))
}

export const getCompletedLessonNumbers = (progress: CourseProgress) => (
  Object.keys(progress)
    .map((lessonNumber) => Number(lessonNumber))
    .filter((lessonNumber) => Number.isInteger(lessonNumber))
    .sort((a, b) => a - b)
)

export const isLessonCompleted = (progress: CourseProgress, lessonNumber: number) => Boolean(progress[String(lessonNumber)])

export const isLessonAccessible = (_progress: CourseProgress, lessonNumber: number) => {
  return lessonNumber > 0
}
