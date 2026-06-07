import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  useGetTrainingAdminAiAnalyticsQuery,
  useGetTrainingAdminAiConversationsQuery,
  useGetTrainingAdminAiOverviewQuery,
  useGetTrainingAdminCourseRoleAssignmentsQuery,
  useGetTrainingAdminReportsOverviewQuery,
  useRebuildTrainingAdminAiIndexMutation,
  useUpdateTrainingAdminAiConversationMutation,
} from "@/bll/training/training.service";
import type { TrainingAiGovernanceStatus } from "@/bll/training/training.type";
import {
  useCreateOnlineAdminKnowledgeDocumentMutation,
  useCreateOnlineAdminKnowledgeSourceMutation,
  useDeleteOnlineAdminKnowledgeDocumentMutation,
  useDeleteOnlineAdminKnowledgeSourceMutation,
  useGetOnlineAdminKnowledgeDocumentsQuery,
  useGetOnlineAdminKnowledgeSourcesQuery,
  useGetOnlineCoursesQuery,
  useUpdateOnlineAdminKnowledgeDocumentMutation,
  useUpdateOnlineAdminKnowledgeSourceMutation,
} from "@/bll/online/online.service";
import shared from "./AdminPagesShared.module.css";
import styles from "./AdminKnowledgePage.module.css";
import { courseDisplayTitle, formatDateTime } from "./adminPageUtils";
import { useAdminCourseScope } from "./useAdminCourseScope";

type QueueStateFilter = "all" | TrainingAiGovernanceStatus;
type QueueAssignmentFilter = "all" | "assigned" | "unassigned" | "recommended";

const governanceStatusLabel: Record<TrainingAiGovernanceStatus, string> = {
  open: "Open",
  in_review: "In review",
  resolved: "Resolved",
  archived: "Archived",
};

