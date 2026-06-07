import { useEffect, useMemo, useState } from "react";

import {
  useCreateTrainingAdminUserAudienceGrantMutation,
  useDeleteTrainingAdminUserAudienceGrantMutation,
  useGetTrainingAdminAudiencesQuery,
  useGetTrainingAdminUserAudienceGrantsQuery,
} from "@/bll/training/training.service";
import type { TrainingAdminUserAudienceGrant } from "@/bll/training/training.type";
import type { OnlineAdminUserSummary } from "@/bll/online/online.type";
import DemoRolePolicyFieldset from "@/components/access/DemoRolePolicyFieldset";
import shared from "./AdminPagesShared.module.css";
import styles from "./AdminCuratorDemoRolePanel.module.css";

type Props = {
  selectedUser: OnlineAdminUserSummary | null;
};

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

const pickPrimaryDemoGrant = (grants: TrainingAdminUserAudienceGrant[]) =>
  [...grants].sort(
    (left, right) =>
      right.audience.privilege_rank - left.audience.privilege_rank || right.id - left.id,
  )[0] ?? null;

export const AdminCuratorDemoRolePanel = ({ selectedUser }: Props) => {
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: audienceData, isLoading: isAudiencesLoading } = useGetTrainingAdminAudiencesQuery();
  const { data: grantData, isLoading: isGrantsLoading } = useGetTrainingAdminUserAudienceGrantsQuery(
    selectedUser ? { userId: selectedUser.id, activeOnly: true } : undefined,
    { skip: !selectedUser },
  );
  const [createGrant, createState] = useCreateTrainingAdminUserAudienceGrantMutation();
  const [deleteGrant, deleteState] = useDeleteTrainingAdminUserAudienceGrantMutation();

  const audiences = audienceData?.results ?? [];
  const userDemoRoleGrants = useMemo(
    () =>
      (grantData?.results ?? []).filter(
        (grant) =>
          grant.user.id === selectedUser?.id && grant.audience.audience_type === "demo_role",
      ),
    [grantData?.results, selectedUser?.id],
  );
  const activeGrant = useMemo(() => pickPrimaryDemoGrant(userDemoRoleGrants), [userDemoRoleGrants]);
  const selectedRoleIds = activeGrant ? [activeGrant.audience.id] : [];
  const isSaving = createState.isLoading || deleteState.isLoading;

  useEffect(() => {
    setMessage(null);
    setError(null);
  }, [selectedUser?.id]);

  const syncRoleSelection = async (nextIds: number[]) => {
    if (!selectedUser) return;
    const nextAudienceId = nextIds[0] ?? null;
    const currentAudienceId = activeGrant?.audience.id ?? null;
    if (nextAudienceId === currentAudienceId && userDemoRoleGrants.length <= 1) {
      setMessage(null);
      setError(null);
      return;
    }

    setMessage(null);
    setError(null);

    try {
      await Promise.all(
        userDemoRoleGrants
          .filter((grant) => grant.audience.id !== nextAudienceId)
          .map((grant) => deleteGrant(grant.id).unwrap()),
      );
      if (nextAudienceId && !userDemoRoleGrants.some((grant) => grant.audience.id === nextAudienceId)) {
        await createGrant({
          user_id: selectedUser.id,
          audience_id: nextAudienceId,
          note: "Demo role assignment",
          expires_at: null,
        }).unwrap();
      }
      setMessage(
        nextAudienceId
          ? "Demo learner role updated."
          : "Demo learner role removed. The user now sees only unrestricted content.",
      );
    } catch (mutationError) {
      setError(errorMessageFrom(mutationError, "Failed to update the demo learner role."));
    }
  };

  return (
    <section className={shared.panel}>
      <header className={shared.panelHeader}>
        <div>
          <h2>Demo learner role</h2>
          <p>
            Assign the learner-facing role used by public section pages and access-controlled
            course materials. In demo mode, higher-ranked roles inherit lower-ranked content.
          </p>
        </div>
        {selectedUser ? (
          <span className={shared.sectionHint}>{selectedUser.fullName}</span>
        ) : null}
      </header>

      {!selectedUser ? (
        <p className={shared.emptyText}>Select a registered user first to assign a demo learner role.</p>
      ) : (
        <div className={styles.stack}>
          <div className={styles.summaryGrid}>
            <article className={styles.summaryCard}>
              <span className={shared.fieldLabel}>Selected account</span>
              <strong>{selectedUser.fullName}</strong>
              <span>{selectedUser.email}</span>
            </article>
            <article className={styles.summaryCard}>
              <span className={shared.fieldLabel}>Active demo role</span>
              <strong>{activeGrant?.audience.short_label || activeGrant?.audience.name || "Not assigned"}</strong>
              <span>
                {activeGrant?.audience.description ||
                  "No learner role is currently assigned. Restricted content stays locked."}
              </span>
            </article>
            <article className={styles.summaryCard}>
              <span className={shared.fieldLabel}>Access behavior</span>
              <strong>{activeGrant ? "Role-based access enabled" : "Only unrestricted content"}</strong>
              <span>
                Public section pages show the assigned role and block protected materials
                automatically.
              </span>
            </article>
          </div>

          {isAudiencesLoading || isGrantsLoading ? (
            <p className={shared.emptyText}>Loading demo roles...</p>
          ) : null}

          <DemoRolePolicyFieldset
            audiences={audiences}
            selectedIds={selectedRoleIds}
            selectionMode="single"
            label="Assigned learner role"
            hint="Only one demo learner role should be active for a user at a time. Clear the selection to remove learner-specific access."
            onChange={(nextIds) => {
              void syncRoleSelection(nextIds);
            }}
          />

          <div className={styles.actionRow}>
            <button
              type="button"
              className={styles.secondaryButton}
              disabled={isSaving || selectedRoleIds.length === 0}
              onClick={() => {
                void syncRoleSelection([]);
              }}
            >
              {isSaving ? "Saving..." : "Clear learner role"}
            </button>
          </div>

          {message ? <p className={styles.successText}>{message}</p> : null}
          {error ? <p className={shared.errorText}>{error}</p> : null}
        </div>
      )}
    </section>
  );
};

export default AdminCuratorDemoRolePanel;
