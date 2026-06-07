import { Link } from "react-router-dom"
import { useTranslation } from "react-i18next"

import type { CourseSummary } from "../../types"
import styles from "./CourseCard.module.css"

type Props = {
  course: CourseSummary
}

export const CourseCard = ({ course }: Props) => {
  const { t } = useTranslation()
  const routeSlug = course.route_slug ?? course.slug

  return (
    <article className={styles["course-card"]}>
      {course.hero_image_url ? (
        <Link
          to={`/course/${routeSlug}`}
          className={styles["course-card__image-link"]}
        >
          <img
            src={course.hero_image_url}
            className={styles["course-card__image"]}
            alt={course.title}
          />
        </Link>
      ) : null}
      <div className={styles["course-card__content"]}>
        <div className={styles["course-card__badges"]}>
          {course.trial_available ? (
            <span className={styles["course-card__badge"]}>
              {t("courseTrialBadge")}
            </span>
          ) : null}
          <span
            className={`${styles["course-card__badge"]} ${styles["course-card__badge--muted"]}`}
          >
            {course.is_subscription
              ? t("courseSubscription")
              : t("courseSinglePayment")}
          </span>
        </div>

        <h3 className={styles["course-card__title"]}>{course.title}</h3>
        <p className={styles["course-card__description"]}>
          {course.short_description}
        </p>
        <div className={styles["course-card__down"]}>
          <div className={styles["course-card__meta"]}>
            <span>
              {course.lessons_count} {t("lessonsLabel")}
            </span>
            <span className={styles["course-card__meta-price"]}>
              {course.price_amount} {course.currency}
            </span>
          </div>

          <div className={styles["course-card__actions"]}>
            <Link
              to={`/course/${routeSlug}`}
              className={`${styles["course-card__button"]} ${styles["course-card__button--ghost"]}`}
            >
              {t("exploreCourse")}
            </Link>
            <Link
              to={`/checkout/${routeSlug}`}
              className={styles["course-card__button"]}
            >
              {t("orderCourse")}
            </Link>
          </div>
        </div>
      </div>
    </article>
  )
}
