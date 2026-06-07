from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.online.models import OnlineCourse
from apps.training.models import (
    TrainingAiConversation,
    TrainingAiMessage,
    TrainingAiQuizAttempt,
    TrainingAssetClass,
    TrainingAudience,
    TrainingContentCrossReference,
    TrainingContentItem,
    TrainingCourseRoleAssignment,
    TrainingGradebookEntry,
    TrainingGraderJob,
    TrainingLabSubmission,
    TrainingNotebookLabHint,
    TrainingNotebookLabProfile,
    TrainingTopic,
)
from apps.training.services.notebook_assignments import (
    build_student_lab_summary,
    effective_assignment_code,
)

User = get_user_model()


class TrainingAssetClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingAssetClass
        fields = ("id", "slug", "name", "description")


class TrainingTopicSerializer(serializers.ModelSerializer):
    parent_slug = serializers.CharField(source="parent.slug", read_only=True)

    class Meta:
        model = TrainingTopic
        fields = ("id", "slug", "name", "description", "parent_slug")


class TrainingAudienceSerializer(serializers.ModelSerializer):
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
        )


class TrainingCourseSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    title_de = serializers.CharField()
    title_en = serializers.CharField()


class TrainingNotebookLabProfileSerializer(serializers.ModelSerializer):
    assignmentCode = serializers.SerializerMethodField()

    def get_assignmentCode(self, obj: TrainingNotebookLabProfile) -> str:
        return effective_assignment_code(obj)

    class Meta:
        model = TrainingNotebookLabProfile
        fields = (
            "assignmentCode",
            "runtime_backend",
            "grader_backend",
            "runtime_image",
            "notebook_path",
            "launch_path",
            "pass_threshold_percent",
            "max_attempts",
            "allow_gpu",
            "allow_network",
            "max_session_minutes",
            "is_active",
        )


class TrainingNotebookLabHintSerializer(serializers.ModelSerializer):
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


class TrainingContentReferenceSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(source="to_item.slug", read_only=True)
    name = serializers.CharField(source="to_item.name", read_only=True)
    content_kind = serializers.CharField(source="to_item.content_kind", read_only=True)

    class Meta:
        model = TrainingContentCrossReference
        fields = ("relation_type", "slug", "name", "content_kind", "note")


class TrainingContentListSerializer(serializers.ModelSerializer):
    asset_classes = TrainingAssetClassSerializer(many=True, read_only=True)
    topics = TrainingTopicSerializer(many=True, read_only=True)
    course = TrainingCourseSummarySerializer(read_only=True)
    lab = serializers.SerializerMethodField()

    def get_lab(self, obj: TrainingContentItem):
        try:
            lab_profile = obj.lab_profile
        except TrainingNotebookLabProfile.DoesNotExist:
            return None
        return TrainingNotebookLabProfileSerializer(lab_profile).data

    class Meta:
        model = TrainingContentItem
        fields = (
            "id",
            "slug",
            "name",
            "description",
            "content_kind",
            "access_scope",
            "difficulty",
            "version_label",
            "estimated_minutes",
            "is_repeatable_on_demand",
            "supports_inline_lab",
            "source_url",
            "published_at",
            "course",
            "asset_classes",
            "topics",
            "lab",
        )


class TrainingContentDetailSerializer(TrainingContentListSerializer):
    body_markdown = serializers.CharField(read_only=True)
    cross_references = TrainingContentReferenceSerializer(source="outgoing_references", many=True, read_only=True)
    labSummary = serializers.SerializerMethodField()

    class Meta(TrainingContentListSerializer.Meta):
        fields = TrainingContentListSerializer.Meta.fields + (
            "body_markdown",
            "cross_references",
            "labSummary",
        )

    def get_labSummary(self, obj: TrainingContentItem):
        request = self.context.get("request")
        user = self.context.get("user") or getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return None
        return build_student_lab_summary(content_item=obj, user=user)


class TrainingDirectusTaxonomySerializer(serializers.Serializer):
    slug = serializers.SlugField()
    name = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")


