import { useDeferredValue, useMemo, useState } from "react";

import type { CourseBuilderTemplateSummary } from "@/bll/course-builder/courseBuilder.type";
import CollapsibleSection from "./CollapsibleSection";
import styles from "./AdminCourseBuilderModal.module.css";

type Props = {
  templates: CourseBuilderTemplateSummary[];
  selectedTemplateId: number | null;
  onApplyTemplate: (templateId: number) => void;
  onClearTemplate: () => void;
  isLoading?: boolean;
  isError?: boolean;
};

const CourseBuilderTemplatePanel = ({
  templates,
  selectedTemplateId,
  onApplyTemplate,
  onClearTemplate,
  isLoading,
  isError,
}: Props) => {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());

  const filteredTemplates = useMemo(() => {
    if (!deferredQuery) return templates;
    return templates.filter((template) =>
      [template.title, template.slug, template.description].join(" ").toLowerCase().includes(deferredQuery),
    );
  }, [deferredQuery, templates]);

  return (
    <div className={styles.stack}>
      <CollapsibleSection
        title="Choose a course template"
        description="Start from a reusable course skeleton or continue with a blank course and define your own structure."
        summary={<span className={styles.statusNote}>{filteredTemplates.length} templates</span>}
        actions={
          selectedTemplateId ? (
            <button type="button" className={styles.ghostButton} onClick={onClearTemplate}>
              Clear template
            </button>
          ) : null
        }
      >

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Search templates</span>
          <input
            className={styles.input}
            value={query}
            onChange={(event) => setQuery(event.currentTarget.value)}
            placeholder="Template name, slug, or description"
          />
        </label>

        {isLoading ? <p className={styles.helperText}>Loading templates...</p> : null}
        {isError ? <p className={styles.helperText}>Failed to load templates.</p> : null}
      </CollapsibleSection>

      <div className={styles.templateGrid}>
        {filteredTemplates.length === 0 ? (
          <p className={styles.emptyState}>No templates match the current search.</p>
        ) : null}
        {filteredTemplates.map((template) => {
          const active = template.id === selectedTemplateId;
          return (
            <article
              key={template.id}
              className={`${styles.templateCard} ${active ? styles.templateCardActive : ""}`}
            >
              <div className={styles.templateMeta}>
                <span className={styles.miniPill}>{template.defaultLessonsCount} lessons</span>
                <span className={styles.miniPill}>{template.slug}</span>
              </div>
              <strong>{template.title}</strong>
              <span>{template.description}</span>
              <div className={styles.row}>
                <button type="button" className={styles.primaryButton} onClick={() => onApplyTemplate(template.id)}>
                  {active ? "Template selected" : "Apply template"}
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
};

export default CourseBuilderTemplatePanel;
