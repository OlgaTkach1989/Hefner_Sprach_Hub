import type { OnlineAdminCuratorSummary, OnlineCohortCard } from "@/bll/online/online.type";
import type { OnlineAdminSessionRow } from "@/bll/online/online.type";
import type {
  CourseBuilderDeliveryDraft,
  CourseBuilderDeliverySessionDraft,
  CourseBuilderDeliverySessionsDraft,
} from "./courseBuilderState";
import CollapsibleSection from "./CollapsibleSection";
import CourseBuilderDeliverySessionsPanel from "./CourseBuilderDeliverySessionsPanel";
import styles from "./AdminCourseBuilderModal.module.css";

type Props = {
  isPersistedCourse: boolean;
  courseTitle: string;
  lessonCount: number;
  cohorts: OnlineCohortCard[];
  curators: OnlineAdminCuratorSummary[];
  draft: CourseBuilderDeliveryDraft;
  sessionDraft: CourseBuilderDeliverySessionsDraft;
  existingSessions: OnlineAdminSessionRow[];
  remainingSessionSlots: number;
  isSaving: boolean;
  isLoading?: boolean;
  isCuratorsLoading?: boolean;
  isSessionsLoading?: boolean;
  isSavingSessions?: boolean;
  curatorWorkspaceHref?: string | null;
  hasCuratorAssigned: boolean;
  error?: string | null;
  message?: string | null;
  sessionsError?: string | null;
  sessionsMessage?: string | null;
  onPatchDraft: (patch: Partial<CourseBuilderDeliveryDraft>) => void;
  onSelectExistingCohort: (cohortId: number | null) => void;
  onResetDraft: () => void;
  onSave: () => void;
  onPatchSessionDraft: (patch: Partial<CourseBuilderDeliverySessionsDraft>) => void;
  onPatchSessionItem: (clientId: string, patch: Partial<CourseBuilderDeliverySessionDraft>) => void;
  onGenerateSessions: () => void;
  onSaveSessions: () => void;
};

