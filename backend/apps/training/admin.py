from django.contrib import admin

from apps.training.models import (
    TrainingAiConversation,
    TrainingAiMessage,
    TrainingAiQuizAttempt,
    TrainingAssetClass,
    TrainingAuditEvent,
    TrainingAudience,
    TrainingContentAudiencePolicy,
    TrainingContentCrossReference,
    TrainingContentItem,
    TrainingContentSyncEvent,
    TrainingCourseRoleAssignment,
    TrainingGradebookEntry,
    TrainingGraderJob,
    TrainingJupyterLoginToken,
    TrainingKnowledgeChunk,
    TrainingLabLaunchToken,
    TrainingLabSubmission,
    TrainingLabSubmissionArtifact,
    TrainingNotebookLabProfile,
    TrainingTopic,
    TrainingUserAudienceGrant,
)


@admin.register(TrainingAudience)
class TrainingAudienceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_internal", "is_active")
    list_filter = ("is_internal", "is_active")
    search_fields = ("name", "slug", "description")


@admin.register(TrainingAssetClass)
class TrainingAssetClassAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "description")


@admin.register(TrainingTopic)
class TrainingTopicAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "description")


@admin.register(TrainingCourseRoleAssignment)
class TrainingCourseRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("course", "user", "role", "is_primary", "response_sla_hours")
    list_filter = ("role", "is_primary")
    search_fields = ("course__slug", "user__email")


@admin.register(TrainingUserAudienceGrant)
class TrainingUserAudienceGrantAdmin(admin.ModelAdmin):
    list_display = ("user", "audience", "expires_at", "granted_by")
    list_filter = ("audience",)
    search_fields = ("user__email", "audience__slug", "audience__name")


class TrainingContentAudiencePolicyInline(admin.TabularInline):
    model = TrainingContentAudiencePolicy
    extra = 0


class TrainingContentCrossReferenceInline(admin.TabularInline):
    model = TrainingContentCrossReference
    fk_name = "from_item"
    extra = 0


class TrainingNotebookLabProfileInline(admin.StackedInline):
    model = TrainingNotebookLabProfile
    extra = 0


class TrainingKnowledgeChunkInline(admin.TabularInline):
    model = TrainingKnowledgeChunk
    extra = 0
    fields = ("chunk_index", "section_title", "citation_label", "snippet", "source_checksum", "is_active")
    readonly_fields = ("chunk_index", "section_title", "citation_label", "snippet", "source_checksum")
    can_delete = False


@admin.register(TrainingContentItem)
class TrainingContentItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "content_kind",
        "status",
        "access_scope",
        "course",
        "authoring_source",
        "last_synced_at",
        "knowledge_indexed_at",
        "is_repeatable_on_demand",
    )
    list_filter = (
        "content_kind",
        "status",
        "access_scope",
        "difficulty",
        "is_repeatable_on_demand",
        "authoring_source",
    )
    search_fields = ("name", "slug", "description", "search_keywords", "authoring_source_id")
    filter_horizontal = ("asset_classes", "topics")
    inlines = (
        TrainingContentAudiencePolicyInline,
        TrainingContentCrossReferenceInline,
        TrainingNotebookLabProfileInline,
        TrainingKnowledgeChunkInline,
    )


@admin.register(TrainingContentSyncEvent)
class TrainingContentSyncEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "source", "event_type", "status", "content_slug", "external_source_id", "content_item")
    list_filter = ("source", "event_type", "status")
    search_fields = ("content_slug", "external_source_id", "detail", "content_item__slug", "content_item__name")
    readonly_fields = ("created_at",)


@admin.register(TrainingContentAudiencePolicy)
class TrainingContentAudiencePolicyAdmin(admin.ModelAdmin):
    list_display = ("content_item", "audience", "created_at")
    list_filter = ("audience",)
    search_fields = ("content_item__name", "audience__name", "audience__slug")


@admin.register(TrainingContentCrossReference)
class TrainingContentCrossReferenceAdmin(admin.ModelAdmin):
    list_display = ("from_item", "relation_type", "to_item")
    list_filter = ("relation_type",)
    search_fields = ("from_item__name", "to_item__name", "note")


