import { useTranslation } from "react-i18next"
import { FeedbackItem } from "../../types"
import { FeedbackCard } from "./FeedbackCard"
import styles from "./FeedbackSection.module.css"

type Props = {
  feedbacks: FeedbackItem[]
}

export const FeedbackSection = ({ feedbacks }: Props) => {
  const { t } = useTranslation()

  return (
    <section className={styles.feedback} id="feedback">
      <h2 className={styles.sectionTitle}>{t("sectionFeedbackTitle")}</h2>
      <div className={styles.inner}>
        {feedbacks.map((item, index) => (
          <FeedbackCard key={index} {...item} />
        ))}
      </div>
    </section>
  )
}
