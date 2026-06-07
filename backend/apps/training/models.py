from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from apps.online.models import OnlineCourse


class TrainingAudience(models.Model):
    class AudienceType(models.TextChoices):
        GENERAL = "general", "General audience"
        DEMO_ROLE = "demo_role", "Demo access role"

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    short_label = models.CharField(max_length=40, blank=True, default="")
    description = models.TextField(blank=True, default="")
    audience_type = models.CharField(
        max_length=20,
        choices=AudienceType.choices,
        default=AudienceType.GENERAL,
    )
    privilege_rank = models.PositiveSmallIntegerField(default=0)
    is_internal = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_audience"
        ordering = ("audience_type", "privilege_rank", "name", "id")
        indexes = [
            models.Index(fields=("is_active",)),
            models.Index(fields=("is_internal",)),
            models.Index(fields=("audience_type", "is_active")),
            models.Index(fields=("audience_type", "privilege_rank")),
        ]

    def __str__(self) -> str:
        return self.name


class TrainingAssetClass(models.Model):
    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_asset_class"
        ordering = ("name", "id")
        indexes = [
            models.Index(fields=("is_active",)),
        ]

    def __str__(self) -> str:
        return self.name


class TrainingTopic(models.Model):
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="children",
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_topic"
        ordering = ("name", "id")
        indexes = [
            models.Index(fields=("is_active",)),
        ]

    def __str__(self) -> str:
        return self.name


class TrainingCourseRoleAssignment(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Course Owner"
        COURSE_OWNER = "course_owner", "Course Owner"
        KNOWLEDGE_OWNER = "knowledge_owner", "Knowledge Owner"
        LAB_OWNER = "lab_owner", "Lab Owner"
        REVIEWER = "reviewer", "Reviewer"
        INSTRUCTOR = "instructor", "Instructor"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="training_course_roles",
    )
    course = models.ForeignKey(
        OnlineCourse,
        on_delete=models.CASCADE,
        related_name="training_role_assignments",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    is_primary = models.BooleanField(default=False)
    response_sla_hours = models.PositiveSmallIntegerField(default=24)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_course_role_assignment"
        ordering = ("course_id", "role", "user_id")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "course", "role"),
                name="training_course_role_assignment_unique_per_role",
            )
        ]
        indexes = [
            models.Index(fields=("role",)),
            models.Index(fields=("course",)),
        ]

    def __str__(self) -> str:
        return f"{self.course.slug}: {self.user_id} ({self.role})"


class TrainingUserAudienceGrant(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="training_audience_grants",
    )
    audience = models.ForeignKey(
        TrainingAudience,
        on_delete=models.CASCADE,
        related_name="user_grants",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="issued_training_audience_grants",
        blank=True,
        null=True,
    )
    note = models.CharField(max_length=255, blank=True, default="")
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_user_audience_grant"
        ordering = ("user_id", "audience_id")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "audience"),
                name="training_user_audience_grant_unique",
            )
        ]
        indexes = [
            models.Index(fields=("expires_at",)),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.audience.slug}"


class TrainingContentItem(models.Model):
    class ContentKind(models.TextChoices):
        ARTICLE = "article", "Article"
        VIDEO = "video", "Video"
        NOTEBOOK = "notebook", "Notebook"
        FAQ = "faq", "FAQ"
        RECORDING = "recording", "Recording"
        EXERCISE = "exercise", "Exercise"
        DATASET = "dataset", "Dataset"
        LINK = "link", "External Link"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "In Review"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    class AccessScope(models.TextChoices):
        PUBLIC = "public", "Public"
        AUTHENTICATED = "authenticated", "Authenticated"
        ENTITLED = "entitled", "Entitled"

    class Difficulty(models.TextChoices):
        FOUNDATION = "foundation", "Foundation"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    class AudienceMatchMode(models.TextChoices):
        ANY = "any", "Any audience"
        ALL = "all", "All audiences"

    class AuthoringSource(models.TextChoices):
        MANUAL = "manual", "Manual"
        DIRECTUS = "directus", "Directus"

    slug = models.SlugField(max_length=140, unique=True)
    name = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    body_markdown = models.TextField(blank=True, default="")
    content_kind = models.CharField(max_length=20, choices=ContentKind.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    access_scope = models.CharField(max_length=20, choices=AccessScope.choices, default=AccessScope.ENTITLED)
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices, default=Difficulty.INTERMEDIATE)
    audience_match_mode = models.CharField(
        max_length=10,
        choices=AudienceMatchMode.choices,
        default=AudienceMatchMode.ANY,
    )
    course = models.ForeignKey(
        OnlineCourse,
        on_delete=models.SET_NULL,
        related_name="training_content_items",
        blank=True,
        null=True,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="training_owned_content_items",
        blank=True,
        null=True,
    )
    authoring_source = models.CharField(
        max_length=20,
        choices=AuthoringSource.choices,
        default=AuthoringSource.MANUAL,
    )
    authoring_source_id = models.CharField(max_length=120, blank=True, default="")
    authoring_checksum = models.CharField(max_length=64, blank=True, default="")
    last_synced_at = models.DateTimeField(blank=True, null=True)
    source_url = models.URLField(blank=True, null=True)
    search_keywords = models.CharField(max_length=400, blank=True, default="")
    version_label = models.CharField(max_length=40, blank=True, default="")
    estimated_minutes = models.PositiveSmallIntegerField(default=0)
    is_repeatable_on_demand = models.BooleanField(default=True)
    supports_inline_lab = models.BooleanField(default=False)
    knowledge_indexed_at = models.DateTimeField(blank=True, null=True)
    published_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    asset_classes = models.ManyToManyField(
        TrainingAssetClass,
        related_name="content_items",
        blank=True,
    )
    topics = models.ManyToManyField(
        TrainingTopic,
        related_name="content_items",
        blank=True,
    )

    class Meta:
        db_table = "training_content_item"
        ordering = ("name", "id")
        indexes = [
            models.Index(fields=("status",)),
            models.Index(fields=("access_scope",)),
            models.Index(fields=("content_kind",)),
            models.Index(fields=("course",)),
            models.Index(fields=("authoring_source",)),
            models.Index(fields=("authoring_source", "authoring_source_id")),
        ]

    def __str__(self) -> str:
        return self.name


