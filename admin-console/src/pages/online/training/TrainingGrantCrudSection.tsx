import { useEffect, useMemo, useState, type FormEvent } from "react";

import {
  useCreateTrainingAdminUserAudienceGrantMutation,
  useDeleteTrainingAdminUserAudienceGrantMutation,
  useGetTrainingAdminUserAudienceGrantsQuery,
  useUpdateTrainingAdminUserAudienceGrantMutation,
} from "@/bll/training/training.service";
import type { TrainingAdminAudience } from "@/bll/training/training.type";
import { formatDateTime, fromDatetimeLocalValue, resolveApiErrorMessage, toDatetimeLocalValue } from "./training.utils";
import cl from "../OnlinePage.module.scss";

type CreateFormState = {
  userId: string;
  audienceId: string;
  note: string;
  expiresAt: string;
};

type EditFormState = {
  note: string;
  expiresAt: string;
};

const emptyCreateForm = (): CreateFormState => ({
  userId: "",
  audienceId: "",
  note: "",
  expiresAt: "",
});

const TrainingGrantCrudSection = ({
  audiences,
  isLoadingAudiences,
  isErrorAudiences,
}: {
  audiences: TrainingAdminAudience[];
  isLoadingAudiences: boolean;
  isErrorAudiences: boolean;
}) => {
  const { data, isLoading, isError } = useGetTrainingAdminUserAudienceGrantsQuery();
  const grants = useMemo(() => data?.results ?? [], [data]);

  const [createForm, setCreateForm] = useState<CreateFormState>(emptyCreateForm());
  const [editingGrantId, setEditingGrantId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<EditFormState | null>(null);
  const [actionError, setActionError] = useState("");

  const [createGrant, { isLoading: isCreating }] = useCreateTrainingAdminUserAudienceGrantMutation();
  const [updateGrant, { isLoading: isUpdating }] = useUpdateTrainingAdminUserAudienceGrantMutation();
  const [deleteGrant, { isLoading: isDeleting }] = useDeleteTrainingAdminUserAudienceGrantMutation();

  const activeAudiences = useMemo(() => audiences.filter((audience) => audience.is_active), [audiences]);

  const sortedGrants = useMemo(
    () =>
      [...grants].sort((left, right) => {
        if (left.user.email !== right.user.email) {
          return left.user.email.localeCompare(right.user.email);
        }
        return left.audience.name.localeCompare(right.audience.name);
      }),
    [grants]
  );

  const editingGrant = useMemo(
    () => sortedGrants.find((grant) => grant.id === editingGrantId) ?? null,
    [editingGrantId, sortedGrants]
  );

  useEffect(() => {
    if (createForm.audienceId || activeAudiences.length === 0) return;
    setCreateForm((current) => ({ ...current, audienceId: String(activeAudiences[0].id) }));
  }, [activeAudiences, createForm.audienceId]);

  useEffect(() => {
    if (!editingGrant) {
      setEditForm(null);
      return;
    }
    setEditForm({
      note: editingGrant.note,
      expiresAt: toDatetimeLocalValue(editingGrant.expires_at),
    });
  }, [editingGrant]);

  const resetCreateForm = () => {
    setCreateForm(emptyCreateForm());
    setActionError("");
  };

  const resetEditForm = () => {
    setEditingGrantId(null);
    setEditForm(null);
    setActionError("");
  };

  const onCreateSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionError("");

    const userId = Number(createForm.userId);
    const audienceId = Number(createForm.audienceId);
    if (!Number.isInteger(userId) || userId <= 0) {
      setActionError("User ID must be a positive integer.");
      return;
    }
    if (!Number.isInteger(audienceId) || audienceId <= 0) {
      setActionError("Audience must be selected.");
      return;
    }

    try {
      await createGrant({
        user_id: userId,
        audience_id: audienceId,
        note: createForm.note.trim(),
        expires_at: fromDatetimeLocalValue(createForm.expiresAt),
      }).unwrap();
      resetCreateForm();
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to create audience grant."));
    }
  };

  const onEditSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editingGrantId || !editForm) return;

    setActionError("");
    try {
      await updateGrant({
        grantId: editingGrantId,
        body: {
          note: editForm.note.trim(),
          expires_at: fromDatetimeLocalValue(editForm.expiresAt),
        },
      }).unwrap();
      resetEditForm();
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to update audience grant."));
    }
  };

  const onDelete = async (grantId: number) => {
    if (!window.confirm("Delete this audience grant?")) {
      return;
    }
    setActionError("");
    try {
      await deleteGrant(grantId).unwrap();
      if (editingGrantId === grantId) {
        resetEditForm();
      }
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to delete audience grant."));
    }
  };

  const busy = isCreating || isUpdating || isDeleting;
  const createDisabled = isLoadingAudiences || isErrorAudiences || activeAudiences.length === 0;

  return (
    <section className={cl.block}>
      <div className={cl.blockHead}>
        <div>
          <h3>Audience Grants</h3>
          <p className={cl.governanceMuted}>Grant users access to external or internal entitlement audiences.</p>
        </div>
        <span className={cl.sectionHint}>{sortedGrants.length} grants</span>
      </div>

      {isLoading ? <p>Loading grants...</p> : null}
      {isError ? <p className={cl.errorText}>Failed to load audience grants.</p> : null}

      <form className={cl.crudForm} onSubmit={onCreateSubmit}>
        <div className={cl.crudGrid}>
          <label className={cl.field}>
            <span className={cl.fieldLabel}>User ID</span>
            <input
              className={cl.fieldInput}
              value={createForm.userId}
              onChange={(event) => setCreateForm((current) => ({ ...current, userId: event.currentTarget.value }))}
              required
              inputMode="numeric"
            />
          </label>
          <label className={cl.field}>
            <span className={cl.fieldLabel}>Audience</span>
            <select
              className={cl.fieldInput}
              value={createForm.audienceId}
              onChange={(event) => setCreateForm((current) => ({ ...current, audienceId: event.currentTarget.value }))}
              required
              disabled={createDisabled}
            >
              {activeAudiences.length === 0 ? <option value="">No active audiences</option> : null}
              {activeAudiences.map((audience) => (
                <option key={audience.id} value={audience.id}>
                  {audience.name} ({audience.slug})
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className={cl.field}>
          <span className={cl.fieldLabel}>Note</span>
          <textarea
            className={cl.fieldTextarea}
            value={createForm.note}
            onChange={(event) => setCreateForm((current) => ({ ...current, note: event.currentTarget.value }))}
            rows={3}
          />
        </label>
        <label className={cl.field}>
          <span className={cl.fieldLabel}>Expires at</span>
          <input
            className={cl.fieldInput}
            type="datetime-local"
            value={createForm.expiresAt}
            onChange={(event) => setCreateForm((current) => ({ ...current, expiresAt: event.currentTarget.value }))}
          />
        </label>
        <p className={cl.governanceMuted}>
          Only active audiences are shown for new grants. If empty, enable or create one first.
        </p>
        {actionError ? <p className={cl.errorText}>{actionError}</p> : null}
        <div className={cl.formActions}>
          <button type="submit" className={cl.primaryButton} disabled={busy || createDisabled}>
            Create grant
          </button>
          <button type="button" className={cl.secondaryButton} onClick={resetCreateForm} disabled={busy}>
            Reset
          </button>
        </div>
      </form>

      {editingGrant && editForm ? (
        <form className={cl.editPanel} onSubmit={onEditSubmit}>
          <div className={cl.blockHead}>
            <h4>Edit grant</h4>
            <span className={cl.sectionHint}>
              {editingGrant.user.email} - {editingGrant.audience.name}
            </span>
          </div>
          <label className={cl.field}>
            <span className={cl.fieldLabel}>Note</span>
            <textarea
              className={cl.fieldTextarea}
              value={editForm.note}
              onChange={(event) => setEditForm((current) => (current ? { ...current, note: event.currentTarget.value } : current))}
              rows={3}
            />
          </label>
          <label className={cl.field}>
            <span className={cl.fieldLabel}>Expires at</span>
            <input
              className={cl.fieldInput}
              type="datetime-local"
              value={editForm.expiresAt}
              onChange={(event) =>
                setEditForm((current) => (current ? { ...current, expiresAt: event.currentTarget.value } : current))
              }
            />
          </label>
          {actionError ? <p className={cl.errorText}>{actionError}</p> : null}
          <div className={cl.formActions}>
            <button type="submit" className={cl.primaryButton} disabled={busy}>
              Save changes
            </button>
            <button type="button" className={cl.secondaryButton} onClick={resetEditForm} disabled={busy}>
              Cancel edit
            </button>
          </div>
        </form>
      ) : null}

      <div className={cl.tableWrap}>
        <table className={cl.dataTable}>
          <thead>
            <tr>
              <th>User</th>
              <th>Audience</th>
              <th>Status</th>
              <th>Expires</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedGrants.length === 0 ? (
              <tr>
                <td colSpan={5}>No audience grants defined yet.</td>
              </tr>
            ) : null}
            {sortedGrants.map((grant) => (
              <tr key={grant.id}>
                <td>
                  <div className={cl.governanceCell}>
                    <strong>{grant.user.email}</strong>
                    {grant.user.username ? <span className={cl.governanceMuted}>{grant.user.username}</span> : null}
                  </div>
                </td>
                <td>
                  <div className={cl.governanceCell}>
                    <strong>{grant.audience.name}</strong>
                    <span className={cl.governanceMuted}>{grant.audience.slug}</span>
                  </div>
                </td>
                <td>
                  <span className={grant.isActive ? cl.governancePrimaryPill : cl.flagPill}>
                    {grant.isActive ? "Active" : "Expired"}
                  </span>
                </td>
                <td>{formatDateTime(grant.expires_at)}</td>
                <td>
                  <div className={cl.actionRow}>
                    <button type="button" className={cl.tableAction} onClick={() => setEditingGrantId(grant.id)}>
                      Edit
                    </button>
                    <button type="button" className={cl.tableDangerAction} onClick={() => onDelete(grant.id)}>
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};

export default TrainingGrantCrudSection;
