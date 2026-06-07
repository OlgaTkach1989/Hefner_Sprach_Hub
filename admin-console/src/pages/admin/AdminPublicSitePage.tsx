import { useDeferredValue, useEffect, useMemo, useState, type FormEvent } from "react";

import {
  useCreateOnlineAdminWorkspaceItemMutation,
  useCreateOnlineAdminWorkspaceMutation,
  useDeleteOnlineAdminWorkspaceItemMutation,
  useDeleteOnlineAdminWorkspaceMutation,
  useGetOnlineAdminWorkspaceItemsQuery,
  useGetOnlineAdminWorkspacesQuery,
  useUpdateOnlineAdminWorkspaceItemMutation,
  useUpdateOnlineAdminWorkspaceMutation,
} from "@/bll/site/site.service";
import { useGetOnlineCohortsQuery, useGetOnlineCoursesQuery } from "@/bll/online/online.service";
import type { OnlineCohortCard } from "@/bll/online/online.type";
import { useGetTrainingAdminAudiencesQuery } from "@/bll/training/training.service";
import type {
  OnlineAdminWorkspaceContentItem,
  OnlineAdminWorkspaceContentItemUpsertInput,
  OnlineAdminWorkspaceKind,
  OnlineAdminWorkspaceSection,
  OnlineAdminWorkspaceSummary,
  OnlineAdminWorkspaceUpsertInput,
} from "@/bll/site/site.type";
import DemoRolePolicyFieldset from "@/components/access/DemoRolePolicyFieldset";
import shared from "./AdminPagesShared.module.css";
import styles from "./AdminPublicSitePage.module.css";
import { courseDisplayTitle } from "./adminPageUtils";

type WorkspaceFormState = OnlineAdminWorkspaceUpsertInput;
type ItemFormState = OnlineAdminWorkspaceContentItemUpsertInput;

const EMPTY_WORKSPACE_FORM: WorkspaceFormState = {
  slug: "",
  title: "",
  subtitle: "",
  summary: "",
  iconKey: "berlin",
  kind: "group",
  sortOrder: 10,
  showOnHomepage: true,
  isPublished: true,
  audienceIds: [],
};

const EMPTY_ITEM_FORM: ItemFormState = {
  section: "courses",
  title: "",
  description: "",
  previewImageUrl: "",
  assetUrl: "",
  linkedCourseId: null,
  linkedCohortId: null,
  primaryMeta: "",
  secondaryMeta: "",
  publishedOn: null,
  sortOrder: 10,
  isActive: true,
  audienceIds: [],
};

const SECTION_OPTIONS: Array<{ value: OnlineAdminWorkspaceSection; label: string }> = [
  { value: "courses", label: "Courses" },
  { value: "assignments", label: "Assignments / Labs" },
  { value: "recordings", label: "Video recordings" },
  { value: "materials", label: "Educational materials" },
];

const ICON_OPTIONS = [
  "berlin",
  "new_york",
  "london",
  "prague",
  "paris",
  "vienna",
  "it",
  "finance",
  "academy",
];

const errorMessageFrom = (error: unknown, fallback: string) => {
  if (!error || typeof error !== "object" || !("data" in error)) return fallback;
  const payload = (error as { data?: unknown }).data;
  if (!payload || typeof payload !== "object") return fallback;
  const objectPayload = payload as Record<string, unknown>;
  if (typeof objectPayload.detail === "string") return objectPayload.detail;
  for (const value of Object.values(objectPayload)) {
    if (typeof value === "string") return value;
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
  }
  return fallback;
};

const slugify = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

const workspaceFormFrom = (workspace: OnlineAdminWorkspaceSummary): WorkspaceFormState => ({
  slug: workspace.slug,
  title: workspace.title,
  subtitle: workspace.subtitle,
  summary: workspace.summary,
  iconKey: workspace.iconKey,
  kind: workspace.kind,
  sortOrder: workspace.sortOrder,
  showOnHomepage: workspace.showOnHomepage,
  isPublished: workspace.isPublished,
  audienceIds: workspace.audienceIds ?? [],
});

const itemFormFrom = (item: OnlineAdminWorkspaceContentItem): ItemFormState => ({
  section: item.section,
  title: item.title,
  description: item.description,
  previewImageUrl: item.previewImageUrl,
  assetUrl: item.assetUrl,
  linkedCourseId: item.linkedCourseId,
  linkedCohortId: item.linkedCohortId,
  primaryMeta: item.primaryMeta,
  secondaryMeta: item.secondaryMeta,
  publishedOn: item.publishedOn,
  sortOrder: item.sortOrder,
  isActive: item.isActive,
  audienceIds: item.audienceIds ?? [],
});

