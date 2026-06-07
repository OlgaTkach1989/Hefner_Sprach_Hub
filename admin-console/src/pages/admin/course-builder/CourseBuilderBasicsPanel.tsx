import type { OnlineAdminCuratorSummary } from "@/bll/online/online.type";
import type { OnlineAdminWorkspaceSummary } from "@/bll/site/site.type";
import type { TrainingAdminAudience } from "@/bll/training/training.type";
import DemoRolePolicyFieldset from "@/components/access/DemoRolePolicyFieldset";
import type { CourseBuilderCourseDraft } from "./courseBuilderState";
import CollapsibleSection from "./CollapsibleSection";
import styles from "./AdminCourseBuilderModal.module.css";

type Props = {
  draft: CourseBuilderCourseDraft;
  audiences: TrainingAdminAudience[];
  instructors: OnlineAdminCuratorSummary[];
  workspaces: OnlineAdminWorkspaceSummary[];
  onPatchDraft: (patch: Partial<CourseBuilderCourseDraft>) => void;
};

const LIFECYCLE_OPTIONS: Array<{ value: CourseBuilderCourseDraft["lifecycleStatus"]; label: string }> = [
  { value: "draft", label: "Draft" },
  { value: "in_review", label: "In review" },
  { value: "approved", label: "Approved" },
  { value: "published", label: "Published" },
  { value: "archived", label: "Archived" },
];

const PROVIDER_OPTIONS: Array<{ value: CourseBuilderCourseDraft["providerType"]; label: string }> = [
  { value: "internal", label: "Internal" },
  { value: "linkedin_learning", label: "LinkedIn Learning" },
  { value: "coursera", label: "Coursera" },
  { value: "udemy_business", label: "Udemy Business" },
  { value: "external_custom", label: "External custom" },
];

const ORIGIN_OPTIONS: Array<{ value: CourseBuilderCourseDraft["courseOrigin"]; label: string }> = [
  { value: "internal_authored", label: "Internal authored" },
  { value: "external_synced", label: "External synced" },
  { value: "external_manual", label: "External manual" },
];

const COURSE_TYPE_OPTIONS: Array<{ value: CourseBuilderCourseDraft["courseType"]; label: string }> = [
  { value: "interactive", label: "Interactive" },
  { value: "recording", label: "Recording" },
  { value: "video", label: "Video" },
  { value: "text", label: "Text" },
  { value: "audio", label: "Audio" },
  { value: "live", label: "Live" },
  { value: "blended", label: "Blended" },
  { value: "external", label: "External" },
];

const DELIVERY_OPTIONS: Array<{ value: CourseBuilderCourseDraft["deliveryModel"]; label: string }> = [
  { value: "cohort", label: "Cohort" },
  { value: "self_paced", label: "Self-paced" },
  { value: "instructor_led", label: "Instructor-led" },
  { value: "hybrid", label: "Hybrid" },
];

const DIFFICULTY_OPTIONS: Array<{ value: CourseBuilderCourseDraft["difficultyLevel"]; label: string }> = [
  { value: "foundation", label: "Foundation" },
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
  { value: "expert", label: "Expert" },
];

const CONFIDENTIALITY_OPTIONS: Array<{ value: CourseBuilderCourseDraft["confidentialityLevel"]; label: string }> = [
  { value: "public", label: "Public" },
  { value: "internal", label: "Internal" },
  { value: "restricted", label: "Restricted" },
  { value: "confidential", label: "Confidential" },
  { value: "highly_confidential", label: "Highly confidential" },
];

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

const toCommaSeparated = (value: string[]) => value.join(", ");

