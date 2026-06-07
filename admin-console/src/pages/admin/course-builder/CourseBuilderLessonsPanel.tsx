import { useState } from "react";

import type {
  CourseBuilderAssetType,
  CourseBuilderLibraryItem,
  CourseBuilderNotebookOption,
  CourseBuilderSectionType,
} from "@/bll/course-builder/courseBuilder.type";
import type { TrainingAdminAudience } from "@/bll/training/training.type";
import DemoRolePolicyFieldset from "@/components/access/DemoRolePolicyFieldset";
import type {
  CourseBuilderCourseDraft,
  CourseBuilderLessonDraft,
  CourseBuilderModuleDraft,
  CourseBuilderSectionDraft,
  CourseBuilderSectionItemDraft,
} from "./courseBuilderState";
import {
  getLessonDocumentPreset,
  lessonDocumentPresets,
  parseLessonDocumentFile,
  type ImportedLessonDocument,
} from "./lessonDocumentBlueprints";
import CollapsibleSection from "./CollapsibleSection";
import styles from "./AdminCourseBuilderModal.module.css";

type Props = {
  draft: CourseBuilderCourseDraft;
  libraryItems: CourseBuilderLibraryItem[];
  notebookOptions: CourseBuilderNotebookOption[];
  audiences: TrainingAdminAudience[];
  onAddModule: () => void;
  onRemoveModule: (moduleClientId: string) => void;
  onPatchModule: (moduleClientId: string, patch: Partial<CourseBuilderModuleDraft>) => void;
  onAddLesson: () => void;
  onRemoveLesson: (lessonClientId: string) => void;
  onPatchLesson: (lessonClientId: string, patch: Partial<CourseBuilderLessonDraft>) => void;
  onPatchSection: (lessonClientId: string, sectionType: CourseBuilderSectionType, patch: Partial<CourseBuilderSectionDraft>) => void;
  onAddSectionItem: (
    lessonClientId: string,
    sectionType: CourseBuilderSectionType,
    seed: Pick<CourseBuilderSectionItemDraft, "assetType"> & Partial<CourseBuilderSectionItemDraft>,
  ) => void;
  onRemoveSectionItem: (lessonClientId: string, sectionType: CourseBuilderSectionType, itemClientId: string) => void;
  onPatchSectionItem: (
    lessonClientId: string,
    sectionType: CourseBuilderSectionType,
    itemClientId: string,
    patch: Partial<CourseBuilderSectionItemDraft>,
  ) => void;
  onApplyLibraryItemToSectionItem: (
    lessonClientId: string,
    sectionType: CourseBuilderSectionType,
    itemClientId: string,
    libraryItemId: number,
  ) => void;
  onOpenLibraryForm: (sectionType: CourseBuilderSectionType) => void;
  onReplaceLessonDocument: (lessonClientId: string, document: ImportedLessonDocument) => void;
  onGenerateLesson: (lessonClientId: string, draft: LessonGeneratorDraft) => Promise<string>;
};

export type LessonGeneratorDraft = {
  sourceText: string;
  language: "de" | "en";
  videoUrl: string;
  videoDescription: string;
  videoFile: File | null;
};

type LessonToolbarSeed = {
  assetType: CourseBuilderAssetType;
  activityType?: CourseBuilderSectionItemDraft["activityType"];
  title: string;
  description: string;
  bodyMarkdown?: string;
};

const sectionTitleLabel: Record<CourseBuilderSectionType, string> = {
  introduction: "Introduction",
  main: "Main content",
  conclusion: "Conclusion",
};

const assetTypeLabel: Record<CourseBuilderAssetType, string> = {
  text: "Text",
  document: "Document",
  link: "Link",
  notebook: "Notebook",
};

const toInputValue = (value?: string | null) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
};

