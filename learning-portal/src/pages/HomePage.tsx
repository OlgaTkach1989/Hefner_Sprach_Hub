import { useEffect, useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { useTranslation } from "react-i18next"
import { Link, useNavigate } from "react-router-dom"

import { fetchPublicWorkspaces } from "../api/onlineApi"
import { FaqSection } from "../components/common/FaqSection"
import { SupportSection } from "../components/common/SupportSection"
import {
  BerlinGateIcon,
  BookIcon,
  FinanceIcon,
  ItIcon,
  LondonIcon,
  NewsIcon,
  NewYorkIcon,
  ParisIcon,
  PlusIcon,
  PragueIcon,
  VideoIcon,
  ViennaIcon,
} from "../components/common/LandingIcons"
import {
  buildLearningFormatLink,
  buildWorkspaceLink,
  defaultSharedWorkspaceSlug,
} from "../data/workspaceDemo"
import { buildOrganizationSchema } from "../seo/schemas"
import type { WorkspaceSummary } from "../types"
import { resolveLearnerCabinetAccess } from "../utils/learnerCabinet"
import styles from "./HomePage.module.css"

const officeIcons = {
  berlin: BerlinGateIcon,
  new_york: NewYorkIcon,
  london: LondonIcon,
  prague: PragueIcon,
  paris: ParisIcon,
  vienna: ViennaIcon,
  it: ItIcon,
  finance: FinanceIcon,
  academy: BookIcon,
} as const

const buildResourceItems = (sharedWorkspaceSlug: string) => [
  {
    title: "Updates",
    description: "Read platform announcements, release notes, and learning updates.",
    Icon: NewsIcon,
    to: buildLearningFormatLink("news", sharedWorkspaceSlug),
  },
  {
    title: "Session Recordings",
    description: "View recorded sessions, walkthroughs, and replayable learning content.",
    Icon: VideoIcon,
    to: buildLearningFormatLink("recordings", sharedWorkspaceSlug),
  },
  {
    title: "Learning Materials",
    description: "Open documents, articles, and reference materials from the shared library.",
    Icon: BookIcon,
    to: buildLearningFormatLink("materials", sharedWorkspaceSlug),
  },
]

export const HomePage = () => {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([])
  const [isWorkspacesLoading, setIsWorkspacesLoading] = useState(true)
  const [workspacesError, setWorkspacesError] = useState(false)
  const [cabinetMessage, setCabinetMessage] = useState("")
  const [isCabinetBusy, setIsCabinetBusy] = useState(false)

  const siteUrl = import.meta.env.VITE_PUBLIC_SITE_URL ?? "https://onlinelesson.serveftp.com"
  const organizationSchema = useMemo(() => buildOrganizationSchema(siteUrl), [siteUrl])

  useEffect(() => {
    let active = true
    setIsWorkspacesLoading(true)

    fetchPublicWorkspaces()
      .then((response) => {
        if (!active) return
        setWorkspaces(response)
        setWorkspacesError(false)
      })
      .catch(() => {
        if (!active) return
        setWorkspaces([])
        setWorkspacesError(true)
      })
      .finally(() => {
        if (!active) return
        setIsWorkspacesLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!cabinetMessage) return
    const timer = window.setTimeout(() => setCabinetMessage(""), 5000)
    return () => window.clearTimeout(timer)
  }, [cabinetMessage])

  const groupWorkspaces = useMemo(
    () => workspaces.filter((workspace) => workspace.kind === "group" && workspace.showOnHomepage),
    [workspaces],
  )
  const sharedWorkspaceSlug = useMemo(
    () =>
      workspaces.find((workspace) => workspace.kind === "shared" && workspace.isPublished)?.slug ??
      defaultSharedWorkspaceSlug,
    [workspaces],
  )
  const resourceItems = useMemo(() => buildResourceItems(sharedWorkspaceSlug), [sharedWorkspaceSlug])
  const needsPlaceholderCard = !isWorkspacesLoading && groupWorkspaces.length < 9

  const faqItems = [
    {
      id: 1,
      question: t("faqQuestion1"),
      answer: t("faqAnswer1"),
      sort_order: 1,
    },
    {
      id: 2,
      question: t("faqQuestion2"),
      answer: t("faqAnswer2"),
      sort_order: 2,
    },
    {
      id: 3,
      question: t("faqQuestion3"),
      answer: t("faqAnswer3"),
      sort_order: 3,
    },
  ]

  const handleCabinetClick = async () => {
    if (isCabinetBusy) return

    setIsCabinetBusy(true)
    setCabinetMessage("")
    try {
      const resolution = await resolveLearnerCabinetAccess()
      if (resolution.kind === "dashboard") {
        window.location.assign(resolution.url)
        return
      }
      if (resolution.kind === "sign_in") {
        navigate(resolution.url)
        return
      }
      setCabinetMessage(resolution.message)
    } catch {
      setCabinetMessage("The learner dashboard is temporarily unavailable. Please try again.")
    } finally {
      setIsCabinetBusy(false)
    }
  }

  return (
    <main className={styles.homePage}>
      <Helmet>
        <title>{t("brand")}</title>
        <meta name="description" content={t("heroSubtitle")} />
        <meta name="geo.region" content="DE-BE" />
        <meta name="geo.placename" content="Berlin" />
        <meta property="og:title" content={t("brand")} />
        <meta property="og:description" content={t("heroSubtitle")} />
        <meta property="og:url" content={siteUrl} />
        <meta property="og:type" content="website" />
        <meta property="og:locale" content="en_US" />
        <link rel="canonical" href={`${siteUrl.replace(/\/+$/, "")}/home`} />
        <link rel="alternate" hrefLang="en" href={`${siteUrl.replace(/\/+$/, "")}/home`} />
        <link rel="alternate" hrefLang="x-default" href={`${siteUrl.replace(/\/+$/, "")}/home`} />
        <script type="application/ld+json">{JSON.stringify(organizationSchema)}</script>
      </Helmet>

      <section className={styles.hero} aria-label={t("heroTitle")}>
        <div className={styles.heroInner}>
          <div className={styles.heroContent}>
            <h1>{t("heroTitle")}</h1>
            <p className={styles.heroLead}>{t("heroSubtitle")}</p>
            <p className={styles.heroSupportCopy}>{t("heroLead")}</p>
            <div className={styles.heroActions}>
              <button
                type="button"
                className={`${styles.heroAction} ${styles.heroActionPrimary}`}
                onClick={() => void handleCabinetClick()}
                disabled={isCabinetBusy}
              >
                {isCabinetBusy ? t("loading") : t("heroCabinetCta")}
              </button>
              <a href="#resources" className={`${styles.heroAction} ${styles.heroActionSecondary}`}>
                {t("navResources")}
              </a>
            </div>
            <p className={styles.heroCabinetNote}>{t("heroCabinetNote")}</p>
            {cabinetMessage ? <p className={styles.heroCabinetMessage}>{cabinetMessage}</p> : null}
            <blockquote className={styles.heroQuote}>{t("slogan")}</blockquote>
            <p className={styles.heroQuoteAuthor}>{t("sloganAuthor")}</p>
          </div>
        </div>
      </section>

      <section className={styles.featureSection} aria-label={t("navOffices")} id="sections">
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{t("navOffices")}</h2>
          <p className={styles.sectionSubtitle}>
            Browse the teams, departments, and learning topics that organize the public catalog.
          </p>
        </div>
        <div className={styles.featureGrid}>
          {groupWorkspaces.map((workspace) => {
            const Icon = officeIcons[workspace.iconKey as keyof typeof officeIcons] ?? BerlinGateIcon
            return (
              <Link
                key={workspace.slug}
                to={buildWorkspaceLink(workspace.slug)}
                className={`${styles.featureCard} ${styles.featureCardLink}`}
              >
                <div className={styles.featureIconWrap}>
                  <Icon className={styles.featureIcon} />
                </div>
                <h3>{workspace.title}</h3>
                <p>{workspace.subtitle}</p>
              </Link>
            )
          })}
          {needsPlaceholderCard ? (
            <div className={`${styles.featureCard} ${styles.featureCardPlaceholder}`}>
              <div className={styles.featureIconWrap}>
                <PlusIcon className={styles.featureIcon} />
              </div>
              <h3>Add team or topic</h3>
              <p>Create new public discovery cards through the admin control plane.</p>
            </div>
          ) : null}
        </div>
        {workspacesError ? (
          <p className={styles.sectionError}>
            Failed to load teams and topics. Refresh the page after the public content API becomes available.
          </p>
        ) : null}
      </section>

      <section
        id="resources"
        className={`${styles.featureSection} ${styles.featureSectionAlt}`}
        aria-label={t("navResources")}
      >
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{t("navResources")}</h2>
          <p className={styles.sectionSubtitle}>
            Open shared recordings, updates, and learning materials without committing to a single team or topic area.
          </p>
        </div>
        <div className={`${styles.featureGrid} ${styles.featureGridCompact}`}>
          {resourceItems.map(({ title, description, Icon, to }) => (
            <Link key={title} to={to} className={`${styles.featureCard} ${styles.featureCardLink}`}>
              <div className={styles.featureIconWrap}>
                <Icon className={styles.featureIcon} />
              </div>
              <h3>{title}</h3>
              <p>{description}</p>
            </Link>
          ))}
        </div>
      </section>

      <FaqSection items={faqItems} />
      <SupportSection />
    </main>
  )
}
