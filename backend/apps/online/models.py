from decimal import Decimal
import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q

from apps.employees.models import Lehrer


class OnlineCourse(models.Model):
    LOCALE_DE = "de"
    LOCALE_EN = "en"
    LOCALE_CHOICES = (
        (LOCALE_DE, "German"),
        (LOCALE_EN, "English"),
    )
    LIFECYCLE_DRAFT = "draft"
    LIFECYCLE_IN_REVIEW = "in_review"
    LIFECYCLE_APPROVED = "approved"
    LIFECYCLE_PUBLISHED = "published"
    LIFECYCLE_ARCHIVED = "archived"
    LIFECYCLE_CHOICES = (
        (LIFECYCLE_DRAFT, "Draft"),
        (LIFECYCLE_IN_REVIEW, "In review"),
        (LIFECYCLE_APPROVED, "Approved"),
        (LIFECYCLE_PUBLISHED, "Published"),
        (LIFECYCLE_ARCHIVED, "Archived"),
    )
    PROVIDER_INTERNAL = "internal"
    PROVIDER_LINKEDIN = "linkedin_learning"
    PROVIDER_COURSERA = "coursera"
    PROVIDER_UDEMY = "udemy_business"
    PROVIDER_EXTERNAL = "external_custom"
    PROVIDER_CHOICES = (
        (PROVIDER_INTERNAL, "Internal"),
        (PROVIDER_LINKEDIN, "LinkedIn Learning"),
        (PROVIDER_COURSERA, "Coursera"),
        (PROVIDER_UDEMY, "Udemy Business"),
        (PROVIDER_EXTERNAL, "External custom"),
    )
    ORIGIN_INTERNAL_AUTHORED = "internal_authored"
    ORIGIN_EXTERNAL_SYNCED = "external_synced"
    ORIGIN_EXTERNAL_MANUAL = "external_manual"
    ORIGIN_CHOICES = (
        (ORIGIN_INTERNAL_AUTHORED, "Internal authored"),
        (ORIGIN_EXTERNAL_SYNCED, "External synced"),
        (ORIGIN_EXTERNAL_MANUAL, "External manual"),
    )
    COURSE_TYPE_TEXT = "text"
    COURSE_TYPE_VIDEO = "video"
    COURSE_TYPE_AUDIO = "audio"
    COURSE_TYPE_INTERACTIVE = "interactive"
    COURSE_TYPE_RECORDING = "recording"
    COURSE_TYPE_LIVE = "live"
    COURSE_TYPE_BLENDED = "blended"
    COURSE_TYPE_EXTERNAL = "external"
    COURSE_TYPE_CHOICES = (
        (COURSE_TYPE_TEXT, "Text"),
        (COURSE_TYPE_VIDEO, "Video"),
        (COURSE_TYPE_AUDIO, "Audio"),
        (COURSE_TYPE_INTERACTIVE, "Interactive"),
        (COURSE_TYPE_RECORDING, "Recording"),
        (COURSE_TYPE_LIVE, "Live"),
        (COURSE_TYPE_BLENDED, "Blended"),
        (COURSE_TYPE_EXTERNAL, "External"),
    )
    DELIVERY_SELF_PACED = "self_paced"
    DELIVERY_COHORT = "cohort"
    DELIVERY_INSTRUCTOR_LED = "instructor_led"
    DELIVERY_HYBRID = "hybrid"
    DELIVERY_CHOICES = (
        (DELIVERY_SELF_PACED, "Self-paced"),
        (DELIVERY_COHORT, "Cohort"),
        (DELIVERY_INSTRUCTOR_LED, "Instructor-led"),
        (DELIVERY_HYBRID, "Hybrid"),
    )
    DIFFICULTY_FOUNDATION = "foundation"
    DIFFICULTY_BEGINNER = "beginner"
    DIFFICULTY_INTERMEDIATE = "intermediate"
    DIFFICULTY_ADVANCED = "advanced"
    DIFFICULTY_EXPERT = "expert"
    DIFFICULTY_CHOICES = (
        (DIFFICULTY_FOUNDATION, "Foundation"),
        (DIFFICULTY_BEGINNER, "Beginner"),
        (DIFFICULTY_INTERMEDIATE, "Intermediate"),
        (DIFFICULTY_ADVANCED, "Advanced"),
        (DIFFICULTY_EXPERT, "Expert"),
    )
    CONFIDENTIALITY_PUBLIC = "public"
    CONFIDENTIALITY_INTERNAL = "internal"
    CONFIDENTIALITY_RESTRICTED = "restricted"
    CONFIDENTIALITY_CONFIDENTIAL = "confidential"
    CONFIDENTIALITY_HIGHLY_CONFIDENTIAL = "highly_confidential"
    CONFIDENTIALITY_CHOICES = (
        (CONFIDENTIALITY_PUBLIC, "Public"),
        (CONFIDENTIALITY_INTERNAL, "Internal"),
        (CONFIDENTIALITY_RESTRICTED, "Restricted"),
        (CONFIDENTIALITY_CONFIDENTIAL, "Confidential"),
        (CONFIDENTIALITY_HIGHLY_CONFIDENTIAL, "Highly confidential"),
    )

    slug = models.SlugField(max_length=120, unique=True)
    title_de = models.CharField(max_length=220)
    title_en = models.CharField(max_length=220)
    short_description_de = models.TextField(max_length=1000)
    short_description_en = models.TextField(max_length=1000)
    description_de = models.TextField()
    description_en = models.TextField()
    lessons_count = models.PositiveSmallIntegerField(default=12)
    trial_available = models.BooleanField(default=False)
    price_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, default="EUR")
    is_subscription = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    lifecycle_status = models.CharField(max_length=20, choices=LIFECYCLE_CHOICES, default=LIFECYCLE_PUBLISHED)
    provider_type = models.CharField(max_length=40, choices=PROVIDER_CHOICES, default=PROVIDER_INTERNAL)
    course_origin = models.CharField(max_length=40, choices=ORIGIN_CHOICES, default=ORIGIN_INTERNAL_AUTHORED)
    course_type = models.CharField(max_length=24, choices=COURSE_TYPE_CHOICES, default=COURSE_TYPE_INTERACTIVE)
    delivery_model = models.CharField(max_length=24, choices=DELIVERY_CHOICES, default=DELIVERY_COHORT)
    difficulty_level = models.CharField(max_length=24, choices=DIFFICULTY_CHOICES, default=DIFFICULTY_BEGINNER)
    confidentiality_level = models.CharField(
        max_length=24,
        choices=CONFIDENTIALITY_CHOICES,
        default=CONFIDENTIALITY_INTERNAL,
    )
    knowledge_domain = models.CharField(max_length=120, blank=True, default="")
    target_audience = models.CharField(max_length=220, blank=True, default="")
    estimated_duration_minutes = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.00"))
    ratings_count = models.PositiveIntegerField(default=0)
    is_mandatory = models.BooleanField(default=False)
    is_recommended = models.BooleanField(default=True)
    provider_course_id = models.CharField(max_length=180, blank=True, default="")
    external_url = models.URLField(blank=True, default="")
    tags = models.JSONField(blank=True, default=list)
    skills = models.JSONField(blank=True, default=list)
    metadata_json = models.JSONField(blank=True, default=dict)
    custom_fields = models.JSONField(blank=True, default=dict)
    required_completion_percent = models.PositiveSmallIntegerField(default=100)
    required_attendance_percent = models.PositiveSmallIntegerField(default=0)
    requires_attestation = models.BooleanField(default=True)
    hero_image_url = models.URLField(blank=True, null=True)
    seo_title_de = models.CharField(max_length=180, blank=True, default="")
    seo_title_en = models.CharField(max_length=180, blank=True, default="")
    seo_description_de = models.CharField(max_length=300, blank=True, default="")
    seo_description_en = models.CharField(max_length=300, blank=True, default="")
    geo_city = models.CharField(max_length=100, default="Berlin")
    geo_country = models.CharField(max_length=2, default="DE")
    starts_at = models.DateTimeField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    lifecycle_status_changed_at = models.DateTimeField(blank=True, null=True)
    submitted_for_review_at = models.DateTimeField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    published_at = models.DateTimeField(blank=True, null=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_course"
        ordering = ("id",)
        indexes = [
            models.Index(fields=("is_published",)),
            models.Index(fields=("lifecycle_status",)),
            models.Index(fields=("slug",)),
            models.Index(fields=("provider_type", "course_origin")),
            models.Index(fields=("course_type", "delivery_model")),
            models.Index(fields=("confidentiality_level",)),
            models.Index(fields=("knowledge_domain",)),
        ]

    def __str__(self) -> str:
        return self.title_de

    def localized_title(self, locale: str = LOCALE_DE) -> str:
        if locale == self.LOCALE_EN:
            return self.title_en
        return self.title_de

    def localized_short_description(self, locale: str = LOCALE_DE) -> str:
        if locale == self.LOCALE_EN:
            return self.short_description_en
        return self.short_description_de

    def localized_description(self, locale: str = LOCALE_DE) -> str:
        if locale == self.LOCALE_EN:
            return self.description_en
        return self.description_de


class OnlineCourseApproval(models.Model):
    ACTION_SUBMITTED = "submitted"
    ACTION_APPROVED = "approved"
    ACTION_RETURNED_TO_DRAFT = "returned_to_draft"
    ACTION_PUBLISHED = "published"
    ACTION_ARCHIVED = "archived"
    ACTION_CHOICES = (
        (ACTION_SUBMITTED, "Submitted for review"),
        (ACTION_APPROVED, "Approved"),
        (ACTION_RETURNED_TO_DRAFT, "Returned to draft"),
        (ACTION_PUBLISHED, "Published"),
        (ACTION_ARCHIVED, "Archived"),
    )

    course = models.ForeignKey(OnlineCourse, on_delete=models.CASCADE, related_name="approval_events")
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    from_status = models.CharField(max_length=20, choices=OnlineCourse.LIFECYCLE_CHOICES, blank=True, default="")
    to_status = models.CharField(max_length=20, choices=OnlineCourse.LIFECYCLE_CHOICES)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="online_course_approval_events",
    )
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "online_course_approval"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("course", "created_at")),
            models.Index(fields=("to_status",)),
        ]

    def __str__(self) -> str:
        return f"{self.course.slug}: {self.action}"


