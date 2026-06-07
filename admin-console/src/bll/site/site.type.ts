export type OnlineAdminWorkspaceKind = "group" | "shared";

export type OnlineAdminWorkspaceSection =
  | "courses"
  | "assignments"
  | "recordings"
  | "materials";

export type OnlineAdminWorkspaceSummary = {
  id: number;
  slug: string;
  title: string;
  subtitle: string;
  summary: string;
  iconKey: string;
  kind: OnlineAdminWorkspaceKind;
  sortOrder: number;
  showOnHomepage: boolean;
  isPublished: boolean;
  audienceIds: number[];
  audiences: Array<{
    id: number;
    slug: string;
    name: string;
    shortLabel: string;
  }>;
  activeItemsCount: number;
  sectionCounts: Record<OnlineAdminWorkspaceSection, number>;
};

export type OnlineAdminWorkspaceListResponse = {
  results: OnlineAdminWorkspaceSummary[];
};

export type OnlineAdminWorkspaceUpsertInput = {
  slug: string;
  title: string;
  subtitle: string;
  summary: string;
  iconKey: string;
  kind: OnlineAdminWorkspaceKind;
  sortOrder: number;
  showOnHomepage: boolean;
  isPublished: boolean;
  audienceIds?: number[];
};

export type OnlineAdminWorkspaceContentItem = {
  id: number;
  workspaceId: number;
  section: OnlineAdminWorkspaceSection;
  title: string;
  description: string;
  previewImageUrl: string;
  assetUrl: string;
  linkedCourseId: number | null;
  linkedCourseSlug: string;
  linkedCohortId: number | null;
  linkedCohortCode: string;
  audienceIds: number[];
  audiences: Array<{
    id: number;
    slug: string;
    name: string;
    shortLabel: string;
  }>;
  primaryMeta: string;
  secondaryMeta: string;
  publishedOn: string | null;
  sortOrder: number;
  isActive: boolean;
};

export type OnlineAdminWorkspaceContentItemListResponse = {
  results: OnlineAdminWorkspaceContentItem[];
};

export type OnlineAdminWorkspaceContentItemUpsertInput = {
  section: OnlineAdminWorkspaceSection;
  title: string;
  description: string;
  previewImageUrl: string;
  assetUrl: string;
  linkedCourseId?: number | null;
  linkedCohortId?: number | null;
  audienceIds?: number[];
  primaryMeta: string;
  secondaryMeta: string;
  publishedOn: string | null;
  sortOrder: number;
  isActive: boolean;
};
