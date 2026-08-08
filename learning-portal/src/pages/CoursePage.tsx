import { useEffect, useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useParams } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { fetchCourseBySlug } from "../api/onlineApi"
import { AnnaAssistant } from "../components/anna/AnnaAssistant"
import { decorateCourseDetail, resolveCourseApiSlug } from "../config/courseAliases"
import { useUiPreferences } from "../context/UiPreferencesContext"
import { buildCourseSchema, buildFaqSchema } from "../seo/schemas"
import type { CourseDetail, Locale } from "../types"
import { getCourseProgress, isLessonAccessible, isLessonCompleted } from "../utils/courseProgress"
import "./CoursePage.css"

type LessonPreview = {
  duration: string
  icon: string
  subtitle: string
  title: string
}

type ModulePreview = {
  lessons: LessonPreview[]
  locked?: boolean
  subtitle: string
  title: string
  week: string
}

const levelFromCourse = (course: CourseDetail) => {
  const source = `${course.slug} ${course.title}`.toUpperCase()
  return source.match(/\b(A0|A1|A2|B1|B2|C1|C2)\b/)?.[1] ?? "A1"
}

const levelFromSlug = (slug = "deutsch-a1") => slug.toUpperCase().match(/\b(A0|A1|A2|B1|B2|C1|C2)\b/)?.[1] ?? "A1"

const lessonCountForLevel = (level: string) => (["B1", "B2", "C1", "C2"].includes(level) ? 16 : 12)

const priceForLevel = (_level: string) => {
  return "0.00"
}

const createFallbackCourse = (slug = "deutsch-a1"): CourseDetail => {
  const level = levelFromSlug(slug)

  return {
    id: 0,
    slug,
    route_slug: slug,
    title: `Deutsch ${level}`,
    short_description: `Deutsch ${level} lernen - Schritt für Schritt.`,
    lessons_count: lessonCountForLevel(level),
    trial_available: true,
    price_amount: priceForLevel(level),
    currency: "EUR",
    is_subscription: false,
    hero_image_url: null,
    geo_city: "",
    geo_country: "DE",
    description: `Deutsch ${level} - Deutsch-Ukrainischer Kurs.`,
    faq_items: [],
    cohorts: [],
    seo_title: `Deutsch ${level} - Hefner Sprach Hub`,
    seo_description: `Deutsch ${level} lernen mit Hefner Sprach Hub.`,
  }
}

const getCourseCopy = (locale: Locale, level: string) => {
  const isGerman = locale === "de"
  const isRussian = locale === "ru"

  return {
    courseLabel: isGerman ? `Deutsch ${level} - Mein Kurs` : isRussian ? `Deutsch ${level} - мой курс` : `Deutsch ${level} - Мій курс`,
    authorLine: isGerman ? "Autorin: Anna Hefner · Hefner Sprach Hub" : "Автор: Anna Hefner · Hefner Sprach Hub",
    modulesLabel: isGerman ? "Module" : isRussian ? "Модули" : "Модулі",
    moduleLabel: isGerman ? "Modul" : isRussian ? "Модуль" : "Модуль",
    lessonsLabel: isGerman ? "Lektionen" : isRussian ? "Уроков" : "Уроків",
    completedLabel: isGerman ? "abgeschlossen" : isRussian ? "завершено" : "завершено",
    progressDone: isGerman ? "abgeschlossen" : isRussian ? "пройдено" : "виконано",
    completedDuration: isGerman ? "Abgeschlossen" : isRussian ? "Пройдено" : "Пройдено",
    goalEyebrow: isGerman ? `Deutsch ${level} · Deutsch-Ukrainischer Kurs` : isRussian ? `Deutsch ${level} · курс немецкого с русской поддержкой` : `Deutsch ${level} · німецько-український курс`,
    goalTitle: isGerman ? `Deutsch ${level} - Kurs` : isRussian ? `Немецкий ${level} - курс` : `Німецька ${level} - курс`,
    germanGoalTitle: isGerman ? "Kursziel" : isRussian ? "Цель курса на немецком" : "Мета курсу німецькою",
    ukrainianGoalTitle: isGerman ? "Ukrainische Begleitung" : isRussian ? "Сопровождение на русском" : "Мета курсу українською",
    germanGoalIntro: isGerman ? "Nach Abschluss dieses Kurses kann der Lernende:" : isRussian ? "После завершения курса ученик сможет:" : "Після завершення курсу учень зможе:",
    ukrainianGoalIntro: isGerman ? "Die ukrainische Erklärung hilft beim sicheren Einstieg:" : isRussian ? "Русское объяснение помогает уверенно двигаться по курсу:" : "Українське пояснення допомагає впевнено рухатися в курсі:",
    goalsDe: [
      "sich vorstellen",
      "über Familie, Arbeit und Alltag sprechen",
      "einfache Gespräche führen",
      "einkaufen und Essen bestellen",
      "Termine vereinbaren",
      "einfache Texte verstehen und schreiben",
    ],
    goalsUa: [
      isRussian ? "представиться" : "представитися",
      isRussian ? "рассказывать о семье, работе и повседневной жизни" : "розповідати про сім'ю, роботу та повсякденне життя",
      isRussian ? "вести простые разговоры" : "вести прості розмови",
      isRussian ? "делать покупки и заказывать еду" : "робити покупки та замовляти їжу",
      isRussian ? "договариваться о встречах" : "домовлятися про зустрічі",
      isRussian ? "читать и писать простые тексты" : "читати й писати прості тексти",
    ],
    locked: isGerman ? "Gesperrt" : isRussian ? "Заблокировано" : "Заблоковано",
    readyTitle: isGerman ? "Bereit anzufangen?" : isRussian ? "Готовы начать?" : "Готові почати?",
    readyText: isGerman
      ? "In der Testversion können Sie sich kostenlos einschreiben und alle Module öffnen."
      : isRussian
        ? "В тестовой версии можно записаться бесплатно и открыть все модули."
        : "У тестовій версії можна записатися безкоштовно й відкрити всі модулі.",
    buy: isGerman ? "Kostenlos einschreiben" : isRussian ? "Записаться бесплатно" : "Записатися безкоштовно",
  }
}