class OnlineCourseVersion(models.Model):
    course = models.ForeignKey(OnlineCourse, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    lifecycle_status = models.CharField(max_length=20, choices=OnlineCourse.LIFECYCLE_CHOICES)
    source = models.CharField(max_length=80, blank=True, default="")
    change_summary = models.CharField(max_length=255, blank=True, default="")
    snapshot = models.JSONField(blank=True, default=dict)
    structure_summary = models.JSONField(blank=True, default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="online_course_versions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "online_course_version"
        ordering = ("-version_number", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("course", "version_number"),
                name="online_course_version_unique_course_version_number",
            )
        ]
        indexes = [
            models.Index(fields=("course", "version_number")),
            models.Index(fields=("lifecycle_status", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.course.slug} v{self.version_number}"


class OnlineAuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="online_audit_events",
    )
    actor_email = models.CharField(max_length=255, blank=True, default="")
    course = models.ForeignKey(
        OnlineCourse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="online_audit_events",
        limit_choices_to=Q(app_label="online"),
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    event_type = models.CharField(max_length=120)
    summary = models.CharField(max_length=220, blank=True, default="")
    request_method = models.CharField(max_length=12, blank=True, default="")
    request_path = models.CharField(max_length=255, blank=True, default="")
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    metadata = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "online_audit_event"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("event_type", "created_at")),
            models.Index(fields=("course", "created_at")),
            models.Index(fields=("content_type", "object_id")),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M:%S}"


class OnlineIdentityProvider(models.Model):
    PROVIDER_LOCAL_PASSWORD = "local_password"
    PROVIDER_GOOGLE_OIDC = "google_oidc"
    PROVIDER_MICROSOFT_OIDC = "microsoft_oidc"
    PROVIDER_CHOICES = (
        (PROVIDER_LOCAL_PASSWORD, "Local password"),
        (PROVIDER_GOOGLE_OIDC, "Google OIDC"),
        (PROVIDER_MICROSOFT_OIDC, "Microsoft OIDC"),
    )

    STATUS_DRAFT = "draft"
    STATUS_READY = "ready"
    STATUS_ERROR = "error"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_READY, "Ready"),
        (STATUS_ERROR, "Error"),
    )

    slug = models.SlugField(max_length=120, unique=True)
    display_name = models.CharField(max_length=180)
    provider_type = models.CharField(max_length=40, choices=PROVIDER_CHOICES)
    sort_order = models.PositiveSmallIntegerField(default=0)
    issuer = models.URLField(blank=True, default="")
    discovery_url = models.URLField(blank=True, default="")
    authorization_url = models.URLField(blank=True, default="")
    token_url = models.URLField(blank=True, default="")
    jwks_url = models.URLField(blank=True, default="")
    redirect_uri = models.URLField(blank=True, default="")
    tenant_id = models.CharField(max_length=180, blank=True, default="")
    client_id = models.CharField(max_length=255, blank=True, default="")
    scopes = models.JSONField(blank=True, default=list)
    claim_map = models.JSONField(blank=True, default=dict)
    is_enabled = models.BooleanField(default=False)
    is_sso = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    verification_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    verification_message = models.CharField(max_length=255, blank=True, default="")
    last_verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_identity_provider"
        ordering = ("sort_order", "id")
        indexes = [
            models.Index(fields=("provider_type",)),
            models.Index(fields=("is_enabled", "verification_status")),
            models.Index(fields=("is_default",)),
        ]

    def __str__(self) -> str:
        return self.display_name


