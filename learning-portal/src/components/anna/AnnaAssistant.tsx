import { useEffect, useMemo, useRef, useState } from "react"

import annaPortraitOpen from "../../assets/anna-portrait-open.png"
import annaPortrait from "../../assets/anna-portrait.png"
import annaPortraitRound from "../../assets/anna-portrait-round.png"
import { createAnnaSpeech } from "../../api/onlineApi"
import { useUiPreferences } from "../../context/UiPreferencesContext"
import type { Locale } from "../../types"
import { AnnaGeminiLiveClient } from "./AnnaGeminiLiveClient"
import styles from "./AnnaAssistant.module.css"

type AnnaAssistantProps = {
  lessonTitle?: string
  level: string
  mode?: "course" | "lesson"
}

type AnnaAction = "explain" | "practice" | "questions"
type VoiceStatus = "idle" | "listening" | "speaking" | "unsupported"
type ChatLanguage = "de-DE" | "uk-UA" | "ru-RU"
type Viseme = 0 | 1 | 2 | 3 | 4 | 5
type ChatTurn = {
  answer: string
  question: string
}

type SpeechRecognitionResult = {
  readonly 0: { transcript: string }
}

type SpeechRecognitionEvent = Event & {
  results: {
    readonly length: number
    readonly [index: number]: SpeechRecognitionResult
  }
}

type BrowserSpeechRecognition = {
  continuous: boolean
  interimResults: boolean
  lang: string
  onend: (() => void) | null
  onerror: ((event: { error?: string }) => void) | null
  onnomatch: (() => void) | null
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  start: () => void
  stop: () => void
}

type SpeechRecognitionConstructor = new () => BrowserSpeechRecognition

type SpeechWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor
  webkitSpeechRecognition?: SpeechRecognitionConstructor
}

const annaTtsProvider = (
  (import.meta.env.VITE_ANNA_TTS_PROVIDER as string | undefined)
  ?? "gemini-live"
).toLowerCase()
const normalizeLevel = (level: string) => level.toUpperCase().match(/\b(A1|A2|B1|B2|C1|C2)\b/)?.[1] ?? "A1"

const visemeForCharacter = (char: string): Viseme => {
  if (!char.trim()) return 0
  if (/[mbpмбп]/i.test(char)) return 0
  if (/[aаäя]/i.test(char)) return 2
  if (/[oоуюö]/i.test(char)) return 4
  if (/[eиіыїеєэiü]/i.test(char)) return 1
  if (/[fvwфв]/i.test(char)) return 5
  if (/[szцсзшжчщ]/i.test(char)) return 3
  return 1
}

const buildVisemeTimeline = (text: string): Viseme[] => {
  const compact = text.replace(/\s+/g, " ").trim()
  if (!compact) return [0]

  return compact
    .slice(0, 260)
    .split("")
    .flatMap((char) => {
      const viseme = visemeForCharacter(char)
      return char === " " ? [0] : [viseme, viseme]
    })
}

const portraitForViseme = (viseme: Viseme) => {
  if (viseme === 2 || viseme === 1 || viseme === 5) return annaPortraitOpen
  if (viseme === 4) return annaPortraitRound
  return annaPortrait
}

const getSpeechRecognition = () => {
  if (typeof window === "undefined") return null
  const speechWindow = window as SpeechWindow
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null
}

const prepareSpeechText = (text: string) => (
  text
    .replace(/\s+/g, " ")
    .replace(/([.!?])\s+/g, "$1 ")
    .replace(/:/g, ". ")
    .trim()
)

const naturalVoiceHints: Record<ChatLanguage, string[]> = {
  "de-DE": ["natural", "online", "google", "katja", "conrad", "microsoft"],
  "ru-RU": ["natural", "online", "google", "svetlana", "irina", "microsoft"],
  "uk-UA": ["natural", "online", "google", "ukrain", "uk-ua", "microsoft"],
}

const findBrowserVoice = (voices: SpeechSynthesisVoice[], lang: ChatLanguage) => {
  const languageVoices = voices.filter((voice) => voice.lang.toLowerCase().startsWith(lang.slice(0, 2).toLowerCase()))
  const hints = naturalVoiceHints[lang]
  return languageVoices.find((voice) => {
    const name = voice.name.toLowerCase()
    return hints.some((hint) => name.includes(hint))
  }) ?? languageVoices[0]
}

