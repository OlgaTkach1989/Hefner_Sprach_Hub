from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.online.models import OnlineCourse
from apps.training.models import (
    TrainingAiConversation,
    TrainingAudience,
    TrainingAuditEvent,
    TrainingContentItem,
    TrainingContentSyncEvent,
    TrainingCourseRoleAssignment,
    TrainingGraderJob,
    TrainingNotebookLabHint,
    TrainingNotebookLabProfile,
    TrainingAssetClass,
    TrainingTopic,
    TrainingUserAudienceGrant,
)
from apps.training.serializers import TrainingCourseSummarySerializer
from apps.training.services.notebook_assignments import (
    build_notebook_assignment_admin_analytics,
    effective_assignment_code,
    sync_course_library_for_notebook_content,
)

User = get_user_model()


def _validate_notebook_grader_config(grader_config: dict) -> dict:
    mode = str(grader_config.get("mode") or "demo").strip().lower()
    if mode == "custom_rules":
        checks = grader_config.get("checks")
        if not isinstance(checks, list) or not checks:
            raise serializers.ValidationError("custom_rules mode requires at least one grading check.")
        for index, raw_check in enumerate(checks, start=1):
            if not isinstance(raw_check, dict):
                raise serializers.ValidationError(f"Check #{index} must be an object.")
            kind = str(raw_check.get("kind") or "").strip()
            if kind not in {
                "code_contains",
                "markdown_contains",
                "forbidden_text",
                "required_function",
                "numeric_assignment",
            }:
                raise serializers.ValidationError(f"Check #{index} uses unsupported kind '{kind}'.")
            if kind == "numeric_assignment":
                if not str(raw_check.get("variable") or "").strip():
                    raise serializers.ValidationError(f"Check #{index} must define 'variable'.")
                if raw_check.get("expected") in (None, ""):
                    raise serializers.ValidationError(f"Check #{index} must define 'expected'.")
    return grader_config


def _validate_course_role_eligibility(*, user: User, role: str) -> None:
    if not user.is_active:
        raise serializers.ValidationError("Inactive users cannot receive course role assignments.")

    is_admin = bool(user.is_admin or user.is_superuser)
    is_curator = hasattr(user, "lehrer_user")

    if role == TrainingCourseRoleAssignment.Role.INSTRUCTOR:
        if not is_curator:
            raise serializers.ValidationError("Instructor assignments require curator access.")
        return

    if role in {TrainingCourseRoleAssignment.Role.OWNER, TrainingCourseRoleAssignment.Role.REVIEWER}:
        if not (is_curator or is_admin):
            raise serializers.ValidationError("Course owner and reviewer assignments require curator or admin access.")
        return


class TrainingAdminUserSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    username = serializers.CharField(allow_null=True)
    fullName = serializers.SerializerMethodField()
    isAdmin = serializers.BooleanField(source="is_admin")

    def get_fullName(self, obj) -> str:
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name or obj.email


class TrainingAdminUserLookupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    username = serializers.CharField(allow_null=True)
    firstName = serializers.CharField(source="first_name", allow_blank=True)
    lastName = serializers.CharField(source="last_name", allow_blank=True)
    fullName = serializers.SerializerMethodField()
    isAdmin = serializers.BooleanField(source="is_admin")
    isActive = serializers.BooleanField(source="is_active")

    def get_fullName(self, obj) -> str:
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name or obj.email


class TrainingAdminAudienceSerializer(serializers.ModelSerializer):
    grantsCount = serializers.SerializerMethodField()
    contentPoliciesCount = serializers.SerializerMethodField()

    class Meta:
        model = TrainingAudience
        fields = (
            "id",
            "slug",
            "name",
            "short_label",
            "description",
            "audience_type",
            "privilege_rank",
            "is_internal",
            "is_active",
            "grantsCount",
            "contentPoliciesCount",
        )

    def get_grantsCount(self, obj: TrainingAudience) -> int:
        return obj.user_grants.count()

    def get_contentPoliciesCount(self, obj: TrainingAudience) -> int:
        return obj.content_policies.count()


class TrainingAdminAudienceWriteSerializer(serializers.ModelSerializer):
    short_label = serializers.CharField(required=False, allow_blank=True, default="")
    audience_type = serializers.ChoiceField(
        choices=TrainingAudience.AudienceType.choices,
        required=False,
        default=TrainingAudience.AudienceType.GENERAL,
    )
    privilege_rank = serializers.IntegerField(required=False, min_value=0, max_value=999, default=0)

    class Meta:
        model = TrainingAudience
        fields = (
            "slug",
            "name",
            "short_label",
            "description",
            "audience_type",
            "privilege_rank",
            "is_internal",
            "is_active",
        )


