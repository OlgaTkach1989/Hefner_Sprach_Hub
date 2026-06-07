from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from apps.training.services.grading import process_pending_grader_jobs


class Command(BaseCommand):
    help = "Process queued training grader jobs."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--worker-name", type=str, default="training-grader-worker")
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--sleep-seconds", type=int, default=15)

    def handle(self, *args, **options):
        limit = max(int(options["limit"]), 1)
        worker_name = str(options["worker_name"] or "training-grader-worker").strip() or "training-grader-worker"
        loop = bool(options["loop"])
        sleep_seconds = max(int(options["sleep_seconds"]), 1)

        while True:
            summary = process_pending_grader_jobs(limit=limit, worker_name=worker_name)
            self.stdout.write(
                self.style.SUCCESS(
                    "Training grader jobs finished. "
                    f"processed={summary['processed']}, "
                    f"succeeded={summary['succeeded']}, "
                    f"failed={summary['failed']}"
                )
            )
            if not loop:
                break
            time.sleep(sleep_seconds)