class TrainingContentAudiencePolicy(models.Model):
    content_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.CASCADE,
        related_name="audience_policies",
    )
    audience = models.ForeignKey(
        TrainingAudience,
        on_delete=models.CASCADE,
        related_name="content_policies",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "training_content_audience_policy"
        ordering = ("content_item_id", "audience_id")
        constraints = [
            models.UniqueConstraint(
                fields=("content_item", "audience"),
                name="training_content_audience_policy_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.content_item_id} -> {self.audience.slug}"


class TrainingContentCrossReference(models.Model):
    class RelationType(models.TextChoices):
        RELATED = "related", "Related"
        PREREQUISITE = "prerequisite", "Prerequisite"
        FOLLOW_UP = "follow_up", "Follow-up"
        USED_IN = "used_in", "Used In"

    from_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.CASCADE,
        related_name="outgoing_references",
    )
    to_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.CASCADE,
        related_name="incoming_references",
    )
    relation_type = models.CharField(max_length=20, choices=RelationType.choices, default=RelationType.RELATED)
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "training_content_cross_reference"
        ordering = ("from_item_id", "relation_type", "to_item_id")
        constraints = [
            models.UniqueConstraint(
                fields=("from_item", "to_item", "relation_type"),
                name="training_content_cross_reference_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.from_item_id} -> {self.to_item_id} ({self.relation_type})"


class TrainingRuntimePreset(models.Model):
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True, default="")
    runtime_image = models.CharField(max_length=180, blank=True, default="")
    package_profile = models.CharField(max_length=120, blank=True, default="")
    package_lock = models.JSONField(default=list, blank=True)
    internal_packages = models.JSONField(default=list, blank=True)
    tool_bindings = models.JSONField(default=dict, blank=True)
    allow_network = models.BooleanField(default=False)
    allow_gpu = models.BooleanField(default=False)
    math_support = models.BooleanField(default=True)
    version_label = models.CharField(max_length=40, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_runtime_preset"
        ordering = ("name", "id")
        indexes = [
            models.Index(fields=("is_active",)),
        ]

    def __str__(self) -> str:
        return self.name


class TrainingProgram(models.Model):
    class ProgramType(models.TextChoices):
        INTERNAL = "internal", "Internal"
        EXTERNAL = "external", "External"
        HYBRID = "hybrid", "Hybrid"

    class EntryMode(models.TextChoices):
        COHORT = "cohort", "Cohort"
        ON_DEMAND = "on_demand", "On-demand"
        HYBRID = "hybrid", "Hybrid"

    slug = models.SlugField(max_length=140, unique=True)
    name = models.CharField(max_length=220)
    summary = models.TextField(blank=True, default="")
    description_markdown = models.TextField(blank=True, default="")
    course = models.OneToOneField(
        OnlineCourse,
        on_delete=models.CASCADE,
        related_name="training_program",
    )
    runtime_preset = models.ForeignKey(
        "TrainingRuntimePreset",
        on_delete=models.SET_NULL,
        related_name="programs",
        blank=True,
        null=True,
    )
    program_type = models.CharField(
        max_length=20,
        choices=ProgramType.choices,
        default=ProgramType.INTERNAL,
    )
    entry_mode = models.CharField(
        max_length=20,
        choices=EntryMode.choices,
        default=EntryMode.COHORT,
    )
    target_roles = models.JSONField(default=list, blank=True)
    estimated_minutes = models.PositiveSmallIntegerField(default=0)
    is_certificate_enabled = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_program"
        ordering = ("course_id", "id")
        indexes = [
            models.Index(fields=("is_published",)),
            models.Index(fields=("program_type", "entry_mode")),
        ]

    def __str__(self) -> str:
        return self.name


class TrainingProgramModule(models.Model):
    program = models.ForeignKey(
        TrainingProgram,
        on_delete=models.CASCADE,
        related_name="modules",
    )
    slug = models.SlugField(max_length=140)
    title = models.CharField(max_length=220)
    summary = models.TextField(blank=True, default="")
    learning_objectives_markdown = models.TextField(blank=True, default="")
    estimated_minutes = models.PositiveSmallIntegerField(default=0)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_program_module"
        ordering = ("program_id", "sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("program", "slug"),
                name="training_program_module_slug_unique",
            )
        ]
        indexes = [
            models.Index(fields=("program", "is_active")),
        ]

    def __str__(self) -> str:
        return f"{self.program.slug}: {self.title}"


class TrainingProgramStep(models.Model):
    class StepType(models.TextChoices):
        VIDEO = "video", "Video"
        FORMULA = "formula", "Formula"
        NOTEBOOK = "notebook", "Notebook"
        SCENARIO = "scenario", "Scenario"
        AI_QUIZ = "ai_quiz", "AI Quiz"

    module = models.ForeignKey(
        TrainingProgramModule,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    slug = models.SlugField(max_length=140)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    body_markdown = models.TextField(blank=True, default="")
    step_type = models.CharField(max_length=20, choices=StepType.choices)
    content_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.SET_NULL,
        related_name="program_steps",
        blank=True,
        null=True,
    )
    runtime_preset = models.ForeignKey(
        "TrainingRuntimePreset",
        on_delete=models.SET_NULL,
        related_name="program_steps",
        blank=True,
        null=True,
    )
    estimated_minutes = models.PositiveSmallIntegerField(default=0)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    is_preview = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_program_step"
        ordering = ("module_id", "sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("module", "slug"),
                name="training_program_step_slug_unique",
            )
        ]
        indexes = [
            models.Index(fields=("module", "step_type")),
            models.Index(fields=("content_item",)),
        ]

    def __str__(self) -> str:
        return f"{self.module.program.slug}: {self.title}"


class TrainingProgramStepProgress(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="training_program_step_progress",
    )
    step = models.ForeignKey(
        TrainingProgramStep,
        on_delete=models.CASCADE,
        related_name="progress_entries",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    completed_via = models.CharField(max_length=40, blank=True, default="")
    started_at = models.DateTimeField(blank=True, null=True)
    last_viewed_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_program_step_progress"
        ordering = ("user_id", "step_id")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "step"),
                name="training_program_step_progress_unique",
            )
        ]
        indexes = [
            models.Index(fields=("status",)),
            models.Index(fields=("step",)),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.step_id} ({self.status})"


