from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.utils.text import slugify
from rest_framework import serializers

from apps.online.models import (
    OnlineCourse,
    OnlineCourseContentLibraryItem,
    OnlineCohort,
    OnlineCourseLessonSectionItem,
    OnlineCourseModule,
    OnlineCourseTemplate,
)
from apps.online.services.access import online_access_policy_audience_ids_for_instance
from apps.online.services.course_structure import build_course_template_payload, build_course_builder_payload
from apps.online.services.governance import normalize_course_lifecycle_status
from apps.training.models import TrainingContentItem


class OnlineAdminCourseTemplateSerializer(serializers.ModelSerializer):
    defaultLessonsCount = serializers.IntegerField(source="default_lessons_count")
    lessons = serializers.SerializerMethodField()

    class Meta:
        model = OnlineCourseTemplate
        fields = (
            "id",
            "slug",
            "title",
            "description",
            "defaultLessonsCount",
            "lessons",
        )

    def get_lessons(self, obj: OnlineCourseTemplate):
        return build_course_template_payload(obj)["lessons"]


class OnlineAdminNotebookOptionSerializer(serializers.ModelSerializer):
    contentKind = serializers.CharField(source="content_kind")
    sourceUrl = serializers.CharField(source="source_url", allow_null=True)
    courseId = serializers.IntegerField(source="course_id", allow_null=True)
    courseSlug = serializers.CharField(source="course.slug", read_only=True, default="")

    class Meta:
        model = TrainingContentItem
        fields = (
            "id",
            "slug",
            "name",
            "contentKind",
            "description",
            "sourceUrl",
            "courseId",
            "courseSlug",
            "supports_inline_lab",
        )


class OnlineAdminCourseContentLibraryItemSerializer(serializers.ModelSerializer):
    sectionType = serializers.CharField(source="section_type")
    libraryGroup = serializers.CharField(source="library_group")
    assetType = serializers.CharField(source="asset_type")
    bodyMarkdown = serializers.CharField(source="body_markdown")
    externalUrl = serializers.CharField(source="external_url")
    fileUrl = serializers.SerializerMethodField()
    trainingContentId = serializers.IntegerField(source="training_content_id", allow_null=True)
    trainingContentSlug = serializers.CharField(source="training_content.slug", read_only=True, default="")
    trainingContentName = serializers.CharField(source="training_content.name", read_only=True, default="")
    sortOrder = serializers.IntegerField(source="sort_order")
    isActive = serializers.BooleanField(source="is_active")
    audienceIds = serializers.SerializerMethodField()

    class Meta:
        model = OnlineCourseContentLibraryItem
        fields = (
            "id",
            "sectionType",
            "title",
            "description",
            "libraryGroup",
            "assetType",
            "language",
            "bodyMarkdown",
            "externalUrl",
            "fileUrl",
            "trainingContentId",
            "trainingContentSlug",
            "trainingContentName",
            "audienceIds",
            "sortOrder",
            "isActive",
        )

    def get_fileUrl(self, obj: OnlineCourseContentLibraryItem) -> str:
        if not obj.file_asset:
            return ""
        url = f"/api/online/media/course-library/{obj.id}/file/"
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(url)
        return url

    def get_audienceIds(self, obj: OnlineCourseContentLibraryItem) -> list[int]:
        return online_access_policy_audience_ids_for_instance(obj)


