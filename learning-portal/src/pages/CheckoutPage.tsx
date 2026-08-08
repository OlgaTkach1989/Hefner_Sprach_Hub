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

type CheckoutPaymentChoice = PaymentProvider;

const courseLevels = [
  { level: "A1", slug: "deutsch-a1", summaryDe: "Kostenloser Probekurs für alle.", summaryUk: "Безкоштовний пробний курс для всіх.", summaryRu: "Бесплатный пробный курс для всех." },
  { level: "A2", slug: "deutsch-a2", summaryDe: "Kostenloser Testzugang für alle Module.", summaryUk: "Безкоштовний тестовий доступ до всіх модулів.", summaryRu: "Бесплатный тестовый доступ ко всем модулям." },
  { level: "B1", slug: "deutsch-b1", summaryDe: "Kostenloser Testzugang für alle Module.", summaryUk: "Безкоштовний тестовий доступ до всіх модулів.", summaryRu: "Бесплатный тестовый доступ ко всем модулям." },
  { level: "B2", slug: "deutsch-b2", summaryDe: "Kostenloser Testzugang für alle Module.", summaryUk: "Безкоштовний тестовий доступ до всіх модулів.", summaryRu: "Бесплатный тестовый доступ ко всем модулям." },
  { level: "C1", slug: "deutsch-c1", summaryDe: "Kostenloser Testzugang für alle Module.", summaryUk: "Безкоштовний тестовий доступ до всіх модулів.", summaryRu: "Бесплатный тестовый доступ ко всем модулям." },
  { level: "C2", slug: "deutsch-c2", summaryDe: "Kostenloser Testzugang für alle Module.", summaryUk: "Безкоштовний тестовий доступ до всіх модулів.", summaryRu: "Бесплатный тестовый доступ ко всем модулям." }
];

