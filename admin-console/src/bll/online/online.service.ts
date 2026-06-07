import { baseApi } from "@/bll/base-api";
import type {
  OnlineAdminCohortCuratorAssignmentInput,
  OnlineAdminCohortCuratorAssignmentResponse,
  OnlineAdminAttendanceSyncResponse,
  OnlineAdminCatalogAttributeDefinition,
  OnlineAdminCatalogAttributeDefinitionListResponse,
  OnlineAdminCatalogAttributeDefinitionWriteInput,
  OnlineAdminCatalogAttributeValue,
  OnlineAdminCatalogAttributeValueListResponse,
  OnlineAdminCatalogAttributeValueWriteInput,
  OnlineAdminCatalogSearchArgs,
  OnlineAdminCatalogSearchResponse,
  OnlineAdminSessionBulkActionInput,
  OnlineAdminSessionBulkActionResponse,
  OnlineAdminCuratorCreateInput,
  OnlineAdminCuratorOnboardingInput,
  OnlineAdminCuratorListResponse,
  OnlineAdminSessionListResponse,
  OnlineAdminCuratorSummary,
  OnlineAdminEnterpriseSummary,
  OnlineAdminExternalCatalogProvider,
  OnlineAdminExternalCatalogProviderListResponse,
  OnlineAdminExternalCatalogProviderWriteInput,
  OnlineAdminInstructorProfile,
  OnlineAdminInstructorProfileListResponse,
  OnlineAdminInstructorProfileWriteInput,
  OnlineAdminKnowledgeDocument,
  OnlineAdminKnowledgeDocumentListResponse,
  OnlineAdminKnowledgeDocumentWriteInput,
  OnlineAdminKnowledgeSource,
  OnlineAdminKnowledgeSourceListResponse,
  OnlineAdminKnowledgeSourceWriteInput,
  OnlineAdminLearningProgram,
  OnlineAdminLearningProgramListResponse,
  OnlineAdminLearningProgramWriteInput,
  OnlineAdminScopeAssignmentListResponse,
  OnlineAdminScopeAssignmentPatchInput,
  OnlineAdminScopeAssignmentWriteInput,
  OnlineAdminStudentProfile,
  OnlineAdminStudentProfileListResponse,
  OnlineAdminStudentProfilePatchInput,
  OnlineAdminStudentProgramAssignment,
  OnlineAdminStudentProgramAssignmentListResponse,
  OnlineAdminStudentProgramAssignmentWriteInput,
  OnlineAdminCuratorUpdateInput,
  OnlineAdminUserListResponse,
  OnlineAdminUserStatusInput,
  OnlineAdminUserSummary,
  OnlineAdminUserTemporaryPasswordInput,
  OnlineCourseDetail,
  OnlineCourseListResponse,
  OnlineCohortDetail,
  OnlineCohortListResponse,
  OnlineSessionStatus,
  OnlineSessionStatusUpdateResponse,
} from "./online.type";

type OnlineCohortsQueryArgs = {
  q?: string;
  courseId?: number;
};

type OnlineAdminSessionsQueryArgs = {
  q?: string;
  courseId?: number;
  cohortId?: number;
  teacherId?: number;
  status?: OnlineSessionStatus;
  startsFrom?: string;
  startsTo?: string;
  attendanceSynced?: boolean;
  hasJoinUrl?: boolean;
  hasRecording?: boolean;
};

type OnlineAdminScopeAssignmentsQueryArgs = {
  userId?: number;
  courseId?: number;
  role?: "manager" | "delivery_manager" | "compliance_manager" | "review_manager";
  scopeType?: "academy" | "course" | "cohort";
  activeOnly?: boolean;
};

type OnlineAdminCatalogAttributeValueQueryArgs = {
  definitionId?: number;
  objectId?: number;
  entityType?: "course" | "student" | "instructor" | "program" | "knowledge";
};

