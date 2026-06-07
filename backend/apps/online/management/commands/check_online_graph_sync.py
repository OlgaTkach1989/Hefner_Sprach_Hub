from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.online.models import OnlineSession
from apps.online.services.graph_attendance_service import (
    GraphSyncNotConfigured,
    GraphSyncRequestError,
    probe_session_attendance_from_graph,
    sync_session_attendance_from_graph,
)


class Command(BaseCommand):
    help = "Check Microsoft Graph attendance connectivity for an online session. Use --sync to write attendance to DB."

    def add_arguments(self, parser):
        parser.add_argument("--session-id", type=int, required=True, help="OnlineSession.id to check.")
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run real graph sync and write attendance rows. Without this flag, command runs probe only.",
        )

    def handle(self, *args, **options):
        session_id = int(options["session_id"])
        do_sync = bool(options.get("sync"))

        session = (
            OnlineSession.objects.select_related("cohort", "cohort__teacher", "cohort__course")
            .filter(id=session_id)
            .first()
        )
        if session is None:
            raise CommandError(f"Online session with id={session_id} not found.")

        self.stdout.write(f"Session id: {session.id}")
        self.stdout.write(f"Course slug: {session.cohort.course.slug}")
        self.stdout.write(f"Cohort code: {session.cohort.group_code}")
        self.stdout.write(f"Session title: {session.title}")
        self.stdout.write(f"Join URL: {session.join_url or '-'}")
        self.stdout.write(f"Session status: {session.status}")

        try:
            if do_sync:
                sync_payload = sync_session_attendance_from_graph(session=session)
                self.stdout.write(self.style.SUCCESS("Graph sync succeeded."))
                self.stdout.write(f"Meeting id: {sync_payload.meeting_id}")
                self.stdout.write(f"Report id: {sync_payload.report_id}")
                self.stdout.write(f"Students total: {sync_payload.students_total}")
                self.stdout.write(f"Attendance rows total: {sync_payload.rows_total}")
                self.stdout.write(
                    "Attendance summary: "
                    f"present={sync_payload.summary.get('present', 0)}, "
                    f"absent={sync_payload.summary.get('absent', 0)}, "
                    f"excused={sync_payload.summary.get('excused', 0)}, "
                    f"unknown={sync_payload.summary.get('unknown', 0)}"
                )
            else:
                probe_payload = probe_session_attendance_from_graph(session=session)
                self.stdout.write(self.style.SUCCESS("Graph probe succeeded."))
                self.stdout.write(f"Organizer user id: {probe_payload.organizer_user_id}")
                self.stdout.write(f"Meeting id: {probe_payload.meeting_id}")
                self.stdout.write(f"Report id: {probe_payload.report_id}")
                self.stdout.write(f"Attendance records in latest report: {probe_payload.records_total}")
        except GraphSyncNotConfigured as exc:
            raise CommandError(f"Graph is not configured: {exc}") from exc
        except GraphSyncRequestError as exc:
            raise CommandError(f"Graph request failed: {exc}") from exc