const metaLabelsFor = (section: OnlineAdminWorkspaceSection) => {
  if (section === "courses") {
    return {
      preview: "Cover image URL",
      asset: "Optional destination URL",
      primary: "Duration / primary badge",
      secondary: "Format / secondary badge",
      date: "Optional publish date",
    };
  }
  if (section === "assignments") {
    return {
      preview: "Optional cover image URL",
      asset: "Notebook or reference URL",
      primary: "Notebook label",
      secondary: "Difficulty",
      date: "Optional publish date",
    };
  }
  if (section === "recordings") {
    return {
      preview: "Thumbnail image URL",
      asset: "Video URL",
      primary: "Primary label",
      secondary: "Duration",
      date: "Recording date",
    };
  }
  return {
    preview: "Optional preview image URL",
    asset: "Document URL",
    primary: "Category",
    secondary: "Secondary badge",
    date: "Publish date",
  };
};

const AdminPublicSitePage = () => {
  const [workspaceSearch, setWorkspaceSearch] = useState("");
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [workspaceForm, setWorkspaceForm] = useState<WorkspaceFormState>(EMPTY_WORKSPACE_FORM);
  const [isCreatingWorkspace, setIsCreatingWorkspace] = useState(false);
  const [workspaceMessage, setWorkspaceMessage] = useState<string | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);

  const [sectionFilter, setSectionFilter] = useState<OnlineAdminWorkspaceSection>("courses");
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null);
  const [itemForm, setItemForm] = useState<ItemFormState>(EMPTY_ITEM_FORM);
  const [isCreatingItem, setIsCreatingItem] = useState(true);
  const [itemMessage, setItemMessage] = useState<string | null>(null);
  const [itemError, setItemError] = useState<string | null>(null);

  const deferredWorkspaceSearch = useDeferredValue(workspaceSearch.trim().toLowerCase());

  const { data: workspaceData, isLoading: isWorkspacesLoading, isError: isWorkspacesError } =
    useGetOnlineAdminWorkspacesQuery();
  const { data: audienceData } = useGetTrainingAdminAudiencesQuery();
  const workspaces = workspaceData?.results ?? [];
  const audiences = audienceData?.results ?? [];

  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? null,
    [selectedWorkspaceId, workspaces],
  );

  const filteredWorkspaces = useMemo(
    () =>
      workspaces.filter((workspace) => {
        if (!deferredWorkspaceSearch) return true;
        return [workspace.title, workspace.subtitle, workspace.slug, workspace.summary, workspace.kind]
          .join(" ")
          .toLowerCase()
          .includes(deferredWorkspaceSearch);
      }),
    [deferredWorkspaceSearch, workspaces],
  );

  useEffect(() => {
    if (isCreatingWorkspace) return;
    if (selectedWorkspaceId === null && filteredWorkspaces.length > 0) {
      setSelectedWorkspaceId(filteredWorkspaces[0].id);
      return;
    }
    if (selectedWorkspaceId !== null && !workspaces.some((workspace) => workspace.id === selectedWorkspaceId)) {
      setSelectedWorkspaceId(filteredWorkspaces[0]?.id ?? null);
    }
  }, [filteredWorkspaces, isCreatingWorkspace, selectedWorkspaceId, workspaces]);

  useEffect(() => {
    if (selectedWorkspace && !isCreatingWorkspace) {
      setWorkspaceForm(workspaceFormFrom(selectedWorkspace));
      return;
    }
    if (!selectedWorkspace && !isCreatingWorkspace) {
      setWorkspaceForm(EMPTY_WORKSPACE_FORM);
    }
  }, [isCreatingWorkspace, selectedWorkspace]);

  const {
    data: workspaceItemsData,
    isLoading: isItemsLoading,
    isError: isItemsError,
  } = useGetOnlineAdminWorkspaceItemsQuery(
    { workspaceId: selectedWorkspaceId as number, section: sectionFilter },
    { skip: !selectedWorkspaceId },
  );

  const items = workspaceItemsData?.results ?? [];
  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedItemId) ?? null,
    [items, selectedItemId],
  );
  const { data: courseDirectory } = useGetOnlineCoursesQuery();
  const courseOptions = courseDirectory?.results ?? [];
  const { data: cohortDirectory } = useGetOnlineCohortsQuery(
    { courseId: itemForm.linkedCourseId as number },
    { skip: itemForm.section !== "courses" || !itemForm.linkedCourseId },
  );
  const cohortOptions = useMemo<OnlineCohortCard[]>(
    () =>
      (cohortDirectory?.results ?? []).filter(
        (cohort) => !itemForm.linkedCourseId || cohort.courseId === itemForm.linkedCourseId,
      ),
    [cohortDirectory?.results, itemForm.linkedCourseId],
  );

  useEffect(() => {
    if (selectedItem && !isCreatingItem) {
      setItemForm(itemFormFrom(selectedItem));
      return;
    }
    if (isCreatingItem) {
      setItemForm((current) => ({ ...EMPTY_ITEM_FORM, section: current.section }));
      return;
    }
    setItemForm((current) => ({ ...EMPTY_ITEM_FORM, section: current.section }));
  }, [isCreatingItem, selectedItem]);

  useEffect(() => {
    setSelectedItemId(null);
    setIsCreatingItem(true);
    setItemForm((current) => ({ ...EMPTY_ITEM_FORM, section: current.section }));
    setItemMessage(null);
    setItemError(null);
  }, [selectedWorkspaceId]);

  useEffect(() => {
    setSelectedItemId(null);
    setIsCreatingItem(true);
    setItemForm({ ...EMPTY_ITEM_FORM, section: sectionFilter });
    setItemMessage(null);
    setItemError(null);
  }, [sectionFilter]);

  useEffect(() => {
    if (itemForm.section !== "courses") {
      if (itemForm.linkedCourseId !== null || itemForm.linkedCohortId !== null) {
        setItemForm((current) => ({ ...current, linkedCourseId: null, linkedCohortId: null }));
      }
      return;
    }
    if (
      itemForm.linkedCohortId &&
      !cohortOptions.some((cohort) => cohort.id === itemForm.linkedCohortId)
    ) {
      setItemForm((current) => ({ ...current, linkedCohortId: null }));
    }
  }, [cohortOptions, itemForm.linkedCohortId, itemForm.linkedCourseId, itemForm.section]);

  const [createWorkspace, createWorkspaceState] = useCreateOnlineAdminWorkspaceMutation();
  const [updateWorkspace, updateWorkspaceState] = useUpdateOnlineAdminWorkspaceMutation();
  const [deleteWorkspace, deleteWorkspaceState] = useDeleteOnlineAdminWorkspaceMutation();
  const [createWorkspaceItem, createWorkspaceItemState] = useCreateOnlineAdminWorkspaceItemMutation();
  const [updateWorkspaceItem, updateWorkspaceItemState] = useUpdateOnlineAdminWorkspaceItemMutation();
  const [deleteWorkspaceItem, deleteWorkspaceItemState] = useDeleteOnlineAdminWorkspaceItemMutation();

  const groupsCount = workspaces.filter((workspace) => workspace.kind === "group").length;
  const sharedCount = workspaces.filter((workspace) => workspace.kind === "shared").length;
  const homeVisibleCount = workspaces.filter((workspace) => workspace.showOnHomepage && workspace.isPublished).length;
  const placeholderVisible = groupsCount < 9;
  const activeItemsCount = workspaces.reduce((sum, workspace) => sum + workspace.activeItemsCount, 0);

  const startCreatingWorkspace = (kind: OnlineAdminWorkspaceKind) => {
    const nextSortOrder = (workspaces[workspaces.length - 1]?.sortOrder ?? 0) + 10;
    setIsCreatingWorkspace(true);
    setSelectedWorkspaceId(null);
    setWorkspaceForm({
      ...EMPTY_WORKSPACE_FORM,
      kind,
      sortOrder: nextSortOrder,
      iconKey: kind === "shared" ? "academy" : "berlin",
    });
    setWorkspaceMessage(null);
    setWorkspaceError(null);
  };

  const selectWorkspace = (workspace: OnlineAdminWorkspaceSummary) => {
    setIsCreatingWorkspace(false);
    setSelectedWorkspaceId(workspace.id);
    setWorkspaceMessage(null);
    setWorkspaceError(null);
  };

  const startCreatingItem = () => {
    setSelectedItemId(null);
    setIsCreatingItem(true);
    setItemForm({
      ...EMPTY_ITEM_FORM,
      section: sectionFilter,
      sortOrder: (items[items.length - 1]?.sortOrder ?? 0) + 10,
    });
    setItemMessage(null);
    setItemError(null);
  };

  const selectItem = (item: OnlineAdminWorkspaceContentItem) => {
    setSelectedItemId(item.id);
    setIsCreatingItem(false);
    setItemMessage(null);
    setItemError(null);
  };

  const onSubmitWorkspace = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = {
      ...workspaceForm,
      slug: slugify(workspaceForm.slug || workspaceForm.title),
      title: workspaceForm.title.trim(),
      subtitle: workspaceForm.subtitle.trim(),
      summary: workspaceForm.summary.trim(),
      iconKey: workspaceForm.iconKey.trim(),
      audienceIds: workspaceForm.audienceIds ?? [],
    };

    if (!normalized.slug || !normalized.title) {
      setWorkspaceError("Title and slug are required.");
      setWorkspaceMessage(null);
      return;
    }

    setWorkspaceMessage(null);
    setWorkspaceError(null);

    try {
      if (isCreatingWorkspace || !selectedWorkspaceId) {
        const created = await createWorkspace(normalized).unwrap();
        setSelectedWorkspaceId(created.id);
        setIsCreatingWorkspace(false);
        setWorkspaceMessage("Section card created.");
      } else {
        const updated = await updateWorkspace({ workspaceId: selectedWorkspaceId, body: normalized }).unwrap();
        setSelectedWorkspaceId(updated.id);
        setWorkspaceMessage("Section card updated.");
      }
    } catch (error) {
      setWorkspaceError(errorMessageFrom(error, "Failed to save the section card."));
    }
  };

  const onDeleteWorkspace = async () => {
    if (!selectedWorkspaceId || !selectedWorkspace) return;
    if (!window.confirm(`Delete "${selectedWorkspace.title}" and all of its content items?`)) return;
    setWorkspaceMessage(null);
    setWorkspaceError(null);
    try {
      await deleteWorkspace(selectedWorkspaceId).unwrap();
      setWorkspaceMessage("Section card removed.");
      setSelectedWorkspaceId(null);
      setIsCreatingWorkspace(false);
    } catch (error) {
      setWorkspaceError(errorMessageFrom(error, "Failed to delete the section card."));
    }
  };

  const onSubmitItem = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedWorkspaceId) {
      setItemError("Select a section card first.");
      setItemMessage(null);
      return;
    }
    const normalized = {
      ...itemForm,
      title: itemForm.title.trim(),
      description: itemForm.description.trim(),
      previewImageUrl: itemForm.previewImageUrl.trim(),
      assetUrl: itemForm.assetUrl.trim(),
      primaryMeta: itemForm.primaryMeta.trim(),
      secondaryMeta: itemForm.secondaryMeta.trim(),
      audienceIds: itemForm.audienceIds ?? [],
    };
    if (!normalized.title) {
      setItemError("Content title is required.");
      setItemMessage(null);
      return;
    }
    setItemMessage(null);
    setItemError(null);
    try {
      if (isCreatingItem || !selectedItemId) {
        const created = await createWorkspaceItem({
          workspaceId: selectedWorkspaceId,
          body: normalized,
        }).unwrap();
        setSelectedItemId(created.id);
        setIsCreatingItem(false);
        setItemMessage("Content item created.");
      } else {
        const updated = await updateWorkspaceItem({
          itemId: selectedItemId,
          body: normalized,
        }).unwrap();
        setSelectedItemId(updated.id);
        setItemMessage("Content item updated.");
      }
    } catch (error) {
      setItemError(errorMessageFrom(error, "Failed to save the content item."));
    }
  };

  const onDeleteItem = async () => {
    if (!selectedItemId || !selectedItem) return;
    if (!window.confirm(`Delete "${selectedItem.title}"?`)) return;
    setItemMessage(null);
    setItemError(null);
    try {
      await deleteWorkspaceItem(selectedItemId).unwrap();
      setItemMessage("Content item removed.");
      startCreatingItem();
    } catch (error) {
      setItemError(errorMessageFrom(error, "Failed to delete the content item."));
    }
  };

  const currentMetaLabels = metaLabelsFor(itemForm.section);
  const selectedWorkspaceAudienceLabels = useMemo(
    () =>
      audiences
        .filter((audience) => workspaceForm.audienceIds?.includes(audience.id))
        .map((audience) => audience.short_label || audience.name),
    [audiences, workspaceForm.audienceIds],
  );
  const selectedItemAudienceLabels = useMemo(
    () =>
      audiences
        .filter((audience) => itemForm.audienceIds?.includes(audience.id))
        .map((audience) => audience.short_label || audience.name),
    [audiences, itemForm.audienceIds],
  );

  return (
    <div className={shared.page}>
      <section className={shared.hero}>
        <div className={shared.heroCopy}>
          <span className={shared.eyebrow}>Homepage control</span>
          <h1>Landing sections and shared academy library</h1>
          <p>
            Manage the cards shown on the public landing page, control which sections are published,
            and populate the dedicated content behind each group or shared academy resource hub.
          </p>
        </div>
        <div className={shared.heroMeta}>
          <span>{groupsCount} group sections</span>
          <span>{sharedCount} shared libraries</span>
          <span>{activeItemsCount} content items</span>
          <span>{homeVisibleCount} published cards on homepage</span>
        </div>
      </section>

      <section className={shared.kpiGrid}>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Landing section cards</span>
          <strong className={shared.kpiValue}>{groupsCount}</strong>
          <span className={shared.kpiMeta}>Visible group and domain cards that drive dedicated workspace pages.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Shared library blocks</span>
          <strong className={shared.kpiValue}>{sharedCount}</strong>
          <span className={shared.kpiMeta}>General academy content hubs used by the shared resources section.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Homepage placeholder</span>
          <strong className={shared.kpiValue}>{placeholderVisible ? "Visible" : "Hidden"}</strong>
          <span className={shared.kpiMeta}>A plus-card is shown automatically while fewer than 9 group cards are published.</span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Active content rows</span>
          <strong className={shared.kpiValue}>{activeItemsCount}</strong>
          <span className={shared.kpiMeta}>Published content powering courses, labs, recordings, and materials views.</span>
        </article>
      </section>

      {isWorkspacesError ? <p className={shared.errorText}>Failed to load public-site sections.</p> : null}

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Landing section cards</h2>
              <p>Choose a group or shared library to edit, or create a new block for the homepage.</p>
            </div>
            <span className={shared.sectionHint}>{filteredWorkspaces.length} visible</span>
          </header>

          <div className={styles.toolbarRow}>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Find card</span>
              <input
                type="search"
                className={shared.inlineInput}
                value={workspaceSearch}
                onChange={(event) => setWorkspaceSearch(event.currentTarget.value)}
                placeholder="Search by title, slug, or kind"
              />
            </label>
            <div className={styles.inlineActionGroup}>
              <button type="button" className={styles.secondaryButton} onClick={() => startCreatingWorkspace("group")}>
                Add group card
              </button>
              <button type="button" className={styles.secondaryButton} onClick={() => startCreatingWorkspace("shared")}>
                Add shared library
              </button>
            </div>
          </div>

          {isWorkspacesLoading ? <p className={shared.emptyText}>Loading landing sections...</p> : null}

          <div className={styles.directoryList}>
            {filteredWorkspaces.map((workspace) => (
              <button
                key={workspace.id}
                type="button"
                className={`${styles.directoryItem} ${workspace.id === selectedWorkspaceId && !isCreatingWorkspace ? styles.directoryItemActive : ""}`}
                onClick={() => selectWorkspace(workspace)}
              >
                <div className={styles.directoryHeader}>
                  <div className={styles.directoryCopy}>
                    <strong>{workspace.title}</strong>
                    <span>{workspace.subtitle || workspace.slug}</span>
                  </div>
                  <span className={styles.directoryValue}>{workspace.activeItemsCount}</span>
                </div>
                <div className={styles.badgeRow}>
                  <span className={workspace.kind === "shared" ? shared.goodPill : shared.neutralPill}>
                    {workspace.kind === "shared" ? "Shared library" : "Group section"}
                  </span>
                  {!workspace.isPublished ? <span className={shared.warnPill}>Draft</span> : null}
                  {!workspace.showOnHomepage ? <span className={shared.linkPill}>Hidden from homepage</span> : null}
                  {workspace.audiences.slice(0, 2).map((audience) => (
                    <span key={audience.id} className={shared.linkPill}>
                      {audience.shortLabel}
                    </span>
                  ))}
                </div>
                <div className={styles.directoryMeta}>
                  <span>{workspace.slug}</span>
                  <span>{workspace.sectionCounts.courses} courses</span>
                  <span>{workspace.sectionCounts.recordings} recordings</span>
                  <span>{workspace.sectionCounts.materials} materials</span>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>{isCreatingWorkspace ? "Create section card" : "Edit section card"}</h2>
              <p>These fields control homepage cards and the route shell for the selected section or shared library.</p>
            </div>
            {selectedWorkspace ? <span className={shared.sectionHint}>{selectedWorkspace.slug}</span> : null}
          </header>

          <form className={styles.form} onSubmit={onSubmitWorkspace}>
            <div className={styles.formGrid}>
              <label className={styles.field}>
                <span className={shared.fieldLabel}>Title</span>
                <input
                  type="text"
                  className={shared.inlineInput}
                  value={workspaceForm.title}
                  onChange={(event) =>
                    setWorkspaceForm((current) => ({
                      ...current,
                      title: event.currentTarget.value,
                      slug: current.slug ? current.slug : slugify(event.currentTarget.value),
                    }))
                  }
                />
              </label>
              <label className={styles.field}>
                <span className={shared.fieldLabel}>Subtitle</span>
                <input
                  type="text"
                  className={shared.inlineInput}
                  value={workspaceForm.subtitle}
                  onChange={(event) =>
                    setWorkspaceForm((current) => ({ ...current, subtitle: event.currentTarget.value }))
                  }
                />
              </label>
              <label className={styles.field}>
                <span className={shared.fieldLabel}>Slug</span>
                <input
                  type="text"
                  className={shared.inlineInput}
                  value={workspaceForm.slug}
                  onChange={(event) =>
                    setWorkspaceForm((current) => ({ ...current, slug: slugify(event.currentTarget.value) }))
                  }
                />
              </label>
              <label className={styles.field}>
                <span className={shared.fieldLabel}>Kind</span>
                <select
                  className={shared.select}
                  value={workspaceForm.kind}
                  onChange={(event) =>
                    setWorkspaceForm((current) => ({
                      ...current,
                      kind: event.currentTarget.value as OnlineAdminWorkspaceKind,
                      iconKey: event.currentTarget.value === "shared" ? "academy" : current.iconKey,
                    }))
                  }
                >
                  <option value="group">Group section</option>
                  <option value="shared">Shared library</option>
                </select>
              </label>
              <label className={styles.field}>
                <span className={shared.fieldLabel}>Icon key</span>
                <select
                  className={shared.select}
                  value={workspaceForm.iconKey}
                  onChange={(event) =>
                    setWorkspaceForm((current) => ({ ...current, iconKey: event.currentTarget.value }))
                  }
                >
                  {ICON_OPTIONS.map((iconKey) => (
                    <option key={iconKey} value={iconKey}>
                      {iconKey}
                    </option>
                  ))}
                </select>
              </label>
              <label className={styles.field}>
                <span className={shared.fieldLabel}>Sort order</span>
                <input
                  type="number"
                  className={shared.inlineInput}
                  value={workspaceForm.sortOrder}
                  onChange={(event) =>
                    setWorkspaceForm((current) => ({
                      ...current,
                      sortOrder: Number(event.currentTarget.value) || 0,
                    }))
                  }
                />
              </label>
            </div>

            <label className={styles.field}>
              <span className={shared.fieldLabel}>Card summary</span>
              <textarea
                className={shared.textarea}
                value={workspaceForm.summary}
                onChange={(event) =>
                  setWorkspaceForm((current) => ({ ...current, summary: event.currentTarget.value }))
                }
                rows={3}
              />
            </label>

            <div className={styles.toggleGrid}>
              <label className={styles.toggleCard}>
                <input
                  type="checkbox"
                  checked={workspaceForm.showOnHomepage}
                  onChange={(event) =>
                    setWorkspaceForm((current) => ({ ...current, showOnHomepage: event.currentTarget.checked }))
                  }
                />
                <div>
                  <strong>Show on homepage</strong>
                  <span>Controls whether the card appears in the landing grid.</span>
                </div>
              </label>
              <label className={styles.toggleCard}>
                <input
                  type="checkbox"
                  checked={workspaceForm.isPublished}
                  onChange={(event) =>
                    setWorkspaceForm((current) => ({ ...current, isPublished: event.currentTarget.checked }))
                  }
                />
                <div>
                  <strong>Published</strong>
                  <span>Published cards are available through the public API.</span>
                </div>
              </label>
            </div>

            <DemoRolePolicyFieldset
              audiences={audiences}
              selectedIds={workspaceForm.audienceIds ?? []}
              label="Section access roles"
              hint="Restrict the whole section workspace to one or more demo roles. Leave empty to keep this section broadly visible."
              onChange={(nextIds) =>
                setWorkspaceForm((current) => ({ ...current, audienceIds: nextIds }))
              }
            />
            {selectedWorkspaceAudienceLabels.length > 0 ? (
              <p className={styles.helperText}>
                Current access: {selectedWorkspaceAudienceLabels.join(", ")}
              </p>
            ) : null}

            {workspaceMessage ? <p className={styles.successText}>{workspaceMessage}</p> : null}
            {workspaceError ? <p className={shared.errorText}>{workspaceError}</p> : null}

            <div className={styles.actionRow}>
              <button
                type="submit"
                className={styles.primaryButton}
                disabled={createWorkspaceState.isLoading || updateWorkspaceState.isLoading}
              >
                {createWorkspaceState.isLoading || updateWorkspaceState.isLoading
                  ? "Saving..."
                  : isCreatingWorkspace
                    ? "Create card"
                    : "Save changes"}
              </button>
              {!isCreatingWorkspace && selectedWorkspace ? (
                <button
                  type="button"
                  className={styles.dangerButton}
                  disabled={deleteWorkspaceState.isLoading}
                  onClick={onDeleteWorkspace}
                >
                  {deleteWorkspaceState.isLoading ? "Deleting..." : "Delete card"}
                </button>
              ) : null}
            </div>
          </form>
        </section>
      </div>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Content directory</h2>
              <p>Each section card owns its own courses, labs, recordings, and materials. Shared libraries work the same way.</p>
            </div>
            {selectedWorkspace ? <span className={shared.sectionHint}>{selectedWorkspace.title}</span> : null}
          </header>

          <div className={styles.toolbarRow}>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Content section</span>
              <select
                className={shared.select}
                value={sectionFilter}
                onChange={(event) => setSectionFilter(event.currentTarget.value as OnlineAdminWorkspaceSection)}
                disabled={!selectedWorkspace}
              >
                {SECTION_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <div className={styles.inlineActionGroup}>
              <button type="button" className={styles.secondaryButton} onClick={startCreatingItem} disabled={!selectedWorkspace}>
                Add content item
              </button>
            </div>
          </div>

          {!selectedWorkspace ? <p className={shared.emptyText}>Select a section card first to manage its content.</p> : null}
          {selectedWorkspace && isItemsLoading ? <p className={shared.emptyText}>Loading content items...</p> : null}
          {selectedWorkspace && isItemsError ? <p className={shared.errorText}>Failed to load content items.</p> : null}

          <div className={styles.directoryList}>
            {selectedWorkspace && items.length === 0 && !isItemsLoading ? (
              <p className={shared.emptyText}>No content items exist for this section yet.</p>
            ) : null}
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`${styles.directoryItem} ${item.id === selectedItemId && !isCreatingItem ? styles.directoryItemActive : ""}`}
                onClick={() => selectItem(item)}
              >
                <div className={styles.directoryHeader}>
                  <div className={styles.directoryCopy}>
                    <strong>{item.title}</strong>
                    <span>{item.primaryMeta || item.section}</span>
                  </div>
                  <span className={styles.directoryValue}>{item.sortOrder}</span>
                </div>
                <div className={styles.badgeRow}>
                  <span className={shared.neutralPill}>{item.section}</span>
                  {!item.isActive ? <span className={shared.warnPill}>Inactive</span> : null}
                  {item.publishedOn ? <span className={shared.linkPill}>{item.publishedOn}</span> : null}
                  {item.linkedCourseSlug ? <span className={shared.goodPill}>{item.linkedCourseSlug}</span> : null}
                  {item.audiences.slice(0, 2).map((audience) => (
                    <span key={audience.id} className={shared.linkPill}>
                      {audience.shortLabel}
                    </span>
                  ))}
                </div>
                <div className={styles.directoryMeta}>
                  <span>{item.secondaryMeta || "No secondary label"}</span>
                  <span>{item.assetUrl ? "Linked asset" : "No asset URL"}</span>
                  <span>{item.linkedCohortCode || "No linked cohort"}</span>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>{isCreatingItem ? "Create content item" : "Edit content item"}</h2>
              <p>Populate the selected section with public content cards that will be rendered on the corresponding workspace page.</p>
            </div>
            <span className={shared.sectionHint}>{SECTION_OPTIONS.find((option) => option.value === sectionFilter)?.label}</span>
          </header>

          {!selectedWorkspace ? (
            <p className={shared.emptyText}>Choose a section card before creating or editing content.</p>
          ) : (
            <form className={styles.form} onSubmit={onSubmitItem}>
              <div className={styles.formGrid}>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Title</span>
                  <input
                    type="text"
                    className={shared.inlineInput}
                    value={itemForm.title}
                    onChange={(event) =>
                      setItemForm((current) => ({ ...current, title: event.currentTarget.value }))
                    }
                  />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Section</span>
                  <select
                    className={shared.select}
                    value={itemForm.section}
                    onChange={(event) =>
                      setItemForm((current) => ({
                        ...current,
                        section: event.currentTarget.value as OnlineAdminWorkspaceSection,
                      }))
                    }
                  >
                    {SECTION_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <label className={styles.field}>
                <span className={shared.fieldLabel}>Description</span>
                <textarea
                  className={shared.textarea}
                  value={itemForm.description}
                  onChange={(event) =>
                    setItemForm((current) => ({ ...current, description: event.currentTarget.value }))
                  }
                  rows={4}
                />
              </label>

              <div className={styles.formGrid}>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>{currentMetaLabels.preview}</span>
                  <input
                    type="text"
                    className={shared.inlineInput}
                    value={itemForm.previewImageUrl}
                    onChange={(event) =>
                      setItemForm((current) => ({ ...current, previewImageUrl: event.currentTarget.value }))
                    }
                    placeholder="/images/example.jpeg"
                  />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>{currentMetaLabels.asset}</span>
                  <input
                    type="text"
                    className={shared.inlineInput}
                    value={itemForm.assetUrl}
                    onChange={(event) =>
                      setItemForm((current) => ({ ...current, assetUrl: event.currentTarget.value }))
                    }
                    placeholder="https://..."
                  />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>{currentMetaLabels.primary}</span>
                  <input
                    type="text"
                    className={shared.inlineInput}
                    value={itemForm.primaryMeta}
                    onChange={(event) =>
                      setItemForm((current) => ({ ...current, primaryMeta: event.currentTarget.value }))
                    }
                  />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>{currentMetaLabels.secondary}</span>
                  <input
                    type="text"
                    className={shared.inlineInput}
                    value={itemForm.secondaryMeta}
                    onChange={(event) =>
                      setItemForm((current) => ({ ...current, secondaryMeta: event.currentTarget.value }))
                    }
                  />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>{currentMetaLabels.date}</span>
                  <input
                    type="date"
                    className={shared.inlineInput}
                    value={itemForm.publishedOn ?? ""}
                    onChange={(event) =>
                      setItemForm((current) => ({
                        ...current,
                        publishedOn: event.currentTarget.value || null,
                      }))
                    }
                  />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Sort order</span>
                  <input
                    type="number"
                    className={shared.inlineInput}
                    value={itemForm.sortOrder}
                    onChange={(event) =>
                      setItemForm((current) => ({
                        ...current,
                        sortOrder: Number(event.currentTarget.value) || 0,
                      }))
                    }
                  />
                </label>
              </div>

              {itemForm.section === "courses" ? (
                <div className={styles.formGrid}>
                  <label className={styles.field}>
                    <span className={shared.fieldLabel}>Linked academy course</span>
                    <select
                      className={shared.select}
                      value={itemForm.linkedCourseId ?? ""}
                      onChange={(event) =>
                        setItemForm((current) => ({
                          ...current,
                          linkedCourseId: event.currentTarget.value ? Number(event.currentTarget.value) : null,
                          linkedCohortId: null,
                        }))
                      }
                    >
                      <option value="">Not linked yet</option>
                      {courseOptions.map((course) => (
                        <option key={course.id} value={course.id}>
                          {courseDisplayTitle(course)} ({course.slug})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className={styles.field}>
                    <span className={shared.fieldLabel}>Linked public cohort</span>
                    <select
                      className={shared.select}
                      value={itemForm.linkedCohortId ?? ""}
                      onChange={(event) =>
                        setItemForm((current) => ({
                          ...current,
                          linkedCohortId: event.currentTarget.value ? Number(event.currentTarget.value) : null,
                        }))
                      }
                      disabled={!itemForm.linkedCourseId}
                    >
                      <option value="">Auto-select first public cohort</option>
                      {cohortOptions.map((cohort) => (
                        <option key={cohort.id} value={cohort.id}>
                          {cohort.groupCode} · {cohort.groupName}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              ) : null}

              <label className={styles.toggleCard}>
                <input
                  type="checkbox"
                  checked={itemForm.isActive}
                  onChange={(event) =>
                    setItemForm((current) => ({ ...current, isActive: event.currentTarget.checked }))
                  }
                />
                <div>
                  <strong>Active</strong>
                  <span>Inactive rows stay in admin history but are hidden from the public workspace page.</span>
                </div>
              </label>

              <DemoRolePolicyFieldset
                audiences={audiences}
                selectedIds={itemForm.audienceIds ?? []}
                label="Item access roles"
                hint="Restrict this content card to one or more demo roles. Leave empty to inherit the parent section or linked course policy."
                onChange={(nextIds) => setItemForm((current) => ({ ...current, audienceIds: nextIds }))}
              />
              {selectedItemAudienceLabels.length > 0 ? (
                <p className={styles.helperText}>
                  Current access: {selectedItemAudienceLabels.join(", ")}
                </p>
              ) : null}

              {itemMessage ? <p className={styles.successText}>{itemMessage}</p> : null}
              {itemError ? <p className={shared.errorText}>{itemError}</p> : null}

              <div className={styles.actionRow}>
                <button
                  type="submit"
                  className={styles.primaryButton}
                  disabled={createWorkspaceItemState.isLoading || updateWorkspaceItemState.isLoading}
                >
                  {createWorkspaceItemState.isLoading || updateWorkspaceItemState.isLoading
                    ? "Saving..."
                    : isCreatingItem
                      ? "Create content item"
                      : "Save changes"}
                </button>
                {!isCreatingItem && selectedItem ? (
                  <button
                    type="button"
                    className={styles.dangerButton}
                    disabled={deleteWorkspaceItemState.isLoading}
                    onClick={onDeleteItem}
                  >
                    {deleteWorkspaceItemState.isLoading ? "Deleting..." : "Delete item"}
                  </button>
                ) : null}
              </div>
            </form>
          )}
        </section>
      </div>
    </div>
  );
};

export default AdminPublicSitePage;