const checkoutCopy = {
  de: {
    secureBadge: "Sichere Kursbuchung",
    title: "Deutschkurs buchen",
    subtitle: "Wählen Sie Ihr Niveau, erstellen Sie Ihr Konto und buchen Sie den Kurs direkt online.",
    chooseLevel: "Niveau wählen",
    chooseLevelText: "Alle Niveaus sind in der Testversion kostenlos.",
    free: "Kostenlos",
    studentDetails: "Teilnehmerdaten",
    studentDetailsText: "Diese Daten werden für Ihr Studentenkonto und den Kurszugang verwendet.",
    chooseGroup: "Gruppe wählen",
    seatsLeft: "Freie Plätze",
    full: "Ausgebucht",
    noGroup: "Gruppe wird nach Verfügbarkeit zugewiesen.",
    groupFull: "Diese Gruppe ist aktuell ausgebucht.",
    firstName: "Vorname",
    lastName: "Nachname",
    email: "E-Mail",
    password: "Passwort",
    phone: "Telefon",
    paymentTitle: "Zahlung",
    paymentText: "Debitkarte oder Kreditkarte wählen und Zahlung starten.",
    debitCard: "Debitkarte",
    cardName: "Name auf der Karte",
    cardNumber: "Kartennummer",
    cardExpiry: "MM/JJ",
    cardCvc: "CVC",
    cardSecurity: "Kartendaten werden nicht auf diesem Server gespeichert. Die Zahlung wird über den Zahlungsanbieter abgeschlossen.",
    terms: "Ich akzeptiere die Kursbedingungen.",
    wait: "Bitte warten...",
    freeSubmit: "Kostenlos einschreiben",
    paidSubmit: "Jetzt mit Debitkarte bezahlen",
    summary: "Buchungsübersicht",
    bookingType: "Buchungstyp",
    freeCourse: "Kostenloser Probekurs",
    paidCourse: "Kostenloser Testkurs",
    group: "Gruppe",
    lessons: "Lektionen",
    price: "Preis",
    freeA1Point: "A1 ist für alle kostenlos",
    accessPoint: "Direkter Zugang nach erfolgreicher Zahlung",
    emailPoint: "Zugangsdaten per E-Mail",
    noCardPoint: "Keine Kartenzahlung für A1 nötig",
    debitPoint: "Zahlung per Debitkarte"
  },
  uk: {
    secureBadge: "Безпечне бронювання курсу",
    title: "Записатися на курс німецької",
    subtitle: "Оберіть рівень, створіть акаунт і забронюйте курс онлайн.",
    chooseLevel: "Оберіть рівень",
    chooseLevelText: "Усі рівні безкоштовні в тестовій версії.",
    free: "Безкоштовно",
    studentDetails: "Дані учасника",
    studentDetailsText: "Ці дані потрібні для вашого кабінету та доступу до курсу.",
    chooseGroup: "Оберіть групу",
    seatsLeft: "Вільні місця",
    full: "Немає місць",
    noGroup: "Групу буде призначено за наявністю місць.",
    groupFull: "У цій групі зараз немає місць.",
    firstName: "Ім'я",
    lastName: "Прізвище",
    email: "E-mail",
    password: "Пароль",
    phone: "Телефон",
    paymentTitle: "Оплата",
    paymentText: "Оберіть дебетову або кредитну картку та почніть оплату.",
    debitCard: "Дебетова картка",
    cardName: "Ім'я на картці",
    cardNumber: "Номер картки",
    cardExpiry: "MM/РР",
    cardCvc: "CVC",
    cardSecurity: "Дані картки не зберігаються на цьому сервері. Оплата завершується через платіжного провайдера.",
    terms: "Я приймаю умови курсу.",
    wait: "Зачекайте...",
    freeSubmit: "Записатися безкоштовно",
    paidSubmit: "Оплатити дебетовою карткою",
    summary: "Підсумок бронювання",
    bookingType: "Тип бронювання",
    freeCourse: "Безкоштовний пробний курс",
    paidCourse: "Безкоштовний тестовий курс",
    group: "Група",
    lessons: "Уроки",
    price: "Ціна",
    freeA1Point: "A1 безкоштовний для всіх",
    accessPoint: "Доступ після успішної оплати",
    emailPoint: "Дані доступу на e-mail",
    noCardPoint: "Для A1 картка не потрібна",
    debitPoint: "Оплата дебетовою карткою"
  },
  ru: {
    secureBadge: "Безопасное бронирование курса",
    title: "Записаться на курс немецкого",
    subtitle: "Выберите уровень, создайте аккаунт и забронируйте курс онлайн.",
    chooseLevel: "Выберите уровень",
    chooseLevelText: "Все уровни бесплатны в тестовой версии.",
    free: "Бесплатно",
    studentDetails: "Данные участника",
    studentDetailsText: "Эти данные нужны для вашего кабинета и доступа к курсу.",
    chooseGroup: "Выберите группу",
    seatsLeft: "Свободные места",
    full: "Мест нет",
    noGroup: "Группа будет назначена по наличию мест.",
    groupFull: "В этой группе сейчас нет мест.",
    firstName: "Имя",
    lastName: "Фамилия",
    email: "E-mail",
    password: "Пароль",
    phone: "Телефон",
    paymentTitle: "Оплата",
    paymentText: "Выберите дебетовую или кредитную карту и начните оплату.",
    debitCard: "Дебетовая карта",
    cardName: "Имя на карте",
    cardNumber: "Номер карты",
    cardExpiry: "MM/ГГ",
    cardCvc: "CVC",
    cardSecurity: "Данные карты не хранятся на этом сервере. Оплата завершается через платежного провайдера.",
    terms: "Я принимаю условия курса.",
    wait: "Подождите...",
    freeSubmit: "Записаться бесплатно",
    paidSubmit: "Оплатить дебетовой картой",
    summary: "Итог бронирования",
    bookingType: "Тип бронирования",
    freeCourse: "Бесплатный пробный курс",
    paidCourse: "Бесплатный тестовый курс",
    group: "Группа",
    lessons: "Уроки",
    price: "Цена",
    freeA1Point: "A1 бесплатный для всех",
    accessPoint: "Доступ после успешной оплаты",
    emailPoint: "Данные доступа на e-mail",
    noCardPoint: "Для A1 карта не нужна",
    debitPoint: "Оплата дебетовой картой"
  }
} as const;

