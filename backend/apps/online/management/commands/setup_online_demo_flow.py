from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.employees.models import Lehrer
from apps.online.models import OnlineCohort, OnlineCourse, OnlineEnrollment, OnlineOrder, OnlineSession, OnlineStudentProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Prepare an end-to-end online lessons demo flow with test teacher, cohort, session, and demo students."

    @staticmethod
    def _make_unique_username(base: str) -> str:
        cleaned = (base or "online_demo_user").strip().replace(" ", "_").lower()[:40]
        candidate = cleaned
        index = 1
        while User.objects.filter(username=candidate).exists():
            index += 1
            candidate = f"{cleaned}_{index}"[:55]
        return candidate

    def add_arguments(self, parser):
        parser.add_argument("--teacher-email", type=str, default="test.dozent.dozent@kunstschuleberlin.de")
        parser.add_argument("--teacher-password", type=str, default="TestDozent12345!")
        parser.add_argument("--student-password", type=str, default="TestStudent12345!")
        parser.add_argument("--course-slug", type=str, default="trial-group-lesson")
        parser.add_argument("--cohort-code", type=str, default="TRIAL_GROUP_LESSON_G1")
        parser.add_argument("--students", type=int, default=0)
        parser.add_argument("--join-url", type=str, default="")
        parser.add_argument(
            "--keep-join-url-empty",
            action="store_true",
            help="Do not set session join_url. Teacher open endpoint will auto-create Teams meeting in graph mode.",
        )
        parser.add_argument("--starts-in-minutes", type=int, default=60)
        parser.add_argument("--duration-minutes", type=int, default=120)
        parser.add_argument(
            "--reschedule-existing",
            action="store_true",
            help="When matching upcoming session exists, reschedule it to starts-in-minutes/duration-minutes window.",
        )
        parser.add_argument("--session-title", type=str, default="Probestunde mit Lehrkraft in der Gruppe")

    def handle(self, *args, **options):
        teacher_email = str(options["teacher_email"]).strip().lower()
        teacher_password = str(options["teacher_password"]).strip()
        student_password = str(options["student_password"]).strip()
        course_slug = str(options["course_slug"]).strip()
        cohort_code = str(options["cohort_code"]).strip().upper()
        students_count = max(0, int(options["students"]))
        join_url = str(options["join_url"]).strip()
        keep_join_url_empty = bool(options.get("keep_join_url_empty"))
        starts_in_minutes = max(0, int(options.get("starts_in_minutes") or 0))
        duration_minutes = max(5, int(options.get("duration_minutes") or 0))
        reschedule_existing = bool(options.get("reschedule_existing"))
        session_title = str(options["session_title"]).strip() or "Probestunde mit Lehrkraft in der Gruppe"

        teacher_user, _ = User.objects.get_or_create(
            email=teacher_email,
            defaults={
                "username": self._make_unique_username("test_dozent_dozent"),
                "first_name": "Test",
                "last_name": "Dozent",
                "is_staff": True,
            },
        )
        teacher_user.set_password(teacher_password)
        teacher_user.is_staff = True
        teacher_user.save(update_fields=["password", "is_staff"])

        teacher_profile, teacher_created = Lehrer.objects.get_or_create(
            user=teacher_user,
            defaults={
                "Nachname": "Dozent",
                "Vorname": "Test",
                "Schule_Email": teacher_email,
                "Private_Email": f"{teacher_email}.private",
                "KurzName": "TDOZENT",
            },
        )

        course, course_created = OnlineCourse.objects.get_or_create(
            slug=course_slug,
            defaults={
                "title_de": "Probestunde mit Lehrkraft in der Gruppe",
                "title_en": "Trial Group Lesson with Instructor",
                "short_description_de": "Kostenlose Probestunde in kleiner Gruppe mit Live-Feedback.",
                "short_description_en": "Free trial lesson in a small group with live instructor feedback.",
                "description_de": "Automatisch vorbereitete Probestunde fuer den End-to-End-Testlauf.",
                "description_en": "Automatically prepared trial lesson for end-to-end demo flow.",
                "lessons_count": 1,
                "trial_available": True,
                "price_amount": Decimal("0.00"),
                "currency": "EUR",
                "is_subscription": False,
                "is_published": True,
            },
        )
        if not course.is_published:
            course.is_published = True
            course.save(update_fields=["is_published", "updated_at"])

        cohort, cohort_created = OnlineCohort.objects.get_or_create(
            group_code=cohort_code,
            defaults={
                "course": course,
                "teacher": teacher_profile,
                "name": "Webinar Demo Group",
                "capacity": max(10, students_count + 2),
                "timezone": "Europe/Berlin",
                "status": OnlineCohort.STATUS_OPEN,
                "is_public": True,
            },
        )
        cohort.course = course
        cohort.teacher = teacher_profile
        cohort.status = OnlineCohort.STATUS_OPEN
        cohort.is_public = True
        if cohort.capacity < students_count + 2:
            cohort.capacity = students_count + 2
        cohort.save(update_fields=["course", "teacher", "status", "is_public", "capacity", "updated_at"])

        starts_at = timezone.now() + timedelta(minutes=starts_in_minutes)
        ends_at = starts_at + timedelta(minutes=duration_minutes)
        session = (
            cohort.sessions.filter(starts_at__gte=timezone.now() - timedelta(hours=1))
            .order_by("starts_at")
            .first()
        )
        default_demo_join_url = "https://teams.microsoft.com/l/meetup-join/demo-online-session"
        target_join_url = ""
        if not keep_join_url_empty:
            target_join_url = join_url or default_demo_join_url

        if session is None:
            session = OnlineSession.objects.create(
                cohort=cohort,
                title=session_title,
                starts_at=starts_at,
                ends_at=ends_at,
                status=OnlineSession.STATUS_SCHEDULED,
                join_url=target_join_url,
                description="Demo lesson prepared by setup_online_demo_flow command.",
                is_completed=False,
            )
        else:
            update_fields: list[str] = []
            if session.title != session_title:
                session.title = session_title
                update_fields.append("title")
            if keep_join_url_empty:
                if session.join_url:
                    session.join_url = ""
                    update_fields.append("join_url")
                if session.provider_meeting_id:
                    session.provider_meeting_id = ""
                    update_fields.append("provider_meeting_id")
            elif join_url and session.join_url != join_url:
                session.join_url = join_url
                update_fields.append("join_url")
            elif not session.join_url:
                session.join_url = default_demo_join_url
                update_fields.append("join_url")
            if reschedule_existing and (session.starts_at != starts_at or session.ends_at != ends_at):
                session.starts_at = starts_at
                session.ends_at = ends_at
                update_fields.extend(["starts_at", "ends_at"])
            if update_fields:
                session.save(update_fields=update_fields + ["updated_at"])

        created_students = 0
        activated_enrollments = 0
        for index in range(1, students_count + 1):
            student_email = f"online.demo.student{index}@kunstschuleberlin.de"
            student_user, student_user_created = User.objects.get_or_create(
                email=student_email,
                defaults={
                    "username": self._make_unique_username(f"online_demo_student_{index}"),
                    "first_name": f"Demo{index}",
                    "last_name": "Student",
                },
            )
            if student_user_created:
                created_students += 1
            student_user.set_password(student_password)
            student_user.save(update_fields=["password"])

            profile, _ = OnlineStudentProfile.objects.get_or_create(
                user=student_user,
                defaults={
                    "first_name": f"Demo{index}",
                    "last_name": "Student",
                    "phone": "",
                    "preferred_language": "de",
                },
            )

            is_trial_course = bool(course.trial_available and course.price_amount <= 0)
            order_defaults = {
                "profile": profile,
                "course": course,
                "cohort": cohort,
                "provider": OnlineOrder.PROVIDER_TRIAL if is_trial_course else OnlineOrder.PROVIDER_PAYPAL,
                "status": OnlineOrder.STATUS_TRIAL if is_trial_course else OnlineOrder.STATUS_PAID,
                "amount": Decimal("0.00") if is_trial_course else course.price_amount,
                "currency": course.currency,
                "is_trial": is_trial_course,
                "paid_at": timezone.now(),
                "provider_payment_id": f"demo_pay_{cohort_code}_{index}",
                "external_reference": f"demo_order_{cohort_code}_{index}",
            }
            order, _ = OnlineOrder.objects.get_or_create(
                idempotency_key=f"demo-flow-{cohort_code}-{index}",
                defaults=order_defaults,
            )
            expected_status = OnlineOrder.STATUS_TRIAL if is_trial_course else OnlineOrder.STATUS_PAID
            if order.status != expected_status:
                order.status = expected_status
                order.paid_at = timezone.now()
                order.is_trial = is_trial_course
                order.provider = OnlineOrder.PROVIDER_TRIAL if is_trial_course else OnlineOrder.PROVIDER_PAYPAL
                order.amount = Decimal("0.00") if is_trial_course else course.price_amount
                order.save(update_fields=["status", "paid_at", "is_trial", "provider", "amount", "updated_at"])

            enrollment, enrollment_created = OnlineEnrollment.objects.get_or_create(
                profile=profile,
                cohort=cohort,
                defaults={
                    "course": course,
                    "order": order,
                    "status": OnlineEnrollment.STATUS_TRIAL if is_trial_course else OnlineEnrollment.STATUS_ACTIVE,
                },
            )
            expected_enrollment_status = OnlineEnrollment.STATUS_TRIAL if is_trial_course else OnlineEnrollment.STATUS_ACTIVE
            if enrollment.status != expected_enrollment_status or enrollment.order_id != order.id:
                enrollment.status = expected_enrollment_status
                enrollment.order = order
                enrollment.save(update_fields=["status", "order"])
            if enrollment_created:
                activated_enrollments += 1

        self.stdout.write(self.style.SUCCESS("Online demo flow is ready."))
        self.stdout.write(
            "\n".join(
                [
                    f"Teacher email: {teacher_email}",
                    f"Teacher profile created: {'yes' if teacher_created else 'no'}",
                    f"Course slug: {course.slug} (created: {'yes' if course_created else 'no'})",
                    f"Cohort code: {cohort.group_code} (created: {'yes' if cohort_created else 'no'})",
                    f"Session id: {session.id}, starts_at={session.starts_at}, ends_at={session.ends_at}, join_url={session.join_url or '<empty>'}",
                    f"Auto-create mode: {'enabled' if keep_join_url_empty else 'disabled'}",
                    f"Demo students created: {created_students}",
                    f"Enrollments created: {activated_enrollments}",
                    "Demo student emails: online.demo.student1@kunstschuleberlin.de ...",
                ]
            )
        )
