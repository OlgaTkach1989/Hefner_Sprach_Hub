from __future__ import annotations

from apps.training.models import TrainingGradebookEntry


def repeatable_lab_reentry_enabled(*, content_item, gradebook_entry: TrainingGradebookEntry | None) -> bool:
    return bool(
        getattr(content_item, "is_repeatable_on_demand", False)
        and gradebook_entry is not None
        and gradebook_entry.passed
    )
