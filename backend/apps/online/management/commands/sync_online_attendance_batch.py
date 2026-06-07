from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.online.models import OnlineSession
from apps.online.services.attendance_service import sync_session_attendance_and_stamp


class Command(BaseCommand):
    help = "Batch-sync attendance for ended online sessions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--session-id",
            action="append",
            type=int,
            dest="session_ids",
            help="Optional session id (can be repeated).",
        )
        parser.add_argument(
            "--lookback-hours",
            type=int,
            default=48,
            help="Process sessions ended in the last N hours.",
        )
        parser.add_argument(
            "--retry-minutes",
            type=int,
            default=30,
            help="Skip sessions synced more recently than this window.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum sessions per run.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ignore lookback/retry windows and process selected sessions directly.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List candidates without syncing.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        session_ids = options.get("session_ids") or []
        lookback_hours = max(0, int(options.get("lookback_hours") or 0))
        retry_minutes = max(0, int(options.get("retry_minutes") or 0))
        limit = max(1, int(options.get("limit") or 1))
        force = bool(options.get("force"))
        dry_run = bool(options.get("dry_run"))

        queryset = OnlineSession.objects.filter(
            status=OnlineSession.STATUS_ENDED,
            ends_at__lte=now,
        ).order_by("ends_at", "id")

        if session_ids:
            queryset = queryset.filter(id__in=session_ids)

        if not force and not session_ids and lookback_hours > 0:
            queryset = queryset.filter(ends_at__gte=now - timedelta(hours=lookback_hours))

        if not force and retry_minutes > 0:
            retry_cutoff = now - timedelta(minutes=retry_minutes)
            queryset = queryset.filter(
                Q(attendance_synced_at__isnull=True)
                | Q(attendance_synced_at__lte=retry_cutoff)
            )

        sessions = list(queryset.select_related("cohort", "cohort__teacher")[:limit])
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Attendance batch dry-run: candidates={len(sessions)} "
                    f"ids={[session.id for session in sessions]}"
                )
            )
            return

        processed = 0
        synced = 0
        failed = 0
        summary_present = 0
        summary_absent = 0
        summary_excused = 0
        summary_unknown = 0

        for session in sessions:
            processed += 1
            try:
                result = sync_session_attendance_and_stamp(session=session)
                synced += 1
                summary_present += int(result.summary.get("present", 0))
                summary_absent += int(result.summary.get("absent", 0))
                summary_excused += int(result.summary.get("excused", 0))
                summary_unknown += int(result.summary.get("unknown", 0))
            except Exception as exc:  # noqa: BLE001 - keep batch resilient
                failed += 1
                self.stderr.write(f"[session {session.id}] sync failed: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                "Attendance batch finished. "
                f"processed={processed}, synced={synced}, failed={failed}, "
                f"summary_present={summary_present}, summary_absent={summary_absent}, "
                f"summary_excused={summary_excused}, summary_unknown={summary_unknown}"
            )
        )
