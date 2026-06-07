from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.training.models import TrainingContentItem
from apps.training.services.knowledge_base import ensure_training_content_indexed


class Command(BaseCommand):
    help = "Rebuild the training knowledge index for published content items."

    def add_arguments(self, parser):
        parser.add_argument("--slug", dest="slug", default="", help="Rebuild only a single content item slug.")
        parser.add_argument("--course", dest="course_slug", default="", help="Rebuild only content for a course slug.")

    def handle(self, *args, **options):
        queryset = TrainingContentItem.objects.filter(status=TrainingContentItem.Status.PUBLISHED).order_by("course_id", "name", "id")
        slug = str(options.get("slug") or "").strip()
        course_slug = str(options.get("course_slug") or "").strip()
        if slug:
            queryset = queryset.filter(slug=slug)
        if course_slug:
            queryset = queryset.filter(course__slug=course_slug)

        rebuilt = 0
        total_chunks = 0
        for content_item in queryset.iterator():
            chunks = ensure_training_content_indexed(content_item)
            rebuilt += 1
            total_chunks += len(chunks)
            self.stdout.write(f"[ok] {content_item.slug}: {len(chunks)} chunk(s)")

        self.stdout.write(
            self.style.SUCCESS(
                f"Knowledge index rebuild finished. content_items={rebuilt}, chunks={total_chunks}"
            )
        )
