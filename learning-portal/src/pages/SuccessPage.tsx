import { useEffect, useMemo, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Helmet } from "react-helmet-async";

import { getCheckoutStatus } from "../api/onlineApi";
import type { CheckoutStatusResponse } from "../types";
import styles from "./SuccessPage.module.scss";
import { GoldButton } from "../components/common/GoldButton";
import { publicAsset } from "../utils/publicAsset";

type SuccessState = {
  courseTitle?: string;
  cohortName?: string;
  email?: string;
  mode?: "trial" | "paid";
};

export const SuccessPage = () => {
  const { t } = useTranslation();
  const studentLoginUrl = import.meta.env.VITE_ONLINE_STUDENT_URL ?? "http://localhost:5180/login";
  const siteUrl = import.meta.env.VITE_PUBLIC_SITE_URL ?? "http://localhost:5182";
  const paymentMode = String(import.meta.env.VITE_ONLINE_PAYMENT_MODE ?? "free")
    .trim()
    .toLowerCase();
  const isFreePaymentMode = paymentMode === "free";
  const location = useLocation();
  const state = (location.state as SuccessState | null) ?? null;
  const [searchParams] = useSearchParams();
  const [checkoutStatus, setCheckoutStatus] = useState<CheckoutStatusResponse | null>(null);
  const [checkoutStatusError, setCheckoutStatusError] = useState("");
  const [isLoadingStatus, setIsLoadingStatus] = useState(false);

  const orderId = useMemo(() => Number.parseInt(searchParams.get("order") ?? "", 10), [searchParams]);
  const checkoutToken = (searchParams.get("token") ?? "").trim();

  const loadCheckoutStatus = async () => {
    if (!Number.isFinite(orderId) || !checkoutToken) return;
    setIsLoadingStatus(true);
    if (!isFreePaymentMode) {
      setCheckoutStatusError("");
    }
    try {
      const statusResponse = await getCheckoutStatus(orderId, checkoutToken);
      setCheckoutStatus(statusResponse);
    } catch {
      if (!isFreePaymentMode) {
        setCheckoutStatusError(t("checkoutStatusError"));
      }
    } finally {
      setIsLoadingStatus(false);
    }
  };

  useEffect(() => {
    void loadCheckoutStatus();
  }, [orderId, checkoutToken]);

  const remoteStatus = checkoutStatus?.status ?? "";
  const isPending = !isFreePaymentMode && remoteStatus === "pending";
  const isFailed = !isFreePaymentMode && (remoteStatus === "failed" || remoteStatus === "refunded");
  const hasWebhookStatus = !isFreePaymentMode && Boolean(checkoutStatus && Number.isFinite(orderId) && checkoutToken);
  const showSuccess = isFreePaymentMode || !hasWebhookStatus || remoteStatus === "paid";

  const variant: "success" | "pending" | "failed" = showSuccess ? "success" : isPending ? "pending" : "failed";
  const titleText = showSuccess ? t("successTitle") : isPending ? t("paymentPendingTitle") : t("paymentFailedTitle");
  const descriptionText = showSuccess
    ? t("successText")
    : isPending
      ? t("paymentPendingText")
      : checkoutStatus?.failureReason || t("paymentFailedText");

  const metaItems = [
    state?.courseTitle
      ? { label: t("portalTableCourse"), value: state.courseTitle }
      : checkoutStatus?.courseSlug
        ? { label: t("portalTableCourse"), value: checkoutStatus.courseSlug }
        : null,
    state?.cohortName
      ? { label: t("portalTableGroup"), value: state.cohortName }
      : checkoutStatus?.groupCode
        ? { label: t("portalTableGroup"), value: checkoutStatus.groupCode }
        : null,
    state?.email ? { label: t("email"), value: state.email } : null,
    state?.mode
      ? {
          label: t("portalStudent"),
          value: state.mode === "trial" ? t("modeTrial") : t("modePaid"),
        }
      : null,
  ].filter(Boolean) as Array<{ label: string; value: string }>;

  const cardClasses = [styles.successCard];
  const iconClasses = [styles.successCard__icon];
  if (variant !== "success") {
    cardClasses.push(styles[`successCard--${variant}`]);
    iconClasses.push(styles[`successCard__icon--${variant}`]);
  }

  return (
    <main className={styles.successPage}>
      <Helmet>
        <title>{t("successTitle")}</title>
        <meta name="robots" content="noindex, nofollow" />
        <link rel="canonical" href={`${siteUrl}/success`} />
      </Helmet>

      <section className={styles.successHero}>
        <div className={styles.successHero__content}>

          <div className={cardClasses.join(" ")}>
            <div className={iconClasses.join(" ")} aria-hidden="true">
              {variant === "pending" ? (
                <svg viewBox="0 0 64 64" className={styles.successCard__iconVector}>
                  <circle
                    cx="32"
                    cy="32"
                    r="20"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="6"
                    strokeLinecap="round"
                    className={styles.spinnerStroke}
                  />
                </svg>
              ) : isFailed ? (
                <svg viewBox="0 0 64 64" className={styles.successCard__iconVector}>
                  <path d="M20 20 44 44M44 20 20 44" fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" />
                </svg>
              ) : (
                <img src={publicAsset("images/check_circle.png")} alt="" className={styles.successCard__iconImg} />
              )}
            </div>

            <h1 className={styles.successCard__title}>{titleText}</h1>
            {descriptionText ? (
              <p className={styles.successCard__text} aria-live="polite">
                {descriptionText}
              </p>
            ) : null}

            {!isFreePaymentMode && isLoadingStatus ? <p className={styles.successCard__note}>{t("loading")}</p> : null}
            {!isFreePaymentMode && checkoutStatusError ? <p className={styles.successCard__note}>{checkoutStatusError}</p> : null}

            {metaItems.length ? (
              <dl className={styles.successCard__meta}>
                {metaItems.map((item) => (
                  <div key={`${item.label}-${item.value}`} className={styles.successCard__metaItem}>
                    <dt>{item.label}</dt>
                    <dd>{item.value}</dd>
                  </div>
                ))}
              </dl>
            ) : null}

            <div className={styles.successCard__actions}>
              {showSuccess ? (
                <a className={`${styles.successCard__btn} ${styles["successCard__btn--primary"]}`} href={studentLoginUrl} target="_blank" rel="noreferrer">
                  {t("goStudentCabinet")}
                </a>
              ) : null}

              {!isFreePaymentMode && isPending ? (
                <button
                  type="button"
                  className={`${styles.successCard__btn} ${styles["successCard__btn--ghost"]}`}
                  onClick={() => void loadCheckoutStatus()}
                >
                  {t("refreshStatus")}
                </button>
              ) : null}

              <GoldButton className={`${styles.successCard__btn} ${styles["successCard__btn--link"]}`} to="/">
                {t("backHome")}
              </GoldButton>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
};
