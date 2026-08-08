import type { ReactNode } from "react"
import { useMemo, useState } from "react"
import { Link, Navigate, useParams } from "react-router-dom"

import { AnnaAssistant } from "../components/anna/AnnaAssistant"
import logo from "../assets/hefner-sprach-hub-logo.jpeg"
import { getCourseProgress, isLessonAccessible, isLessonCompleted, saveLessonProgress } from "../utils/courseProgress"
import "./CourseLessonPage.css"

type LessonSection =
  | { kind: "text"; title?: string; lines: string[] }
  | { kind: "list"; title: string; items: string[] }
  | { kind: "table"; title: string; headers: string[]; rows: string[][] }

type FillTask = {
  answer: string
  sentenceAfter: string
  sentenceBefore: string
  translation: string
}

type ExamQuestion = {
  answer: string
  options: string[]
  prompt: string
}

type LessonContent = {
  exam?: ExamQuestion[]
  fillTasks?: FillTask[]
  mode: "theory" | "practice" | "exam"
  moduleNumber: number
  sections?: LessonSection[]
  subtitle: string
  title: string
  videoUrl?: string
  wordBank?: string[]
}

const videoUrls = {
  basics: "https://www.youtube-nocookie.com/embed/videoseries?list=PLF9mJC4RrjIhS4MMm0x72-qWEn1LRvPuW",
  grammar: "https://www.youtube-nocookie.com/embed/videoseries?list=PLF9mJC4RrjIgJFl418R-1xwz4KDX53XoN",
}

const getGermanSpeechText = (value: string) => {
  const germanPart = value.split("→")[0].trim()
  if (!germanPart || /[А-Яа-яЁёІіЇїЄєҐґ]/.test(germanPart)) return ""
  if (!/[A-Za-zÄÖÜäöüß]/.test(germanPart)) return ""
  return germanPart.replace(/^nicht:\s*|^kein:\s*/i, "").trim()
}

const speakGerman = (value: string) => {
  const text = getGermanSpeechText(value)
  if (!text || typeof window === "undefined" || !("speechSynthesis" in window)) return

  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  const voices = window.speechSynthesis.getVoices()
  const preferredVoice = voices.find((voice) => voice.lang.toLowerCase().startsWith("de") && voice.name.toLowerCase().includes("google"))
    ?? voices.find((voice) => voice.lang.toLowerCase().startsWith("de"))

  utterance.lang = "de-DE"
  utterance.rate = 0.82
  utterance.pitch = 1
  if (preferredVoice) utterance.voice = preferredVoice
  window.speechSynthesis.speak(utterance)
}

const SpeakableText = ({ children, value }: { children?: ReactNode; value: string }) => {
  const speechText = getGermanSpeechText(value)

  if (!speechText) return <span>{children ?? value}</span>

  return (
    <button className="course-speak-button" type="button" onClick={() => speakGerman(value)} title={`Anhören: ${speechText}`}>
      <span>{children ?? value}</span>
      <small aria-hidden="true">🔊</small>
    </button>
  )
}

