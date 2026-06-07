from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.online.models import OnlineEnrollment, OnlineSession, OnlineSessionReminder
from apps.online.services.email_service import send_session_reminder_email


class Command(BaseCommand):
    help = "Send reminder emails to online students before sessions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=str,
            default="24,1",
            help="Comma-separated reminder offsets in hours (example: 24,1).",
        )
        parser.add_argument(
            "--window-minutes",
            type=int,
            default=10,
            help="Time window in minutes for selecting upcoming sessions per offset.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Scan candidates without creating reminder logs or sending emails.",
        )

    def handle(self, *args, **options):
        raw_hours = str(options["hours"] or "").strip()
        try:
            offsets = sorted(
                {
                    int(part.strip())
                    for part in raw_hours.split(",")
                    if part.strip()
                    and int(part.strip()) > 0
                },
                reverse=True,
            )
        except ValueError as exc:
            raise CommandError("Invalid --hours value. Use comma-separated positive integers.") from exc

        if not offsets:
            self.stdout.write(self.style.WARNING("No valid reminder offsets provided. Nothing to do."))
            return

        window_minutes = max(1, int(options["window_minutes"]))
        dry_run = bool(options["dry_run"])
        now = timezone.now()

        scanned = 0
        candidates = 0
        created_logs = 0
        skipped_existing = 0
        sent = 0
        failed = 0

        for hours_before in offsets:
            start_from = now + timedelta(hours=hours_before)
            start_to = start_from + timedelta(minutes=window_minutes)
            sessions = (
                OnlineSession.objects.filter(
                    starts_at__gte=start_from,
                    starts_at__lt=start_to,
                    status__in=(OnlineSession.STATUS_SCHEDULED, OnlineSession.STATUS_LIVE),
                )
                .select_related("cohort")
                .order_by("starts_at")
            )
            for session in sessions:
                scanned += 1
                enrollments = (
                    OnlineEnrollment.objects.filter(
                        cohort=session.cohort,
                        status__in=(OnlineEnrollment.STATUS_TRIAL, OnlineEnrollment.STATUS_ACTIVE),
                    )
                    .select_related("profile", "profile__user")
                    .order_by("id")
                )
                for enrollment in enrollments:
                    candidates += 1
                    if dry_run:
                        continue
                    reminder, created = OnlineSessionReminder.objects.get_or_create(
                        enrollment=enrollment,
                        session=session,
                        hours_before=hours_before,
                        defaults={"email_sent": False},
                    )
                    if not created:
                        skipped_existing += 1
                        continue
                    created_logs += 1
                    email_sent = send_session_reminder_email(
                        enrollment.profile,
                        session,
                        hours_before=hours_before,
                    )
                    if reminder.email_sent != email_sent:
                        reminder.email_sent = email_sent
                        reminder.save(update_fields=["email_sent"])
                    if email_sent:
                        sent += 1
                    else:
                        failed += 1

        mode_label = "dry-run" if dry_run else "send"
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Online reminders ({mode_label}) finished. "
                    f"sessions_scanned={scanned}, candidates={candidates}, "
                    f"logs_created={created_logs}, skipped_existing={skipped_existing}, "
                    f"sent={sent}, failed={failed}"
                )
            )
        )
