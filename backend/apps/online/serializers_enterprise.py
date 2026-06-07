from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import serializers

from apps.online.models import (
    OnlineCatalogAttributeDefinition,
    OnlineCatalogAttributeValue,
    OnlineExternalCatalogProvider,
    OnlineInstructorProfile,
    OnlineKnowledgeDocument,
    OnlineKnowledgeSource,
    OnlineLearningProgram,
    OnlineLearningProgramCourse,
    OnlineStudentProfile,
    OnlineStudentProgramAssignment,
)
from apps.online.services.catalog_registry import resolve_catalog_content_type


class OnlineCatalogSearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True)
    confidentialityLevel = serializers.ChoiceField(choices=(), required=False)
    providerType = serializers.ChoiceField(choices=(), required=False)
    courseType = serializers.ChoiceField(choices=(), required=False)
    difficultyLevel = serializers.ChoiceField(choices=(), required=False)
    knowledgeDomain = serializers.CharField(required=False, allow_blank=True)
    ratingMin = serializers.FloatField(required=False, min_value=0.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.online.models import OnlineCourse

        self.fields["confidentialityLevel"].choices = OnlineCourse.CONFIDENTIALITY_CHOICES
        self.fields["providerType"].choices = OnlineCourse.PROVIDER_CHOICES
        self.fields["courseType"].choices = OnlineCourse.COURSE_TYPE_CHOICES
        self.fields["difficultyLevel"].choices = OnlineCourse.DIFFICULTY_CHOICES


class OnlineCatalogAttributeDefinitionSerializer(serializers.ModelSerializer):
    entityType = serializers.CharField(source="entity_type")
    helpText = serializers.CharField(source="help_text")
    dataType = serializers.CharField(source="data_type")
    defaultValue = serializers.JSONField(source="default_value")
    isRequired = serializers.BooleanField(source="is_required")
    isFilterable = serializers.BooleanField(source="is_filterable")
    isSearchable = serializers.BooleanField(source="is_searchable")
    isActive = serializers.BooleanField(source="is_active")
    sortOrder = serializers.IntegerField(source="sort_order")
    valuesCount = serializers.SerializerMethodField()

    class Meta:
        model = OnlineCatalogAttributeDefinition
        fields = (
            "id",
            "slug",
            "entityType",
            "label",
            "helpText",
            "dataType",
            "options",
            "defaultValue",
            "isRequired",
            "isFilterable",
            "isSearchable",
            "isActive",
            "sortOrder",
            "valuesCount",
        )

    def get_valuesCount(self, obj: OnlineCatalogAttributeDefinition) -> int:
        return obj.values.count()


class OnlineCatalogAttributeDefinitionUpsertSerializer(serializers.ModelSerializer):
    entityType = serializers.ChoiceField(source="entity_type", choices=OnlineCatalogAttributeDefinition.ENTITY_CHOICES)
    helpText = serializers.CharField(source="help_text", required=False, allow_blank=True)
    dataType = serializers.ChoiceField(source="data_type", choices=OnlineCatalogAttributeDefinition.DATA_TYPE_CHOICES)
    defaultValue = serializers.JSONField(source="default_value", required=False)
    isRequired = serializers.BooleanField(source="is_required", required=False)
    isFilterable = serializers.BooleanField(source="is_filterable", required=False)
    isSearchable = serializers.BooleanField(source="is_searchable", required=False)
    isActive = serializers.BooleanField(source="is_active", required=False)
    sortOrder = serializers.IntegerField(source="sort_order", required=False)

    class Meta:
        model = OnlineCatalogAttributeDefinition
        fields = (
            "slug",
            "entityType",
            "label",
            "helpText",
            "dataType",
            "options",
            "defaultValue",
            "isRequired",
            "isFilterable",
            "isSearchable",
            "isActive",
            "sortOrder",
        )


class OnlineCatalogAttributeValueSerializer(serializers.ModelSerializer):
    definitionId = serializers.IntegerField(source="definition_id")
    entityType = serializers.CharField(source="definition.entity_type")
    objectId = serializers.IntegerField(source="object_id")
    valueJson = serializers.JSONField(source="value_json")

    class Meta:
        model = OnlineCatalogAttributeValue
        fields = ("id", "definitionId", "entityType", "objectId", "valueJson", "updated_at")


class OnlineCatalogAttributeValueUpsertSerializer(serializers.Serializer):
    definitionId = serializers.IntegerField(min_value=1)
    entityType = serializers.ChoiceField(choices=OnlineCatalogAttributeDefinition.ENTITY_CHOICES)
    objectId = serializers.IntegerField(min_value=1)
    valueJson = serializers.JSONField(required=False)

    def validate(self, attrs):
        definition = get_object_or_404(OnlineCatalogAttributeDefinition, id=attrs["definitionId"])
        if definition.entity_type != attrs["entityType"]:
            raise serializers.ValidationError({"entityType": "Entity type does not match the selected definition."})
        content_type = resolve_catalog_content_type(attrs["entityType"])
        model_class = content_type.model_class()
        if model_class is None or not model_class.objects.filter(id=attrs["objectId"]).exists():
            raise serializers.ValidationError({"objectId": "Target object does not exist."})
        attrs["definition"] = definition
        attrs["content_type"] = content_type
        return attrs


class OnlineStudentProfileAdminSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name")
    lastName = serializers.CharField(source="last_name")
    employeeId = serializers.CharField(source="employee_id")
    teamName = serializers.CharField(source="team_name")
    officeLocation = serializers.CharField(source="office_location")
    jobTitle = serializers.CharField(source="job_title")
    managerName = serializers.CharField(source="manager_name")
    preferredLanguage = serializers.CharField(source="preferred_language")
    employmentStatus = serializers.CharField(source="employment_status")
    hiredAt = serializers.DateField(source="hired_at", allow_null=True)
    customFields = serializers.JSONField(source="custom_fields")
    email = serializers.EmailField(source="user.email", read_only=True)
    activeEnrollmentsCount = serializers.SerializerMethodField()

    class Meta:
        model = OnlineStudentProfile
        fields = (
            "id",
            "email",
            "firstName",
            "lastName",
            "employeeId",
            "department",
            "teamName",
            "officeLocation",
            "jobTitle",
            "managerName",
            "phone",
            "preferredLanguage",
            "employmentStatus",
            "hiredAt",
            "customFields",
            "activeEnrollmentsCount",
        )

    def get_activeEnrollmentsCount(self, obj: OnlineStudentProfile) -> int:
        return obj.enrollments.filter(status__in=("trial", "active")).count()


class OnlineStudentProfileAdminUpsertSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name", required=False)
    lastName = serializers.CharField(source="last_name", required=False)
    employeeId = serializers.CharField(source="employee_id", required=False, allow_blank=True)
    teamName = serializers.CharField(source="team_name", required=False, allow_blank=True)
    officeLocation = serializers.CharField(source="office_location", required=False, allow_blank=True)
    jobTitle = serializers.CharField(source="job_title", required=False, allow_blank=True)
    managerName = serializers.CharField(source="manager_name", required=False, allow_blank=True)
    preferredLanguage = serializers.CharField(source="preferred_language", required=False)
    employmentStatus = serializers.CharField(source="employment_status", required=False)
    hiredAt = serializers.DateField(source="hired_at", required=False, allow_null=True)
    customFields = serializers.JSONField(source="custom_fields", required=False)

    class Meta:
        model = OnlineStudentProfile
        fields = (
            "firstName",
            "lastName",
            "employeeId",
            "department",
            "teamName",
            "officeLocation",
            "jobTitle",
            "managerName",
            "phone",
            "preferredLanguage",
            "employmentStatus",
            "hiredAt",
            "customFields",
        )


class OnlineInstructorProfileSerializer(serializers.ModelSerializer):
    teacherId = serializers.IntegerField(source="teacher_id")
    fullName = serializers.SerializerMethodField()
    schoolEmail = serializers.EmailField(source="teacher.Schule_Email", read_only=True)
    jobTitle = serializers.CharField(source="job_title")
    expertiseAreas = serializers.JSONField(source="expertise_areas")
    spokenLanguages = serializers.JSONField(source="spoken_languages")
    canAuthor = serializers.BooleanField(source="can_author")
    canReview = serializers.BooleanField(source="can_review")
    canPublish = serializers.BooleanField(source="can_publish")
    canGenerateWithAi = serializers.BooleanField(source="can_generate_with_ai")
    canManageAssessments = serializers.BooleanField(source="can_manage_assessments")
    customFields = serializers.JSONField(source="custom_fields")

    class Meta:
        model = OnlineInstructorProfile
        fields = (
            "id",
            "teacherId",
            "fullName",
            "schoolEmail",
            "department",
            "jobTitle",
            "bio",
            "expertiseAreas",
            "spokenLanguages",
            "canAuthor",
            "canReview",
            "canPublish",
            "canGenerateWithAi",
            "canManageAssessments",
            "customFields",
        )

    def get_fullName(self, obj: OnlineInstructorProfile) -> str:
        return f"{obj.teacher.Vorname} {obj.teacher.Nachname}".strip()


class OnlineInstructorProfileUpsertSerializer(serializers.ModelSerializer):
    jobTitle = serializers.CharField(source="job_title", required=False, allow_blank=True)
    expertiseAreas = serializers.JSONField(source="expertise_areas", required=False)
    spokenLanguages = serializers.JSONField(source="spoken_languages", required=False)
    canAuthor = serializers.BooleanField(source="can_author", required=False)
    canReview = serializers.BooleanField(source="can_review", required=False)
    canPublish = serializers.BooleanField(source="can_publish", required=False)
    canGenerateWithAi = serializers.BooleanField(source="can_generate_with_ai", required=False)
    canManageAssessments = serializers.BooleanField(source="can_manage_assessments", required=False)
    customFields = serializers.JSONField(source="custom_fields", required=False)

    class Meta:
        model = OnlineInstructorProfile
        fields = (
            "department",
            "jobTitle",
            "bio",
            "expertiseAreas",
            "spokenLanguages",
            "canAuthor",
            "canReview",
            "canPublish",
            "canGenerateWithAi",
            "canManageAssessments",
            "customFields",
        )


class OnlineExternalCatalogProviderSerializer(serializers.ModelSerializer):
    displayName = serializers.CharField(source="display_name")
    providerType = serializers.CharField(source="provider_type")
    importMode = serializers.CharField(source="import_mode")
    baseUrl = serializers.CharField(source="base_url")
    apiBaseUrl = serializers.CharField(source="api_base_url")
    metadataSchema = serializers.JSONField(source="metadata_schema")
    isEnabled = serializers.BooleanField(source="is_enabled")
    syncStatus = serializers.CharField(source="sync_status")
    verificationMessage = serializers.CharField(source="verification_message")
    lastSyncAt = serializers.DateTimeField(source="last_sync_at", allow_null=True)

    class Meta:
        model = OnlineExternalCatalogProvider
        fields = (
            "id",
            "slug",
            "displayName",
            "providerType",
            "importMode",
            "baseUrl",
            "apiBaseUrl",
            "metadataSchema",
            "isEnabled",
            "syncStatus",
            "verificationMessage",
            "lastSyncAt",
        )


class OnlineExternalCatalogProviderUpsertSerializer(serializers.ModelSerializer):
    displayName = serializers.CharField(source="display_name")
    providerType = serializers.ChoiceField(source="provider_type", choices=OnlineExternalCatalogProvider.TYPE_CHOICES)
    importMode = serializers.ChoiceField(source="import_mode", choices=OnlineExternalCatalogProvider.IMPORT_CHOICES)
    baseUrl = serializers.CharField(source="base_url", required=False, allow_blank=True)
    apiBaseUrl = serializers.CharField(source="api_base_url", required=False, allow_blank=True)
    metadataSchema = serializers.JSONField(source="metadata_schema", required=False)
    isEnabled = serializers.BooleanField(source="is_enabled", required=False)
    syncStatus = serializers.ChoiceField(source="sync_status", choices=OnlineExternalCatalogProvider.STATUS_CHOICES, required=False)
    verificationMessage = serializers.CharField(source="verification_message", required=False, allow_blank=True)

    class Meta:
        model = OnlineExternalCatalogProvider
        fields = (
            "slug",
            "displayName",
            "providerType",
            "importMode",
            "baseUrl",
            "apiBaseUrl",
            "metadataSchema",
            "isEnabled",
            "syncStatus",
            "verificationMessage",
        )


class OnlineLearningProgramCourseItemSerializer(serializers.ModelSerializer):
    courseId = serializers.IntegerField(source="course_id")
    courseTitle = serializers.CharField(source="course.title_en", read_only=True)
    sortOrder = serializers.IntegerField(source="sort_order")
    isRequired = serializers.BooleanField(source="is_required")
    unlockRule = serializers.CharField(source="unlock_rule")
    minCompletionPercent = serializers.IntegerField(source="min_completion_percent")

    class Meta:
        model = OnlineLearningProgramCourse
        fields = (
            "id",
            "courseId",
            "courseTitle",
            "sortOrder",
            "isRequired",
            "unlockRule",
            "minCompletionPercent",
            "note",
        )


class OnlineLearningProgramCourseItemUpsertSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    courseId = serializers.IntegerField(min_value=1)
    sortOrder = serializers.IntegerField(required=False)
    isRequired = serializers.BooleanField(required=False)
    unlockRule = serializers.ChoiceField(choices=OnlineLearningProgramCourse.UNLOCK_CHOICES, required=False)
    minCompletionPercent = serializers.IntegerField(required=False, min_value=0, max_value=100)
    note = serializers.CharField(required=False, allow_blank=True)


class OnlineLearningProgramSerializer(serializers.ModelSerializer):
    targetAudience = serializers.CharField(source="target_audience")
    assignmentMode = serializers.CharField(source="assignment_mode")
    recommendationPrompt = serializers.CharField(source="recommendation_prompt")
    isActive = serializers.BooleanField(source="is_active")
    createdByEmail = serializers.EmailField(source="created_by.email", read_only=True, allow_null=True)
    programCourses = OnlineLearningProgramCourseItemSerializer(source="program_courses", many=True, read_only=True)
    assignmentsCount = serializers.SerializerMethodField()

    class Meta:
        model = OnlineLearningProgram
        fields = (
            "id",
            "slug",
            "title",
            "description",
            "targetAudience",
            "assignmentMode",
            "recommendationPrompt",
            "isActive",
            "createdByEmail",
            "programCourses",
            "assignmentsCount",
        )

    def get_assignmentsCount(self, obj: OnlineLearningProgram) -> int:
        return obj.student_assignments.count()


class OnlineLearningProgramUpsertSerializer(serializers.ModelSerializer):
    targetAudience = serializers.CharField(source="target_audience", required=False, allow_blank=True)
    assignmentMode = serializers.ChoiceField(source="assignment_mode", choices=OnlineLearningProgram.ASSIGNMENT_CHOICES)
    recommendationPrompt = serializers.CharField(source="recommendation_prompt", required=False, allow_blank=True)
    isActive = serializers.BooleanField(source="is_active", required=False)
    programCourses = OnlineLearningProgramCourseItemUpsertSerializer(many=True, required=False)

    class Meta:
        model = OnlineLearningProgram
        fields = (
            "slug",
            "title",
            "description",
            "targetAudience",
            "assignmentMode",
            "recommendationPrompt",
            "isActive",
            "programCourses",
        )


class OnlineStudentProgramAssignmentSerializer(serializers.ModelSerializer):
    profileId = serializers.IntegerField(source="profile_id")
    programId = serializers.IntegerField(source="program_id")
    programTitle = serializers.CharField(source="program.title", read_only=True)
    sourceLabel = serializers.CharField(source="get_source_display", read_only=True)
    statusLabel = serializers.CharField(source="get_status_display", read_only=True)
    aiReason = serializers.CharField(source="ai_reason")
    assignedByEmail = serializers.EmailField(source="assigned_by.email", read_only=True, allow_null=True)
    startedAt = serializers.DateTimeField(source="started_at")
    completedAt = serializers.DateTimeField(source="completed_at", allow_null=True)

    class Meta:
        model = OnlineStudentProgramAssignment
        fields = (
            "id",
            "profileId",
            "programId",
            "programTitle",
            "source",
            "sourceLabel",
            "status",
            "statusLabel",
            "aiReason",
            "assignedByEmail",
            "startedAt",
            "completedAt",
        )


class OnlineStudentProgramAssignmentUpsertSerializer(serializers.ModelSerializer):
    profileId = serializers.IntegerField(source="profile_id")
    programId = serializers.IntegerField(source="program_id")
    aiReason = serializers.CharField(source="ai_reason", required=False, allow_blank=True)
    completedAt = serializers.DateTimeField(source="completed_at", required=False, allow_null=True)

    class Meta:
        model = OnlineStudentProgramAssignment
        fields = ("profileId", "programId", "source", "status", "aiReason", "completedAt")


class OnlineKnowledgeSourceSerializer(serializers.ModelSerializer):
    sourceType = serializers.CharField(source="source_type")
    externalUrl = serializers.CharField(source="external_url")
    linkedCourseId = serializers.IntegerField(source="linked_course_id", allow_null=True)
    ownerEmail = serializers.EmailField(source="owner.email", read_only=True, allow_null=True)
    isActive = serializers.BooleanField(source="is_active")
    isIndexed = serializers.BooleanField(source="is_indexed")
    lastIngestedAt = serializers.DateTimeField(source="last_ingested_at", allow_null=True)
    metadataJson = serializers.JSONField(source="metadata_json")
    documentsCount = serializers.SerializerMethodField()

    class Meta:
        model = OnlineKnowledgeSource
        fields = (
            "id",
            "slug",
            "title",
            "description",
            "sourceType",
            "externalUrl",
            "ownerEmail",
            "linkedCourseId",
            "isActive",
            "isIndexed",
            "lastIngestedAt",
            "metadataJson",
            "documentsCount",
        )

    def get_documentsCount(self, obj: OnlineKnowledgeSource) -> int:
        return obj.documents.count()


class OnlineKnowledgeSourceUpsertSerializer(serializers.ModelSerializer):
    sourceType = serializers.ChoiceField(source="source_type", choices=OnlineKnowledgeSource.SOURCE_CHOICES)
    externalUrl = serializers.CharField(source="external_url", required=False, allow_blank=True)
    linkedCourseId = serializers.IntegerField(source="linked_course_id", required=False, allow_null=True)
    isActive = serializers.BooleanField(source="is_active", required=False)
    isIndexed = serializers.BooleanField(source="is_indexed", required=False)
    metadataJson = serializers.JSONField(source="metadata_json", required=False)

    class Meta:
        model = OnlineKnowledgeSource
        fields = (
            "slug",
            "title",
            "description",
            "sourceType",
            "externalUrl",
            "linkedCourseId",
            "isActive",
            "isIndexed",
            "metadataJson",
        )


class OnlineKnowledgeDocumentSerializer(serializers.ModelSerializer):
    sourceId = serializers.IntegerField(source="source_id")
    documentType = serializers.CharField(source="document_type")
    externalUrl = serializers.CharField(source="external_url")
    bodyMarkdown = serializers.CharField(source="body_markdown")
    transcriptText = serializers.CharField(source="transcript_text")
    chunkCount = serializers.IntegerField(source="chunk_count")
    isActive = serializers.BooleanField(source="is_active")
    indexedAt = serializers.DateTimeField(source="indexed_at", allow_null=True)
    metadataJson = serializers.JSONField(source="metadata_json")

    class Meta:
        model = OnlineKnowledgeDocument
        fields = (
            "id",
            "sourceId",
            "title",
            "description",
            "documentType",
            "language",
            "externalUrl",
            "bodyMarkdown",
            "transcriptText",
            "chunkCount",
            "isActive",
            "indexedAt",
            "metadataJson",
        )


class OnlineKnowledgeDocumentUpsertSerializer(serializers.ModelSerializer):
    sourceId = serializers.IntegerField(source="source_id")
    documentType = serializers.ChoiceField(source="document_type", choices=OnlineKnowledgeDocument.DOC_CHOICES)
    externalUrl = serializers.CharField(source="external_url", required=False, allow_blank=True)
    bodyMarkdown = serializers.CharField(source="body_markdown", required=False, allow_blank=True)
    transcriptText = serializers.CharField(source="transcript_text", required=False, allow_blank=True)
    chunkCount = serializers.IntegerField(source="chunk_count", required=False, min_value=0)
    isActive = serializers.BooleanField(source="is_active", required=False)
    metadataJson = serializers.JSONField(source="metadata_json", required=False)

    class Meta:
        model = OnlineKnowledgeDocument
        fields = (
            "sourceId",
            "title",
            "description",
            "documentType",
            "language",
            "externalUrl",
            "file_asset",
            "bodyMarkdown",
            "transcriptText",
            "chunkCount",
            "isActive",
            "metadataJson",
        )