class TrainingDirectusCrossReferenceSerializer(serializers.Serializer):
    slug = serializers.SlugField()
    relationType = serializers.ChoiceField(
        choices=TrainingContentCrossReference.RelationType.choices,
        required=False,
        default=TrainingContentCrossReference.RelationType.RELATED,
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class TrainingDirectusSyncSerializer(serializers.Serializer):
    operation = serializers.ChoiceField(choices=("upsert", "delete"), required=False, default="upsert")
    externalId = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")
    slug = serializers.SlugField()
    name = serializers.CharField(required=False, allow_blank=True, max_length=220, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    bodyMarkdown = serializers.CharField(required=False, allow_blank=True, max_length=200_000, default="")
    contentKind = serializers.ChoiceField(
        choices=TrainingContentItem.ContentKind.choices,
        required=False,
        default=TrainingContentItem.ContentKind.ARTICLE,
    )
    status = serializers.ChoiceField(
        choices=TrainingContentItem.Status.choices,
        required=False,
        default=TrainingContentItem.Status.PUBLISHED,
    )
    accessScope = serializers.ChoiceField(
        choices=TrainingContentItem.AccessScope.choices,
        required=False,
        default=TrainingContentItem.AccessScope.ENTITLED,
    )
    difficulty = serializers.ChoiceField(
        choices=TrainingContentItem.Difficulty.choices,
        required=False,
        default=TrainingContentItem.Difficulty.INTERMEDIATE,
    )
    audienceMatchMode = serializers.ChoiceField(
        choices=TrainingContentItem.AudienceMatchMode.choices,
        required=False,
        default=TrainingContentItem.AudienceMatchMode.ANY,
    )
    courseSlug = serializers.SlugField(required=False, allow_blank=True, default="")
    ownerEmail = serializers.EmailField(required=False, allow_blank=True, default="")
    sourceUrl = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    searchKeywords = serializers.CharField(required=False, allow_blank=True, max_length=400, default="")
    versionLabel = serializers.CharField(required=False, allow_blank=True, max_length=40, default="")
    estimatedMinutes = serializers.IntegerField(required=False, min_value=0, max_value=1440, default=0)
    isRepeatableOnDemand = serializers.BooleanField(required=False, default=True)
    supportsInlineLab = serializers.BooleanField(required=False, default=False)
    publishedAt = serializers.DateTimeField(required=False, allow_null=True)
    assetClasses = serializers.JSONField(required=False)
    topics = serializers.JSONField(required=False)
    audienceSlugs = serializers.ListField(
        child=serializers.SlugField(),
        required=False,
        allow_empty=True,
        max_length=32,
    )
    crossReferences = TrainingDirectusCrossReferenceSerializer(many=True, required=False)

    def validate(self, attrs):
        if attrs.get("operation") == "delete":
            if not str(attrs.get("externalId") or "").strip():
                raise serializers.ValidationError({"externalId": "This field is required for delete operations."})
        else:
            if not str(attrs.get("name") or "").strip():
                raise serializers.ValidationError({"name": "This field is required for upsert operations."})
        if len(attrs.get("crossReferences") or []) > 32:
            raise serializers.ValidationError({"crossReferences": "No more than 32 cross references are allowed."})
        return attrs

    def validate_courseSlug(self, value):
        if not value:
            return value
        if not OnlineCourse.objects.filter(slug=value).exists():
            raise serializers.ValidationError("Referenced course was not found.")
        return value

    def validate_ownerEmail(self, value):
        if not value:
            return value
        if not User.objects.filter(email__iexact=value, is_active=True).exists():
            raise serializers.ValidationError("Referenced owner email was not found.")
        return value

    def validate_assetClasses(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("assetClasses must be a list.")
        if len(value) > 32:
            raise serializers.ValidationError("No more than 32 asset classes are allowed.")
        return value

    def validate_topics(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("topics must be a list.")
        if len(value) > 32:
            raise serializers.ValidationError("No more than 32 topics are allowed.")
        return value


class TrainingDirectusSyncResponseSerializer(serializers.Serializer):
    action = serializers.CharField()
    contentId = serializers.IntegerField(allow_null=True)
    slug = serializers.CharField()
    status = serializers.CharField()
    indexAction = serializers.CharField()
    indexedChunks = serializers.IntegerField()
    warnings = serializers.ListField(child=serializers.CharField(), allow_empty=True)


class TrainingCourseRoleAssignmentSerializer(serializers.ModelSerializer):
    course = TrainingCourseSummarySerializer(read_only=True)

    class Meta:
        model = TrainingCourseRoleAssignment
        fields = ("course", "role", "is_primary", "response_sla_hours")


class TrainingLabSubmissionSerializer(serializers.ModelSerializer):
    content = TrainingCourseSummarySerializer(source="content_item.course", read_only=True)
    contentSlug = serializers.CharField(source="content_item.slug", read_only=True)
    contentName = serializers.CharField(source="content_item.name", read_only=True)
    submissionMode = serializers.CharField(source="submission_mode", read_only=True)
    hasResponseText = serializers.SerializerMethodField()
    responseTextPreview = serializers.SerializerMethodField()
    graderStatus = serializers.CharField(source="grader_job.status", read_only=True, default="")
    hasNotebookArtifact = serializers.BooleanField(source="has_notebook_artifact", read_only=True)
    notebookArtifactFilename = serializers.CharField(source="notebook_artifact_filename", read_only=True)
    feedbackReportUrl = serializers.SerializerMethodField()
    jsonReportUrl = serializers.SerializerMethodField()

    def _build_artifact_url(self, obj: TrainingLabSubmission, artifact_kind: str) -> str | None:
        request = self.context.get("request")
        if request is None:
            return None
        if not obj.artifacts.filter(artifact_kind=artifact_kind).exists():
            return None
        path = f"/api/training/labs/{obj.content_item.slug}/submissions/{obj.public_id}/artifacts/{artifact_kind}/"
        return request.build_absolute_uri(path)

    def get_feedbackReportUrl(self, obj: TrainingLabSubmission) -> str | None:
        return self._build_artifact_url(obj, "feedback_html")

    def get_jsonReportUrl(self, obj: TrainingLabSubmission) -> str | None:
        return self._build_artifact_url(obj, "json_report")

    def get_hasResponseText(self, obj: TrainingLabSubmission) -> bool:
        return bool(str(obj.response_text or "").strip())

    def get_responseTextPreview(self, obj: TrainingLabSubmission) -> str:
        normalized = str(obj.response_text or "").strip()
        if not normalized:
            return ""
        preview = normalized[:240].strip()
        return preview + ("..." if len(normalized) > 240 else "")

    class Meta:
        model = TrainingLabSubmission
        fields = (
            "public_id",
            "attempt_number",
            "status",
            "submissionMode",
            "grader_backend",
            "graderStatus",
            "notebook_path",
            "hasNotebookArtifact",
            "notebookArtifactFilename",
            "hasResponseText",
            "responseTextPreview",
            "feedbackReportUrl",
            "jsonReportUrl",
            "feedback_markdown",
            "feedback_payload",
            "max_score",
            "score",
            "passed",
            "submitted_at",
            "graded_at",
            "created_at",
            "updated_at",
            "content",
            "contentSlug",
            "contentName",
        )


class TrainingGradebookEntrySerializer(serializers.ModelSerializer):
    content = TrainingContentListSerializer(source="content_item", read_only=True)
    latestSubmission = TrainingLabSubmissionSerializer(source="latest_submission", read_only=True)
    bestSubmissionId = serializers.UUIDField(source="best_submission.public_id", read_only=True)

    class Meta:
        model = TrainingGradebookEntry
        fields = (
            "content",
            "attempts_count",
            "latest_score",
            "best_score",
            "max_score",
            "passed",
            "completed_at",
            "updated_at",
            "latestSubmission",
            "bestSubmissionId",
        )


class TrainingLabSubmissionCreateSerializer(serializers.Serializer):
    notebook = serializers.FileField(required=False)
    answerText = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    client_checksum = serializers.CharField(required=False, allow_blank=True, max_length=128, default="")

    def validate(self, attrs):
        notebook = attrs.get("notebook")
        answer_text = str(attrs.get("answerText") or "").strip()
        if notebook is None and not answer_text:
            raise serializers.ValidationError("Upload a notebook or provide a text answer.")
        attrs["answerText"] = answer_text
        return attrs


class TrainingGraderWebhookResultSerializer(serializers.Serializer):
    submissionId = serializers.UUIDField()
    score = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True)
    maxScore = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True)
    passed = serializers.BooleanField(required=False, allow_null=True)
    feedbackMarkdown = serializers.CharField(required=False, allow_blank=True, default="")
    feedbackPayload = serializers.JSONField(required=False)
    artifacts = serializers.ListField(child=serializers.JSONField(), required=False, allow_empty=True)


class TrainingGraderJobSerializer(serializers.ModelSerializer):
    submission = TrainingLabSubmissionSerializer(read_only=True)

    class Meta:
        model = TrainingGraderJob
        fields = (
            "id",
            "submission",
            "backend",
            "status",
            "priority",
            "attempts_count",
            "available_at",
            "locked_at",
            "finished_at",
            "worker_name",
            "error_message",
            "result_payload",
        )


class TrainingAiConversationSerializer(serializers.ModelSerializer):
    contentSlug = serializers.CharField(source="content_item.slug", read_only=True)
    contentName = serializers.CharField(source="content_item.name", read_only=True)
    publicId = serializers.UUIDField(source="public_id", read_only=True)
    lastActivityAt = serializers.DateTimeField(source="last_activity_at", read_only=True)

    class Meta:
        model = TrainingAiConversation
        fields = (
            "publicId",
            "title",
            "status",
            "contentSlug",
            "contentName",
            "lastActivityAt",
        )


class TrainingAiMessageSerializer(serializers.ModelSerializer):
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    promptType = serializers.CharField(source="prompt_type", read_only=True)
    resolutionStatus = serializers.CharField(source="resolution_status", read_only=True)

    class Meta:
        model = TrainingAiMessage
        fields = (
            "id",
            "role",
            "promptType",
            "body",
            "payload",
            "citations",
            "resolutionStatus",
            "createdAt",
        )


class TrainingAiAskSerializer(serializers.Serializer):
    contentSlug = serializers.SlugField()
    question = serializers.CharField(max_length=5000)
    promptType = serializers.ChoiceField(
        choices=TrainingAiMessage.PromptType.choices,
        required=False,
        default=TrainingAiMessage.PromptType.ASK,
    )
    conversationId = serializers.UUIDField(required=False)


class TrainingAiConversationResponseSerializer(serializers.Serializer):
    conversation = TrainingAiConversationSerializer(allow_null=True)
    messages = TrainingAiMessageSerializer(many=True)


class TrainingAiQuizGenerateSerializer(serializers.Serializer):
    contentSlug = serializers.SlugField()
    conversationId = serializers.UUIDField(required=False)
    questionCount = serializers.IntegerField(required=False, min_value=3, max_value=5, default=4)


class TrainingAiQuizAnswerSerializer(serializers.Serializer):
    questionId = serializers.CharField(max_length=40)
    selectedOptionId = serializers.CharField(max_length=20, allow_blank=True, default="")


class TrainingAiQuizSubmitSerializer(serializers.Serializer):
    answers = TrainingAiQuizAnswerSerializer(many=True)


class TrainingAiQuizAttemptSerializer(serializers.ModelSerializer):
    publicId = serializers.UUIDField(source="public_id", read_only=True)
    contentSlug = serializers.CharField(source="content_item.slug", read_only=True)
    contentName = serializers.CharField(source="content_item.name", read_only=True)
    maxScore = serializers.IntegerField(source="max_score", read_only=True)
    correctAnswersCount = serializers.IntegerField(source="correct_answers_count", read_only=True)
    submittedAt = serializers.DateTimeField(source="submitted_at", read_only=True)
    questions = serializers.SerializerMethodField()

    class Meta:
        model = TrainingAiQuizAttempt
        fields = (
            "publicId",
            "status",
            "title",
            "contentSlug",
            "contentName",
            "score",
            "maxScore",
            "correctAnswersCount",
            "submittedAt",
            "questions",
        )

    def get_questions(self, obj: TrainingAiQuizAttempt):
        raw_questions = list((obj.quiz_payload or {}).get("questions") or [])
        scored_by_question = {
            str(item.get("questionId") or "").strip(): item
            for item in (obj.submitted_answers or [])
        }
        results = []
        for raw_question in raw_questions:
            question_id = str(raw_question.get("questionId") or "").strip()
            payload = {
                "questionId": question_id,
                "prompt": str(raw_question.get("prompt") or "").strip(),
                "options": raw_question.get("options") or [],
                "explanation": str(raw_question.get("explanation") or "").strip(),
            }
            if obj.status == TrainingAiQuizAttempt.Status.COMPLETED:
                scored = scored_by_question.get(question_id, {})
                payload.update(
                    {
                        "selectedOptionId": str(scored.get("selectedOptionId") or "").strip(),
                        "correctOptionId": str(scored.get("correctOptionId") or "").strip(),
                        "isCorrect": bool(scored.get("isCorrect")),
                    }
                )
            results.append(payload)
        return results
