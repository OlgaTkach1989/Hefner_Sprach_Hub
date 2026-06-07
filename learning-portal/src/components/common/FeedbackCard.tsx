import styles from "./FeedbackCard.module.css"
import { FeedbackItem } from "../../types"

export const FeedbackCard = ({
  avatar_url,
  full_name,
  geo_city,
  message,
  rating,
}: FeedbackItem) => {
  return (
    <div className={styles.card}>
      <div className={styles.avatarContainer}>
        <img src={avatar_url} alt={full_name} className={styles.avatar} />
      </div>

      <div className={styles.content}>
        <div className={styles.rating}>
          {[...Array(rating)].map((_, i) => (
            <span key={i} className={styles.star}>
              ★
            </span>
          ))}
        </div>

        <h3 className={styles.author}>
          {full_name}, {geo_city}
        </h3>

        <p className={styles.text}>&bdquo;{message}&ldquo;</p>
      </div>
    </div>
  )
}
