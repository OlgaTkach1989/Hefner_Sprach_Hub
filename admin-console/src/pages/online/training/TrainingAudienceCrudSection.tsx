import { useMemo, useState, type FormEvent } from "react";

import {
  useCreateTrainingAdminAudienceMutation,
  useDeleteTrainingAdminAudienceMutation,
  useUpdateTrainingAdminAudienceMutation,
} from "@/bll/training/training.service";
import type { TrainingAdminAudience, TrainingAdminAudienceWriteInput } from "@/bll/training/training.type";
import { resolveApiErrorMessage } from "./training.utils";
import cl from "../OnlinePage.module.scss";

type AudienceFormState = TrainingAdminAudienceWriteInput;

const emptyAudienceForm = (): AudienceFormState => ({
  slug: "",
  name: "",
  short_label: "",
  description: "",
  audience_type: "general",
  privilege_rank: 0,
  is_internal: true,
  is_active: true,
});

type TrainingAudienceCrudSectionProps = {
  audiences: TrainingAdminAudience[];
  isLoading: boolean;
  isError: boolean;
};

const TrainingAudienceCrudSection = ({ audiences, isLoading, isError }: TrainingAudienceCrudSectionProps) => {
  const [form, setForm] = useState<AudienceFormState>(emptyAudienceForm());
  const [editingAudienceId, setEditingAudienceId] = useState<number | null>(null);
  const [actionError, setActionError] = useState("");

  const [createAudience, { isLoading: isCreating }] = useCreateTrainingAdminAudienceMutation();
  const [updateAudience, { isLoading: isUpdating }] = useUpdateTrainingAdminAudienceMutation();
  const [deleteAudience, { isLoading: isDeleting }] = useDeleteTrainingAdminAudienceMutation();

  const sortedAudiences = useMemo(
    () =>
      [...audiences].sort((left, right) => {
        if (left.is_active !== right.is_active) return left.is_active ? -1 : 1;
        return left.name.localeCompare(right.name);
      }),
    [audiences]
  );

  const editingAudience = useMemo(
    () => sortedAudiences.find((item) => item.id === editingAudienceId) ?? null,
    [editingAudienceId, sortedAudiences]
  );

  const resetForm = () => {
    setEditingAudienceId(null);
    setForm(emptyAudienceForm());
    setActionError("");
  };

  const onEdit = (audience: TrainingAdminAudience) => {
    setEditingAudienceId(audience.id);
    setForm({
      slug: audience.slug,
      name: audience.name,
      short_label: audience.short_label,
      description: audience.description,
      audience_type: audience.audience_type,
      privilege_rank: audience.privilege_rank,
      is_internal: audience.is_internal,
      is_active: audience.is_active,
    });
    setActionError("");
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionError("");

    try {
      if (editingAudienceId) {
        await updateAudience({
          audienceId: editingAudienceId,
          body: form,
        }).unwrap();
      } else {
        await createAudience(form).unwrap();
      }
      resetForm();
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to save audience."));
    }
  };

  const onDelete = async (audienceId: number) => {
    if (!window.confirm("Delete this audience? This is only possible when no grants or policies exist.")) {
      return;
    }
    setActionError("");
    try {
      await deleteAudience(audienceId).unwrap();
      if (editingAudienceId === audienceId) {
        resetForm();
      }
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to delete audience."));
    }
  };

  const busy = isCreating || isUpdating || isDeleting;

  return (
    <section className={cl.block}>
      <div className={cl.blockHead}>
        <div>
          <h3>Audiences</h3>
          <p className={cl.governanceMuted}>Define entitlement audiences and control whether they are internal or public.</p>
        </div>
        <span className={cl.sectionHint}>{sortedAudiences.length} audiences</span>
      </div>

      {isLoading ? <p>Loading audiences...</p> : null}
      {isError ? <p className={cl.errorText}>Failed to load audiences.</p> : null}

      <form className={cl.crudForm} onSubmit={onSubmit}>
        <div className={cl.crudGrid}>
          <label className={cl.field}>
            <span className={cl.fieldLabel}>Slug</span>
            <input
              className={cl.fieldInput}
              value={form.slug}
              onChange={(event) => setForm((current) => ({ ...current, slug: event.currentTarget.value }))}
              required
            />
          </label>
          <label className={cl.field}>
            <span className={cl.fieldLabel}>Name</span>
            <input
              className={cl.fieldInput}
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.currentTarget.value }))}
              required
            />
          </label>
          <label className={cl.field}>
            <span className={cl.fieldLabel}>Short label</span>
            <input
              className={cl.fieldInput}
              value={form.short_label}
              onChange={(event) =>
                setForm((current) => ({ ...current, short_label: event.currentTarget.value }))
              }
              placeholder="Short role label"
              required
            />
          </label>
          <label className={cl.field}>
            <span className={cl.fieldLabel}>Audience type</span>
            <select
              className={cl.fieldInput}
              value={form.audience_type}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  audience_type: event.currentTarget.value as AudienceFormState["audience_type"],
                }))
              }
            >
              <option value="general">General</option>
              <option value="demo_role">Demo role</option>
            </select>
          </label>
          <label className={cl.field}>
            <span className={cl.fieldLabel}>Privilege rank</span>
            <input
              className={cl.fieldInput}
              type="number"
              min={0}
              step={10}
              value={form.privilege_rank}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  privilege_rank: Number(event.currentTarget.value || 0),
                }))
              }
            />
          </label>
        </div>
        <label className={cl.field}>
          <span className={cl.fieldLabel}>Description</span>
          <textarea
            className={cl.fieldTextarea}
            value={form.description}
            onChange={(event) => setForm((current) => ({ ...current, description: event.currentTarget.value }))}
            rows={3}
          />
        </label>
        <div className={cl.crudToggleRow}>
          <label className={cl.fieldCheckbox}>
            <input
              type="checkbox"
              checked={form.is_internal}
              onChange={(event) => setForm((current) => ({ ...current, is_internal: event.currentTarget.checked }))}
            />
            Internal audience
          </label>
          <label className={cl.fieldCheckbox}>
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) => setForm((current) => ({ ...current, is_active: event.currentTarget.checked }))}
            />
            Active
          </label>
        </div>
        {actionError ? <p className={cl.errorText}>{actionError}</p> : null}
        <div className={cl.formActions}>
          <button type="submit" className={cl.primaryButton} disabled={busy}>
            {editingAudienceId ? "Save audience" : "Create audience"}
          </button>
          {editingAudienceId ? (
            <button type="button" className={cl.secondaryButton} onClick={resetForm} disabled={busy}>
              Cancel edit
            </button>
          ) : null}
        </div>
      </form>

      {editingAudience ? (
        <div className={cl.editBanner}>
          Editing audience <strong>{editingAudience.name}</strong> ({editingAudience.slug})
        </div>
      ) : null}

      <div className={cl.tableWrap}>
        <table className={cl.dataTable}>
          <thead>
            <tr>
              <th>Audience</th>
              <th>Type</th>
              <th>Status</th>
              <th>Counts</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedAudiences.length === 0 ? (
              <tr>
                <td colSpan={5}>No audiences defined yet.</td>
              </tr>
            ) : null}
            {sortedAudiences.map((audience) => (
              <tr key={audience.id}>
                <td>
                  <div className={cl.governanceCell}>
                    <strong>{audience.name}</strong>
                    <span className={cl.governanceMuted}>{audience.slug}</span>
                    <span className={cl.governanceMuted}>{audience.description || "No description"}</span>
                  </div>
                </td>
                <td>
                  <span
                    className={
                      audience.audience_type === "demo_role"
                        ? cl.governanceRolePill
                        : audience.is_internal
                          ? cl.governancePrimaryPill
                          : cl.flagPill
                    }
                  >
                    {audience.audience_type === "demo_role"
                      ? `Demo role · ${audience.privilege_rank}`
                      : audience.is_internal
                        ? "Internal"
                        : "External"}
                  </span>
                </td>
                <td>
                  <span className={audience.is_active ? cl.governancePrimaryPill : cl.flagPill}>
                    {audience.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td>
                  <div className={cl.governanceCell}>
                    <span>{audience.grantsCount} grants</span>
                    <span className={cl.governanceMuted}>{audience.contentPoliciesCount} content policies</span>
                  </div>
                </td>
                <td>
                  <div className={cl.actionRow}>
                    <button type="button" className={cl.tableAction} onClick={() => onEdit(audience)}>
                      Edit
                    </button>
                    <button type="button" className={cl.tableDangerAction} onClick={() => onDelete(audience.id)}>
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

export default TrainingAudienceCrudSection;
