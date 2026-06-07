from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand

from apps.online.models import (
    OnlineCohort,
    OnlineCourse,
    OnlineCourseFaq,
    OnlineCourseMaterial,
    OnlineSession,
)


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
                    "Warm-up, kurze Demonstration, gefuehrte Uebung und Feedbackrunde. "
                    "Das Format entspricht gaengigen Einstiegssessions aus bekannten Lernplattformen: "
                    "niedrige Einstiegshuerde, klarer Lernfokus, sofortige Interaktion."
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
                    "Projektbasierter Kurs nach bewaehrtem Bootcamp-Prinzip: jeden Tag ein klarer Schritt "
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
                "short_description_de": "Webinar-Format mit Live-Session und Replay fuer vertieftes Lernen.",
                "short_description_en": "Webinar format with live lesson and replay for deeper learning.",
                "description_de": (
                    "Masterclass im Webinar-Stil mit praxisnahen Demos, Q&A und Aufzeichnung. "
                    "Das Design folgt gaengigen Virtual-Classroom-Standards: klare Agenda, "
                    "strukturierte Materialpakete, Nachbereitung ueber Replay und Lernnotizen."
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
                "seo_description_de": "Live-Webinar mit Q&A und Replay fuer flexible Nachbereitung.",
                "seo_description_en": "Live webinar with Q&A and replay access for flexible review.",
            },
            {
                "slug": "studio-club-subscription",
                "title_de": "Studio-Club Abo: Bibliothek + woechentliche Treffen",
                "title_en": "Studio Club Subscription: Library + Weekly Meetups",
                "short_description_de": "Abo-Modell mit On-Demand-Bibliothek und Live-Community-Treffen.",
                "short_description_en": "Subscription model with on-demand library and live community meetups.",
                "description_de": (
                    "Mitgliedschaft im Studio-Club mit Zugriff auf eine kuratierte Video-Bibliothek "
                    "und regelmaessigen Live-Sessions. Das Modell orientiert sich an bewaehrten "
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
                "seo_title_de": "Studio-Club Online Abo fuer Kunstkurse",
                "seo_title_en": "Studio Club Online Art Subscription",
                "seo_description_de": "Video-Bibliothek und Live-Treffen im flexiblen Online-Abo.",
                "seo_description_en": "Lesson library and live meetups in a flexible online subscription.",
            },
            {
                "slug": "kids-painting-course",
                "title_de": "Kinder-Malkurs: Farben und Fantasie",
                "title_en": "Kids Painting Course: Colors and Imagination",
                "short_description_de": "Spielerischer Live-Kurs fuer Kinder mit kreativen Wochenprojekten.",
                "short_description_en": "Playful live course for kids with creative weekly projects.",
                "description_de": (
                    "Dieser Kurs vermittelt Kindern die Grundlagen von Farbe, Form und Komposition "
                    "in klaren, altersgerechten Schritten. Der Aufbau folgt bewaehrten Kreativmodellen "
                    "fuer junge Lernende: kurze Inputs, praktische Uebungen und motivierendes Feedback."
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
                "seo_title_de": "Online-Malkurs fuer Kinder",
                "seo_title_en": "Online Painting Course for Kids",
                "seo_description_de": "Kreativer Kinderkurs mit Live-Unterricht und spielerischen Projekten.",
                "seo_description_en": "Creative kids course with live lessons and playful projects.",
            },
            {
                "slug": "tattoo-design-course",
                "title_de": "Tattoo Design Studio: Entwirf dein eigenes Tattoo",
                "title_en": "Tattoo Design Studio: Create Your Own Tattoo",
                "short_description_de": "Von Idee bis fertigem Entwurf: Linienfuehrung, Stil und Komposition.",
                "short_description_en": "From idea to finished concept: linework, style, and composition.",
                "description_de": (
                    "Der Kurs orientiert sich an professionellen Tattoo-Design-Workflows: "
                    "Referenzrecherche, Thumbnail-Skizzen, saubere Linien, Schattenaufbau und finale Praesentation. "
                    "Ideal fuer Einsteigerinnen und Einsteiger mit Interesse an Motiventwicklung."
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

        faq_template = [
            (
                "Wie laufen die Online-Sitzungen ab?",
                "How are the online sessions structured?",
                "Jede Sitzung folgt einem klaren Ablauf mit Demo, Uebung und Feedback.",
                "Each session follows a clear structure with demo, practice, and feedback.",
            ),
            (
                "Bekomme ich Zugriff auf Materialien?",
                "Do I get access to materials?",
                "Ja, Sie erhalten strukturierte Materialien und weiterfuehrende Uebungen.",
                "Yes, you receive structured materials and follow-up exercises.",
            ),
            (
                "Kann ich spaeter einsteigen?",
                "Can I join later?",
                "Bei freien Plaetzen ist ein spaeter Einstieg moeglich. Kontaktieren Sie uns.",
                "Late enrollment is possible if seats are available. Contact us.",
            ),
        ]

        for course_data in courses_data:
            course, _ = OnlineCourse.objects.update_or_create(
                slug=course_data["slug"],
                defaults=course_data,
            )
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
                        description="Live-Unterricht mit Uebung und Feedback.",
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