const buildA1CourseModules = (locale: Locale): ModulePreview[] => {
  const isGerman = locale === "de"

  return [
    {
      week: isGerman ? "Woche 1" : "Тиждень 1",
      title: isGerman ? "Begrüßung und erste Verben" : "Привітання та перші дієслова",
      subtitle: isGerman ? "Vorstellung, Personalpronomen, sein und regelmäßige Verben" : "Знайомство, особові займенники, sein і правильні дієслова",
      lessons: [
        {
          icon: "🎬",
          title: "Unterricht 1: Video + Theorie",
          subtitle: isGerman ? "Begrüßung, Vorstellung, Personalpronomen und sein" : "Відео, теорія, привітання, займенники та sein",
          duration: "30-45 min",
        },
        {
          icon: "✏️",
          title: "Unterricht 2: Praktische Aufgabe",
          subtitle: isGerman ? "Wörter interaktiv in Sätze einsetzen" : "Інтерактивно вставити слова в речення",
          duration: "30-45 min",
        },
        {
          icon: "✅",
          title: "Unterricht 3: Prüfung",
          subtitle: isGerman ? "Wissenstest wie ein kleiner A1-Test" : "Перевірка знань як маленький іспит",
          duration: "30-45 min",
        },
      ],
    },
    {
      week: isGerman ? "Woche 2" : "Тиждень 2",
      title: isGerman ? "Artikel, Nomen und Akkusativ" : "Артиклі, іменники та Akkusativ",
      subtitle: isGerman ? "Bestimmte und unbestimmte Artikel, Objekt im Satz" : "Означені й неозначені артиклі, об'єкт у реченні",
      locked: true,
      lessons: [
        {
          icon: "🎬",
          title: "Unterricht 1: Video + Theorie",
          subtitle: isGerman ? "Artikel, Nomen, Akkusativ und trennbare Verben" : "Відео, теорія, артиклі, Akkusativ і відокремлювані дієслова",
          duration: "30-45 min",
        },
        {
          icon: "📝",
          title: "Unterricht 2: Praktische Aufgabe",
          subtitle: isGerman ? "Artikel und Verben in Sätze einsetzen" : "Вставити артиклі та дієслова в речення",
          duration: "30-45 min",
        },
        {
          icon: "✅",
          title: "Unterricht 3: Prüfung",
          subtitle: isGerman ? "Test zu Artikel, Akkusativ und trennbaren Verben" : "Тест з артиклів, Akkusativ і відокремлюваних дієслів",
          duration: "30-45 min",
        },
      ],
    },
    {
      week: isGerman ? "Woche 3" : "Тиждень 3",
      title: isGerman ? "Modalverben, Dativ und Alltag" : "Модальні дієслова, Dativ і повсякденне життя",
      subtitle: isGerman ? "Können, wollen, müssen, Dativ und Zeitangaben" : "können, wollen, müssen, Dativ і позначення часу",
      locked: true,
      lessons: [
        {
          icon: "🎬",
          title: "Unterricht 1: Video + Theorie",
          subtitle: isGerman ? "Modalverben, Dativ, Zeit und Alltag" : "Відео, теорія, модальні дієслова, Dativ і час",
          duration: "30-45 min",
        },
        {
          icon: "✏️",
          title: "Unterricht 2: Praktische Aufgabe",
          subtitle: isGerman ? "Modalverb, Dativ und Zeitangabe einsetzen" : "Вставити модальне дієслово, Dativ і час",
          duration: "30-45 min",
        },
        {
          icon: "✅",
          title: "Unterricht 3: Prüfung",
          subtitle: isGerman ? "Test zu Modalverben, Dativ und Zeit" : "Тест з модальних дієслів, Dativ і часу",
          duration: "30-45 min",
        },
      ],
    },
    {
      week: isGerman ? "Woche 4" : "Тиждень 4",
      title: isGerman ? "Perfekt, Verbindungen und Abschluss A1" : "Perfekt, поєднання речень і завершення A1",
      subtitle: isGerman ? "Vergangenheit, Satzverbindungen, Selbstvorstellung und Lernrhythmus" : "Минулий час, поєднання речень, самопрезентація та темп навчання",
      locked: true,
      lessons: [
        {
          icon: "🎬",
          title: "Unterricht 1: Video + Theorie",
          subtitle: isGerman ? "Perfekt, Satzverbindungen und Selbstvorstellung" : "Відео, теорія, Perfekt, поєднання речень і самопрезентація",
          duration: "30-45 min",
        },
        {
          icon: "✏️",
          title: "Unterricht 2: Praktische Aufgabe",
          subtitle: isGerman ? "Perfekt und Satzverbindungen einsetzen" : "Вставити слова для Perfekt і поєднання речень",
          duration: "30-45 min",
        },
        {
          icon: "🎓",
          title: "Unterricht 3: Abschlussprüfung A1",
          subtitle: isGerman ? "Finaler Wissenstest für A1" : "Фінальна перевірка знань A1",
          duration: "30-45 min",
        },
      ],
    },
  ]
}

