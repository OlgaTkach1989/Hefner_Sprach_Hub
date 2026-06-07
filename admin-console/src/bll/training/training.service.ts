import { baseApi } from "@/bll/base-api";
import type {
  TrainingAdminAudience,
  TrainingAdminAssetClass,
  TrainingAdminAiConversation,
  TrainingAdminAiConversationPatchInput,
  TrainingAdminAiAnalytics,
  TrainingAdminAuditEvent,
  TrainingAdminAiOverview,
  TrainingAdminAiRebuildIndexInput,
  TrainingAdminAiRebuildIndexResult,
  TrainingAdminAudiencePatchInput,
  TrainingAdminAudienceWriteInput,
  TrainingAdminContentSyncEvent,
  TrainingAdminCourseRoleAssignment,
  TrainingAdminCourseRoleAssignmentPatchInput,
  TrainingAdminCourseRoleAssignmentWriteInput,
  TrainingAdminGraderJob,
  TrainingAdminListResponse,
  TrainingAdminNotebookAssignment,
  TrainingAdminNotebookAssignmentWriteInput,
  TrainingAdminNotebookUploadResponse,
  TrainingAdminOverview,
  TrainingAdminReportsOverview,
  TrainingAdminTopic,
  TrainingContentGovernanceItem,
  TrainingContentKind,
  TrainingContentStatus,
  TrainingAdminUserAudienceGrant,
  TrainingAdminUserAudienceGrantPatchInput,
  TrainingAdminUserAudienceGrantWriteInput,
} from "./training.type";

type TrainingAdminOverviewArgs = {
  courseId?: number;
};

type TrainingAdminAudiencesArgs = {
  q?: string;
};

type TrainingAdminCourseRoleAssignmentsArgs = {
  courseId?: number;
  userId?: number;
  role?: "owner" | "reviewer" | "instructor";
  q?: string;
};

type TrainingAdminContentGovernanceArgs = {
  courseId?: number;
  missingOnly?: boolean;
  status?: TrainingContentStatus;
  kind?: TrainingContentKind;
  q?: string;
};

type TrainingAdminNotebookAssignmentsArgs = {
  courseId?: number;
  status?: TrainingContentStatus;
  q?: string;
};

type TrainingAdminAiConversationsArgs = {
  courseId?: number;
  includeResolved?: boolean;
  limit?: number;
};

type TrainingAdminReportsQueryArgs = {
  courseId?: number;
  limit?: number;
  q?: string;
};

type TrainingAdminAuditEventsArgs = TrainingAdminReportsQueryArgs & {
  outcome?: "succeeded" | "denied" | "failed";
  category?: "content" | "entitlement" | "lab" | "grading" | "admin" | "ai";
};

type TrainingAdminContentSyncEventsArgs = TrainingAdminReportsQueryArgs & {
  status?: "succeeded" | "failed";
};

type TrainingAdminGraderJobsArgs = TrainingAdminReportsQueryArgs & {
  status?: "queued" | "running" | "succeeded" | "failed";
};