class OnlineIdentityLink(models.Model):
    provider = models.ForeignKey(
        OnlineIdentityProvider,
        on_delete=models.CASCADE,
        related_name="identity_links",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="online_identity_links",
    )
    subject = models.CharField(max_length=255)
    email = models.EmailField(blank=True, default="")
    full_name = models.CharField(max_length=180, blank=True, default="")
    claims_snapshot = models.JSONField(blank=True, default=dict)
    last_authenticated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_identity_link"
        ordering = ("provider__sort_order", "provider_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "subject"),
                name="online_identity_link_unique_provider_subject",
            )
        ]
        indexes = [
            models.Index(fields=("provider", "user")),
            models.Index(fields=("last_authenticated_at",)),
        ]

    def __str__(self) -> str:
        return f"{self.provider.slug}:{self.subject}"


class OnlineCourseFaq(models.Model):
    course = models.ForeignKey(OnlineCourse, on_delete=models.CASCADE, related_name="faqs")
    question_de = models.CharField(max_length=300)
    question_en = models.CharField(max_length=300)
    answer_de = models.TextField()
    answer_en = models.TextField()
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "online_course_faq"
        ordering = ("sort_order", "id")

    def __str__(self) -> str:
        return f"FAQ #{self.id} ({self.course.slug})"


class OnlineCourseMaterial(models.Model):
    MATERIAL_RESOURCE = "resource"
    MATERIAL_RECORDING = "recording"
    MATERIAL_CONDITION = "condition"
    MATERIAL_CHOICES = (
        (MATERIAL_RESOURCE, "Resource"),
        (MATERIAL_RECORDING, "Recording"),
        (MATERIAL_CONDITION, "Condition"),
    )

    course = models.ForeignKey(OnlineCourse, on_delete=models.CASCADE, related_name="materials")
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    material_type = models.CharField(max_length=20, choices=MATERIAL_CHOICES, default=MATERIAL_RESOURCE)
    language = models.CharField(max_length=2, choices=OnlineCourse.LOCALE_CHOICES, default=OnlineCourse.LOCALE_DE)
    link_url = models.URLField(blank=True, null=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "online_course_material"
        ordering = ("sort_order", "id")

    def __str__(self) -> str:
        return f"{self.course.slug}: {self.title}"


class OnlineCourseTemplate(models.Model):
    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True, default="")
    default_lessons_count = models.PositiveSmallIntegerField(default=1)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_course_template"
        ordering = ("sort_order", "id")
        indexes = [
            models.Index(fields=("is_active",)),
            models.Index(fields=("slug",)),
        ]

    def __str__(self) -> str:
        return self.title


class OnlineCourseTemplateLesson(models.Model):
    template = models.ForeignKey(
        OnlineCourseTemplate,
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    introduction_title = models.CharField(max_length=180, default="Introduction")
    introduction_description = models.TextField(blank=True, default="")
    main_title = models.CharField(max_length=180, default="Main content")
    main_description = models.TextField(blank=True, default="")
    conclusion_title = models.CharField(max_length=180, default="Conclusion")
    conclusion_description = models.TextField(blank=True, default="")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "online_course_template_lesson"
        ordering = ("sort_order", "id")

    def __str__(self) -> str:
        return f"{self.template.slug}: {self.title}"


class OnlineCourseContentLibraryItem(models.Model):
    SECTION_INTRODUCTION = "introduction"
    SECTION_MAIN = "main"
    SECTION_CONCLUSION = "conclusion"
    SECTION_CHOICES = (
        (SECTION_INTRODUCTION, "Introduction"),
        (SECTION_MAIN, "Main content"),
        (SECTION_CONCLUSION, "Conclusion"),
    )

    ASSET_TEXT = "text"
    ASSET_DOCUMENT = "document"
    ASSET_LINK = "link"
    ASSET_NOTEBOOK = "notebook"
    ASSET_CHOICES = (
        (ASSET_TEXT, "Text"),
        (ASSET_DOCUMENT, "Document"),
        (ASSET_LINK, "External link"),
        (ASSET_NOTEBOOK, "Notebook"),
    )

    section_type = models.CharField(max_length=20, choices=SECTION_CHOICES)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    library_group = models.CharField(max_length=120, blank=True, default="")
    asset_type = models.CharField(max_length=20, choices=ASSET_CHOICES, default=ASSET_DOCUMENT)
    language = models.CharField(max_length=2, choices=OnlineCourse.LOCALE_CHOICES, default=OnlineCourse.LOCALE_EN)
    body_markdown = models.TextField(blank=True, default="")
    external_url = models.URLField(blank=True, default="")
    file_asset = models.FileField(upload_to="online/course_library/", blank=True, null=True)
    training_content = models.ForeignKey(
        "training.TrainingContentItem",
        on_delete=models.SET_NULL,
        related_name="online_course_library_items",
        blank=True,
        null=True,
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_course_content_library_item"
        ordering = ("section_type", "sort_order", "id")
        indexes = [
            models.Index(fields=("section_type", "is_active")),
            models.Index(fields=("asset_type", "is_active")),
            models.Index(fields=("library_group",)),
        ]

    def __str__(self) -> str:
        return self.title


class OnlineCourseLesson(models.Model):
    module = models.ForeignKey(
        "OnlineCourseModule",
        on_delete=models.CASCADE,
        related_name="lessons",
        blank=True,
        null=True,
    )
    course = models.ForeignKey(OnlineCourse, on_delete=models.CASCADE, related_name="structured_lessons")
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    starts_at = models.DateTimeField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_course_lesson"
        ordering = ("sort_order", "id")
        indexes = [
            models.Index(fields=("course", "is_active")),
        ]

    def __str__(self) -> str:
        return f"{self.course.slug}: {self.title}"


class OnlineCourseLessonSection(models.Model):
    SECTION_INTRODUCTION = OnlineCourseContentLibraryItem.SECTION_INTRODUCTION
    SECTION_MAIN = OnlineCourseContentLibraryItem.SECTION_MAIN
    SECTION_CONCLUSION = OnlineCourseContentLibraryItem.SECTION_CONCLUSION
    SECTION_CHOICES = OnlineCourseContentLibraryItem.SECTION_CHOICES

    lesson = models.ForeignKey(OnlineCourseLesson, on_delete=models.CASCADE, related_name="sections")
    section_type = models.CharField(max_length=20, choices=SECTION_CHOICES)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True, default="")
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_course_lesson_section"
        ordering = ("sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("lesson", "section_type"),
                name="online_course_lesson_section_unique",
            )
        ]
        indexes = [
            models.Index(fields=("lesson", "section_type", "is_active")),
        ]

    def __str__(self) -> str:
        return f"{self.lesson_id}:{self.section_type}"