const resolveApiErrorMessage = (error: unknown, fallback: string) => {
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

type KnowledgeSourceFormState = {
  slug: string;
  title: string;
  description: string;
  sourceType:
    | "upload"
    | "url"
    | "sharepoint"
    | "confluence"
    | "notion"
    | "video_transcript"
    | "audio_transcript"
    | "external_kb";
  externalUrl: string;
  linkedCourseId: number | null;
  isActive: boolean;
  isIndexed: boolean;
};

type KnowledgeDocumentFormState = {
  title: string;
  description: string;
  documentType: "pdf" | "docx" | "markdown" | "html" | "transcript" | "link";
  language: string;
  externalUrl: string;
  bodyMarkdown: string;
  transcriptText: string;
  isActive: boolean;
};

const EMPTY_SOURCE_FORM: KnowledgeSourceFormState = {
  slug: "",
  title: "",
  description: "",
  sourceType: "upload",
  externalUrl: "",
  linkedCourseId: null,
  isActive: true,
  isIndexed: false,
};

const EMPTY_DOCUMENT_FORM: KnowledgeDocumentFormState = {
  title: "",
  description: "",
  documentType: "markdown",
  language: "en",
  externalUrl: "",
  bodyMarkdown: "",
  transcriptText: "",
  isActive: true,
};

const slugify = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

const AdminKnowledgePage = () => {
  const { courses, isCoursesLoading, isCoursesError, selectedCourseId, selectedCourse, setSelectedCourseId } =
    useAdminCourseScope();
  const [windowDays, setWindowDays] = useState(30);
  const [includeResolved, setIncludeResolved] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [stateFilter, setStateFilter] = useState<QueueStateFilter>("all");
  const [assignmentFilter, setAssignmentFilter] = useState<QueueAssignmentFilter>("all");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [sharedNote, setSharedNote] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [sourceForm, setSourceForm] = useState<KnowledgeSourceFormState>(EMPTY_SOURCE_FORM);
  const [documentForm, setDocumentForm] = useState<KnowledgeDocumentFormState>(EMPTY_DOCUMENT_FORM);
  const [registryMessage, setRegistryMessage] = useState("");
  const [registryError, setRegistryError] = useState("");

  const baseArgs = selectedCourseId ? { courseId: selectedCourseId } : undefined;
  const { data: courseDirectory } = useGetOnlineCoursesQuery();
  const { data: knowledgeSourcesData } = useGetOnlineAdminKnowledgeSourcesQuery();
  const knowledgeSources = useMemo(() => knowledgeSourcesData?.results ?? [], [knowledgeSourcesData]);
  const { data: knowledgeDocumentsData } = useGetOnlineAdminKnowledgeDocumentsQuery(
    selectedSourceId ? { sourceId: selectedSourceId } : undefined,
    { skip: !selectedSourceId }
  );
  const knowledgeDocuments = useMemo(() => knowledgeDocumentsData?.results ?? [], [knowledgeDocumentsData]);
  const { data: overview, isLoading: isOverviewLoading, isError: isOverviewError } = useGetTrainingAdminAiOverviewQuery(
    baseArgs,
    { skip: !selectedCourseId }
  );
  const { data: analytics, isLoading: isAnalyticsLoading, isError: isAnalyticsError } = useGetTrainingAdminAiAnalyticsQuery(
    selectedCourseId ? { courseId: selectedCourseId, windowDays } : undefined,
    { skip: !selectedCourseId }
  );
  const { data: reportsOverview } = useGetTrainingAdminReportsOverviewQuery(baseArgs, { skip: !selectedCourseId });
  const { data: queueData, isLoading: isQueueLoading, isError: isQueueError } = useGetTrainingAdminAiConversationsQuery(
    selectedCourseId ? { courseId: selectedCourseId, includeResolved, limit: 100 } : undefined,
    { skip: !selectedCourseId }
  );
  const { data: ownerAssignmentsData } = useGetTrainingAdminCourseRoleAssignmentsQuery(
    selectedCourseId ? { courseId: selectedCourseId } : undefined,
    { skip: !selectedCourseId }
  );
  const [updateConversation] = useUpdateTrainingAdminAiConversationMutation();
  const [rebuildKnowledgeIndex, { isLoading: isRebuildingIndex }] = useRebuildTrainingAdminAiIndexMutation();
  const [createKnowledgeSource, createKnowledgeSourceState] = useCreateOnlineAdminKnowledgeSourceMutation();
  const [updateKnowledgeSource, updateKnowledgeSourceState] = useUpdateOnlineAdminKnowledgeSourceMutation();
  const [deleteKnowledgeSource, deleteKnowledgeSourceState] = useDeleteOnlineAdminKnowledgeSourceMutation();
  const [createKnowledgeDocument, createKnowledgeDocumentState] = useCreateOnlineAdminKnowledgeDocumentMutation();
  const [updateKnowledgeDocument, updateKnowledgeDocumentState] = useUpdateOnlineAdminKnowledgeDocumentMutation();
  const [deleteKnowledgeDocument, deleteKnowledgeDocumentState] = useDeleteOnlineAdminKnowledgeDocumentMutation();

  const queue = useMemo(() => queueData?.results ?? [], [queueData]);
  const ownerByUserId = useMemo(() => {
    const assignments = (ownerAssignmentsData?.results ?? []).filter((assignment) => assignment.role === "owner");
    return assignments.reduce<Record<number, (typeof assignments)[number]["user"]>>((acc, assignment) => {
      acc[assignment.user.id] = assignment.user;
      return acc;
    }, {});
  }, [ownerAssignmentsData]);

  const visibleQueue = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    return queue.filter((conversation) => {
      if (stateFilter !== "all" && conversation.governanceStatus !== stateFilter) return false;
      if (assignmentFilter === "assigned" && !conversation.assignedTo) return false;
      if (assignmentFilter === "unassigned" && conversation.assignedTo) return false;
      if (assignmentFilter === "recommended" && !conversation.recommendedOwnerId) return false;
      if (!normalizedQuery) return true;
      return [
        conversation.title,
        conversation.latestUserPrompt,
        conversation.learner.email,
        conversation.learner.fullName,
        conversation.content?.name,
        conversation.content?.slug,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery);
    });
  }, [assignmentFilter, queue, searchQuery, stateFilter]);

  useEffect(() => {
    setSelectedIds((current) => current.filter((publicId) => visibleQueue.some((item) => item.publicId === publicId)));
  }, [visibleQueue]);

  const selectedQueue = useMemo(
    () => visibleQueue.filter((conversation) => selectedIds.includes(conversation.publicId)),
    [selectedIds, visibleQueue]
  );
  const queueStats = useMemo(
    () => ({
      assigned: visibleQueue.filter((conversation) => Boolean(conversation.assignedTo)).length,
      unassigned: visibleQueue.filter((conversation) => !conversation.assignedTo).length,
      recommended: visibleQueue.filter((conversation) => conversation.recommendedOwnerId !== null).length,
      inReview: visibleQueue.filter((conversation) => conversation.governanceStatus === "in_review").length,
    }),
    [visibleQueue]
  );
  const isLoading = isOverviewLoading || isAnalyticsLoading || isQueueLoading;
  const isError = isOverviewError || isAnalyticsError || isQueueError;
  const courseQuery = selectedCourseId ? `?courseId=${selectedCourseId}` : "";

  const selectedSource = useMemo(
    () => knowledgeSources.find((source) => source.id === selectedSourceId) ?? null,
    [knowledgeSources, selectedSourceId]
  );
  const selectedDocument = useMemo(
    () => knowledgeDocuments.find((document) => document.id === selectedDocumentId) ?? null,
    [knowledgeDocuments, selectedDocumentId]
  );

  useEffect(() => {
    if (selectedSourceId !== null && !knowledgeSources.some((source) => source.id === selectedSourceId)) {
      setSelectedSourceId(null);
    }
    if (selectedSource) {
      setSourceForm({
        slug: selectedSource.slug,
        title: selectedSource.title,
        description: selectedSource.description,
        sourceType: selectedSource.sourceType,
        externalUrl: selectedSource.externalUrl,
        linkedCourseId: selectedSource.linkedCourseId,
        isActive: selectedSource.isActive,
        isIndexed: selectedSource.isIndexed,
      });
      return;
    }
    if (selectedSourceId === null) {
      setSourceForm({
        ...EMPTY_SOURCE_FORM,
        linkedCourseId: selectedCourseId ?? null,
      });
    }
  }, [knowledgeSources, selectedCourseId, selectedSource, selectedSourceId]);

  useEffect(() => {
    if (selectedDocumentId !== null && !knowledgeDocuments.some((document) => document.id === selectedDocumentId)) {
      setSelectedDocumentId(null);
    }
    if (selectedDocument) {
      setDocumentForm({
        title: selectedDocument.title,
        description: selectedDocument.description,
        documentType: selectedDocument.documentType,
        language: selectedDocument.language,
        externalUrl: selectedDocument.externalUrl,
        bodyMarkdown: "",
        transcriptText: "",
        isActive: selectedDocument.isActive,
      });
      return;
    }
    if (selectedDocumentId === null) {
      setDocumentForm(EMPTY_DOCUMENT_FORM);
    }
  }, [knowledgeDocuments, selectedDocument, selectedDocumentId]);

  const toggleSelection = (publicId: string) => {
    setSelectedIds((current) =>
      current.includes(publicId) ? current.filter((itemId) => itemId !== publicId) : [...current, publicId]
    );
  };

  const runBulkUpdate = async (
    items: typeof selectedQueue,
    buildBody: (conversation: (typeof selectedQueue)[number]) => {
      governance_status?: TrainingAiGovernanceStatus;
      assigned_to_id?: number | null;
      resolution_note?: string;
    },
    successLabel: string
  ) => {
    if (items.length === 0) return;
    setActionError("");
    setActionMessage("");
    setBulkBusy(true);
    let updated = 0;
    let failed = 0;
    for (const item of items) {
      try {
        await updateConversation({ conversationPublicId: item.publicId, body: buildBody(item) }).unwrap();
        updated += 1;
      } catch {
        failed += 1;
      }
    }
    setBulkBusy(false);
    if (failed > 0) {
      setActionError(`${successLabel}: ${updated} updated, ${failed} failed.`);
      return;
    }
    setActionMessage(`${successLabel}: ${updated} conversation${updated === 1 ? "" : "s"} updated.`);
  };

  const rebuildIndexForCourse = async (contentSlug?: string) => {
    if (!selectedCourseId) return;
    setActionError("");
    setActionMessage("");
    try {
      const result = await rebuildKnowledgeIndex(
        contentSlug ? { course_id: selectedCourseId, content_slug: contentSlug } : { course_id: selectedCourseId }
      ).unwrap();
      setActionMessage(
        `Knowledge index rebuilt for ${result.rebuiltContentItems} content item(s) and ${result.rebuiltChunks} chunk(s).`
      );
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to rebuild the knowledge index."));
    }
  };

  const onSaveKnowledgeSource = async () => {
    const body = {
      slug: sourceForm.slug || slugify(sourceForm.title),
      title: sourceForm.title.trim(),
      description: sourceForm.description.trim(),
      sourceType: sourceForm.sourceType,
      externalUrl: sourceForm.externalUrl.trim(),
      linkedCourseId: sourceForm.linkedCourseId,
      isActive: sourceForm.isActive,
      isIndexed: sourceForm.isIndexed,
      metadataJson: {},
    };
    if (!body.title) {
      setRegistryMessage("");
      setRegistryError("Knowledge source title is required.");
      return;
    }
    setRegistryMessage("");
    setRegistryError("");
    try {
      if (selectedSource) {
        await updateKnowledgeSource({ sourceId: selectedSource.id, body }).unwrap();
        setRegistryMessage("Knowledge source updated.");
      } else {
        const created = await createKnowledgeSource(body).unwrap();
        setSelectedSourceId(created.id);
        setRegistryMessage("Knowledge source created.");
      }
    } catch (error) {
      setRegistryError(resolveApiErrorMessage(error, "Failed to save the knowledge source."));
    }
  };

  const onDeleteKnowledgeSource = async () => {
    if (!selectedSource) return;
    setRegistryMessage("");
    setRegistryError("");
    try {
      await deleteKnowledgeSource(selectedSource.id).unwrap();
      setSelectedSourceId(null);
      setRegistryMessage("Knowledge source removed.");
    } catch (error) {
      setRegistryError(resolveApiErrorMessage(error, "Failed to remove the knowledge source."));
    }
  };

  const onSaveKnowledgeDocument = async () => {
    if (!selectedSourceId) {
      setRegistryMessage("");
      setRegistryError("Select a knowledge source before saving a document.");
      return;
    }
    const body = {
      sourceId: selectedSourceId,
      title: documentForm.title.trim(),
      description: documentForm.description.trim(),
      documentType: documentForm.documentType,
      language: documentForm.language.trim() || "en",
      externalUrl: documentForm.externalUrl.trim(),
      bodyMarkdown: documentForm.bodyMarkdown,
      transcriptText: documentForm.transcriptText,
      isActive: documentForm.isActive,
      metadataJson: {},
    };
    if (!body.title) {
      setRegistryMessage("");
      setRegistryError("Knowledge document title is required.");
      return;
    }
    setRegistryMessage("");
    setRegistryError("");
    try {
      if (selectedDocument) {
        await updateKnowledgeDocument({ documentId: selectedDocument.id, body }).unwrap();
        setRegistryMessage("Knowledge document updated.");
      } else {
        const created = await createKnowledgeDocument(body).unwrap();
        setSelectedDocumentId(created.id);
        setRegistryMessage("Knowledge document created.");
      }
    } catch (error) {
      setRegistryError(resolveApiErrorMessage(error, "Failed to save the knowledge document."));
    }
  };

  const onDeleteKnowledgeDocument = async () => {
    if (!selectedDocument) return;
    setRegistryMessage("");
    setRegistryError("");
    try {
      await deleteKnowledgeDocument(selectedDocument.id).unwrap();
      setSelectedDocumentId(null);
      setRegistryMessage("Knowledge document removed.");
    } catch (error) {
      setRegistryError(resolveApiErrorMessage(error, "Failed to remove the knowledge document."));
    }
  };

  return (
    <div className={shared.page}>
      <section className={shared.hero}>
        <div className={shared.heroCopy}>
          <span className={shared.eyebrow}>Knowledge runtime</span>
          <h1>AI assistance and knowledge health</h1>
          <p>
            Work the unresolved AI queue, track index coverage, and rebuild the course knowledge surface without leaving the
            active course scope.
          </p>
        </div>
        <div className={shared.toolbar}>
          <div className={shared.scopeControls}>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Knowledge course scope</span>
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
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Monitoring window</span>
              <select className={shared.select} value={windowDays} onChange={(event) => setWindowDays(Number(event.currentTarget.value))}>
                <option value={7}>7 days</option>
                <option value={14}>14 days</option>
                <option value={30}>30 days</option>
                <option value={90}>90 days</option>
              </select>
            </label>
          </div>
          <div className={shared.heroMeta}>
            <span>{overview?.unresolvedQueueCount ?? 0} unresolved</span>
            <span>{overview?.indexedChunks ?? 0} indexed chunks</span>
            <span>{analytics?.providerMode?.toUpperCase() ?? "DEMO"} runtime</span>
            <span>{reportsOverview?.failedSyncEvents ?? 0} sync failures</span>
          </div>
        </div>
      </section>

      {isCoursesError ? <p className={shared.errorText}>Failed to load knowledge workspace scope.</p> : null}
      {!selectedCourseId && !isCoursesLoading ? (
        <section className={shared.panel}>
          <p className={shared.emptyText}>No courses are available yet, so AI governance cannot be opened.</p>
        </section>
      ) : null}

      {selectedCourseId && selectedCourse ? (
        <>
          <section className={shared.kpiGrid}>
            <article className={shared.kpiCard}>
              <span className={shared.kpiLabel}>Unresolved queue</span>
              <strong className={shared.kpiValue}>{overview?.unresolvedQueueCount ?? "-"}</strong>
              <span className={shared.kpiMeta}>Open or in-review conversations that still need a human response.</span>
            </article>
            <article className={shared.kpiCard}>
              <span className={shared.kpiLabel}>Indexed coverage</span>
              <strong className={shared.kpiValue}>
                {overview?.indexedContentItems ?? 0} / {analytics?.publishedContentItems ?? 0}
              </strong>
              <span className={shared.kpiMeta}>Indexed published items versus the full published content set.</span>
            </article>
            <article className={shared.kpiCard}>
              <span className={shared.kpiLabel}>AI failures / sync failures</span>
              <strong className={shared.kpiValue}>{analytics?.aiResponseFailuresWindow ?? 0} / {analytics?.directusSyncFailedWindow ?? 0}</strong>
              <span className={shared.kpiMeta}>Signals most likely to degrade learner support first.</span>
            </article>
            <article className={shared.kpiCard}>
              <span className={shared.kpiLabel}>Stale / unindexed</span>
              <strong className={shared.kpiValue}>{analytics?.staleIndexedContentCount ?? 0} / {analytics?.unindexedPublishedItems ?? 0}</strong>
              <span className={shared.kpiMeta}>Published content that is stale or missing from the retrieval index.</span>
            </article>
          </section>

          <section className={shared.panel}>
            <header className={shared.panelHeader}>
              <div>
                <h2>Queue filters</h2>
                <p>Filter the queue by state, assignment, and search query before running bulk actions.</p>
              </div>
              <div className={styles.headerLinks}>
                <Link to={`/governance${courseQuery}`} className={shared.linkPill}>Governance</Link>
                <Link to={`/reports${courseQuery}`} className={shared.linkPill}>Reports & Logs</Link>
              </div>
            </header>
            <div className={styles.filterGrid}>
              <label className={styles.filterField}>
                <span className={shared.fieldLabel}>Search queue</span>
                <input className={shared.inlineInput} value={searchQuery} onChange={(event) => setSearchQuery(event.currentTarget.value)} placeholder="Search prompts, content, or learner" />
              </label>
              <label className={styles.filterField}>
                <span className={shared.fieldLabel}>Governance state</span>
                <select className={shared.select} value={stateFilter} onChange={(event) => setStateFilter(event.currentTarget.value as QueueStateFilter)}>
                  <option value="all">All states</option>
                  <option value="open">Open</option>
                  <option value="in_review">In review</option>
                  <option value="resolved">Resolved</option>
                  <option value="archived">Archived</option>
                </select>
              </label>
              <label className={styles.filterField}>
                <span className={shared.fieldLabel}>Assignment</span>
                <select className={shared.select} value={assignmentFilter} onChange={(event) => setAssignmentFilter(event.currentTarget.value as QueueAssignmentFilter)}>
                  <option value="all">All conversations</option>
                  <option value="assigned">Assigned</option>
                  <option value="unassigned">Unassigned</option>
                  <option value="recommended">Recommended owner available</option>
                </select>
              </label>
              <label className={styles.checkboxField}>
                <span className={shared.fieldLabel}>Queue scope</span>
                <span className={styles.checkboxWrap}>
                  <input type="checkbox" checked={includeResolved} onChange={(event) => setIncludeResolved(event.currentTarget.checked)} />
                  <span>Include resolved and archived conversations</span>
                </span>
              </label>
            </div>
          </section>

          {actionMessage ? <p className={styles.successText}>{actionMessage}</p> : null}
          {actionError ? <p className={shared.errorText}>{actionError}</p> : null}
          {isLoading ? <p className={shared.emptyText}>Loading knowledge workspace data...</p> : null}
          {isError ? <p className={shared.errorText}>Failed to load AI governance data.</p> : null}

          <div className={shared.grid2}>
            <section className={shared.panel}>
              <header className={shared.panelHeader}>
                <div>
                  <h2>Conversation queue</h2>
                  <p>Use selection checkboxes for bulk operations or row actions for individual governance handling.</p>
                </div>
                <div className={styles.selectionActions}>
                  <button type="button" className={styles.secondaryButton} onClick={() => setSelectedIds(visibleQueue.map((item) => item.publicId))}>Select visible</button>
                  <button type="button" className={styles.secondaryButton} onClick={() => setSelectedIds([])}>Clear</button>
                </div>
              </header>
              <div className={shared.tableWrap}>
                <table className={shared.table}>
                  <thead>
                    <tr>
                      <th className={styles.checkboxCell}>Select</th>
                      <th>Conversation</th>
                      <th>Status</th>
                      <th>Recommended owner</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleQueue.length === 0 && !isLoading ? (
                      <tr><td colSpan={5}><p className={shared.emptyText}>No AI conversations match the current filters.</p></td></tr>
                    ) : null}
                    {visibleQueue.map((conversation) => {
                      const recommendedOwner = conversation.recommendedOwnerId !== null ? ownerByUserId[conversation.recommendedOwnerId] ?? null : null;
                      return (
                        <tr key={conversation.publicId}>
                          <td className={styles.checkboxCell}>
                            <label className={styles.checkboxOnly}>
                              <input type="checkbox" checked={selectedIds.includes(conversation.publicId)} onChange={() => toggleSelection(conversation.publicId)} />
                            </label>
                          </td>
                          <td>
                            <div className={shared.tableCellStack}>
                              <strong>{conversation.title || "Untitled conversation"}</strong>
                              <span>{conversation.learner.fullName} · {conversation.learner.email}</span>
                              <span>{conversation.content?.name ?? "Detached content"}</span>
                              <span>{conversation.latestUserPrompt}</span>
                            </div>
                          </td>
                          <td>
                            <div className={shared.tableCellStack}>
                              <span className={conversation.governanceStatus === "resolved" ? shared.goodPill : conversation.governanceStatus === "archived" ? shared.warnPill : shared.neutralPill}>{governanceStatusLabel[conversation.governanceStatus]}</span>
                              <span>Assigned: {conversation.assignedTo?.email ?? "Nobody"}</span>
                              <span>Last activity {formatDateTime(conversation.lastActivityAt)}</span>
                            </div>
                          </td>
                          <td>
                            <div className={shared.tableCellStack}>
                              <strong>{recommendedOwner?.fullName ?? (conversation.recommendedOwnerId ? `User #${conversation.recommendedOwnerId}` : "No recommendation")}</strong>
                              <span>{recommendedOwner?.email ?? "Recommended owner not resolved in directory"}</span>
                              <span>SLA {conversation.recommendedOwnerSlaHours ? `${conversation.recommendedOwnerSlaHours}h` : "-"}</span>
                            </div>
                          </td>
                          <td>
                            <div className={styles.rowActions}>
                              {conversation.recommendedOwnerId ? (
                                <button
                                  type="button"
                                  className={styles.secondaryButton}
                                  disabled={bulkBusy}
                                  onClick={() => void updateConversation({
                                    conversationPublicId: conversation.publicId,
                                    body: {
                                      assigned_to_id: conversation.recommendedOwnerId ?? undefined,
                                      governance_status: conversation.governanceStatus === "open" ? "in_review" : conversation.governanceStatus,
                                    },
                                  }).unwrap().then(() => setActionMessage(`Assigned "${conversation.title || conversation.publicId}" to the recommended owner.`)).catch((error) => setActionError(resolveApiErrorMessage(error, "Failed to assign the recommended owner.")))}
                                >
                                  Assign recommended
                                </button>
                              ) : null}
                              <button
                                type="button"
                                className={styles.primaryButton}
                                disabled={bulkBusy}
                                onClick={() => void updateConversation({
                                  conversationPublicId: conversation.publicId,
                                  body: { governance_status: "resolved", resolution_note: sharedNote.trim() },
                                }).unwrap().then(() => setActionMessage(`Resolved "${conversation.title || conversation.publicId}".`)).catch((error) => setActionError(resolveApiErrorMessage(error, "Failed to resolve the conversation.")))}
                              >
                                Resolve
                              </button>
                              <button
                                type="button"
                                className={styles.dangerButton}
                                disabled={bulkBusy}
                                onClick={() => void updateConversation({
                                  conversationPublicId: conversation.publicId,
                                  body: { governance_status: "archived", resolution_note: sharedNote.trim() },
                                }).unwrap().then(() => setActionMessage(`Archived "${conversation.title || conversation.publicId}".`)).catch((error) => setActionError(resolveApiErrorMessage(error, "Failed to archive the conversation.")))}
                              >
                                Archive
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>

            <section className={shared.panel}>
              <header className={shared.panelHeader}>
                <div>
                  <h2>Actions and index health</h2>
                  <p>Resolve or archive the selected conversations, then rebuild the course index when the content surface needs a refresh.</p>
                </div>
              </header>
              <div className={styles.sideStack}>
                <article className={styles.sideCard}>
                  <span className={shared.fieldLabel}>Shared note</span>
                  <textarea className={styles.noteInput} rows={4} value={sharedNote} onChange={(event) => setSharedNote(event.currentTarget.value)} placeholder="Resolution or archive note for bulk actions." />
                  <div className={styles.actionButtons}>
                    <button
                      type="button"
                      className={styles.secondaryButton}
                      disabled={bulkBusy || selectedQueue.length === 0}
                      onClick={() => void runBulkUpdate(
                        selectedQueue.filter((conversation) => Boolean(conversation.recommendedOwnerId) && conversation.governanceStatus !== "resolved" && conversation.governanceStatus !== "archived"),
                        (conversation) => ({
                          assigned_to_id: conversation.recommendedOwnerId ?? undefined,
                          governance_status: conversation.governanceStatus === "open" ? "in_review" : conversation.governanceStatus,
                        }),
                        "Recommended owners assigned"
                      )}
                    >
                      Assign recommended owners
                    </button>
                    <button
                      type="button"
                      className={styles.primaryButton}
                      disabled={bulkBusy || selectedQueue.length === 0}
                      onClick={() => void runBulkUpdate(
                        selectedQueue.filter((conversation) => conversation.governanceStatus !== "resolved" && conversation.governanceStatus !== "archived"),
                        () => ({ governance_status: "resolved", resolution_note: sharedNote.trim() }),
                        "Selected conversations resolved"
                      )}
                    >
                      Resolve selected
                    </button>
                    <button
                      type="button"
                      className={styles.dangerButton}
                      disabled={bulkBusy || selectedQueue.length === 0}
                      onClick={() => void runBulkUpdate(
                        selectedQueue.filter((conversation) => conversation.governanceStatus !== "archived"),
                        () => ({ governance_status: "archived", resolution_note: sharedNote.trim() }),
                        "Selected conversations archived"
                      )}
                    >
                      Archive selected
                    </button>
                  </div>
                </article>

                <article className={styles.sideCard}>
                  <span className={shared.fieldLabel}>Index health</span>
                  <div className={styles.metricList}>
                    <div><strong>AI provider mode</strong><span>{analytics?.providerMode?.toUpperCase() ?? "DEMO"}</span></div>
                    <div><strong>Indexed coverage</strong><span>{overview?.indexedContentItems ?? 0} / {analytics?.publishedContentItems ?? 0}</span></div>
                    <div><strong>Stale / unindexed</strong><span>{analytics?.staleIndexedContentCount ?? 0} / {analytics?.unindexedPublishedItems ?? 0}</span></div>
                    <div><strong>Last index rebuild</strong><span>{formatDateTime(analytics?.latestIndexRebuildAt)}</span></div>
                    <div><strong>Last content sync</strong><span>{formatDateTime(analytics?.latestDirectusSyncAt)}</span></div>
                    <div><strong>Audit / sync / grader failures</strong><span>{reportsOverview?.failedAuditEvents ?? 0} / {reportsOverview?.failedSyncEvents ?? 0} / {reportsOverview?.failedGraderJobs ?? 0}</span></div>
                  </div>
                  <div className={styles.actionButtons}>
                    <button type="button" className={styles.primaryButton} disabled={isRebuildingIndex} onClick={() => void rebuildIndexForCourse()}>
                      {isRebuildingIndex ? "Rebuilding..." : "Rebuild full course index"}
                    </button>
                  </div>
                </article>

                <article className={styles.sideCard}>
                  <span className={shared.fieldLabel}>Queue split</span>
                  <div className={styles.metricList}>
                    <div><strong>Assigned</strong><span>{queueStats.assigned}</span></div>
                    <div><strong>Unassigned</strong><span>{queueStats.unassigned}</span></div>
                    <div><strong>Recommended owner</strong><span>{queueStats.recommended}</span></div>
                    <div><strong>In review</strong><span>{queueStats.inReview}</span></div>
                  </div>
                </article>
              </div>
            </section>
          </div>

          <section className={shared.panel}>
            <header className={shared.panelHeader}>
              <div>
                <h2>Content hotspots</h2>
                <p>These items currently concentrate unresolved learner friction or are the best candidates for a targeted reindex.</p>
              </div>
            </header>
            <div className={shared.tableWrap}>
              <table className={shared.table}>
                <thead>
                  <tr>
                    <th>Content</th>
                    <th>AI questions</th>
                    <th>Unresolved</th>
                    <th>Access denied</th>
                    <th>Latest question</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {analytics?.topContentItems.length ? null : (
                    <tr><td colSpan={6}><p className={shared.emptyText}>No hot-content signals available for the selected course.</p></td></tr>
                  )}
                  {analytics?.topContentItems.map((item) => (
                    <tr key={item.contentId}>
                      <td><div className={shared.tableCellStack}><strong>{item.name}</strong><span>{item.slug}</span></div></td>
                      <td>{item.aiQuestions}</td>
                      <td>{item.unresolvedConversations}</td>
                      <td>{item.accessDeniedCount}</td>
                      <td>{formatDateTime(item.latestQuestionAt)}</td>
                      <td>
                        <button type="button" className={styles.secondaryButton} disabled={isRebuildingIndex} onClick={() => void rebuildIndexForCourse(item.slug)}>
                          Rebuild item
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <div className={shared.grid2}>
            <section className={shared.panel}>
              <header className={shared.panelHeader}>
                <div>
                  <h2>Knowledge sources</h2>
                  <p>Register uploads, transcripts, SharePoint, Confluence, Notion, or external KB sources so AI retrieval and course generation can reuse them.</p>
                </div>
                <span className={shared.sectionHint}>{knowledgeSources.length} source(s)</span>
              </header>
              <div className={shared.list}>
                {knowledgeSources.map((source) => (
                  <button
                    key={source.id}
                    type="button"
                    className={shared.listItem}
                    onClick={() => setSelectedSourceId(source.id)}
                  >
                    <strong>{source.title}</strong>
                    <span>{source.sourceType} · {source.linkedCourseTitle || "No linked course"}</span>
                    <span>{source.externalUrl || "No external URL"}</span>
                  </button>
                ))}
              </div>
              <div className={styles.metricList}>
                <label>
                  <strong>Source title</strong>
                  <input className={shared.inlineInput} value={sourceForm.title} onChange={(event) => setSourceForm((current) => ({ ...current, title: event.currentTarget.value, slug: current.slug || slugify(event.currentTarget.value) }))} />
                </label>
                <label>
                  <strong>Type</strong>
                  <select className={shared.select} value={sourceForm.sourceType} onChange={(event) => setSourceForm((current) => ({ ...current, sourceType: event.currentTarget.value as KnowledgeSourceFormState["sourceType"] }))}>
                    <option value="upload">Upload</option>
                    <option value="url">URL</option>
                    <option value="sharepoint">SharePoint</option>
                    <option value="confluence">Confluence</option>
                    <option value="notion">Notion</option>
                    <option value="video_transcript">Video transcript</option>
                    <option value="audio_transcript">Audio transcript</option>
                    <option value="external_kb">External knowledge base</option>
                  </select>
                </label>
                <label>
                  <strong>Linked course</strong>
                  <select className={shared.select} value={sourceForm.linkedCourseId ?? ""} onChange={(event) => setSourceForm((current) => ({ ...current, linkedCourseId: event.currentTarget.value ? Number(event.currentTarget.value) : null }))}>
                    <option value="">No linked course</option>
                    {(courseDirectory?.results ?? []).map((course) => (
                      <option key={course.id} value={course.id}>
                        {courseDisplayTitle(course)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <strong>External URL</strong>
                  <input className={shared.inlineInput} value={sourceForm.externalUrl} onChange={(event) => setSourceForm((current) => ({ ...current, externalUrl: event.currentTarget.value }))} />
                </label>
              </div>
              <label className={shared.selectWrap}>
                <span className={shared.fieldLabel}>Description</span>
                <textarea className={shared.textarea} rows={3} value={sourceForm.description} onChange={(event) => setSourceForm((current) => ({ ...current, description: event.currentTarget.value }))} />
              </label>
              <div className={styles.actionButtons}>
                <button type="button" className={styles.primaryButton} disabled={createKnowledgeSourceState.isLoading || updateKnowledgeSourceState.isLoading} onClick={onSaveKnowledgeSource}>
                  {createKnowledgeSourceState.isLoading || updateKnowledgeSourceState.isLoading ? "Saving..." : selectedSource ? "Save source" : "Create source"}
                </button>
                {selectedSource ? (
                  <button type="button" className={styles.dangerButton} disabled={deleteKnowledgeSourceState.isLoading} onClick={onDeleteKnowledgeSource}>
                    {deleteKnowledgeSourceState.isLoading ? "Removing..." : "Remove source"}
                  </button>
                ) : null}
              </div>
            </section>

            <section className={shared.panel}>
              <header className={shared.panelHeader}>
                <div>
                  <h2>Knowledge documents</h2>
                  <p>Create KB items, transcripts, markdown notes, or linked references under the selected source.</p>
                </div>
                <span className={shared.sectionHint}>{knowledgeDocuments.length} document(s)</span>
              </header>
              {!selectedSourceId ? <p className={shared.emptyText}>Select a knowledge source first.</p> : null}
              {selectedSourceId ? (
                <>
                  <div className={shared.list}>
                    {knowledgeDocuments.map((document) => (
                      <button key={document.id} type="button" className={shared.listItem} onClick={() => setSelectedDocumentId(document.id)}>
                        <strong>{document.title}</strong>
                        <span>{document.documentType} · {document.language}</span>
                        <span>{document.externalUrl || `${document.chunkCount} chunk(s)`}</span>
                      </button>
                    ))}
                  </div>
                  <div className={styles.metricList}>
                    <label>
                      <strong>Document title</strong>
                      <input className={shared.inlineInput} value={documentForm.title} onChange={(event) => setDocumentForm((current) => ({ ...current, title: event.currentTarget.value }))} />
                    </label>
                    <label>
                      <strong>Document type</strong>
                      <select className={shared.select} value={documentForm.documentType} onChange={(event) => setDocumentForm((current) => ({ ...current, documentType: event.currentTarget.value as KnowledgeDocumentFormState["documentType"] }))}>
                        <option value="markdown">Markdown</option>
                        <option value="transcript">Transcript</option>
                        <option value="link">Link</option>
                        <option value="pdf">PDF</option>
                        <option value="docx">DOCX</option>
                        <option value="html">HTML</option>
                      </select>
                    </label>
                    <label>
                      <strong>Language</strong>
                      <input className={shared.inlineInput} value={documentForm.language} onChange={(event) => setDocumentForm((current) => ({ ...current, language: event.currentTarget.value }))} />
                    </label>
                    <label>
                      <strong>External URL</strong>
                      <input className={shared.inlineInput} value={documentForm.externalUrl} onChange={(event) => setDocumentForm((current) => ({ ...current, externalUrl: event.currentTarget.value }))} />
                    </label>
                  </div>
                  <label className={shared.selectWrap}>
                    <span className={shared.fieldLabel}>Description</span>
                    <textarea className={shared.textarea} rows={2} value={documentForm.description} onChange={(event) => setDocumentForm((current) => ({ ...current, description: event.currentTarget.value }))} />
                  </label>
                  <label className={shared.selectWrap}>
                    <span className={shared.fieldLabel}>Body / notes</span>
                    <textarea className={shared.textarea} rows={4} value={documentForm.documentType === "transcript" ? documentForm.transcriptText : documentForm.bodyMarkdown} onChange={(event) => setDocumentForm((current) => current.documentType === "transcript" ? { ...current, transcriptText: event.currentTarget.value } : { ...current, bodyMarkdown: event.currentTarget.value })} />
                  </label>
                  {registryMessage ? <p className={styles.successText}>{registryMessage}</p> : null}
                  {registryError ? <p className={shared.errorText}>{registryError}</p> : null}
                  <div className={styles.actionButtons}>
                    <button type="button" className={styles.primaryButton} disabled={createKnowledgeDocumentState.isLoading || updateKnowledgeDocumentState.isLoading} onClick={onSaveKnowledgeDocument}>
                      {createKnowledgeDocumentState.isLoading || updateKnowledgeDocumentState.isLoading ? "Saving..." : selectedDocument ? "Save document" : "Create document"}
                    </button>
                    {selectedDocument ? (
                      <button type="button" className={styles.dangerButton} disabled={deleteKnowledgeDocumentState.isLoading} onClick={onDeleteKnowledgeDocument}>
                        {deleteKnowledgeDocumentState.isLoading ? "Removing..." : "Remove document"}
                      </button>
                    ) : null}
                  </div>
                </>
              ) : null}
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
};

export default AdminKnowledgePage;