const a1Lessons: Record<number, LessonContent> = {
  1: {
    mode: "theory",
    moduleNumber: 1,
    title: "Modul 1 · Unterricht 1: Video + Theorie",
    subtitle: "Привітання, знайомство, займенники та sein",
    videoUrl: videoUrls.basics,
    sections: [
      {
        kind: "table",
        title: "Vokabeln / Словник",
        headers: ["Deutsch", "Українська"],
        rows: [
          ["Hallo", "Привіт"],
          ["Guten Morgen", "Доброго ранку"],
          ["Guten Tag", "Добрий день"],
          ["Guten Abend", "Добрий вечір"],
          ["Tschüss", "Бувай"],
          ["Auf Wiedersehen", "До побачення"],
          ["Danke", "Дякую"],
          ["Bitte", "Будь ласка"],
        ],
      },
      {
        kind: "table",
        title: "Personalpronomen + sein",
        headers: ["Person", "Verb"],
        rows: [
          ["ich", "bin"],
          ["du", "bist"],
          ["er/sie/es", "ist"],
          ["wir", "sind"],
          ["ihr", "seid"],
          ["sie/Sie", "sind"],
        ],
      },
    ],
  },
  2: {
    mode: "practice",
    moduleNumber: 1,
    title: "Modul 1 · Unterricht 2: Praktische Aufgabe",
    subtitle: "Вставте правильне слово в речення",
    wordBank: ["heiße", "bin", "komme", "wohne", "Guten Tag"],
    fillTasks: [
      { sentenceBefore: "", answer: "Guten Tag", sentenceAfter: ", Frau Hefner!", translation: "Добрий день, пані Хефнер!" },
      { sentenceBefore: "Ich ", answer: "heiße", sentenceAfter: " Olena.", translation: "Мене звати Олена." },
      { sentenceBefore: "Ich ", answer: "bin", sentenceAfter: " aus der Ukraine.", translation: "Я з України." },
      { sentenceBefore: "Ich ", answer: "wohne", sentenceAfter: " in Deutschland.", translation: "Я живу в Німеччині." },
    ],
  },
  3: {
    mode: "exam",
    moduleNumber: 1,
    title: "Modul 1 · Unterricht 3: Prüfung",
    subtitle: "Перевірка знань після першого модуля",
    exam: [
      { prompt: "Як сказати 'Добрий ранок' німецькою?", options: ["Guten Abend", "Guten Morgen", "Auf Wiedersehen"], answer: "Guten Morgen" },
      { prompt: "Яка форма sein підходить до ich?", options: ["bin", "bist", "ist"], answer: "bin" },
      { prompt: "Як перекласти 'Ich heiße Olena'?", options: ["Я живу в Олени", "Мене звати Олена", "Я з України"], answer: "Мене звати Олена" },
    ],
  },
  4: {
    mode: "theory",
    moduleNumber: 2,
    title: "Modul 2 · Unterricht 1: Video + Theorie",
    subtitle: "Артиклі, іменники, Akkusativ та відокремлювані дієслова",
    videoUrl: videoUrls.grammar,
    sections: [
      {
        kind: "table",
        title: "Artikel und Nomen",
        headers: ["Deutsch", "Українська"],
        rows: [
          ["der Mann", "чоловік"],
          ["die Frau", "жінка"],
          ["das Kind", "дитина"],
          ["ein Buch", "книга"],
        ],
      },
      {
        kind: "table",
        title: "Akkusativ",
        headers: ["Nominativ", "Akkusativ"],
        rows: [["der", "den"], ["die", "die"], ["das", "das"], ["die", "die"]],
      },
      {
        kind: "list",
        title: "Trennbare Verben",
        items: ["Ich stehe um 7 Uhr auf. → Я встаю о 7 годині.", "Er ruft seine Mutter an. → Він телефонує своїй мамі."],
      },
    ],
  },
  5: {
    mode: "practice",
    moduleNumber: 2,
    title: "Modul 2 · Unterricht 2: Praktische Aufgabe",
    subtitle: "Вставте артикль або дієслово",
    wordBank: ["den", "ein", "kauft", "steht", "ruft"],
    fillTasks: [
      { sentenceBefore: "Ich kaufe ", answer: "den", sentenceAfter: " Kaffee.", translation: "Я купую каву." },
      { sentenceBefore: "Sie liest ", answer: "ein", sentenceAfter: " Buch.", translation: "Вона читає книгу." },
      { sentenceBefore: "Anna ", answer: "kauft", sentenceAfter: " Brot.", translation: "Анна купує хліб." },
      { sentenceBefore: "Er ", answer: "ruft", sentenceAfter: " seine Mutter an.", translation: "Він телефонує своїй мамі." },
    ],
  },
  6: {
    mode: "exam",
    moduleNumber: 2,
    title: "Modul 2 · Unterricht 3: Prüfung",
    subtitle: "Перевірка знань: Artikel, Akkusativ, trennbare Verben",
    exam: [
      { prompt: "Що стає з der в Akkusativ?", options: ["der", "den", "dem"], answer: "den" },
      { prompt: "Який артикль у '___ Frau'?", options: ["der", "die", "das"], answer: "die" },
      { prompt: "Де стоїть префікс у реченні з aufstehen?", options: ["на початку", "після підмета", "у кінці речення"], answer: "у кінці речення" },
    ],
  },
  7: {
    mode: "theory",
    moduleNumber: 3,
    title: "Modul 3 · Unterricht 1: Video + Theorie",
    subtitle: "Модальні дієслова, Dativ, час і повсякденне життя",
    videoUrl: videoUrls.grammar,
    sections: [
      {
        kind: "list",
        title: "Modalverben",
        items: ["Ich kann Deutsch sprechen. → Я можу говорити німецькою.", "Ich will Kaffee trinken. → Я хочу пити каву.", "Ich muss arbeiten. → Я мушу працювати."],
      },
      {
        kind: "table",
        title: "Dativ",
        headers: ["Nominativ", "Dativ"],
        rows: [["der", "dem"], ["die", "der"], ["das", "dem"]],
      },
      {
        kind: "table",
        title: "Wochentage",
        headers: ["Deutsch", "Українська"],
        rows: [["Montag", "понеділок"], ["Dienstag", "вівторок"], ["Mittwoch", "середа"], ["Donnerstag", "четвер"], ["Freitag", "п'ятниця"]],
      },
    ],
  },
  8: {
    mode: "practice",
    moduleNumber: 3,
    title: "Modul 3 · Unterricht 2: Praktische Aufgabe",
    subtitle: "Вставте модальне дієслово, Dativ або час",
    wordBank: ["kann", "muss", "dem", "am Montag", "um 8 Uhr"],
    fillTasks: [
      { sentenceBefore: "Ich ", answer: "kann", sentenceAfter: " Deutsch sprechen.", translation: "Я можу говорити німецькою." },
      { sentenceBefore: "Ich helfe ", answer: "dem", sentenceAfter: " Mann.", translation: "Я допомагаю чоловікові." },
      { sentenceBefore: "Wir lernen ", answer: "am Montag", sentenceAfter: ".", translation: "Ми навчаємося в понеділок." },
      { sentenceBefore: "Der Kurs beginnt ", answer: "um 8 Uhr", sentenceAfter: ".", translation: "Курс починається о 8 годині." },
    ],
  },
  9: {
    mode: "exam",
    moduleNumber: 3,
    title: "Modul 3 · Unterricht 3: Prüfung",
    subtitle: "Перевірка знань: Modalverben, Dativ, Zeit",
    exam: [
      { prompt: "Де стоїть інфінітив з модальним дієсловом?", options: ["на початку", "у кінці", "перед підметом"], answer: "у кінці" },
      { prompt: "Яка форма Dativ для der?", options: ["den", "dem", "die"], answer: "dem" },
      { prompt: "Як сказати 'у понеділок'?", options: ["am Montag", "um Montag", "im Montag"], answer: "am Montag" },
    ],
  },
  10: {
    mode: "theory",
    moduleNumber: 4,
    title: "Modul 4 · Unterricht 1: Video + Theorie",
    subtitle: "Perfekt, поєднання речень і самопрезентація",
    videoUrl: videoUrls.grammar,
    sections: [
      {
        kind: "list",
        title: "Perfekt",
        items: ["Ich habe gearbeitet. → Я працював/працювала.", "Ich bin gekommen. → Я прийшов/прийшла."],
      },
      {
        kind: "list",
        title: "Satzverbindungen",
        items: ["Ich lerne Deutsch und arbeite. → Я вивчаю німецьку і працюю.", "Ich bin müde, aber ich lerne. → Я втомлений, але навчаюся."],
      },
      {
        kind: "text",
        title: "Selbstvorstellung",
        lines: ["Hallo!", "Ich heiße Olena.", "Ich komme aus der Ukraine.", "Ich wohne in Deutschland.", "Ich lerne Deutsch."],
      },
    ],
  },
  11: {
    mode: "practice",
    moduleNumber: 4,
    title: "Modul 4 · Unterricht 2: Praktische Aufgabe",
    subtitle: "Вставте слово для Perfekt або поєднання речень",
    wordBank: ["habe", "bin", "und", "aber", "weil"],
    fillTasks: [
      { sentenceBefore: "Ich ", answer: "habe", sentenceAfter: " gearbeitet.", translation: "Я працював/працювала." },
      { sentenceBefore: "Ich ", answer: "bin", sentenceAfter: " gekommen.", translation: "Я прийшов/прийшла." },
      { sentenceBefore: "Ich lerne Deutsch ", answer: "und", sentenceAfter: " arbeite.", translation: "Я вивчаю німецьку і працюю." },
      { sentenceBefore: "Ich lerne Deutsch, ", answer: "weil", sentenceAfter: " ich in Deutschland arbeite.", translation: "Я вивчаю німецьку, тому що працюю в Німеччині." },
    ],
  },
  12: {
    mode: "exam",
    moduleNumber: 4,
    title: "Modul 4 · Unterricht 3: Abschlussprüfung A1",
    subtitle: "Фінальна перевірка знань",
    exam: [
      { prompt: "Який допоміжний дієслово у 'Ich ___ gearbeitet'?", options: ["bin", "habe", "ist"], answer: "habe" },
      { prompt: "Як сказати 'Я прийшов/прийшла'?", options: ["Ich habe gekommen", "Ich bin gekommen", "Ich ist gekommen"], answer: "Ich bin gekommen" },
      { prompt: "Яке слово означає 'і'?", options: ["aber", "weil", "und"], answer: "und" },
      { prompt: "Оберіть правильну самопрезентацію", options: ["Ich heiße Olena.", "Ich Olena heiße.", "Heiße ich Olena."], answer: "Ich heiße Olena." },
    ],
  },
}

