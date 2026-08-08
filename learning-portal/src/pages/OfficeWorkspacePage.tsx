import { useEffect, useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom"
import { isAxiosError } from "axios"

import { fetchPublicWorkspaceBySlug, joinWorkspaceCourse } from "../api/onlineApi"
import {
  BookIcon,
  LockIcon,
  NewsIcon,
  OnlineCoursesIcon,
  VideoIcon,
} from "../components/common/LandingIcons"
import {
  academySharedNews,
  academySharedProgrammingRecordings,
  defaultSharedWorkspaceSlug,
  workspaceHeroBadge,
  workspaceSectionMeta,
} from "../data/workspaceDemo"
import { useUiPreferences } from "../context/UiPreferencesContext"
import type {
  WorkspaceOfficeDefinition,
  WorkspaceRecordingItem,
  WorkspaceSectionKey,
} from "../types"
import styles from "./OfficeWorkspacePage.module.css"

const validSectionKeys: WorkspaceSectionKey[] = [
  "news",
  "courses",
  "assignments",
  "recordings",
  "materials",
]

const sectionIconMap = {
  news: NewsIcon,
  courses: OnlineCoursesIcon,
  assignments: BookIcon,
  recordings: VideoIcon,
  materials: BookIcon,
} as const

const sectionLabels: Record<WorkspaceSectionKey, string> = {
  news: "News",
  courses: "Courses",
  assignments: "Assignments",
  recordings: "Recordings",
  materials: "Materials",
}

const workspaceCopy = {
  de: {
    back: "Zur Übersicht",
    loading: "Workspace-Inhalte werden geladen...",
    failed: "Dieser Workspace konnte nicht geladen werden. Bitte aktualisieren Sie die Seite.",
    accessRole: "Zugriffsrolle",
    noRole: "Dieses Konto hat aktuell keine Demo-Lernerrolle. Eingeschränkte Materialien bleiben gesperrt, bis ein Administrator Zugriff erteilt.",
    restricted: "Gesperrt",
    requires: "Erforderlich",
    courseDetails: "Kursdetails",
    studentWorkspace: "Studentenbereich",
    openWorkspace: "Im Studentenbereich öffnen",
    requestAccess: "Zugriff anfragen",
    joined: "Beigetreten",
    joining: "Beitritt...",
    join: "Beitreten",
    availableSoon: "Bald verfügbar",
    dismiss: "Schließen",
    close: "Schließen",
    play: "Abspielen",
    videoUnsupported: "Ihr Browser unterstützt das Video-Tag nicht.",
    accessDenied: "Ihre aktuelle Rolle erlaubt keinen Zugriff auf diesen Inhalt. Kontaktieren Sie einen Administrator.",
  },
  uk: {
    back: "До огляду",
    loading: "Завантаження workspace...",
    failed: "Не вдалося завантажити workspace. Оновіть сторінку.",
    accessRole: "Роль доступу",
    noRole: "Цей акаунт зараз не має demo-ролі учня. Обмежені матеріали залишаються закритими, доки адміністратор не надасть доступ.",
    restricted: "Обмежено",
    requires: "Потрібно",
    courseDetails: "Деталі курсу",
    studentWorkspace: "Кабінет учня",
    openWorkspace: "Відкрити в кабінеті учня",
    requestAccess: "Запросити доступ",
    joined: "Приєднано",
    joining: "Приєднання...",
    join: "Приєднатися",
    availableSoon: "Скоро доступно",
    dismiss: "Закрити",
    close: "Закрити",
    play: "Відтворити",
    videoUnsupported: "Ваш браузер не підтримує відео.",
    accessDenied: "Поточна роль не дозволяє доступ до цього контенту. Зверніться до адміністратора.",
  },
  ru: {
    back: "К обзору",
    loading: "Загрузка workspace...",
    failed: "Не удалось загрузить workspace. Обновите страницу.",
    accessRole: "Роль доступа",
    noRole: "У этого аккаунта сейчас нет demo-роли ученика. Ограниченные материалы останутся закрытыми, пока администратор не даст доступ.",
    restricted: "Ограничено",
    requires: "Требуется",
    courseDetails: "Детали курса",
    studentWorkspace: "Кабинет ученика",
    openWorkspace: "Открыть в кабинете ученика",
    requestAccess: "Запросить доступ",
    joined: "Присоединено",
    joining: "Присоединение...",
    join: "Присоединиться",
    availableSoon: "Скоро доступно",
    dismiss: "Закрыть",
    close: "Закрыть",
    play: "Воспроизвести",
    videoUnsupported: "Ваш браузер не поддерживает видео.",
    accessDenied: "Текущая роль не разрешает доступ к этому контенту. Обратитесь к администратору.",
  },
} as const

const formatDateLabel = (value: string) => {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}

const formatDateTimeLabel = (value: string) => {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ""
  return parsed.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

const isDirectVideoUrl = (value: string) => /\.(mp4|webm|ogg)($|\?)/i.test(value)

const resolveVideoEmbedUrl = (value: string) => {
  if (!value) return ""
  const youtubeWatchMatch = value.match(/[?&]v=([^&]+)/)
  if (value.includes("youtube.com/watch") && youtubeWatchMatch?.[1]) {
    return `https://www.youtube.com/embed/${youtubeWatchMatch[1]}`
  }
  const youtubeShortMatch = value.match(/youtu\.be\/([^?&]+)/)
  if (youtubeShortMatch?.[1]) {
    return `https://www.youtube.com/embed/${youtubeShortMatch[1]}`
  }
  return value
}

export const OfficeWorkspacePage = () => {
  const { locale } = useUiPreferences()
  const copy = workspaceCopy[locale]
  const { workspaceSlug, officeSlug } = useParams<{
    workspaceSlug?: string
    officeSlug?: string
  }>()
  const slug = workspaceSlug ?? officeSlug ?? ""
  const [searchParams, setSearchParams] = useSearchParams()
  const [workspace, setWorkspace] = useState<WorkspaceOfficeDefinition | null>(null)
  const [activeRecording, setActiveRecording] =
    useState<WorkspaceRecordingItem | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [isError, setIsError] = useState(false)
  const [joiningCourseId, setJoiningCourseId] = useState<number | null>(null)
  const [joinMessages, setJoinMessages] = useState<Record<number, string>>({})
  const [joinedCourseIds, setJoinedCourseIds] = useState<Record<number, boolean>>({})
  const [accessFeedback, setAccessFeedback] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setIsLoading(true)
    setNotFound(false)
    setIsError(false)
    setJoinMessages({})
    setJoinedCourseIds({})
    setAccessFeedback(null)
    setActiveRecording(null)
    fetchPublicWorkspaceBySlug(slug)
      .then((response) => {
        if (!active) return
        setWorkspace(response)
        setIsLoading(false)
        setJoinMessages({})
        setJoinedCourseIds({})
      })
      .catch((error: unknown) => {
        if (!active) return
        const statusCode =
          typeof error === "object" && error && "response" in error
            ? (error as { response?: { status?: number } }).response?.status
            : undefined
        setWorkspace(null)
        setIsLoading(false)
        setNotFound(statusCode === 404)
        setIsError(statusCode !== 404)
      })
    return () => {
      active = false
    }
  }, [slug])

  const isSharedAcademyWorkspace =
    workspace?.kind === "shared" && workspace.slug === defaultSharedWorkspaceSlug

  const availableSections = useMemo<WorkspaceSectionKey[]>(() => {
    if (!workspace) return ["courses", "assignments", "recordings", "materials"]
    if (!isSharedAcademyWorkspace) return workspace.availableSections
    const withoutCourses = workspace.availableSections.filter((sectionKey) => sectionKey !== "courses")
    return ["news", ...withoutCourses]
  }, [isSharedAcademyWorkspace, workspace])

  const activeSection = useMemo<WorkspaceSectionKey>(() => {
    const raw = searchParams.get("section")
    if (!workspace) return "courses"
    const normalizedSection =
      isSharedAcademyWorkspace && (!raw || raw === "courses") ? "news" : raw
    if (
      normalizedSection &&
      validSectionKeys.includes(normalizedSection as WorkspaceSectionKey) &&
      availableSections.includes(normalizedSection as WorkspaceSectionKey)
    ) {
      return normalizedSection as WorkspaceSectionKey
    }
    return availableSections[0] ?? "courses"
  }, [availableSections, isSharedAcademyWorkspace, searchParams, workspace])

  const workspaceRecordings = useMemo(
    () =>
      isSharedAcademyWorkspace ? academySharedProgrammingRecordings : workspace?.recordings ?? [],
    [isSharedAcademyWorkspace, workspace],
  )

  const panelSummary =
    activeSection === "news"
      ? "Academy release notes, content updates, delivery notices, and platform changes that affect all shared learners."
      : workspace?.summary ||
        "Public content for this section is managed centrally through the academy admin control plane."

  const activeRoleLabel =
    workspace?.activeRole?.shortLabel ||
    workspace?.activeRole?.name ||
    "No learner role assigned"

  const showAccessDenied = (message?: string) => {
    setAccessFeedback(
      message || copy.accessDenied,
    )
  }

  const requirementLabel = (labels: string[]) =>
    labels.length > 0 ? `${copy.requires}: ${labels.join(", ")}` : ""

  if (notFound) {
    return <Navigate to="/404" replace />
  }

  const updateSection = (section: WorkspaceSectionKey) => {
    setAccessFeedback(null)
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set("section", section)
    setSearchParams(nextParams, { replace: true })
  }

  const sectionContent = (() => {
    if (!workspace) return null

    if (activeSection === "news") {
      const [featuredNews, ...otherNews] = academySharedNews
      return (
        <div className={styles.newsShell}>
          <section className={styles.newsFeature}>
            <div className={styles.newsFeatureMeta}>
              <span>{featuredNews.category}</span>
              <span>{formatDateLabel(featuredNews.date)}</span>
            </div>
            <div className={styles.newsFeatureBody}>
              <div className={styles.newsFeatureCopy}>
                <span className={styles.newsStatus}>{featuredNews.status}</span>
                <h3>{featuredNews.title}</h3>
                <p>{featuredNews.summary}</p>
              </div>
              <div className={styles.newsFeatureAside}>
                <span className={styles.newsAudienceLabel}>Audience</span>
                <strong>{featuredNews.audience}</strong>
                <ul className={styles.newsBulletList}>
                  {featuredNews.bullets.map((bullet) => (
                    <li key={bullet}>{bullet}</li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          <div className={styles.newsGrid}>
            {otherNews.map((item) => (
              <article key={item.id} className={styles.newsCard}>
                <div className={styles.newsCardMeta}>
                  <span>{item.category}</span>
                  <span>{formatDateLabel(item.date)}</span>
                </div>
                <h3>{item.title}</h3>
                <p>{item.summary}</p>
                <div className={styles.newsCardFooter}>
                  <span className={styles.newsStatusMuted}>{item.status}</span>
                  <span>{item.audience}</span>
                </div>
              </article>
            ))}
          </div>
        </div>
      )
    }

    if (activeSection === "courses") {
      return (
        <div className={styles.contentGrid}>
          {workspace.courses.map((course) => {
            const courseDetailHref = course.linkedCourseSlug ? `/course/${course.linkedCourseSlug}` : null

            const courseOverview = (
              <>
                <div className={styles.cardMetaLine}>
                  <span>{course.duration}</span>
                  <span>{course.format}</span>
                  {course.linkedGroupCode ? <span>{course.linkedGroupCode}</span> : null}
                </div>
                <h3>{course.title}</h3>
                {course.startsAt ? (
                  <p className={styles.courseStartMeta}>Starts {formatDateTimeLabel(course.startsAt)}</p>
                ) : null}
                <p>{course.description}</p>
                {!course.isAccessible ? (
                  <div className={styles.accessBadgeRow}>
                    <span className={styles.lockedBadge}>
                      <LockIcon className={styles.lockedIcon} />
                      {copy.restricted}
                    </span>
                    {requirementLabel(course.requiredAudienceLabels) ? (
                      <span className={styles.accessMeta}>
                        {requirementLabel(course.requiredAudienceLabels)}
                      </span>
                    ) : null}
                  </div>
                ) : null}
              </>
            )

            return (
              <article
                key={course.id}
                id={`course-${course.id}`}
                className={`${styles.courseCard} ${!course.isAccessible ? styles.restrictedCard : ""}`}
              >
                <div className={styles.courseBody}>
                  {courseDetailHref ? (
                    <Link to={courseDetailHref} className={styles.coursePrimaryLink}>
                      {course.imageUrl ? (
                        <img src={course.imageUrl} alt="" className={styles.courseImage} />
                      ) : null}
                      <div className={styles.courseCopy}>
                        {courseOverview}
                      </div>
                    </Link>
                  ) : (
                    <>
                      {course.imageUrl ? (
                        <img src={course.imageUrl} alt="" className={styles.courseImage} />
                      ) : null}
                      <div className={styles.courseCopy}>
                        {courseOverview}
                      </div>
                    </>
                  )}
                  <div className={styles.courseActions}>
                    <button
                      type="button"
                      className={styles.joinButton}
                      disabled={
                        joiningCourseId === course.id ||
                        Boolean(joinedCourseIds[course.id]) ||
                        (!course.joinEnabled && course.isAccessible)
                      }
                      onClick={async () => {
                        if (!course.isAccessible) {
                          showAccessDenied(course.accessMessage)
                          setJoinMessages((current) => ({
                            ...current,
                            [course.id]:
                              course.accessMessage ||
                              copy.accessDenied,
                          }))
                          return
                        }
                        setJoiningCourseId(course.id)
                        setJoinMessages((current) => ({ ...current, [course.id]: "" }))
                        try {
                          const response = await joinWorkspaceCourse(course.id)
                          setJoinedCourseIds((current) => ({ ...current, [course.id]: true }))
                          setJoinMessages((current) => ({
                            ...current,
                            [course.id]: response.alreadyJoined
                              ? `${response.courseTitle}: ${copy.studentWorkspace}`
                              : `${response.courseTitle}: ${copy.joined}`,
                          }))
                        } catch (error: unknown) {
                          if (isAxiosError(error) && [401, 403].includes(error.response?.status ?? 0)) {
                            window.location.assign("/")
                            return
                          }
                          const detail = isAxiosError(error) ? error.response?.data?.detail : undefined
                          setJoinMessages((current) => ({
                            ...current,
                            [course.id]: detail || copy.accessDenied,
                          }))
                        } finally {
                          setJoiningCourseId((current) => (current === course.id ? null : current))
                        }
                      }}
                    >
                      {joinedCourseIds[course.id]
                        ? copy.joined
                        : joiningCourseId === course.id
                          ? copy.joining
                          : !course.isAccessible
                            ? copy.restricted
                          : course.joinEnabled
                            ? copy.join
                            : copy.availableSoon}
                    </button>
                    {courseDetailHref ? (
                      <Link className={styles.secondaryActionLink} to={courseDetailHref}>
                        {copy.courseDetails}
                      </Link>
                    ) : (
                      <a className={styles.secondaryActionLink} href="/student/dashboard">
                        {copy.studentWorkspace}
                      </a>
                    )}
                  </div>
                  {joinMessages[course.id] ? (
                    <p
                      className={
                        joinedCourseIds[course.id] ? styles.joinSuccessText : styles.joinErrorText
                      }
                    >
                      {joinMessages[course.id]}
                    </p>
                  ) : null}
                </div>
              </article>
            )
          })}
        </div>
      )
    }

    if (activeSection === "assignments") {
      return (
        <div className={styles.assignmentGrid}>
          {workspace.assignments.map((assignment) => (
            <article
              key={assignment.id}
              className={`${styles.assignmentCard} ${!assignment.isAccessible ? styles.restrictedCard : ""}`}
            >
              <div className={styles.assignmentBadge}>{assignment.notebookLabel}</div>
              <h3>{assignment.title}</h3>
              <p>{assignment.description}</p>
              <span className={styles.assignmentMeta}>{assignment.difficulty}</span>
              <div className={styles.assignmentActions}>
                {!assignment.isAccessible ? (
                  <span className={styles.lockedBadge}>
                    <LockIcon className={styles.lockedIcon} />
                    {copy.restricted}
                  </span>
                ) : null}
                {requirementLabel(assignment.requiredAudienceLabels) ? (
                  <span className={styles.accessMeta}>
                    {requirementLabel(assignment.requiredAudienceLabels)}
                  </span>
                ) : null}
                <button
                  type="button"
                  className={styles.inlineActionButton}
                  onClick={() => {
                    if (!assignment.isAccessible) {
                      showAccessDenied(assignment.accessMessage)
                      return
                    }
                    window.location.assign("/student/dashboard")
                  }}
                >
                  {assignment.isAccessible ? copy.openWorkspace : copy.requestAccess}
                </button>
              </div>
            </article>
          ))}
        </div>
      )
    }

    if (activeSection === "recordings") {
      return (
        <div className={styles.stackList}>
          {workspaceRecordings.map((recording) => (
            <button
              key={recording.id}
              type="button"
              className={`${styles.mediaRow} ${!recording.isAccessible ? styles.restrictedCard : ""}`}
              onClick={() => {
                if (!recording.isAccessible) {
                  showAccessDenied(recording.accessMessage)
                  return
                }
                setActiveRecording(recording)
              }}
            >
              <div className={styles.mediaThumbWrap}>
                {recording.thumbnailUrl ? (
                  <img src={recording.thumbnailUrl} alt="" className={styles.mediaThumb} />
                ) : (
                  <div className={styles.documentPreview}>
                    <VideoIcon className={styles.documentIcon} />
                  </div>
                )}
                <span className={styles.playBadge}>{copy.play}</span>
              </div>
              <div className={styles.mediaBody}>
                <div className={styles.cardMetaLine}>
                  <span>{formatDateLabel(recording.date)}</span>
                  <span>{recording.duration}</span>
                </div>
                <h3>{recording.title}</h3>
                <p>{recording.description}</p>
                {!recording.isAccessible || requirementLabel(recording.requiredAudienceLabels) ? (
                  <div className={styles.accessBadgeRow}>
                    {!recording.isAccessible ? (
                      <span className={styles.lockedBadge}>
                        <LockIcon className={styles.lockedIcon} />
                        {copy.restricted}
                      </span>
                    ) : null}
                    {requirementLabel(recording.requiredAudienceLabels) ? (
                      <span className={styles.accessMeta}>
                        {requirementLabel(recording.requiredAudienceLabels)}
                      </span>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </button>
          ))}
        </div>
      )
    }

    return (
      <div className={styles.stackList}>
        {workspace.materials.map((material) => (
          <button
            key={material.id}
            type="button"
            className={`${styles.mediaRow} ${!material.isAccessible ? styles.restrictedCard : ""}`}
            onClick={() => {
              if (!material.isAccessible) {
                showAccessDenied(material.accessMessage)
                return
              }
              if (material.documentUrl) {
                window.open(material.documentUrl, "_blank", "noopener,noreferrer")
              }
            }}
          >
            <div className={styles.documentPreview}>
              <BookIcon className={styles.documentIcon} />
            </div>
            <div className={styles.mediaBody}>
              <div className={styles.cardMetaLine}>
                <span>{formatDateLabel(material.date)}</span>
                <span>{material.category}</span>
              </div>
              <h3>{material.title}</h3>
              <p>{material.description}</p>
              {!material.isAccessible || requirementLabel(material.requiredAudienceLabels) ? (
                <div className={styles.accessBadgeRow}>
                  {!material.isAccessible ? (
                    <span className={styles.lockedBadge}>
                      <LockIcon className={styles.lockedIcon} />
                      {copy.restricted}
                    </span>
                  ) : null}
                  {requirementLabel(material.requiredAudienceLabels) ? (
                    <span className={styles.accessMeta}>
                      {requirementLabel(material.requiredAudienceLabels)}
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>
          </button>
        ))}
      </div>
    )
  })()

  return (
    <main className={styles.page}>
      <Helmet>
        <title>{workspace ? `${workspace.title} | Hefner Sprach Hub` : "Hefner Sprach Hub"}</title>
        <meta
          name="description"
          content={
            workspace
              ? `${workspace.title} workspace with news, recordings, materials, and practical resources.`
              : "Hefner Sprach Hub workspace."
          }
        />
      </Helmet>

      <section className={styles.hero}>
        <div className={styles.heroInner}>
          <div>
            <Link to="/" className={styles.backLink}>
              ← {copy.back}
            </Link>
            <h1>{workspace?.title ?? copy.loading}</h1>
            <p className={styles.heroSubtitle}>{workspace?.subtitle ?? "Section workspace"}</p>
          </div>
          <div className={styles.heroMeta}>
            <span>{workspace ? sectionLabels[activeSection] : "Workspace"}</span>
            <span>{workspace ? workspaceHeroBadge(workspace.kind) : copy.loading}</span>
          </div>
        </div>
      </section>

      <section className={styles.shell}>
        {isLoading ? <p className={styles.statusText}>{copy.loading}</p> : null}
        {isError ? <p className={styles.statusError}>{copy.failed}</p> : null}

        {workspace ? (
          <>
            <section className={styles.rolePanel}>
              <div className={styles.rolePanelHeader}>
                <div>
                  <span className={styles.panelEyebrow}>{copy.accessRole}</span>
                  <h2 className={styles.rolePanelTitle}>{activeRoleLabel}</h2>
                </div>
                <p className={styles.rolePanelCopy}>
                  {workspace.activeRole?.description || copy.noRole}
                </p>
              </div>
              <div className={styles.roleChipRow}>
                {workspace.roleCatalog.map((role) => (
                  <span
                    key={role.slug}
                    className={`${styles.roleChip} ${
                      workspace.activeRole?.slug === role.slug ? styles.roleChipActive : ""
                    }`}
                  >
                    {role.shortLabel}
                  </span>
                ))}
              </div>
              <p className={styles.roleNotice}>{workspace.accessNotice}</p>
            </section>

            {workspace.kind === "shared" ? (
              <div className={styles.sectionCards}>
                {availableSections.map((sectionKey) => {
                  const Icon = sectionIconMap[sectionKey]
                  const meta = workspaceSectionMeta[sectionKey]
                  return (
                    <button
                      key={sectionKey}
                      type="button"
                      className={`${styles.sectionCard} ${
                        activeSection === sectionKey ? styles.sectionCardActive : ""
                      }`}
                      onClick={() => updateSection(sectionKey)}
                    >
                      <div className={styles.sectionCardIconWrap}>
                        <Icon className={styles.sectionCardIcon} />
                      </div>
                      <h2>{meta.title}</h2>
                      <p>
                        {workspace.kind === "shared"
                          ? meta.sharedDescription
                          : meta.groupDescription(workspace.title)}
                      </p>
                    </button>
                  )
                })}
              </div>
            ) : null}

            <section className={styles.contentPanel}>
              <header className={styles.panelHeader}>
                <div>
                  <span className={styles.panelEyebrow}>
                    {workspace.title} {workspace.subtitle}
                  </span>
                  <h2>{sectionLabels[activeSection]}</h2>
                </div>
                <p>
                  {panelSummary}
                </p>
              </header>

              {accessFeedback ? (
                <div className={styles.accessNoticeBanner}>
                  <p>{accessFeedback}</p>
                  <button type="button" className={styles.dismissButton} onClick={() => setAccessFeedback(null)}>
                    {copy.dismiss}
                  </button>
                </div>
              ) : null}

              {sectionContent}
            </section>
          </>
        ) : null}
      </section>

      <aside
        className={`${styles.videoModal} ${
          activeRecording ? styles.videoModalOpen : ""
        }`}
        aria-hidden={activeRecording ? "false" : "true"}
      >
        <div
          className={styles.videoBackdrop}
          onClick={() => setActiveRecording(null)}
        />
        {activeRecording ? (
          <div className={styles.videoDialog}>
            <div className={styles.videoDialogHeader}>
              <div>
                <span className={styles.panelEyebrow}>
                  {formatDateLabel(activeRecording.date)}
                </span>
                <h3>{activeRecording.title}</h3>
              </div>
              <button
                type="button"
                className={styles.closeButton}
                onClick={() => setActiveRecording(null)}
              >
                {copy.close}
              </button>
            </div>
            {isDirectVideoUrl(activeRecording.videoUrl) ? (
              <video
                key={activeRecording.id}
                className={styles.videoPlayer}
                controls
                preload="metadata"
                poster={activeRecording.thumbnailUrl}
              >
                <source src={activeRecording.videoUrl} type="video/mp4" />
                {copy.videoUnsupported}
              </video>
            ) : (
              <iframe
                key={activeRecording.id}
                className={styles.videoFrame}
                src={resolveVideoEmbedUrl(activeRecording.videoUrl)}
                title={activeRecording.title}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                allowFullScreen
              />
            )}
            <p className={styles.videoDescription}>
              {activeRecording.description}
            </p>
          </div>
        ) : null}
      </aside>
    </main>
  )
}

