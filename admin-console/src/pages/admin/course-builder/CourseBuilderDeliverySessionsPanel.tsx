import type { OnlineAdminSessionRow } from "@/bll/online/online.type";
import type {
  CourseBuilderDeliverySessionDraft,
  CourseBuilderDeliverySessionsDraft,
} from "./courseBuilderState";
import CollapsibleSection from "./CollapsibleSection";
import styles from "./AdminCourseBuilderModal.module.css";

type Props = {
  isPersistedCourse: boolean;
  hasCohortSelected: boolean;
  courseTitle: string;
  lessonCount: number;
  existingSessions: OnlineAdminSessionRow[];
  remainingSlots: number;
  draft: CourseBuilderDeliverySessionsDraft;
  isLoading?: boolean;
  isSaving: boolean;
  curatorWorkspaceHref?: string | null;
  hasCuratorAssigned: boolean;
  error?: string | null;
  message?: string | null;
  onPatchDraft: (patch: Partial<CourseBuilderDeliverySessionsDraft>) => void;
  onPatchSession: (clientId: string, patch: Partial<CourseBuilderDeliverySessionDraft>) => void;
  onGenerate: () => void;
  onSave: () => void;
};

const formatSessionMoment = (value: string) => {
  if (!value) return "Not scheduled";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const CourseBuilderDeliverySessionsPanel = ({
  isPersistedCourse,
  hasCohortSelected,
  courseTitle,
  lessonCount,
  existingSessions,
  remainingSlots,
  draft,
  isLoading,
  isSaving,
  curatorWorkspaceHref,
  hasCuratorAssigned,
  error,
  message,
  onPatchDraft,
  onPatchSession,
  onGenerate,
  onSave,
}: Props) => {
  if (!isPersistedCourse) {
    return null;
  }

  if (!hasCohortSelected) {
    return (
      <CollapsibleSection
        title="Initial sessions"
        description="Save or select a delivery cohort first. The session wizard becomes available as soon as the cohort exists."
        summary={<span className={styles.statusNote}>Select cohort</span>}
      >
        <p className={styles.emptyState}>
          Delivery scheduling is tied to a cohort. Once the cohort is saved, this wizard can generate the first live meetings
          from the course lesson structure.
        </p>
      </CollapsibleSection>
    );
  }

  return (
    <CollapsibleSection
      title="Initial sessions"
      description={
        <>
          Generate the first live meetings for <strong>{courseTitle || "this course"}</strong> and edit the preview before
          committing it to the cohort schedule.
        </>
      }
      summary={<span className={styles.statusNote}>{remainingSlots} slots remaining</span>}
      actions={
        <>
          <button type="button" className={styles.secondaryButton} onClick={onGenerate} disabled={isLoading || remainingSlots <= 0}>
            Regenerate preview
          </button>
          <button type="button" className={styles.primaryButton} onClick={onSave} disabled={isSaving || draft.sessions.length === 0 || remainingSlots <= 0}>
            {isSaving ? "Creating..." : "Create sessions"}
          </button>
        </>
      }
    >

      <div className={styles.pillRow}>
        <span className={styles.pill}>{lessonCount} lessons in course</span>
        <span className={styles.pill}>{existingSessions.length} sessions already scheduled</span>
        <span className={styles.pill}>{remainingSlots} lesson slots remaining</span>
      </div>

      {message ? <p className={styles.helperSuccess}>{message}</p> : null}
      {error ? <p className={styles.helperError}>{error}</p> : null}
      {isLoading ? <p className={styles.helperText}>Loading cohort sessions...</p> : null}

      {remainingSlots <= 0 ? (
        <p className={styles.emptyState}>
          This cohort already has sessions for every lesson in the current course structure. Use the broader session board if you
          need additional ad-hoc meetings.
        </p>
      ) : (
        <>
          <div className={styles.formGrid}>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>Sessions to create</span>
              <input
                className={styles.input}
                type="number"
                min={1}
                max={Math.max(1, remainingSlots)}
                value={draft.sessionCount}
                onChange={(event) =>
                  onPatchDraft({
                    sessionCount: Math.min(Math.max(Number(event.currentTarget.value) || 1, 1), Math.max(1, remainingSlots)),
                  })
                }
              />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>First start</span>
              <input
                className={styles.input}
                type="datetime-local"
                value={draft.firstStartsAt}
                onChange={(event) => onPatchDraft({ firstStartsAt: event.currentTarget.value })}
              />
            </label>
          </div>

          <div className={styles.formGrid}>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>Duration (minutes)</span>
              <input
                className={styles.input}
                type="number"
                min={15}
                step={15}
                value={draft.durationMinutes}
                onChange={(event) => onPatchDraft({ durationMinutes: Math.max(Number(event.currentTarget.value) || 120, 15) })}
              />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>Interval (days)</span>
              <input
                className={styles.input}
                type="number"
                min={1}
                value={draft.intervalDays}
                onChange={(event) => onPatchDraft({ intervalDays: Math.max(Number(event.currentTarget.value) || 7, 1) })}
              />
            </label>
          </div>

          <div className={styles.deliverySessionsStack}>
            {draft.sessions.length === 0 ? (
              <p className={styles.emptyState}>Generate a preview to review the initial session plan.</p>
            ) : null}
            {draft.sessions.map((session, index) => (
              <article key={session.clientId} className={styles.sessionDraftCard}>
                <div className={styles.cardHeader}>
                  <div className={styles.stack}>
                    <strong>Session {existingSessions.length + index + 1}</strong>
                    <span className={styles.helperText}>{formatSessionMoment(session.startsAt)}</span>
                  </div>
                  <span className={styles.miniPill}>Scheduled</span>
                </div>
                <div className={styles.formGrid}>
                  <label className={styles.field}>
                    <span className={styles.fieldLabel}>Title</span>
                    <input
                      className={styles.input}
                      value={session.title}
                      onChange={(event) => onPatchSession(session.clientId, { title: event.currentTarget.value })}
                    />
                  </label>
                  <label className={styles.field}>
                    <span className={styles.fieldLabel}>Description</span>
                    <input
                      className={styles.input}
                      value={session.description}
                      onChange={(event) => onPatchSession(session.clientId, { description: event.currentTarget.value })}
                    />
                  </label>
                </div>
                <div className={styles.formGrid}>
                  <label className={styles.field}>
                    <span className={styles.fieldLabel}>Starts at</span>
                    <input
                      className={styles.input}
                      type="datetime-local"
                      value={session.startsAt}
                      onChange={(event) => onPatchSession(session.clientId, { startsAt: event.currentTarget.value })}
                    />
                  </label>
                  <label className={styles.field}>
                    <span className={styles.fieldLabel}>Ends at</span>
                    <input
                      className={styles.input}
                      type="datetime-local"
                      value={session.endsAt}
                      onChange={(event) => onPatchSession(session.clientId, { endsAt: event.currentTarget.value })}
                    />
                  </label>
                </div>
              </article>
            ))}
          </div>
        </>
      )}

      {existingSessions.length > 0 ? (
        <div className={styles.deliveryExistingSessions}>
          <div className={styles.cardHeader}>
            <div>
              <h4 className={styles.cardTitle}>Existing cohort schedule</h4>
              <p className={styles.cardText}>These meetings are already attached to the selected cohort.</p>
            </div>
          </div>
          <div className={styles.deliveryExistingSessionList}>
            {existingSessions.map((session) => (
              <div key={session.id} className={styles.deliveryExistingSessionItem}>
                <div className={styles.stack}>
                  <strong>{session.title}</strong>
                  <span className={styles.helperText}>{formatSessionMoment(session.startsAt)}</span>
                </div>
                <span className={styles.miniPill}>{session.status}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className={styles.deliveryBridgeCard}>
        <div className={styles.cardHeader}>
          <div>
            <h4 className={styles.cardTitle}>Instructor bridge</h4>
            <p className={styles.cardText}>
              Send the instructor straight into the online workspace for this cohort so the newly created schedule is visible immediately.
            </p>
          </div>
        </div>
        {curatorWorkspaceHref && hasCuratorAssigned ? (
          <div className={styles.toolbar}>
            <a className={`${styles.secondaryButton} ${styles.buttonLink}`} href={curatorWorkspaceHref} target="_blank" rel="noreferrer">
              Open instructor online workspace
            </a>
            <span className={styles.helperText}>Requires the assigned instructor account.</span>
          </div>
        ) : (
          <p className={styles.emptyState}>Assign an instructor to this cohort to unlock the direct workspace bridge.</p>
        )}
      </div>
    </CollapsibleSection>
  );
};

export default CourseBuilderDeliverySessionsPanel;
