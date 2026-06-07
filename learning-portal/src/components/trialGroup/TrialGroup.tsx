import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import styles from "./TrialGroup.module.scss";

export const TrialGroup = () => {
  const { t } = useTranslation();
  const bannerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      const bannerEl = bannerRef.current;
      if (!bannerEl) return;

      const titleEl = bannerEl.querySelector(`.${styles.title}`) as HTMLElement;
      
      const bannerRect = bannerEl.getBoundingClientRect();
      const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

      const titleHeight = titleEl ? titleEl.offsetHeight : 0;
      const targetY = bannerRect.top + scrollTop + (titleHeight / 2); 

      window.scrollTo({
        top: targetY,
        behavior: "smooth",
      });
    }, 3000);

    return () => clearTimeout(timer);
  }, []);

  return (
    <section ref={bannerRef} className={styles.trialGroup} aria-label={t("trialGroupText")}>
      <div className={styles.inner} style={{backgroundImage:"linear-gradient(rgba(1,52,68,0.65), rgba(1,52,68,0.65)), url(/images/trial-group-banner.jpg)",}}>
        <h2 className={styles.title}>{t("trialGroupText")}</h2>
      </div>
    </section>
  );
};