const addFillTasks = (lessonNumber: number, words: string[], tasks: FillTask[]) => {
  const lesson = a1Lessons[lessonNumber]
  if (!lesson) return
  lesson.wordBank = Array.from(new Set([...(lesson.wordBank ?? []), ...words]))
  lesson.fillTasks = [...(lesson.fillTasks ?? []), ...tasks]
}

const addExamQuestions = (lessonNumber: number, questions: ExamQuestion[]) => {
  const lesson = a1Lessons[lessonNumber]
  if (!lesson) return
  lesson.exam = [...(lesson.exam ?? []), ...questions]
}

const levelFromSlug = (slug = "deutsch-a1") => slug.toUpperCase().match(/\b(A0|A1|A2|B1|B2|C1|C2)\b/)?.[1] ?? "A1"

const buildGenericLesson = (slug: string, lessonNumber: number): LessonContent => {
  const level = levelFromSlug(slug)
  const moduleNumber = Math.max(1, Math.ceil(lessonNumber / 3))
  const lessonKindIndex = ((lessonNumber - 1) % 3) + 1
  const moduleTopics: Record<number, string> = {
    1: "Einstieg und Wiederholung",
    2: "Grammatik und Satzbau",
    3: "Alltag, Beruf und Dialoge",
    4: "Prüfungsvorbereitung und Abschluss",
    5: "Vertiefung und freies Sprechen",
    6: "Finale Aufgaben",
  }
  const topic = moduleTopics[moduleNumber] ?? "Kursmodul"

  if (lessonKindIndex === 1) {
    return {
      mode: "theory",
      moduleNumber,
      title: `Deutsch ${level} · Modul ${moduleNumber} · Unterricht ${lessonNumber}: Video + Theorie`,
      subtitle: `${topic}: Wortschatz, Beispiele und klare Erklärung`,
      videoUrl: videoUrls.grammar,
      sections: [
        {
          kind: "list",
          title: "Lernziele",
          items: [
            `Ich kann zentrale Strukturen für Deutsch ${level} erkennen.`,
            "Ich verstehe Beispielsätze und kann sie laut üben.",
            "Ich bereite mich auf die praktische Aufgabe vor.",
          ],
        },
        {
          kind: "table",
          title: "Beispiele",
          headers: ["Deutsch", "Bedeutung"],
          rows: [
            ["Ich lerne Deutsch.", "Lernen und Alltag"],
            ["Ich möchte sicher sprechen.", "Ziel ausdrücken"],
            ["Können Sie das bitte wiederholen?", "Rückfrage im Unterricht"],
          ],
        },
      ],
    }
  }

  if (lessonKindIndex === 2) {
    return {
      mode: "practice",
      moduleNumber,
      title: `Deutsch ${level} · Modul ${moduleNumber} · Unterricht ${lessonNumber}: Praktische Aufgabe`,
      subtitle: "Setzen Sie das passende Wort ein.",
      wordBank: ["lerne", "spreche", "verstehe", "wiederholen", "bitte"],
      fillTasks: [
        { sentenceBefore: "Ich ", answer: "lerne", sentenceAfter: " Deutsch.", translation: "Lernaktivität ausdrücken." },
        { sentenceBefore: "Ich ", answer: "spreche", sentenceAfter: " jeden Tag.", translation: "Sprechtraining beschreiben." },
        { sentenceBefore: "Ich ", answer: "verstehe", sentenceAfter: " die Aufgabe.", translation: "Verständnis ausdrücken." },
        { sentenceBefore: "Können Sie das ", answer: "wiederholen", sentenceAfter: "?", translation: "Rückfrage im Unterricht." },
      ],
    }
  }

  return {
    mode: "exam",
    moduleNumber,
    title: `Deutsch ${level} · Modul ${moduleNumber} · Unterricht ${lessonNumber}: Prüfung`,
    subtitle: "Kurzer Test für den aktuellen Abschnitt.",
    exam: [
      { prompt: "Welche Form ist richtig?", options: ["Ich lerne Deutsch.", "Ich Deutsch lerne.", "Ich lernen Deutsch."], answer: "Ich lerne Deutsch." },
      { prompt: "Welche Frage passt im Unterricht?", options: ["Können Sie das bitte wiederholen?", "Ich bin Kaffee.", "Morgen gut."], answer: "Können Sie das bitte wiederholen?" },
      { prompt: "Was bedeutet 'Ich verstehe die Aufgabe'?", options: ["Ich verstehe die Aufgabe.", "Ich kaufe Brot.", "Ich schlafe."], answer: "Ich verstehe die Aufgabe." },
    ],
  }
}