class TrainingAdminCourseRoleAssignmentSerializer(serializers.ModelSerializer):
    course = TrainingCourseSummarySerializer(read_only=True)
    user = TrainingAdminUserSummarySerializer(read_only=True)

    class Meta:
        model = TrainingCourseRoleAssignment
        fields = ("id", "course", "user", "role", "is_primary", "response_sla_hours", "created_at")


class TrainingAdminCourseRoleAssignmentWriteSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    course_id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=TrainingCourseRoleAssignment.Role.choices)
    is_primary = serializers.BooleanField(required=False, default=False)
    response_sla_hours = serializers.IntegerField(required=False, min_value=1, max_value=168, default=24)

    def validate_user_id(self, value: int) -> int:
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User was not found.")
        return value

    def validate_course_id(self, value: int) -> int:
        if not OnlineCourse.objects.filter(id=value).exists():
            raise serializers.ValidationError("Course was not found.")
        return value

    def validate(self, attrs):
        user = User.objects.filter(id=attrs["user_id"]).first()
        if user is None:
            raise serializers.ValidationError({"user_id": "User was not found."})
        _validate_course_role_eligibility(user=user, role=attrs["role"])
        return attrs

    def create(self, validated_data):
        instance = TrainingCourseRoleAssignment.objects.create(
            user_id=validated_data["user_id"],
            course_id=validated_data["course_id"],
            role=validated_data["role"],
            is_primary=validated_data.get("is_primary", False),
            response_sla_hours=validated_data.get("response_sla_hours", 24),
        )
        return instance