const splitSpeechText = (text: string) => {
  const prepared = prepareSpeechText(text)
  const sentences = prepared.match(/[^.!?]+[.!?]?/g)?.map((part) => part.trim()).filter(Boolean) ?? [prepared]
  return sentences.flatMap((sentence) => {
    if (sentence.length <= 150) return [sentence]
    return sentence.split(/,\s+/).map((part) => part.trim()).filter(Boolean)
  })
}

const speakWithBrowserVoice = async (text: string, language: ChatLanguage) => {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    throw new Error("Browser TTS is not supported.")
  }

  window.speechSynthesis.cancel()
  const voices = window.speechSynthesis.getVoices()
  const preferredVoice = findBrowserVoice(voices, language)
  const chunks = splitSpeechText(text)

  await new Promise<void>((resolve, reject) => {
    const speakChunk = (index: number) => {
      const chunk = chunks[index]
      if (!chunk) {
        resolve()
        return
      }

      const utterance = new SpeechSynthesisUtterance(chunk)
      utterance.lang = language
      utterance.rate = language === "de-DE" ? 0.78 : 0.82
      utterance.pitch = 0.98
      utterance.volume = 1
      if (preferredVoice) utterance.voice = preferredVoice
      utterance.onend = () => window.setTimeout(() => speakChunk(index + 1), 120)
      utterance.onerror = () => reject(new Error("Browser TTS playback failed."))
      window.speechSynthesis.speak(utterance)
    }

    speakChunk(0)
  })
}

const playOpenAiSpeech = async (text: string, language: ChatLanguage) => {
  const audioBlob = await createAnnaSpeech({ text: prepareSpeechText(text), language })
  const audioUrl = URL.createObjectURL(audioBlob)
  const audio = new Audio(audioUrl)

  await new Promise<void>((resolve, reject) => {
    audio.onended = () => resolve()
    audio.onerror = () => reject(new Error("OpenAI TTS audio playback failed."))
    audio.play().catch(reject)
  }).finally(() => {
    URL.revokeObjectURL(audioUrl)
  })
}