const parseCommaSeparated = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const CourseBuilderBasicsPanel = ({ draft, audiences, instructors, workspaces, onPatchDraft }: Props) => {
  const toggleId = (key: "instructorIds" | "workspaceIds", id: number) => {
    const currentIds = draft[key] ?? [];
    const nextIds = currentIds.includes(id) ? currentIds.filter((entry) => entry !== id) : [...currentIds, id];
    onPatchDraft({ [key]: nextIds } as Partial<CourseBuilderCourseDraft>);
  };

  const patchEnglishOnlyField = (
    deKey:
      | "titleDe"
      | "shortDescriptionDe"
      | "descriptionDe"
      | "seoTitleDe"
      | "seoDescriptionDe",
    enKey:
      | "titleEn"
      | "shortDescriptionEn"
      | "descriptionEn"
      | "seoTitleEn"
      | "seoDescriptionEn",
    value: string
  ) => {
    onPatchDraft({
      [deKey]: value,
      [enKey]: value,
    } as Partial<CourseBuilderCourseDraft>);
  };

  const courseTitle = draft.titleEn || draft.titleDe;
  const shortDescription = draft.shortDescriptionEn || draft.shortDescriptionDe;
  const description = draft.descriptionEn || draft.descriptionDe;
  const seoTitle = draft.seoTitleEn || draft.seoTitleDe;
  const seoDescription = draft.seoDescriptionEn || draft.seoDescriptionDe;

  return (
    <div className={styles.stack}>
      <CollapsibleSection
        title="Course basics"
        description="Define the public identity, onboarding copy, and delivery metadata."
        summary={<span className={styles.statusNote}>{draft.lessons.length} lessons</span>}
      >

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Starts at</span>
            <input
              className={styles.input}
              type="datetime-local"
              value={toInputValue(draft.startsAt)}
              onChange={(event) => onPatchDraft({ startsAt: toIsoValue(event.currentTarget.value) })}
            />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Ends at</span>
            <input
              className={styles.input}
              type="datetime-local"
              value={toInputValue(draft.endsAt)}
              onChange={(event) => onPatchDraft({ endsAt: toIsoValue(event.currentTarget.value) })}
            />
          </label>
        </div>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Slug</span>
            <input
              className={styles.input}
              value={draft.slug}
              onChange={(event) => onPatchDraft({ slug: event.currentTarget.value })}
              placeholder="quant-core-strats"
            />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Hero image URL</span>
            <input
              className={styles.input}
              value={draft.heroImageUrl}
              onChange={(event) => onPatchDraft({ heroImageUrl: event.currentTarget.value })}
              placeholder="https://..."
            />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Title</span>
            <input
              className={styles.input}
              value={courseTitle}
              onChange={(event) => patchEnglishOnlyField("titleDe", "titleEn", event.currentTarget.value)}
              placeholder="Course name in English"
            />
          </label>
        </div>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Short description</span>
            <textarea
              className={styles.textarea}
              value={shortDescription}
              onChange={(event) =>
                patchEnglishOnlyField("shortDescriptionDe", "shortDescriptionEn", event.currentTarget.value)
              }
            />
          </label>
        </div>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Description</span>
            <textarea
              className={styles.textarea}
              value={description}
              onChange={(event) => patchEnglishOnlyField("descriptionDe", "descriptionEn", event.currentTarget.value)}
            />
          </label>
        </div>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Geo city</span>
            <input
              className={styles.input}
              value={draft.geoCity}
              onChange={(event) => onPatchDraft({ geoCity: event.currentTarget.value })}
            />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Geo country</span>
            <input
              className={styles.input}
              value={draft.geoCountry}
              onChange={(event) => onPatchDraft({ geoCountry: event.currentTarget.value })}
            />
          </label>
        </div>
      </CollapsibleSection>

      <CollapsibleSection
        title="Catalog metadata"
        description="Normalize the course for search, external providers, confidentiality, and program assignment logic."
        summary={<span className={styles.statusNote}>{draft.providerType.replace(/_/g, " ")}</span>}
      >

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Provider</span>
            <select className={styles.select} value={draft.providerType} onChange={(event) => onPatchDraft({ providerType: event.currentTarget.value as CourseBuilderCourseDraft["providerType"] })}>
              {PROVIDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Origin</span>
            <select className={styles.select} value={draft.courseOrigin} onChange={(event) => onPatchDraft({ courseOrigin: event.currentTarget.value as CourseBuilderCourseDraft["courseOrigin"] })}>
              {ORIGIN_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Course type</span>
            <select className={styles.select} value={draft.courseType} onChange={(event) => onPatchDraft({ courseType: event.currentTarget.value as CourseBuilderCourseDraft["courseType"] })}>
              {COURSE_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Delivery model</span>
            <select className={styles.select} value={draft.deliveryModel} onChange={(event) => onPatchDraft({ deliveryModel: event.currentTarget.value as CourseBuilderCourseDraft["deliveryModel"] })}>
              {DELIVERY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Difficulty</span>
            <select className={styles.select} value={draft.difficultyLevel} onChange={(event) => onPatchDraft({ difficultyLevel: event.currentTarget.value as CourseBuilderCourseDraft["difficultyLevel"] })}>
              {DIFFICULTY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Confidentiality</span>
            <select className={styles.select} value={draft.confidentialityLevel} onChange={(event) => onPatchDraft({ confidentialityLevel: event.currentTarget.value as CourseBuilderCourseDraft["confidentialityLevel"] })}>
              {CONFIDENTIALITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Knowledge domain</span>
            <input className={styles.input} value={draft.knowledgeDomain} onChange={(event) => onPatchDraft({ knowledgeDomain: event.currentTarget.value })} placeholder="Python, Finance, Compliance, Risk..." />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Target audience</span>
            <input className={styles.input} value={draft.targetAudience} onChange={(event) => onPatchDraft({ targetAudience: event.currentTarget.value })} placeholder="Analysts, new hires, managers..." />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Estimated duration (min)</span>
            <input className={styles.input} type="number" min={0} value={draft.estimatedDurationMinutes} onChange={(event) => onPatchDraft({ estimatedDurationMinutes: Number(event.currentTarget.value || 0) })} />
          </label>
        </div>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Provider course ID</span>
            <input className={styles.input} value={draft.providerCourseId} onChange={(event) => onPatchDraft({ providerCourseId: event.currentTarget.value })} placeholder="EXT-12345" />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>External URL</span>
            <input className={styles.input} value={draft.externalUrl} onChange={(event) => onPatchDraft({ externalUrl: event.currentTarget.value })} placeholder="https://..." />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Average rating</span>
            <input className={styles.input} value={draft.averageRating} onChange={(event) => onPatchDraft({ averageRating: event.currentTarget.value })} placeholder="4.50" />
          </label>
        </div>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Ratings count</span>
            <input className={styles.input} type="number" min={0} value={draft.ratingsCount} onChange={(event) => onPatchDraft({ ratingsCount: Number(event.currentTarget.value || 0) })} />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Tags</span>
            <input className={styles.input} value={toCommaSeparated(draft.tags ?? [])} onChange={(event) => onPatchDraft({ tags: parseCommaSeparated(event.currentTarget.value) })} placeholder="python, onboarding, finance" />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Skills</span>
            <input className={styles.input} value={toCommaSeparated(draft.skills ?? [])} onChange={(event) => onPatchDraft({ skills: parseCommaSeparated(event.currentTarget.value) })} placeholder="variables, pandas, reporting" />
          </label>
        </div>

        <div className={styles.row}>
          <label className={styles.statusNote}>
            <input type="checkbox" checked={draft.isMandatory} onChange={(event) => onPatchDraft({ isMandatory: event.currentTarget.checked })} />
            Mandatory
          </label>
          <label className={styles.statusNote}>
            <input type="checkbox" checked={draft.isRecommended} onChange={(event) => onPatchDraft({ isRecommended: event.currentTarget.checked })} />
            Recommended
          </label>
        </div>
      </CollapsibleSection>

      <CollapsibleSection
        title="Publishing and SEO"
        description="Set governance status, visibility, pricing, and catalog metadata in one place."
        summary={<span className={styles.statusNote}>{draft.lifecycleStatus.replace(/_/g, " ")}</span>}
      >

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Governance status</span>
            <select
              className={styles.select}
              value={draft.lifecycleStatus}
              onChange={(event) =>
                onPatchDraft({
                  lifecycleStatus: event.currentTarget.value as CourseBuilderCourseDraft["lifecycleStatus"],
                  isPublished: event.currentTarget.value === "published",
                })
              }
            >
              {LIFECYCLE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Price amount</span>
            <input
              className={styles.input}
              value={draft.priceAmount}
              onChange={(event) => onPatchDraft({ priceAmount: event.currentTarget.value })}
              placeholder="0.00"
            />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Currency</span>
            <input
              className={styles.input}
              value={draft.currency}
              onChange={(event) => onPatchDraft({ currency: event.currentTarget.value })}
              placeholder="EUR"
            />
          </label>
        </div>

        <p className={styles.helperText}>
          Only <strong>Published</strong> courses are visible in public spaces and learner-facing catalog surfaces.
          <strong> In review</strong> and <strong>Approved</strong> keep the course private while governance and release checks are completed.
        </p>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Required course completion %</span>
            <input
              className={styles.input}
              type="number"
              min={0}
              max={100}
              value={draft.requiredCompletionPercent}
              onChange={(event) => onPatchDraft({ requiredCompletionPercent: Number(event.currentTarget.value || 0) })}
            />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Required attendance %</span>
            <input
              className={styles.input}
              type="number"
              min={0}
              max={100}
              value={draft.requiredAttendancePercent}
              onChange={(event) => onPatchDraft({ requiredAttendancePercent: Number(event.currentTarget.value || 0) })}
            />
          </label>
        </div>

        <div className={styles.row}>
          <label className={styles.statusNote}>
            <input
              type="checkbox"
              checked={draft.trialAvailable}
              onChange={(event) => onPatchDraft({ trialAvailable: event.currentTarget.checked })}
            />
            Trial available
          </label>
          <label className={styles.statusNote}>
            <input
              type="checkbox"
              checked={draft.isSubscription}
              onChange={(event) => onPatchDraft({ isSubscription: event.currentTarget.checked })}
            />
            Subscription
          </label>
          <label className={styles.statusNote}>
            <input
              type="checkbox"
              checked={draft.requiresAttestation}
              onChange={(event) => onPatchDraft({ requiresAttestation: event.currentTarget.checked })}
            />
            Attestation required
          </label>
          <span className={styles.statusNote}>Public visibility: {draft.lifecycleStatus === "published" ? "Live" : "Private"}</span>
        </div>

        <DemoRolePolicyFieldset
          audiences={audiences}
          selectedIds={draft.audienceIds ?? []}
          label="Course access roles"
          hint="Use this for course-wide visibility. Learners must have at least one matching demo role to see the course in public spaces and student workspace."
          onChange={(nextIds) => onPatchDraft({ audienceIds: nextIds })}
        />

        <div className={styles.inlineAccessGrid}>
          <section className={styles.inlineAccessCard}>
            <header className={styles.inlineAccessHeader}>
              <div>
                <h4 className={styles.inlineAccessTitle}>Instructors</h4>
                <p className={styles.inlineAccessCopy}>Assign one or more teachers to this course.</p>
              </div>
              <span className={styles.statusNote}>{(draft.instructorIds ?? []).length} selected</span>
            </header>
            <div className={styles.inlineChoiceList}>
              {instructors.length === 0 ? (
                <p className={styles.helperText}>No instructors are available yet.</p>
              ) : null}
              {instructors.map((instructor) => {
                const selected = (draft.instructorIds ?? []).includes(instructor.id);
                return (
                  <label key={instructor.id} className={`${styles.inlineChoiceCard} ${selected ? styles.inlineChoiceCardActive : ""}`}>
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => toggleId("instructorIds", instructor.id)}
                    />
                    <div>
                      <strong>{instructor.fullName}</strong>
                      <span>{instructor.schoolEmail}</span>
                    </div>
                  </label>
                );
              })}
            </div>
          </section>

          <section className={styles.inlineAccessCard}>
            <header className={styles.inlineAccessHeader}>
              <div>
                <h4 className={styles.inlineAccessTitle}>Homepage sections</h4>
                <p className={styles.inlineAccessCopy}>Choose which public department or academy section should surface this course.</p>
              </div>
              <span className={styles.statusNote}>{(draft.workspaceIds ?? []).length} selected</span>
            </header>
            <div className={styles.inlineChoiceList}>
              {workspaces.length === 0 ? (
                <p className={styles.helperText}>No workspaces are available yet.</p>
              ) : null}
              {workspaces.map((workspace) => {
                const selected = (draft.workspaceIds ?? []).includes(workspace.id);
                return (
                  <label key={workspace.id} className={`${styles.inlineChoiceCard} ${selected ? styles.inlineChoiceCardActive : ""}`}>
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => toggleId("workspaceIds", workspace.id)}
                    />
                    <div>
                      <strong>{workspace.title}</strong>
                      <span>{workspace.subtitle || workspace.slug}</span>
                    </div>
                  </label>
                );
              })}
            </div>
          </section>
        </div>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>SEO title</span>
            <input
              className={styles.input}
              value={seoTitle}
              onChange={(event) => patchEnglishOnlyField("seoTitleDe", "seoTitleEn", event.currentTarget.value)}
            />
          </label>
        </div>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>SEO description</span>
            <textarea
              className={styles.textarea}
              value={seoDescription}
              onChange={(event) =>
                patchEnglishOnlyField("seoDescriptionDe", "seoDescriptionEn", event.currentTarget.value)
              }
            />
          </label>
        </div>
      </CollapsibleSection>
    </div>
  );
};

export default CourseBuilderBasicsPanel;