class OnlineCourseLessonSectionItem(models.Model):
    ACTIVITY_VIDEO = "video"
    ACTIVITY_TEXT = "text"
    ACTIVITY_QUIZ = "quiz"
    ACTIVITY_ASSIGNMENT = "assignment"
    ACTIVITY_CHOICES = (
        (ACTIVITY_VIDEO, "Video"),
        (ACTIVITY_TEXT, "Text"),
        (ACTIVITY_QUIZ, "Quiz"),
        (ACTIVITY_ASSIGNMENT, "Assignment"),
    )

    ASSET_TEXT = OnlineCourseContentLibraryItem.ASSET_TEXT
    ASSET_DOCUMENT = OnlineCourseContentLibraryItem.ASSET_DOCUMENT
    ASSET_LINK = OnlineCourseContentLibraryItem.ASSET_LINK
    ASSET_NOTEBOOK = OnlineCourseContentLibraryItem.ASSET_NOTEBOOK
    ASSET_CHOICES = OnlineCourseContentLibraryItem.ASSET_CHOICES

    section = models.ForeignKey(OnlineCourseLessonSection, on_delete=models.CASCADE, related_name="items")
    source_library_item = models.ForeignKey(
        OnlineCourseContentLibraryItem,
        on_delete=models.SET_NULL,
        related_name="course_section_items",
        blank=True,
        null=True,
    )
    linked_training_content = models.ForeignKey(
        "training.TrainingContentItem",
        on_delete=models.SET_NULL,
        related_name="online_course_section_items",
        blank=True,
        null=True,
    )
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    asset_type = models.CharField(max_length=20, choices=ASSET_CHOICES, default=ASSET_DOCUMENT)
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_CHOICES, default=ACTIVITY_TEXT)
    language = models.CharField(max_length=2, choices=OnlineCourse.LOCALE_CHOICES, default=OnlineCourse.LOCALE_EN)
    body_markdown = models.TextField(blank=True, default="")
    structured_data = models.JSONField(blank=True, default=dict)
    external_url = models.URLField(blank=True, default="")
    file_asset = models.FileField(upload_to="online/course_sections/", blank=True, null=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_course_lesson_section_item"
        ordering = ("sort_order", "id")
        indexes = [
            models.Index(fields=("section", "is_active")),
            models.Index(fields=("asset_type", "is_active")),
        ]

    def __str__(self) -> str:
        return self.title


class OnlineCourseModule(models.Model):
    MODULE_TYPE_STANDARD = "module"
    MODULE_TYPE_FINAL = "final_assessment"
    MODULE_TYPE_CHOICES = (
        (MODULE_TYPE_STANDARD, "Module"),
        (MODULE_TYPE_FINAL, "Final assessment"),
    )

    course = models.ForeignKey(OnlineCourse, on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    module_type = models.CharField(max_length=24, choices=MODULE_TYPE_CHOICES, default=MODULE_TYPE_STANDARD)
    week_number = models.PositiveSmallIntegerField(blank=True, null=True)
    starts_at = models.DateTimeField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_course_module"
        ordering = ("sort_order", "id")
        indexes = [
            models.Index(fields=("course", "is_active")),
            models.Index(fields=("course", "module_type", "is_active")),
        ]

    def __str__(self) -> str:
        return f"{self.course.slug}: {self.title}"


class OnlineAccessPolicy(models.Model):
    audience = models.ForeignKey(
        "training.TrainingAudience",
        on_delete=models.CASCADE,
        related_name="online_access_policies",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="online_access_policies",
        limit_choices_to=Q(app_label="online"),
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_access_policy"
        ordering = ("content_type_id", "object_id", "audience__privilege_rank", "audience__name", "audience_id")
        constraints = [
            models.UniqueConstraint(
                fields=("content_type", "object_id", "audience"),
                name="online_access_policy_unique_object_audience",
            )
        ]
        indexes = [
            models.Index(fields=("content_type", "object_id")),
            models.Index(fields=("audience",)),
        ]

    def __str__(self) -> str:
        return f"{self.content_type.app_label}.{self.content_type.model}:{self.object_id} -> {self.audience.slug}"


class OnlineWorkspace(models.Model):
    KIND_GROUP = "group"
    KIND_SHARED = "shared"
    KIND_CHOICES = (
        (KIND_GROUP, "Group"),
        (KIND_SHARED, "Shared library"),
    )

    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=180)
    subtitle = models.CharField(max_length=180, blank=True, default="")
    summary = models.TextField(blank=True, default="")
    icon_key = models.CharField(max_length=40, default="berlin")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_GROUP)
    sort_order = models.PositiveSmallIntegerField(default=0)
    show_on_homepage = models.BooleanField(default=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_workspace"
        ordering = ("sort_order", "id")
        indexes = [
            models.Index(fields=("kind", "is_published", "show_on_homepage")),
            models.Index(fields=("slug",)),
        ]

    def __str__(self) -> str:
        return self.title


class OnlineWorkspaceContentItem(models.Model):
    SECTION_COURSES = "courses"
    SECTION_ASSIGNMENTS = "assignments"
    SECTION_RECORDINGS = "recordings"
    SECTION_MATERIALS = "materials"
    SECTION_CHOICES = (
        (SECTION_COURSES, "Courses"),
        (SECTION_ASSIGNMENTS, "Assignments"),
        (SECTION_RECORDINGS, "Recordings"),
        (SECTION_MATERIALS, "Materials"),
    )

    workspace = models.ForeignKey(OnlineWorkspace, on_delete=models.CASCADE, related_name="content_items")
    section = models.CharField(max_length=20, choices=SECTION_CHOICES)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    preview_image_url = models.URLField(blank=True, default="")
    asset_url = models.URLField(blank=True, default="")
    linked_course = models.ForeignKey(
        "OnlineCourse",
        on_delete=models.SET_NULL,
        related_name="workspace_content_items",
        blank=True,
        null=True,
    )
    linked_cohort = models.ForeignKey(
        "OnlineCohort",
        on_delete=models.SET_NULL,
        related_name="workspace_content_items",
        blank=True,
        null=True,
    )
    primary_meta = models.CharField(max_length=160, blank=True, default="")
    secondary_meta = models.CharField(max_length=160, blank=True, default="")
    published_on = models.DateField(blank=True, null=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_workspace_content_item"
        ordering = ("section", "sort_order", "id")
        indexes = [
            models.Index(fields=("workspace", "section", "is_active")),
            models.Index(fields=("published_on",)),
            models.Index(fields=("linked_course",)),
            models.Index(fields=("linked_cohort",)),
        ]

    def __str__(self) -> str:
        return f"{self.workspace.slug}: {self.section} / {self.title}"


class OnlineCohort(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_OPEN = "open"
    STATUS_RUNNING = "running"
    STATUS_FINISHED = "finished"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_OPEN, "Open"),
        (STATUS_RUNNING, "Running"),
        (STATUS_FINISHED, "Finished"),
    )

    course = models.ForeignKey(OnlineCourse, on_delete=models.CASCADE, related_name="cohorts")
    teacher = models.ForeignKey(
        Lehrer,
        on_delete=models.SET_NULL,
        related_name="online_cohorts",
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=220)
    group_code = models.CharField(max_length=80, unique=True)
    capacity = models.PositiveSmallIntegerField(default=20)
    timezone = models.CharField(max_length=64, default="Europe/Berlin")
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_cohort"
        ordering = ("start_date", "id")
        indexes = [
            models.Index(fields=("status",)),
            models.Index(fields=("group_code",)),
        ]

    def __str__(self) -> str:
        return f"{self.group_code} - {self.name}"


class OnlineSession(models.Model):
    STATUS_SCHEDULED = "scheduled"
    STATUS_LIVE = "live"
    STATUS_ENDED = "ended"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = (
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_LIVE, "Live"),
        (STATUS_ENDED, "Ended"),
        (STATUS_CANCELED, "Canceled"),
    )

    cohort = models.ForeignKey(OnlineCohort, on_delete=models.CASCADE, related_name="sessions")
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    join_url = models.URLField(max_length=1000, blank=True, null=True)
    provider_meeting_id = models.CharField(max_length=220, blank=True, default="")
    recording_url = models.URLField(max_length=1000, blank=True, null=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    attendance_synced_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_session"
        ordering = ("sort_order", "starts_at", "id")
        indexes = [
            models.Index(fields=("starts_at",)),
            models.Index(fields=("is_completed",)),
            models.Index(fields=("status",)),
            models.Index(fields=("attendance_synced_at",)),
        ]

    def __str__(self) -> str:
        return f"{self.cohort.group_code}: {self.title}"


class OnlineScopeAssignment(models.Model):
    SCOPE_ACADEMY = "academy"
    SCOPE_COURSE = "course"
    SCOPE_COHORT = "cohort"
    SCOPE_CHOICES = (
        (SCOPE_ACADEMY, "Academy"),
        (SCOPE_COURSE, "Course"),
        (SCOPE_COHORT, "Cohort"),
    )

    ROLE_MANAGER = "manager"
    ROLE_DELIVERY_MANAGER = "delivery_manager"
    ROLE_COMPLIANCE_MANAGER = "compliance_manager"
    ROLE_REVIEW_MANAGER = "review_manager"
    ROLE_CHOICES = (
        (ROLE_MANAGER, "Manager"),
        (ROLE_DELIVERY_MANAGER, "Delivery manager"),
        (ROLE_COMPLIANCE_MANAGER, "Compliance manager"),
        (ROLE_REVIEW_MANAGER, "Review manager"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="online_scope_assignments",
    )
    role = models.CharField(max_length=40, choices=ROLE_CHOICES)
    scope_type = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    scope_key = models.CharField(max_length=120, blank=True, default="")
    course = models.ForeignKey(
        OnlineCourse,
        on_delete=models.CASCADE,
        related_name="scope_assignments",
        blank=True,
        null=True,
    )
    cohort = models.ForeignKey(
        OnlineCohort,
        on_delete=models.CASCADE,
        related_name="scope_assignments",
        blank=True,
        null=True,
    )
    note = models.CharField(max_length=255, blank=True, default="")
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_online_scope_assignments",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_scope_assignment"
        ordering = ("-is_primary", "scope_type", "role", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "role", "scope_key"),
                name="online_scope_assignment_unique_user_role_scope",
            )
        ]
        indexes = [
            models.Index(fields=("scope_type", "role", "is_active")),
            models.Index(fields=("user", "is_active")),
            models.Index(fields=("course", "is_active")),
            models.Index(fields=("cohort", "is_active")),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.role}:{self.scope_key}"


class OnlineStudentProfile(models.Model):
    GENDER_UNSPECIFIED = "unspecified"
    GENDER_FEMALE = "female"
    GENDER_MALE = "male"
    GENDER_DIVERSE = "diverse"
    GENDER_CHOICES = (
        (GENDER_UNSPECIFIED, "Unspecified"),
        (GENDER_FEMALE, "Female"),
        (GENDER_MALE, "Male"),
        (GENDER_DIVERSE, "Diverse"),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="online_profile")
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    employee_id = models.CharField(max_length=80, blank=True, default="")
    department = models.CharField(max_length=140, blank=True, default="")
    team_name = models.CharField(max_length=140, blank=True, default="")
    office_location = models.CharField(max_length=140, blank=True, default="")
    job_title = models.CharField(max_length=140, blank=True, default="")
    manager_name = models.CharField(max_length=180, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default=GENDER_UNSPECIFIED)
    avatar = models.ImageField(upload_to="online/student_avatars/", blank=True, null=True)
    preferred_language = models.CharField(
        max_length=2, choices=OnlineCourse.LOCALE_CHOICES, default=OnlineCourse.LOCALE_DE
    )
    employment_status = models.CharField(
        max_length=24,
        choices=(
            ("active", "Active"),
            ("on_leave", "On leave"),
            ("contractor", "Contractor"),
            ("inactive", "Inactive"),
        ),
        default="active",
    )
    hired_at = models.DateField(blank=True, null=True)
    is_trial_user = models.BooleanField(default=False)
    custom_fields = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_student_profile"
        ordering = ("id",)

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} ({self.user.email})"