class TrainingCertificateRule(models.Model):
    program = models.OneToOneField(
        TrainingProgram,
        on_delete=models.CASCADE,
        related_name="certificate_rule",
    )
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    require_all_required_steps = models.BooleanField(default=True)
    minimum_completed_steps = models.PositiveSmallIntegerField(default=0)
    minimum_notebook_pass_count = models.PositiveSmallIntegerField(default=0)
    minimum_ai_quiz_score = models.PositiveSmallIntegerField(default=0)
    required_attendance_percent = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_certificate_rule"

    def __str__(self) -> str:
        return self.title


class TrainingContentSyncEvent(models.Model):
    class Source(models.TextChoices):
        DIRECTUS = "directus", "Directus"
        ADMIN = "admin", "Admin"
        COMMAND = "command", "Command"

    class EventType(models.TextChoices):
        UPSERT = "upsert", "Upsert"
        UNPUBLISH = "unpublish", "Unpublish"
        REINDEX = "reindex", "Reindex"

    class Status(models.TextChoices):
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    content_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.SET_NULL,
        related_name="sync_events",
        blank=True,
        null=True,
    )
    source = models.CharField(max_length=20, choices=Source.choices)
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUCCEEDED)
    external_source_id = models.CharField(max_length=120, blank=True, default="")
    content_slug = models.SlugField(max_length=140, blank=True, default="")
    detail = models.CharField(max_length=255, blank=True, default="")
    payload_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "training_content_sync_event"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("source", "status", "created_at")),
            models.Index(fields=("content_item", "created_at")),
            models.Index(fields=("content_slug",)),
        ]

    def __str__(self) -> str:
        return f"{self.source}:{self.event_type}:{self.content_slug or self.external_source_id}"