const CourseBuilderDeliveryPanel = ({
  isPersistedCourse,
  courseTitle,
  lessonCount,
  cohorts,
  curators,
  draft,
  sessionDraft,
  existingSessions,
  remainingSessionSlots,
  isSaving,
  isLoading,
  isCuratorsLoading,
  isSessionsLoading,
  isSavingSessions,
  curatorWorkspaceHref,
  hasCuratorAssigned,
  error,
  message,
  sessionsError,
  sessionsMessage,
  onPatchDraft,
  onSelectExistingCohort,
  onResetDraft,
  onSave,
  onPatchSessionDraft,
  onPatchSessionItem,
  onGenerateSessions,
  onSaveSessions,
}: Props) => {
  if (!isPersistedCourse) {
    return (
      <CollapsibleSection
        title="Delivery assignment"
        description="Save the course first. After that you can create the initial cohort and assign an instructor without leaving the builder."
        summary={<span className={styles.statusNote}>Save draft first</span>}
      >
        <p className={styles.emptyState}>
          The delivery step becomes active as soon as the course is created. The modal will stay open so you can continue directly into cohort setup.
        </p>
      </CollapsibleSection>
    );
  }

  return (
    <div className={styles.stackLarge}>
      <div className={styles.deliveryGrid}>
        <CollapsibleSection
          title="Delivery cohorts"
          description={
            <>
              Review existing cohorts for <strong>{courseTitle || "this course"}</strong> or start a new one from the same workflow.
            </>
          }
          summary={<span className={styles.statusNote}>{cohorts.length} cohorts</span>}
          actions={
            <button type="button" className={styles.secondaryButton} onClick={onResetDraft}>
              New cohort
            </button>
          }
        >

          {isLoading ? <p className={styles.helperText}>Loading course cohorts...</p> : null}

          <div className={styles.deliveryList}>
            {cohorts.length === 0 ? (
              <p className={styles.emptyState}>No cohorts yet. Create the first cohort to put this course into the delivery pipeline.</p>
            ) : null}
            {cohorts.map((cohort) => {
              const active = cohort.id === draft.cohortId;
              return (
                <button
                  key={cohort.id}
                  type="button"
                  className={`${styles.deliveryListItem} ${active ? styles.deliveryListItemActive : ""}`}
                  onClick={() => onSelectExistingCohort(cohort.id)}
                >
                  <div className={styles.cardHeader}>
                    <div className={styles.stack}>
                      <strong>{cohort.groupName}</strong>
                      <span className={styles.helperText}>{cohort.groupCode}</span>
                    </div>
                    <span className={styles.miniPill}>{cohort.status}</span>
                  </div>
                  <div className={styles.templateMeta}>
                    <span className={styles.miniPill}>{cohort.teacherName || "No instructor"}</span>
                    <span className={styles.miniPill}>{cohort.studentsCount} learners</span>
                    <span className={styles.miniPill}>{cohort.isPublic ? "Public" : "Private"}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </CollapsibleSection>

        <CollapsibleSection
          title={draft.cohortId ? "Edit delivery cohort" : "Create delivery cohort"}
          description="Configure the initial cohort and bind it to an instructor so the course becomes visible in the instructor workspace."
          summary={<span className={styles.statusNote}>{draft.status}</span>}
          actions={
            <button type="button" className={styles.primaryButton} onClick={onSave} disabled={isSaving}>
              {isSaving ? "Saving..." : draft.cohortId ? "Update cohort" : "Create cohort"}
            </button>
          }
        >

          {message ? <p className={styles.helperSuccess}>{message}</p> : null}
          {error ? <p className={styles.helperError}>{error}</p> : null}

          <div className={styles.formGrid}>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>Group code</span>
              <input
                className={styles.input}
                value={draft.groupCode}
                onChange={(event) => onPatchDraft({ groupCode: event.currentTarget.value })}
                placeholder="BERLIN_G1"
              />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>Group name</span>
              <input
                className={styles.input}
                value={draft.groupName}
                onChange={(event) => onPatchDraft({ groupName: event.currentTarget.value })}
                placeholder="Berlin Group 1"
              />
            </label>
          </div>

          <div className={styles.formGrid}>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>Capacity</span>
              <input
                className={styles.input}
                type="number"
                min={1}
                value={draft.capacity}
                onChange={(event) => onPatchDraft({ capacity: Number(event.currentTarget.value) || 1 })}
              />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>Timezone</span>
              <input
                className={styles.input}
                value={draft.timezone}
                onChange={(event) => onPatchDraft({ timezone: event.currentTarget.value })}
              />
            </label>
          </div>

          <div className={styles.formGrid}>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>Start date</span>
              <input
                className={styles.input}
                type="date"
                value={draft.startDate}
                onChange={(event) => onPatchDraft({ startDate: event.currentTarget.value })}
              />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>End date</span>
              <input
                className={styles.input}
                type="date"
                value={draft.endDate}
                onChange={(event) => onPatchDraft({ endDate: event.currentTarget.value })}
              />
            </label>
          </div>

          <div className={styles.formGrid}>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>Status</span>
              <select
                className={styles.select}
                value={draft.status}
                onChange={(event) => onPatchDraft({ status: event.currentTarget.value as CourseBuilderDeliveryDraft["status"] })}
              >
                <option value="draft">Draft</option>
                <option value="open">Open</option>
                <option value="running">Running</option>
                <option value="finished">Finished</option>
              </select>
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>Instructor</span>
              <select
                className={styles.select}
                value={draft.curatorId ?? ""}
                onChange={(event) =>
                  onPatchDraft({ curatorId: event.currentTarget.value ? Number(event.currentTarget.value) : null })
                }
                disabled={isCuratorsLoading}
              >
                <option value="">No instructor assigned</option>
                {curators.map((curator) => (
                  <option key={curator.id} value={curator.id}>
                    {curator.fullName} ({curator.shortName})
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className={styles.row}>
            <label className={styles.statusNote}>
              <input
                type="checkbox"
                checked={draft.isPublic}
                onChange={(event) => onPatchDraft({ isPublic: event.currentTarget.checked })}
              />
              Public cohort
            </label>
          </div>
        </CollapsibleSection>
      </div>

      <CourseBuilderDeliverySessionsPanel
        isPersistedCourse={isPersistedCourse}
        hasCohortSelected={Boolean(draft.cohortId)}
        courseTitle={courseTitle}
        lessonCount={lessonCount}
        existingSessions={existingSessions}
        remainingSlots={remainingSessionSlots}
        draft={sessionDraft}
        isLoading={isSessionsLoading}
        isSaving={Boolean(isSavingSessions)}
        curatorWorkspaceHref={curatorWorkspaceHref}
        hasCuratorAssigned={hasCuratorAssigned}
        error={sessionsError}
        message={sessionsMessage}
        onPatchDraft={onPatchSessionDraft}
        onPatchSession={onPatchSessionItem}
        onGenerate={onGenerateSessions}
        onSave={onSaveSessions}
      />
    </div>
  );
};

export default CourseBuilderDeliveryPanel;
