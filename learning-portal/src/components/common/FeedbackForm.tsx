import { FormEvent, useState } from "react"
import { useTranslation } from "react-i18next"

import { createFeedback } from "../../api/onlineApi"
import { useUiPreferences } from "../../context/UiPreferencesContext"
import styles from "./FeedbackForm.module.css"

type Props = {
  courseSlug?: string
  sourcePage: string
}

export const FeedbackForm = ({ courseSlug, sourcePage }: Props) => {
  const { t } = useTranslation()
  const { locale } = useUiPreferences()
  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [subject, setSubject] = useState("")
  const [message, setMessage] = useState("")
  const [statusText, setStatusText] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIsSubmitting(true)
    try {
      await createFeedback({
        course_slug: courseSlug,
        full_name: fullName.trim(),
        email: email.trim(),
        subject: subject.trim(),
        message: message.trim(),
        preferred_language: locale,
        source_page: sourcePage,
      })
      setStatusText("OK")
      setFullName("")
      setEmail("")
      setSubject("")
      setMessage("")
    } catch {
      setStatusText("ERROR")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className={styles.feedbackForm}>
      <form onSubmit={submit} className={styles.form}>
        <input
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          required
          placeholder={t("feedbackName")}
        />
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          type="email"
          placeholder={t("email")}
        />
        <input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          required
          placeholder={t("feedbackSubject")}
        />
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          required
          rows={4}
          placeholder={t("feedbackMessage")}
        />

        {statusText === "OK" ? (
          <p className={styles.ok}>{t("feedbackSuccess")}</p>
        ) : null}
        {statusText === "ERROR" ? (
          <p className={styles.error}>{t("feedbackError")}</p>
        ) : null}
      </form>
      <button type="submit" disabled={isSubmitting}>
        {t("sendFeedback")}
      </button>
    </section>
  )
}