const toIsoValue = (value: string) => {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toISOString();
};

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const markdownPreviewHtml = (body: string) => {
  const blocks = body
    .split(/\n\s*\n/g)
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks
    .map((block) => {
      if (/^#{1,6}\s/.test(block)) {
        const level = Math.min(block.match(/^#+/)?.[0].length ?? 1, 6);
        return `<h${level}>${escapeHtml(block.replace(/^#{1,6}\s+/, ""))}</h${level}>`;
      }

      const listRows = block
        .split("\n")
        .map((row) => row.trim())
        .filter(Boolean);

      if (listRows.length > 0 && listRows.every((row) => row.startsWith("- "))) {
        return `<ul>${listRows.map((row) => `<li>${escapeHtml(row.slice(2))}</li>`).join("")}</ul>`;
      }

      if (block.startsWith("```")) {
        return `<pre><code>${escapeHtml(block.replace(/^```[a-z]*\n?/i, "").replace(/```$/, "").trim())}</code></pre>`;
      }

      return `<p>${escapeHtml(block)}</p>`;
    })
    .join("");
};

const lessonGenerationErrorMessage = (error: unknown) => {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  if (error && typeof error === "object") {
    const maybeError = error as {
      data?: unknown;
      error?: string;
      status?: string | number;
    };
    if (maybeError.data && typeof maybeError.data === "object") {
      const data = maybeError.data as Record<string, unknown>;
      if (typeof data.detail === "string" && data.detail.trim()) {
        return data.detail.trim();
      }
      const fieldMessages = Object.values(data)
        .flatMap((value) => (Array.isArray(value) ? value : [value]))
        .map((value) => String(value || "").trim())
        .filter(Boolean);
      if (fieldMessages.length > 0) {
        return fieldMessages.join(" ");
      }
    }
    if (typeof maybeError.error === "string" && maybeError.error.trim()) {
      if (maybeError.error.includes("Unexpected token '<'")) {
        return "The server returned an HTML error page instead of JSON. The generation request probably timed out. Please try again.";
      }
      return maybeError.error.trim();
    }
  }
  return "Failed to generate the lesson flow.";
};

const lessonBlockSeed = (kind: "reading" | "document" | "video" | "quiz" | "notebook"): LessonToolbarSeed => {
  switch (kind) {
    case "document":
      return {
        assetType: "document",
        activityType: "text",
        title: "Document asset",
        description: "Attach a PDF, deck, or other structured lesson file.",
      };
    case "video":
      return {
        assetType: "link",
        activityType: "video",
        title: "Video block",
        description: "Attach a lecture video or screen recording.",
      };
    case "quiz":
      return {
        assetType: "text",
        activityType: "quiz",
        title: "Quiz block",
        description: "Short knowledge check embedded inside the lesson document.",
        bodyMarkdown: "## Quick check\n\n- Add your first question\n- Add your second question\n- Add the checkpoint explanation",
      };
    case "notebook":
      return {
        assetType: "notebook",
        activityType: "assignment",
        title: "Notebook assignment",
        description: "Managed Jupyter notebook task linked to the academy runtime.",
        bodyMarkdown:
          "### Notebook brief\n\nDescribe the coding objective, success criteria, and what the learner must submit after using JupyterLab.",
      };
    default:
      return {
        assetType: "text",
        activityType: "text",
        title: "Reading block",
        description: "Theory, explanation, or delivery guidance.",
        bodyMarkdown: "## Reading block\n\nAdd the lesson explanation, formulas, or step-by-step instructions here.",
      };
  }
};

const CourseBuilderLessonsPanel = ({
  draft,
  libraryItems,
  notebookOptions,
  audiences,
  onAddModule,
  onRemoveModule,
  onPatchModule,
  onAddLesson,
  onRemoveLesson,
  onPatchLesson,
  onPatchSection,
  onAddSectionItem,
  onRemoveSectionItem,
  onPatchSectionItem,
  onApplyLibraryItemToSectionItem,
  onOpenLibraryForm,
  onReplaceLessonDocument,
  onGenerateLesson,
}: Props) => {
  const [presetByLesson, setPresetByLesson] = useState<Record<string, string>>({});
  const [lessonMessages, setLessonMessages] = useState<Record<string, string>>({});
  const [lessonErrors, setLessonErrors] = useState<Record<string, string>>({});
  const [generatorByLesson, setGeneratorByLesson] = useState<Record<string, LessonGeneratorDraft>>({});
  const [generatorBusyByLesson, setGeneratorBusyByLesson] = useState<Record<string, boolean>>({});
  const [successDialog, setSuccessDialog] = useState<{ title: string; message: string } | null>(null);

  const setLessonNotice = (lessonClientId: string, message: string) => {
    setLessonMessages((current) => ({ ...current, [lessonClientId]: message }));
    setLessonErrors((current) => ({ ...current, [lessonClientId]: "" }));
  };

  const setLessonFailure = (lessonClientId: string, message: string) => {
    setLessonErrors((current) => ({ ...current, [lessonClientId]: message }));
    setLessonMessages((current) => ({ ...current, [lessonClientId]: "" }));
  };

  const generatorDraftForLesson = (lesson: CourseBuilderLessonDraft): LessonGeneratorDraft => {
    const stored = generatorByLesson[lesson.clientId];
    if (stored) {
      return stored;
    }
    return {
      sourceText: "",
      language: "en",
      videoUrl: "",
      videoDescription: "",
      videoFile: null,
    };
  };

  const patchGeneratorDraft = (lessonClientId: string, patch: Partial<LessonGeneratorDraft>) => {
    setGeneratorByLesson((current) => ({
      ...current,
      [lessonClientId]: {
        ...(current[lessonClientId] ?? {
          sourceText: "",
          language: "en",
          videoUrl: "",
          videoDescription: "",
          videoFile: null,
        }),
        ...patch,
      },
    }));
  };

  const applyPresetToLesson = (lessonClientId: string) => {
    const presetId = presetByLesson[lessonClientId];
    if (!presetId) {
      setLessonFailure(lessonClientId, "Choose a lesson preset first.");
      return;
    }
    const document = getLessonDocumentPreset(presetId);
    if (!document) {
      setLessonFailure(lessonClientId, "Selected lesson preset is not available.");
      return;
    }
    onReplaceLessonDocument(lessonClientId, document);
    const label = lessonDocumentPresets.find((preset) => preset.id === presetId)?.label ?? "preset";
    setLessonNotice(lessonClientId, `Applied "${label}" to this lesson.`);
  };

  const importLessonFromFile = async (lessonClientId: string, file: File | null) => {
    if (!file) return;
    try {
      const imported = await parseLessonDocumentFile(file);
      onReplaceLessonDocument(lessonClientId, imported);
      setLessonNotice(lessonClientId, `Imported lesson document from ${file.name}.`);
    } catch (error) {
      setLessonFailure(
        lessonClientId,
        error instanceof Error ? error.message : "Failed to import the lesson file. Use .json or .ipynb.",
      );
    }
  };

  const importLessonSourceText = async (lessonClientId: string, file: File | null) => {
    if (!file) return;
    try {
      const text = await file.text();
      patchGeneratorDraft(lessonClientId, { sourceText: text });
      setLessonNotice(lessonClientId, `Loaded source text from ${file.name}.`);
    } catch (error) {
      setLessonFailure(
        lessonClientId,
        error instanceof Error ? error.message : "Failed to read the source text file.",
      );
    }
  };

  const generateLesson = async (lesson: CourseBuilderLessonDraft) => {
    const generatorDraft = generatorDraftForLesson(lesson);
    if (!generatorDraft.sourceText.trim() && !generatorDraft.videoFile) {
      setLessonFailure(lesson.clientId, "Paste source text, upload a text file, or upload a video file before generating the lesson.");
      return;
    }

    const currentBlocksCount = lesson.sections.reduce((count, section) => count + section.items.length, 0);
    if (
      currentBlocksCount > 0
      && !window.confirm(`Generate lesson will replace the current blocks in "${lesson.title || "this lesson"}". Continue?`)
    ) {
      return;
    }

    setGeneratorBusyByLesson((current) => ({ ...current, [lesson.clientId]: true }));
    try {
      const message = await onGenerateLesson(lesson.clientId, generatorDraft);
      setLessonNotice(lesson.clientId, message);
      setSuccessDialog({
        title: "Lesson generated",
        message: "The AI lesson flow was created successfully. Review the generated blocks and save the course when ready.",
      });
    } catch (error) {
      setLessonFailure(
        lesson.clientId,
        lessonGenerationErrorMessage(error),
      );
    } finally {
      setGeneratorBusyByLesson((current) => ({ ...current, [lesson.clientId]: false }));
    }
  };

  return (
    <>
    <div className={styles.stackLarge}>
      <CollapsibleSection
        title="Modules and lesson studio"
        description="Build the course as a single learning document flow: course, modules, lessons, then the lesson document that learners see in Student and Instructor workspaces."
        summary={
          <div className={styles.templateMeta}>
            <span className={styles.miniPill}>{draft.modules.length} modules</span>
            <span className={styles.miniPill}>{draft.lessons.length} lessons</span>
          </div>
        }
        actions={
          <>
            <button type="button" className={styles.secondaryButton} onClick={onAddModule}>
              Add module
            </button>
            <button type="button" className={styles.primaryButton} onClick={onAddLesson}>
              Add lesson
            </button>
          </>
        }
      >

        <div className={styles.lessonStudioHint}>
          <strong>Lesson document pattern</strong>
          <p>
            Each lesson is rendered as one scroll-based teaching document. Keep blocks in learner order, attach a managed notebook only where real Jupyter practice is needed, and use the lesson library/import tools to avoid rebuilding repeated structures.
          </p>
        </div>

        <div className={styles.sectionList}>
          {draft.modules.map((module, index) => (
            <CollapsibleSection
              key={module.clientId}
              variant="nested"
              title={module.title || `Module ${index + 1}`}
              description={`Module #${index + 1}`}
              summary={<span className={styles.statusNote}>{module.moduleType.replace(/_/g, " ")}</span>}
              actions={
                <button type="button" className={styles.ghostButton} onClick={() => onRemoveModule(module.clientId)}>
                  Delete module
                </button>
              }
            >

              <div className={styles.formGrid}>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Module title</span>
                  <input
                    className={styles.input}
                    value={module.title}
                    onChange={(event) => onPatchModule(module.clientId, { title: event.currentTarget.value })}
                  />
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Module type</span>
                  <select
                    className={styles.select}
                    value={module.moduleType}
                    onChange={(event) =>
                      onPatchModule(module.clientId, {
                        moduleType: event.currentTarget.value as "module" | "final_assessment",
                      })
                    }
                  >
                    <option value="module">Module</option>
                    <option value="final_assessment">Final assessment</option>
                  </select>
                </label>
              </div>

              <div className={styles.formGrid}>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Start date</span>
                  <input
                    className={styles.input}
                    type="datetime-local"
                    value={toInputValue(module.startsAt)}
                    onChange={(event) => onPatchModule(module.clientId, { startsAt: toIsoValue(event.currentTarget.value) })}
                  />
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>End date</span>
                  <input
                    className={styles.input}
                    type="datetime-local"
                    value={toInputValue(module.endsAt)}
                    onChange={(event) => onPatchModule(module.clientId, { endsAt: toIsoValue(event.currentTarget.value) })}
                  />
                </label>
              </div>

              <div className={styles.formGrid}>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Week number</span>
                  <input
                    className={styles.input}
                    type="number"
                    min={1}
                    value={module.weekNumber ?? ""}
                    onChange={(event) =>
                      onPatchModule(module.clientId, {
                        weekNumber: event.currentTarget.value ? Number(event.currentTarget.value) : null,
                      })
                    }
                  />
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Sort order</span>
                  <input
                    className={styles.input}
                    type="number"
                    min={1}
                    value={module.sortOrder}
                    onChange={(event) => onPatchModule(module.clientId, { sortOrder: Number(event.currentTarget.value) || 1 })}
                  />
                </label>
              </div>

              <label className={styles.field}>
                <span className={styles.fieldLabel}>Module description</span>
                <textarea
                  className={styles.textarea}
                  value={module.description}
                  onChange={(event) => onPatchModule(module.clientId, { description: event.currentTarget.value })}
                />
              </label>
            </CollapsibleSection>
          ))}
        </div>
      </CollapsibleSection>

      <div className={styles.sectionList}>
        {draft.lessons.map((lesson, lessonIndex) => {
          const generatorDraft = generatorDraftForLesson(lesson);

          return (
            <CollapsibleSection
              key={lesson.clientId}
              variant="lesson"
              title={lesson.title || `Lesson ${lessonIndex + 1}`}
              description={`Lesson #${lessonIndex + 1}`}
              summary={
                <div className={styles.templateMeta}>
                  <span className={styles.miniPill}>{lesson.sections.length} sections</span>
                  <span className={styles.miniPill}>{lesson.sections.reduce((count, section) => count + section.items.length, 0)} blocks</span>
                </div>
              }
              actions={
                <button type="button" className={styles.ghostButton} onClick={() => onRemoveLesson(lesson.clientId)}>
                  Delete lesson
                </button>
              }
            >

            <div className={styles.formGrid}>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>Module</span>
                <select
                  className={styles.select}
                  value={lesson.moduleClientId}
                  onChange={(event) => onPatchLesson(lesson.clientId, { moduleClientId: event.currentTarget.value })}
                >
                  {draft.modules.map((module) => (
                    <option key={module.clientId} value={module.clientId}>
                      {module.title}
                    </option>
                  ))}
                </select>
              </label>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>Lesson title</span>
                <input
                  className={styles.input}
                  value={lesson.title}
                  onChange={(event) => onPatchLesson(lesson.clientId, { title: event.currentTarget.value })}
                />
              </label>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>Start date</span>
                <input
                  className={styles.input}
                  type="datetime-local"
                  value={toInputValue(lesson.startsAt)}
                  onChange={(event) => onPatchLesson(lesson.clientId, { startsAt: toIsoValue(event.currentTarget.value) })}
                />
              </label>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>End date</span>
                <input
                  className={styles.input}
                  type="datetime-local"
                  value={toInputValue(lesson.endsAt)}
                  onChange={(event) => onPatchLesson(lesson.clientId, { endsAt: toIsoValue(event.currentTarget.value) })}
                />
              </label>
            </div>

            <div className={styles.formGrid}>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>Sort order</span>
                <input
                  className={styles.input}
                  type="number"
                  min={1}
                  value={lesson.sortOrder}
                  onChange={(event) => onPatchLesson(lesson.clientId, { sortOrder: Number(event.currentTarget.value) || 1 })}
                />
              </label>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>Lesson visibility</span>
                <label className={styles.statusNote}>
                  <input
                    type="checkbox"
                    checked={lesson.isActive}
                    onChange={(event) => onPatchLesson(lesson.clientId, { isActive: event.currentTarget.checked })}
                  />
                  Active
                </label>
              </label>
            </div>

            <label className={styles.field}>
              <span className={styles.fieldLabel}>Lesson description</span>
              <textarea
                className={styles.textarea}
                value={lesson.description}
                onChange={(event) => onPatchLesson(lesson.clientId, { description: event.currentTarget.value })}
              />
            </label>

            <section className={styles.lessonGeneratorCard}>
              <div className={styles.cardHeader}>
                <div>
                  <h4 className={styles.cardTitle}>Generate interactive lesson flow</h4>
                  <p className={styles.cardText}>
                    Paste source content or upload a video, then generate a ready-made `Theory → Concept → Video → Quiz → Practice → Summary` lesson document.
                  </p>
                </div>
                <button
                  type="button"
                  className={styles.primaryButton}
                  onClick={() => void generateLesson(lesson)}
                  disabled={generatorBusyByLesson[lesson.clientId]}
                >
                  {generatorBusyByLesson[lesson.clientId] ? "Generating..." : "Generate lesson"}
                </button>
              </div>

              <div className={styles.formGrid}>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Video URL</span>
                  <input
                    className={styles.input}
                    value={generatorDraft.videoUrl}
                    onChange={(event) => patchGeneratorDraft(lesson.clientId, { videoUrl: event.currentTarget.value })}
                    placeholder="https://www.youtube.com/watch?v=..."
                  />
                </label>
              </div>

              <label className={styles.field}>
                <span className={styles.fieldLabel}>Source content</span>
                <textarea
                  className={`${styles.textarea} ${styles.textareaTall}`}
                  value={generatorDraft.sourceText}
                  onChange={(event) => patchGeneratorDraft(lesson.clientId, { sourceText: event.currentTarget.value })}
                  placeholder="Paste lesson description, theory notes, delivery guidance, or raw content here."
                />
              </label>

              <div className={styles.lessonGeneratorToolbar}>
                <label className={styles.inlineFileControl}>
                  <span>Upload source text (.txt / .md)</span>
                  <input
                    type="file"
                    accept=".txt,.md,.markdown,text/plain,text/markdown"
                    onChange={(event) => {
                      const file = event.currentTarget.files?.[0] ?? null;
                      void importLessonSourceText(lesson.clientId, file);
                      event.currentTarget.value = "";
                    }}
                  />
                </label>

                <label className={styles.inlineFileControl}>
                  <span>{generatorDraft.videoFile ? `Video file: ${generatorDraft.videoFile.name}` : "Upload video file"}</span>
                  <input
                    type="file"
                    accept="video/*"
                    onChange={(event) => {
                      const file = event.currentTarget.files?.[0] ?? null;
                      patchGeneratorDraft(lesson.clientId, { videoFile: file });
                      if (file) {
                        setLessonNotice(lesson.clientId, `Selected video file ${file.name}. It will be uploaded when you generate the lesson.`);
                      }
                      event.currentTarget.value = "";
                    }}
                  />
                </label>
              </div>

              <label className={styles.field}>
                <span className={styles.fieldLabel}>Video description</span>
                <textarea
                  className={styles.textarea}
                  value={generatorDraft.videoDescription}
                  onChange={(event) => patchGeneratorDraft(lesson.clientId, { videoDescription: event.currentTarget.value })}
                  placeholder="Describe what the learner should see or understand in the video step."
                />
              </label>

              <p className={styles.helperText}>
                Lesson generation is fixed to English across the admin workspace.
              </p>

              <p className={styles.helperText}>
                Uploaded video files are transcribed, added to the internal lesson library, and attached to the generated `Video` step. If no video asset is provided, the generator still creates the step as a placeholder.
              </p>
            </section>

            <div className={styles.lessonImportToolbar}>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>Internal lesson library</span>
                <select
                  className={styles.select}
                  value={presetByLesson[lesson.clientId] ?? ""}
                  onChange={(event) => setPresetByLesson((current) => ({ ...current, [lesson.clientId]: event.currentTarget.value }))}
                >
                  <option value="">Choose reusable lesson pattern</option>
                  {lessonDocumentPresets.map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.label}
                    </option>
                  ))}
                </select>
                <span className={styles.helperText}>
                  Reuse a proven lesson-document skeleton and then replace the content with course-specific material.
                </span>
              </label>

              <div className={styles.lessonImportActions}>
                <button type="button" className={styles.secondaryButton} onClick={() => applyPresetToLesson(lesson.clientId)}>
                  Apply preset
                </button>
                <label className={styles.inlineFileControl}>
                  <span>Upload lesson (.json / .ipynb)</span>
                  <input
                    type="file"
                    accept=".json,.ipynb,application/json"
                    onChange={(event) => {
                      const file = event.currentTarget.files?.[0] ?? null;
                      void importLessonFromFile(lesson.clientId, file);
                      event.currentTarget.value = "";
                    }}
                  />
                </label>
              </div>
            </div>

            {lessonErrors[lesson.clientId] ? <p className={styles.helperError}>{lessonErrors[lesson.clientId]}</p> : null}
            {lessonMessages[lesson.clientId] ? <p className={styles.helperSuccess}>{lessonMessages[lesson.clientId]}</p> : null}

            <div className={styles.sectionList}>
              {lesson.sections.map((section) => (
                <CollapsibleSection
                  key={section.clientId}
                  variant="nested"
                  title={sectionTitleLabel[section.sectionType]}
                  description={`${section.sectionType} · ${section.items.length} block(s) in the learner document`}
                  summary={<span className={styles.statusNote}>{section.isActive ? "Active" : "Hidden"}</span>}
                  actions={
                    <>
                      <button type="button" className={styles.ghostButton} onClick={() => onOpenLibraryForm(section.sectionType)}>
                        Library asset
                      </button>
                      <button type="button" className={styles.secondaryButton} onClick={() => onAddSectionItem(lesson.clientId, section.sectionType, lessonBlockSeed("reading"))}>
                        Add reading
                      </button>
                      <button type="button" className={styles.secondaryButton} onClick={() => onAddSectionItem(lesson.clientId, section.sectionType, lessonBlockSeed("document"))}>
                        Add document
                      </button>
                      <button type="button" className={styles.secondaryButton} onClick={() => onAddSectionItem(lesson.clientId, section.sectionType, lessonBlockSeed("video"))}>
                        Add video
                      </button>
                      <button type="button" className={styles.secondaryButton} onClick={() => onAddSectionItem(lesson.clientId, section.sectionType, lessonBlockSeed("quiz"))}>
                        Add quiz
                      </button>
                      <button type="button" className={styles.primaryButton} onClick={() => onAddSectionItem(lesson.clientId, section.sectionType, lessonBlockSeed("notebook"))}>
                        Add notebook
                      </button>
                    </>
                  }
                >

                  <div className={styles.formGrid}>
                    <label className={styles.field}>
                      <span className={styles.fieldLabel}>Section title</span>
                      <input
                        className={styles.input}
                        value={section.title}
                        onChange={(event) => onPatchSection(lesson.clientId, section.sectionType, { title: event.currentTarget.value })}
                      />
                    </label>
                    <label className={styles.field}>
                      <span className={styles.fieldLabel}>Sort order</span>
                      <input
                        className={styles.input}
                        type="number"
                        min={1}
                        value={section.sortOrder}
                        onChange={(event) =>
                          onPatchSection(lesson.clientId, section.sectionType, { sortOrder: Number(event.currentTarget.value) || 1 })
                        }
                      />
                    </label>
                  </div>

                  <label className={styles.field}>
                    <span className={styles.fieldLabel}>Section description</span>
                    <textarea
                      className={styles.textarea}
                      value={section.description}
                      onChange={(event) => onPatchSection(lesson.clientId, section.sectionType, { description: event.currentTarget.value })}
                    />
                  </label>

                  <div className={styles.row}>
                    <label className={styles.statusNote}>
                      <input
                        type="checkbox"
                        checked={section.isActive}
                        onChange={(event) => onPatchSection(lesson.clientId, section.sectionType, { isActive: event.currentTarget.checked })}
                      />
                      Active
                    </label>
                  </div>

                  <div className={styles.sectionList}>
                    {section.items.length === 0 ? (
                      <p className={styles.emptyState}>
                        No blocks yet. Add reading, document, video, quiz, or notebook content in the order learners should see it.
                      </p>
                    ) : null}
                    {section.items.map((item) => {
                      const libraryItem = item.sourceLibraryItemId
                        ? libraryItems.find((candidate) => candidate.id === item.sourceLibraryItemId) ?? null
                        : null;

                      return (
                        <CollapsibleSection
                          key={item.clientId}
                          variant="item"
                          title={item.title || "Untitled block"}
                          description={item.isActive ? "Active lesson block" : "Hidden lesson block"}
                          summary={
                            <div className={styles.templateMeta}>
                              <span className={styles.miniPill}>{assetTypeLabel[item.assetType]}</span>
                              <span className={styles.miniPill}>{(item.activityType ?? "text").toUpperCase()}</span>
                              {libraryItem ? <span className={styles.miniPill}>Library: {libraryItem.title}</span> : null}
                            </div>
                          }
                          actions={
                            <button
                              type="button"
                              className={styles.ghostButton}
                              onClick={() => onRemoveSectionItem(lesson.clientId, section.sectionType, item.clientId)}
                            >
                              Remove
                            </button>
                          }
                        >

                          <div className={styles.formGrid}>
                            <label className={styles.field}>
                              <span className={styles.fieldLabel}>Title</span>
                              <input
                                className={styles.input}
                                value={item.title}
                                onChange={(event) =>
                                  onPatchSectionItem(lesson.clientId, section.sectionType, item.clientId, { title: event.currentTarget.value })
                                }
                              />
                            </label>
                            <label className={styles.field}>
                              <span className={styles.fieldLabel}>Source library item</span>
                              <select
                                className={styles.select}
                                value={item.sourceLibraryItemId ?? ""}
                                onChange={(event) => {
                                  const nextValue = event.currentTarget.value ? Number(event.currentTarget.value) : null;
                                  if (nextValue) {
                                    onApplyLibraryItemToSectionItem(lesson.clientId, section.sectionType, item.clientId, nextValue);
                                  } else {
                                    onPatchSectionItem(lesson.clientId, section.sectionType, item.clientId, { sourceLibraryItemId: null });
                                  }
                                }}
                              >
                                <option value="">Custom lesson block</option>
                                {libraryItems
                                  .map((candidate) => (
                                    <option key={candidate.id} value={candidate.id}>
                                      {candidate.title} ({candidate.assetType})
                                    </option>
                                  ))}
                              </select>
                            </label>
                          </div>

                          <div className={styles.formGrid}>
                            <label className={styles.field}>
                              <span className={styles.fieldLabel}>Asset type</span>
                              <select
                                className={styles.select}
                                value={item.assetType}
                                onChange={(event) =>
                                  onPatchSectionItem(lesson.clientId, section.sectionType, item.clientId, {
                                    assetType: event.currentTarget.value as CourseBuilderAssetType,
                                  })
                                }
                              >
                                <option value="text">Text</option>
                                <option value="document">Document</option>
                                <option value="link">Link</option>
                                <option value="notebook">Notebook</option>
                              </select>
                            </label>
                            <label className={styles.field}>
                              <span className={styles.fieldLabel}>Activity type</span>
                              <select
                                className={styles.select}
                                value={item.activityType ?? "text"}
                                onChange={(event) =>
                                  onPatchSectionItem(lesson.clientId, section.sectionType, item.clientId, {
                                    activityType: event.currentTarget.value as "video" | "text" | "quiz" | "assignment",
                                  })
                                }
                              >
                                <option value="text">Text / Reading</option>
                                <option value="video">Video</option>
                                <option value="quiz">Quiz</option>
                                <option value="assignment">Assignment</option>
                              </select>
                            </label>
                          </div>

                          <div className={styles.formGrid}>
                            <label className={styles.field}>
                              <span className={styles.fieldLabel}>Sort order</span>
                              <input
                                className={styles.input}
                                type="number"
                                min={1}
                                value={item.sortOrder}
                                onChange={(event) =>
                                  onPatchSectionItem(lesson.clientId, section.sectionType, item.clientId, {
                                    sortOrder: Number(event.currentTarget.value) || 1,
                                  })
                                }
                              />
                            </label>
                            <label className={styles.field}>
                              <span className={styles.fieldLabel}>Notebook reference</span>
                              <select
                                className={styles.select}
                                value={item.linkedTrainingContentId ?? ""}
                                onChange={(event) =>
                                  onPatchSectionItem(lesson.clientId, section.sectionType, item.clientId, {
                                    linkedTrainingContentId: event.currentTarget.value ? Number(event.currentTarget.value) : null,
                                  })
                                }
                              >
                                <option value="">No notebook linked</option>
                                {notebookOptions.map((notebook) => (
                                  <option key={notebook.id} value={notebook.id}>
                                    {notebook.name}
                                  </option>
                                ))}
                              </select>
                            </label>
                          </div>

                          <label className={styles.field}>
                            <span className={styles.fieldLabel}>Description</span>
                            <textarea
                              className={styles.textarea}
                              value={item.description}
                              onChange={(event) =>
                                onPatchSectionItem(lesson.clientId, section.sectionType, item.clientId, { description: event.currentTarget.value })
                              }
                            />
                          </label>

                          <DemoRolePolicyFieldset
                            audiences={audiences}
                            selectedIds={item.audienceIds ?? []}
                            label="Item access roles"
                            hint="Leave empty to inherit from the course or source library asset. Use this when a single lesson block should be visible only to selected demo roles."
                            onChange={(nextIds) =>
                              onPatchSectionItem(lesson.clientId, section.sectionType, item.clientId, { audienceIds: nextIds })
                            }
                          />

                          {item.assetType === "text" ? (
                            <>
                              <label className={styles.field}>
                                <span className={styles.fieldLabel}>Markdown content</span>
                                <textarea
                                  className={styles.textarea}
                                  value={item.bodyMarkdown}
                                  onChange={(event) =>
                                    onPatchSectionItem(lesson.clientId, section.sectionType, item.clientId, {
                                      bodyMarkdown: event.currentTarget.value,
                                    })
                                  }
                                />
                              </label>
                              {item.bodyMarkdown.trim() ? (
                                <div className={styles.markdownPreview}>
                                  <span className={styles.fieldLabel}>Live lesson preview</span>
                                  <div
                                    className={styles.markdownPreviewBody}
                                    dangerouslySetInnerHTML={{ __html: markdownPreviewHtml(item.bodyMarkdown) }}
                                  />
                                </div>
                              ) : null}
                            </>
                          ) : null}

                          {item.assetType === "link" || item.assetType === "document" ? (
                            <label className={styles.field}>
                              <span className={styles.fieldLabel}>{item.assetType === "link" ? "Link URL" : "Document URL"}</span>
                              <input
                                className={styles.input}
                                value={item.externalUrl}
                                onChange={(event) =>
                                  onPatchSectionItem(lesson.clientId, section.sectionType, item.clientId, { externalUrl: event.currentTarget.value })
                                }
                              />
                            </label>
                          ) : null}

                          {item.assetType === "notebook" ? (
                            <p className={styles.helperText}>
                              Notebook blocks stay inside the lesson document but open the managed Jupyter runtime for actual coding. Link a notebook above before publishing.
                            </p>
                          ) : null}

                          <div className={styles.row}>
                            <label className={styles.statusNote}>
                              <input
                                type="checkbox"
                                checked={item.isActive}
                                onChange={(event) =>
                                  onPatchSectionItem(lesson.clientId, section.sectionType, item.clientId, { isActive: event.currentTarget.checked })
                                }
                              />
                              Active
                            </label>
                          </div>
                        </CollapsibleSection>
                      );
                    })}
                  </div>
                </CollapsibleSection>
              ))}
            </div>
            </CollapsibleSection>
          );
        })}
      </div>

      <div className={styles.row}>
        <button type="button" className={styles.secondaryButton} onClick={onAddModule}>
          + Add module
        </button>
        <button type="button" className={styles.primaryButton} onClick={onAddLesson}>
          + Add lesson
        </button>
      </div>
    </div>
    {successDialog ? (
      <div className={styles.successDialogOverlay} role="dialog" aria-modal="true" aria-labelledby="lesson-generation-success-title">
        <div className={styles.successDialogCard}>
          <span className={styles.successDialogIcon} aria-hidden="true">✓</span>
          <div className={styles.stack}>
            <h3 id="lesson-generation-success-title" className={styles.cardTitle}>{successDialog.title}</h3>
            <p className={styles.cardText}>{successDialog.message}</p>
          </div>
          <button type="button" className={styles.primaryButton} onClick={() => setSuccessDialog(null)}>
            OK
          </button>
        </div>
      </div>
    ) : null}
    </>
  );
};

export default CourseBuilderLessonsPanel;
