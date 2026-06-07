import { useMemo, useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import type { CourseDetail } from "../../types";
import styles from "./TrialGroupPriceBanner.module.css";
import { GoldButton } from "../common/GoldButton";
import { publicAsset } from "../../utils/publicAsset";

type Props = {
  course: CourseDetail;
  orderLabel: string;
};

export const TrialGroupPriceBanner = ({ course, orderLabel }: Props) => {
  const { t } = useTranslation();
  const routeSlug = course.route_slug ?? course.slug;
  const heroTitle = course.title?.trim() || t("trialHeroTitle");
  const heroTitleParts = heroTitle.split(":");
  const [isRevealed, setIsRevealed] = useState(false);
  const [activeId, setActiveId] = useState(1);
  const [tabOffset, setTabOffset] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsRevealed(true);
    }, 1000);
    return () => clearTimeout(timer);
  }, []);

  const lessons = useMemo(() => {
    const total = Math.max(course.lessons_count ?? 15, 15);
    return Array.from({ length: total }, (_, i) => {
      const id = i + 1;
      const images = id === 8 
        ? [publicAsset("images/lesson_8.jpeg"), publicAsset("images/lesson_8.1.jpeg")] 
        : [publicAsset(`images/lesson_${id}.jpeg`)];

      return {
        id,
        title: t(`lessons.${id}.title`),
        text: t(`lessons.${id}.text`),
        images, 
        pdfUrl: `/files/OnlineKurs_${id}.pdf` 
      };
    });
  }, [course.lessons_count, t]);

  const visibleTabs = lessons.slice(tabOffset, tabOffset + 9);
  const activeLesson = lessons.find((l) => l.id === activeId) ?? lessons[0];

  return (
    <section className={styles.wrapper} id="price-banner-section">
      <motion.div 
        className={styles.innerContainer}
        initial={{ opacity: 0, y: 50, filter: "blur(10px)" }}
        animate={isRevealed ? { opacity: 1, y: 0, filter: "blur(0px)" } : { opacity: 0, y: 50, filter: "blur(10px)" }}
        transition={{ 
          duration: 1.8, 
          ease: [0.22, 1, 0.36, 1]
        }}
      >
        <div className={styles.hero}>
          <div className={styles.heroLeft}>
            <h1 className={styles.heroTitle}>
              {heroTitleParts.map((text, i) => (
                <span key={i}>
                  {text}
                  {i < heroTitleParts.length - 1 ? ":" : ""}
                  <br />
                </span>
              ))}
            </h1>
            <div className={styles.heroMeta}>
              <span>{t("trialLessonsCount", { count: course.lessons_count ?? 15 })}</span>
              <span className={styles.heroPrice}>
                {course.price_amount ?? "99,00"} {course.currency ?? "EUR"}
              </span>
            </div>
            <GoldButton to={`/checkout/${routeSlug}`} size="md" className={styles.orderBtn}>
              {orderLabel}
            </GoldButton>
          </div>
          <div className={styles.heroRight}>
            <ul className={styles.heroBullets}>
              {[1, 2, 3, 4, 5].map(i => <li key={i}>{t(`hero.bullet${i}`)}</li>)}
            </ul>
          </div>
        </div>

<div className={styles.tabs}>
  {tabOffset > 0 && (
    <button className={styles.tabArrow} onClick={() => setTabOffset(Math.max(tabOffset - 9, 0))}>
      ←
    </button>
  )}
  {visibleTabs.map((lesson) => (
    <button
      key={lesson.id}
      className={`${styles.tab} ${lesson.id === activeId ? styles.tabActive : ""}`}
      onClick={() => setActiveId(lesson.id)}
    >
      {t("lessonLabel")} {lesson.id}
    </button>
  ))}

  {tabOffset + 9 < lessons.length && (
    <button className={styles.tabArrow} onClick={() => setTabOffset(tabOffset + 9)}>
      →
    </button>
  )}
</div>

        <div className={styles.lessonCardWrapper}>
          <AnimatePresence mode="wait">
            <motion.article
              key={activeId}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3 }}
              className={styles.lessonCard}
            >
              <div className={styles.preview}>
                {activeLesson?.images.length > 1 ? (
                  <div className={styles.multiPreview}>
                    {activeLesson.images.map((img, idx) => <img key={idx} src={img} alt="" />)}
                  </div>
                ) : (
                  <img src={activeLesson?.images[0]} alt="" />
                )}
              </div>
              <div className={styles.lessonContent}>
                <p className={styles.lessonEyebrow}>{t("lessonLabel")} {activeLesson?.id}</p>
                <h2 className={styles.lessonTitle}>{activeLesson?.title}</h2>
                <p className={styles.lessonText}>{activeLesson?.text}</p>
                <a className={styles.lessonPdf} href={activeLesson?.pdfUrl} target="_blank" rel="noreferrer">
                  <img src="/images/pdfDownLoad.png" alt="PDF" /> {t("lessons.pdfLink")}
                </a>
              </div>
            </motion.article>
          </AnimatePresence>
        </div>
      </motion.div>
    </section>
  );
};
