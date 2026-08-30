from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand

from apps.online.models import (
    OnlineCohort,
    OnlineCourse,
    OnlineCourseFaq,
    OnlineCourseLessonSection,
    OnlineCourseLessonSectionItem,
    OnlineCourseModule,
    OnlineCourseMaterial,
    OnlineSession,
)
from apps.online.services.course_structure import upsert_course_structure


GERMAN_LEVEL_CONTENT = {
    "A1": {
        "module_titles": ["Startklar", "Alltag", "In der Stadt", "Mini-Projekt"],
        "topics": [
            "Begrüßung und Namen",
            "Familie und Personen",
            "Essen und Bestellen",
            "Wegbeschreibung",
            "Uhrzeit und Termine",
            "Einkaufen",
            "Arzt und Befinden",
            "Wohnen",
            "Arbeit und Schule",
            "Freizeit",
            "Telefonieren",
            "Vorstellung im Alltag",
        ],
        "redewendungen": ["Alles klar.", "Kein Problem.", "Ich bin dran.", "Bis gleich.", "Gute Besserung."],
        "outcome": "simple sentences, polite questions, and safe everyday answers",
    },
    "A2": {
        "module_titles": ["Alltag sicher", "Erlebnisse", "Planen", "Mini-Projekt"],
        "topics": [
            "Wochenende erzählen",
            "Reisen und Unterkunft",
            "Termine verschieben",
            "Nach Hilfe fragen",
            "Kaufen und umtauschen",
            "Wohnung suchen",
            "Gesundheit",
            "Arbeitstag",
            "Einladung",
            "E-Mail im Alltag",
            "Vergleichen",
            "Persönliche Geschichte",
        ],
        "redewendungen": ["Das passt mir gut.", "Ich habe es eilig.", "Das kommt darauf an.", "Schauen wir mal.", "Das klingt gut."],
        "outcome": "connected everyday speech, short explanations, and useful follow-up questions",
    },
    "B1": {
        "module_titles": ["Meinung", "Problem lösen", "Beruf und Alltag", "Prüfung"],
        "topics": [
            "Meinung begründen",
            "Erfahrung beschreiben",
            "Beschwerde freundlich formulieren",
            "Vor- und Nachteile",
            "Nachrichten verstehen",
            "Arbeit und Bewerbung",
            "Konflikt im Alltag",
            "Umwelt und Konsum",
            "Lernen planen",
            "Präsentation",
            "Brief schreiben",
            "Prüfungsgespräch",
            "Argumente ordnen",
            "Hören und Notizen",
            "Fehler verbessern",
            "Abschlussdialog",
        ],
        "redewendungen": ["Meiner Meinung nach ...", "Das ist nicht mein Ding.", "Ich sehe das anders.", "Da bin ich mir nicht sicher.", "Es geht um ..."],
        "outcome": "clear opinions, everyday problem solving, and exam-ready connected speech",
    },
    "B2": {
        "module_titles": ["Argumentieren", "Beruf", "Gesellschaft", "Debatte"],
        "topics": [
            "Argumente strukturieren",
            "Berufliche E-Mail",
            "Meeting und Rückfrage",
            "Grafik beschreiben",
            "Medien und Meinung",
            "Bildung",
            "Mobilität",
            "Gesundheitssystem",
            "Kulturvergleich",
            "Beschwerde mit Lösung",
            "Verhandlung",
            "Präsentation",
            "Debatte vorbereiten",
            "Text zusammenfassen",
            "Einwand behandeln",
            "Abschlussprojekt",
        ],
        "redewendungen": ["Auf den Punkt bringen.", "Den Faden verlieren.", "Das liegt auf der Hand.", "Eine Rolle spielen.", "Unter dem Strich ..."],
        "outcome": "structured arguments, professional clarity, and confident discussion",
    },
    "C1": {
        "module_titles": ["Präzision", "Akademisch", "Beruflich", "Nuance"],
        "topics": [
            "Nuanciert zustimmen",
            "Kritisch zusammenfassen",
            "Akademische Diskussion",
            "Strategisch nachfragen",
            "Projektkommunikation",
            "Risiken formulieren",
            "Komplexe Grafik",
            "Kommentar schreiben",
            "Implizite Bedeutung",
            "Stilregister wechseln",
            "Konflikt moderieren",
            "Fachtext auswerten",
            "These verteidigen",
            "Präzise Rückmeldung",
            "Policy-Debatte",
            "Abschlusskolloquium",
        ],
        "redewendungen": ["Etwas auf den Punkt bringen.", "Zwischen den Zeilen lesen.", "Den Nagel auf den Kopf treffen.", "Ins Gewicht fallen.", "Sich die Frage stellen."],
        "outcome": "precise register control, nuanced argumentation, and fluent academic or workplace speech",
    },
    "C2": {
        "module_titles": ["Souveränität", "Stil", "Diskurs", "Meisterstück"],
        "topics": [
            "Ironie und Unterton",
            "Stilmittel erkennen",
            "Komplexe Debatte leiten",
            "Fachliche Kontroverse",
            "Essay mit Haltung",
            "Rhetorik analysieren",
            "Verhandlung auf Augenhöhe",
            "Kulturelle Referenzen",
            "Sprachkritik",
            "Präzise Gegenrede",
            "Narrative Argumentation",
            "Medientext sezieren",
            "Impulsrede",
            "Panel-Diskussion",
            "Feinschliff",
            "Abschlussperformance",
        ],
        "redewendungen": ["Das ist ein zweischneidiges Schwert.", "Den Ball flach halten.", "Etwas auf die lange Bank schieben.", "Mit offenen Karten spielen.", "Das Kind beim Namen nennen."],
        "outcome": "near-native nuance, rhetorical control, and flexible idiomatic expression",
    },
}