class TrainingNotebookLabProfile(models.Model):
    class RuntimeBackend(models.TextChoices):
        JUPYTERHUB = "jupyterhub", "JupyterHub"
        EXTERNAL = "external", "External"

    class GraderBackend(models.TextChoices):
        NONE = "none", "None"
        NBGRADER = "nbgrader", "nbgrader"
        OTTER = "otter", "Otter-Grader"
        CUSTOM = "custom", "Custom"

    content_item = models.OneToOneField(
        TrainingContentItem,
        on_delete=models.CASCADE,
        related_name="lab_profile",
    )
    runtime_preset = models.ForeignKey(
        "TrainingRuntimePreset",
        on_delete=models.SET_NULL,
        related_name="lab_profiles",
        blank=True,
        null=True,
    )
    runtime_backend = models.CharField(max_length=20, choices=RuntimeBackend.choices, default=RuntimeBackend.JUPYTERHUB)
    grader_backend = models.CharField(max_length=20, choices=GraderBackend.choices, default=GraderBackend.NONE)
    runtime_image = models.CharField(max_length=180, blank=True, default="")
    notebook_path = models.CharField(max_length=255)
    launch_path = models.CharField(max_length=255, blank=True, default="")
    assignment_code = models.SlugField(max_length=120, blank=True, default="")
    pass_threshold_percent = models.PositiveSmallIntegerField(default=70)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    grader_config = models.JSONField(default=dict, blank=True)
    allow_gpu = models.BooleanField(default=False)
    allow_network = models.BooleanField(default=False)
    max_session_minutes = models.PositiveSmallIntegerField(default=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_notebook_lab_profile"
        indexes = [
            models.Index(fields=("is_active",)),
            models.Index(fields=("runtime_backend",)),
        ]

    def __str__(self) -> str:
        return f"{self.content_item.slug} ({self.runtime_backend})"


class TrainingNotebookLabHint(models.Model):
    class AvailabilityMode(models.TextChoices):
        ALWAYS = "always", "Always visible"
        AFTER_ATTEMPT = "after_attempt", "Visible after attempt"
        AFTER_FAILURE = "after_failure", "Visible after failed attempt"
        AFTER_SCORE_BELOW = "after_score_below", "Visible below score threshold"

    lab_profile = models.ForeignKey(
        TrainingNotebookLabProfile,
        on_delete=models.CASCADE,
        related_name="hints",
    )
    title = models.CharField(max_length=180)
    body_markdown = models.TextField()
    availability_mode = models.CharField(
        max_length=20,
        choices=AvailabilityMode.choices,
        default=AvailabilityMode.ALWAYS,
    )
    min_attempt_number = models.PositiveSmallIntegerField(default=1)
    max_score_percent = models.PositiveSmallIntegerField(default=100)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_notebook_lab_hint"
        ordering = ("sort_order", "id")
        indexes = [
            models.Index(fields=("lab_profile", "is_active")),
            models.Index(fields=("availability_mode", "is_active")),
        ]

    def __str__(self) -> str:
        return f"{self.lab_profile.content_item.slug}: {self.title}"


class TrainingLabLaunchToken(models.Model):
    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"
        CONSUMED = "consumed", "Consumed"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    token_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="training_lab_launch_tokens",
    )
    content_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.CASCADE,
        related_name="lab_launch_tokens",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ISSUED)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(blank=True, null=True)
    requested_ip = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=400, blank=True, default="")
    audience_snapshot = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_lab_launch_token"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status",)),
            models.Index(fields=("expires_at",)),
            models.Index(fields=("content_item",)),
            models.Index(fields=("user",)),
        ]

    def __str__(self) -> str:
        return f"{self.token_id} ({self.content_item.slug})"


class TrainingJupyterLoginToken(models.Model):
    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"
        CONSUMED = "consumed", "Consumed"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    token_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    launch_token = models.ForeignKey(
        TrainingLabLaunchToken,
        on_delete=models.CASCADE,
        related_name="jupyter_login_tokens",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="training_jupyter_login_tokens",
    )
    content_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.CASCADE,
        related_name="jupyter_login_tokens",
    )
    jupyter_username = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ISSUED)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(blank=True, null=True)
    auth_state = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_jupyter_login_token"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status",)),
            models.Index(fields=("expires_at",)),
            models.Index(fields=("jupyter_username",)),
            models.Index(fields=("user",)),
        ]

    def __str__(self) -> str:
        return f"{self.token_id} ({self.jupyter_username})"