const buildGenericCourseModules = (level: string, locale: Locale): ModulePreview[] => {
  const isGerman = locale === "de"

  return [
    {
      week: isGerman ? "Woche 1" : "Тиждень 1",
      title: isGerman ? `Deutsch ${level}: Einstieg` : `Deutsch ${level}: старт`,
      subtitle: isGerman ? "Grundlagen und erste Aufgaben" : "Основи та перші завдання",
      lessons: [
        { icon: "📘", title: "Lektion 1", subtitle: isGerman ? "Einstieg in den Kurs" : "Початок курсу", duration: "30-45 min" },
        { icon: "✏️", title: "Lektion 2", subtitle: isGerman ? "Wortschatz und Struktur" : "Словник і структура", duration: "30-45 min" },
        { icon: "💬", title: "Lektion 3", subtitle: isGerman ? "Sprechen und Übungen" : "Розмова та вправи", duration: "30-45 min" },
      ],
    },
    {
      week: isGerman ? "Woche 2" : "Тиждень 2",
      title: isGerman ? `Deutsch ${level}: Aufbau` : `Deutsch ${level}: розвиток`,
      subtitle: isGerman ? "Neue Grammatik und Alltagssprache" : "Нова граматика та повсякденна мова",
      locked: true,
      lessons: [
        { icon: "📚", title: "Lektion 4", subtitle: isGerman ? "Grammatik" : "Граматика", duration: "30-45 min" },
        { icon: "📝", title: "Lektion 5", subtitle: isGerman ? "Schreiben" : "Письмо", duration: "30-45 min" },
        { icon: "🎧", title: "Lektion 6", subtitle: isGerman ? "Hören" : "Аудіювання", duration: "30-45 min" },
      ],
    },
    {
      week: isGerman ? "Woche 3" : "Тиждень 3",
      title: isGerman ? `Deutsch ${level}: Praxis` : `Deutsch ${level}: практика`,
      subtitle: isGerman ? "Dialoge, Lesen und Aufgaben" : "Діалоги, читання та завдання",
      locked: true,
      lessons: [
        { icon: "💬", title: "Lektion 7", subtitle: isGerman ? "Dialoge" : "Діалоги", duration: "30-45 min" },
        { icon: "📌", title: "Lektion 8", subtitle: isGerman ? "Alltagssituationen" : "Повсякденні ситуації", duration: "30-45 min" },
        { icon: "🕘", title: "Lektion 9", subtitle: isGerman ? "Wiederholung" : "Повторення", duration: "30-45 min" },
      ],
    },
    {
      week: isGerman ? "Woche 4" : "Тиждень 4",
      title: isGerman ? `Deutsch ${level}: Abschluss` : `Deutsch ${level}: завершення`,
      subtitle: isGerman ? "Projekt, Test und nächste Schritte" : "Проєкт, тест і наступні кроки",
      locked: true,
      lessons: [
        { icon: "⏳", title: "Lektion 10", subtitle: isGerman ? "Vertiefung" : "Закріплення", duration: "30-45 min" },
        { icon: "🔀", title: "Lektion 11", subtitle: isGerman ? "Abschlussaufgaben" : "Фінальні завдання", duration: "30-45 min" },
        { icon: "🎓", title: "Lektion 12", subtitle: isGerman ? "Abschluss" : "Завершення", duration: "30-45 min" },
      ],
    },
  ]
}