addFillTasks(2, ["lerne", "spreche", "Danke", "komme"], [
  { sentenceBefore: "Ich ", answer: "komme", sentenceAfter: " aus Kyjiw.", translation: "Ich sage meine Herkunft." },
  { sentenceBefore: "Ich ", answer: "lerne", sentenceAfter: " Deutsch.", translation: "Ich sage, was ich lerne." },
  { sentenceBefore: "Ich ", answer: "spreche", sentenceAfter: " Ukrainisch.", translation: "Ich sage, welche Sprache ich spreche." },
  { sentenceBefore: "", answer: "Danke", sentenceAfter: " und auf Wiedersehen.", translation: "Ich beende ein Gespräch freundlich." },
])

addExamQuestions(3, [
  { prompt: "Welche Antwort passt zu 'Wie heißen Sie?'", options: ["Ich heiße Anna.", "Ich wohne Berlin.", "Guten Abend."], answer: "Ich heiße Anna." },
  { prompt: "Welche Form passt: du ___?", options: ["bin", "bist", "sind"], answer: "bist" },
  { prompt: "Welche Form passt: wir ___?", options: ["sind", "seid", "ist"], answer: "sind" },
  { prompt: "Was bedeutet 'Ich wohne in Deutschland'?", options: ["Ich lebe in Deutschland.", "Ich lerne Deutsch.", "Ich komme morgen."], answer: "Ich lebe in Deutschland." },
  { prompt: "Welche Begrüßung passt am Abend?", options: ["Guten Morgen", "Guten Abend", "Danke"], answer: "Guten Abend" },
])