class OnlineInstructorProfile(models.Model):
    teacher = models.OneToOneField(
        Lehrer,
        on_delete=models.CASCADE,
        related_name="online_instructor_profile",
    )
    department = models.CharField(max_length=140, blank=True, default="")
    job_title = models.CharField(max_length=140, blank=True, default="")
    bio = models.TextField(blank=True, default="")
    expertise_areas = models.JSONField(blank=True, default=list)
    spoken_languages = models.JSONField(blank=True, default=list)
    can_author = models.BooleanField(default=True)
    can_review = models.BooleanField(default=False)
    can_publish = models.BooleanField(default=False)
    can_generate_with_ai = models.BooleanField(default=True)
    can_manage_assessments = models.BooleanField(default=True)
    custom_fields = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_instructor_profile"
        ordering = ("teacher_id",)

    def __str__(self) -> str:
        return f"Instructor profile #{self.id} ({self.teacher_id})"


class OnlineCatalogAttributeDefinition(models.Model):
    ENTITY_COURSE = "course"
    ENTITY_STUDENT = "student"
    ENTITY_INSTRUCTOR = "instructor"
    ENTITY_PROGRAM = "program"
    ENTITY_KNOWLEDGE = "knowledge"
    ENTITY_CHOICES = (
        (ENTITY_COURSE, "Course"),
        (ENTITY_STUDENT, "Student"),
        (ENTITY_INSTRUCTOR, "Instructor"),
        (ENTITY_PROGRAM, "Program"),
        (ENTITY_KNOWLEDGE, "Knowledge"),
    )

    TYPE_TEXT = "text"
    TYPE_LONG_TEXT = "long_text"
    TYPE_NUMBER = "number"
    TYPE_DECIMAL = "decimal"
    TYPE_BOOLEAN = "boolean"
    TYPE_DATE = "date"
    TYPE_DATETIME = "datetime"
    TYPE_SINGLE_SELECT = "single_select"
    TYPE_MULTI_SELECT = "multi_select"
    TYPE_JSON = "json"
    DATA_TYPE_CHOICES = (
        (TYPE_TEXT, "Text"),
        (TYPE_LONG_TEXT, "Long text"),
        (TYPE_NUMBER, "Number"),
        (TYPE_DECIMAL, "Decimal"),
        (TYPE_BOOLEAN, "Boolean"),
        (TYPE_DATE, "Date"),
        (TYPE_DATETIME, "Datetime"),
        (TYPE_SINGLE_SELECT, "Single select"),
        (TYPE_MULTI_SELECT, "Multi select"),
        (TYPE_JSON, "JSON"),
    )

    slug = models.SlugField(max_length=120, unique=True)
    entity_type = models.CharField(max_length=20, choices=ENTITY_CHOICES)
    label = models.CharField(max_length=180)
    help_text = models.CharField(max_length=255, blank=True, default="")
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES, default=TYPE_TEXT)
    options = models.JSONField(blank=True, default=list)
    default_value = models.JSONField(blank=True, default=dict)
    is_required = models.BooleanField(default=False)
    is_filterable = models.BooleanField(default=True)
    is_searchable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_catalog_attribute_definition"
        ordering = ("entity_type", "sort_order", "id")
        indexes = [
            models.Index(fields=("entity_type", "is_active")),
            models.Index(fields=("slug",)),
        ]

    def __str__(self) -> str:
        return f"{self.entity_type}:{self.slug}"