const assistantCopy = (locale: Locale, level: string, lessonTitle?: string) => {
  const de = locale === "de"
  const levelText = normalizeLevel(level)
  const topic = lessonTitle ? `: ${lessonTitle}` : ""

  const focus: Record<string, { de: string; uk: string }> = {
    A1: {
      de: "Ich helfe mit Aussprache, Artikeln, einfachen Fragen und kurzen Alltagssätzen.",
      uk: "Я допомагаю з вимовою, артиклями, простими питаннями та короткими реченнями на щодень.",
    },
    A2: {
      de: "Ich trainiere Dialoge für Alltag, Termine, Einkaufen und einfache Vergangenheit.",
      uk: "Я треную діалоги для побуту, зустрічей, покупок і простої минулої форми.",
    },
    B1: {
      de: "Ich frage nach deiner Meinung, korrigiere Satzbau und helfe bei kleinen Texten.",
      uk: "Я ставлю питання про думку, виправляю порядок слів і допомагаю з короткими текстами.",
    },
    B2: {
      de: "Ich simuliere Berufssituationen, Diskussionen und präzise schriftliche Antworten.",
      uk: "Я моделюю робочі ситуації, дискусії та точні письмові відповіді.",
    },
    C1: {
      de: "Ich prüfe Stil, Argumentation, Nuancen und akademische oder berufliche Sprache.",
      uk: "Я перевіряю стиль, аргументацію, нюанси й академічну або професійну мову.",
    },
    C2: {
      de: "Ich feile mit dir an Ausdruck, Idiomatik, Register und sehr präzisen Formulierungen.",
      uk: "Я відпрацьовую виразність, ідіоми, регістр і дуже точні формулювання.",
    },
  }

  const answers: Record<AnnaAction, { de: string; uk: string }> = {
    explain: {
      de: `Fokus ${levelText}${topic}: Ich erkläre die Regel kurz, zeige ein Beispiel und nenne eine typische Falle.`,
      uk: `Фокус ${levelText}${topic}: я коротко поясню правило, покажу приклад і типову помилку.`,
    },
    practice: {
      de: `Praxis ${levelText}: Antworte laut in 2-3 Sätzen. Ich führe dich von einfacher Antwort zu natürlicher Formulierung.`,
      uk: `Практика ${levelText}: відповідай уголос 2-3 реченнями. Я веду від простої відповіді до природного формулювання.`,
    },
    questions: {
      de: `Fragen ${levelText}: Ich stelle passende Kontrollfragen und du kannst die Antwort direkt im Kurs prüfen.`,
      uk: `Питання ${levelText}: я ставлю контрольні питання під рівень, а відповідь можна одразу перевірити в курсі.`,
    },
  }

  return {
    actionLabels: {
      explain: de ? "Erklären" : "Пояснити",
      practice: de ? "Üben" : "Практика",
      questions: de ? "Fragen" : "Питання",
    },
    answers,
    focus: focus[levelText] ?? focus.A1,
    intro: de
      ? "Drücke auf das Mikrofon, stelle deine Frage und Anna antwortet mit natürlicher Gemini-Stimme."
      : "Натисни мікрофон, постав питання, і Anna відповість голосом.",
    micIdle: de ? "Mikrofon starten" : "Увімкнути мікрофон",
    micListening: de ? "Ich höre zu..." : "Я слухаю...",
    micReady: de ? "Sprich nach dem Klick. Der erkannte Text erscheint im Feld." : "Говори після кліку. Розпізнаний текст з'явиться в полі.",
    noVoice: de ? "Spracherkennung wird in diesem Browser nicht unterstützt." : "Розпізнавання голосу не підтримується в цьому браузері.",
    noSpeech: de ? "Ich habe nichts gehört. Prüfe das Mikrofon oder schreibe die Frage ins Feld." : "Я нічого не почула. Перевір мікрофон або напиши питання в поле.",
    permissionDenied: de ? "Der Browser hat den Mikrofonzugriff blockiert. Erlaube das Mikrofon in der Adressleiste." : "Браузер заблокував мікрофон. Дозволь доступ до мікрофона в адресному рядку.",
    placeholder: de ? "Oder schreibe deine Frage an Anna..." : "Або напиши своє питання Anna...",
    repeat: de ? "Antwort vorlesen" : "Озвучити відповідь",
    send: de ? "Anna fragen" : "Запитати Anna",
    speechHint: de ? "Langsam und klar. Gemini Live antwortet mit natürlicher Stimme." : "Говори повільно й чітко. Gemini Live відповідає природним голосом.",
    stateLabel: de ? "Modus" : "Режим",
    subtitle: de ? "Deutsch-ukrainische Lernassistentin mit Stimme" : "Німецько-українська голосова асистентка",
    title: de ? `Anna für Deutsch ${levelText}` : `Anna для Deutsch ${levelText}`,
  }
}

const extractPhrase = (question: string) => {
  const quoted = question.match(/[«"](.*?)[»"]/)
  if (quoted?.[1]) return quoted[1].trim()
  return question
    .replace(/^(как сказать|как будет|переведи|перевести|что значит|як сказати|як буде|uebersetze|übersetze)\s+/i, "")
    .trim()
}

const knownPhraseTranslation = (phrase: string) => {
  const value = phrase.toLowerCase()
  if (/меня зовут|мене звати/.test(value)) return "Ich heiße ..."
  if (/я из|я з/.test(value)) return "Ich komme aus ..."
  if (/я живу|я живу/.test(value)) return "Ich wohne in ..."
  if (/я учу|я вчу|изучаю/.test(value)) return "Ich lerne Deutsch."
  if (/сколько стоит|скільки коштує/.test(value)) return "Wie viel kostet das?"
  if (/доброе утро|доброго ранку/.test(value)) return "Guten Morgen."
  if (/добрый день|добрий день/.test(value)) return "Guten Tag."
  if (/до свидания|до побачення/.test(value)) return "Auf Wiedersehen."
  return ""
}