class TrainingLabSubmission(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        GRADED = "graded", "Graded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    class SubmissionMode(models.TextChoices):
        NOTEBOOK = "notebook", "Notebook"
        TEXT_ANSWER = "text_answer", "Text answer"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="training_lab_submissions",
    )
    content_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.CASCADE,
        related_name="lab_submissions",
    )
    launch_token = models.ForeignKey(
        TrainingLabLaunchToken,
        on_delete=models.SET_NULL,
        related_name="submissions",
        blank=True,
        null=True,
    )
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    submission_mode = models.CharField(
        max_length=20,
        choices=SubmissionMode.choices,
        default=SubmissionMode.NOTEBOOK,
    )
    grader_backend = models.CharField(max_length=20, choices=TrainingNotebookLabProfile.GraderBackend.choices)
    source_path = models.CharField(max_length=255, blank=True, default="")
    notebook_path = models.CharField(max_length=255, blank=True, default="")
    response_text = models.TextField(blank=True, default="")
    checksum = models.CharField(max_length=128, blank=True, default="")
    feedback_markdown = models.TextField(blank=True, default="")
    feedback_payload = models.JSONField(default=dict, blank=True)
    max_score = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    score = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    passed = models.BooleanField(blank=True, null=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    graded_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_lab_submission"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status",)),
            models.Index(fields=("content_item", "user")),
            models.Index(fields=("submitted_at",)),
        ]

    def __str__(self) -> str:
        return f"{self.public_id} ({self.content_item.slug})"

    def get_primary_notebook_artifact(self):
        prefetched_artifacts = getattr(self, "_prefetched_objects_cache", {}).get("artifacts")
        if prefetched_artifacts is not None:
            for artifact in prefetched_artifacts:
                if artifact.artifact_kind == TrainingLabSubmissionArtifact.ArtifactKind.NOTEBOOK:
                    return artifact
            return None
        return (
            self.artifacts.filter(artifact_kind=TrainingLabSubmissionArtifact.ArtifactKind.NOTEBOOK)
            .order_by("id")
            .first()
        )

    @property
    def has_notebook_artifact(self) -> bool:
        return self.get_primary_notebook_artifact() is not None

    @property
    def notebook_artifact_filename(self) -> str:
        artifact = self.get_primary_notebook_artifact()
        if artifact is None:
            return ""
        return Path(artifact.storage_path).name


class TrainingLabSubmissionArtifact(models.Model):
    class ArtifactKind(models.TextChoices):
        NOTEBOOK = "notebook", "Notebook"
        FEEDBACK_HTML = "feedback_html", "Feedback HTML"
        JSON_REPORT = "json_report", "JSON report"
        ATTACHMENT = "attachment", "Attachment"

    submission = models.ForeignKey(
        TrainingLabSubmission,
        on_delete=models.CASCADE,
        related_name="artifacts",
    )
    artifact_kind = models.CharField(max_length=20, choices=ArtifactKind.choices)
    storage_path = models.CharField(max_length=400)
    media_type = models.CharField(max_length=120, blank=True, default="")
    checksum = models.CharField(max_length=128, blank=True, default="")
    size_bytes = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "training_lab_submission_artifact"
        ordering = ("submission_id", "artifact_kind", "id")
        indexes = [
            models.Index(fields=("artifact_kind",)),
        ]

    def __str__(self) -> str:
        return f"{self.submission_id} ({self.artifact_kind})"


class TrainingGradebookEntry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="training_gradebook_entries",
    )
    content_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.CASCADE,
        related_name="gradebook_entries",
    )
    latest_submission = models.ForeignKey(
        TrainingLabSubmission,
        on_delete=models.SET_NULL,
        related_name="latest_gradebook_entries",
        blank=True,
        null=True,
    )
    best_submission = models.ForeignKey(
        TrainingLabSubmission,
        on_delete=models.SET_NULL,
        related_name="best_gradebook_entries",
        blank=True,
        null=True,
    )
    attempts_count = models.PositiveIntegerField(default=0)
    latest_score = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    best_score = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    max_score = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    passed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_gradebook_entry"
        ordering = ("content_item_id", "user_id")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "content_item"),
                name="training_gradebook_entry_unique",
            )
        ]
        indexes = [
            models.Index(fields=("passed",)),
            models.Index(fields=("content_item",)),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.content_item.slug}"


class TrainingGraderJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    submission = models.OneToOneField(
        TrainingLabSubmission,
        on_delete=models.CASCADE,
        related_name="grader_job",
    )
    backend = models.CharField(max_length=20, choices=TrainingNotebookLabProfile.GraderBackend.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    priority = models.PositiveSmallIntegerField(default=100)
    attempts_count = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField()
    locked_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    worker_name = models.CharField(max_length=120, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    result_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_grader_job"
        ordering = ("priority", "available_at", "id")
        indexes = [
            models.Index(fields=("status", "available_at")),
            models.Index(fields=("backend",)),
        ]

    def __str__(self) -> str:
        return f"{self.submission_id} ({self.backend})"


class TrainingAuditEvent(models.Model):
    class Category(models.TextChoices):
        CONTENT = "content", "Content"
        ENTITLEMENT = "entitlement", "Entitlement"
        LAB = "lab", "Lab"
        GRADING = "grading", "Grading"
        ADMIN = "admin", "Admin"
        AI = "ai", "AI"

    class Outcome(models.TextChoices):
        SUCCEEDED = "succeeded", "Succeeded"
        DENIED = "denied", "Denied"
        FAILED = "failed", "Failed"

    class EventType(models.TextChoices):
        CONTENT_LIST_VIEWED = "content.list_viewed", "Content list viewed"
        CONTENT_DETAIL_VIEWED = "content.detail_viewed", "Content detail viewed"
        CONTENT_ACCESS_DENIED = "content.access_denied", "Content access denied"
        ENTITLEMENTS_VIEWED = "entitlements.viewed", "Entitlements viewed"
        GRADEBOOK_VIEWED = "gradebook.viewed", "Gradebook viewed"
        ADMIN_AUDIENCE_CREATED = "admin.audience_created", "Admin audience created"
        ADMIN_AUDIENCE_UPDATED = "admin.audience_updated", "Admin audience updated"
        ADMIN_AUDIENCE_DELETED = "admin.audience_deleted", "Admin audience deleted"
        ADMIN_COURSE_ROLE_CREATED = "admin.course_role_created", "Admin course role created"
        ADMIN_COURSE_ROLE_UPDATED = "admin.course_role_updated", "Admin course role updated"
        ADMIN_COURSE_ROLE_DELETED = "admin.course_role_deleted", "Admin course role deleted"
        ADMIN_AUDIENCE_GRANT_CREATED = "admin.audience_grant_created", "Admin audience grant created"
        ADMIN_AUDIENCE_GRANT_UPDATED = "admin.audience_grant_updated", "Admin audience grant updated"
        ADMIN_AUDIENCE_GRANT_DELETED = "admin.audience_grant_deleted", "Admin audience grant deleted"
        SUBMISSION_CREATED = "submission.created", "Submission created"
        SUBMISSION_REJECTED = "submission.rejected", "Submission rejected"
        LAB_SUBMISSION_CREATED = "lab.submission_created", "Lab submission created"
        LAB_SUBMISSION_REJECTED = "lab.submission_rejected", "Lab submission rejected"
        LAB_SUBMISSION_DENIED = "lab.submission_denied", "Lab submission denied"
        LAB_SUBMISSION_NOT_FOUND = "lab.submission_not_found", "Lab submission content not found"
        LAB_HINT_VIEWED = "lab.hint_viewed", "Lab hint viewed"
        LAB_LAUNCH_ISSUED = "lab.launch_issued", "Lab launch issued"
        LAB_LAUNCH_REJECTED = "lab.launch_rejected", "Lab launch rejected"
        LAB_GATEWAY_REJECTED = "lab.gateway_rejected", "Lab gateway rejected"
        JUPYTER_LOGIN_EXCHANGED = "jupyter.login_exchanged", "Jupyter login exchanged"
        JUPYTER_LOGIN_REJECTED = "jupyter.login_rejected", "Jupyter login rejected"
        LAB_LAUNCH_REQUESTED = "lab.launch_requested", "Lab launch requested"
        LAB_LAUNCH_FAILED = "lab.launch_failed", "Lab launch failed"
        LAB_LAUNCH_DENIED = "lab.launch_denied", "Lab launch denied"
        LAB_LAUNCH_NOT_FOUND = "lab.launch_not_found", "Lab launch content not found"
        LAB_GATEWAY_REDIRECTED = "lab.gateway_redirected", "Lab gateway redirected"
        LAB_GATEWAY_LAUNCH_INVALID = "lab.gateway_launch_invalid", "Lab gateway launch invalid"
        LAB_GATEWAY_LOGIN_ISSUE_FAILED = "lab.gateway_login_issue_failed", "Lab gateway login issue failed"
        LAB_LAUNCH_RESOLVED = "lab.launch_resolved", "Lab launch resolved"
        LAB_LAUNCH_RESOLVE_FAILED = "lab.launch_resolve_failed", "Lab launch resolve failed"
        LAB_LOGIN_ISSUED = "lab.login_issued", "Lab login issued"
        LAB_LOGIN_ISSUE_FAILED = "lab.login_issue_failed", "Lab login issue failed"
        LAB_LOGIN_ISSUE_NOT_FOUND = "lab.login_issue_not_found", "Lab login issue launch token not found"
        LAB_LOGIN_EXCHANGED = "lab.login_exchanged", "Lab login exchanged"
        LAB_LOGIN_EXCHANGE_FAILED = "lab.login_exchange_failed", "Lab login exchange failed"
        GRADING_WEBHOOK_APPLIED = "grading.webhook_applied", "Grading webhook applied"
        GRADING_WEBHOOK_FAILED = "grading.webhook_failed", "Grading webhook failed"
        GRADING_RESULT_APPLIED = "grading.result_applied", "Grading result applied"
        GRADING_JOB_FAILED = "grading.job_failed", "Grading job failed"
        AI_CONVERSATION_VIEWED = "ai.conversation_viewed", "AI conversation viewed"
        AI_QUESTION_ASKED = "ai.question_asked", "AI question asked"
        AI_RESPONSE_GENERATED = "ai.response_generated", "AI response generated"
        AI_RESPONSE_FAILED = "ai.response_failed", "AI response failed"
        AI_QUIZ_GENERATED = "ai.quiz_generated", "AI quiz generated"
        AI_QUIZ_SUBMITTED = "ai.quiz_submitted", "AI quiz submitted"
        AI_QUIZ_SUBMIT_FAILED = "ai.quiz_submit_failed", "AI quiz submit failed"
        AI_ESCALATION_SUGGESTED = "ai.escalation_suggested", "AI escalation suggested"
        ADMIN_AI_OVERVIEW_VIEWED = "admin.ai_overview_viewed", "Admin AI overview viewed"
        ADMIN_AI_QUEUE_VIEWED = "admin.ai_queue_viewed", "Admin AI queue viewed"
        ADMIN_AI_CONVERSATION_UPDATED = "admin.ai_conversation_updated", "Admin AI conversation updated"
        ADMIN_AI_INDEX_REBUILT = "admin.ai_index_rebuilt", "Admin AI index rebuilt"
        ADMIN_AI_OPERATIONS_VIEWED = "admin.ai_operations_viewed", "Admin AI operations viewed"
        DIRECTUS_SYNC_APPLIED = "directus.sync_applied", "Directus sync applied"
        DIRECTUS_SYNC_FAILED = "directus.sync_failed", "Directus sync failed"
        ADMIN_AI_ANALYTICS_VIEWED = "admin.ai_analytics_viewed", "Admin AI analytics viewed"

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    category = models.CharField(max_length=20, choices=Category.choices)
    event_type = models.CharField(max_length=80, choices=EventType.choices)
    outcome = models.CharField(max_length=20, choices=Outcome.choices, default=Outcome.SUCCEEDED)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="training_audit_events",
        blank=True,
        null=True,
    )
    actor_email = models.EmailField(blank=True, default="")
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="targeted_training_audit_events",
        blank=True,
        null=True,
    )
    target_user_email = models.EmailField(blank=True, default="")
    course = models.ForeignKey(
        OnlineCourse,
        on_delete=models.SET_NULL,
        related_name="training_audit_events",
        blank=True,
        null=True,
    )
    content_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        blank=True,
        null=True,
    )
    submission = models.ForeignKey(
        TrainingLabSubmission,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        blank=True,
        null=True,
    )
    launch_token = models.ForeignKey(
        TrainingLabLaunchToken,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        blank=True,
        null=True,
    )
    jupyter_login_token = models.ForeignKey(
        TrainingJupyterLoginToken,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        blank=True,
        null=True,
    )
    request_id = models.CharField(max_length=80, blank=True, default="")
    request_method = models.CharField(max_length=10, blank=True, default="")
    request_path = models.CharField(max_length=255, blank=True, default="")
    request_ip = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=400, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "training_audit_event"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("category", "created_at")),
            models.Index(fields=("event_type",)),
            models.Index(fields=("outcome",)),
            models.Index(fields=("actor",)),
            models.Index(fields=("target_user",)),
            models.Index(fields=("course",)),
            models.Index(fields=("content_item",)),
            models.Index(fields=("submission",)),
            models.Index(fields=("request_id",)),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} ({self.outcome})"


