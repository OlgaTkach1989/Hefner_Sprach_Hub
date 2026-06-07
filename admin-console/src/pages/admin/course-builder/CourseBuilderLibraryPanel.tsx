import { useDeferredValue, useMemo, useState } from "react";

import type { CourseBuilderLibraryItem, CourseBuilderNotebookOption, CourseBuilderSectionType } from "@/bll/course-builder/courseBuilder.type";
import type { TrainingAdminAudience } from "@/bll/training/training.type";
import DemoRolePolicyFieldset from "@/components/access/DemoRolePolicyFieldset";
import type { CourseBuilderLibraryDraft } from "./courseBuilderState";
import CollapsibleSection from "./CollapsibleSection";
import styles from "./AdminCourseBuilderModal.module.css";

type Props = {
  draft: CourseBuilderLibraryDraft;
  items: CourseBuilderLibraryItem[];
  notebooks: CourseBuilderNotebookOption[];
  audiences: TrainingAdminAudience[];
  selectedLibraryItemId: number | null;
  onSelectLibraryItem: (itemId: number | null) => void;
  onNewDraft: (sectionType?: CourseBuilderSectionType) => void;
  onPatchDraft: (patch: Partial<CourseBuilderLibraryDraft>) => void;
  onSave: () => void;
  onDelete: () => void;
  isSaving: boolean;
  isDeleting: boolean;
  isLoading?: boolean;
  isError?: boolean;
};

const sectionLabels: Record<CourseBuilderSectionType, string> = {
  introduction: "Introduction",
  main: "Main content",
  conclusion: "Conclusion",
};

