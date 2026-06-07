import {
  createApi,
  fetchBaseQuery,
  type BaseQueryFn,
  type FetchArgs,
  type FetchBaseQueryError,
} from "@reduxjs/toolkit/query/react";

import { apiRootUrl } from "../api/apiUrls";
import { clearTokens, getCsrfToken } from "../api/authStorage";

const createBaseQuery = () =>
  fetchBaseQuery({
    baseUrl: apiRootUrl,
    credentials: "include",
    prepareHeaders: (headers) => {
      headers.set("X-Online-Auth-Scope", "staff");
      const csrfToken = getCsrfToken();
      if (csrfToken) {
        headers.set("X-CSRFToken", csrfToken);
      }
      return headers;
    },
  });

const rawBaseQuery = createBaseQuery();
const refreshBaseQuery = createBaseQuery();

const shouldSkipRefresh = (args: string | FetchArgs) => {
  const url = typeof args === "string" ? args : String(args.url ?? "");
  return ["/online/staff/auth/login/", "/online/staff/auth/refresh/", "/online/staff/auth/logout/"].some((prefix) =>
    url.includes(prefix),
  );
};

const baseQueryWithReauth: BaseQueryFn<string | FetchArgs, unknown, FetchBaseQueryError> = async (
  args,
  api,
  extraOptions,
) => {
  let result = await rawBaseQuery(args, api, extraOptions);

  if (result.error?.status === 401 && !shouldSkipRefresh(args)) {
    const refreshResult = await refreshBaseQuery(
      {
        url: "/online/staff/auth/refresh/",
        method: "POST",
        body: {},
      },
      api,
      extraOptions,
    );

    if (refreshResult.error) {
      clearTokens();
      return result;
    }

    result = await rawBaseQuery(args, api, extraOptions);
  }

  return result;
};

export const baseApi = createApi({
  reducerPath: "onlineAdminApi",
  tagTypes: [
    "TrainingAudience",
    "TrainingCourseRoleAssignment",
    "TrainingUserAudienceGrant",
    "TrainingAdminOverview",
    "TrainingContentGovernance",
    "TrainingAdminAiOverview",
    "TrainingAdminAiConversationQueue",
    "TrainingAdminAiAnalytics",
    "TrainingNotebookAssignment",
    "TrainingAdminReportsOverview",
    "TrainingAdminAuditEvents",
    "TrainingAdminContentSyncEvents",
    "TrainingAdminGraderJobs",
    "OnlineAdminUserDirectory",
    "OnlineAdminCurator",
    "OnlineAdminCohortDirectory",
    "OnlineAdminSessionDirectory",
    "OnlineAdminScopeAssignment",
    "OnlineAdminEnterpriseSummary",
    "OnlineAdminCatalogSearch",
    "OnlineAdminCatalogAttribute",
    "OnlineAdminCatalogAttributeValue",
    "OnlineAdminStudentProfile",
    "OnlineAdminInstructorProfile",
    "OnlineAdminExternalProvider",
    "OnlineAdminLearningProgram",
    "OnlineAdminProgramAssignment",
    "OnlineAdminKnowledgeSource",
    "OnlineAdminKnowledgeDocument",
    "OnlineAdminWorkspace",
    "OnlineAdminWorkspaceContent",
    "CourseBuilderTemplate",
    "CourseBuilderLibraryItem",
    "CourseBuilderNotebook",
    "CourseBuilderCourse",
  ],
  baseQuery: baseQueryWithReauth,
  endpoints: () => ({}),
});