@admin.register(TrainingNotebookLabProfile)
class TrainingNotebookLabProfileAdmin(admin.ModelAdmin):
    list_display = ("content_item", "runtime_backend", "grader_backend", "is_active", "allow_gpu")
    list_filter = ("runtime_backend", "grader_backend", "is_active", "allow_gpu", "allow_network")
    search_fields = ("content_item__name", "content_item__slug", "runtime_image", "notebook_path")


@admin.register(TrainingLabLaunchToken)
class TrainingLabLaunchTokenAdmin(admin.ModelAdmin):
    list_display = ("token_id", "content_item", "user", "status", "expires_at", "consumed_at")
    list_filter = ("status", "content_item__content_kind")
    search_fields = ("token_id", "content_item__slug", "user__email")


@admin.register(TrainingJupyterLoginToken)
class TrainingJupyterLoginTokenAdmin(admin.ModelAdmin):
    list_display = ("token_id", "jupyter_username", "content_item", "user", "status", "expires_at", "consumed_at")
    list_filter = ("status",)
    search_fields = ("token_id", "jupyter_username", "content_item__slug", "user__email")


class TrainingLabSubmissionArtifactInline(admin.TabularInline):
    model = TrainingLabSubmissionArtifact
    extra = 0


@admin.register(TrainingLabSubmission)
class TrainingLabSubmissionAdmin(admin.ModelAdmin):
    list_display = ("public_id", "content_item", "user", "attempt_number", "status", "score", "passed", "submitted_at")
    list_filter = ("status", "grader_backend", "passed")
    search_fields = ("public_id", "content_item__slug", "user__email", "source_path", "notebook_path")
    inlines = (TrainingLabSubmissionArtifactInline,)


@admin.register(TrainingGradebookEntry)
class TrainingGradebookEntryAdmin(admin.ModelAdmin):
    list_display = ("content_item", "user", "attempts_count", "latest_score", "best_score", "passed", "completed_at")
    list_filter = ("passed", "content_item__content_kind")
    search_fields = ("content_item__slug", "content_item__name", "user__email")


@admin.register(TrainingGraderJob)
class TrainingGraderJobAdmin(admin.ModelAdmin):
    list_display = ("submission", "backend", "status", "priority", "attempts_count", "available_at", "finished_at")
    list_filter = ("backend", "status")
    search_fields = ("submission__public_id", "submission__content_item__slug", "submission__user__email", "worker_name")


@admin.register(TrainingAuditEvent)
class TrainingAuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "category", "outcome", "actor_email", "target_user_email", "content_item")
    list_filter = ("category", "outcome", "event_type")
    search_fields = (
        "event_type",
        "request_id",
        "actor_email",
        "target_user_email",
        "content_item__slug",
        "content_item__name",
        "submission__public_id",
    )
    readonly_fields = (
        "created_at",
        "event_id",
        "request_id",
    )


@admin.register(TrainingKnowledgeChunk)
class TrainingKnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ("content_item", "chunk_index", "citation_label", "token_count", "embedding_model", "is_active")
    list_filter = ("is_active", "embedding_model")
    search_fields = ("content_item__slug", "content_item__name", "section_title", "citation_label", "chunk_text")
    readonly_fields = ("source_checksum", "chunk_checksum", "created_at", "updated_at")


@admin.register(TrainingAiConversation)
class TrainingAiConversationAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "user",
        "content_item",
        "status",
        "governance_status",
        "assigned_to",
        "resolved_by",
        "last_activity_at",
    )
    list_filter = ("status", "governance_status")
    search_fields = ("public_id", "user__email", "content_item__slug", "content_item__name", "title")


@admin.register(TrainingAiMessage)
class TrainingAiMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "prompt_type", "resolution_status", "provider", "created_at")
    list_filter = ("role", "prompt_type", "resolution_status", "provider")
    search_fields = ("conversation__public_id", "content_item__slug", "body")
    readonly_fields = ("created_at",)


@admin.register(TrainingAiQuizAttempt)
class TrainingAiQuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("public_id", "user", "content_item", "status", "score", "max_score", "submitted_at")
    list_filter = ("status",)
    search_fields = ("public_id", "user__email", "content_item__slug", "content_item__name", "title")