const answerQuestion = (question: string, locale: Locale, level: string, lessonTitle?: string, chatLanguage?: ChatLanguage) => {
  const answerLanguage = chatLanguage?.startsWith("ru") ? "ru" : chatLanguage?.startsWith("de") || locale === "de" ? "de" : "uk"
  const de = answerLanguage === "de"
  const ru = answerLanguage === "ru"
  const levelText = normalizeLevel(level)
  const topic = lessonTitle ? ` ${de ? "Thema" : ru ? "Тема" : "Тема"}: ${lessonTitle}.` : ""
  const normalizedQuestion = question.trim()
  const lowerQuestion = normalizedQuestion.toLowerCase()

  if (!normalizedQuestion) {
    if (de) return `Stell mir eine konkrete Frage zu Deutsch ${levelText}. Zum Beispiel: Wie benutze ich der, die, das? Dann antworte ich mit Regel, Beispiel und Übung.${topic}`
    if (ru) return `Спроси меня конкретно по Deutsch ${levelText}. Например: как использовать der, die, das? Я отвечу правилом, примером и маленькой тренировкой.${topic}`
    return `Запитай мене конкретно по Deutsch ${levelText}. Наприклад: як використовувати der, die, das? Я відповім правилом, прикладом і маленькою вправою.${topic}`
  }

  const asksArticle = /artikel|article|der|die|das|артик|артикль|артикли/.test(lowerQuestion)
  const asksVerb = /verb|sein|haben|дієсл|глагол|быть|иметь|дієслово/.test(lowerQuestion)
  const asksGreeting = /hallo|guten|привет|поздор|вітання|добрий|доброе/.test(lowerQuestion)
  const asksSentence = /satz|sentence|предлож|реченн|порядок слов|wortstellung/.test(lowerQuestion)
  const asksTranslate = /translate|uebersetz|übersetz|переклад|переведи|перевести|як сказати|как сказать|как будет|означає|значит|перевод/.test(lowerQuestion)
  const asksPronunciation = /произнош|вимов|aussprache|как читать|як читати/.test(lowerQuestion)
  const asksQuestionForm = /вопрос|питання|frage|спросить|запитати/.test(lowerQuestion)

  if (asksArticle) {
    if (de) return `Gute Frage. Artikel sind wie kleine Signale vor dem Nomen. der ist maskulin: der Mann. die ist feminin: die Frau. das ist neutral: das Kind. Wichtig für A1: im Akkusativ wird nur der zu den. Beispiel: Das ist der Mann. Ich sehe den Mann. Jetzt übe: Sage laut drei Wörter mit Artikel: der Kaffee, die Tasche, das Buch.`
    if (ru) return `Хороший вопрос. Артикль — это маленький сигнал перед существительным. der — мужской род: der Mann. die — женский: die Frau. das — средний: das Kind. Важно для A1: в Akkusativ меняется только der на den. Пример: Das ist der Mann. Ich sehe den Mann. Теперь тренировка: скажи вслух три слова с артиклем: der Kaffee, die Tasche, das Buch.`
    return `Гарне питання. Артикль — це маленький сигнал перед іменником. der — чоловічий рід: der Mann. die — жіночий: die Frau. das — середній: das Kind. Важливо для A1: в Akkusativ змінюється тільки der на den. Приклад: Das ist der Mann. Ich sehe den Mann. Тренування: скажи вголос три слова з артиклем: der Kaffee, die Tasche, das Buch.`
  }

  if (asksVerb) {
    if (de) return `Bei Verben schauen wir zuerst auf die Person. sein: ich bin, du bist, er ist, wir sind. haben: ich habe, du hast, er hat, wir haben. Im normalen Satz steht das Verb auf Position zwei: Ich bin Anna. Ich habe ein Buch. Jetzt sag einen eigenen Satz mit ich bin oder ich habe.`
    if (ru) return `С глаголами сначала смотрим на лицо. sein: ich bin, du bist, er ist, wir sind. haben: ich habe, du hast, er hat, wir haben. В обычном немецком предложении глагол стоит на втором месте: Ich bin Anna. Ich habe ein Buch. Теперь скажи свой пример с ich bin или ich habe.`
    return `З дієсловами спочатку дивимось на особу. sein: ich bin, du bist, er ist, wir sind. haben: ich habe, du hast, er hat, wir haben. У звичайному німецькому реченні дієслово стоїть на другому місці: Ich bin Anna. Ich habe ein Buch. Тепер скажи свій приклад з ich bin або ich habe.`
  }

  if (asksTranslate) {
    const phrase = extractPhrase(normalizedQuestion)
    const translated = knownPhraseTranslation(phrase)
    if (translated) {
      if (de) return `Die einfache A1-Form ist: ${translated} Wiederhole sie langsam. Wenn du möchtest, sag mir jetzt deinen ganzen Satz, und ich mache ihn natürlicher.`
      if (ru) return `Простая форма для A1: ${translated} Повтори ее медленно. Если хочешь, скажи мне теперь всё предложение целиком, и я сделаю его естественнее.`
      return `Проста форма для A1: ${translated} Повтори її повільно. Якщо хочеш, скажи мені тепер усе речення повністю, і я зроблю його природнішим.`
    }
    if (de) return `Ich kann das übersetzen, aber ich brauche den ganzen Satz. Sag zum Beispiel: Wie sagt man "Ich wohne in Berlin"? Dann gebe ich dir die deutsche Version und erkläre die Struktur.`
    if (ru) return `Я могу перевести, но мне нужно всё предложение целиком. Скажи, например: как сказать "я живу в Берлине"? Тогда я дам немецкий вариант и объясню структуру.`
    return `Я можу перекласти, але мені потрібне все речення повністю. Скажи, наприклад: як сказати "я живу в Берліні"? Тоді я дам німецький варіант і поясню структуру.`
  }

  if (asksGreeting) {
    if (de) return `Für Begrüßungen brauchst du drei Situationen. Morgens: Guten Morgen. Tagsüber: Guten Tag. Abends: Guten Abend. Danach kannst du sagen: Ich heiße Anna. Sehr A1 und sehr natürlich. Jetzt antworte mir: Guten Tag, ich heiße ...`
    if (ru) return `Для приветствий запомни три ситуации. Утром: Guten Morgen. Днем: Guten Tag. Вечером: Guten Abend. Потом можно сказать: Ich heiße Anna. Это A1 и звучит естественно. Теперь ответь мне: Guten Tag, ich heiße ...`
    return `Для вітань запам'ятай три ситуації. Вранці: Guten Morgen. Вдень: Guten Tag. Ввечері: Guten Abend. Потім можна сказати: Ich heiße Anna. Це A1 і звучить природно. Тепер відповідай: Guten Tag, ich heiße ...`
  }

  if (asksSentence) {
    if (de) return `Der normale deutsche Satz ist: Subjekt, Verb, Rest. Beispiel: Ich lerne Deutsch. In der Frage kommt das Verb nach vorne: Lernst du Deutsch? Antwort: Ja, ich lerne Deutsch. Dein Mini-Training: mache aus Ich wohne in Berlin eine Frage.`
    if (ru) return `Обычный порядок слов в немецком: подлежащее, глагол, остальная часть. Пример: Ich lerne Deutsch. В вопросе глагол выходит вперед: Lernst du Deutsch? Ответ: Ja, ich lerne Deutsch. Мини-тренировка: сделай вопрос из Ich wohne in Berlin.`
    return `Звичайний порядок слів у німецькій: підмет, дієслово, решта. Приклад: Ich lerne Deutsch. У питанні дієслово виходить вперед: Lernst du Deutsch? Відповідь: Ja, ich lerne Deutsch. Міні-вправа: зроби питання з Ich wohne in Berlin.`
  }

  if (asksQuestionForm) {
    if (de) return `Um eine Ja-Nein-Frage zu machen, stell das Verb an den Anfang: Du lernst Deutsch wird Lernst du Deutsch? Ich wohne in Berlin wird Wohnst du in Berlin? Antworte kurz: Ja, ich lerne Deutsch.`
    if (ru) return `Чтобы сделать вопрос да или нет, поставь глагол в начало: Du lernst Deutsch превращается в Lernst du Deutsch? Ich wohne in Berlin превращается в Wohnst du in Berlin? Ответь коротко: Ja, ich lerne Deutsch.`
    return `Щоб зробити питання так або ні, постав дієслово на початок: Du lernst Deutsch стає Lernst du Deutsch? Ich wohne in Berlin стає Wohnst du in Berlin? Відповідай коротко: Ja, ich lerne Deutsch.`
  }

  if (asksPronunciation) {
    if (de) return `Aussprache-Tipp: Sprich langsam in Silben. Deutsch: Deu-tsch. Guten Morgen: Gu-ten Mor-gen. ch klingt oft weich, wie in ich. Wiederhole: Ich lerne Deutsch.`
    if (ru) return `Совет по произношению: говори медленно по слогам. Deutsch: Deu-tsch. Guten Morgen: Gu-ten Mor-gen. Звук ch часто мягкий, как в ich. Повтори: Ich lerne Deutsch.`
    return `Порада з вимови: говори повільно по складах. Deutsch: Deu-tsch. Guten Morgen: Gu-ten Mor-gen. Звук ch часто м'який, як в ich. Повтори: Ich lerne Deutsch.`
  }

  if (de) return `Ich habe dich verstanden: ${normalizedQuestion}. Ich antworte auf A1-Niveau: Wir nehmen einen einfachen Satz, sprechen ihn laut und wechseln ein Wort. Muster: Ich lerne Deutsch. Du kannst sagen: Ich lerne heute Deutsch. Jetzt bist du dran: Sag einen Satz mit ich.`
  if (ru) return `Я поняла: ${normalizedQuestion}. Отвечаю на уровне A1: берем простое предложение, произносим вслух и меняем одно слово. Шаблон: Ich lerne Deutsch. Можно сказать: Ich lerne heute Deutsch. Теперь твоя очередь: скажи одно предложение с ich.`
  return `Я зрозуміла: ${normalizedQuestion}. Відповідаю на рівні A1: беремо просте речення, промовляємо вголос і міняємо одне слово. Шаблон: Ich lerne Deutsch. Можна сказати: Ich lerne heute Deutsch. Тепер твоя черга: скажи одне речення з ich.`
}