addFillTasks(5, ["die", "das", "auf", "sieht"], [
  { sentenceBefore: "Ich sehe ", answer: "die", sentenceAfter: " Frau.", translation: "Akkusativ mit feminin bleibt die." },
  { sentenceBefore: "Das ist ", answer: "das", sentenceAfter: " Kind.", translation: "Neutrum mit das." },
  { sentenceBefore: "Er ", answer: "sieht", sentenceAfter: " den Mann.", translation: "Verb + Akkusativ." },
  { sentenceBefore: "Ich stehe um 6 Uhr ", answer: "auf", sentenceAfter: ".", translation: "Trennbares Verb: auf steht am Ende." },
])

addExamQuestions(6, [
  { prompt: "Welche Form ist richtig?", options: ["Ich kaufe den Kaffee.", "Ich kaufe der Kaffee.", "Ich kaufe dem Kaffee."], answer: "Ich kaufe den Kaffee." },
  { prompt: "Welcher Artikel passt: ___ Kind?", options: ["der", "die", "das"], answer: "das" },
  { prompt: "Was ist trennbar?", options: ["aufstehen", "lernen", "wohnen"], answer: "aufstehen" },
  { prompt: "Welche Satzstellung ist richtig?", options: ["Ich stehe um 7 Uhr auf.", "Ich auf stehe um 7 Uhr.", "Ich stehe auf um 7 Uhr."], answer: "Ich stehe um 7 Uhr auf." },
  { prompt: "Welche Form passt: Ich sehe ___ Mann.", options: ["der", "den", "dem"], answer: "den" },
])