class TrainingAdminCourseRoleAssignmentPatchSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=TrainingCourseRoleAssignment.Role.choices, required=False)
    is_primary = serializers.BooleanField(required=False)
    response_sla_hours = serializers.IntegerField(required=False, min_value=1, max_value=168)

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        if instance is None:
            return attrs
        role = attrs.get("role", instance.role)
        _validate_course_role_eligibility(user=instance.user, role=role)
        return attrs

    def update(self, instance: TrainingCourseRoleAssignment, validated_data):
        for field in ("role", "is_primary", "response_sla_hours"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save()
        return instance


class TrainingAdminReportsOverviewSerializer(serializers.Serializer):
    courseId = serializers.IntegerField(allow_null=True)
    failedAuditEvents = serializers.IntegerField()
    deniedAuditEvents = serializers.IntegerField()
    failedSyncEvents = serializers.IntegerField()
    failedGraderJobs = serializers.IntegerField()
    unresolvedAiConversations = serializers.IntegerField()
    latestAuditFailureAt = serializers.DateTimeField(allow_null=True)
    latestSyncFailureAt = serializers.DateTimeField(allow_null=True)
    latestGraderFailureAt = serializers.DateTimeField(allow_null=True)


class TrainingAdminAuditEventSerializer(serializers.ModelSerializer):
    eventId = serializers.UUIDField(source="event_id", read_only=True)
    actorEmail = serializers.SerializerMethodField()
    targetUserEmail = serializers.SerializerMethodField()
    contentSlug = serializers.SerializerMethodField()
    submissionPublicId = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    course = serializers.SerializerMethodField()

    class Meta:
        model = TrainingAuditEvent
        fields = (
            "eventId",
            "category",
            "event_type",
            "outcome",
            "actorEmail",
            "targetUserEmail",
            "course",
            "contentSlug",
            "submissionPublicId",
            "request_method",
            "request_path",
            "metadata",
            "createdAt",
        )

    def get_actorEmail(self, obj: TrainingAuditEvent) -> str:
        return obj.actor_email or getattr(obj.actor, "email", "")

    def get_targetUserEmail(self, obj: TrainingAuditEvent) -> str:
        return obj.target_user_email or getattr(obj.target_user, "email", "")

    def get_contentSlug(self, obj: TrainingAuditEvent) -> str:
        if obj.content_item_id:
            return obj.content_item.slug
        if obj.submission_id:
            return obj.submission.content_item.slug
        return ""

    def get_submissionPublicId(self, obj: TrainingAuditEvent) -> str:
        return str(obj.submission.public_id) if obj.submission_id else ""

    def get_course(self, obj: TrainingAuditEvent):
        course = obj.course
        if course is None and obj.content_item_id:
            course = obj.content_item.course
        if course is None and obj.submission_id:
            course = obj.submission.content_item.course
        if course is None:
            return None
        return TrainingCourseSummarySerializer(course).data


class TrainingAdminContentSyncEventSerializer(serializers.ModelSerializer):
    eventType = serializers.CharField(source="event_type", read_only=True)
    externalSourceId = serializers.CharField(source="external_source_id", read_only=True)
    contentSlug = serializers.CharField(source="content_slug", read_only=True)
    payloadSummary = serializers.JSONField(source="payload_summary", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    course = serializers.SerializerMethodField()

    class Meta:
        model = TrainingContentSyncEvent
        fields = (
            "id",
            "source",
            "eventType",
            "status",
            "course",
            "contentSlug",
            "externalSourceId",
            "detail",
            "payloadSummary",
            "createdAt",
        )

    def get_course(self, obj: TrainingContentSyncEvent):
        course = obj.content_item.course if obj.content_item_id and obj.content_item.course_id else None
        if course is None:
            return None
        return TrainingCourseSummarySerializer(course).data


class TrainingAdminGraderJobSerializer(serializers.ModelSerializer):
    submissionPublicId = serializers.UUIDField(source="submission.public_id", read_only=True)
    contentSlug = serializers.CharField(source="submission.content_item.slug", read_only=True)
    contentName = serializers.CharField(source="submission.content_item.name", read_only=True)
    studentEmail = serializers.EmailField(source="submission.user.email", read_only=True)
    attemptsCount = serializers.IntegerField(source="attempts_count", read_only=True)
    availableAt = serializers.DateTimeField(source="available_at", read_only=True)
    lockedAt = serializers.DateTimeField(source="locked_at", read_only=True, allow_null=True)
    finishedAt = serializers.DateTimeField(source="finished_at", read_only=True, allow_null=True)
    workerName = serializers.CharField(source="worker_name", read_only=True)
    errorMessage = serializers.CharField(source="error_message", read_only=True)
    course = serializers.SerializerMethodField()

    class Meta:
        model = TrainingGraderJob
        fields = (
            "id",
            "status",
            "backend",
            "priority",
            "attemptsCount",
            "course",
            "contentSlug",
            "contentName",
            "studentEmail",
            "submissionPublicId",
            "availableAt",
            "lockedAt",
            "finishedAt",
            "workerName",
            "errorMessage",
        )

    def get_course(self, obj: TrainingGraderJob):
        course = obj.submission.content_item.course if obj.submission_id and obj.submission.content_item.course_id else None
        if course is None:
            return None
        return TrainingCourseSummarySerializer(course).data


class TrainingAdminUserAudienceGrantSerializer(serializers.ModelSerializer):
    user = TrainingAdminUserSummarySerializer(read_only=True)
    audience = TrainingAdminAudienceSerializer(read_only=True)
    grantedBy = TrainingAdminUserSummarySerializer(source="granted_by", read_only=True)
    isActive = serializers.SerializerMethodField()

    class Meta:
        model = TrainingUserAudienceGrant
        fields = ("id", "user", "audience", "grantedBy", "note", "expires_at", "isActive", "created_at")

    def get_isActive(self, obj: TrainingUserAudienceGrant) -> bool:
        return obj.expires_at is None or obj.expires_at > timezone.now()


class TrainingAdminUserAudienceGrantWriteSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    audience_id = serializers.IntegerField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_user_id(self, value: int) -> int:
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User was not found.")
        return value

    def validate_audience_id(self, value: int) -> int:
        audience = TrainingAudience.objects.filter(id=value).first()
        if audience is None:
            raise serializers.ValidationError("Audience was not found.")
        if not audience.is_active:
            raise serializers.ValidationError("Audience must be active.")
        return value

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("Expiration must be in the future.")
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        granted_by = getattr(request, "user", None) if request and getattr(request.user, "is_authenticated", False) else None
        instance = TrainingUserAudienceGrant.objects.create(
            user_id=validated_data["user_id"],
            audience_id=validated_data["audience_id"],
            granted_by=granted_by,
            note=validated_data.get("note", ""),
            expires_at=validated_data.get("expires_at"),
        )
        return instance


class TrainingAdminUserAudienceGrantPatchSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("Expiration must be in the future.")
        return value

    def update(self, instance: TrainingUserAudienceGrant, validated_data):
        for field in ("note", "expires_at"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save()
        return instance


class TrainingAdminContentGovernanceSerializer(serializers.ModelSerializer):
    course = TrainingCourseSummarySerializer(read_only=True)
    owner = TrainingAdminUserSummarySerializer(read_only=True)
    assetClassCount = serializers.SerializerMethodField()
    topicCount = serializers.SerializerMethodField()
    audiencePolicyCount = serializers.SerializerMethodField()
    hasLab = serializers.SerializerMethodField()
    labReady = serializers.SerializerMethodField()
    governanceFlags = serializers.SerializerMethodField()

    class Meta:
        model = TrainingContentItem
        fields = (
            "id",
            "slug",
            "name",
            "content_kind",
            "status",
            "access_scope",
            "difficulty",
            "course",
            "owner",
            "is_repeatable_on_demand",
            "supports_inline_lab",
            "assetClassCount",
            "topicCount",
            "audiencePolicyCount",
            "hasLab",
            "labReady",
            "governanceFlags",
            "updated_at",
        )

    def get_assetClassCount(self, obj: TrainingContentItem) -> int:
        return obj.asset_classes.count()

    def get_topicCount(self, obj: TrainingContentItem) -> int:
        return obj.topics.count()

    def get_audiencePolicyCount(self, obj: TrainingContentItem) -> int:
        return obj.audience_policies.count()

    def get_hasLab(self, obj: TrainingContentItem) -> bool:
        return hasattr(obj, "lab_profile")

    def get_labReady(self, obj: TrainingContentItem) -> bool:
        try:
            lab = obj.lab_profile
        except TrainingNotebookLabProfile.DoesNotExist:
            return False
        return bool(lab.is_active and lab.notebook_path)

    def get_governanceFlags(self, obj: TrainingContentItem) -> list[str]:
        flags: list[str] = []
        if obj.asset_classes.count() == 0:
            flags.append("missing_asset_class")
        if obj.topics.count() == 0:
            flags.append("missing_topic")
        if obj.owner_id is None:
            flags.append("missing_owner")
        if obj.access_scope == TrainingContentItem.AccessScope.ENTITLED and obj.audience_policies.count() == 0:
            flags.append("missing_audience_policy")
        if obj.content_kind == TrainingContentItem.ContentKind.NOTEBOOK:
            try:
                lab = obj.lab_profile
            except TrainingNotebookLabProfile.DoesNotExist:
                flags.append("missing_lab_profile")
            else:
                if not lab.is_active or not lab.notebook_path:
                    flags.append("lab_profile_incomplete")
        return flags


class TrainingAdminNotebookLabHintSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingNotebookLabHint
        fields = (
            "id",
            "title",
            "body_markdown",
            "availability_mode",
            "min_attempt_number",
            "max_score_percent",
            "sort_order",
            "is_active",
        )


class TrainingAdminNotebookAssignmentAnalyticsSerializer(serializers.Serializer):
    learnersAttempted = serializers.IntegerField()
    totalSubmissions = serializers.IntegerField()
    passRatePercent = serializers.FloatField()
    averageScorePercent = serializers.FloatField(allow_null=True)
    latestSubmissionAt = serializers.DateTimeField(allow_null=True)
    pendingJobs = serializers.IntegerField()
    failedJobs = serializers.IntegerField()
    averageAttemptsPerLearner = serializers.FloatField()
    bestScorePercent = serializers.FloatField(allow_null=True)
    hintViews = serializers.IntegerField()
    gradeDistribution = serializers.DictField(child=serializers.IntegerField())


class TrainingAdminNotebookAssignmentSerializer(serializers.ModelSerializer):
    course = TrainingCourseSummarySerializer(read_only=True)
    owner = TrainingAdminUserSummarySerializer(read_only=True)
    assetClassIds = serializers.SerializerMethodField()
    topicIds = serializers.SerializerMethodField()
    audienceIds = serializers.SerializerMethodField()
    labProfile = serializers.SerializerMethodField()
    hints = serializers.SerializerMethodField()
    analytics = serializers.SerializerMethodField()
    builderLibraryItemId = serializers.SerializerMethodField()

    class Meta:
        model = TrainingContentItem
        fields = (
            "id",
            "slug",
            "name",
            "description",
            "body_markdown",
            "status",
            "access_scope",
            "difficulty",
            "source_url",
            "search_keywords",
            "version_label",
            "estimated_minutes",
            "is_repeatable_on_demand",
            "supports_inline_lab",
            "course",
            "owner",
            "assetClassIds",
            "topicIds",
            "audienceIds",
            "labProfile",
            "hints",
            "analytics",
            "builderLibraryItemId",
            "updated_at",
        )

    def get_assetClassIds(self, obj: TrainingContentItem) -> list[int]:
        return list(obj.asset_classes.values_list("id", flat=True))

    def get_topicIds(self, obj: TrainingContentItem) -> list[int]:
        return list(obj.topics.values_list("id", flat=True))

    def get_audienceIds(self, obj: TrainingContentItem) -> list[int]:
        return list(obj.audience_policies.values_list("audience_id", flat=True))

    def get_labProfile(self, obj: TrainingContentItem) -> dict[str, object] | None:
        try:
            lab_profile = obj.lab_profile
        except TrainingNotebookLabProfile.DoesNotExist:
            return None
        return {
            "assignmentCode": effective_assignment_code(lab_profile),
            "runtimeBackend": lab_profile.runtime_backend,
            "graderBackend": lab_profile.grader_backend,
            "runtimeImage": lab_profile.runtime_image,
            "notebookPath": lab_profile.notebook_path,
            "launchPath": lab_profile.launch_path,
            "passThresholdPercent": lab_profile.pass_threshold_percent,
            "maxAttempts": lab_profile.max_attempts,
            "allowGpu": lab_profile.allow_gpu,
            "allowNetwork": lab_profile.allow_network,
            "maxSessionMinutes": lab_profile.max_session_minutes,
            "isActive": lab_profile.is_active,
            "graderConfig": lab_profile.grader_config,
        }

    def get_hints(self, obj: TrainingContentItem) -> list[dict[str, object]]:
        try:
            lab_profile = obj.lab_profile
        except TrainingNotebookLabProfile.DoesNotExist:
            return []
        hints = list(lab_profile.hints.order_by("sort_order", "id"))
        return TrainingAdminNotebookLabHintSerializer(hints, many=True).data

    def get_analytics(self, obj: TrainingContentItem) -> dict[str, object]:
        analytics = build_notebook_assignment_admin_analytics(content_item=obj)
        return TrainingAdminNotebookAssignmentAnalyticsSerializer(
            {
                "learnersAttempted": analytics.learners_attempted,
                "totalSubmissions": analytics.total_submissions,
                "passRatePercent": analytics.pass_rate_percent,
                "averageScorePercent": analytics.average_score_percent,
                "latestSubmissionAt": analytics.latest_submission_at,
                "pendingJobs": analytics.pending_jobs,
                "failedJobs": analytics.failed_jobs,
                "averageAttemptsPerLearner": analytics.average_attempts_per_learner,
                "bestScorePercent": analytics.best_score_percent,
                "hintViews": analytics.hint_views,
                "gradeDistribution": analytics.grade_distribution,
            }
        ).data

    def get_builderLibraryItemId(self, obj: TrainingContentItem) -> int | None:
        library_item = obj.online_course_library_items.order_by("id").first()
        return library_item.id if library_item else None


class TrainingAdminNotebookLabHintWriteSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    title = serializers.CharField(max_length=180)
    body_markdown = serializers.CharField()
    availability_mode = serializers.ChoiceField(choices=TrainingNotebookLabHint.AvailabilityMode.choices)
    min_attempt_number = serializers.IntegerField(required=False, min_value=1, max_value=99, default=1)
    max_score_percent = serializers.IntegerField(required=False, min_value=0, max_value=100, default=100)
    sort_order = serializers.IntegerField(required=False, min_value=0, max_value=999, default=0)
    is_active = serializers.BooleanField(required=False, default=True)


class TrainingAdminNotebookAssignmentWriteSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=140)
    name = serializers.CharField(max_length=220)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    body_markdown = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(
        choices=TrainingContentItem.Status.choices,
        required=False,
        default=TrainingContentItem.Status.PUBLISHED,
    )
    access_scope = serializers.ChoiceField(
        choices=TrainingContentItem.AccessScope.choices,
        required=False,
        default=TrainingContentItem.AccessScope.ENTITLED,
    )
    difficulty = serializers.ChoiceField(
        choices=TrainingContentItem.Difficulty.choices,
        required=False,
        default=TrainingContentItem.Difficulty.INTERMEDIATE,
    )
    course_id = serializers.IntegerField(required=False, allow_null=True)
    owner_id = serializers.IntegerField(required=False, allow_null=True)
    source_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    search_keywords = serializers.CharField(required=False, allow_blank=True, max_length=400, default="")
    version_label = serializers.CharField(required=False, allow_blank=True, max_length=40, default="")
    estimated_minutes = serializers.IntegerField(required=False, min_value=0, max_value=1440, default=0)
    is_repeatable_on_demand = serializers.BooleanField(required=False, default=True)
    supports_inline_lab = serializers.BooleanField(required=False, default=True)
    asset_class_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)
    topic_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)
    audience_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)
    lab = serializers.DictField()
    hints = TrainingAdminNotebookLabHintWriteSerializer(many=True, required=False)

    def validate_course_id(self, value):
        if value is None:
            return value
        if not OnlineCourse.objects.filter(id=value).exists():
            raise serializers.ValidationError("Course was not found.")
        return value

    def validate_owner_id(self, value):
        if value is None:
            return value
        if not User.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Owner was not found.")
        return value

    def validate_asset_class_ids(self, value):
        ids = list(dict.fromkeys(value))
        if TrainingAssetClass.objects.filter(id__in=ids).count() != len(ids):
            raise serializers.ValidationError("One or more asset classes were not found.")
        return ids

    def validate_topic_ids(self, value):
        ids = list(dict.fromkeys(value))
        if TrainingTopic.objects.filter(id__in=ids).count() != len(ids):
            raise serializers.ValidationError("One or more topics were not found.")
        return ids

    def validate_audience_ids(self, value):
        ids = list(dict.fromkeys(value))
        if TrainingAudience.objects.filter(id__in=ids).count() != len(ids):
            raise serializers.ValidationError("One or more audiences were not found.")
        return ids

    def validate_lab(self, value):
        assignment_code = str(value.get("assignmentCode") or "").strip()
        notebook_path = str(value.get("notebookPath") or "").strip()
        if not notebook_path:
            raise serializers.ValidationError("notebookPath is required.")
        pass_threshold_percent = int(value.get("passThresholdPercent") or 70)
        if pass_threshold_percent < 1 or pass_threshold_percent > 100:
            raise serializers.ValidationError("passThresholdPercent must be between 1 and 100.")
        max_attempts = int(value.get("maxAttempts") or 5)
        if max_attempts < 1 or max_attempts > 99:
            raise serializers.ValidationError("maxAttempts must be between 1 and 99.")
        grader_config = _validate_notebook_grader_config(dict(value.get("graderConfig") or {}))
        return {
            "runtime_backend": str(value.get("runtimeBackend") or TrainingNotebookLabProfile.RuntimeBackend.JUPYTERHUB).strip(),
            "grader_backend": str(value.get("graderBackend") or TrainingNotebookLabProfile.GraderBackend.NBGRADER).strip(),
            "runtime_image": str(value.get("runtimeImage") or "").strip(),
            "notebook_path": notebook_path,
            "launch_path": str(value.get("launchPath") or "").strip(),
            "assignment_code": assignment_code,
            "pass_threshold_percent": pass_threshold_percent,
            "max_attempts": max_attempts,
            "allow_gpu": bool(value.get("allowGpu")),
            "allow_network": bool(value.get("allowNetwork")),
            "max_session_minutes": int(value.get("maxSessionMinutes") or 120),
            "is_active": bool(value.get("isActive", True)),
            "grader_config": grader_config,
        }

    def create(self, validated_data):
        return self._write(instance=None, validated_data=validated_data)

    def update(self, instance: TrainingContentItem, validated_data):
        return self._write(instance=instance, validated_data=validated_data)

    @transaction.atomic
    def _write(self, *, instance: TrainingContentItem | None, validated_data):
        hints_payload = validated_data.pop("hints", None)
        lab_payload = validated_data.pop("lab")
        asset_class_ids = validated_data.pop("asset_class_ids", None)
        topic_ids = validated_data.pop("topic_ids", None)
        audience_ids = validated_data.pop("audience_ids", None)

        defaults = {
            **validated_data,
            "content_kind": TrainingContentItem.ContentKind.NOTEBOOK,
            "supports_inline_lab": validated_data.get("supports_inline_lab", True),
        }
        if instance is None:
            content_item = TrainingContentItem.objects.create(**defaults)
        else:
            for field, value in defaults.items():
                setattr(instance, field, value)
            instance.content_kind = TrainingContentItem.ContentKind.NOTEBOOK
            instance.save()
            content_item = instance

        if asset_class_ids is not None:
            content_item.asset_classes.set(asset_class_ids)
        if topic_ids is not None:
            content_item.topics.set(topic_ids)
        if audience_ids is not None:
            content_item.audience_policies.all().delete()
            content_item.audience_policies.bulk_create(
                [
                    content_item.audience_policies.model(content_item=content_item, audience_id=audience_id)
                    for audience_id in audience_ids
                ]
            )

        lab_profile, _created = TrainingNotebookLabProfile.objects.get_or_create(content_item=content_item)
        for field, value in lab_payload.items():
            setattr(lab_profile, field, value)
        lab_profile.save()

        if hints_payload is not None:
            lab_profile.hints.all().delete()
            TrainingNotebookLabHint.objects.bulk_create(
                [
                    TrainingNotebookLabHint(
                        lab_profile=lab_profile,
                        title=hint["title"],
                        body_markdown=hint["body_markdown"],
                        availability_mode=hint["availability_mode"],
                        min_attempt_number=hint.get("min_attempt_number", 1),
                        max_score_percent=hint.get("max_score_percent", 100),
                        sort_order=hint.get("sort_order", 0),
                        is_active=hint.get("is_active", True),
                    )
                    for hint in hints_payload
                ]
            )
            persisted_hints = list(lab_profile.hints.order_by("sort_order", "id"))
            if persisted_hints:
                hint_id_map = {hint.id: hint.id for hint in persisted_hints}
                hint_id_map.update({index: hint.id for index, hint in enumerate(persisted_hints, start=1)})
                grader_config = dict(lab_profile.grader_config or {})
                checks = grader_config.get("checks")
                if isinstance(checks, list):
                    updated = False
                    for check in checks:
                        raw_hint_ids = check.get("hintIds")
                        if not isinstance(raw_hint_ids, list):
                            continue
                        normalized_hint_ids = []
                        for raw_hint_id in raw_hint_ids:
                            try:
                                resolved_hint_id = hint_id_map.get(int(raw_hint_id))
                            except (TypeError, ValueError):
                                resolved_hint_id = None
                            if resolved_hint_id is not None:
                                normalized_hint_ids.append(resolved_hint_id)
                        normalized_hint_ids = list(dict.fromkeys(normalized_hint_ids))
                        if normalized_hint_ids != raw_hint_ids:
                            check["hintIds"] = normalized_hint_ids
                            updated = True
                    if updated:
                        lab_profile.grader_config = grader_config
                        lab_profile.save(update_fields=["grader_config", "updated_at"])

        sync_course_library_for_notebook_content(content_item=content_item)
        return content_item


