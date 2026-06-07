import { useMemo, useState } from "react";

import {
  useGetTrainingAdminAiAnalyticsQuery,
  useGetTrainingAdminAiConversationsQuery,
  useGetTrainingAdminAiOverviewQuery,
  useGetTrainingAdminCourseRoleAssignmentsQuery,
  useRebuildTrainingAdminAiIndexMutation,
  useUpdateTrainingAdminAiConversationMutation,
} from "@/bll/training/training.service";
import type {
  TrainingAdminAiConversation,
  TrainingAiGovernanceStatus,
  TrainingAiResolutionStatus,
} from "@/bll/training/training.type";
import { formatDateTime, resolveApiErrorMessage } from "./training.utils";
import cl from "../OnlinePage.module.scss";

const governanceStatusLabel: Record<TrainingAiGovernanceStatus, string> = {
  open: "Open",
  in_review: "In review",
  resolved: "Resolved",
  archived: "Archived",
};

const resolutionStatusLabel: Record<TrainingAiResolutionStatus, string> = {
  resolved: "Resolved",
  partial: "Partial",
  escalate: "Escalate",
};

const formatPercent = (value: number) => `${Math.round(value)}%`;

const TrainingAiGovernanceSection = ({
  courseId,
  courseTitle,
}: {
  courseId: number;
  courseTitle: string;
}) => {
  const {
    data: overview,
    isLoading: isOverviewLoading,
    isError: isOverviewError,
  } = useGetTrainingAdminAiOverviewQuery({ courseId }, { skip: !courseId });
  const {
    data: analytics,
    isLoading: isAnalyticsLoading,
    isError: isAnalyticsError,
  } = useGetTrainingAdminAiAnalyticsQuery({ courseId }, { skip: !courseId });
  const {
    data: queueData,
    isLoading: isQueueLoading,
    isError: isQueueError,
  } = useGetTrainingAdminAiConversationsQuery({ courseId, limit: 50 }, { skip: !courseId });
  const { data: ownerAssignmentsData } = useGetTrainingAdminCourseRoleAssignmentsQuery({ courseId }, { skip: !courseId });

  const [updateConversation, { isLoading: isUpdatingConversation }] = useUpdateTrainingAdminAiConversationMutation();
  const [rebuildKnowledgeIndex, { isLoading: isRebuildingIndex }] = useRebuildTrainingAdminAiIndexMutation();

  const [notesByConversation, setNotesByConversation] = useState<Record<string, string>>({});
  const [busyConversationId, setBusyConversationId] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");

  const queue = useMemo(() => queueData?.results ?? [], [queueData]);
  const ownerAssignments = useMemo(
    () => (ownerAssignmentsData?.results ?? []).filter((assignment) => assignment.role === "owner"),
    [ownerAssignmentsData]
  );
  const ownerByUserId = useMemo(
    () =>
      ownerAssignments.reduce<Record<number, (typeof ownerAssignments)[number]["user"]>>((acc, assignment) => {
        acc[assignment.user.id] = assignment.user;
        return acc;
      }, {}),
    [ownerAssignments]
  );

  const isLoading = isOverviewLoading || isAnalyticsLoading || isQueueLoading;
  const isError = isOverviewError || isAnalyticsError || isQueueError;

  const setNoteValue = (conversationPublicId: string, value: string) => {
    setNotesByConversation((current) => ({ ...current, [conversationPublicId]: value }));
  };

  const runConversationAction = async (
    conversation: TrainingAdminAiConversation,
    body: {
      assigned_to_id?: number | null;
      governance_status?: TrainingAiGovernanceStatus;
      resolution_note?: string;
    },
    successMessage: string
  ) => {
    setActionError("");
    setActionSuccess("");
    setBusyConversationId(conversation.publicId);
    try {
      await updateConversation({
        conversationPublicId: conversation.publicId,
        body,
      }).unwrap();
      setActionSuccess(successMessage);
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to update AI governance state."));
    } finally {
      setBusyConversationId(null);
    }
  };

  const onAssignRecommended = async (conversation: TrainingAdminAiConversation) => {
    if (!conversation.recommendedOwnerId) return;
    await runConversationAction(
      conversation,
      {
        assigned_to_id: conversation.recommendedOwnerId,
        governance_status:
          conversation.governanceStatus === "open" ? "in_review" : conversation.governanceStatus,
      },
      `Assigned conversation "${conversation.title || conversation.publicId}" to the recommended owner.`
    );
  };

  const onResolve = async (conversation: TrainingAdminAiConversation) => {
    await runConversationAction(
      conversation,
      {
        governance_status: "resolved",
        resolution_note: (notesByConversation[conversation.publicId] ?? conversation.resolutionNote ?? "").trim(),
      },
      `Marked conversation "${conversation.title || conversation.publicId}" as resolved.`
    );
  };

  const onArchive = async (conversation: TrainingAdminAiConversation) => {
    await runConversationAction(
      conversation,
      {
        governance_status: "archived",
        resolution_note: (notesByConversation[conversation.publicId] ?? conversation.resolutionNote ?? "").trim(),
      },
      `Archived conversation "${conversation.title || conversation.publicId}".`
    );
  };

  const onRebuildIndex = async () => {
    setActionError("");
    setActionSuccess("");
    try {
      const result = await rebuildKnowledgeIndex({ course_id: courseId }).unwrap();
      setActionSuccess(
        `Knowledge index rebuilt for ${result.rebuiltContentItems} content items and ${result.rebuiltChunks} chunks.`
      );
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to rebuild the training knowledge index."));
    }
  };

  return (
    <section className={cl.block}>
      <div className={cl.blockHead}>
        <div>
          <h3>AI Governance</h3>
          <p className={cl.governanceMuted}>
            Review unresolved AI questions, route escalations to course owners, and keep the knowledge index healthy for{" "}
            {courseTitle}.
          </p>
        </div>
        <div className={cl.aiHeaderActions}>
          <span className={cl.sectionHint}>Course ID {courseId}</span>
          <button type="button" className={cl.secondaryButton} onClick={onRebuildIndex} disabled={isRebuildingIndex}>
            {isRebuildingIndex ? "Rebuilding..." : "Rebuild knowledge index"}
          </button>
        </div>
      </div>

      {isLoading ? <p>Loading AI governance data...</p> : null}
      {isError ? <p className={cl.errorText}>Failed to load AI governance data.</p> : null}
      {actionError ? <p className={cl.errorText}>{actionError}</p> : null}
      {actionSuccess ? <p className={cl.successText}>{actionSuccess}</p> : null}

      {!isLoading && !isError && overview ? (
        <>
          <section className={cl.kpiGrid}>
            <div className={cl.kpiCard}>
              <span className={cl.kpiLabel}>Unresolved queue</span>
              <strong>{overview.unresolvedQueueCount}</strong>
              <span className={cl.governanceMuted}>{overview.aiConversations} total AI conversations</span>
            </div>
            <div className={cl.kpiCard}>
              <span className={cl.kpiLabel}>Assigned queue</span>
              <strong>{overview.assignedQueueCount}</strong>
              <span className={cl.governanceMuted}>Items already routed to owners or admins</span>
            </div>
            <div className={cl.kpiCard}>
              <span className={cl.kpiLabel}>Escalations / partials</span>
              <strong>
                {overview.escalatedResponses} / {overview.partialResponses}
              </strong>
              <span className={cl.governanceMuted}>AI answers that still need human follow-up</span>
            </div>
            <div className={cl.kpiCard}>
              <span className={cl.kpiLabel}>FAQ coverage</span>
              <strong>{formatPercent(overview.faqCoveragePercent)}</strong>
              <span className={cl.governanceMuted}>
                {overview.contentItemsCoveredByFaq} content items linked to FAQ
              </span>
            </div>
            <div className={cl.kpiCard}>
              <span className={cl.kpiLabel}>Indexed chunks</span>
              <strong>{overview.indexedChunks}</strong>
              <span className={cl.governanceMuted}>{overview.indexedContentItems} content items currently indexed</span>
            </div>
          </section>

          {analytics ? (
            <>
              <section className={cl.kpiGrid}>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>AI runtime</span>
                  <strong>{analytics.providerMode.toUpperCase()}</strong>
                  <span className={cl.governanceMuted}>
                    Provider configured: {analytics.externalProviderConfigured ? "yes" : "no"} / pgvector:{" "}
                    {analytics.pgvectorEnabled ? "on" : "off"}
                  </span>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Window health</span>
                  <strong>
                    {analytics.aiQuestionsWindow} / {analytics.aiResponseFailuresWindow}
                  </strong>
                  <span className={cl.governanceMuted}>
                    Questions / AI failures in the last {analytics.windowDays} days
                  </span>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Directus sync</span>
                  <strong>
                    {analytics.directusSyncAppliedWindow} / {analytics.directusSyncFailedWindow}
                  </strong>
                  <span className={cl.governanceMuted}>
                    Applied / failed. Last sync: {formatDateTime(analytics.latestDirectusSyncAt)}
                  </span>
                </div>
                <div className={cl.kpiCard}>
                  <span className={cl.kpiLabel}>Index freshness</span>
                  <strong>
                    {analytics.staleIndexedContentCount} / {analytics.unindexedPublishedItems}
                  </strong>
                  <span className={cl.governanceMuted}>
                    Stale / unindexed published items. Last rebuild: {formatDateTime(analytics.latestIndexRebuildAt)}
                  </span>
                </div>
              </section>

              <div className={cl.tableWrap}>
                <table className={cl.dataTable}>
                  <thead>
                    <tr>
                      <th>Operational signal</th>
                      <th>Value</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Escalations / quiz failures</td>
                      <td>
                        {analytics.aiEscalationsWindow} / {analytics.quizSubmitFailuresWindow}
                      </td>
                      <td>Escalation pressure versus quiz friction in the current window.</td>
                    </tr>
                    <tr>
                      <td>Access denied</td>
                      <td>{analytics.contentAccessDeniedWindow}</td>
                      <td>Useful for spotting entitlement misconfiguration and hidden-content drift.</td>
                    </tr>
                    <tr>
                      <td>Directus managed content</td>
                      <td>
                        {analytics.directusManagedContentItems} items / {analytics.directusItemsWithoutOwner} without owner
                      </td>
                      <td>Owner gaps are the fastest way to miss SLA on unresolved AI questions.</td>
                    </tr>
                    <tr>
                      <td>Resolution speed</td>
                      <td>{analytics.avgResolutionHours !== null ? `${analytics.avgResolutionHours}h` : "-"}</td>
                      <td>Average time to resolve governance-reviewed AI conversations.</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className={cl.tableWrap}>
                <table className={cl.dataTable}>
                  <thead>
                    <tr>
                      <th>Hot content</th>
                      <th>AI questions</th>
                      <th>Unresolved</th>
                      <th>Access denied</th>
                      <th>Latest question</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analytics.topContentItems.length === 0 ? (
                      <tr>
                        <td colSpan={5}>No hot content signals for the selected course yet.</td>
                      </tr>
                    ) : null}
                    {analytics.topContentItems.map((item) => (
                      <tr key={item.contentId}>
                        <td>
                          <div className={cl.governanceCell}>
                            <strong>{item.name}</strong>
                            <span className={cl.governanceMuted}>{item.slug}</span>
                          </div>
                        </td>
                        <td>{item.aiQuestions}</td>
                        <td>{item.unresolvedConversations}</td>
                        <td>{item.accessDeniedCount}</td>
                        <td>{formatDateTime(item.latestQuestionAt)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}

          <div className={cl.tableWrap}>
            <table className={cl.dataTable}>
              <thead>
                <tr>
                  <th>Conversation</th>
                  <th>AI status</th>
                  <th>Recommended owner</th>
                  <th>Governance</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {queue.length === 0 ? (
                  <tr>
                    <td colSpan={5}>No unresolved AI conversations for this course.</td>
                  </tr>
                ) : null}
                {queue.map((conversation) => {
                  const recommendedOwner =
                    conversation.recommendedOwnerId !== null
                      ? ownerByUserId[conversation.recommendedOwnerId] ?? null
                      : null;
                  const noteValue = notesByConversation[conversation.publicId] ?? conversation.resolutionNote ?? "";
                  const isBusy = isUpdatingConversation && busyConversationId === conversation.publicId;
                  const canAssignRecommended =
                    conversation.recommendedOwnerId !== null &&
                    (conversation.assignedTo?.id ?? null) !== conversation.recommendedOwnerId &&
                    conversation.governanceStatus !== "resolved" &&
                    conversation.governanceStatus !== "archived";

                  return (
                    <tr key={conversation.publicId}>
                      <td>
                        <div className={cl.governanceCell}>
                          <strong>{conversation.title || "Untitled conversation"}</strong>
                          <span className={cl.governanceMuted}>
                            Learner: {conversation.learner.fullName} ({conversation.learner.email})
                          </span>
                          <span className={cl.governanceMuted}>
                            Content: {conversation.content?.name ?? "Detached content"}
                          </span>
                          <p className={cl.aiPreview}>
                            <strong>Prompt:</strong> {conversation.latestUserPrompt}
                          </p>
                          <p className={cl.aiPreview}>
                            <strong>Assistant:</strong> {conversation.latestAssistantBody || "No assistant preview available."}
                          </p>
                        </div>
                      </td>
                      <td>
                        <div className={cl.governanceCell}>
                          <span
                            className={
                              conversation.latestResolutionStatus === "resolved"
                                ? cl.governancePrimaryPill
                                : conversation.latestResolutionStatus === "escalate"
                                  ? cl.flagPill
                                  : cl.governanceRolePill
                            }
                          >
                            {conversation.latestResolutionStatus
                              ? resolutionStatusLabel[conversation.latestResolutionStatus]
                              : "Unknown"}
                          </span>
                          <span className={cl.governanceMuted}>
                            {conversation.userMessageCount} learner / {conversation.assistantMessageCount} assistant messages
                          </span>
                          <span className={cl.governanceMuted}>
                            Last AI response: {formatDateTime(conversation.latestAssistantCreatedAt)}
                          </span>
                        </div>
                      </td>
                      <td>
                        <div className={cl.governanceCell}>
                          <strong>
                            {recommendedOwner?.fullName ??
                              (conversation.recommendedOwnerId ? `User #${conversation.recommendedOwnerId}` : "Unassigned")}
                          </strong>
                          <span className={cl.governanceMuted}>
                            {recommendedOwner?.email ?? "No explicit owner suggestion"}
                          </span>
                          <span className={cl.governanceMuted}>
                            SLA: {conversation.recommendedOwnerSlaHours ? `${conversation.recommendedOwnerSlaHours}h` : "-"}
                          </span>
                        </div>
                      </td>
                      <td>
                        <div className={cl.governanceCell}>
                          <span
                            className={
                              conversation.governanceStatus === "resolved"
                                ? cl.governancePrimaryPill
                                : conversation.governanceStatus === "archived"
                                  ? cl.flagPill
                                  : cl.governanceRolePill
                            }
                          >
                            {governanceStatusLabel[conversation.governanceStatus]}
                          </span>
                          <span className={cl.governanceMuted}>
                            Assigned: {conversation.assignedTo?.email ?? "Nobody"}
                          </span>
                          <span className={cl.governanceMuted}>
                            Last activity: {formatDateTime(conversation.lastActivityAt)}
                          </span>
                          {conversation.resolvedBy ? (
                            <span className={cl.governanceMuted}>
                              Resolved by {conversation.resolvedBy.email} at {formatDateTime(conversation.resolvedAt)}
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td>
                        <div className={cl.aiActionCell}>
                          <label className={cl.field}>
                            <span className={cl.fieldLabel}>Resolution note</span>
                            <textarea
                              className={`${cl.fieldTextarea} ${cl.aiNoteInput}`}
                              value={noteValue}
                              onChange={(event) => setNoteValue(conversation.publicId, event.currentTarget.value)}
                              rows={3}
                              disabled={isBusy}
                            />
                          </label>
                          <div className={cl.aiButtonRow}>
                            {canAssignRecommended ? (
                              <button
                                type="button"
                                className={cl.secondaryButton}
                                onClick={() => onAssignRecommended(conversation)}
                                disabled={isBusy}
                              >
                                Assign recommended
                              </button>
                            ) : null}
                            <button
                              type="button"
                              className={cl.primaryButton}
                              onClick={() => onResolve(conversation)}
                              disabled={isBusy}
                            >
                              Resolve
                            </button>
                            <button
                              type="button"
                              className={cl.tableDangerAction}
                              onClick={() => onArchive(conversation)}
                              disabled={isBusy}
                            >
                              Archive
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  );
};

export default TrainingAiGovernanceSection;