addFillTasks(8, ["will", "der", "am Freitag", "heute"], [
  { sentenceBefore: "Ich ", answer: "will", sentenceAfter: " Tee trinken.", translation: "Modalverb + Infinitiv am Ende." },
  { sentenceBefore: "Ich helfe ", answer: "der", sentenceAfter: " Frau.", translation: "Dativ feminin: der Frau." },
  { sentenceBefore: "Wir sprechen ", answer: "am Freitag", sentenceAfter: ".", translation: "Zeitangabe mit am." },
  { sentenceBefore: "Ich muss ", answer: "heute", sentenceAfter: " arbeiten.", translation: "Zeitangabe im Alltag." },
])

addExamQuestions(9, [
  { prompt: "Welche Form ist richtig?", options: ["Ich kann Deutsch sprechen.", "Ich kann spreche Deutsch.", "Ich kann Deutsch spreche."], answer: "Ich kann Deutsch sprechen." },
  { prompt: "Was bedeutet 'Ich muss arbeiten'?", options: ["Ich muss arbeiten.", "Ich will schlafen.", "Ich darf frei haben."], answer: "Ich muss arbeiten." },
  { prompt: "Welche Dativ-Form passt: Ich helfe ___ Frau.", options: ["die", "der", "den"], answer: "der" },
  { prompt: "Welche Frage passt zur Zeit?", options: ["Wann beginnt der Kurs?", "Wie heißt du?", "Wo wohnst du?"], answer: "Wann beginnt der Kurs?" },
  { prompt: "Wie sagt man 'am Freitag'?", options: ["on Friday", "at 8 o'clock", "in Berlin"], answer: "on Friday" },
])

addFillTasks(11, ["gearbeitet", "gekommen", "gelernt"], [
  { sentenceBefore: "Ich habe Deutsch ", answer: "gelernt", sentenceAfter: ".", translation: "Perfekt mit haben." },
  { sentenceBefore: "Ich bin nach Berlin ", answer: "gekommen", sentenceAfter: ".", translation: "Perfekt mit sein bei Bewegung." },
  { sentenceBefore: "Ich habe viel ", answer: "gearbeitet", sentenceAfter: ".", translation: "Perfekt im Alltag." },
  { sentenceBefore: "Ich bin müde, ", answer: "aber", sentenceAfter: " ich lerne.", translation: "Satzverbindung mit aber." },
])

addExamQuestions(12, [
  { prompt: "Welche Perfekt-Form ist richtig?", options: ["Ich habe gelernt.", "Ich bin gelernt.", "Ich gelernt habe."], answer: "Ich habe gelernt." },
  { prompt: "Welche Perfekt-Form nutzt 'sein'?", options: ["Ich bin gekommen.", "Ich habe gearbeitet.", "Ich habe gelernt."], answer: "Ich bin gekommen." },
  { prompt: "Welche Verbindung bedeutet 'aber'?", options: ["aber", "und", "weil"], answer: "aber" },
  { prompt: "Welche Verbindung erklärt einen Grund?", options: ["weil", "und", "aber"], answer: "weil" },
  { prompt: "Welche Frage passt zur Vorstellung?", options: ["Wie heißen Sie?", "Wann beginnt der Kurs?", "Wie viel kostet das?"], answer: "Wie heißen Sie?" },
  { prompt: "Welche Antwort ist A1-korrekt?", options: ["Ich komme aus der Ukraine.", "Ich aus Ukraine komme.", "Ich kommen aus der Ukraine."], answer: "Ich komme aus der Ukraine." },
])