class TrainingAdminAiOverviewSerializer(serializers.Serializer):
    courseId = serializers.IntegerField(allow_null=True)
    aiConversations = serializers.IntegerField()
    distinctLearners = serializers.IntegerField()
    aiQuestions = serializers.IntegerField()
    resolvedResponses = serializers.IntegerField()
    partialResponses = serializers.IntegerField()
    escalatedResponses = serializers.IntegerField()
    unresolvedQueueCount = serializers.IntegerField()
    assignedQueueCount = serializers.IntegerField()
    resolvedConversations = serializers.IntegerField()
    archivedConversations = serializers.IntegerField()
    faqItems = serializers.IntegerField()
    contentItemsCoveredByFaq = serializers.IntegerField()
    faqCoveragePercent = serializers.FloatField()
    indexedContentItems = serializers.IntegerField()
    indexedChunks = serializers.IntegerField()
    generatedQuizzes = serializers.IntegerField()
    completedQuizzes = serializers.IntegerField()


class TrainingAdminAiAnalyticsTopContentSerializer(serializers.Serializer):
    contentId = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()
    aiQuestions = serializers.IntegerField()
    unresolvedConversations = serializers.IntegerField()
    accessDeniedCount = serializers.IntegerField()
    latestQuestionAt = serializers.DateTimeField(allow_null=True)