class OnlineCatalogAttributeValue(models.Model):
    definition = models.ForeignKey(
        OnlineCatalogAttributeDefinition,
        on_delete=models.CASCADE,
        related_name="values",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="online_catalog_attribute_values",
        limit_choices_to=Q(app_label="online"),
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    value_json = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_catalog_attribute_value"
        ordering = ("definition__sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("definition", "content_type", "object_id"),
                name="online_catalog_attribute_value_unique_definition_object",
            )
        ]
        indexes = [
            models.Index(fields=("content_type", "object_id")),
            models.Index(fields=("definition",)),
        ]

    def __str__(self) -> str:
        return f"{self.definition.slug}:{self.content_type_id}:{self.object_id}"


class OnlineExternalCatalogProvider(models.Model):
    TYPE_LINKEDIN = "linkedin_learning"
    TYPE_COURSERA = "coursera"
    TYPE_UDEMY = "udemy_business"
    TYPE_CUSTOM = "custom"
    TYPE_CHOICES = (
        (TYPE_LINKEDIN, "LinkedIn Learning"),
        (TYPE_COURSERA, "Coursera"),
        (TYPE_UDEMY, "Udemy Business"),
        (TYPE_CUSTOM, "Custom"),
    )

    IMPORT_API = "api"
    IMPORT_FILE = "file"
    IMPORT_MANUAL = "manual"
    IMPORT_CHOICES = (
        (IMPORT_API, "API"),
        (IMPORT_FILE, "File"),
        (IMPORT_MANUAL, "Manual"),
    )

    STATUS_DRAFT = "draft"
    STATUS_READY = "ready"
    STATUS_ERROR = "error"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_READY, "Ready"),
        (STATUS_ERROR, "Error"),
    )

    slug = models.SlugField(max_length=120, unique=True)
    display_name = models.CharField(max_length=180)
    provider_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_CUSTOM)
    import_mode = models.CharField(max_length=16, choices=IMPORT_CHOICES, default=IMPORT_MANUAL)
    base_url = models.URLField(blank=True, default="")
    api_base_url = models.URLField(blank=True, default="")
    metadata_schema = models.JSONField(blank=True, default=dict)
    is_enabled = models.BooleanField(default=False)
    sync_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    verification_message = models.CharField(max_length=255, blank=True, default="")
    last_sync_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_external_catalog_provider"
        ordering = ("display_name", "id")
        indexes = [
            models.Index(fields=("provider_type", "is_enabled")),
            models.Index(fields=("sync_status",)),
        ]

    def __str__(self) -> str:
        return self.display_name


class OnlineLearningProgram(models.Model):
    ASSIGNMENT_MANUAL = "manual"
    ASSIGNMENT_ROLE = "role_based"
    ASSIGNMENT_AI = "ai_recommended"
    ASSIGNMENT_HYBRID = "hybrid"
    ASSIGNMENT_CHOICES = (
        (ASSIGNMENT_MANUAL, "Manual"),
        (ASSIGNMENT_ROLE, "Role-based"),
        (ASSIGNMENT_AI, "AI recommended"),
        (ASSIGNMENT_HYBRID, "Hybrid"),
    )

    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    target_audience = models.CharField(max_length=220, blank=True, default="")
    assignment_mode = models.CharField(max_length=20, choices=ASSIGNMENT_CHOICES, default=ASSIGNMENT_HYBRID)
    recommendation_prompt = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="online_learning_programs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_learning_program"
        ordering = ("title", "id")
        indexes = [
            models.Index(fields=("is_active",)),
            models.Index(fields=("slug",)),
        ]

    def __str__(self) -> str:
        return self.title


class OnlineLearningProgramCourse(models.Model):
    UNLOCK_IMMEDIATE = "immediate"
    UNLOCK_AFTER_PREVIOUS = "after_previous"
    UNLOCK_AFTER_PERCENT = "after_percent"
    UNLOCK_CHOICES = (
        (UNLOCK_IMMEDIATE, "Immediate"),
        (UNLOCK_AFTER_PREVIOUS, "After previous item"),
        (UNLOCK_AFTER_PERCENT, "After progress threshold"),
    )

    program = models.ForeignKey(
        OnlineLearningProgram,
        on_delete=models.CASCADE,
        related_name="program_courses",
    )
    course = models.ForeignKey(
        OnlineCourse,
        on_delete=models.CASCADE,
        related_name="learning_program_items",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    unlock_rule = models.CharField(max_length=24, choices=UNLOCK_CHOICES, default=UNLOCK_IMMEDIATE)
    min_completion_percent = models.PositiveSmallIntegerField(default=0)
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_learning_program_course"
        ordering = ("sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("program", "course"),
                name="online_learning_program_course_unique_program_course",
            )
        ]
        indexes = [
            models.Index(fields=("program", "sort_order")),
        ]

    def __str__(self) -> str:
        return f"{self.program.slug}:{self.course.slug}"