class OnlineAdminCourseContentLibraryItemUpsertSerializer(serializers.ModelSerializer):
    sectionType = serializers.CharField(source="section_type")
    libraryGroup = serializers.CharField(source="library_group", required=False, allow_blank=True)
    assetType = serializers.CharField(source="asset_type")
    bodyMarkdown = serializers.CharField(source="body_markdown", required=False, allow_blank=True)
    externalUrl = serializers.CharField(source="external_url", required=False, allow_blank=True)
    file = serializers.FileField(source="file_asset", required=False, allow_null=True)
    trainingContentId = serializers.PrimaryKeyRelatedField(
        source="training_content",
        queryset=TrainingContentItem.objects.filter(content_kind=TrainingContentItem.ContentKind.NOTEBOOK),
        allow_null=True,
        required=False,
    )
    audienceIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        write_only=True,
    )
    sortOrder = serializers.IntegerField(source="sort_order", required=False)
    isActive = serializers.BooleanField(source="is_active", required=False)

    class Meta:
        model = OnlineCourseContentLibraryItem
        fields = (
            "sectionType",
            "title",
            "description",
            "libraryGroup",
            "assetType",
            "language",
            "bodyMarkdown",
            "externalUrl",
            "file",
            "trainingContentId",
            "audienceIds",
            "sortOrder",
            "isActive",
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        section_type = attrs.get("section_type", getattr(self.instance, "section_type", None))
        asset_type = attrs.get("asset_type", getattr(self.instance, "asset_type", None))
        body_markdown = attrs.get("body_markdown", getattr(self.instance, "body_markdown", ""))
        external_url = attrs.get("external_url", getattr(self.instance, "external_url", ""))
        file_asset = attrs.get("file_asset", getattr(self.instance, "file_asset", None))
        training_content = attrs.get("training_content", getattr(self.instance, "training_content", None))

        if section_type not in dict(OnlineCourseContentLibraryItem.SECTION_CHOICES):
            raise serializers.ValidationError({"sectionType": "Unknown section type."})
        if asset_type not in dict(OnlineCourseContentLibraryItem.ASSET_CHOICES):
            raise serializers.ValidationError({"assetType": "Unknown asset type."})

        if asset_type == OnlineCourseContentLibraryItem.ASSET_TEXT and not body_markdown.strip():
            raise serializers.ValidationError({"bodyMarkdown": "Text assets require markdown content."})
        if asset_type == OnlineCourseContentLibraryItem.ASSET_LINK and not (external_url.strip() or file_asset):
            raise serializers.ValidationError({"externalUrl": "Link assets require a URL or uploaded file."})
        if asset_type == OnlineCourseContentLibraryItem.ASSET_DOCUMENT and not (file_asset or external_url.strip()):
            raise serializers.ValidationError({"file": "Document assets require an uploaded file or URL."})
        if asset_type == OnlineCourseContentLibraryItem.ASSET_NOTEBOOK and training_content is None:
            raise serializers.ValidationError({"trainingContentId": "Notebook assets require a notebook content item."})
        return attrs


class OnlineAdminCourseBuilderSectionItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    sourceLibraryItemId = serializers.PrimaryKeyRelatedField(
        source="source_library_item",
        queryset=OnlineCourseContentLibraryItem.objects.filter(is_active=True),
        allow_null=True,
        required=False,
    )
    title = serializers.CharField(max_length=220, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    assetType = serializers.ChoiceField(
        choices=OnlineCourseContentLibraryItem.ASSET_CHOICES,
        source="asset_type",
        required=False,
    )
    activityType = serializers.ChoiceField(
        choices=OnlineCourseLessonSectionItem.ACTIVITY_CHOICES,
        source="activity_type",
        required=False,
    )
    language = serializers.ChoiceField(choices=OnlineCourse.LOCALE_CHOICES, required=False, default=OnlineCourse.LOCALE_EN)
    bodyMarkdown = serializers.CharField(source="body_markdown", required=False, allow_blank=True)
    structuredData = serializers.JSONField(source="structured_data", required=False)
    externalUrl = serializers.CharField(source="external_url", required=False, allow_blank=True)
    linkedTrainingContentId = serializers.PrimaryKeyRelatedField(
        source="linked_training_content",
        queryset=TrainingContentItem.objects.filter(content_kind=TrainingContentItem.ContentKind.NOTEBOOK),
        allow_null=True,
        required=False,
    )
    audienceIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    sortOrder = serializers.IntegerField(source="sort_order", required=False)
    isActive = serializers.BooleanField(source="is_active", required=False, default=True)

    def validate(self, attrs):
        source_library_item = attrs.get("source_library_item")
        asset_type = attrs.get("asset_type")
        body_markdown = attrs.get("body_markdown", "")
        external_url = attrs.get("external_url", "")
        linked_training_content = attrs.get("linked_training_content")

        if source_library_item is None:
            if not asset_type:
                raise serializers.ValidationError({"assetType": "Asset type is required for custom section items."})
            if asset_type == OnlineCourseContentLibraryItem.ASSET_TEXT and not body_markdown.strip():
                raise serializers.ValidationError({"bodyMarkdown": "Text items require markdown content."})
            activity_type = attrs.get("activity_type")
            if (
                asset_type == OnlineCourseContentLibraryItem.ASSET_LINK
                and not external_url.strip()
                and activity_type != OnlineCourseLessonSectionItem.ACTIVITY_VIDEO
            ):
                raise serializers.ValidationError({"externalUrl": "Link items require a URL."})
            if asset_type == OnlineCourseContentLibraryItem.ASSET_DOCUMENT and not external_url.strip():
                raise serializers.ValidationError(
                    {"externalUrl": "Custom document items require a document URL. Use the library uploader for files."}
                )
            if asset_type == OnlineCourseContentLibraryItem.ASSET_NOTEBOOK and linked_training_content is None:
                raise serializers.ValidationError({"linkedTrainingContentId": "Notebook items require a notebook link."})
        structured_data = attrs.get("structured_data")
        if structured_data is not None and not isinstance(structured_data, dict):
            raise serializers.ValidationError({"structuredData": "Structured data must be a JSON object."})
        return attrs


class OnlineAdminCourseBuilderSectionSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    sectionType = serializers.ChoiceField(choices=OnlineCourseContentLibraryItem.SECTION_CHOICES, source="section_type")
    title = serializers.CharField(max_length=180, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    sortOrder = serializers.IntegerField(source="sort_order", required=False)
    isActive = serializers.BooleanField(source="is_active", required=False, default=True)
    items = OnlineAdminCourseBuilderSectionItemSerializer(many=True, required=False)


class OnlineAdminCourseBuilderLessonSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    title = serializers.CharField(max_length=220)
    description = serializers.CharField(required=False, allow_blank=True)
    startsAt = serializers.DateTimeField(source="starts_at", required=False, allow_null=True)
    endsAt = serializers.DateTimeField(source="ends_at", required=False, allow_null=True)
    sortOrder = serializers.IntegerField(source="sort_order", required=False)
    isActive = serializers.BooleanField(source="is_active", required=False, default=True)
    sections = OnlineAdminCourseBuilderSectionSerializer(many=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        starts_at = attrs.get("starts_at")
        ends_at = attrs.get("ends_at")
        if starts_at and ends_at and ends_at < starts_at:
            raise serializers.ValidationError({"endsAt": "Lesson end must be after lesson start."})
        return attrs

    def validate_sections(self, value):
        section_types = [item["section_type"] for item in value]
        if not section_types:
            raise serializers.ValidationError("Each lesson must contain a main content section.")
        if len(section_types) != len(set(section_types)):
            raise serializers.ValidationError("Each lesson section type can only be used once.")
        if OnlineCourseContentLibraryItem.SECTION_MAIN not in section_types:
            raise serializers.ValidationError("Each lesson must contain a main content section.")
        return value


class OnlineAdminCourseBuilderModuleSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    title = serializers.CharField(max_length=220)
    description = serializers.CharField(required=False, allow_blank=True)
    moduleType = serializers.ChoiceField(choices=OnlineCourseModule.MODULE_TYPE_CHOICES, source="module_type", required=False)
    weekNumber = serializers.IntegerField(source="week_number", required=False, allow_null=True, min_value=1)
    startsAt = serializers.DateTimeField(source="starts_at", required=False, allow_null=True)
    endsAt = serializers.DateTimeField(source="ends_at", required=False, allow_null=True)
    sortOrder = serializers.IntegerField(source="sort_order", required=False)
    isActive = serializers.BooleanField(source="is_active", required=False, default=True)
    lessons = OnlineAdminCourseBuilderLessonSerializer(many=True, required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        starts_at = attrs.get("starts_at")
        ends_at = attrs.get("ends_at")
        if starts_at and ends_at and ends_at < starts_at:
            raise serializers.ValidationError({"endsAt": "Module end must be after module start."})
        return attrs

    def validate_lessons(self, value):
        if value is None:
            return []
        return value


class OnlineAdminCourseBuilderUpsertSerializer(serializers.Serializer):
    templateId = serializers.PrimaryKeyRelatedField(
        source="template",
        queryset=OnlineCourseTemplate.objects.filter(is_active=True),
        allow_null=True,
        required=False,
    )
    slug = serializers.SlugField(max_length=120, required=False, allow_blank=True)
    titleDe = serializers.CharField(source="title_de", max_length=220)
    titleEn = serializers.CharField(source="title_en", max_length=220)
    shortDescriptionDe = serializers.CharField(source="short_description_de")
    shortDescriptionEn = serializers.CharField(source="short_description_en")
    descriptionDe = serializers.CharField(source="description_de")
    descriptionEn = serializers.CharField(source="description_en")
    startsAt = serializers.DateTimeField(source="starts_at", required=False, allow_null=True)
    endsAt = serializers.DateTimeField(source="ends_at", required=False, allow_null=True)
    trialAvailable = serializers.BooleanField(source="trial_available", required=False, default=False)
    priceAmount = serializers.CharField(source="price_amount", required=False, default="0.00")
    currency = serializers.CharField(required=False, default="EUR", max_length=8)
    isSubscription = serializers.BooleanField(source="is_subscription", required=False, default=False)
    isPublished = serializers.BooleanField(source="is_published", required=False, default=True)
    lifecycleStatus = serializers.ChoiceField(
        source="lifecycle_status",
        choices=OnlineCourse.LIFECYCLE_CHOICES,
        required=False,
    )
    providerType = serializers.ChoiceField(source="provider_type", choices=OnlineCourse.PROVIDER_CHOICES, required=False)
    courseOrigin = serializers.ChoiceField(source="course_origin", choices=OnlineCourse.ORIGIN_CHOICES, required=False)
    courseType = serializers.ChoiceField(source="course_type", choices=OnlineCourse.COURSE_TYPE_CHOICES, required=False)
    deliveryModel = serializers.ChoiceField(source="delivery_model", choices=OnlineCourse.DELIVERY_CHOICES, required=False)
    difficultyLevel = serializers.ChoiceField(source="difficulty_level", choices=OnlineCourse.DIFFICULTY_CHOICES, required=False)
    confidentialityLevel = serializers.ChoiceField(
        source="confidentiality_level",
        choices=OnlineCourse.CONFIDENTIALITY_CHOICES,
        required=False,
    )
    knowledgeDomain = serializers.CharField(source="knowledge_domain", required=False, allow_blank=True, default="")
    targetAudience = serializers.CharField(source="target_audience", required=False, allow_blank=True, default="")
    estimatedDurationMinutes = serializers.IntegerField(source="estimated_duration_minutes", required=False, min_value=0)
    averageRating = serializers.DecimalField(source="average_rating", required=False, max_digits=4, decimal_places=2)
    ratingsCount = serializers.IntegerField(source="ratings_count", required=False, min_value=0)
    isMandatory = serializers.BooleanField(source="is_mandatory", required=False, default=False)
    isRecommended = serializers.BooleanField(source="is_recommended", required=False, default=True)
    providerCourseId = serializers.CharField(source="provider_course_id", required=False, allow_blank=True, default="")
    externalUrl = serializers.CharField(source="external_url", required=False, allow_blank=True, default="")
    tags = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    skills = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    metadataJson = serializers.JSONField(source="metadata_json", required=False)
    customFields = serializers.JSONField(source="custom_fields", required=False)
    requiredCompletionPercent = serializers.IntegerField(source="required_completion_percent", required=False, min_value=0, max_value=100)
    requiredAttendancePercent = serializers.IntegerField(source="required_attendance_percent", required=False, min_value=0, max_value=100)
    requiresAttestation = serializers.BooleanField(source="requires_attestation", required=False, default=True)
    heroImageUrl = serializers.CharField(source="hero_image_url", required=False, allow_blank=True)
    seoTitleDe = serializers.CharField(source="seo_title_de", required=False, allow_blank=True)
    seoTitleEn = serializers.CharField(source="seo_title_en", required=False, allow_blank=True)
    seoDescriptionDe = serializers.CharField(source="seo_description_de", required=False, allow_blank=True)
    seoDescriptionEn = serializers.CharField(source="seo_description_en", required=False, allow_blank=True)
    geoCity = serializers.CharField(source="geo_city", required=False, allow_blank=True, default="Berlin")
    geoCountry = serializers.CharField(source="geo_country", required=False, allow_blank=True, default="DE")
    audienceIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    instructorIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    workspaceIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    modules = OnlineAdminCourseBuilderModuleSerializer(many=True, required=False)
    lessons = OnlineAdminCourseBuilderLessonSerializer(many=True, required=False)

    def validate_slug(self, value: str) -> str:
        return value.strip().lower()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        slug = attrs.get("slug", "").strip().lower()
        instance: OnlineCourse | None = getattr(self, "instance", None)
        title_de = (attrs.get("title_de") or getattr(instance, "title_de", "")).strip()
        if not slug:
            slug = slugify(title_de)[:120]
        if not slug:
            raise serializers.ValidationError({"slug": "Slug is required."})
        attrs["slug"] = slug

        try:
            price_amount = Decimal(str(attrs.get("price_amount", "0.00")))
        except (InvalidOperation, TypeError):
            raise serializers.ValidationError({"priceAmount": "Price must be a valid decimal value."})
        if price_amount < 0:
            raise serializers.ValidationError({"priceAmount": "Price cannot be negative."})
        attrs["price_amount"] = price_amount
        attrs["lifecycle_status"] = normalize_course_lifecycle_status(
            lifecycle_status=attrs.get("lifecycle_status"),
            is_published=attrs.get("is_published"),
            current_status=getattr(instance, "lifecycle_status", None),
        )
        attrs["is_published"] = attrs["lifecycle_status"] == OnlineCourse.LIFECYCLE_PUBLISHED
        starts_at = attrs.get("starts_at")
        ends_at = attrs.get("ends_at")
        if starts_at and ends_at and ends_at < starts_at:
            raise serializers.ValidationError({"endsAt": "Course end must be after course start."})

        modules = attrs.get("modules")
        lessons = attrs.get("lessons")
        if not (self.partial and modules is None and lessons is None):
            if modules is None and lessons is None:
                raise serializers.ValidationError({"modules": "Provide modules or lessons for this course structure."})
            if modules is not None and len(modules) == 0:
                raise serializers.ValidationError({"modules": "At least one module is required."})
            if lessons is not None and len(lessons) == 0 and not modules:
                raise serializers.ValidationError({"lessons": "At least one lesson is required."})
            if modules is not None:
                modules_lessons_count = sum(len(module_data.get("lessons") or []) for module_data in modules)
                if modules_lessons_count < 1:
                    raise serializers.ValidationError(
                        {"modules": "At least one lesson is required across the module structure."}
                    )

        slug_qs = OnlineCourse.objects.filter(slug=slug)
        if instance is not None:
            slug_qs = slug_qs.exclude(id=instance.id)
        if slug_qs.exists():
            raise serializers.ValidationError({"slug": "A course with this slug already exists."})
        return attrs


class OnlineAdminCourseBuilderDetailSerializer(serializers.Serializer):
    def to_representation(self, instance: OnlineCourse):
        request = self.context.get("request")
        return build_course_builder_payload(instance, request=request)


class OnlineAdminCourseBuilderImportSerializer(serializers.Serializer):
    SOURCE_COURSERA_JSON = "coursera_json"
    SOURCE_GENERIC_JSON = "generic_json"
    SOURCE_CHOICES = (
        (SOURCE_COURSERA_JSON, "Coursera-like JSON"),
        (SOURCE_GENERIC_JSON, "Generic JSON"),
    )

    source = serializers.ChoiceField(choices=SOURCE_CHOICES, default=SOURCE_COURSERA_JSON)
    payload = serializers.JSONField()
    slug = serializers.SlugField(max_length=120, required=False, allow_blank=True)
    titleDe = serializers.CharField(max_length=220, required=False, allow_blank=True)
    titleEn = serializers.CharField(max_length=220, required=False, allow_blank=True)
    shortDescriptionDe = serializers.CharField(required=False, allow_blank=True)
    shortDescriptionEn = serializers.CharField(required=False, allow_blank=True)
    descriptionDe = serializers.CharField(required=False, allow_blank=True)
    descriptionEn = serializers.CharField(required=False, allow_blank=True)
    startsAt = serializers.DateTimeField(required=False, allow_null=True)
    endsAt = serializers.DateTimeField(required=False, allow_null=True)
    trialAvailable = serializers.BooleanField(required=False, default=False)
    priceAmount = serializers.CharField(required=False, default="0.00")
    currency = serializers.CharField(required=False, default="EUR", max_length=8)
    isSubscription = serializers.BooleanField(required=False, default=False)
    isPublished = serializers.BooleanField(required=False, default=True)
    lifecycleStatus = serializers.ChoiceField(choices=OnlineCourse.LIFECYCLE_CHOICES, required=False)
    providerType = serializers.ChoiceField(choices=OnlineCourse.PROVIDER_CHOICES, required=False)
    courseOrigin = serializers.ChoiceField(choices=OnlineCourse.ORIGIN_CHOICES, required=False)
    courseType = serializers.ChoiceField(choices=OnlineCourse.COURSE_TYPE_CHOICES, required=False)
    deliveryModel = serializers.ChoiceField(choices=OnlineCourse.DELIVERY_CHOICES, required=False)
    difficultyLevel = serializers.ChoiceField(choices=OnlineCourse.DIFFICULTY_CHOICES, required=False)
    confidentialityLevel = serializers.ChoiceField(choices=OnlineCourse.CONFIDENTIALITY_CHOICES, required=False)
    knowledgeDomain = serializers.CharField(required=False, allow_blank=True, default="")
    targetAudience = serializers.CharField(required=False, allow_blank=True, default="")
    estimatedDurationMinutes = serializers.IntegerField(required=False, min_value=0)
    averageRating = serializers.DecimalField(required=False, max_digits=4, decimal_places=2)
    ratingsCount = serializers.IntegerField(required=False, min_value=0)
    isMandatory = serializers.BooleanField(required=False, default=False)
    isRecommended = serializers.BooleanField(required=False, default=True)
    providerCourseId = serializers.CharField(required=False, allow_blank=True, default="")
    externalUrl = serializers.CharField(required=False, allow_blank=True, default="")
    tags = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    skills = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    metadataJson = serializers.JSONField(required=False)
    customFields = serializers.JSONField(required=False)
    requiredCompletionPercent = serializers.IntegerField(required=False, min_value=0, max_value=100)
    requiredAttendancePercent = serializers.IntegerField(required=False, min_value=0, max_value=100)
    requiresAttestation = serializers.BooleanField(required=False, default=True)
    heroImageUrl = serializers.CharField(required=False, allow_blank=True, default="")
    geoCity = serializers.CharField(required=False, allow_blank=True, default="Berlin")
    geoCountry = serializers.CharField(required=False, allow_blank=True, default="DE")
    audienceIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    instructorIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    workspaceIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        payload = attrs.get("payload")
        if not isinstance(payload, dict):
            raise serializers.ValidationError({"payload": "Payload must be a JSON object."})
        starts_at = attrs.get("startsAt")
        ends_at = attrs.get("endsAt")
        if starts_at and ends_at and ends_at < starts_at:
            raise serializers.ValidationError({"endsAt": "Course end must be after course start."})
        attrs["lifecycleStatus"] = normalize_course_lifecycle_status(
            lifecycle_status=attrs.get("lifecycleStatus"),
            is_published=attrs.get("isPublished"),
        )
        attrs["isPublished"] = attrs["lifecycleStatus"] == OnlineCourse.LIFECYCLE_PUBLISHED
        return attrs


class OnlineAdminCourseBuilderDeliverySerializer(serializers.Serializer):
    cohortId = serializers.IntegerField(required=False, allow_null=True)
    groupCode = serializers.CharField(max_length=80, required=False, allow_blank=True)
    groupName = serializers.CharField(max_length=220, required=False, allow_blank=True)
    capacity = serializers.IntegerField(required=False, min_value=1, max_value=500, default=20)
    timezone = serializers.CharField(max_length=64, required=False, allow_blank=True, default="Europe/Berlin")
    startDate = serializers.DateField(required=False, allow_null=True)
    endDate = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=OnlineCohort.STATUS_CHOICES, required=False, default=OnlineCohort.STATUS_DRAFT)
    isPublic = serializers.BooleanField(required=False, default=True)
    curatorId = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        cohort_id = attrs.get("cohortId")
        group_code = (attrs.get("groupCode") or "").strip().upper()
        group_name = (attrs.get("groupName") or "").strip()
        timezone_value = (attrs.get("timezone") or "").strip() or "Europe/Berlin"
        start_date = attrs.get("startDate")
        end_date = attrs.get("endDate")

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"endDate": "End date must be greater than or equal to start date."})

        if cohort_id is None:
            if not group_code:
                raise serializers.ValidationError({"groupCode": "Group code is required when creating a cohort."})
            if not group_name:
                raise serializers.ValidationError({"groupName": "Group name is required when creating a cohort."})

        attrs["groupCode"] = group_code
        attrs["groupName"] = group_name
        attrs["timezone"] = timezone_value
        return attrs


class OnlineAdminCourseBuilderSessionSeedItemSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=220, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    startsAt = serializers.DateTimeField()
    endsAt = serializers.DateTimeField()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["endsAt"] <= attrs["startsAt"]:
            raise serializers.ValidationError({"endsAt": "Session end must be after the start time."})
        return attrs


class OnlineAdminCourseBuilderSessionSeedSerializer(serializers.Serializer):
    cohortId = serializers.IntegerField()
    sessions = OnlineAdminCourseBuilderSessionSeedItemSerializer(many=True)

    def validate_sessions(self, value):
        if not value:
            raise serializers.ValidationError("Add at least one session before saving.")
        if len(value) > 24:
            raise serializers.ValidationError("You can create at most 24 sessions in one builder operation.")
        return value
