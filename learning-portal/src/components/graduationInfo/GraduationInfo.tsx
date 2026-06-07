import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import styles from "./GraduationInfo.module.css";
import { FeedbackSection } from "../common/FeedbackSection";
import { SupportSection } from "../common/SupportSection";
import { FaqSection } from "../common/FaqSection";
import type { FeedbackItem, CourseFaqItem } from "../../types";
import fbfoto1 from "../../assets/feedback-foto.png";
import fbfoto2 from "../../assets/feedback-foto2.png";
import fbfoto3 from "../../assets/feedback-foto1.png";
import heroImage from "../../assets/heroImage.jpg"
import { publicAsset } from "../../utils/publicAsset"

const itemKeys = ["replay", "project", "feedback", "focus"] as const;

export const GraduationInfo = () => {
  const { t } = useTranslation();
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsLoaded(true);
    }, 3000);
    return () => clearTimeout(timer);
  }, []);

  const feedbacks: FeedbackItem[] = [
    { full_name: "Anna M.", geo_city: "Berlin", message: t("feedback.anna"), avatar_url: fbfoto1, rating: 5 },
    { full_name: "Lukas B.", geo_city: "München", message: t("feedback.lukas"), avatar_url: fbfoto2, rating: 5 },
    { full_name: "Sophie K.", geo_city: "Hamburg", message: t("feedback.sophie"), avatar_url: fbfoto3, rating: 5 },
  ];

  const faqItems: CourseFaqItem[] = [
    { id: 1, question: t("faqQuestion1"), answer: t("faqAnswer1"), sort_order: 1 },
    { id: 2, question: t("faqQuestion2"), answer: t("faqAnswer2"), sort_order: 2 },
    { id: 3, question: t("faqQuestion3"), answer: t("faqAnswer3"), sort_order: 3 },
    { id: 4, question: t("faqQuestion4", { defaultValue: t("faqQuestion1") }), answer: t("faqAnswer4", { defaultValue: t("faqAnswer1") }), sort_order: 4 },
    { id: 5, question: t("faqQuestion5", { defaultValue: t("faqQuestion2") }), answer: t("faqAnswer5", { defaultValue: t("faqAnswer2") }), sort_order: 5 },
    { id: 6, question: t("faqQuestion6", { defaultValue: t("faqQuestion3") }), answer: t("faqAnswer6", { defaultValue: t("faqAnswer3") }), sort_order: 6 },
  ];

  return (
    <motion.section
      className={styles.wrapper}
      aria-label={t("graduationInfoTitle")}
      initial={{ opacity: 0 }}
      animate={{ opacity: isLoaded ? 1 : 0 }}
      transition={{ duration: 1, ease: "easeInOut" }}
    >
      <div className={styles.inner}>
        <h2 className={styles.title}>{t("graduationMainTitle")}</h2>

        <div className={styles.timeline}>
          {itemKeys.map((key) => (
            <article className={styles.row} key={key}>
              <div className={styles.markerWrap}>
                <span className={styles.marker}>
                  <img src={publicAsset("images/draw.png")} alt="" />
                </span>
              </div>
              <div className={styles.card}>
                <h3>{t(`graduationInfo.${key}.title`)}</h3>
                <p>{t(`graduationInfo.${key}.text`)}</p>
              </div>
            </article>
          ))}

          <div className={styles.videoSection}>
            <h3 className={styles.videoTitle}>{t("graduationVideoTitle")}</h3>
            <div className={styles.videoFrame}>
              <video
                controls
                poster={heroImage}
                className={styles.videoPlayer}
                preload="metadata"
              >
                <source src="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4" type="video/mp4" />
                {t("videoNotSupported")}
              </video>
            </div>
          </div>
        </div>

        <div className={styles.feedbackBlock}>
          <FeedbackSection feedbacks={feedbacks} />
        </div>
      </div>

      <div className={styles.faqBlock}>
        <FaqSection items={faqItems} />
      </div>

      <div className={styles.supportBlock}>
        <SupportSection />
      </div>
    </motion.section>
  );
};
