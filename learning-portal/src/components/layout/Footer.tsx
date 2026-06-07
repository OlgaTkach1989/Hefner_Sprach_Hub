import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { motion, AnimatePresence } from "framer-motion"

import logo from "../../assets/logo-footer.svg"
import bgImage from "../../assets/diagonal-footer.png"
import styles from "./Footer.module.css"

export const Footer = () => {
  const { t } = useTranslation()
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(true)
    }, 3500)
    return () => clearTimeout(timer)
  }, [])

  const siteUrl =
    import.meta.env.VITE_PUBLIC_SITE_URL ?? "https://onlinelesson.serveftp.com/"
  const appBasePath = import.meta.env.BASE_URL ?? "/"
  const normalizedBasePath = appBasePath.endsWith("/") ? appBasePath.slice(0, -1) : appBasePath
  const homePath = `${normalizedBasePath || ""}/home`
  const homeHashLink = (hash: string) => `${homePath}${hash}`

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.footer
          className={styles.footer}
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        >
          <img src={bgImage} className={styles.bgImg} alt="background image" />
          <div className={styles.inner}>
            <div className={styles.logoWrap}>
              <a href={`${siteUrl.replace(/\/+$/, "")}/home`} className={styles.brandLink}>
                <img
                  src={logo}
                  className={styles.logo}
                  alt={t("brand")}
                />
                <span>{t("brand")}</span>
              </a>
            </div>
            <nav className={styles.nav} aria-label="Main navigation">
              <a
                href={homeHashLink("#sections")}
                className={styles.navLink}
              >
                {t("navOffices")}
              </a>
              <a href={homeHashLink("#resources")} className={styles.navLink}>
                {t("navResources")}
              </a>
              <a href={homeHashLink("#faq")} className={styles.navLink}>
                {t("navFaq")}
              </a>
            </nav>

            <div className={styles.contacts}>
              <p dangerouslySetInnerHTML={{ __html: t("footerAddress") }} />
              <a href="mailto:contact@onlinelesson.serveftp.com">
                contact@onlinelesson.serveftp.com
              </a>
            </div>
          </div>
        </motion.footer>
      )}
    </AnimatePresence>
  )
}
