from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.online.models import OnlineCohort, OnlineCourse, OnlineEnrollment, OnlineStudentProfile
from apps.training.models import TrainingContentCrossReference, TrainingContentItem
from apps.training.services.knowledge_base import ensure_training_content_indexed

User = get_user_model()


class Command(BaseCommand):
    help = "Seed a demo training module for the AI assistant workflow."

    def add_arguments(self, parser):
        parser.add_argument(
            "--student-email",
            dest="student_email",
            default="",
            help="Optionally enroll an existing student user into the demo course.",
        )

    def handle(self, *args, **options):
        course, _created = OnlineCourse.objects.get_or_create(
            slug="investment-analysis-demo",
            defaults={
                "title_de": "Fundamentals of Investment Analysis",
                "title_en": "Fundamentals of Investment Analysis",
                "short_description_de": "AI demo module",
                "short_description_en": "AI demo module",
                "description_de": "Classic value-investing principles for AI-assisted learning demos.",
                "description_en": "Classic value-investing principles for AI-assisted learning demos.",
                "lessons_count": 3,
                "trial_available": False,
                "price_amount": Decimal("0.00"),
                "currency": "EUR",
            },
        )
        cohort, _created = OnlineCohort.objects.get_or_create(
            course=course,
            group_code="IA-DEMO",
            defaults={
                "name": "Investment Analysis Demo Cohort",
                "capacity": 100,
                "timezone": "Europe/Berlin",
                "status": OnlineCohort.STATUS_OPEN,
                "is_public": False,
            },
        )

        module = self._upsert_content(
            slug="fundamentals-of-investment-analysis",
            name="Fundamentals of Investment Analysis",
            description="A repeatable demo module for AI-assisted learning around investment analysis concepts.",
            body_markdown=(
                "## Margin of Safety\n"
                "A prudent investor does not rely on a perfect forecast. The margin of safety is the buffer between an estimate of value and the price paid, which helps absorb mistakes and uncertainty.\n\n"
                "## Investment versus Speculation\n"
                "Investment is grounded in analysis, valuation discipline, and downside protection. Speculation is more dependent on market psychology and short-term price moves.\n\n"
                "## Risk Review\n"
                "A strong process asks what can go wrong, how concentrated the position is, and whether the downside case is survivable before capital is committed."
            ),
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            course=course,
            estimated_minutes=20,
            source_url="https://example.com/investment-analysis-demo",
        )
        faq = self._upsert_content(
            slug="investment-analysis-faq",
            name="Investment Analysis FAQ",
            description="Compact answers for the AI assistant demo.",
            body_markdown=(
                "## What is margin of safety?\n"
                "It is a deliberate gap between estimated value and purchase price.\n\n"
                "## Why distinguish investment from speculation?\n"
                "Because discipline, downside review, and time horizon change the quality of the decision.\n\n"
                "## What should a junior analyst focus on first?\n"
                "Start with assumptions, downside cases, and the reason the market price differs from your estimate of value."
            ),
            content_kind=TrainingContentItem.ContentKind.FAQ,
            course=course,
            estimated_minutes=8,
        )
        exercise = self._upsert_content(
            slug="investment-analysis-quiz-prep",
            name="Investment Analysis Quiz Prep",
            description="Practice prompts for the knowledge-to-assessment loop.",
            body_markdown=(
                "## Key takeaways\n"
                "Always connect valuation to uncertainty, distinguish analysis from momentum-driven behavior, and state the main risks before recommending a trade.\n\n"
                "## Practice prompts\n"
                "Summarize the chapter in simple words. Explain it to a junior analyst. Identify the three most important risks."
            ),
            content_kind=TrainingContentItem.ContentKind.EXERCISE,
            course=course,
            estimated_minutes=10,
        )

        TrainingContentCrossReference.objects.get_or_create(
            from_item=module,
            to_item=faq,
            relation_type=TrainingContentCrossReference.RelationType.RELATED,
        )
        TrainingContentCrossReference.objects.get_or_create(
            from_item=module,
            to_item=exercise,
            relation_type=TrainingContentCrossReference.RelationType.FOLLOW_UP,
        )

        for item in (module, faq, exercise):
            ensure_training_content_indexed(item)

        student_email = str(options.get("student_email") or "").strip()
        if student_email:
            user = User.objects.filter(email=student_email).first()
            if user is None:
                raise CommandError(f"User with email '{student_email}' was not found.")
            profile, _created = OnlineStudentProfile.objects.get_or_create(
                user=user,
                defaults={
                    "first_name": user.first_name or "Demo",
                    "last_name": user.last_name or "Student",
                    "preferred_language": "en",
                },
            )
            OnlineEnrollment.objects.get_or_create(
                profile=profile,
                course=course,
                cohort=cohort,
                defaults={"status": OnlineEnrollment.STATUS_ACTIVE},
            )
            self.stdout.write(self.style.SUCCESS(f"Enrolled {student_email} into {course.slug}."))

        self.stdout.write(self.style.SUCCESS("AI demo training module is ready."))

    def _upsert_content(
        self,
        *,
        slug: str,
        name: str,
        description: str,
        body_markdown: str,
        content_kind: str,
        course: OnlineCourse,
        estimated_minutes: int,
        source_url: str = "",
    ) -> TrainingContentItem:
        item, _created = TrainingContentItem.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": description,
                "body_markdown": body_markdown,
                "content_kind": content_kind,
                "status": TrainingContentItem.Status.PUBLISHED,
                "access_scope": TrainingContentItem.AccessScope.ENTITLED,
                "course": course,
                "estimated_minutes": estimated_minutes,
                "source_url": source_url or None,
                "is_repeatable_on_demand": True,
            },
        )
        return item
