import { useTranslation } from "react-i18next"
import chatIcon from "../../assets/chat_icon.svg"
import styles from "./SupportSection.module.css"
import { FeedbackForm } from "./FeedbackForm"

const supportChatUrl =
  import.meta.env.VITE_SUPPORT_CHAT_URL ?? "https://teams.microsoft.com/"

export const SupportSection = () => {
  const { t } = useTranslation()

  return (
    <section className={styles.support} id="support">
      <h2 className={`${styles.sectionTitle} ${styles.colorGold}`}>
        {t("supportTitle")}
      </h2>
      <div className={styles.supportInner}>
        <div className={styles.chat}>
          <img src={chatIcon} alt="chat icon" />
          <h2>{t("chatTitle")}</h2>
          <p>{t("chatText")}</p>
          <a href={supportChatUrl} target="_blank" rel="noreferrer">
            {t("openChat")} →
          </a>
        </div>
        <FeedbackForm sourcePage="home" />
      </div>
    </section>
  )
}
