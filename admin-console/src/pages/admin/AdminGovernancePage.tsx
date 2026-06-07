import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  useGetTrainingAdminContentGovernanceQuery,
  useGetTrainingAdminOverviewQuery,
  useRebuildTrainingAdminAiIndexMutation,
} from "@/bll/training/training.service";
import type {
  TrainingContentGovernanceItem,
  TrainingContentKind,
  TrainingContentStatus,
  TrainingGovernanceFlag,
} from "@/bll/training/training.type";
import shared from "./AdminPagesShared.module.css";
import styles from "./AdminGovernancePage.module.css";
import { courseDisplayTitle, formatDateTime } from "./adminPageUtils";
import { useAdminCourseScope } from "./useAdminCourseScope";

const governanceFlagLabels: Record<TrainingGovernanceFlag, string> = {
  missing_asset_class: "Missing asset class",
  missing_topic: "Missing topic",
  missing_owner: "Missing owner",
  missing_audience_policy: "Missing audience policy",
  missing_lab_profile: "Missing practice setup",
  lab_profile_incomplete: "Incomplete practice setup",
};

const contentKindLabels: Record<TrainingContentKind, string> = {
  article: "Article",
  video: "Video",
  notebook: "Practice",
  faq: "FAQ",
  recording: "Recording",
  exercise: "Exercise",
  dataset: "Dataset",
  link: "External link",
};

const accessScopeLabels: Record<TrainingContentGovernanceItem["access_scope"], string> = {
  public: "Public",
  authenticated: "Authenticated",
  entitled: "Entitled",
};

type GovernanceFilterState = {
  search: string;
  status: "" | TrainingContentStatus;
  kind: "" | TrainingContentKind;
  flaggedOnly: boolean;
  flagFocus: "all" | TrainingGovernanceFlag;
};

const defaultFilters: GovernanceFilterState = {
  search: "",
  status: "",
  kind: "",
  flaggedOnly: true,
  flagFocus: "all",
};

const countItemsWithFlag = (items: TrainingContentGovernanceItem[], flag: TrainingGovernanceFlag) =>
  items.filter((item) => item.governanceFlags.includes(flag)).length;