export const trainingService = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getTrainingAdminOverview: builder.query<TrainingAdminOverview, TrainingAdminOverviewArgs | void>({
      query: (args) => ({
        url: "/training/admin/overview/",
        method: "GET",
        params: args?.courseId ? { course_id: args.courseId } : undefined,
      }),
      providesTags: [{ type: "TrainingAdminOverview", id: "GLOBAL" }],
    }),
    getTrainingAdminAudiences: builder.query<TrainingAdminListResponse<TrainingAdminAudience>, TrainingAdminAudiencesArgs | void>({
      query: (args) => ({
        url: "/training/admin/audiences/",
        method: "GET",
        params: args?.q ? { q: args.q } : undefined,
      }),
      providesTags: (result) =>
        result
          ? [
              { type: "TrainingAudience" as const, id: "LIST" },
              ...result.results.map((item) => ({ type: "TrainingAudience" as const, id: item.id })),
            ]
          : [{ type: "TrainingAudience" as const, id: "LIST" }],
    }),
    getTrainingAdminAssetClasses: builder.query<TrainingAdminListResponse<TrainingAdminAssetClass>, void>({
      query: () => ({
        url: "/training/admin/asset-classes/",
        method: "GET",
      }),
    }),
    getTrainingAdminTopics: builder.query<TrainingAdminListResponse<TrainingAdminTopic>, void>({
      query: () => ({
        url: "/training/admin/topics/",
        method: "GET",
      }),
    }),
    createTrainingAdminAudience: builder.mutation<TrainingAdminAudience, TrainingAdminAudienceWriteInput>({
      query: (body) => ({
        url: "/training/admin/audiences/",
        method: "POST",
        body,
      }),
      invalidatesTags: [
        { type: "TrainingAudience", id: "LIST" },
        { type: "TrainingAdminOverview", id: "GLOBAL" },
      ],
    }),
    updateTrainingAdminAudience: builder.mutation<
      TrainingAdminAudience,
      { audienceId: number; body: TrainingAdminAudiencePatchInput }
    >({
      query: ({ audienceId, body }) => ({
        url: `/training/admin/audiences/${audienceId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { audienceId }) => [
        { type: "TrainingAudience", id: audienceId },
        { type: "TrainingAudience", id: "LIST" },
        { type: "TrainingAdminOverview", id: "GLOBAL" },
      ],
    }),
    deleteTrainingAdminAudience: builder.mutation<void, number>({
      query: (audienceId) => ({
        url: `/training/admin/audiences/${audienceId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [
        { type: "TrainingAudience", id: "LIST" },
        { type: "TrainingAdminOverview", id: "GLOBAL" },
      ],
    }),
    getTrainingAdminCourseRoleAssignments: builder.query<
      TrainingAdminListResponse<TrainingAdminCourseRoleAssignment>,
      TrainingAdminCourseRoleAssignmentsArgs | void
    >({
      query: (args) => ({
        url: "/training/admin/course-role-assignments/",
        method: "GET",
        params: {
          ...(args?.courseId ? { course_id: args.courseId } : {}),
          ...(args?.userId ? { user_id: args.userId } : {}),
          ...(args?.role ? { role: args.role } : {}),
          ...(args?.q ? { q: args.q } : {}),
        },
      }),
      providesTags: (result) =>
        result
          ? [
              { type: "TrainingCourseRoleAssignment" as const, id: "LIST" },
              ...result.results.map((item) => ({ type: "TrainingCourseRoleAssignment" as const, id: item.id })),
            ]
          : [{ type: "TrainingCourseRoleAssignment" as const, id: "LIST" }],
    }),
    createTrainingAdminCourseRoleAssignment: builder.mutation<
      TrainingAdminCourseRoleAssignment,
      TrainingAdminCourseRoleAssignmentWriteInput
    >({
      query: (body) => ({
        url: "/training/admin/course-role-assignments/",
        method: "POST",
        body,
      }),
      invalidatesTags: [
        { type: "TrainingCourseRoleAssignment", id: "LIST" },
        { type: "TrainingAdminOverview", id: "GLOBAL" },
      ],
    }),
    updateTrainingAdminCourseRoleAssignment: builder.mutation<
      TrainingAdminCourseRoleAssignment,
      { assignmentId: number; body: TrainingAdminCourseRoleAssignmentPatchInput }
    >({
      query: ({ assignmentId, body }) => ({
        url: `/training/admin/course-role-assignments/${assignmentId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { assignmentId }) => [
        { type: "TrainingCourseRoleAssignment", id: assignmentId },
        { type: "TrainingCourseRoleAssignment", id: "LIST" },
        { type: "TrainingAdminOverview", id: "GLOBAL" },
      ],
    }),
    deleteTrainingAdminCourseRoleAssignment: builder.mutation<void, number>({
      query: (assignmentId) => ({
        url: `/training/admin/course-role-assignments/${assignmentId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [
        { type: "TrainingCourseRoleAssignment", id: "LIST" },
        { type: "TrainingAdminOverview", id: "GLOBAL" },
      ],
    }),
    getTrainingAdminContentGovernance: builder.query<
      TrainingAdminListResponse<TrainingContentGovernanceItem>,
      TrainingAdminContentGovernanceArgs | void
    >({
      query: (args) => ({
        url: "/training/admin/content/",
        method: "GET",
        params: {
          ...(args?.courseId ? { course_id: args.courseId } : {}),
          ...(args?.missingOnly ? { missing_only: 1 } : {}),
          ...(args?.status ? { status: args.status } : {}),
          ...(args?.kind ? { kind: args.kind } : {}),
          ...(args?.q ? { q: args.q } : {}),
        },
      }),
      providesTags: [{ type: "TrainingContentGovernance", id: "GLOBAL" }],
    }),
    getTrainingAdminNotebookAssignments: builder.query<
      TrainingAdminListResponse<TrainingAdminNotebookAssignment>,
      TrainingAdminNotebookAssignmentsArgs | void
    >({
      query: (args) => ({
        url: "/training/admin/notebook-assignments/",
        method: "GET",
        params: {
          ...(args?.courseId ? { course_id: args.courseId } : {}),
          ...(args?.status ? { status: args.status } : {}),
          ...(args?.q ? { q: args.q } : {}),
        },
      }),
      providesTags: (result) =>
        result
          ? [
              { type: "TrainingNotebookAssignment" as const, id: "LIST" },
              ...result.results.map((item) => ({ type: "TrainingNotebookAssignment" as const, id: item.id })),
            ]
          : [{ type: "TrainingNotebookAssignment" as const, id: "LIST" }],
    }),
    createTrainingAdminNotebookAssignment: builder.mutation<
      TrainingAdminNotebookAssignment,
      TrainingAdminNotebookAssignmentWriteInput
    >({
      query: (body) => ({
        url: "/training/admin/notebook-assignments/",
        method: "POST",
        body,
      }),
      invalidatesTags: [
        { type: "TrainingNotebookAssignment", id: "LIST" },
        { type: "TrainingContentGovernance", id: "GLOBAL" },
        { type: "TrainingAdminAiOverview", id: "GLOBAL" },
      ],
    }),
    updateTrainingAdminNotebookAssignment: builder.mutation<
      TrainingAdminNotebookAssignment,
      { contentId: number; body: TrainingAdminNotebookAssignmentWriteInput }
    >({
      query: ({ contentId, body }) => ({
        url: `/training/admin/notebook-assignments/${contentId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { contentId }) => [
        { type: "TrainingNotebookAssignment", id: contentId },
        { type: "TrainingNotebookAssignment", id: "LIST" },
        { type: "TrainingContentGovernance", id: "GLOBAL" },
        { type: "TrainingAdminAiOverview", id: "GLOBAL" },
      ],
    }),
    deleteTrainingAdminNotebookAssignment: builder.mutation<void, number>({
      query: (contentId) => ({
        url: `/training/admin/notebook-assignments/${contentId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [
        { type: "TrainingNotebookAssignment", id: "LIST" },
        { type: "TrainingContentGovernance", id: "GLOBAL" },
        { type: "TrainingAdminAiOverview", id: "GLOBAL" },
      ],
    }),
    uploadTrainingAdminNotebookStarter: builder.mutation<
      TrainingAdminNotebookUploadResponse,
      { contentSlug: string; notebook: File }
    >({
      query: ({ contentSlug, notebook }) => {
        const formData = new FormData();
        formData.append("content_slug", contentSlug);
        formData.append("notebook", notebook);
        return {
          url: "/training/admin/notebook-assignments/upload-starter/",
          method: "POST",
          body: formData,
        };
      },
    }),
    getTrainingAdminAiOverview: builder.query<TrainingAdminAiOverview, TrainingAdminOverviewArgs | void>({
      query: (args) => ({
        url: "/training/admin/ai/overview/",
        method: "GET",
        params: args?.courseId ? { course_id: args.courseId } : undefined,
      }),
      providesTags: [{ type: "TrainingAdminAiOverview", id: "GLOBAL" }],
    }),
    getTrainingAdminAiAnalytics: builder.query<
      TrainingAdminAiAnalytics,
      (TrainingAdminOverviewArgs & { windowDays?: number }) | void
    >({
      query: (args) => ({
        url: "/training/admin/ai/analytics/",
        method: "GET",
        params: {
          ...(args?.courseId ? { course_id: args.courseId } : {}),
          ...(args?.windowDays ? { window_days: args.windowDays } : {}),
        },
      }),
      providesTags: [{ type: "TrainingAdminAiAnalytics", id: "GLOBAL" }],
    }),
    getTrainingAdminReportsOverview: builder.query<TrainingAdminReportsOverview, TrainingAdminOverviewArgs | void>({
      query: (args) => ({
        url: "/training/admin/reports/overview/",
        method: "GET",
        params: args?.courseId ? { course_id: args.courseId } : undefined,
      }),
      providesTags: [{ type: "TrainingAdminReportsOverview", id: "GLOBAL" }],
    }),
    getTrainingAdminAuditEvents: builder.query<
      TrainingAdminListResponse<TrainingAdminAuditEvent>,
      TrainingAdminAuditEventsArgs | void
    >({
      query: (args) => ({
        url: "/training/admin/reports/audit-events/",
        method: "GET",
        params: {
          ...(args?.courseId ? { course_id: args.courseId } : {}),
          ...(args?.outcome ? { outcome: args.outcome } : {}),
          ...(args?.category ? { category: args.category } : {}),
          ...(args?.q ? { q: args.q } : {}),
          ...(args?.limit ? { limit: args.limit } : {}),
        },
      }),
      providesTags: [{ type: "TrainingAdminAuditEvents", id: "GLOBAL" }],
    }),
    getTrainingAdminContentSyncEvents: builder.query<
      TrainingAdminListResponse<TrainingAdminContentSyncEvent>,
      TrainingAdminContentSyncEventsArgs | void
    >({
      query: (args) => ({
        url: "/training/admin/reports/sync-events/",
        method: "GET",
        params: {
          ...(args?.courseId ? { course_id: args.courseId } : {}),
          ...(args?.status ? { status: args.status } : {}),
          ...(args?.q ? { q: args.q } : {}),
          ...(args?.limit ? { limit: args.limit } : {}),
        },
      }),
      providesTags: [{ type: "TrainingAdminContentSyncEvents", id: "GLOBAL" }],
    }),
    getTrainingAdminGraderJobs: builder.query<
      TrainingAdminListResponse<TrainingAdminGraderJob>,
      TrainingAdminGraderJobsArgs | void
    >({
      query: (args) => ({
        url: "/training/admin/reports/grader-jobs/",
        method: "GET",
        params: {
          ...(args?.courseId ? { course_id: args.courseId } : {}),
          ...(args?.status ? { status: args.status } : {}),
          ...(args?.q ? { q: args.q } : {}),
          ...(args?.limit ? { limit: args.limit } : {}),
        },
      }),
      providesTags: [{ type: "TrainingAdminGraderJobs", id: "GLOBAL" }],
    }),
    getTrainingAdminAiConversations: builder.query<
      TrainingAdminListResponse<TrainingAdminAiConversation>,
      TrainingAdminAiConversationsArgs | void
    >({
      query: (args) => ({
        url: "/training/admin/ai/conversations/",
        method: "GET",
        params: {
          ...(args?.courseId ? { course_id: args.courseId } : {}),
          ...(args?.includeResolved ? { include_resolved: 1 } : {}),
          ...(args?.limit ? { limit: args.limit } : {}),
        },
      }),
      providesTags: (result) =>
        result
          ? [
              { type: "TrainingAdminAiConversationQueue" as const, id: "LIST" },
              ...result.results.map((item) => ({ type: "TrainingAdminAiConversationQueue" as const, id: item.publicId })),
            ]
          : [{ type: "TrainingAdminAiConversationQueue" as const, id: "LIST" }],
    }),
    updateTrainingAdminAiConversation: builder.mutation<
      TrainingAdminAiConversation,
      { conversationPublicId: string; body: TrainingAdminAiConversationPatchInput }
    >({
      query: ({ conversationPublicId, body }) => ({
        url: `/training/admin/ai/conversations/${conversationPublicId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { conversationPublicId }) => [
        { type: "TrainingAdminAiConversationQueue", id: conversationPublicId },
        { type: "TrainingAdminAiConversationQueue", id: "LIST" },
        { type: "TrainingAdminAiOverview", id: "GLOBAL" },
        { type: "TrainingAdminAiAnalytics", id: "GLOBAL" },
      ],
    }),
    rebuildTrainingAdminAiIndex: builder.mutation<
      TrainingAdminAiRebuildIndexResult,
      TrainingAdminAiRebuildIndexInput
    >({
      query: (body) => ({
        url: "/training/admin/ai/rebuild-index/",
        method: "POST",
        body,
      }),
      invalidatesTags: [
        { type: "TrainingAdminAiOverview", id: "GLOBAL" },
        { type: "TrainingAdminAiAnalytics", id: "GLOBAL" },
        { type: "TrainingAdminAiConversationQueue", id: "LIST" },
        { type: "TrainingContentGovernance", id: "GLOBAL" },
      ],
    }),
    getTrainingAdminUserAudienceGrants: builder.query<
      TrainingAdminListResponse<TrainingAdminUserAudienceGrant>,
      { q?: string; activeOnly?: boolean; userId?: number } | void
    >({
      query: (args) => ({
        url: "/training/admin/user-audience-grants/",
        method: "GET",
        params: {
          ...(args?.q ? { q: args.q } : {}),
          ...(args?.activeOnly ? { active_only: 1 } : {}),
          ...(args?.userId ? { user_id: args.userId } : {}),
        },
      }),
      providesTags: (result) =>
        result
          ? [
              { type: "TrainingUserAudienceGrant" as const, id: "LIST" },
              ...result.results.map((item) => ({ type: "TrainingUserAudienceGrant" as const, id: item.id })),
            ]
          : [{ type: "TrainingUserAudienceGrant" as const, id: "LIST" }],
    }),
    createTrainingAdminUserAudienceGrant: builder.mutation<
      TrainingAdminUserAudienceGrant,
      TrainingAdminUserAudienceGrantWriteInput
    >({
      query: (body) => ({
        url: "/training/admin/user-audience-grants/",
        method: "POST",
        body,
      }),
      invalidatesTags: [
        { type: "TrainingUserAudienceGrant", id: "LIST" },
        { type: "TrainingAudience", id: "LIST" },
        { type: "TrainingAdminOverview", id: "GLOBAL" },
      ],
    }),
    updateTrainingAdminUserAudienceGrant: builder.mutation<
      TrainingAdminUserAudienceGrant,
      { grantId: number; body: TrainingAdminUserAudienceGrantPatchInput }
    >({
      query: ({ grantId, body }) => ({
        url: `/training/admin/user-audience-grants/${grantId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { grantId }) => [
        { type: "TrainingUserAudienceGrant", id: grantId },
        { type: "TrainingUserAudienceGrant", id: "LIST" },
        { type: "TrainingAdminOverview", id: "GLOBAL" },
      ],
    }),
    deleteTrainingAdminUserAudienceGrant: builder.mutation<void, number>({
      query: (grantId) => ({
        url: `/training/admin/user-audience-grants/${grantId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [
        { type: "TrainingUserAudienceGrant", id: "LIST" },
        { type: "TrainingAdminOverview", id: "GLOBAL" },
      ],
    }),
  }),
});

export const {
  useGetTrainingAdminAiAnalyticsQuery,
  useGetTrainingAdminAuditEventsQuery,
  useGetTrainingAdminAiConversationsQuery,
  useGetTrainingAdminAiOverviewQuery,
  useGetTrainingAdminAssetClassesQuery,
  useCreateTrainingAdminAudienceMutation,
  useCreateTrainingAdminCourseRoleAssignmentMutation,
  useCreateTrainingAdminUserAudienceGrantMutation,
  useRebuildTrainingAdminAiIndexMutation,
  useUpdateTrainingAdminAiConversationMutation,
  useDeleteTrainingAdminAudienceMutation,
  useDeleteTrainingAdminCourseRoleAssignmentMutation,
  useDeleteTrainingAdminUserAudienceGrantMutation,
  useGetTrainingAdminAudiencesQuery,
  useGetTrainingAdminContentSyncEventsQuery,
  useGetTrainingAdminContentGovernanceQuery,
  useGetTrainingAdminCourseRoleAssignmentsQuery,
  useGetTrainingAdminGraderJobsQuery,
  useGetTrainingAdminNotebookAssignmentsQuery,
  useGetTrainingAdminOverviewQuery,
  useGetTrainingAdminReportsOverviewQuery,
  useGetTrainingAdminTopicsQuery,
  useGetTrainingAdminUserAudienceGrantsQuery,
  useCreateTrainingAdminNotebookAssignmentMutation,
  useDeleteTrainingAdminNotebookAssignmentMutation,
  useUploadTrainingAdminNotebookStarterMutation,
  useUpdateTrainingAdminAudienceMutation,
  useUpdateTrainingAdminCourseRoleAssignmentMutation,
  useUpdateTrainingAdminNotebookAssignmentMutation,
  useUpdateTrainingAdminUserAudienceGrantMutation,
} = trainingService;