const CourseBuilderLibraryPanel = ({
  draft,
  items,
  notebooks,
  audiences,
  selectedLibraryItemId,
  onSelectLibraryItem,
  onNewDraft,
  onPatchDraft,
  onSave,
  onDelete,
  isSaving,
  isDeleting,
  isLoading,
  isError,
}: Props) => {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());
  const [sectionFilter, setSectionFilter] = useState<CourseBuilderSectionType | "all">("all");
  const [assetFilter, setAssetFilter] = useState<string>("all");

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (sectionFilter !== "all" && item.sectionType !== sectionFilter) return false;
      if (assetFilter !== "all" && item.assetType !== assetFilter) return false;
      if (!deferredQuery) return true;
      return [item.title, item.description, item.libraryGroup, item.trainingContentName]
        .join(" ")
        .toLowerCase()
        .includes(deferredQuery);
    });
  }, [assetFilter, deferredQuery, items, sectionFilter]);

  return (
    <div className={styles.librarySplit}>
      <CollapsibleSection
        title="Shared library"
        description="Create reusable section assets and notebook references for future courses."
        summary={<span className={styles.statusNote}>{filteredItems.length} shown</span>}
        actions={
          <button type="button" className={styles.primaryButton} onClick={() => onNewDraft(draft.sectionType)}>
            New item
          </button>
        }
      >

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Search</span>
            <input
              className={styles.input}
              value={query}
              onChange={(event) => setQuery(event.currentTarget.value)}
              placeholder="Title, description, group, notebook"
            />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Section</span>
            <select className={styles.select} value={sectionFilter} onChange={(event) => setSectionFilter(event.currentTarget.value as any)}>
              <option value="all">All sections</option>
              <option value="introduction">Introduction</option>
              <option value="main">Main content</option>
              <option value="conclusion">Conclusion</option>
            </select>
          </label>
        </div>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Asset type</span>
          <select className={styles.select} value={assetFilter} onChange={(event) => setAssetFilter(event.currentTarget.value)}>
            <option value="all">All asset types</option>
            <option value="text">Text</option>
            <option value="document">Document</option>
            <option value="link">Link</option>
            <option value="notebook">Notebook</option>
          </select>
        </label>

        {isLoading ? <p className={styles.helperText}>Loading library items...</p> : null}
        {isError ? <p className={styles.helperText}>Failed to load library items.</p> : null}

        <div className={styles.libraryList}>
          {filteredItems.length === 0 ? <p className={styles.emptyState}>No library items match the current filters.</p> : null}
          {filteredItems.map((item) => {
            const active = item.id === selectedLibraryItemId;
            return (
              <button
                key={item.id}
                type="button"
                className={`${styles.libraryListItem} ${active ? styles.libraryListItemActive : ""}`}
                onClick={() => onSelectLibraryItem(item.id)}
              >
                <div className={styles.cardHeader}>
                  <div className={styles.stack}>
                    <strong>{item.title}</strong>
                    <span className={styles.helperText}>{item.description || "No description provided."}</span>
                  </div>
                  <span className={styles.miniPill}>{item.assetType}</span>
                </div>
                <div className={styles.templateMeta}>
                  <span className={styles.miniPill}>{sectionLabels[item.sectionType]}</span>
                  <span className={styles.miniPill}>{item.libraryGroup || "General"}</span>
                </div>
              </button>
            );
          })}
        </div>
      </CollapsibleSection>

      <CollapsibleSection
        title={draft.id ? "Edit library item" : "Create library item"}
        description="The same library entry can be reused across lessons, templates, and future builder sessions."
        summary={<span className={styles.statusNote}>{draft.assetType}</span>}
        actions={
          <>
            {draft.id ? (
              <button type="button" className={styles.dangerButton} disabled={isDeleting} onClick={onDelete}>
                {isDeleting ? "Deleting..." : "Delete"}
              </button>
            ) : null}
            <button type="button" className={styles.secondaryButton} onClick={() => onNewDraft(draft.sectionType)}>
              Reset form
            </button>
            <button type="button" className={styles.primaryButton} disabled={isSaving} onClick={onSave}>
              {isSaving ? "Saving..." : draft.id ? "Update item" : "Create item"}
            </button>
          </>
        }
      >

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Section</span>
            <select
              className={styles.select}
              value={draft.sectionType}
              onChange={(event) => onPatchDraft({ sectionType: event.currentTarget.value as CourseBuilderSectionType })}
            >
              <option value="introduction">Introduction</option>
              <option value="main">Main content</option>
              <option value="conclusion">Conclusion</option>
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Library group</span>
            <input
              className={styles.input}
              value={draft.libraryGroup}
              onChange={(event) => onPatchDraft({ libraryGroup: event.currentTarget.value })}
              placeholder="Core / Math / Quant / Demo"
            />
          </label>
        </div>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Title</span>
            <input className={styles.input} value={draft.title} onChange={(event) => onPatchDraft({ title: event.currentTarget.value })} />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Asset type</span>
            <select
              className={styles.select}
              value={draft.assetType}
              onChange={(event) => onPatchDraft({ assetType: event.currentTarget.value as any })}
            >
              <option value="text">Text</option>
              <option value="document">Document</option>
              <option value="link">Link</option>
              <option value="notebook">Notebook</option>
            </select>
          </label>
        </div>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Description</span>
          <textarea
            className={styles.textarea}
            value={draft.description}
            onChange={(event) => onPatchDraft({ description: event.currentTarget.value })}
          />
        </label>

        <p className={styles.helperText}>Library items are stored in English only.</p>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Sort order</span>
            <input
              className={styles.input}
              type="number"
              min={1}
              value={draft.sortOrder}
              onChange={(event) => onPatchDraft({ sortOrder: Number(event.currentTarget.value) || 1 })}
            />
          </label>
        </div>

        <div className={styles.row}>
          <label className={styles.statusNote}>
            <input
              type="checkbox"
              checked={draft.isActive}
              onChange={(event) => onPatchDraft({ isActive: event.currentTarget.checked })}
            />
            Active
          </label>
        </div>

        <DemoRolePolicyFieldset
          audiences={audiences}
          selectedIds={draft.audienceIds ?? []}
          label="Library item access roles"
          hint="Restrict this reusable asset to selected demo roles. Section items that reference it will inherit this policy unless they override access directly."
          onChange={(nextIds) => onPatchDraft({ audienceIds: nextIds })}
        />

        {draft.assetType === "text" ? (
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Markdown content</span>
            <textarea
              className={styles.textarea}
              value={draft.bodyMarkdown}
              onChange={(event) => onPatchDraft({ bodyMarkdown: event.currentTarget.value })}
            />
          </label>
        ) : null}

        {draft.assetType === "link" || draft.assetType === "document" ? (
          <label className={styles.field}>
            <span className={styles.fieldLabel}>{draft.assetType === "link" ? "Link URL" : "Document URL"}</span>
            <input
              className={styles.input}
              value={draft.externalUrl}
              onChange={(event) => onPatchDraft({ externalUrl: event.currentTarget.value })}
            />
          </label>
        ) : null}

        {draft.assetType === "document" ? (
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Upload file</span>
            <input
              className={styles.input}
              type="file"
              onChange={(event) => onPatchDraft({ file: event.currentTarget.files?.[0] ?? null })}
            />
          </label>
        ) : null}

        {draft.assetType === "notebook" ? (
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Notebook source</span>
            <select
              className={styles.select}
              value={draft.trainingContentId ?? ""}
              onChange={(event) =>
                onPatchDraft({ trainingContentId: event.currentTarget.value ? Number(event.currentTarget.value) : null })
              }
            >
              <option value="">Select notebook</option>
              {notebooks.map((notebook) => (
                <option key={notebook.id} value={notebook.id}>
                  {notebook.name}
                </option>
              ))}
            </select>
            <span className={styles.helperText}>Pick an internal notebook from the academy runtime catalog.</span>
          </label>
        ) : null}

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>File URL snapshot</span>
            <input className={styles.input} value={draft.file ? draft.file.name : ""} readOnly placeholder="No file selected" />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Training notebook preview</span>
            <input
              className={styles.input}
              value={draft.trainingContentId ? String(draft.trainingContentId) : ""}
              readOnly
              placeholder="No notebook linked"
            />
          </label>
        </div>
      </CollapsibleSection>
    </div>
  );
};

export default CourseBuilderLibraryPanel;