const levelFromSlug = (slug = "deutsch-a1") => slug.toUpperCase().match(/\b(A0|A1|A2|B1|B2|C1|C2)\b/)?.[1] ?? "A1";

const lessonCountForLevel = (level: string) => (["B1", "B2", "C1", "C2"].includes(level) ? 16 : 12);

const priceForLevel = (_level: string) => {
  return "0.00";
};

const createFallbackCourse = (slug = "deutsch-a1"): CourseDetail => {
  const level = levelFromSlug(slug);

  return {
    id: 0,
    slug,
    route_slug: slug,
    title: `Deutsch ${level}`,
    short_description: `Deutsch ${level} lernen - Schritt für Schritt.`,
    lessons_count: lessonCountForLevel(level),
    trial_available: true,
    price_amount: priceForLevel(level),
    currency: "EUR",
    is_subscription: false,
    hero_image_url: null,
    geo_city: "Berlin",
    geo_country: "DE",
    description: `Deutsch ${level} - Deutsch-Ukrainischer Kurs.`,
    faq_items: [],
    cohorts: [
      {
        id: 0,
        name: "Online-Gruppe",
        group_code: `DE-${level}`,
        capacity: 12,
        seats_left: 8,
        start_date: null,
        status: "open"
      }
    ],
    seo_title: `Deutsch ${level} kaufen - Hefner Sprach Hub`,
    seo_description: `Deutsch ${level} online kaufen und direkt Zugang zum Kurs erhalten.`
  };
};

const formatCardNumber = (value: string) =>
  value
    .replace(/\D/g, "")
    .slice(0, 19)
    .replace(/(.{4})/g, "$1 ")
    .trim();