export const AnnaAssistant = ({ lessonTitle, level, mode = "course" }: AnnaAssistantProps) => {
  const { locale } = useUiPreferences()
  const [action, setAction] = useState<AnnaAction>("practice")
  const [chatLanguage, setChatLanguage] = useState<ChatLanguage>(() => (locale === "de" ? "de-DE" : "ru-RU"))
  const [question, setQuestion] = useState("")
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>(() => (getSpeechRecognition() ? "idle" : "unsupported"))
  const [voiceMessage, setVoiceMessage] = useState("")
  const [answer, setAnswer] = useState("")
  const [chatTurns, setChatTurns] = useState<ChatTurn[]>([])
  const [viseme, setViseme] = useState<Viseme>(0)
  const heardSpeechRef = useRef(false)
  const liveClientRef = useRef<AnnaGeminiLiveClient | null>(null)
  const copy = useMemo(() => assistantCopy(locale, level, lessonTitle), [locale, level, lessonTitle])
  const stateName = voiceStatus === "listening" ? "listening" : voiceStatus === "speaking" ? "speaking" : action === "explain" ? "curious_lean" : action === "questions" ? "nod_yes" : "hello"
  const defaultAnswer = locale === "de" ? copy.answers[action].de : copy.answers[action].uk
  const displayedAnswer = answer || defaultAnswer
  const visemeTimeline = useMemo(() => buildVisemeTimeline(displayedAnswer), [displayedAnswer])

  useEffect(() => {
    return () => {
      liveClientRef.current?.disconnect()
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  useEffect(() => {
    setChatLanguage((current) => {
      if (current === "ru-RU") return current
      return locale === "de" ? "de-DE" : "uk-UA"
    })
  }, [locale])

  useEffect(() => {
    if (voiceStatus !== "speaking") {
      setViseme(0)
      return undefined
    }

    let frame = 0
    const timer = window.setInterval(() => {
      setViseme(visemeTimeline[frame % visemeTimeline.length] ?? 0)
      frame += 1
    }, 95)

    return () => window.clearInterval(timer)
  }, [voiceStatus, visemeTimeline])

  const speakWithLipSync = async (text: string) => {
    setVoiceStatus("speaking")
    try {
      if (annaTtsProvider === "browser") {
        await speakWithBrowserVoice(text, chatLanguage)
      } else {
        await playOpenAiSpeech(text, chatLanguage)
      }
      setVoiceStatus(getSpeechRecognition() ? "idle" : "unsupported")
    } catch {
      setVoiceStatus(getSpeechRecognition() ? "idle" : "unsupported")
      setVoiceMessage(
        locale === "de"
          ? "Die natürliche Stimme ist gerade nicht verfügbar. Prüfe Gemini API und Mikrofonzugriff."
          : "Натуральный голос сейчас недоступен. Проверь Gemini API и доступ к микрофону.",
      )
    }
  }

  const answerWithVoice = async (nextQuestion = question) => {
    const cleanQuestion = nextQuestion.trim()
    if (annaTtsProvider === "gemini-live") {
      let liveClient = liveClientRef.current
      if (!liveClient) {
        await startGeminiLiveChat({ keepOpen: true })
        liveClient = liveClientRef.current
      }
      const sent = liveClient?.sendText(cleanQuestion || displayedAnswer)
      if (sent) {
        setVoiceMessage(locale === "de" ? "Anna denkt..." : "Anna думает...")
        setVoiceStatus("listening")
        if (cleanQuestion) {
          setChatTurns((current) => [{ question: cleanQuestion, answer: "" }, ...current].slice(0, 3))
        }
        return
      }
    }

    const nextAnswer = answerQuestion(nextQuestion, locale, level, lessonTitle, chatLanguage)
    setAnswer(nextAnswer)
    setChatTurns((current) => [{ question: nextQuestion || "...", answer: nextAnswer }, ...current].slice(0, 3))
    setVoiceMessage("")
    speakWithLipSync(nextAnswer)
  }

  const startVoiceChat = () => {
    if (annaTtsProvider === "gemini-live") {
      startGeminiLiveChat()
      return
    }

    const Recognition = getSpeechRecognition()
    if (!Recognition) {
      setVoiceStatus("unsupported")
      setVoiceMessage(copy.noVoice)
      return
    }

    const recognition = new Recognition()
    heardSpeechRef.current = false
    recognition.lang = chatLanguage
    recognition.continuous = false
    recognition.interimResults = false
    recognition.onresult = (event) => {
      const transcript = event.results[event.results.length - 1]?.[0]?.transcript.trim() ?? ""
      heardSpeechRef.current = Boolean(transcript)
      setQuestion(transcript)
      answerWithVoice(transcript)
    }
    recognition.onerror = (event) => {
      const error = event.error ?? ""
      setVoiceStatus("idle")
      if (error === "not-allowed" || error === "service-not-allowed") {
        setVoiceMessage(copy.permissionDenied)
        return
      }
      if (error === "no-speech" || error === "audio-capture") {
        setVoiceMessage(copy.noSpeech)
        return
      }
      setVoiceMessage(error ? `${copy.noSpeech} (${error})` : copy.noSpeech)
    }
    recognition.onnomatch = () => {
      setVoiceMessage(copy.noSpeech)
      setVoiceStatus("idle")
    }
    recognition.onend = () => {
      setVoiceStatus((current) => (current === "listening" ? "idle" : current))
      if (!heardSpeechRef.current) {
        setVoiceMessage((current) => current || copy.noSpeech)
      }
    }
    setVoiceStatus("listening")
    setVoiceMessage(copy.micReady)
    try {
      recognition.start()
    } catch {
      setVoiceStatus("idle")
      setVoiceMessage(copy.noSpeech)
    }
  }

  const startGeminiLiveChat = async (options: { keepOpen?: boolean } = {}) => {
    if (liveClientRef.current && !options.keepOpen) {
      await liveClientRef.current.disconnect()
      liveClientRef.current = null
      setVoiceStatus(getSpeechRecognition() ? "idle" : "unsupported")
      setVoiceMessage(locale === "de" ? "Gemini Live getrennt." : "Gemini Live отключен.")
      return
    }

    setVoiceStatus("listening")
    setVoiceMessage(locale === "de" ? "Gemini Live verbindet sich. Erlaube das Mikrofon." : "Gemini Live подключается. Разреши микрофон.")
    const client = new AnnaGeminiLiveClient({
      onAudioEnd: () => setVoiceStatus("listening"),
      onAudioStart: () => setVoiceStatus("speaking"),
      onError: (error) => {
        setVoiceStatus(getSpeechRecognition() ? "idle" : "unsupported")
        setVoiceMessage(error.message)
        liveClientRef.current = null
      },
      onInputTranscript: (text) => {
        if (text) setQuestion(text)
      },
      onOutputTranscript: (text) => {
        if (!text) return
        setAnswer(text)
        setChatTurns((current) => [{ question: question || "...", answer: text }, ...current].slice(0, 3))
      },
      onReady: (session) => {
        setVoiceStatus("listening")
        setVoiceMessage(`${session.voice} · Gemini Live`)
      },
      onStatus: (statusText) => setVoiceMessage(statusText),
      onTurnComplete: () => setVoiceStatus("listening"),
    })
    liveClientRef.current = client
    try {
      await client.connect({
        language: chatLanguage,
        lessonTitle,
        level: normalizeLevel(level),
        voice: "Achernar",
      })
    } catch (error) {
      liveClientRef.current = null
      setVoiceStatus(getSpeechRecognition() ? "idle" : "unsupported")
      setVoiceMessage(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <section className={`${styles.assistant} ${mode === "lesson" ? styles.lessonAssistant : ""}`} aria-label="Anna assistant">
      <div className={styles.stage}>
        <div className={`${styles.portraitRig} ${styles[stateName]}`} aria-label="Anna animated assistant" role="img">
          <img src={portraitForViseme(viseme)} alt="" />
        </div>
        <span className={styles.voiceBadge}>{voiceStatus === "listening" ? copy.micListening : "Voice chat"}</span>
      </div>
      <div className={styles.copy}>
        <p className={styles.eyebrow}>Anna Assistant</p>
        <h2>{copy.title}</h2>
        <strong>{copy.subtitle}</strong>
        <p>{locale === "de" ? copy.focus.de : copy.focus.uk}</p>
        <p className={styles.intro}>{copy.intro}</p>
        <div className={styles.actions} role="group" aria-label="Anna actions">
          {(["explain", "practice", "questions"] as AnnaAction[]).map((item) => (
            <button className={action === item ? styles.activeAction : ""} key={item} type="button" onClick={() => setAction(item)}>
              {copy.actionLabels[item]}
            </button>
          ))}
        </div>
        <div className={styles.voiceChat}>
          <button className={styles.micButton} type="button" onClick={startVoiceChat} disabled={annaTtsProvider !== "gemini-live" && (voiceStatus === "listening" || voiceStatus === "speaking")}>
            <span aria-hidden="true" />
            {annaTtsProvider === "gemini-live" && liveClientRef.current ? (locale === "de" ? "Live stoppen" : "Остановить Live") : voiceStatus === "listening" ? copy.micListening : copy.micIdle}
          </button>
          <label className={styles.languageSelect}>
            <span>{locale === "de" ? "Sprache für Mikrofon und Antwort" : "Мова мікрофона та відповіді"}</span>
            <select value={chatLanguage} onChange={(event) => setChatLanguage(event.target.value as ChatLanguage)}>
              <option value="ru-RU">RU</option>
              <option value="uk-UA">UK</option>
              <option value="de-DE">DE</option>
            </select>
          </label>
          <p className={styles.speechHint}>{copy.speechHint}</p>
          <textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder={copy.placeholder} rows={2} />
          <div className={styles.voiceActions}>
            <button type="button" onClick={() => answerWithVoice()}>{copy.send}</button>
            <button type="button" onClick={() => speakWithLipSync(displayedAnswer)}>
              {copy.repeat}
            </button>
          </div>
          {voiceStatus === "unsupported" ? <p className={styles.voiceWarning}>{copy.noVoice}</p> : null}
          {voiceMessage ? <p className={styles.voiceStatus}>{voiceMessage}</p> : null}
        </div>
        <div className={styles.response}>
          <span>{copy.stateLabel}: {stateName}</span>
          <p>{displayedAnswer}</p>
        </div>
        {chatTurns.length > 0 ? (
          <div className={styles.chatHistory} aria-label="Anna chat history">
            {chatTurns.map((turn, index) => (
              <article key={`${turn.question}-${index}`}>
                <strong>{turn.question}</strong>
                <p>{turn.answer}</p>
              </article>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  )
}


