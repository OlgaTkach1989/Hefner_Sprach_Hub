import { useTranslation } from "react-i18next"
import bgImage from "../../assets/diagonal-footer.png"
import type { CourseFaqItem } from "../../types"
import styles from "./FaqSection.module.css"

type Props = {
  items: CourseFaqItem[]
}

export const FaqSection = ({ items }: Props) => {
  const { t } = useTranslation()

  return (
    <section className={styles.faq} id="faq">
      <img src={bgImage} className={styles.bgImg} alt="" />
      <div className={styles.block}>
        <header className={styles.catalogHeader}>
          <h2 className={styles.sectionTitle}>{t("faqTitle")}</h2>
          <p>{t("faqSubtitle")}</p>
        </header>
        <div className={styles.list}>
          {items.map((item) => (
            <details className={styles.item} key={item.id}>
              <summary className={styles.summary}>
                <span className={styles.questionText}>{item.question}</span>
                <span className={styles.icon}></span>
              </summary>
              <div className={styles.content}>
                <p>{item.answer}</p>
              </div>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}
