import type { TrainingAdminAudience } from "@/bll/training/training.type";

import styles from "./DemoRolePolicyFieldset.module.css";

type Props = {
  audiences: TrainingAdminAudience[];
  selectedIds: number[];
  label: string;
  hint: string;
  emptyText?: string;
  selectionMode?: "multiple" | "single";
  onChange: (nextIds: number[]) => void;
};

const DemoRolePolicyFieldset = ({
  audiences,
  selectedIds,
  label,
  hint,
  emptyText = "No active demo roles available yet.",
  selectionMode = "multiple",
  onChange,
}: Props) => {
  const demoRoleAudiences = audiences
    .filter((audience) => audience.is_active && audience.audience_type === "demo_role")
    .sort((left, right) => left.privilege_rank - right.privilege_rank || left.name.localeCompare(right.name));

  const toggleAudience = (audienceId: number) => {
    if (selectedIds.includes(audienceId)) {
      onChange(selectedIds.filter((item) => item !== audienceId));
      return;
    }
    if (selectionMode === "single") {
      onChange([audienceId]);
      return;
    }
    onChange([...selectedIds, audienceId].sort((left, right) => left - right));
  };

  return (
    <section className={styles.field}>
      <header className={styles.header}>
        <span className={styles.label}>{label}</span>
        <p className={styles.hint}>{hint}</p>
      </header>

      {demoRoleAudiences.length === 0 ? <p className={styles.empty}>{emptyText}</p> : null}

      {demoRoleAudiences.length > 0 ? (
        <div className={styles.grid}>
          {demoRoleAudiences.map((audience) => {
            const isActive = selectedIds.includes(audience.id);
            return (
              <label
                key={audience.id}
                className={`${styles.option} ${isActive ? styles.optionActive : ""}`}
              >
                <div className={styles.titleRow}>
                  <input
                    className={styles.checkbox}
                    type="checkbox"
                    checked={isActive}
                    onChange={() => toggleAudience(audience.id)}
                  />
                  <span className={styles.title}>{audience.short_label || audience.name}</span>
                </div>
                <span className={styles.badge}>Level {audience.privilege_rank}</span>
                <p className={styles.description}>{audience.description || audience.name}</p>
              </label>
            );
          })}
        </div>
      ) : null}
    </section>
  );
};

export default DemoRolePolicyFieldset;