const FillPractice = ({
  courseSlug,
  lessonNumber,
  tasks,
  wordBank,
}: {
  courseSlug: string
  lessonNumber: number
  tasks: FillTask[]
  wordBank: string[]
}) => {
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [saved, setSaved] = useState(false)
  const allAnswered = tasks.every((_, index) => Boolean(answers[index]))
  const score = tasks.filter((task, index) => answers[index] === task.answer).length
  const saveResult = () => {
    saveLessonProgress(courseSlug, lessonNumber, { score, total: tasks.length })
    setSaved(true)
  }

  return (
    <section className="course-lesson-section">
      <h2>Interaktive Aufgabe · Інтерактивне завдання</h2>
      <div className="course-word-bank">
        {wordBank.map((word) => (
          <button key={word} type="button" onClick={() => speakGerman(word)}>
            {word}
            <span aria-hidden="true">🔊</span>
          </button>
        ))}
      </div>
      <div className="course-fill-list">
        {tasks.map((task, index) => {
          const value = answers[index] ?? ""
          const isCorrect = value === task.answer
          return (
            <label className={`course-fill-task${value ? (isCorrect ? " is-correct" : " is-wrong") : ""}`} key={`${task.sentenceBefore}-${task.answer}`}>
              <span>
                <SpeakableText value={`${task.sentenceBefore}${task.answer}${task.sentenceAfter}`}>
                  {task.sentenceBefore}
                </SpeakableText>
                <select value={value} onChange={(event) => setAnswers((current) => ({ ...current, [index]: event.target.value }))}>
                  <option value="">...</option>
                  {wordBank.map((word) => <option key={word} value={word}>{word}</option>)}
                </select>
                <SpeakableText value={`${task.sentenceBefore}${task.answer}${task.sentenceAfter}`}>
                  {task.sentenceAfter}
                </SpeakableText>
              </span>
              <small>{task.translation}</small>
            </label>
          )
        })}
      </div>
      <div className="course-result-actions">
        <strong className="course-score">{allAnswered ? `Результат: ${score}/${tasks.length}` : "Заполните все пропуски"}</strong>
        <button type="button" disabled={!allAnswered} onClick={saveResult}>
          {saved ? "Результат сохранен" : "Завершить урок"}
        </button>
        {saved ? <Link to={`/course/${courseSlug}`}>К шкале результата</Link> : null}
      </div>
    </section>
  )
}

const ExamPractice = ({ courseSlug, lessonNumber, questions }: { courseSlug: string; lessonNumber: number; questions: ExamQuestion[] }) => {
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [saved, setSaved] = useState(false)
  const allAnswered = questions.every((_, index) => Boolean(answers[index]))
  const score = questions.filter((question, index) => answers[index] === question.answer).length
  const saveResult = () => {
    saveLessonProgress(courseSlug, lessonNumber, { score, total: questions.length })
    setSaved(true)
  }

  return (
    <section className="course-lesson-section">
      <h2>Prüfung · Екзамен</h2>
      <div className="course-exam-list">
        {questions.map((question, index) => (
          <fieldset className="course-exam-question" key={question.prompt}>
            <legend>{index + 1}. {question.prompt}</legend>
            {question.options.map((option) => {
              const selected = answers[index] === option
              const checked = Boolean(answers[index])
              const correct = option === question.answer
              return (
                <button
                  className={`${selected ? "is-selected" : ""}${checked && correct ? " is-correct" : ""}${selected && !correct ? " is-wrong" : ""}`}
                  key={option}
                  type="button"
                  onClick={() => setAnswers((current) => ({ ...current, [index]: option }))}
                >
                  <SpeakableText value={option}>{option}</SpeakableText>
                </button>
              )
            })}
          </fieldset>
        ))}
      </div>
      <div className="course-result-actions">
        <strong className="course-score">{allAnswered ? `Екзамен: ${score}/${questions.length}` : "Выберите ответы"}</strong>
        <button type="button" disabled={!allAnswered} onClick={saveResult}>
          {saved ? "Результат сохранен" : "Завершить урок"}
        </button>
        {saved ? <Link to={`/course/${courseSlug}`}>К шкале результата</Link> : null}
      </div>
    </section>
  )
}

