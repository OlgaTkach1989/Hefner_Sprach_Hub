import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"

import logo from "../../assets/hefner-sprach-hub-logo.jpeg"
import styles from "./Footer.module.css"

export const Footer = () => {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(true)
    }, 3500)
    return () => clearTimeout(timer)
  }, [])

  const appBasePath = import.meta.env.BASE_URL ?? "/"
  const normalizedBasePath = appBasePath.endsWith("/") ? appBasePath.slice(0, -1) : appBasePath
  const homePath = `${normalizedBasePath || ""}/`
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
          <div className={styles.inner}>
            <div className={styles.logoWrap}>
              <a href={homePath} className={styles.brandLink}>
                <img src={logo} className={styles.logo} alt="Hefner Sprach Hub" />
                <span>HEFNER SPRACH HUB</span>
              </a>
            </div>
            <nav className={styles.nav} aria-label="Main navigation">
              <a href={homeHashLink("#levels")} className={styles.navLink}>Kurse</a>
              <a href="/course/deutsch-a1" className={styles.navLink}>A1</a>
              <a href="/course/deutsch-a2" className={styles.navLink}>A2</a>
              <a href="/course/deutsch-b1" className={styles.navLink}>B1</a>
              <a href="/course/deutsch-b2" className={styles.navLink}>B2</a>
              <a href="/course/deutsch-c1" className={styles.navLink}>C1</a>
              <a href="/course/deutsch-c2" className={styles.navLink}>C2</a>
            </nav>

            <div className={styles.contacts}>
              <p>Deutsch lernen · Вивчення німецької</p>
              <a href="mailto:Annahefner79@yahoo.com">Annahefner79@yahoo.com</a>
              <a href="tel:+4915785553934">0049 15785553934</a>
            </div>
          </div>
        </motion.footer>
      )}
    </AnimatePresence>
  )
}