class OnlineStudentProgramAssignment(models.Model):
    SOURCE_MANUAL = "manual"
    SOURCE_STANDARD_SET = "standard_set"
    SOURCE_AI = "ai_recommendation"
    SOURCE_CHOICES = (
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_STANDARD_SET, "Standard set"),
        (SOURCE_AI, "AI recommendation"),
    )

    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_PAUSED = "paused"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_PAUSED, "Paused"),
    )

    profile = models.ForeignKey(
        "OnlineStudentProfile",
        on_delete=models.CASCADE,
        related_name="program_assignments",
    )
    program = models.ForeignKey(
        OnlineLearningProgram,
        on_delete=models.CASCADE,
        related_name="student_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_student_programs",
    )
    source = models.CharField(max_length=24, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    ai_reason = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_student_program_assignment"
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("profile", "program"),
                name="online_student_program_assignment_unique_profile_program",
            )
        ]
        indexes = [
            models.Index(fields=("status",)),
            models.Index(fields=("source",)),
        ]

    def __str__(self) -> str:
        return f"{self.profile_id}:{self.program_id}"


class OnlineKnowledgeSource(models.Model):
    SOURCE_UPLOAD = "upload"
    SOURCE_URL = "url"
    SOURCE_SHAREPOINT = "sharepoint"
    SOURCE_CONFLUENCE = "confluence"
    SOURCE_NOTION = "notion"
    SOURCE_VIDEO_TRANSCRIPT = "video_transcript"
    SOURCE_AUDIO_TRANSCRIPT = "audio_transcript"
    SOURCE_EXTERNAL_KB = "external_kb"
    SOURCE_CHOICES = (
        (SOURCE_UPLOAD, "Upload"),
        (SOURCE_URL, "URL"),
        (SOURCE_SHAREPOINT, "SharePoint"),
        (SOURCE_CONFLUENCE, "Confluence"),
        (SOURCE_NOTION, "Notion"),
        (SOURCE_VIDEO_TRANSCRIPT, "Video transcript"),
        (SOURCE_AUDIO_TRANSCRIPT, "Audio transcript"),
        (SOURCE_EXTERNAL_KB, "External knowledge base"),
    )

    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    source_type = models.CharField(max_length=24, choices=SOURCE_CHOICES, default=SOURCE_UPLOAD)
    external_url = models.URLField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_online_knowledge_sources",
    )
    linked_course = models.ForeignKey(
        OnlineCourse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knowledge_sources",
    )
    is_active = models.BooleanField(default=True)
    is_indexed = models.BooleanField(default=False)
    last_ingested_at = models.DateTimeField(blank=True, null=True)
    metadata_json = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_knowledge_source"
        ordering = ("title", "id")
        indexes = [
            models.Index(fields=("source_type", "is_active")),
            models.Index(fields=("linked_course",)),
        ]

    def __str__(self) -> str:
        return self.title


class OnlineKnowledgeDocument(models.Model):
    DOC_PDF = "pdf"
    DOC_DOCX = "docx"
    DOC_MARKDOWN = "markdown"
    DOC_HTML = "html"
    DOC_TRANSCRIPT = "transcript"
    DOC_LINK = "link"
    DOC_CHOICES = (
        (DOC_PDF, "PDF"),
        (DOC_DOCX, "DOCX"),
        (DOC_MARKDOWN, "Markdown"),
        (DOC_HTML, "HTML"),
        (DOC_TRANSCRIPT, "Transcript"),
        (DOC_LINK, "Link"),
    )

    source = models.ForeignKey(
        OnlineKnowledgeSource,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    document_type = models.CharField(max_length=20, choices=DOC_CHOICES, default=DOC_MARKDOWN)
    language = models.CharField(max_length=2, choices=OnlineCourse.LOCALE_CHOICES, default=OnlineCourse.LOCALE_EN)
    external_url = models.URLField(blank=True, default="")
    file_asset = models.FileField(upload_to="online/knowledge_documents/", blank=True, null=True)
    body_markdown = models.TextField(blank=True, default="")
    transcript_text = models.TextField(blank=True, default="")
    chunk_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    indexed_at = models.DateTimeField(blank=True, null=True)
    metadata_json = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_knowledge_document"
        ordering = ("source_id", "id")
        indexes = [
            models.Index(fields=("source", "is_active")),
            models.Index(fields=("document_type",)),
        ]

    def __str__(self) -> str:
        return f"{self.source.slug}:{self.title}"


class OnlineOrder(models.Model):
    PROVIDER_PAYPAL = "paypal"
    PROVIDER_KLARNA = "klarna"
    PROVIDER_SOFORT = "sofort"
    PROVIDER_TRIAL = "trial"
    PROVIDER_CHOICES = (
        (PROVIDER_PAYPAL, "PayPal"),
        (PROVIDER_KLARNA, "Klarna"),
        (PROVIDER_SOFORT, "Sofort"),
        (PROVIDER_TRIAL, "Trial"),
    )

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_REFUNDED = "refunded"
    STATUS_TRIAL = "trial"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REFUNDED, "Refunded"),
        (STATUS_TRIAL, "Trial"),
    )

    profile = models.ForeignKey(OnlineStudentProfile, on_delete=models.CASCADE, related_name="orders")
    course = models.ForeignKey(OnlineCourse, on_delete=models.PROTECT, related_name="orders")
    cohort = models.ForeignKey(OnlineCohort, on_delete=models.PROTECT, related_name="orders")
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, default="EUR")
    is_trial = models.BooleanField(default=False)
    paid_at = models.DateTimeField(blank=True, null=True)
    refunded_at = models.DateTimeField(blank=True, null=True)
    provider_payment_id = models.CharField(max_length=160, blank=True, default="")
    paid_event_id = models.CharField(max_length=160, blank=True, default="")
    payment_failure_reason = models.CharField(max_length=300, blank=True, default="")
    checkout_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    checkout_url = models.TextField(blank=True, default="")
    idempotency_key = models.CharField(max_length=120, blank=True, null=True, unique=True)
    external_reference = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_order"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status",)),
            models.Index(fields=("provider",)),
            models.Index(fields=("provider_payment_id",)),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("profile",),
                condition=Q(is_trial=True),
                name="online_order_single_trial_per_profile",
            )
        ]

    def __str__(self) -> str:
        return f"Order #{self.id} ({self.course.slug})"