const buildCourseModules = (level: string, locale: Locale): ModulePreview[] => (
  level === "A1" ? buildA1CourseModules(locale) : buildGenericCourseModules(level, locale)
)

export const CoursePage = () => {
  const { slug } = useParams<{ slug: string }>()
  const { t } = useTranslation()
  const { locale } = useUiPreferences()
  const [course, setCourse] = useState<CourseDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [progressVersion, setProgressVersion] = useState(0)
  const siteUrl = import.meta.env.VITE_PUBLIC_SITE_URL ?? "http://localhost:5182"
  const routeSlug = course?.route_slug ?? slug ?? "deutsch-a1"

  useEffect(() => {
    if (!slug) return
    setLoading(true)
    fetchCourseBySlug(resolveCourseApiSlug(slug) ?? slug, locale)
      .then((data) => setCourse(decorateCourseDetail(data, slug)))
      .catch(() => setCourse(createFallbackCourse(slug)))
      .finally(() => setLoading(false))
  }, [slug, locale])

  useEffect(() => {
    const refreshProgress = () => setProgressVersion((version) => version + 1)
    window.addEventListener("focus", refreshProgress)
    window.addEventListener("storage", refreshProgress)
    return () => {
      window.removeEventListener("focus", refreshProgress)
      window.removeEventListener("storage", refreshProgress)
    }
  }, [])

  const courseSchema = useMemo(() => (course ? buildCourseSchema(siteUrl, course, locale) : null), [course, locale, siteUrl])
  const faqSchema = useMemo(() => (course ? buildFaqSchema(course) : null), [course])
  const level = course ? levelFromCourse(course) : levelFromSlug(slug)
  const copy = useMemo(() => getCourseCopy(locale, level), [locale, level])
  const modules = useMemo(() => buildCourseModules(level, locale), [level, locale])
  const totalLessons = modules.reduce((count, module) => count + module.lessons.length, 0)
  const courseProgress = useMemo(() => getCourseProgress(routeSlug), [routeSlug, progressVersion])
  const completedLessonsCount = Array.from({ length: totalLessons }, (_, index) => index + 1)
    .filter((lessonNumber) => isLessonCompleted(courseProgress, lessonNumber))
    .length
  const progressPercent = totalLessons > 0 ? Math.round((completedLessonsCount / totalLessons) * 100) : 0
  const progressText = `${completedLessonsCount} / ${totalLessons} ${copy.progressDone}`

  if (loading) {
    return (
      <main className="course-modules-page course-modules-page--state">
        <p>{t("loading")}</p>
      </main>
    )
  }

  if (!course) {
    return (
      <main className="course-modules-page course-modules-page--state">
        <p>{t("noCourse")}</p>
        <Link to="/">{t("backHome")}</Link>
      </main>
    )
  }

  return (
    <main className="course-modules-page">
      <Helmet>
        <title>{course.seo_title}</title>
        <meta name="description" content={course.seo_description} />
        <meta property="og:title" content={course.seo_title} />
        <meta property="og:description" content={course.seo_description} />
        <meta property="og:url" content={`${siteUrl}/course/${routeSlug}`} />
        <meta property="og:type" content="article" />
        <link rel="canonical" href={`${siteUrl}/course/${routeSlug}`} />
        {courseSchema ? <script type="application/ld+json">{JSON.stringify(courseSchema)}</script> : null}
        {faqSchema ? <script type="application/ld+json">{JSON.stringify(faqSchema)}</script> : null}
      </Helmet>

      <section className="course-goal-card">
        <p className="course-goal-card__eyebrow">{copy.goalEyebrow}</p>
        <h1>{copy.goalTitle}</h1>
        <div className="course-goal-card__grid">
          <article>
            <h2>{copy.germanGoalTitle}</h2>
            <p>{copy.germanGoalIntro}</p>
            <ul>
              {copy.goalsDe.map((goal) => <li key={goal}>{goal}</li>)}
            </ul>
          </article>
          <article>
            <h2>{copy.ukrainianGoalTitle}</h2>
            <p>{copy.ukrainianGoalIntro}</p>
            <ul>
              {copy.goalsUa.map((goal) => <li key={goal}>{goal}</li>)}
            </ul>
          </article>
        </div>
      </section>

      <section className="course-progress-card" aria-label="Course progress">
        <div>
          <h2>{copy.courseLabel}</h2>
          <p>{copy.authorLine} · 4 {copy.modulesLabel} · {totalLessons} {copy.lessonsLabel}</p>
        </div>
        <strong>{progressPercent}%<span>{copy.completedLabel}</span></strong>
        <div className="course-progress-card__bar" aria-hidden="true">
          <span style={{ width: `${progressPercent}%` }} />
        </div>
        <div className="course-progress-card__legend">
          <span>0%</span>
          <span>{progressText}</span>
          <span>100%</span>
        </div>
      </section>

      <AnnaAssistant level={level} mode="course" />

      <section className="course-module-list" aria-label="Course modules">
        {modules.map((module, moduleIndex) => {
          const moduleLessonNumbers = module.lessons.map((_, lessonIndex) => moduleIndex * 3 + lessonIndex + 1)
          const moduleCompletedCount = moduleLessonNumbers.filter((lessonNumber) => isLessonCompleted(courseProgress, lessonNumber)).length
          const isModuleLocked = false
          return (
          <article
            className={`course-module-card ${isModuleLocked ? "course-module-card--locked" : "course-module-card--active"}`}
            key={module.title}
          >
            <header className="course-module-card__header">
              <div className="course-module-card__number">{isModuleLocked ? "🔒" : moduleIndex + 1}</div>
              <div>
                <span>{`${copy.moduleLabel} ${moduleIndex + 1}`}</span>
                {isModuleLocked ? <small>🔒 {copy.locked}</small> : null}
                <h3>{module.title}</h3>
                <p>{module.subtitle}</p>
                <em>{module.week}</em>
              </div>
              <strong>{moduleCompletedCount}/3<span>{copy.lessonsLabel}</span></strong>
            </header>
            <div className="course-module-card__lessons">
              {module.lessons.map((lesson, lessonIndex) => {
                const lessonNumber = moduleIndex * 3 + lessonIndex + 1
                const completed = isLessonCompleted(courseProgress, lessonNumber)
                const accessible = isLessonAccessible(courseProgress, lessonNumber)
                const rowContent = (
                  <>
                    <div className="course-lesson-row__number">{completed ? "✓" : accessible ? lessonIndex + 1 : "🔒"}</div>
                    <div className="course-lesson-row__copy">
                      <strong>
                        <span aria-hidden="true">{lesson.icon}</span>
                        {lesson.title}
                      </strong>
                      <p>{lesson.subtitle}</p>
                    </div>
                    <span className="course-lesson-row__duration">{completed ? copy.completedDuration : lesson.duration}</span>
                    <span className="course-lesson-row__chevron" aria-hidden="true">›</span>
                  </>
                )

                return accessible ? (
                  <Link
                    className={`course-lesson-row${completed ? " course-lesson-row--completed" : ""}`}
                    key={lesson.title}
                    to={`/course/${routeSlug}/lesson/${lessonNumber}`}
                  >
                    {rowContent}
                  </Link>
                ) : (
                  <div className="course-lesson-row course-lesson-row--locked" key={lesson.title} aria-disabled="true">
                    {rowContent}
                  </div>
                )
              })}
            </div>
          </article>
          )
        })}
      </section>

      <section className="course-purchase-card">
        <div>
          <h2>{copy.readyTitle}</h2>
          <p>{copy.readyText}</p>
        </div>
        <Link to={`/checkout/${routeSlug}`}>{copy.buy}</Link>
      </section>
    </main>
  )
}


