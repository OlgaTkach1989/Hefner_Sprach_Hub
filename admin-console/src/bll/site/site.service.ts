import { baseApi } from "@/bll/base-api";
import type {
  OnlineAdminWorkspaceContentItemListResponse,
  OnlineAdminWorkspaceContentItemUpsertInput,
  OnlineAdminWorkspaceListResponse,
  OnlineAdminWorkspaceUpsertInput,
} from "./site.type";

export const siteService = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getOnlineAdminWorkspaces: builder.query<OnlineAdminWorkspaceListResponse, void>({
      query: () => ({
        url: "/online/admin/workspaces/",
        method: "GET",
      }),
      providesTags: (result) =>
        result
          ? [
              { type: "OnlineAdminWorkspace", id: "LIST" },
              ...result.results.map((item) => ({ type: "OnlineAdminWorkspace" as const, id: item.id })),
            ]
          : [{ type: "OnlineAdminWorkspace", id: "LIST" }],
    }),
    createOnlineAdminWorkspace: builder.mutation<
      OnlineAdminWorkspaceListResponse["results"][number],
      OnlineAdminWorkspaceUpsertInput
    >({
      query: (body) => ({
        url: "/online/admin/workspaces/",
        method: "POST",
        body,
      }),
      invalidatesTags: [{ type: "OnlineAdminWorkspace", id: "LIST" }],
    }),
    updateOnlineAdminWorkspace: builder.mutation<
      OnlineAdminWorkspaceListResponse["results"][number],
      { workspaceId: number; body: Partial<OnlineAdminWorkspaceUpsertInput> }
    >({
      query: ({ workspaceId, body }) => ({
        url: `/online/admin/workspaces/${workspaceId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { workspaceId }) => [
        { type: "OnlineAdminWorkspace", id: "LIST" },
        { type: "OnlineAdminWorkspace", id: workspaceId },
      ],
    }),
    deleteOnlineAdminWorkspace: builder.mutation<void, number>({
      query: (workspaceId) => ({
        url: `/online/admin/workspaces/${workspaceId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [
        { type: "OnlineAdminWorkspace", id: "LIST" },
        { type: "OnlineAdminWorkspaceContent", id: "LIST" },
      ],
    }),
    getOnlineAdminWorkspaceItems: builder.query<
      OnlineAdminWorkspaceContentItemListResponse,
      { workspaceId: number; section?: string }
    >({
      query: (args) => ({
        url: `/online/admin/workspaces/${args.workspaceId}/items/`,
        method: "GET",
        params: args?.section ? { section: args.section } : undefined,
      }),
      providesTags: (result) =>
        result
          ? [
              { type: "OnlineAdminWorkspaceContent", id: "LIST" },
              ...result.results.map((item) => ({ type: "OnlineAdminWorkspaceContent" as const, id: item.id })),
            ]
          : [{ type: "OnlineAdminWorkspaceContent", id: "LIST" }],
    }),
    createOnlineAdminWorkspaceItem: builder.mutation<
      OnlineAdminWorkspaceContentItemListResponse["results"][number],
      { workspaceId: number; body: OnlineAdminWorkspaceContentItemUpsertInput }
    >({
      query: ({ workspaceId, body }) => ({
        url: `/online/admin/workspaces/${workspaceId}/items/`,
        method: "POST",
        body,
      }),
      invalidatesTags: [
        { type: "OnlineAdminWorkspace", id: "LIST" },
        { type: "OnlineAdminWorkspaceContent", id: "LIST" },
      ],
    }),
    updateOnlineAdminWorkspaceItem: builder.mutation<
      OnlineAdminWorkspaceContentItemListResponse["results"][number],
      { itemId: number; body: Partial<OnlineAdminWorkspaceContentItemUpsertInput> }
    >({
      query: ({ itemId, body }) => ({
        url: `/online/admin/workspace-items/${itemId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { itemId }) => [
        { type: "OnlineAdminWorkspace", id: "LIST" },
        { type: "OnlineAdminWorkspaceContent", id: "LIST" },
        { type: "OnlineAdminWorkspaceContent", id: itemId },
      ],
    }),
    deleteOnlineAdminWorkspaceItem: builder.mutation<void, number>({
      query: (itemId) => ({
        url: `/online/admin/workspace-items/${itemId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [
        { type: "OnlineAdminWorkspace", id: "LIST" },
        { type: "OnlineAdminWorkspaceContent", id: "LIST" },
      ],
    }),
  }),
});

export const {
  useGetOnlineAdminWorkspacesQuery,
  useCreateOnlineAdminWorkspaceMutation,
  useUpdateOnlineAdminWorkspaceMutation,
  useDeleteOnlineAdminWorkspaceMutation,
  useGetOnlineAdminWorkspaceItemsQuery,
  useCreateOnlineAdminWorkspaceItemMutation,
  useUpdateOnlineAdminWorkspaceItemMutation,
  useDeleteOnlineAdminWorkspaceItemMutation,
} = siteService;