class OnlineEnrollment(models.Model):
    STATUS_TRIAL = "trial"
    STATUS_ACTIVE = "active"
    STATUS_SUSPENDED = "suspended"
    STATUS_COMPLETED = "completed"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = (
        (STATUS_TRIAL, "Trial"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_REVOKED, "Revoked"),
    )

    profile = models.ForeignKey(OnlineStudentProfile, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(OnlineCourse, on_delete=models.PROTECT, related_name="enrollments")
    cohort = models.ForeignKey(OnlineCohort, on_delete=models.PROTECT, related_name="enrollments")
    order = models.ForeignKey(
        OnlineOrder, on_delete=models.SET_NULL, related_name="enrollments", blank=True, null=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "online_enrollment"
        ordering = ("-started_at",)
        unique_together = (("profile", "cohort"),)
        indexes = [
            models.Index(fields=("status",)),
        ]

    def __str__(self) -> str:
        return f"{self.profile.user.email} -> {self.cohort.group_code}"


class OnlineLessonProgress(models.Model):
    enrollment = models.ForeignKey(OnlineEnrollment, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey(OnlineCourseLesson, on_delete=models.CASCADE, related_name="enrollment_progress")
    active_step_id = models.CharField(max_length=120, blank=True, default="")
    completed_step_ids = models.JSONField(blank=True, default=list)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_lesson_progress"
        ordering = ("lesson__sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("enrollment", "lesson"),
                name="online_lesson_progress_unique_enrollment_lesson",
            )
        ]
        indexes = [
            models.Index(fields=("enrollment", "progress_percent")),
            models.Index(fields=("lesson", "completed_at")),
        ]

    def __str__(self) -> str:
        return f"Lesson progress #{self.id} ({self.enrollment_id}/{self.lesson_id})"


class OnlineEnrollmentAttestation(models.Model):
    enrollment = models.ForeignKey(OnlineEnrollment, on_delete=models.CASCADE, related_name="attestations")
    full_name = models.CharField(max_length=180)
    attestation_text = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    confirmed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "online_enrollment_attestation"
        ordering = ("-confirmed_at", "-id")
        indexes = [
            models.Index(fields=("enrollment", "confirmed_at")),
        ]

    def __str__(self) -> str:
        return f"Attestation #{self.id} ({self.enrollment_id})"


class OnlineCompletionEvidence(models.Model):
    STATUS_ISSUED = "issued"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = (
        (STATUS_ISSUED, "Issued"),
        (STATUS_REVOKED, "Revoked"),
    )

    enrollment = models.OneToOneField(
        OnlineEnrollment,
        on_delete=models.CASCADE,
        related_name="completion_evidence",
    )
    course = models.ForeignKey(OnlineCourse, on_delete=models.CASCADE, related_name="completion_evidence")
    attestation = models.ForeignKey(
        OnlineEnrollmentAttestation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completion_evidence_records",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ISSUED)
    evidence_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    completion_percent = models.PositiveSmallIntegerField(default=0)
    attendance_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    rule_snapshot = models.JSONField(blank=True, default=dict)
    issued_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_completion_evidence"
        ordering = ("-issued_at", "-id")
        indexes = [
            models.Index(fields=("course", "issued_at")),
            models.Index(fields=("status",)),
        ]

    def __str__(self) -> str:
        return f"Evidence {self.evidence_code} ({self.enrollment_id})"


class OnlineAttendance(models.Model):
    STATUS_UNKNOWN = "unknown"
    STATUS_PRESENT = "present"
    STATUS_ABSENT = "absent"
    STATUS_EXCUSED = "excused"
    STATUS_CHOICES = (
        (STATUS_UNKNOWN, "Unknown"),
        (STATUS_PRESENT, "Present"),
        (STATUS_ABSENT, "Absent"),
        (STATUS_EXCUSED, "Excused"),
    )

    enrollment = models.ForeignKey(OnlineEnrollment, on_delete=models.CASCADE, related_name="attendance_records")
    session = models.ForeignKey(OnlineSession, on_delete=models.CASCADE, related_name="attendance_records")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNKNOWN)
    attended_seconds = models.PositiveIntegerField(default=0)
    joined_at = models.DateTimeField(blank=True, null=True)
    left_at = models.DateTimeField(blank=True, null=True)
    notes = models.CharField(max_length=300, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_attendance"
        unique_together = (("enrollment", "session"),)
        ordering = ("session__starts_at",)

    def __str__(self) -> str:
        return f"{self.enrollment_id}/{self.session_id}: {self.status}"


class OnlineFeedbackMessage(models.Model):
    course = models.ForeignKey(
        OnlineCourse, on_delete=models.SET_NULL, blank=True, null=True, related_name="feedback_messages"
    )
    full_name = models.CharField(max_length=180)
    email = models.EmailField()
    subject = models.CharField(max_length=220)
    message = models.TextField()
    preferred_language = models.CharField(
        max_length=2, choices=OnlineCourse.LOCALE_CHOICES, default=OnlineCourse.LOCALE_DE
    )
    source_page = models.CharField(max_length=200, blank=True, default="")
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "online_feedback_message"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.email} ({self.subject})"


class OnlineSupportMessage(models.Model):
    SENDER_STUDENT = "student"
    SENDER_SUPPORT = "support"
    SENDER_CHOICES = (
        (SENDER_STUDENT, "Student"),
        (SENDER_SUPPORT, "Support"),
    )

    profile = models.ForeignKey(OnlineStudentProfile, on_delete=models.CASCADE, related_name="support_messages")
    enrollment = models.ForeignKey(
        OnlineEnrollment, on_delete=models.SET_NULL, blank=True, null=True, related_name="support_messages"
    )
    sender_type = models.CharField(max_length=20, choices=SENDER_CHOICES, default=SENDER_STUDENT)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "online_support_message"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.profile.user.email} ({self.sender_type})"


class OnlinePaymentEvent(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_REFUNDED = "refunded"
    STATUS_UNKNOWN = "unknown"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REFUNDED, "Refunded"),
        (STATUS_UNKNOWN, "Unknown"),
    )

    order = models.ForeignKey(
        OnlineOrder,
        on_delete=models.SET_NULL,
        related_name="payment_events",
        blank=True,
        null=True,
    )
    provider = models.CharField(max_length=20)
    event_id = models.CharField(max_length=160)
    event_type = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNKNOWN)
    provider_payment_id = models.CharField(max_length=160, blank=True, default="")
    signature_valid = models.BooleanField(default=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "online_payment_event"
        ordering = ("-processed_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "event_id"),
                name="online_payment_event_provider_event_unique",
            )
        ]
        indexes = [
            models.Index(fields=("status",)),
            models.Index(fields=("provider",)),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_id}"


class OnlineMagicLinkToken(models.Model):
    profile = models.ForeignKey(OnlineStudentProfile, on_delete=models.CASCADE, related_name="magic_link_tokens")
    cohort = models.ForeignKey(
        OnlineCohort,
        on_delete=models.SET_NULL,
        related_name="magic_link_tokens",
        blank=True,
        null=True,
    )
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(blank=True, null=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "online_magic_link_token"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("expires_at",)),
            models.Index(fields=("revoked_at",)),
        ]

    def __str__(self) -> str:
        return f"MagicLink #{self.id} ({self.profile.user.email})"


class OnlineSessionReminder(models.Model):
    enrollment = models.ForeignKey(OnlineEnrollment, on_delete=models.CASCADE, related_name="session_reminders")
    session = models.ForeignKey(OnlineSession, on_delete=models.CASCADE, related_name="reminders")
    hours_before = models.PositiveSmallIntegerField()
    email_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "online_session_reminder"
        ordering = ("-sent_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("enrollment", "session", "hours_before"),
                name="online_session_reminder_unique_per_offset",
            )
        ]
        indexes = [
            models.Index(fields=("hours_before",)),
            models.Index(fields=("email_sent",)),
        ]

    def __str__(self) -> str:
        return f"Reminder e{self.enrollment_id}/s{self.session_id} ({self.hours_before}h)"