export const onlineService = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getOnlineCourses: builder.query<OnlineCourseListResponse, string | void>({
      query: (queryText) => ({
        url: "/online/admin/courses/",
        method: "GET",
        params: queryText ? { q: queryText } : undefined
      })
    }),
    getOnlineCourseDetail: builder.query<OnlineCourseDetail, number>({
      query: (courseId) => ({
        url: `/online/admin/courses/${courseId}/`,
        method: "GET"
      })
    }),
    getOnlineCohorts: builder.query<OnlineCohortListResponse, OnlineCohortsQueryArgs | void>({
      query: (args) => ({
        url: "/online/admin/cohorts/",
        method: "GET",
        params: args ? {
          ...(args.q ? { q: args.q } : {}),
          ...(args.courseId ? { course_id: args.courseId } : {}),
        } : undefined
      }),
      providesTags: [{ type: "OnlineAdminCohortDirectory", id: "LIST" }],
    }),
    getOnlineCohortDetail: builder.query<OnlineCohortDetail, number>({
      query: (cohortId) => ({
        url: `/online/admin/cohorts/${cohortId}/`,
        method: "GET"
      })
    }),
    getOnlineAdminSessions: builder.query<OnlineAdminSessionListResponse, OnlineAdminSessionsQueryArgs | void>({
      query: (args) => ({
        url: "/online/admin/sessions/",
        method: "GET",
        params: args
          ? {
              ...(args.q ? { q: args.q } : {}),
              ...(args.courseId ? { course_id: args.courseId } : {}),
              ...(args.cohortId ? { cohort_id: args.cohortId } : {}),
              ...(args.teacherId ? { teacher_id: args.teacherId } : {}),
              ...(args.status ? { status: args.status } : {}),
              ...(args.startsFrom ? { starts_from: args.startsFrom } : {}),
              ...(args.startsTo ? { starts_to: args.startsTo } : {}),
              ...(args.attendanceSynced !== undefined ? { attendance_synced: args.attendanceSynced } : {}),
              ...(args.hasJoinUrl !== undefined ? { has_join_url: args.hasJoinUrl } : {}),
              ...(args.hasRecording !== undefined ? { has_recording: args.hasRecording } : {}),
            }
          : undefined,
      }),
      providesTags: [{ type: "OnlineAdminSessionDirectory", id: "LIST" }],
    }),
    getOnlineAdminEnterpriseSummary: builder.query<OnlineAdminEnterpriseSummary, { courseId?: number } | void>({
      query: (args) => ({
        url: "/online/admin/enterprise-summary/",
        method: "GET",
        params: args?.courseId ? { course_id: args.courseId } : undefined,
      }),
      providesTags: [{ type: "OnlineAdminEnterpriseSummary", id: "GLOBAL" }],
    }),
    searchOnlineAdminCatalog: builder.query<OnlineAdminCatalogSearchResponse, OnlineAdminCatalogSearchArgs | void>({
      query: (args) => ({
        url: "/online/admin/catalog/search/",
        method: "GET",
        params: {
          ...(args?.q ? { q: args.q } : {}),
          ...(args?.confidentialityLevel ? { confidentialityLevel: args.confidentialityLevel } : {}),
          ...(args?.providerType ? { providerType: args.providerType } : {}),
          ...(args?.courseType ? { courseType: args.courseType } : {}),
          ...(args?.difficultyLevel ? { difficultyLevel: args.difficultyLevel } : {}),
          ...(args?.knowledgeDomain ? { knowledgeDomain: args.knowledgeDomain } : {}),
          ...(args?.ratingMin !== undefined ? { ratingMin: args.ratingMin } : {}),
        },
      }),
      providesTags: [{ type: "OnlineAdminCatalogSearch", id: "GLOBAL" }],
    }),
    getOnlineAdminCatalogAttributes: builder.query<
      OnlineAdminCatalogAttributeDefinitionListResponse,
      { entityType?: OnlineAdminCatalogAttributeDefinition["entityType"] } | void
    >({
      query: (args) => ({
        url: "/online/admin/catalog/attributes/",
        method: "GET",
        params: args?.entityType ? { entity_type: args.entityType } : undefined,
      }),
      providesTags: [{ type: "OnlineAdminCatalogAttribute", id: "LIST" }],
    }),
    createOnlineAdminCatalogAttribute: builder.mutation<
      OnlineAdminCatalogAttributeDefinition,
      OnlineAdminCatalogAttributeDefinitionWriteInput
    >({
      query: (body) => ({
        url: "/online/admin/catalog/attributes/",
        method: "POST",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminCatalogAttribute", id: "LIST" }],
    }),
    updateOnlineAdminCatalogAttribute: builder.mutation<
      OnlineAdminCatalogAttributeDefinition,
      { definitionId: number; body: Partial<OnlineAdminCatalogAttributeDefinitionWriteInput> }
    >({
      query: ({ definitionId, body }) => ({
        url: `/online/admin/catalog/attributes/${definitionId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminCatalogAttribute", id: "LIST" }],
    }),
    deleteOnlineAdminCatalogAttribute: builder.mutation<void, number>({
      query: (definitionId) => ({
        url: `/online/admin/catalog/attributes/${definitionId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [{ type: "OnlineAdminCatalogAttribute", id: "LIST" }],
    }),
    getOnlineAdminCatalogAttributeValues: builder.query<
      OnlineAdminCatalogAttributeValueListResponse,
      OnlineAdminCatalogAttributeValueQueryArgs | void
    >({
      query: (args) => ({
        url: "/online/admin/catalog/attribute-values/",
        method: "GET",
        params: {
          ...(args?.definitionId ? { definition_id: args.definitionId } : {}),
          ...(args?.objectId ? { object_id: args.objectId } : {}),
          ...(args?.entityType ? { entity_type: args.entityType } : {}),
        },
      }),
      providesTags: [{ type: "OnlineAdminCatalogAttributeValue", id: "LIST" }],
    }),
    createOnlineAdminCatalogAttributeValue: builder.mutation<
      OnlineAdminCatalogAttributeValue,
      OnlineAdminCatalogAttributeValueWriteInput
    >({
      query: (body) => ({
        url: "/online/admin/catalog/attribute-values/",
        method: "POST",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminCatalogAttributeValue", id: "LIST" }],
    }),
    updateOnlineAdminCatalogAttributeValue: builder.mutation<
      OnlineAdminCatalogAttributeValue,
      { valueId: number; body: OnlineAdminCatalogAttributeValueWriteInput }
    >({
      query: ({ valueId, body }) => ({
        url: `/online/admin/catalog/attribute-values/${valueId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminCatalogAttributeValue", id: "LIST" }],
    }),
    deleteOnlineAdminCatalogAttributeValue: builder.mutation<void, number>({
      query: (valueId) => ({
        url: `/online/admin/catalog/attribute-values/${valueId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [{ type: "OnlineAdminCatalogAttributeValue", id: "LIST" }],
    }),
    getOnlineAdminStudentProfiles: builder.query<
      OnlineAdminStudentProfileListResponse,
      { q?: string } | void
    >({
      query: (args) => ({
        url: "/online/admin/student-profiles/",
        method: "GET",
        params: args?.q ? { q: args.q } : undefined,
      }),
      providesTags: [{ type: "OnlineAdminStudentProfile", id: "LIST" }],
    }),
    getOnlineAdminStudentProfileDetail: builder.query<OnlineAdminStudentProfile, number>({
      query: (profileId) => ({
        url: `/online/admin/student-profiles/${profileId}/`,
        method: "GET",
      }),
      providesTags: (_result, _error, profileId) => [{ type: "OnlineAdminStudentProfile", id: profileId }],
    }),
    updateOnlineAdminStudentProfile: builder.mutation<
      OnlineAdminStudentProfile,
      { profileId: number; body: OnlineAdminStudentProfilePatchInput }
    >({
      query: ({ profileId, body }) => ({
        url: `/online/admin/student-profiles/${profileId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { profileId }) => [
        { type: "OnlineAdminStudentProfile", id: profileId },
        { type: "OnlineAdminStudentProfile", id: "LIST" },
        { type: "OnlineAdminUserDirectory", id: "LIST" },
      ],
    }),
    getOnlineAdminInstructorProfiles: builder.query<
      OnlineAdminInstructorProfileListResponse,
      { q?: string } | void
    >({
      query: (args) => ({
        url: "/online/admin/instructor-profiles/",
        method: "GET",
        params: args?.q ? { q: args.q } : undefined,
      }),
      providesTags: [{ type: "OnlineAdminInstructorProfile", id: "LIST" }],
    }),
    createOnlineAdminInstructorProfile: builder.mutation<
      OnlineAdminInstructorProfile,
      OnlineAdminInstructorProfileWriteInput
    >({
      query: (body) => ({
        url: "/online/admin/instructor-profiles/",
        method: "POST",
        body,
      }),
      invalidatesTags: [
        { type: "OnlineAdminInstructorProfile", id: "LIST" },
        { type: "OnlineAdminCurator", id: "LIST" },
      ],
    }),
    updateOnlineAdminInstructorProfile: builder.mutation<
      OnlineAdminInstructorProfile,
      { profileId: number; body: Partial<OnlineAdminInstructorProfileWriteInput> }
    >({
      query: ({ profileId, body }) => ({
        url: `/online/admin/instructor-profiles/${profileId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { profileId }) => [
        { type: "OnlineAdminInstructorProfile", id: profileId },
        { type: "OnlineAdminInstructorProfile", id: "LIST" },
        { type: "OnlineAdminCurator", id: "LIST" },
      ],
    }),
    deleteOnlineAdminInstructorProfile: builder.mutation<void, number>({
      query: (profileId) => ({
        url: `/online/admin/instructor-profiles/${profileId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [
        { type: "OnlineAdminInstructorProfile", id: "LIST" },
        { type: "OnlineAdminCurator", id: "LIST" },
      ],
    }),
    getOnlineAdminExternalProviders: builder.query<
      OnlineAdminExternalCatalogProviderListResponse,
      void
    >({
      query: () => ({
        url: "/online/admin/external-providers/",
        method: "GET",
      }),
      providesTags: [{ type: "OnlineAdminExternalProvider", id: "LIST" }],
    }),
    createOnlineAdminExternalProvider: builder.mutation<
      OnlineAdminExternalCatalogProvider,
      OnlineAdminExternalCatalogProviderWriteInput
    >({
      query: (body) => ({
        url: "/online/admin/external-providers/",
        method: "POST",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminExternalProvider", id: "LIST" }],
    }),
    updateOnlineAdminExternalProvider: builder.mutation<
      OnlineAdminExternalCatalogProvider,
      { providerId: number; body: Partial<OnlineAdminExternalCatalogProviderWriteInput> }
    >({
      query: ({ providerId, body }) => ({
        url: `/online/admin/external-providers/${providerId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminExternalProvider", id: "LIST" }],
    }),
    deleteOnlineAdminExternalProvider: builder.mutation<void, number>({
      query: (providerId) => ({
        url: `/online/admin/external-providers/${providerId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [{ type: "OnlineAdminExternalProvider", id: "LIST" }],
    }),
    getOnlineAdminLearningPrograms: builder.query<OnlineAdminLearningProgramListResponse, void>({
      query: () => ({
        url: "/online/admin/programs/",
        method: "GET",
      }),
      providesTags: [{ type: "OnlineAdminLearningProgram", id: "LIST" }],
    }),
    createOnlineAdminLearningProgram: builder.mutation<
      OnlineAdminLearningProgram,
      OnlineAdminLearningProgramWriteInput
    >({
      query: (body) => ({
        url: "/online/admin/programs/",
        method: "POST",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminLearningProgram", id: "LIST" }],
    }),
    updateOnlineAdminLearningProgram: builder.mutation<
      OnlineAdminLearningProgram,
      { programId: number; body: Partial<OnlineAdminLearningProgramWriteInput> }
    >({
      query: ({ programId, body }) => ({
        url: `/online/admin/programs/${programId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminLearningProgram", id: "LIST" }],
    }),
    deleteOnlineAdminLearningProgram: builder.mutation<void, number>({
      query: (programId) => ({
        url: `/online/admin/programs/${programId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [{ type: "OnlineAdminLearningProgram", id: "LIST" }],
    }),
    getOnlineAdminProgramAssignments: builder.query<
      OnlineAdminStudentProgramAssignmentListResponse,
      { profileId?: number; programId?: number } | void
    >({
      query: (args) => ({
        url: "/online/admin/program-assignments/",
        method: "GET",
        params: {
          ...(args?.profileId ? { profile_id: args.profileId } : {}),
          ...(args?.programId ? { program_id: args.programId } : {}),
        },
      }),
      providesTags: [{ type: "OnlineAdminProgramAssignment", id: "LIST" }],
    }),
    createOnlineAdminProgramAssignment: builder.mutation<
      OnlineAdminStudentProgramAssignment,
      OnlineAdminStudentProgramAssignmentWriteInput
    >({
      query: (body) => ({
        url: "/online/admin/program-assignments/",
        method: "POST",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminProgramAssignment", id: "LIST" }],
    }),
    updateOnlineAdminProgramAssignment: builder.mutation<
      OnlineAdminStudentProgramAssignment,
      { assignmentId: number; body: Partial<OnlineAdminStudentProgramAssignmentWriteInput> }
    >({
      query: ({ assignmentId, body }) => ({
        url: `/online/admin/program-assignments/${assignmentId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminProgramAssignment", id: "LIST" }],
    }),
    deleteOnlineAdminProgramAssignment: builder.mutation<void, number>({
      query: (assignmentId) => ({
        url: `/online/admin/program-assignments/${assignmentId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [{ type: "OnlineAdminProgramAssignment", id: "LIST" }],
    }),
    getOnlineAdminKnowledgeSources: builder.query<OnlineAdminKnowledgeSourceListResponse, void>({
      query: () => ({
        url: "/online/admin/knowledge-sources/",
        method: "GET",
      }),
      providesTags: [{ type: "OnlineAdminKnowledgeSource", id: "LIST" }],
    }),
    createOnlineAdminKnowledgeSource: builder.mutation<
      OnlineAdminKnowledgeSource,
      OnlineAdminKnowledgeSourceWriteInput
    >({
      query: (body) => ({
        url: "/online/admin/knowledge-sources/",
        method: "POST",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminKnowledgeSource", id: "LIST" }],
    }),
    updateOnlineAdminKnowledgeSource: builder.mutation<
      OnlineAdminKnowledgeSource,
      { sourceId: number; body: Partial<OnlineAdminKnowledgeSourceWriteInput> }
    >({
      query: ({ sourceId, body }) => ({
        url: `/online/admin/knowledge-sources/${sourceId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminKnowledgeSource", id: "LIST" }],
    }),
    deleteOnlineAdminKnowledgeSource: builder.mutation<void, number>({
      query: (sourceId) => ({
        url: `/online/admin/knowledge-sources/${sourceId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [{ type: "OnlineAdminKnowledgeSource", id: "LIST" }],
    }),
    getOnlineAdminKnowledgeDocuments: builder.query<
      OnlineAdminKnowledgeDocumentListResponse,
      { sourceId?: number } | void
    >({
      query: (args) => ({
        url: "/online/admin/knowledge-documents/",
        method: "GET",
        params: args?.sourceId ? { source_id: args.sourceId } : undefined,
      }),
      providesTags: [{ type: "OnlineAdminKnowledgeDocument", id: "LIST" }],
    }),
    createOnlineAdminKnowledgeDocument: builder.mutation<
      OnlineAdminKnowledgeDocument,
      OnlineAdminKnowledgeDocumentWriteInput
    >({
      query: (body) => ({
        url: "/online/admin/knowledge-documents/",
        method: "POST",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminKnowledgeDocument", id: "LIST" }],
    }),
    updateOnlineAdminKnowledgeDocument: builder.mutation<
      OnlineAdminKnowledgeDocument,
      { documentId: number; body: Partial<OnlineAdminKnowledgeDocumentWriteInput> }
    >({
      query: ({ documentId, body }) => ({
        url: `/online/admin/knowledge-documents/${documentId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminKnowledgeDocument", id: "LIST" }],
    }),
    deleteOnlineAdminKnowledgeDocument: builder.mutation<void, number>({
      query: (documentId) => ({
        url: `/online/admin/knowledge-documents/${documentId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [{ type: "OnlineAdminKnowledgeDocument", id: "LIST" }],
    }),
    getOnlineAdminScopeAssignments: builder.query<
      OnlineAdminScopeAssignmentListResponse,
      OnlineAdminScopeAssignmentsQueryArgs | void
    >({
      query: (args) => ({
        url: "/online/admin/scope-assignments/",
        method: "GET",
        params: {
          ...(args?.userId ? { user_id: args.userId } : {}),
          ...(args?.courseId ? { course_id: args.courseId } : {}),
          ...(args?.role ? { role: args.role } : {}),
          ...(args?.scopeType ? { scope_type: args.scopeType } : {}),
          ...(args?.activeOnly ? { active_only: 1 } : {}),
        },
      }),
      providesTags: [{ type: "OnlineAdminScopeAssignment", id: "LIST" }],
    }),
    createOnlineAdminScopeAssignment: builder.mutation<void, OnlineAdminScopeAssignmentWriteInput>({
      query: (body) => ({
        url: "/online/admin/scope-assignments/",
        method: "POST",
        body,
      }),
      invalidatesTags: [
        { type: "OnlineAdminScopeAssignment", id: "LIST" },
        { type: "OnlineAdminEnterpriseSummary", id: "GLOBAL" },
      ],
    }),
    updateOnlineAdminScopeAssignment: builder.mutation<
      void,
      { assignmentId: number; body: OnlineAdminScopeAssignmentPatchInput }
    >({
      query: ({ assignmentId, body }) => ({
        url: `/online/admin/scope-assignments/${assignmentId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: [
        { type: "OnlineAdminScopeAssignment", id: "LIST" },
        { type: "OnlineAdminEnterpriseSummary", id: "GLOBAL" },
      ],
    }),
    deleteOnlineAdminScopeAssignment: builder.mutation<void, number>({
      query: (assignmentId) => ({
        url: `/online/admin/scope-assignments/${assignmentId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [
        { type: "OnlineAdminScopeAssignment", id: "LIST" },
        { type: "OnlineAdminEnterpriseSummary", id: "GLOBAL" },
      ],
    }),
    getOnlineAdminUsers: builder.query<
      OnlineAdminUserListResponse,
      { q?: string; role?: "curator" | "admin" | "student" | "" } | void
    >({
      query: (args) => ({
        url: "/online/admin/users/",
        method: "GET",
        params: {
          ...(args?.q ? { q: args.q } : {}),
          ...(args?.role ? { role: args.role } : {}),
        },
      }),
      providesTags: [{ type: "OnlineAdminUserDirectory", id: "LIST" }],
    }),
    updateOnlineAdminUserStatus: builder.mutation<
      OnlineAdminUserSummary,
      { userId: number; body: OnlineAdminUserStatusInput }
    >({
      query: ({ userId, body }) => ({
        url: `/online/admin/users/${userId}/status/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: [
        { type: "OnlineAdminUserDirectory", id: "LIST" },
        { type: "OnlineAdminCurator", id: "LIST" },
      ],
    }),
    resetOnlineAdminUserTemporaryPassword: builder.mutation<
      OnlineAdminUserSummary,
      { userId: number; body: OnlineAdminUserTemporaryPasswordInput }
    >({
      query: ({ userId, body }) => ({
        url: `/online/admin/users/${userId}/temporary-password/`,
        method: "POST",
        body,
      }),
      invalidatesTags: [
        { type: "OnlineAdminUserDirectory", id: "LIST" },
        { type: "OnlineAdminCurator", id: "LIST" },
      ],
    }),
    getOnlineAdminCurators: builder.query<OnlineAdminCuratorListResponse, { q?: string } | void>({
      query: (args) => ({
        url: "/online/admin/curators/",
        method: "GET",
        params: args?.q ? { q: args.q } : undefined,
      }),
      providesTags: (result) =>
        result
          ? [
              { type: "OnlineAdminCurator", id: "LIST" },
              ...result.results.map((item) => ({ type: "OnlineAdminCurator" as const, id: item.id })),
            ]
          : [{ type: "OnlineAdminCurator", id: "LIST" }],
    }),
    createOnlineAdminCurator: builder.mutation<OnlineAdminCuratorSummary, OnlineAdminCuratorCreateInput>({
      query: (body) => ({
        url: "/online/admin/curators/",
        method: "POST",
        body,
      }),
      invalidatesTags: [
        { type: "OnlineAdminCurator", id: "LIST" },
        { type: "OnlineAdminUserDirectory", id: "LIST" },
      ],
    }),
    onboardOnlineAdminCurator: builder.mutation<OnlineAdminCuratorSummary, OnlineAdminCuratorOnboardingInput>({
      query: (body) => ({
        url: "/online/admin/curator-onboarding/",
        method: "POST",
        body,
      }),
      invalidatesTags: [
        { type: "OnlineAdminCurator", id: "LIST" },
        { type: "OnlineAdminUserDirectory", id: "LIST" },
      ],
    }),
    updateOnlineAdminCurator: builder.mutation<
      OnlineAdminCuratorSummary,
      { curatorId: number; body: OnlineAdminCuratorUpdateInput }
    >({
      query: ({ curatorId, body }) => ({
        url: `/online/admin/curators/${curatorId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { curatorId }) => [
        { type: "OnlineAdminCurator", id: curatorId },
        { type: "OnlineAdminCurator", id: "LIST" },
        { type: "OnlineAdminUserDirectory", id: "LIST" },
      ],
    }),
    deleteOnlineAdminCurator: builder.mutation<void, number>({
      query: (curatorId) => ({
        url: `/online/admin/curators/${curatorId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [
        { type: "OnlineAdminCurator", id: "LIST" },
        { type: "OnlineAdminUserDirectory", id: "LIST" },
      ],
    }),
    assignOnlineAdminCohortCurator: builder.mutation<
      OnlineAdminCohortCuratorAssignmentResponse,
      { cohortId: number; body: OnlineAdminCohortCuratorAssignmentInput }
    >({
      query: ({ cohortId, body }) => ({
        url: `/online/admin/cohorts/${cohortId}/curator/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: [
        { type: "OnlineAdminCurator", id: "LIST" },
        { type: "OnlineAdminUserDirectory", id: "LIST" },
        { type: "OnlineAdminCohortDirectory", id: "LIST" },
      ],
    }),
    updateOnlineSessionStatus: builder.mutation<
      OnlineSessionStatusUpdateResponse,
      { sessionId: number; status: OnlineSessionStatus }
    >({
      query: ({ sessionId, status }) => ({
        url: `/online/admin/sessions/${sessionId}/status/`,
        method: "PATCH",
        body: { status },
      }),
      invalidatesTags: [{ type: "OnlineAdminSessionDirectory", id: "LIST" }],
    }),
    openOnlineAdminSession: builder.mutation<OnlineSessionStatusUpdateResponse, number>({
      query: (sessionId) => ({
        url: `/online/admin/sessions/${sessionId}/open/`,
        method: "POST",
      }),
      invalidatesTags: [{ type: "OnlineAdminSessionDirectory", id: "LIST" }],
    }),
    endOnlineAdminSession: builder.mutation<OnlineSessionStatusUpdateResponse, number>({
      query: (sessionId) => ({
        url: `/online/admin/sessions/${sessionId}/end/`,
        method: "POST",
      }),
      invalidatesTags: [{ type: "OnlineAdminSessionDirectory", id: "LIST" }],
    }),
    syncOnlineAdminSessionAttendance: builder.mutation<OnlineAdminAttendanceSyncResponse, number>({
      query: (sessionId) => ({
        url: `/online/admin/sessions/${sessionId}/attendance/sync/`,
        method: "POST",
      }),
      invalidatesTags: [{ type: "OnlineAdminSessionDirectory", id: "LIST" }],
    }),
    runOnlineAdminSessionBulkAction: builder.mutation<
      OnlineAdminSessionBulkActionResponse,
      OnlineAdminSessionBulkActionInput
    >({
      query: (body) => ({
        url: "/online/admin/sessions/bulk/",
        method: "POST",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminSessionDirectory", id: "LIST" }],
    }),
  })
});

export const {
  useGetOnlineCoursesQuery,
  useGetOnlineCourseDetailQuery,
  useGetOnlineCohortsQuery,
  useGetOnlineCohortDetailQuery,
  useGetOnlineAdminSessionsQuery,
  useGetOnlineAdminEnterpriseSummaryQuery,
  useSearchOnlineAdminCatalogQuery,
  useGetOnlineAdminCatalogAttributesQuery,
  useCreateOnlineAdminCatalogAttributeMutation,
  useUpdateOnlineAdminCatalogAttributeMutation,
  useDeleteOnlineAdminCatalogAttributeMutation,
  useGetOnlineAdminCatalogAttributeValuesQuery,
  useCreateOnlineAdminCatalogAttributeValueMutation,
  useUpdateOnlineAdminCatalogAttributeValueMutation,
  useDeleteOnlineAdminCatalogAttributeValueMutation,
  useGetOnlineAdminStudentProfilesQuery,
  useGetOnlineAdminStudentProfileDetailQuery,
  useUpdateOnlineAdminStudentProfileMutation,
  useGetOnlineAdminInstructorProfilesQuery,
  useCreateOnlineAdminInstructorProfileMutation,
  useUpdateOnlineAdminInstructorProfileMutation,
  useDeleteOnlineAdminInstructorProfileMutation,
  useGetOnlineAdminExternalProvidersQuery,
  useCreateOnlineAdminExternalProviderMutation,
  useUpdateOnlineAdminExternalProviderMutation,
  useDeleteOnlineAdminExternalProviderMutation,
  useGetOnlineAdminLearningProgramsQuery,
  useCreateOnlineAdminLearningProgramMutation,
  useUpdateOnlineAdminLearningProgramMutation,
  useDeleteOnlineAdminLearningProgramMutation,
  useGetOnlineAdminProgramAssignmentsQuery,
  useCreateOnlineAdminProgramAssignmentMutation,
  useUpdateOnlineAdminProgramAssignmentMutation,
  useDeleteOnlineAdminProgramAssignmentMutation,
  useGetOnlineAdminKnowledgeSourcesQuery,
  useCreateOnlineAdminKnowledgeSourceMutation,
  useUpdateOnlineAdminKnowledgeSourceMutation,
  useDeleteOnlineAdminKnowledgeSourceMutation,
  useGetOnlineAdminKnowledgeDocumentsQuery,
  useCreateOnlineAdminKnowledgeDocumentMutation,
  useUpdateOnlineAdminKnowledgeDocumentMutation,
  useDeleteOnlineAdminKnowledgeDocumentMutation,
  useGetOnlineAdminScopeAssignmentsQuery,
  useGetOnlineAdminUsersQuery,
  useGetOnlineAdminCuratorsQuery,
  useCreateOnlineAdminScopeAssignmentMutation,
  useUpdateOnlineAdminScopeAssignmentMutation,
  useDeleteOnlineAdminScopeAssignmentMutation,
  useUpdateOnlineAdminUserStatusMutation,
  useResetOnlineAdminUserTemporaryPasswordMutation,
  useCreateOnlineAdminCuratorMutation,
  useOnboardOnlineAdminCuratorMutation,
  useUpdateOnlineAdminCuratorMutation,
  useDeleteOnlineAdminCuratorMutation,
  useAssignOnlineAdminCohortCuratorMutation,
  useUpdateOnlineSessionStatusMutation,
  useOpenOnlineAdminSessionMutation,
  useEndOnlineAdminSessionMutation,
  useSyncOnlineAdminSessionAttendanceMutation,
  useRunOnlineAdminSessionBulkActionMutation,
} = onlineService;
