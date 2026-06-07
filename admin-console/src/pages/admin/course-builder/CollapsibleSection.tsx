import type { ReactNode } from "react";
import { useState } from "react";

import styles from "./AdminCourseBuilderModal.module.css";

type Variant = "card" | "step" | "nested" | "lesson" | "item";

type Props = {
  title: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  summary?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  id?: string;
  variant?: Variant;
};

const variantClass: Record<Variant, string> = {
  card: styles.collapsibleCard,
  step: styles.collapsibleStep,
  nested: styles.collapsibleNested,
  lesson: styles.collapsibleLesson,
  item: styles.collapsibleItem,
};

const CollapsibleSection = ({
  title,
  description,
  eyebrow,
  summary,
  actions,
  children,
  defaultOpen = true,
  id,
  variant = "card",
}: Props) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <section
      id={id}
      className={`${styles.collapsibleSection} ${variantClass[variant]} ${isOpen ? styles.collapsibleOpen : ""}`}
    >
      <div className={styles.collapsibleHeader}>
        <button
          type="button"
          className={styles.collapsibleToggle}
          aria-expanded={isOpen}
          onClick={() => setIsOpen((current) => !current)}
        >
          <span className={styles.collapsibleIcon} aria-hidden="true" />
          <span className={styles.collapsibleCopy}>
            {eyebrow ? <span className={styles.collapsibleEyebrow}>{eyebrow}</span> : null}
            <span className={styles.collapsibleTitle}>{title}</span>
            {description ? <span className={styles.collapsibleDescription}>{description}</span> : null}
          </span>
        </button>
        {summary ? <div className={styles.collapsibleSummary}>{summary}</div> : null}
        {actions ? <div className={styles.collapsibleActions}>{actions}</div> : null}
      </div>
      {isOpen ? <div className={styles.collapsibleBody}>{children}</div> : null}
    </section>
  );
};

export default CollapsibleSection;