export const CourseLessonPage = () => {
  const { slug = "deutsch-a1", lessonNumber = "1" } = useParams<{ slug: string; lessonNumber: string }>()
  const currentLessonNumber = Number(lessonNumber)
  const lesson = slug.includes("a1") ? a1Lessons[currentLessonNumber] : buildGenericLesson(slug, currentLessonNumber)
  const courseProgress = useMemo(() => getCourseProgress(slug), [slug])
  const lessonAlreadyCompleted = isLessonCompleted(courseProgress, currentLessonNumber)
  const lessonCanOpen = isLessonAccessible(courseProgress, currentLessonNumber)
  const [theorySaved, setTheorySaved] = useState(lessonAlreadyCompleted)
  const modeLabel = useMemo(() => {
    if (!lesson) return ""
    if (lesson.mode === "theory") return "Video + Theorie"
    if (lesson.mode === "practice") return "Praktische Aufgabe"
    return "Prüfung"
  }, [lesson])

  if (!lesson || !Number.isInteger(currentLessonNumber) || currentLessonNumber < 1) {
    return <Navigate to={`/course/${slug}`} replace />
  }

  if (!lessonCanOpen) {
    return <Navigate to={`/course/${slug}`} replace />
  }

  const completeTheoryLesson = () => {
    saveLessonProgress(slug, currentLessonNumber)
    setTheorySaved(true)
  }

  return (
    <main className="course-lesson-page">
      <nav className="course-lesson-topbar" aria-label="Lesson navigation">
        <Link to={`/course/${slug}`}>← Zurück · Назад</Link>
        <img src={logo} alt="Hefner Sprach Hub" />
        <span>Modul {lesson.moduleNumber} · {modeLabel}</span>
      </nav>

      <article className="course-lesson-sheet">
        <header>
          <h1>{lesson.title}</h1>
          <p>{lesson.subtitle}</p>
        </header>

        <AnnaAssistant level="A1" lessonTitle={lesson.title} mode="lesson" />

        {lesson.videoUrl ? (
          <section className="course-lesson-video" aria-label="Training video">
            <iframe
              title={`${lesson.title} Video`}
              src={lesson.videoUrl}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
            />
          </section>
        ) : null}

        {lesson.sections?.map((section) => {
          if (section.kind === "table") {
            return (
              <section className="course-lesson-section" key={section.title}>
                <h2>{section.title}</h2>
                <div className="course-lesson-table">
                  <div className="course-lesson-table__head">
                    {section.headers.map((header) => <strong key={header}>{header}</strong>)}
                  </div>
                  {section.rows.map((row) => (
                    <div className="course-lesson-table__row" key={row.join("-")}>
                      {row.map((cell) => <SpeakableText key={cell} value={cell} />)}
                    </div>
                  ))}
                </div>
              </section>
            )
          }

          if (section.kind === "list") {
            return (
              <section className="course-lesson-section" key={section.title}>
                <h2>{section.title}</h2>
                <ul>
                  {section.items.map((item) => <li key={item}><SpeakableText value={item}>{item}</SpeakableText></li>)}
                </ul>
              </section>
            )
          }

          return (
            <section className="course-lesson-section" key={section.title}>
              {section.title ? <h2>{section.title}</h2> : null}
              <div className="course-lesson-text">
                {section.lines.map((line) => <p key={line}><SpeakableText value={line}>{line}</SpeakableText></p>)}
              </div>
            </section>
          )
        })}

        {lesson.mode === "theory" ? (
          <section className="course-complete-card">
            <h2>Завершение урока</h2>
            <p>После просмотра видео и теории нажмите кнопку, чтобы урок отметился как пройденный.</p>
            <button type="button" onClick={completeTheoryLesson}>
              {theorySaved ? "Урок пройден" : "Завершить урок"}
            </button>
            {theorySaved ? <Link to={`/course/${slug}`}>К шкале результата</Link> : null}
          </section>
        ) : null}

        {lesson.fillTasks && lesson.wordBank ? (
          <FillPractice courseSlug={slug} lessonNumber={currentLessonNumber} tasks={lesson.fillTasks} wordBank={lesson.wordBank} />
        ) : null}
        {lesson.exam ? <ExamPractice courseSlug={slug} lessonNumber={currentLessonNumber} questions={lesson.exam} /> : null}

        <footer className="course-lesson-actions">
          <Link to={`/course/${slug}`}>К шкале результата</Link>
        </footer>
      </article>
    </main>
  )
}

