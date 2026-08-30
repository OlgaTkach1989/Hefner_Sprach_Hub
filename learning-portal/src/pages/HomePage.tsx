import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useNavigate } from "react-router-dom"

import logo from "../assets/hefner-sprach-hub-logo.jpeg"
import { useUiPreferences } from "../context/UiPreferencesContext"
import { buildOrganizationSchema } from "../seo/schemas"
import { resolveLearnerCabinetAccess } from "../utils/learnerCabinet"
import styles from "./HomePage.module.css"

const levels = [
  {
    level: "A1",
    titleDe: "Deutsch A1",
    titleUa: "Німецька A1",
    titleRu: "Немецкий A1",
    textDe: "Absolute Anfänger: Alphabet, Begrüßungen, erste Sätze.",
    textUa: "Для початківців: алфавіт, привітання, перші речення.",
    textRu: "Для начинающих: алфавит, приветствия, первые предложения.",
  },
  {
    level: "A2",
    titleDe: "Deutsch A2",
    titleUa: "Німецька A2",
    titleRu: "Немецкий A2",
    textDe: "Alltag sicherer sprechen: Familie, Arbeit, Einkaufen, Termine.",
    textUa: "Впевненіше говорити в побуті: сім'я, робота, покупки, зустрічі.",
    textRu: "Увереннее говорить в быту: семья, работа, покупки, встречи.",
  },
  {
    level: "B1",
    titleDe: "Deutsch B1",
    titleUa: "Німецька B1",
    titleRu: "Немецкий B1",
    textDe: "Gespräche führen, Meinung ausdrücken, einfache Texte schreiben.",
    textUa: "Вести розмови, висловлювати думку, писати прості тексти.",
    textRu: "Вести разговоры, выражать мнение, писать простые тексты.",
  },
  {
    level: "B2",
    titleDe: "Deutsch B2",
    titleUa: "Німецька B2",
    titleRu: "Немецкий B2",
    textDe: "Komplexere Themen verstehen, argumentieren und beruflich kommunizieren.",
    textUa: "Розуміти складніші теми, аргументувати та спілкуватися професійно.",
    textRu: "Понимать более сложные темы, аргументировать и общаться профессионально.",
  },
  {
    level: "C1",
    titleDe: "Deutsch C1",
    titleUa: "Німецька C1",
    titleRu: "Немецкий C1",
    textDe: "Sicher, präzise und flexibel in Studium, Beruf und Alltag sprechen.",
    textUa: "Говорити впевнено, точно й гнучко для навчання, роботи та побуту.",
    textRu: "Говорить уверенно, точно и гибко для учебы, работы и быта.",
  },
  {
    level: "C2",
    titleDe: "Deutsch C2",
    titleUa: "Німецька C2",
    titleRu: "Немецкий C2",
    textDe: "Sehr fortgeschrittenes Deutsch: nuanciert verstehen und formulieren.",
    textUa: "Дуже просунутий рівень: тонко розуміти й точно формулювати.",
    textRu: "Очень продвинутый уровень: тонко понимать и точно формулировать.",
  },
]

