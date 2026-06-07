import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Helmet } from "react-helmet-async";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { isAxiosError } from "axios";

import { createCheckoutStart, createTrialSignup, fetchCourseBySlug } from "../api/onlineApi";
import { PaymentMethods } from "../components/checkout/PaymentMethods";
import { GoldButton } from "../components/common/GoldButton";
import { decorateCourseDetail, resolveCourseApiSlug, TRIAL_ROUTE_SLUG } from "../config/courseAliases";
import { useUiPreferences } from "../context/UiPreferencesContext";
import type { CourseDetail, PaymentProvider } from "../types";
import { publicAsset } from "../utils/publicAsset";
import "./CheckoutPage.css";

const extractApiError = (error: unknown, fallback: string) => {
  if (!isAxiosError(error)) return fallback;
  const payload = error.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;

  if (typeof payload === "object") {
    for (const value of Object.values(payload)) {
      if (Array.isArray(value) && typeof value[0] === "string") return value[0];
      if (typeof value === "string") return value;
    }
  }
  return fallback;
};

export const CheckoutPage = () => {
  const { slug } = useParams<{ slug: string }>();
  const { t } = useTranslation();
  const { locale } = useUiPreferences();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const siteUrl = import.meta.env.VITE_PUBLIC_SITE_URL ?? "http://localhost:5182";
  const paymentMode = String(import.meta.env.VITE_ONLINE_PAYMENT_MODE ?? "free")
    .trim()
    .toLowerCase();
  const isFreePaymentMode = paymentMode === "free";
  const isTrialCheckout = slug === TRIAL_ROUTE_SLUG;

  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [mode, setMode] = useState<"trial" | "paid">("paid");
  const [selectedCohortId, setSelectedCohortId] = useState<number | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [provider, setProvider] = useState<PaymentProvider>("paypal");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [errorText, setErrorText] = useState("");
  const [trialStep, setTrialStep] = useState<"selection" | "registration" | "payment">("selection");
  const [isCohortMenuOpen, setIsCohortMenuOpen] = useState(false);
  const cohortMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    fetchCourseBySlug(resolveCourseApiSlug(slug) ?? slug, locale)
      .then((data) => {
        const preferredCohortFromQuery = Number.parseInt(searchParams.get("cohort") ?? "", 10);
        const preferredCohort = Number.isFinite(preferredCohortFromQuery)
          ? data.cohorts.find((item) => item.id === preferredCohortFromQuery)
          : undefined;
        const firstCohortWithSeats = data.cohorts.find((item) => (item.seats_left ?? 1) > 0);

        setCourse(decorateCourseDetail(data, slug));
        setMode(isTrialCheckout ? "trial" : data.trial_available ? "trial" : "paid");
        setSelectedCohortId(preferredCohort?.id ?? firstCohortWithSeats?.id ?? data.cohorts[0]?.id);
        setTrialStep("selection");
      })
      .catch(() => setCourse(null))
      .finally(() => setLoading(false));
  }, [slug, locale, searchParams, isTrialCheckout]);

  const selectedCohort = useMemo(
    () => course?.cohorts.find((item) => item.id === selectedCohortId),
    [course, selectedCohortId]
  );
  const routeSlug = course?.route_slug ?? slug;
  const isSelectedCohortFull = Boolean(selectedCohort && (selectedCohort.seats_left ?? 1) <= 0);
  const formatCohortTriggerLabel = (cohort: NonNullable<CourseDetail["cohorts"]>[number]) =>
    `${cohort.name} - ${
      (cohort.seats_left ?? 0) > 0 ? `${t("cohortSeatsLeft")}: ${cohort.seats_left}` : t("cohortFull")
    }`;
  const formatCohortLabel = (cohort: NonNullable<CourseDetail["cohorts"]>[number]) =>
    `${cohort.name} (${cohort.group_code}) - ${
      (cohort.seats_left ?? 0) > 0 ? `${t("cohortSeatsLeft")}: ${cohort.seats_left}` : t("cohortFull")
    }`;

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!cohortMenuRef.current?.contains(event.target as Node)) {
        setIsCohortMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);
  const canSubmit = useMemo(() => {
    if (!firstName || !lastName || !email || !password) return false;
    if ((mode === "paid" || isTrialCheckout) && !acceptTerms) return false;
    if (isSelectedCohortFull) return false;
    return true;
  }, [acceptTerms, email, firstName, isSelectedCohortFull, isTrialCheckout, lastName, mode, password]);

  const finalizeCheckout = async (providerOverride?: PaymentProvider) => {
    if (!course || !canSubmit || isSelectedCohortFull) return;

    setSubmitting(true);
    setErrorText("");
    const idempotencyKey = crypto.randomUUID();
    try {
      const payload = {
        course_slug: course.slug,
        cohort_id: selectedCohortId,
        email,
        password,
        first_name: firstName,
        last_name: lastName,
        phone,
        preferred_language: locale,
        idempotency_key: idempotencyKey
      };

      if (mode === "trial") {
        await createTrialSignup(payload);

        navigate("/success", {
          replace: true,
          state: {
            courseTitle: course.title,
            cohortName: selectedCohort?.name,
            email,
            mode
          }
        });
      } else {
        const response = await createCheckoutStart({
          ...payload,
          provider: providerOverride ?? provider,
          accept_terms: acceptTerms
        });
        window.location.assign(response.checkoutUrl);
      }
    } catch (error) {
      setErrorText(extractApiError(error, t("checkoutError")));
    } finally {
      setSubmitting(false);
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await finalizeCheckout();
  };

  const proceedToTrialPayment = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit || isSelectedCohortFull) return;
    setErrorText("");
    setTrialStep("payment");
  };

  const proceedToTrialRegistration = () => {
    if (isSelectedCohortFull) return;
    setErrorText("");
    setTrialStep("registration");
  };

  const submitTrialWithProvider = async (uiProvider: "card" | "klarna" | "sofort" | "paypal") => {
    const providerMap: Record<typeof uiProvider, PaymentProvider> = {
      card: "klarna",
      klarna: "klarna",
      sofort: "sofort",
      paypal: "paypal"
    };
    setProvider(providerMap[uiProvider]);
    await finalizeCheckout(providerMap[uiProvider]);
  };

  const handleSocialAuth = (providerName: "apple" | "facebook") => {
    const urlByProvider: Record<"apple" | "facebook", string> = {
      apple: "https://account.apple.com/account#!/create",
      facebook: "https://www.facebook.com/reg/"
    };
    const url = urlByProvider[providerName];
    const popup = window.open(url, "_blank", "noopener,noreferrer");
    if (!popup) {
      window.location.assign(url);
    }
  };

  const socialCheckoutActions = (
    <>
      <div className="checkout-page__social-divider">
        <span>{t("checkoutOr")}</span>
      </div>
      <button type="button" className="checkout-page__social-btn" onClick={() => handleSocialAuth("facebook")}>
        <img src={publicAsset("images/facebook.png")} alt="Facebook" />
        <span>{t("checkoutWithFacebook")}</span>
      </button>
      <button type="button" className="checkout-page__social-btn" onClick={() => handleSocialAuth("apple")}>
        <span className="checkout-page__social-icon">
          <img src={publicAsset("images/apple.png")} alt="Apple" />
        </span>
        <span>{t("checkoutWithApple")}</span>
      </button>
    </>
  );

  if (loading) {
    return (
      <main className="checkout-page">
        <p>{t("loading")}</p>
      </main>
    );
  }

  if (!course) {
    return (
      <main className="checkout-page">
        <p>{t("noCourse")}</p>
        <Link to="/">{t("backHome")}</Link>
      </main>
    );
  }

  return (
    <main className={`checkout-page${isTrialCheckout ? " checkout-page--trial" : ""}`}>
      <Helmet>
        <title>{`${t("checkoutTitle")} - ${course.title}`}</title>
        <meta name="robots" content="noindex, nofollow" />
        <link rel="canonical" href={`${siteUrl}/checkout/${routeSlug}`} />
      </Helmet>
      {isTrialCheckout ? (
        <>
          <section className="checkout-page__trial-surface">
            <div className="checkout-page__trial-card">
              <aside className="checkout-page__trial-preview">
                <img
                  src={
                    trialStep === "registration"
                      ? publicAsset("images/background.jpg")
                      : publicAsset("images/trial-group-banner.jpg")
                  }
                  alt={t("trialGroupCardImageTitle")}
                />
                {trialStep !== "registration" ? <p>{t("trialGroupCardImageTitle")}</p> : null}
              </aside>

              {trialStep === "selection" ? (
                <div className="checkout-page__form checkout-page__form--trial">
                  <div className="checkout-page__trial-summary-box">
                    <h2>{course.title}</h2>
                    <p>{t("trialGroupText")}</p>
                    <p>
                      {course.lessons_count} {t("lessonsLabel")}
                    </p>
                  </div>

                  {course.cohorts.length > 0 ? (
                    <div className="checkout-page__cohort-select" ref={cohortMenuRef}>
                      <button
                        type="button"
                        className="checkout-page__cohort-trigger"
                        onClick={() => setIsCohortMenuOpen((prev) => !prev)}
                        aria-expanded={isCohortMenuOpen}
                      >
                        <span className="checkout-page__cohort-trigger-text">
                          {selectedCohort ? formatCohortTriggerLabel(selectedCohort) : t("checkoutNoGroup")}
                        </span>
                        <img
                          src={publicAsset("images/accordion.svg")}
                          alt=""
                          className={`checkout-page__cohort-icon${isCohortMenuOpen ? " is-open" : ""}`}
                        />
                      </button>

                      {isCohortMenuOpen ? (
                        <ul className="checkout-page__cohort-menu" role="listbox">
                          {course.cohorts.map((cohort) => {
                            const isDisabled = (cohort.seats_left ?? 1) <= 0;
                            const isSelected = cohort.id === selectedCohortId;
                            return (
                              <li key={cohort.id}>
                                <button
                                  type="button"
                                  className={`checkout-page__cohort-option${isSelected ? " is-selected" : ""}`}
                                  onClick={() => {
                                    if (isDisabled) return;
                                    setSelectedCohortId(cohort.id);
                                    setIsCohortMenuOpen(false);
                                  }}
                                  disabled={isDisabled}
                                >
                                  <span className="checkout-page__cohort-check">{isSelected ? "✓" : ""}</span>
                                  <span>{formatCohortLabel(cohort)}</span>
                                </button>
                              </li>
                            );
                          })}
                        </ul>
                      ) : null}
                    </div>
                  ) : (
                    <p className="checkout-page__hint">{t("checkoutNoGroup")}</p>
                  )}

                  {course.trial_available ? (
                    <div className="checkout-page__modes">
                      <label>
                        <input type="radio" name="mode" checked={mode === "trial"} onChange={() => setMode("trial")} />
                        {t("modeTrial")}
                      </label>
                      <label>
                        <input type="radio" name="mode" checked={mode === "paid"} onChange={() => setMode("paid")} />
                        {t("modePaid")}
                      </label>
                    </div>
                  ) : null}

                  <p className="checkout-page__trial-price">
                    {mode === "trial" ? "0.00" : course.price_amount} {course.currency}
                  </p>

                  <GoldButton
                    className="GoldButton"
                    type="button"
                    size="md"
                    fullWidth
                    onClick={proceedToTrialRegistration}
                    disabled={isSelectedCohortFull}
                  >
                    {t("checkoutRegisterAndOrder")}
                  </GoldButton>

                  {socialCheckoutActions}

                  {isSelectedCohortFull ? <p className="checkout-page__error">{t("checkoutGroupFull")}</p> : null}
                  {errorText ? <p className="checkout-page__error">{errorText}</p> : null}
                </div>
              ) : trialStep === "registration" ? (
                <form className="checkout-page__form checkout-page__form--trial" onSubmit={proceedToTrialPayment}>
                  <h2 className="checkout-page__register-title">{t("checkoutRegisterTitle")}</h2>
                  <input value={firstName} onChange={(e) => setFirstName(e.target.value)} required placeholder={t("firstName")} />
                  <input value={lastName} onChange={(e) => setLastName(e.target.value)} required placeholder={t("lastName")} />
                  <input
                    value={email}
                    type="email"
                    autoComplete="email"
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    placeholder={t("email")}
                  />
                  <input
                    value={password}
                    type="password"
                    autoComplete="new-password"
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={10}
                    placeholder={t("password")}
                  />
                  <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder={t("phone")} />
                  <label className="checkout-page__checkbox checkout-page__checkbox--trial">
                    <input type="checkbox" checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)} />
                    {t("conditionsLabel")}
                  </label>
                  <GoldButton className="GoldButton" type="submit" size="md" fullWidth disabled={!canSubmit || submitting}>
                    {t("checkoutRegisterAndOrder")}
                  </GoldButton>

                  {isSelectedCohortFull ? <p className="checkout-page__error">{t("checkoutGroupFull")}</p> : null}
                  {errorText ? <p className="checkout-page__error">{errorText}</p> : null}
                </form>
              ) : (
                <div className="checkout-page__form checkout-page__form--trial">
                  <div className="checkout-page__trial-summary-box">
                    <h2>{course.title}</h2>
                    <p>{t("trialGroupText")}</p>
                    <p>{selectedCohort?.name ?? t("checkoutNoGroup")}</p>
                    <p>{`${firstName} ${lastName}`.trim()}</p>
                    <p>{email}</p>
                    {phone ? <p>{phone}</p> : null}
                    <p className="checkout-page__trial-price">
                      {mode === "trial" ? "0.00" : course.price_amount} {course.currency}
                    </p>
                  </div>
                  <GoldButton
                    type="button"
                    size="md"
                    fullWidth
                    onClick={() => submitTrialWithProvider("card")}
                    disabled={!canSubmit || submitting}
                  >
                    {t("checkoutOrderByCard")}
                  </GoldButton>
                  <PaymentMethods
                    onChoose={(nextProvider) => {
                      void submitTrialWithProvider(nextProvider);
                    }}
                  />
                  {errorText ? <p className="checkout-page__error">{errorText}</p> : null}
                </div>
              )}
            </div>
          </section>
        </>
      ) : (
        <section className="checkout-page__panel">
          <h1>{t("checkoutTitle")}</h1>
          <p>{course.title}</p>
          <div className="checkout-page__summary">
            <h2>{t("checkoutSummary")}</h2>
            <p>
              {t("checkoutType")}: {mode === "trial" ? t("typeTrial") : t("typePaid")}
            </p>
            <p>
              {t("checkoutGroup")}: {selectedCohort?.name ?? t("checkoutNoGroup")}
            </p>
            <p>
              {t("checkoutPrice")}: {mode === "trial" ? "0.00" : course.price_amount} {course.currency}
            </p>
          </div>
          <form className="checkout-page__form" onSubmit={submit}>
            {course.trial_available ? (
              <div className="checkout-page__modes">
                <label>
                  <input type="radio" name="mode" checked={mode === "trial"} onChange={() => setMode("trial")} />
                  {t("modeTrial")}
                </label>
                <label>
                  <input type="radio" name="mode" checked={mode === "paid"} onChange={() => setMode("paid")} />
                  {t("modePaid")}
                </label>
              </div>
            ) : null}

            {course.cohorts.length > 0 ? (
              <label className="checkout-page__label">
                {t("chooseGroup")}
                <select
                  value={selectedCohortId ?? ""}
                  onChange={(event) => setSelectedCohortId(Number.parseInt(event.target.value, 10) || undefined)}
                >
                  {course.cohorts.map((cohort) => (
                    <option
                      key={cohort.id}
                      value={cohort.id}
                      disabled={(cohort.seats_left ?? 1) <= 0}
                    >
                      {cohort.name} ({cohort.group_code}) -{" "}
                      {(cohort.seats_left ?? 0) > 0
                        ? `${t("cohortSeatsLeft")}: ${cohort.seats_left}`
                        : t("cohortFull")}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <p className="checkout-page__hint">{t("checkoutNoGroup")}</p>
            )}
            {isSelectedCohortFull ? <p className="checkout-page__error">{t("checkoutGroupFull")}</p> : null}

            <input value={firstName} onChange={(e) => setFirstName(e.target.value)} required placeholder={t("firstName")} />
            <input value={lastName} onChange={(e) => setLastName(e.target.value)} required placeholder={t("lastName")} />
            <input
              value={email}
              type="email"
              autoComplete="email"
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder={t("email")}
            />
            <input
              value={password}
              type="password"
              autoComplete="new-password"
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={10}
              placeholder={t("password")}
            />
            <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder={t("phone")} />
{mode === "paid" ? (
              <>
                {!isFreePaymentMode ? (
                  <div className="checkout-page__provider-grid">
                    {["paypal", "klarna", "sofort"].map((p) => (
                      <label 
                        key={p} 
                        className={`checkout-page__provider-item ${provider === p ? "is-selected" : ""}`}
                      >
                        <input 
                          type="radio" 
                          name="provider" 
                          value={p} 
                          checked={provider === p} 
                          onChange={(e) => setProvider(e.target.value as PaymentProvider)} 
                        />
                        <span>{p.charAt(0).toUpperCase() + p.slice(1)}</span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="checkout-page__hint">{t("checkoutNoPaymentRequired")}</p>
                )}
                
                <label className="checkout-page__checkbox">
                  <input 
                    type="checkbox" 
                    checked={acceptTerms} 
                    onChange={(e) => setAcceptTerms(e.target.checked)} 
                  />
                  {t("conditionsLabel")}
                </label>
              </>
            ) : null}

            <button className="checkout-page__provider-item" type="submit" disabled={!canSubmit || submitting}>
              {t("submit")}
            </button>
            {socialCheckoutActions}
            
            {errorText ? <p className="checkout-page__error">{errorText}</p> : null}
          </form>
        </section>
      )}
    </main>
  );
};