EASY_GERMAN_VIDEO_OVERRIDES = {
    ("B1", "Konflikt im Alltag"): "https://www.youtube.com/watch?v=lrrBNFqG1oI&t=28s",
}


def _chunked(values, size):
    return [values[index : index + size] for index in range(0, len(values), size)]


def _video_url(level: str, topic: str) -> str:
    override_url = EASY_GERMAN_VIDEO_OVERRIDES.get((level, topic))
    if override_url:
        return override_url
    query = f"Deutsch {level} {topic} Redewendungen Dialog"
    return "https://www.youtube.com/results?search_query=" + query.replace(" ", "+")


def _quiz_payload(level: str, topic: str, idiom: str) -> dict:
    return {
        "prompt": f"Welche Antwort passt zu {level}: {topic}?",
        "questions": [
            {
                "id": "q1",
                "prompt": f"Was bedeutet die Redewendung '{idiom}' in diesem Kontext?",
                "options": [
                    {"id": "a", "label": "Sie macht die Aussage natürlicher und situationsbezogen.", "isCorrect": True},
                    {"id": "b", "label": "Sie ersetzt alle Grammatikregeln.", "isCorrect": False},
                    {"id": "c", "label": "Sie wird nur schriftlich benutzt.", "isCorrect": False},
                ],
                "successMessage": "Richtig. Nutze die Wendung jetzt in einem eigenen Satz.",
                "errorMessage": "Noch nicht. Lies den Dialog und prüfe die Situation.",
                "explanationMarkdown": f"## Erklärung\n\n'{idiom}' soll nicht isoliert gelernt werden. Wichtig ist die Situation, der Ton und ein eigener Beispielsatz.",
            }
        ],
        "successMessage": "Gut gemacht.",
        "errorMessage": "Wiederhole die Redewendung im Dialog.",
    }