const formatExpiry = (value: string) => {
  const digits = value.replace(/\D/g, "").slice(0, 4);
  if (digits.length <= 2) return digits;
  return `${digits.slice(0, 2)}/${digits.slice(2)}`;
};

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
  const { slug: routeParamSlug } = useParams<{ slug: string }>();
  const { t } = useTranslation();
  const { locale } = useUiPreferences();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const activeSlug = routeParamSlug ?? searchParams.get("level") ?? "deutsch-a1";
  const siteUrl = import.meta.env.VITE_PUBLIC_SITE_URL ?? "http://localhost:5182";
  const paymentMode = String(import.meta.env.VITE_ONLINE_PAYMENT_MODE ?? "mock")
    .trim()
    .toLowerCase();
  const isFreePaymentMode = paymentMode === "free";
  const isTrialCheckout = activeSlug === TRIAL_ROUTE_SLUG;

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
  const [paymentChoice, setPaymentChoice] = useState<CheckoutPaymentChoice>("card");
  const [cardName, setCardName] = useState("");
  const [cardNumber, setCardNumber] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvc, setCardCvc] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [errorText, setErrorText] = useState("");
  const [trialStep, setTrialStep] = useState<"selection" | "registration" | "payment">("selection");
  const [isCohortMenuOpen, setIsCohortMenuOpen] = useState(false);
  const cohortMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchCourseBySlug(resolveCourseApiSlug(activeSlug) ?? activeSlug, locale)
      .then((data) => {
        const preferredCohortFromQuery = Number.parseInt(searchParams.get("cohort") ?? "", 10);
        const preferredCohort = Number.isFinite(preferredCohortFromQuery)
          ? data.cohorts.find((item) => item.id === preferredCohortFromQuery)
          : undefined;
        const firstCohortWithSeats = data.cohorts.find((item) => (item.seats_left ?? 1) > 0);

        setCourse({ ...decorateCourseDetail(data, activeSlug), trial_available: true, price_amount: "0.00" });
        setMode("trial");
        setSelectedCohortId(preferredCohort?.id ?? firstCohortWithSeats?.id ?? data.cohorts[0]?.id);
        setTrialStep("selection");
      })
      .catch(() => {
        const fallback = createFallbackCourse(activeSlug);
        setCourse(fallback);
        setMode(fallback.price_amount === "0.00" ? "trial" : "paid");
        setSelectedCohortId(fallback.cohorts[0]?.id);
      })
      .finally(() => setLoading(false));
  }, [activeSlug, locale, searchParams, isTrialCheckout]);

  const selectedCohort = useMemo(
    () => course?.cohorts.find((item) => item.id === selectedCohortId),
    [course, selectedCohortId]
  );
  const routeSlug = course?.route_slug ?? activeSlug;
  const currentLevel = levelFromSlug(routeSlug);
  const isFreeCourse = Number.parseFloat(course?.price_amount ?? "0") <= 0;
  const copy = locale === "de" ? checkoutCopy.de : locale === "ru" ? checkoutCopy.ru : checkoutCopy.uk;
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
    if (isTrialCheckout && !acceptTerms) return false;
    if (mode === "paid" && !isFreePaymentMode && paymentChoice === "card") {
      if (!cardName.trim()) return false;
      if (cardNumber.replace(/\D/g, "").length < 13) return false;
      if (!/^\d{2}\/\d{2}$/.test(cardExpiry)) return false;
      if (cardCvc.replace(/\D/g, "").length < 3) return false;
    }
    if (isSelectedCohortFull) return false;
    return true;
  }, [
    acceptTerms,
    cardCvc,
    cardExpiry,
    cardName,
    cardNumber,
    email,
    firstName,
    isFreePaymentMode,
    isSelectedCohortFull,
    isTrialCheckout,
    lastName,
    mode,
    password,
    paymentChoice
  ]);

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
          provider: providerOverride ?? paymentChoice,
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
      card: "card",
      klarna: "klarna",
      sofort: "sofort",
      paypal: "paypal"
    };
    setPaymentChoice(uiProvider === "card" ? "card" : providerMap[uiProvider]);
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
        <section className="checkout-page__purchase">
          <div className="checkout-page__purchase-hero">
            <span>{copy.secureBadge}</span>
            <h1>{copy.title}</h1>
            <p>{copy.subtitle}</p>
          </div>
          <form className="checkout-page__form" onSubmit={submit}>
            <div className="checkout-page__level-picker" aria-label={copy.chooseLevel}>
              <div className="checkout-page__form-section">
                <h2>{copy.chooseLevel}</h2>
                <p>{copy.chooseLevelText}</p>
              </div>
              <div className="checkout-page__level-grid">
                {courseLevels.map((item) => {
                  const isActive = item.slug === routeSlug;
                  return (
                    <button
                      type="button"
                      key={item.slug}
                      className={`checkout-page__level-card${isActive ? " is-selected" : ""}`}
                      onClick={() => {
                        if (!isActive) navigate(`/checkout/${item.slug}`);
                      }}
                    >
                      <span>{item.level}</span>
                      <strong>{`Deutsch ${item.level}`}</strong>
                      <small>{locale === "de" ? item.summaryDe : locale === "ru" ? item.summaryRu : item.summaryUk}</small>
                      <em>{copy.free}</em>
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="checkout-page__form-section">
              <h2>{copy.studentDetails}</h2>
              <p>{copy.studentDetailsText}</p>
            </div>
            {course.trial_available && !isFreeCourse ? (
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
                {copy.chooseGroup}
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
                        ? `${copy.seatsLeft}: ${cohort.seats_left}`
                        : copy.full}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <p className="checkout-page__hint">{copy.noGroup}</p>
            )}
            {isSelectedCohortFull ? <p className="checkout-page__error">{copy.groupFull}</p> : null}

            <div className="checkout-page__field-grid">
              <input value={firstName} onChange={(e) => setFirstName(e.target.value)} required placeholder={copy.firstName} />
              <input value={lastName} onChange={(e) => setLastName(e.target.value)} required placeholder={copy.lastName} />
            </div>
            <input value={email} type="email" autoComplete="email" onChange={(e) => setEmail(e.target.value)} required placeholder={copy.email} />
            <input value={password} type="password" autoComplete="new-password" onChange={(e) => setPassword(e.target.value)} required minLength={10} placeholder={copy.password} />
            <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder={copy.phone} />
            {mode === "paid" ? (
              <>
                {!isFreePaymentMode ? (
                  <div className="checkout-page__payment-box">
                    <div className="checkout-page__form-section">
                      <h2>{copy.paymentTitle}</h2>
                      <p>{copy.paymentText}</p>
                    </div>
                    <div className="checkout-page__provider-grid">
                    {(["card", "paypal", "klarna", "sofort"] as CheckoutPaymentChoice[]).map((p) => (
                      <label 
                        key={p} 
                        className={`checkout-page__provider-item ${paymentChoice === p ? "is-selected" : ""}`}
                      >
                        <input 
                          type="radio" 
                          name="provider" 
                          value={p} 
                          checked={paymentChoice === p} 
                          onChange={(e) => setPaymentChoice(e.target.value as CheckoutPaymentChoice)} 
                        />
                        <span>{p === "card" ? copy.debitCard : p.charAt(0).toUpperCase() + p.slice(1)}</span>
                      </label>
                    ))}
                    </div>
                    {paymentChoice === "card" ? (
                      <div className="checkout-page__card-fields">
                        <input value={cardName} onChange={(e) => setCardName(e.target.value)} autoComplete="cc-name" placeholder={copy.cardName} required={mode === "paid" && paymentChoice === "card"} />
                        <input value={cardNumber} onChange={(e) => setCardNumber(formatCardNumber(e.target.value))} inputMode="numeric" autoComplete="cc-number" placeholder={copy.cardNumber} required={mode === "paid" && paymentChoice === "card"} />
                        <div className="checkout-page__field-grid checkout-page__field-grid--compact">
                          <input value={cardExpiry} onChange={(e) => setCardExpiry(formatExpiry(e.target.value))} inputMode="numeric" autoComplete="cc-exp" placeholder={copy.cardExpiry} required={mode === "paid" && paymentChoice === "card"} />
                          <input value={cardCvc} onChange={(e) => setCardCvc(e.target.value.replace(/\D/g, "").slice(0, 4))} inputMode="numeric" autoComplete="cc-csc" placeholder={copy.cardCvc} required={mode === "paid" && paymentChoice === "card"} />
                        </div>
                        <p className="checkout-page__security-note">{copy.cardSecurity}</p>
                      </div>
                    ) : null}
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
                  {copy.terms}
                </label>
              </>
            ) : null}

            <button className="checkout-page__submit" type="submit" disabled={!canSubmit || submitting}>
              {submitting ? copy.wait : isFreeCourse ? copy.freeSubmit : copy.paidSubmit}
            </button>
            
            {errorText ? <p className="checkout-page__error">{errorText}</p> : null}
          </form>
          <aside className="checkout-page__order-summary" aria-label={copy.summary}>
            <h2>{copy.summary}</h2>
            <strong>{course.title}</strong>
            <p>{course.short_description}</p>
            <dl>
              <div>
                <dt>{copy.bookingType}</dt>
                <dd>{isFreeCourse ? copy.freeCourse : copy.paidCourse}</dd>
              </div>
              <div>
                <dt>{copy.group}</dt>
                <dd>{selectedCohort?.name ?? copy.noGroup}</dd>
              </div>
              <div>
                <dt>{copy.lessons}</dt>
                <dd>{course.lessons_count}</dd>
              </div>
            </dl>
            <div className="checkout-page__total">
              <span>{copy.price}</span>
              <strong>{mode === "trial" ? "0.00" : course.price_amount} {course.currency}</strong>
            </div>
            <ul>
              <li>{currentLevel === "A1" ? copy.freeA1Point : copy.accessPoint}</li>
              <li>{copy.emailPoint}</li>
              <li>{isFreeCourse ? copy.noCardPoint : copy.debitPoint}</li>
            </ul>
          </aside>
        </section>
      )}
    </main>
  );
};