class TrainingAdminAiAnalyticsSerializer(serializers.Serializer):
    courseId = serializers.IntegerField(allow_null=True)
    aiQuestionsLast7Days = serializers.IntegerField()
    aiFailuresLast7Days = serializers.IntegerField()
    quizFailuresLast7Days = serializers.IntegerField()
    escalationsLast7Days = serializers.IntegerField()
    avgResolutionHours = serializers.FloatField(allow_null=True)
    publishedContentItems = serializers.IntegerField()
    directusManagedContentItems = serializers.IntegerField()
    directusItemsWithoutOwner = serializers.IntegerField()
    unindexedPublishedItems = serializers.IntegerField()
    staleIndexedPublishedItems = serializers.IntegerField()
    directusSyncFailuresLast7Days = serializers.IntegerField()
    lastDirectusSyncAt = serializers.DateTimeField(allow_null=True)
    lastKnowledgeRefreshAt = serializers.DateTimeField(allow_null=True)
    windowDays = serializers.IntegerField()
    providerMode = serializers.CharField()
    externalProviderConfigured = serializers.BooleanField()
    pgvectorEnabled = serializers.BooleanField()
    aiQuestionsWindow = serializers.IntegerField()
    aiResponseFailuresWindow = serializers.IntegerField()
    aiEscalationsWindow = serializers.IntegerField()
    quizSubmitFailuresWindow = serializers.IntegerField()
    contentAccessDeniedWindow = serializers.IntegerField()
    directusSyncAppliedWindow = serializers.IntegerField()
    directusSyncFailedWindow = serializers.IntegerField()
    unresolvedQueueCount = serializers.IntegerField()
    staleIndexedContentCount = serializers.IntegerField()
    latestIndexRebuildAt = serializers.DateTimeField(allow_null=True)
    latestIndexRebuildOutcome = serializers.CharField(allow_blank=True)
    latestDirectusSyncAt = serializers.DateTimeField(allow_null=True)
    latestDirectusSyncOutcome = serializers.CharField(allow_blank=True)
    topContentItems = TrainingAdminAiAnalyticsTopContentSerializer(many=True)