def _reading_text(level: str, topic: str, idiom: str) -> str:
    if level in {"A1", "A2"}:
        return (
            f"## Lesetext\n\n"
            f"Ich habe heute ein kleines Gespräch über {topic.lower()}. "
            f"Am Anfang bin ich unsicher, aber dann sage ich: {idiom} "
            "Ich stelle eine einfache Frage, höre gut zu und antworte langsam. "
            "So kann ich die Situation Schritt für Schritt verstehen.\n\n"
            "## Verstehen\n\n"
            "- Wer spricht?\n"
            "- Was ist das Thema?\n"
            "- Welche Redewendung passt zur Situation?"
        )
    if level in {"B1", "B2"}:
        return (
            f"## Lesetext\n\n"
            f"In einer Alltagssituation geht es um {topic.lower()}. "
            "Die Personen haben unterschiedliche Ziele: Eine Person möchte schnell eine Lösung, "
            "die andere braucht mehr Informationen. Deshalb ist nicht nur Grammatik wichtig, "
            f"sondern auch eine passende Formulierung wie: {idiom} "
            "Wer solche Wendungen richtig benutzt, klingt hoeflicher, klarer und natürlicher.\n\n"
            "## Verstehen und Meinung\n\n"
            "- Welches Problem entsteht in der Situation?\n"
            "- Welche Lösung waere realistisch?\n"
            "- Formuliere deine Meinung mit Begruendung."
        )
    return (
        f"## Lesetext\n\n"
        f"Das Thema {topic.lower()} zeigt, wie stark Sprache von Kontext, Register und Absicht abhaengt. "
        "Eine Aussage kann sachlich, vorsichtig, ironisch oder konfrontativ wirken, obwohl der Inhalt aehnlich bleibt. "
        f"Die Wendung '{idiom}' eignet sich, um Haltung und Nuance zu markieren. "
        "Entscheidend ist, ob sie zur Beziehung der Sprecher, zur Situation und zum Medium passt. "
        "Fortgeschrittene Lernende sollten deshalb nicht nur Bedeutung, sondern auch Wirkung analysieren.\n\n"
        "## Analyse\n\n"
        "- Welche Haltung transportiert die Wendung?\n"
        "- In welchem Register wirkt sie passend?\n"
        "- Schreibe eine neutralere und eine pointiertere Variante."
    )