export const HomePage = () => {
  const navigate = useNavigate()
  const { locale } = useUiPreferences()
  const [cabinetMessage, setCabinetMessage] = useState("")
  const [isCabinetBusy, setIsCabinetBusy] = useState(false)
  const isGerman = locale === "de"
  const isRussian = locale === "ru"
  const siteUrl = import.meta.env.VITE_PUBLIC_SITE_URL ?? "http://localhost:5182"
  const organizationSchema = useMemo(() => buildOrganizationSchema(siteUrl), [siteUrl])

  const copyByLocale = {
    de: {
      title: "Hefner Sprach Hub - Deutsch lernen",
      description: "Hefner Sprach Hub: Deutsch lernen Schritt für Schritt mit ukrainischer und russischer Begleitung.",
      heroLine: "Deutsch lernen - Schritt für Schritt",
      start: "Kurs starten",
      cabinet: "Mein Konto",
      wait: "Bitte warten...",
      cabinetError: "Das Konto ist momentan nicht verfügbar. Bitte versuchen Sie es erneut.",
      welcomeTitle: "Willkommen",
      teacherRole: "Sprachlehrerin",
      experience: "20 Jahre Erfahrung",
      levelsTitle: "Deutschkurse nach Niveau",
      levelsText: "Wählen Sie das passende Niveau. Weitere Kurse können später in der Admin-Panel hinzugefügt oder gelöscht werden.",
      openLevel: "Zum Kurs",
      readyTitle: "Bereit anzufangen?",
      readyText: "Der erste Kurs wartet bereits auf Sie.",
      welcomeHeading: "Willkommen bei",
      welcomeParagraphs: [
        "Mein Name ist Anna Hefner. Ich bin gebürtige Ukrainerin und lebe seit 26 Jahren in Deutschland.",
        "Aus meiner langjährigen Arbeit in internationalen Banken weiß ich, wie herausfordernd der Berufsalltag sein kann, wenn die Sprache noch nicht sicher sitzt. Genau deshalb habe ich meine Sprachschule gegründet.",
        "In meinen Kursen lernen Sie Deutsch Schritt für Schritt - mit Alphabet, Aussprache, Begrüßungen, Alltagssprache und beruflicher Kommunikation. Dabei sind mir Geduld, Verständnis und eine angenehme Lernatmosphäre besonders wichtig.",
      ],
      welcomeClosing: "Ich freue mich, dass Sie dabei sind. Willkommen im Kurs!",
    },
    uk: {
      title: "Hefner Sprach Hub - вивчення німецької",
      description: "Hefner Sprach Hub: вивчення німецької крок за кроком з українським супроводом.",
      heroLine: "Вчимо німецьку - крок за кроком",
      start: "Почати курс",
      cabinet: "Кабінет",
      wait: "Зачекайте...",
      cabinetError: "Кабінет тимчасово недоступний. Спробуйте ще раз.",
      welcomeTitle: "Ласкаво просимо",
      teacherRole: "Викладачка німецької",
      experience: "20 років досвіду",
      levelsTitle: "Курси німецької за рівнями",
      levelsText: "Оберіть потрібний рівень. Інші курси можна буде додавати або видаляти в адмін-панелі.",
      openLevel: "До курсу",
      readyTitle: "Готові почати?",
      readyText: "Перший курс вже чекає на вас.",
      welcomeHeading: "Ласкаво просимо до",
      welcomeParagraphs: [
        "Мене звати Анна Хефнер. Я народилась в Україні і вже 26 років живу в Німеччині.",
        "Завдяки багаторічній роботі в міжнародних банках я добре знаю, наскільки складним може бути професійне життя, коли мова ще не достатньо впевнена. Саме тому я створила свою мовну школу.",
        "На моїх курсах ми вчимо німецьку крок за кроком: алфавіт, вимову, привітання, повсякденну та професійну комунікацію. Для мене важливі терпіння, розуміння і приємна атмосфера навчання.",
      ],
      welcomeClosing: "Я рада, що ви тут. Ласкаво просимо на курс!",
    },
    ru: {
      title: "Hefner Sprach Hub - изучение немецкого",
      description: "Hefner Sprach Hub: изучение немецкого шаг за шагом с русскоязычным сопровождением.",
      heroLine: "Учите немецкий - шаг за шагом",
      start: "Начать курс",
      cabinet: "Кабинет",
      wait: "Подождите...",
      cabinetError: "Кабинет временно недоступен. Попробуйте еще раз.",
      welcomeTitle: "Добро пожаловать",
      teacherRole: "Преподаватель немецкого",
      experience: "20 лет опыта",
      levelsTitle: "Курсы немецкого по уровням",
      levelsText: "Выберите нужный уровень. Другие курсы можно будет добавлять или удалять в админ-панели.",
      openLevel: "К курсу",
      readyTitle: "Готовы начать?",
      readyText: "Первый курс уже ждет вас.",
      welcomeHeading: "Добро пожаловать в",
      welcomeParagraphs: [
        "Меня зовут Анна Хефнер. Я родилась в Украине и уже 26 лет живу в Германии.",
        "Благодаря многолетней работе в международных банках я хорошо понимаю, насколько сложной может быть профессиональная жизнь, когда язык еще не достаточно уверенный. Именно поэтому я создала свою языковую школу.",
        "На моих курсах мы учим немецкий шаг за шагом: алфавит, произношение, приветствия, повседневную и профессиональную коммуникацию. Для меня важны терпение, понимание и приятная атмосфера обучения.",
      ],
      welcomeClosing: "Я рада, что вы здесь. Добро пожаловать на курс!",
    },
  } as const
  const copy = copyByLocale[locale]

  const handleCabinetClick = async () => {
    if (isCabinetBusy) return

    setIsCabinetBusy(true)
    setCabinetMessage("")
    try {
      const resolution = await resolveLearnerCabinetAccess()
      if (resolution.kind === "dashboard") {
        window.location.assign(resolution.url)
        return
      }
      if (resolution.kind === "sign_in") {
        navigate(resolution.url)
        return
      }
      setCabinetMessage(resolution.message)
    } catch {
      setCabinetMessage(copy.cabinetError)
    } finally {
      setIsCabinetBusy(false)
    }
  }

  return (
    <main className={styles.homePage}>
      <Helmet>
        <title>{copy.title}</title>
        <meta name="description" content={copy.description} />
        <meta property="og:title" content="Hefner Sprach Hub" />
        <meta property="og:description" content={copy.description} />
        <meta property="og:url" content={siteUrl} />
        <meta property="og:type" content="website" />
        <link rel="canonical" href={siteUrl.replace(/\/+$/, "")} />
        <script type="application/ld+json">{JSON.stringify(organizationSchema)}</script>
      </Helmet>

      <section className={styles.hero}>
        <div className={styles.divider} aria-hidden="true"><span /></div>
        <h1>
          {copy.welcomeHeading}
          <span>Hefner Sprach Hub</span>
        </h1>
        <p className={styles.heroDe}>{copy.heroLine}</p>
        <div className={styles.heroSmallDivider} aria-hidden="true" />
        <div className={styles.heroActions}>
          <Link to="/course/deutsch-a1" className={styles.primaryAction}>
            <span aria-hidden="true">▶</span>
            {copy.start}
          </Link>
          <button type="button" className={styles.secondaryAction} onClick={() => void handleCabinetClick()}>
            {isCabinetBusy ? copy.wait : copy.cabinet}
          </button>
        </div>
        {cabinetMessage ? <p className={styles.feedback}>{cabinetMessage}</p> : null}
      </section>

      <section className={styles.welcomeCard}>
        <aside className={styles.teacherPanel}>
          <img src={logo} alt="Hefner Sprach Hub" />
          <strong>ANNA HEFNER</strong>
          <span>{copy.teacherRole}</span>
          <div className={styles.stars} aria-label="5 stars">★ ★ ★ ★ ★</div>
          <small>{copy.experience}</small>
        </aside>
        <article className={styles.welcomeCopy}>
          <div className={styles.sectionTitle}>{copy.welcomeTitle}</div>
          {copy.welcomeParagraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
          <em>{copy.welcomeClosing}</em>
        </article>
      </section>

      <section className={styles.stats} aria-label="Course facts">
        <article>
          <span>□</span>
          <strong>6</strong>
          <p>{isGerman ? "Niveaus" : isRussian ? "Уровней" : "Рівнів"}</p>
        </article>
        <article>
          <span>▷</span>
          <strong>12+</strong>
          <p>{isGerman ? "Lektionen pro Kurs" : isRussian ? "уроков в курсе" : "уроків у курсі"}</p>
        </article>
        <article>
          <span>♙</span>
          <strong>20</strong>
          <p>{isGerman ? "Jahre Erfahrung" : isRussian ? "лет опыта" : "років досвіду"}</p>
        </article>
        <article>
          <span>♢</span>
          <strong>A1-C2</strong>
          <p>{isGerman ? "Deutsch" : isRussian ? "немецкий" : "німецька"}</p>
        </article>
      </section>

      <section className={styles.levels} id="levels" aria-label={copy.levelsTitle}>
        <div className={styles.levelsHead}>
          <h2>{copy.levelsTitle}</h2>
          <p>{copy.levelsText}</p>
        </div>
        <div className={styles.levelGrid}>
          {levels.map((courseLevel) => (
            <Link
              className={styles.levelCard}
              key={courseLevel.level}
              to={`/course/deutsch-${courseLevel.level.toLowerCase()}`}
            >
              <span>{courseLevel.level}</span>
              <strong>{isGerman ? courseLevel.titleDe : isRussian ? courseLevel.titleRu : courseLevel.titleUa}</strong>
              <p>{isGerman ? courseLevel.textDe : isRussian ? courseLevel.textRu : courseLevel.textUa}</p>
              <em>{copy.openLevel} →</em>
            </Link>
          ))}
        </div>
      </section>

      <section className={styles.ready}>
        <div className={styles.divider} aria-hidden="true"><span /></div>
        <h2>{copy.readyTitle}</h2>
        <p>{copy.readyText}</p>
        <Link to="/course/deutsch-a1">{copy.openLevel} →</Link>
      </section>
    </main>
  )
}

