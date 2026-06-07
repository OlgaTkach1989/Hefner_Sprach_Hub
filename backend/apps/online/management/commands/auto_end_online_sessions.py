from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.online.models import OnlineSession
from apps.online.services.session_lifecycle import auto_end_overdue_live_sessions


class Command(BaseCommand):
    help = "Auto-end overdue live online sessions and sync attendance."

    def add_arguments(self, parser):
        parser.add_argument(
            "--session-id",
            action="append",
            type=int,
            dest="session_ids",
            help="Optional session id to process. Can be repeated.",
        )
        parser.add_argument(
            "--grace-minutes",
            type=int,
            default=0,
            help="Only end sessions whose ends_at is older than now minus this grace window.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum sessions per run.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List candidates without ending them.",
        )

    def handle(self, *args, **options):
        session_ids = options.get("session_ids") or []
        grace_minutes = max(0, int(options.get("grace_minutes") or 0))
        limit = max(1, int(options.get("limit") or 1))
        dry_run = bool(options.get("dry_run"))

        if dry_run:
            queryset = (
                OnlineSession.objects.filter(
                    status=OnlineSession.STATUS_LIVE,
                    ends_at__lte=timezone.now() - timedelta(minutes=grace_minutes),
                )
                .order_by("ends_at", "id")
            )
            if session_ids:
                queryset = queryset.filter(id__in=session_ids)
            candidate_ids = list(queryset.values_list("id", flat=True)[:limit])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Auto-end dry-run: candidates={len(candidate_ids)} ids={candidate_ids}"
                )
            )
            return

        results = auto_end_overdue_live_sessions(
            grace_period=timedelta(minutes=grace_minutes),
            session_ids=session_ids,
            limit=limit,
        )
        processed = len(results)
        synced = sum(1 for item in results if item.sync_result is not None)
        sync_failed = sum(1 for item in results if item.sync_error)

        self.stdout.write(
            self.style.SUCCESS(
                "Auto-end finished. "
                f"processed={processed}, synced={synced}, sync_failed={sync_failed}, "
                f"session_ids={[item.session.id for item in results]}"
            )
        )