def _lesson_items(level: str, topic: str, idioms: list[str], sort_order: int) -> list[dict]:
    idiom = idioms[(sort_order - 1) % len(idioms)]
    next_idiom = idioms[sort_order % len(idioms)]
    return [
        {
            "title": "Lernziel und Mini-Wortschatz",
            "description": f"{level} Einstieg für {topic}.",
            "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
            "activityType": OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
            "language": OnlineCourse.LOCALE_DE,
            "bodyMarkdown": (
                f"## Ziel\n\nHeute trainierst du {topic.lower()} auf Niveau {level}.\n\n"
                "## Aktiv sprechen\n\n"
                f"- Ich kann über {topic.lower()} sprechen.\n"
                f"- Ich benutze '{idiom}' in einem natürlichen Satz.\n"
                "- Ich stelle mindestens eine Rückfrage."
            ),
            "externalUrl": "",
            "sortOrder": 1,
            "isActive": True,
        },
        {
            "title": "Redewendungen im Dialog",
            "description": "Modell-Dialog mit passenden Redewendungen und Varianten.",
            "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
            "activityType": OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
            "language": OnlineCourse.LOCALE_DE,
            "bodyMarkdown": (
                "## Dialog\n\n"
                f"Anna: Heute geht es um {topic.lower()}. Was würdest du in dieser Situation zuerst sagen?\n"
                f"Student: Ich würde ruhig anfangen: {idiom}\n"
                "Anna: Gut. Kannst du noch eine Rückfrage stellen?\n"
                "Student: Ja. Kannst du das bitte genauer erklären?\n"
                f"Anna: Sehr gut. Jetzt klingt es natürlicher. Eine zweite Möglichkeit ist: {next_idiom}\n"
                "Student: Ich wiederhole den Satz und ersetze ein Wort, damit er zu meiner Situation passt.\n\n"
                "## Redemittel\n\n"
                f"- {idiom}\n"
                f"- {next_idiom}\n"
                "- Kannst du das bitte wiederholen?\n"
                "- Ich meine damit, dass ...\n\n"
                "## Varianten\n\n"
                "- Höflich: Könnten Sie das bitte kurz erklären?\n"
                "- Direkt: Was genau meinst du?\n"
                "- Unsicher: Ich bin nicht sicher, ob ich das richtig verstanden habe."
            ),
            "externalUrl": "",
            "sortOrder": 2,
            "isActive": True,
        },
        {
            "title": "Lesetext mit Aufgaben",
            "description": "Niveaupassender Text zum Lesen, Verstehen und Weiterdenken.",
            "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
            "activityType": OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
            "language": OnlineCourse.LOCALE_DE,
            "bodyMarkdown": _reading_text(level, topic, idiom),
            "externalUrl": "",
            "sortOrder": 3,
            "isActive": True,
        },
        {
            "title": "Video-Aufgabe",
            "description": "Video suchen, ansehen, stoppen, nachsprechen.",
            "assetType": OnlineCourseLessonSectionItem.ASSET_LINK,
            "activityType": OnlineCourseLessonSectionItem.ACTIVITY_VIDEO,
            "language": OnlineCourse.LOCALE_DE,
            "bodyMarkdown": (
                "## Video-Aufgabe\n\n"
                "- Schaue 3-5 Minuten eines passenden Videos.\n"
                "- Stoppe nach jedem Beispielsatz.\n"
                f"- Notiere eine neue Formulierung zu '{idiom}'.\n"
                "- Sprich den besten Satz laut nach und nimm dich optional selbst auf."
            ),
            "externalUrl": _video_url(level, topic),
            "sortOrder": 4,
            "isActive": True,
        },
        {
            "title": "Kurzer Check",
            "description": "Eine Frage zur Redewendung und zur Situation.",
            "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
            "activityType": OnlineCourseLessonSectionItem.ACTIVITY_QUIZ,
            "language": OnlineCourse.LOCALE_DE,
            "bodyMarkdown": f"## Check\n\n- Was bedeutet '{idiom}' in der Situation?\n- Formuliere einen eigenen Satz zu {topic}.",
            "structuredData": _quiz_payload(level, topic, idiom),
            "externalUrl": "",
            "sortOrder": 5,
            "isActive": True,
        },
        {
            "title": "Speaking und Writing",
            "description": "Produktive Aufgabe für Live-Unterricht oder Selbststudium.",
            "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
            "activityType": OnlineCourseLessonSectionItem.ACTIVITY_ASSIGNMENT,
            "language": OnlineCourse.LOCALE_DE,
            "bodyMarkdown": (
                "## Aufgabe\n\n"
                f"Sprich 60-90 Sekunden über {topic.lower()} und benutze '{idiom}'.\n\n"
                "## Schriftlich\n\n"
                "- Schreibe 5-8 Sätze.\n"
                "- Markiere die Redewendung.\n"
                "- Schreibe eine Rückfrage an deine Lehrkraft."
            ),
            "externalUrl": "",
            "sortOrder": 6,
            "isActive": True,
        },
    ]


def build_german_level_modules(level: str) -> list[dict]:
    content = GERMAN_LEVEL_CONTENT[level]
    lessons_per_module = 3 if level in {"A1", "A2"} else 4
    modules = []
    for module_index, topic_group in enumerate(_chunked(content["topics"], lessons_per_module), start=1):
        module_title = content["module_titles"][module_index - 1]
        lessons = []
        for lesson_index, topic in enumerate(topic_group, start=1):
            global_index = (module_index - 1) * lessons_per_module + lesson_index
            lessons.append(
                {
                    "title": f"{level}.{global_index} {topic}",
                    "description": f"Redewendungen, Video-Aufgabe und aktive Produktion: {content['outcome']}.",
                    "sortOrder": lesson_index,
                    "isActive": True,
                    "sections": [
                        {
                            "sectionType": OnlineCourseLessonSection.SECTION_MAIN,
                            "title": "Lernpfad",
                            "description": "Theorie, Redewendungen, Video, Check und Aufgabe.",
                            "sortOrder": 10,
                            "isActive": True,
                            "items": _lesson_items(level, topic, content["redewendungen"], global_index),
                        }
                    ],
                }
            )
        modules.append(
            {
                "title": f"Modul {module_index}: {module_title}",
                "description": f"Deutsch {level}: {module_title.lower()} mit idiomatischer Alltagssprache.",
                "moduleType": OnlineCourseModule.MODULE_TYPE_STANDARD,
                "weekNumber": module_index,
                "sortOrder": module_index * 10,
                "isActive": True,
                "lessons": lessons,
            }
        )
    return modules