const AdminGovernancePage = () => {
  const {
    courses,
    isCoursesLoading,
    isCoursesError,
    selectedCourseId,
    selectedCourse,
    setSelectedCourseId,
  } = useAdminCourseScope();
  const [filters, setFilters] = useState<GovernanceFilterState>(defaultFilters);
  const [selectedItemIds, setSelectedItemIds] = useState<number[]>([]);
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [bulkActionBusy, setBulkActionBusy] = useState(false);

  const { data: overview, isLoading: isOverviewLoading, isError: isOverviewError } = useGetTrainingAdminOverviewQuery(
    selectedCourseId ? { courseId: selectedCourseId } : undefined,
    { skip: !selectedCourseId }
  );
  const {
    data: governanceData,
    isLoading: isGovernanceLoading,
    isError: isGovernanceError,
  } = useGetTrainingAdminContentGovernanceQuery(
    selectedCourseId
      ? {
          courseId: selectedCourseId,
          missingOnly: filters.flaggedOnly,
          status: filters.status || undefined,
          kind: filters.kind || undefined,
          q: filters.search.trim() || undefined,
        }
      : undefined,
    { skip: !selectedCourseId }
  );
  const [rebuildKnowledgeIndex, { isLoading: isRebuildingIndex }] = useRebuildTrainingAdminAiIndexMutation();

  const governanceItems = useMemo(() => governanceData?.results ?? [], [governanceData]);
  const visibleItems = useMemo(() => {
    const activeFlag = filters.flagFocus;
    if (activeFlag === "all") return governanceItems;
    return governanceItems.filter((item) => item.governanceFlags.includes(activeFlag));
  }, [filters.flagFocus, governanceItems]);
  const selectedItems = useMemo(
    () => visibleItems.filter((item) => selectedItemIds.includes(item.id)),
    [selectedItemIds, visibleItems]
  );

  useEffect(() => {
    setSelectedItemIds((current) => current.filter((itemId) => visibleItems.some((item) => item.id === itemId)));
  }, [visibleItems]);

  const isLoading = isOverviewLoading || isGovernanceLoading;
  const isError = isOverviewError || isGovernanceError;
  const courseQuery = selectedCourseId ? `?courseId=${selectedCourseId}` : "";
  const selectedSlugs = selectedItems.map((item) => item.slug);

  const flagSummary = useMemo(
    () => ({
      owner: countItemsWithFlag(visibleItems, "missing_owner"),
      audience: countItemsWithFlag(visibleItems, "missing_audience_policy"),
      practice:
        countItemsWithFlag(visibleItems, "missing_lab_profile") +
        countItemsWithFlag(visibleItems, "lab_profile_incomplete"),
      metadata:
        countItemsWithFlag(visibleItems, "missing_asset_class") + countItemsWithFlag(visibleItems, "missing_topic"),
    }),
    [visibleItems]
  );
  const selectedPublishedItems = useMemo(
    () => selectedItems.filter((item) => item.status === "published"),
    [selectedItems]
  );

  const toggleItem = (itemId: number) => {
    setSelectedItemIds((current) =>
      current.includes(itemId) ? current.filter((existingId) => existingId !== itemId) : [...current, itemId]
    );
  };

  const selectVisible = () => {
    setSelectedItemIds(visibleItems.map((item) => item.id));
  };

  const clearSelection = () => {
    setSelectedItemIds([]);
  };

  const onCopySelected = async () => {
    if (selectedSlugs.length === 0) return;
    setActionError("");
    setActionMessage("");
    try {
      await navigator.clipboard.writeText(selectedSlugs.join("\n"));
      setActionMessage(`Copied ${selectedSlugs.length} content slug${selectedSlugs.length === 1 ? "" : "s"} to the clipboard.`);
    } catch {
      setActionError("Failed to copy selected content slugs to the clipboard.");
    }
  };

  const rebuildSelectedItems = async (items: TrainingContentGovernanceItem[]) => {
    if (!selectedCourseId || items.length === 0) return;
    setActionError("");
    setActionMessage("");
    setBulkActionBusy(true);
    let rebuilt = 0;
    let failed = 0;
    for (const item of items) {
      try {
        await rebuildKnowledgeIndex({ course_id: selectedCourseId, content_slug: item.slug }).unwrap();
        rebuilt += 1;
      } catch {
        failed += 1;
      }
    }
    setBulkActionBusy(false);
    if (failed > 0) {
      setActionError(`Rebuilt ${rebuilt} item(s), but ${failed} item(s) failed and should be reviewed in Knowledge & AI.`);
      return;
    }
    setActionMessage(`Knowledge index rebuilt for ${rebuilt} selected content item(s).`);
  };

  const setFilter = <TKey extends keyof GovernanceFilterState>(key: TKey, value: GovernanceFilterState[TKey]) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  return (
    <div className={shared.page}>
      <section className={shared.hero}>
        <div className={shared.heroCopy}>
          <span className={shared.eyebrow}>Policy and ownership</span>
          <h1>Training governance workspace</h1>
          <p>
            Governance is the course-scoped release register for ownership, access policy, metadata quality, and practice
            readiness. Keep the list focused on real blockers, then move the selected course into the next fix surface only
            when needed.
          </p>
        </div>
        <div className={shared.toolbar}>
          <div className={shared.scopeControls}>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Governed course</span>
              <select
                className={shared.select}
                value={selectedCourseId ?? ""}
                onChange={(event) => setSelectedCourseId(Number(event.currentTarget.value))}
                disabled={isCoursesLoading || courses.length === 0}
              >
                {courses.map((course) => (
                  <option key={course.id} value={course.id}>
                    {courseDisplayTitle(course)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className={shared.heroMeta}>
            <span>{overview?.ownerAssignments ?? 0} owner assignments</span>
            <span>{overview?.reviewerAssignments ?? 0} reviewer assignments</span>
            <span>{overview?.instructorAssignments ?? 0} instructor assignments</span>
            <span>{visibleItems.length} visible content items</span>
          </div>
        </div>
      </section>

      {isCoursesError ? <p className={shared.errorText}>Failed to load course scope for governance.</p> : null}
      {!selectedCourseId && !isCoursesLoading ? (
        <section className={shared.panel}>
          <p className={shared.emptyText}>No courses are available yet, so governance controls cannot be opened.</p>
        </section>
      ) : null}

      {selectedCourseId && selectedCourse ? (
        <>
          <section className={shared.panel}>
            <header className={shared.panelHeader}>
              <div>
                <h2>Register filters</h2>
                <p>Keep the risk register scoped to the blockers you want to clear in the current pass.</p>
              </div>
              <div className={styles.headerLinks}>
                <Link to={`/curators${courseQuery}`} className={shared.linkPill}>
                  Users & Instructors
                </Link>
                <Link to={`/knowledge${courseQuery}`} className={shared.linkPill}>
                  Knowledge & AI
                </Link>
              </div>
            </header>

            <div className={styles.filterGrid}>
              <label className={styles.filterField}>
                <span className={shared.fieldLabel}>Search</span>
                <input
                  className={shared.inlineInput}
                  value={filters.search}
                  onChange={(event) => setFilter("search", event.currentTarget.value)}
                  placeholder="Search by title, slug, or description"
                />
              </label>
              <label className={styles.filterField}>
                <span className={shared.fieldLabel}>Status</span>
                <select
                  className={shared.select}
                  value={filters.status}
                  onChange={(event) => setFilter("status", event.currentTarget.value as GovernanceFilterState["status"])}
                >
                  <option value="">All statuses</option>
                  <option value="draft">Draft</option>
                  <option value="review">Review</option>
                  <option value="published">Published</option>
                  <option value="retired">Retired</option>
                </select>
              </label>
              <label className={styles.filterField}>
                <span className={shared.fieldLabel}>Content kind</span>
                <select
                  className={shared.select}
                  value={filters.kind}
                  onChange={(event) => setFilter("kind", event.currentTarget.value as GovernanceFilterState["kind"])}
                >
                  <option value="">All kinds</option>
                  <option value="article">Article</option>
                  <option value="video">Video</option>
                  <option value="notebook">Notebook</option>
                  <option value="faq">FAQ</option>
                  <option value="recording">Recording</option>
                  <option value="exercise">Exercise</option>
                  <option value="dataset">Dataset</option>
                  <option value="link">External link</option>
                </select>
              </label>
              <label className={styles.filterField}>
                <span className={shared.fieldLabel}>View mode</span>
                <select
                  className={shared.select}
                  value={filters.flaggedOnly ? "flagged" : "all"}
                  onChange={(event) => setFilter("flaggedOnly", event.currentTarget.value === "flagged")}
                >
                  <option value="flagged">Only flagged items</option>
                  <option value="all">All content items</option>
                </select>
              </label>
            </div>

            <div className={styles.flagFilterRow}>
              <button
                type="button"
                className={`${styles.flagFilterButton} ${filters.flagFocus === "all" ? styles.flagFilterButtonActive : ""}`}
                onClick={() => setFilter("flagFocus", "all")}
              >
                All visible items
              </button>
              {(Object.keys(governanceFlagLabels) as TrainingGovernanceFlag[]).map((flag) => (
                <button
                  key={flag}
                  type="button"
                  className={`${styles.flagFilterButton} ${filters.flagFocus === flag ? styles.flagFilterButtonActive : ""}`}
                  onClick={() => setFilter("flagFocus", flag)}
                >
                  {governanceFlagLabels[flag]}
                </button>
              ))}
            </div>
          </section>

          <section className={shared.kpiGrid}>
            <article className={shared.kpiCard}>
              <span className={shared.kpiLabel}>Visible content</span>
              <strong className={shared.kpiValue}>{visibleItems.length}</strong>
              <span className={shared.kpiMeta}>Filtered content items currently in the governance register.</span>
            </article>
            <article className={shared.kpiCard}>
              <span className={shared.kpiLabel}>Ownership / access gaps</span>
              <strong className={shared.kpiValue}>
                {flagSummary.owner} / {flagSummary.audience}
              </strong>
              <span className={shared.kpiMeta}>Missing owner versus missing audience policy in the current view.</span>
            </article>
            <article className={shared.kpiCard}>
              <span className={shared.kpiLabel}>Practice setup gaps</span>
              <strong className={shared.kpiValue}>{flagSummary.practice}</strong>
              <span className={shared.kpiMeta}>Content with missing or incomplete practice configuration.</span>
            </article>
            <article className={shared.kpiCard}>
              <span className={shared.kpiLabel}>Metadata issues</span>
              <strong className={shared.kpiValue}>{flagSummary.metadata}</strong>
              <span className={shared.kpiMeta}>Missing asset-class or topic coverage in the active course scope.</span>
            </article>
          </section>

          <div className={shared.grid2}>
            <section className={shared.panel}>
              <header className={shared.panelHeader}>
                <div>
                  <h2>Governance risk register</h2>
                  <p>Review each content item as a release object: metadata, access policy, practice setup, and owner accountability.</p>
                </div>
                <div className={styles.selectionActions}>
                  <button type="button" className={styles.secondaryButton} onClick={selectVisible}>
                    Select visible
                  </button>
                  <button type="button" className={styles.secondaryButton} onClick={clearSelection}>
                    Clear selection
                  </button>
                </div>
              </header>

              {actionMessage ? <p className={styles.successText}>{actionMessage}</p> : null}
              {actionError ? <p className={shared.errorText}>{actionError}</p> : null}
              {isLoading ? <p className={shared.emptyText}>Loading governance register...</p> : null}
              {isError ? <p className={shared.errorText}>Failed to load content governance data.</p> : null}

              <div className={shared.tableWrap}>
                <table className={shared.table}>
                  <thead>
                    <tr>
                      <th className={styles.checkboxCell}>Select</th>
                      <th>Content</th>
                      <th>Access</th>
                      <th>Flags</th>
                      <th>Updated</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleItems.length === 0 && !isLoading ? (
                      <tr>
                        <td colSpan={6}>
                          <p className={shared.emptyText}>No content items match the current governance filters.</p>
                        </td>
                      </tr>
                    ) : null}
                    {visibleItems.map((item) => (
                      <tr key={item.id}>
                        <td className={styles.checkboxCell}>
                          <label className={styles.checkboxWrap}>
                            <input
                              type="checkbox"
                              checked={selectedItemIds.includes(item.id)}
                              onChange={() => toggleItem(item.id)}
                            />
                          </label>
                        </td>
                        <td>
                          <div className={shared.tableCellStack}>
                            <strong>{item.name}</strong>
                            <span>
                              {item.slug} · {contentKindLabels[item.content_kind]} · {item.status}
                            </span>
                            <span>Owner: {item.owner?.email ?? "Unassigned"}</span>
                          </div>
                        </td>
                        <td>
                          <div className={shared.tableCellStack}>
                            <strong>{accessScopeLabels[item.access_scope]}</strong>
                            <span>Asset classes {item.assetClassCount}</span>
                            <span>Topics {item.topicCount}</span>
                          </div>
                        </td>
                        <td>
                          <div className={styles.flagList}>
                            {item.governanceFlags.length === 0 ? (
                              <span className={shared.goodPill}>No flags</span>
                            ) : (
                              item.governanceFlags.map((flag) => (
                                <span key={flag} className={shared.warnPill}>
                                  {governanceFlagLabels[flag]}
                                </span>
                              ))
                            )}
                          </div>
                        </td>
                        <td>{formatDateTime(item.updated_at)}</td>
                        <td>
                          <div className={styles.rowActions}>
                            <button
                              type="button"
                              className={styles.secondaryButton}
                              disabled={isRebuildingIndex || item.status !== "published"}
                              onClick={() => void rebuildSelectedItems([item])}
                            >
                              Rebuild index
                            </button>
                            <Link to={`/knowledge${courseQuery}`} className={shared.linkPill}>
                              Knowledge
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className={shared.panel}>
              <header className={shared.panelHeader}>
                <div>
                  <h2>Batch actions</h2>
                  <p>Use the current selection as a workset, rebuild indexes where needed, and hand off only the course-scoped fixes that require another screen.</p>
                </div>
              </header>

              <div className={styles.sideStack}>
                <article className={styles.sideCard}>
                  <span className={shared.fieldLabel}>Selection summary</span>
                  <strong>{selectedItems.length} items selected</strong>
                  <p>
                    {selectedItems.length > 0
                      ? `${selectedPublishedItems.length} published item${selectedPublishedItems.length === 1 ? "" : "s"} can be reindexed immediately.`
                      : "Select content items from the governance register to enable batch actions."}
                  </p>
                  <div className={styles.actionButtons}>
                    <button
                      type="button"
                      className={styles.primaryButton}
                      disabled={bulkActionBusy || selectedPublishedItems.length === 0}
                      onClick={() => void rebuildSelectedItems(selectedPublishedItems)}
                    >
                      {bulkActionBusy ? "Running..." : "Rebuild selected indexes"}
                    </button>
                    <button
                      type="button"
                      className={styles.secondaryButton}
                      disabled={selectedItems.length === 0}
                      onClick={() => void onCopySelected()}
                    >
                      Copy selected slugs
                    </button>
                  </div>
                </article>

                <article className={styles.sideCard}>
                  <span className={shared.fieldLabel}>Gap snapshot</span>
                  <div className={styles.metricList}>
                    <div>
                      <strong>Missing owner</strong>
                      <span>{flagSummary.owner}</span>
                    </div>
                    <div>
                      <strong>Missing audience</strong>
                      <span>{flagSummary.audience}</span>
                    </div>
                    <div>
                      <strong>Practice setup</strong>
                      <span>{flagSummary.practice}</span>
                    </div>
                    <div>
                      <strong>Metadata issues</strong>
                      <span>{flagSummary.metadata}</span>
                    </div>
                  </div>
                </article>

                <article className={styles.sideCard}>
                  <span className={shared.fieldLabel}>Follow-up tools</span>
                  <p>Use these only when the register shows a real ownership or AI follow-up problem.</p>
                  <div className={shared.linkGrid}>
                    <Link to={`/curators${courseQuery}`} className={shared.quickLink}>
                      <strong>Fix ownership and access</strong>
                      <span>Open Users & Instructors to assign owners, reviewers, and course-scoped access roles.</span>
                    </Link>
                    <Link to={`/knowledge${courseQuery}`} className={shared.quickLink}>
                      <strong>Review AI follow-up</strong>
                      <span>Open Knowledge & AI to process unresolved learner questions and refresh indexed content.</span>
                    </Link>
                  </div>
                </article>
              </div>
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
};

export default AdminGovernancePage;
