import { useTranslation } from "react-i18next";
import { GoldButton } from "../common/GoldButton";
import type { CourseDetail } from "../../types";
import style from "./TrialGroupPriceBanner.module.css";
import { publicAsset } from "../../utils/publicAsset";

type Props = {
  course: CourseDetail;
  orderLabel: string;
};

export const OrderCourse = ({ course, orderLabel }: Props) => {
  const { t } = useTranslation();

  return (
    <section className={style.wrapper} aria-label={course.title}>
      <article className={style.card}>
        <div className={style.preview}>
          <img src={publicAsset("images/trial-group-banner.jpg")} alt={course.title} />
          <p>{t("trialGroupCardImageTitle")}</p>
        </div>

        <div className={style.content}>
          <h2 className={style.title}>{course.title}</h2>
          <p className={style.description}>{course.description}</p>

          <div className={style.meta}>
            <span>
              {course.lessons_count} {t("lessonsLabel")}
            </span>
            <strong>
              {course.price_amount} {course.currency}
            </strong>
          </div>

          <div className={style.actions}>
            <GoldButton to={`/checkout/${course.slug}`}>{orderLabel}</GoldButton>
          </div>
        </div>
      </article>
    </section>
  );
};