class TrainingAdminAiConversationSerializer(serializers.Serializer):
    publicId = serializers.UUIDField(source="public_id")
    title = serializers.CharField()
    governanceStatus = serializers.CharField(source="governance_status")
    conversationStatus = serializers.CharField(source="status")
    lastActivityAt = serializers.DateTimeField(source="last_activity_at")
    createdAt = serializers.DateTimeField(source="created_at")
    resolvedAt = serializers.DateTimeField(source="resolved_at", allow_null=True)
    resolutionNote = serializers.CharField(source="resolution_note")
    latestUserPrompt = serializers.CharField(source="last_user_prompt")
    latestResolutionStatus = serializers.CharField(source="latest_resolution_status", allow_null=True)
    latestAssistantBody = serializers.SerializerMethodField()
    latestAssistantCreatedAt = serializers.DateTimeField(source="latest_assistant_created_at", allow_null=True)
    recommendedOwnerId = serializers.IntegerField(source="recommended_owner_id", allow_null=True)
    recommendedOwnerSlaHours = serializers.IntegerField(source="recommended_owner_sla_hours", allow_null=True)
    userMessageCount = serializers.IntegerField(source="user_message_count")
    assistantMessageCount = serializers.IntegerField(source="assistant_message_count")
    learner = TrainingAdminUserSummarySerializer(source="user", read_only=True)
    assignedTo = TrainingAdminUserSummarySerializer(source="assigned_to", read_only=True)
    resolvedBy = TrainingAdminUserSummarySerializer(source="resolved_by", read_only=True)
    content = serializers.SerializerMethodField()

    def get_latestAssistantBody(self, obj: TrainingAiConversation) -> str:
        body = str(getattr(obj, "latest_assistant_body", "") or "").strip()
        if len(body) <= 320:
            return body
        return f"{body[:317].rstrip()}..."

    def get_content(self, obj: TrainingAiConversation) -> dict[str, object] | None:
        if obj.content_item_id is None:
            return None
        course = obj.content_item.course
        return {
            "id": obj.content_item.id,
            "slug": obj.content_item.slug,
            "name": obj.content_item.name,
            "contentKind": obj.content_item.content_kind,
            "course": (
                {
                    "id": course.id,
                    "slug": course.slug,
                    "title_de": course.title_de,
                    "title_en": course.title_en,
                }
                if course is not None
                else None
            ),
        }


class TrainingAdminAiConversationPatchSerializer(serializers.Serializer):
    governance_status = serializers.ChoiceField(
        choices=TrainingAiConversation.GovernanceStatus.choices,
        required=False,
    )
    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    resolution_note = serializers.CharField(required=False, allow_blank=True, max_length=255)


class TrainingAdminAiRebuildIndexSerializer(serializers.Serializer):
    course_id = serializers.IntegerField(required=False, allow_null=True)
    content_slug = serializers.SlugField(required=False, allow_blank=True)

    def validate_course_id(self, value):
        if value is None:
            return value
        if not OnlineCourse.objects.filter(id=value).exists():
            raise serializers.ValidationError("Course was not found.")
        return value