class Command(BaseCommand):
    help = "Seed default online courses, cohorts, sessions, FAQs and materials."

    def handle(self, *args, **options):
        berlin_tz = ZoneInfo("Europe/Berlin")
        today = date.today()
        days_to_monday = (7 - today.weekday()) % 7
        next_monday = today + timedelta(days=days_to_monday or 7)

        courses_data = [
            {
                "slug": "trial-group-lesson",
                "title_de": "Probestunde mit Lehrkraft in der Gruppe",
                "title_en": "Trial Group Lesson with Instructor",
                "short_description_de": "Kostenlose Probestunde in kleiner Gruppe mit Live-Feedback.",
                "short_description_en": "Free trial lesson in a small group with live instructor feedback.",
                "description_de": (
                    "Diese Probestunde orientiert sich an modernen Online-Kursformaten mit klarem Ablauf: "
                    "Warm-up, kurze Demonstration, gefÃ¼hrte Ãœbung und Feedbackrunde. "
                    "Das Format entspricht gÃ¤ngigen Einstiegssessions aus bekannten Lernplattformen: "
                    "niedrige EinstiegshÃ¼rde, klarer Lernfokus, sofortige Interaktion."
                ),
                "description_en": (
                    "This trial follows a modern online class flow: warm-up, short demonstration, "
                    "guided exercise, and feedback round. The structure mirrors common onboarding "
                    "patterns in established learning platforms: low-friction start, clear outcomes, "
                    "and immediate interaction."
                ),
                "lessons_count": 1,
                "trial_available": True,
                "price_amount": "0.00",
                "currency": "EUR",
                "is_subscription": False,
                "hero_image_url": "https://images.unsplash.com/photo-1513364776144-60967b0f800f",
                "seo_title_de": "Kostenlose Online-Probestunde Kunst in Berlin",
                "seo_title_en": "Free Online Art Trial Lesson in Berlin",
                "seo_description_de": "Online-Probestunde mit Lehrkraft: live, interaktiv, in kleiner Gruppe.",
                "seo_description_en": "Live online trial lesson with instructor and small group feedback.",
            },
            {
                "slug": "paint-in-5-days",
                "title_de": "Male ein Bild in 5 Tagen",
                "title_en": "Paint a Picture in 5 Days",
                "short_description_de": "Intensivprogramm mit klaren Tageszielen und Abschlussprojekt.",
                "short_description_en": "Intensive program with daily milestones and final project.",
                "description_de": (
                    "Projektbasierter Kurs nach bewÃ¤hrtem Bootcamp-Prinzip: jeden Tag ein klarer Schritt "
                    "von Komposition bis Farbharmonie. Inspiriert von erfolgreichen 'guided project' "
                    "Modellen aus internationalen E-Learning-Kursen. Enthalten sind Live-Unterricht, "
                    "Aufgabenplan, Peer-Kommentare und Abschlusskritik."
                ),
                "description_en": (
                    "A project-based bootcamp with clear day-by-day milestones from composition to color harmony. "
                    "Inspired by proven guided-project patterns in international e-learning programs. "
                    "Includes live sessions, assignment roadmap, peer comments, and final critique."
                ),
                "lessons_count": 12,
                "trial_available": True,
                "price_amount": "149.00",
                "currency": "EUR",
                "is_subscription": False,
                "hero_image_url": "https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b",
                "seo_title_de": "Online-Malkurs: Bild in 5 Tagen",
                "seo_title_en": "Online Painting Course: Paint in 5 Days",
                "seo_description_de": "Intensiver Online-Kurs mit Live-Feedback und Abschlussprojekt.",
                "seo_description_en": "Intensive online painting course with live feedback and final project.",
            },
            {
                "slug": "webinar-masterclass-live-recording",
                "title_de": "Online Masterclass: Live-Unterricht + Aufzeichnung",
                "title_en": "Online Masterclass: Live Lesson + Recording",
                "short_description_de": "Webinar-Format mit Live-Session und Replay fÃ¼r vertieftes Lernen.",
                "short_description_en": "Webinar format with live lesson and replay for deeper learning.",
                "description_de": (
                    "Masterclass im Webinar-Stil mit praxisnahen Demos, Q&A und Aufzeichnung. "
                    "Das Design folgt gÃ¤ngigen Virtual-Classroom-Standards: klare Agenda, "
                    "strukturierte Materialpakete, Nachbereitung Ã¼ber Replay und Lernnotizen."
                ),
                "description_en": (
                    "Webinar-style masterclass with practical demos, Q&A, and full recording access. "
                    "The structure follows common virtual classroom standards: clear agenda, "
                    "structured materials, and post-class review via replay and notes."
                ),
                "lessons_count": 12,
                "trial_available": False,
                "price_amount": "99.00",
                "currency": "EUR",
                "is_subscription": False,
                "hero_image_url": "https://images.unsplash.com/photo-1516321497487-e288fb19713f",
                "seo_title_de": "Online Masterclass mit Aufzeichnung",
                "seo_title_en": "Online Masterclass with Recording",
                "seo_description_de": "Live-Webinar mit Q&A und Replay fÃ¼r flexible Nachbereitung.",
                "seo_description_en": "Live webinar with Q&A and replay access for flexible review.",
            },
            {
                "slug": "studio-club-subscription",
                "title_de": "Studio-Club Abo: Bibliothek + wÃ¶chentliche Treffen",
                "title_en": "Studio Club Subscription: Library + Weekly Meetups",
                "short_description_de": "Abo-Modell mit On-Demand-Bibliothek und Live-Community-Treffen.",
                "short_description_en": "Subscription model with on-demand library and live community meetups.",
                "description_de": (
                    "Mitgliedschaft im Studio-Club mit Zugriff auf eine kuratierte Video-Bibliothek "
                    "und regelmÃ¤ÃŸigen Live-Sessions. Das Modell orientiert sich an bewÃ¤hrten "
                    "Abo-Lernangeboten mit Community-Fokus, Fortschrittskontrolle und kontinuierlicher Praxis."
                ),
                "description_en": (
                    "Studio Club membership with access to a curated lesson library and regular live sessions. "
                    "The model follows proven subscription-based learning patterns with community support, "
                    "progress tracking, and continuous practice."
                ),
                "lessons_count": 12,
                "trial_available": False,
                "price_amount": "59.00",
                "currency": "EUR",
                "is_subscription": True,
                "hero_image_url": "https://images.unsplash.com/photo-1503676260728-1c00da094a0b",
                "seo_title_de": "Studio-Club Online Abo fÃ¼r Kunstkurse",
                "seo_title_en": "Studio Club Online Art Subscription",
                "seo_description_de": "Video-Bibliothek und Live-Treffen im flexiblen Online-Abo.",
                "seo_description_en": "Lesson library and live meetups in a flexible online subscription.",
            },
            {
                "slug": "kids-painting-course",
                "title_de": "Kinder-Malkurs: Farben und Fantasie",
                "title_en": "Kids Painting Course: Colors and Imagination",
                "short_description_de": "Spielerischer Live-Kurs fÃ¼r Kinder mit kreativen Wochenprojekten.",
                "short_description_en": "Playful live course for kids with creative weekly projects.",
                "description_de": (
                    "Dieser Kurs vermittelt Kindern die Grundlagen von Farbe, Form und Komposition "
                    "in klaren, altersgerechten Schritten. Der Aufbau folgt bewÃ¤hrten Kreativmodellen "
                    "fÃ¼r junge Lernende: kurze Inputs, praktische Ãœbungen und motivierendes Feedback."
                ),
                "description_en": (
                    "This course teaches kids color, shape, and composition through structured, age-appropriate "
                    "steps. The format follows proven young-learner creative models: short instructions, "
                    "hands-on exercises, and motivating feedback."
                ),
                "lessons_count": 10,
                "trial_available": True,
                "price_amount": "89.00",
                "currency": "EUR",
                "is_subscription": False,
                "hero_image_url": "https://images.unsplash.com/photo-1472162072942-cd5147eb3902",
                "seo_title_de": "Online-Malkurs fÃ¼r Kinder",
                "seo_title_en": "Online Painting Course for Kids",
                "seo_description_de": "Kreativer Kinderkurs mit Live-Unterricht und spielerischen Projekten.",
                "seo_description_en": "Creative kids course with live lessons and playful projects.",
            },
            {
                "slug": "tattoo-design-course",
                "title_de": "Tattoo Design Studio: Entwirf dein eigenes Tattoo",
                "title_en": "Tattoo Design Studio: Create Your Own Tattoo",
                "short_description_de": "Von Idee bis fertigem Entwurf: LinienfÃ¼hrung, Stil und Komposition.",
                "short_description_en": "From idea to finished concept: linework, style, and composition.",
                "description_de": (
                    "Der Kurs orientiert sich an professionellen Tattoo-Design-Workflows: "
                    "Referenzrecherche, Thumbnail-Skizzen, saubere Linien, Schattenaufbau und finale PrÃ¤sentation. "
                    "Ideal fÃ¼r Einsteigerinnen und Einsteiger mit Interesse an Motiventwicklung."
                ),
                "description_en": (
                    "This course follows professional tattoo design workflows: reference research, thumbnail sketches, "
                    "clean linework, shading structure, and final presentation. Ideal for beginners interested in "
                    "developing original tattoo concepts."
                ),
                "lessons_count": 8,
                "trial_available": False,
                "price_amount": "119.00",
                "currency": "EUR",
                "is_subscription": False,
                "hero_image_url": "https://images.unsplash.com/photo-1542728928-1413d1894ed1?auto=format&fit=crop&w=1200&q=80",
                "seo_title_de": "Tattoo Design Online Kurs",
                "seo_title_en": "Tattoo Design Online Course",
                "seo_description_de": "Lernen Sie Tattoo-Design von Skizze bis finalem Entwurf.",
                "seo_description_en": "Learn tattoo design from first sketch to final concept.",
            },
        ]

        german_levels = [
            ("A1", "0.00", 12, "Kostenloser Probekurs fÃ¼r alle: Alphabet, Aussprache, BegrÃ¼ÃŸung und erste SÃ¤tze."),
            ("A2", "119.00", 12, "Alltag sicher sprechen: Familie, Arbeit, Einkaufen und Termine."),
            ("B1", "149.00", 16, "GesprÃ¤che fÃ¼hren, Meinung ausdrÃ¼cken und einfache Texte schreiben."),
            ("B2", "179.00", 16, "Komplexere Themen verstehen, argumentieren und beruflich kommunizieren."),
            ("C1", "199.00", 16, "PrÃ¤zise und flexible Sprache fÃ¼r Studium, Beruf und Alltag."),
            ("C2", "229.00", 16, "Sehr fortgeschrittenes Deutsch: nuanciert verstehen und formulieren."),
        ]
        courses_data = [
            {
                "slug": f"deutsch-{level.lower()}",
                "title_de": f"Deutsch {level}",
                "title_en": f"Deutsch {level}",
                "short_description_de": summary,
                "short_description_en": summary,
                "description_de": (
                    f"Deutsch {level} im Hefner Sprach Hub: strukturierter Online-Kurs mit ukrainischer "
                    "Begleitung, klaren Lektionen, Ãœbungen und persÃ¶nlichem Lernrhythmus."
                ),
                "description_en": (
                    f"Deutsch {level} at Hefner Sprach Hub: a structured online German course with "
                    "Ukrainian guidance, clear lessons, practice tasks, and personal learning rhythm."
                ),
                "lessons_count": lessons_count,
                "trial_available": level == "A1",
                "price_amount": price,
                "currency": "EUR",
                "is_subscription": False,
                "hero_image_url": "",
                "seo_title_de": f"Deutsch {level} online kaufen - Hefner Sprach Hub",
                "seo_title_en": f"Buy Deutsch {level} online - Hefner Sprach Hub",
                "seo_description_de": f"Deutsch {level} online buchen und Zugang zum Kurs erhalten.",
                "seo_description_en": f"Book Deutsch {level} online and get access to the course.",
                "knowledge_domain": "Deutsch als Fremdsprache",
                "target_audience": "Ukrainischsprachige Lernende in Deutschland",
                "tags": ["deutsch", level.lower(), "hefner-sprach-hub"],
                "skills": ["sprechen", "hÃ¶ren", "lesen", "schreiben"],
            }
            for level, price, lessons_count, summary in german_levels
        ]

        faq_template = [
            (
                "Wie laufen die Online-Sitzungen ab?",
                "How are the online sessions structured?",
                "Jede Sitzung folgt einem klaren Ablauf mit Demo, Ãœbung und Feedback.",
                "Each session follows a clear structure with demo, practice, and feedback.",
            ),
            (
                "Bekomme ich Zugriff auf Materialien?",
                "Do I get access to materials?",
                "Ja, Sie erhalten strukturierte Materialien und weiterfÃ¼hrende Ãœbungen.",
                "Yes, you receive structured materials and follow-up exercises.",
            ),
            (
                "Kann ich spÃ¤ter einsteigen?",
                "Can I join later?",
                "Bei freien PlÃ¤tzen ist ein spÃ¤ter Einstieg mÃ¶glich. Kontaktieren Sie uns.",
                "Late enrollment is possible if seats are available. Contact us.",
            ),
        ]

        for course_data in courses_data:
            course, _ = OnlineCourse.objects.update_or_create(
                slug=course_data["slug"],
                defaults=course_data,
            )
            level = str(course_data["slug"]).replace("deutsch-", "").upper()
            if level in GERMAN_LEVEL_CONTENT:
                upsert_course_structure(course, None, modules_data=build_german_level_modules(level))
            self.stdout.write(self.style.SUCCESS(f"Course upserted: {course.slug}"))

            for idx, (q_de, q_en, a_de, a_en) in enumerate(faq_template, start=1):
                OnlineCourseFaq.objects.update_or_create(
                    course=course,
                    sort_order=idx,
                    defaults={
                        "question_de": q_de,
                        "question_en": q_en,
                        "answer_de": a_de,
                        "answer_en": a_en,
                        "is_active": True,
                    },
                )

            OnlineCourseMaterial.objects.update_or_create(
                course=course,
                title="Kursleitfaden / Course Guide",
                language="de",
                material_type=OnlineCourseMaterial.MATERIAL_RESOURCE,
                defaults={
                    "description": "Struktur, Ziele und empfohlener Wochenablauf.",
                    "link_url": "",
                    "sort_order": 1,
                    "is_active": True,
                },
            )
            OnlineCourseMaterial.objects.update_or_create(
                course=course,
                title="Teilnahmebedingungen / Terms",
                language="de",
                material_type=OnlineCourseMaterial.MATERIAL_CONDITION,
                defaults={
                    "description": "Rahmenbedingungen, Kommunikation und Supportwege.",
                    "link_url": "",
                    "sort_order": 2,
                    "is_active": True,
                },
            )

            cohort, _ = OnlineCohort.objects.update_or_create(
                group_code=f"{course.slug.upper().replace('-', '_')}_G1",
                defaults={
                    "course": course,
                    "name": f"{course.title_de} - Gruppe 1",
                    "capacity": 24,
                    "timezone": "Europe/Berlin",
                    "start_date": next_monday,
                    "end_date": next_monday + timedelta(days=90),
                    "status": OnlineCohort.STATUS_OPEN,
                    "is_public": True,
                },
            )

            if not cohort.sessions.exists():
                lesson_count = max(1, int(course.lessons_count))
                for idx in range(1, lesson_count + 1):
                    start_dt = datetime.combine(next_monday + timedelta(days=(idx - 1) * 7), time(18, 0)).replace(
                        tzinfo=berlin_tz
                    )
                    end_dt = start_dt + timedelta(hours=2)
                    OnlineSession.objects.create(
                        cohort=cohort,
                        title=f"Lektion {idx}",
                        description="Live-Unterricht mit Ãœbung und Feedback.",
                        starts_at=start_dt,
                        ends_at=end_dt,
                        status=OnlineSession.STATUS_SCHEDULED,
                        join_url="https://teams.microsoft.com/",
                        sort_order=idx,
                        is_completed=False,
                    )
                self.stdout.write(
                    self.style.SUCCESS(f"Created {lesson_count} sessions for cohort {cohort.group_code}")
                )

        self.stdout.write(self.style.SUCCESS("Online data seeding completed."))