class TrainingKnowledgeChunk(models.Model):
    content_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.CASCADE,
        related_name="knowledge_chunks",
    )
    chunk_index = models.PositiveIntegerField(default=0)
    section_title = models.CharField(max_length=220, blank=True, default="")
    citation_label = models.CharField(max_length=220, blank=True, default="")
    chunk_text = models.TextField()
    snippet = models.CharField(max_length=240, blank=True, default="")
    source_checksum = models.CharField(max_length=64)
    chunk_checksum = models.CharField(max_length=64)
    token_count = models.PositiveIntegerField(default=0)
    embedding_vector = models.JSONField(default=list, blank=True)
    embedding_model = models.CharField(max_length=120, blank=True, default="")
    embedding_dimensions = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_knowledge_chunk"
        ordering = ("content_item_id", "chunk_index", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("content_item", "chunk_index", "source_checksum"),
                name="training_knowledge_chunk_unique_snapshot_position",
            )
        ]
        indexes = [
            models.Index(fields=("content_item", "is_active")),
            models.Index(fields=("source_checksum",)),
        ]

    def __str__(self) -> str:
        return f"{self.content_item.slug}#{self.chunk_index}"


class TrainingAiConversation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    class GovernanceStatus(models.TextChoices):
        OPEN = "open", "Open"
        IN_REVIEW = "in_review", "In review"
        RESOLVED = "resolved", "Resolved"
        ARCHIVED = "archived", "Archived"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="training_ai_conversations",
    )
    content_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.SET_NULL,
        related_name="ai_conversations",
        blank=True,
        null=True,
    )
    title = models.CharField(max_length=180, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    governance_status = models.CharField(
        max_length=20,
        choices=GovernanceStatus.choices,
        default=GovernanceStatus.OPEN,
    )
    last_user_prompt = models.CharField(max_length=255, blank=True, default="")
    resolution_note = models.CharField(max_length=255, blank=True, default="")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_training_ai_conversations",
        blank=True,
        null=True,
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="resolved_training_ai_conversations",
        blank=True,
        null=True,
    )
    resolved_at = models.DateTimeField(blank=True, null=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_ai_conversation"
        ordering = ("-last_activity_at", "-id")
        indexes = [
            models.Index(fields=("user", "status")),
            models.Index(fields=("content_item", "status")),
            models.Index(fields=("governance_status", "last_activity_at")),
        ]

    def __str__(self) -> str:
        content_slug = self.content_item.slug if self.content_item_id else "detached"
        return f"{self.public_id} ({content_slug})"


class TrainingAiMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    class PromptType(models.TextChoices):
        ASK = "ask", "Ask"
        KEY_TAKEAWAYS = "key_takeaways", "Key takeaways"
        RISKS = "risks", "Risks"
        SIMPLE_SUMMARY = "simple_summary", "Simple summary"
        ANSWER_REVIEW = "answer_review", "Answer review"
        EXPLAIN_FOR_JUNIOR = "explain_for_junior", "Explain for junior"
        QUIZ_GENERATION = "quiz_generation", "Quiz generation"

    class ResolutionStatus(models.TextChoices):
        RESOLVED = "resolved", "Resolved"
        PARTIAL = "partial", "Partial"
        ESCALATE = "escalate", "Escalate"

    conversation = models.ForeignKey(
        TrainingAiConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    content_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.SET_NULL,
        related_name="ai_messages",
        blank=True,
        null=True,
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    prompt_type = models.CharField(max_length=30, choices=PromptType.choices, blank=True, default=PromptType.ASK)
    body = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    citations = models.JSONField(default=list, blank=True)
    provider = models.CharField(max_length=40, blank=True, default="")
    model_name = models.CharField(max_length=120, blank=True, default="")
    resolution_status = models.CharField(
        max_length=20,
        choices=ResolutionStatus.choices,
        default=ResolutionStatus.RESOLVED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "training_ai_message"
        ordering = ("conversation_id", "created_at", "id")
        indexes = [
            models.Index(fields=("conversation", "role")),
            models.Index(fields=("content_item",)),
            models.Index(fields=("prompt_type",)),
        ]

    def __str__(self) -> str:
        return f"{self.conversation_id}:{self.role}"


class TrainingAiQuizAttempt(models.Model):
    class Status(models.TextChoices):
        GENERATED = "generated", "Generated"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="training_ai_quiz_attempts",
    )
    content_item = models.ForeignKey(
        TrainingContentItem,
        on_delete=models.CASCADE,
        related_name="ai_quiz_attempts",
    )
    conversation = models.ForeignKey(
        TrainingAiConversation,
        on_delete=models.SET_NULL,
        related_name="quiz_attempts",
        blank=True,
        null=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.GENERATED)
    title = models.CharField(max_length=180, blank=True, default="")
    quiz_payload = models.JSONField(default=dict, blank=True)
    submitted_answers = models.JSONField(default=list, blank=True)
    score = models.PositiveSmallIntegerField(blank=True, null=True)
    max_score = models.PositiveSmallIntegerField(blank=True, null=True)
    correct_answers_count = models.PositiveSmallIntegerField(default=0)
    submitted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_ai_quiz_attempt"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("user", "status")),
            models.Index(fields=("content_item", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.public_id} ({self.content_item.slug})"
