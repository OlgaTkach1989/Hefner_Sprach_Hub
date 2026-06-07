import type {
  CourseBuilderAssetType,
  CourseBuilderLanguage,
  CourseBuilderSectionItem,
  CourseBuilderSectionType,
  CourseBuilderStructuredData,
} from "@/bll/course-builder/courseBuilder.type";

export type ImportedLessonItem = {
  title: string;
  description: string;
  assetType: CourseBuilderAssetType;
  activityType?: CourseBuilderSectionItem["activityType"];
  language: CourseBuilderLanguage;
  bodyMarkdown: string;
  externalUrl: string;
  sourceLibraryItemId?: number | null;
  linkedTrainingContentId?: number | null;
  audienceIds?: number[];
  structuredData?: CourseBuilderStructuredData | null;
  sortOrder: number;
  isActive: boolean;
};

export type ImportedLessonSection = {
  sectionType: CourseBuilderSectionType;
  title: string;
  description: string;
  sortOrder: number;
  isActive: boolean;
  items: ImportedLessonItem[];
};

export type ImportedLessonDocument = {
  title?: string;
  description?: string;
  sections: ImportedLessonSection[];
};

export type LessonDocumentPreset = {
  id: string;
  label: string;
  summary: string;
  document: ImportedLessonDocument;
};

type NotebookCell = {
  cell_type?: string;
  source?: string[] | string;
  metadata?: Record<string, unknown>;
  outputs?: Array<Record<string, unknown>>;
};

const SECTION_ORDER: CourseBuilderSectionType[] = ["main"];

const DEFAULT_SECTION_TITLES: Record<CourseBuilderSectionType, string> = {
  introduction: "Introduction",
  main: "Main content",
  conclusion: "Conclusion",
};

const cloneDocument = (document: ImportedLessonDocument): ImportedLessonDocument =>
  JSON.parse(JSON.stringify(document)) as ImportedLessonDocument;

const normalizeWhitespace = (value: string) => value.replace(/\r\n/g, "\n").trim();
const normalizeLanguage = (_value?: CourseBuilderLanguage | string | null): CourseBuilderLanguage => "en";

const asText = (value: unknown) => {
  if (Array.isArray(value)) {
    return value.join("");
  }
  return typeof value === "string" ? value : "";
};

const markdownHeadingTitle = (value: string) => {
  const match = value.match(/^#+\s+(.+)$/m);
  return match?.[1]?.trim() ?? "";
};

const slugSafeTitle = (value: string, fallback: string) => {
  const trimmed = value.trim();
  return trimmed || fallback;
};

const emptySection = (sectionType: CourseBuilderSectionType, sortOrder: number): ImportedLessonSection => ({
  sectionType,
  title: DEFAULT_SECTION_TITLES[sectionType],
  description: "",
  sortOrder,
  isActive: true,
  items: [],
});

const finalizeImportedDocument = (document: ImportedLessonDocument): ImportedLessonDocument => {
  const orderedSections = [...document.sections].sort((left, right) => left.sortOrder - right.sortOrder);
  const mainSource = orderedSections.find((section) => section.sectionType === "main") ?? orderedSections[0];
  const mergedItems = orderedSections
    .flatMap((section, sectionIndex) =>
      section.items.map((item, itemIndex) => ({
        item,
        section,
        itemIndex,
        sectionSortOrder: section.sortOrder || (sectionIndex + 1) * 10,
      })),
    )
    .sort((left, right) => left.sectionSortOrder - right.sectionSortOrder || left.item.sortOrder - right.item.sortOrder);

  return {
    title: document.title?.trim() || "",
    description: document.description?.trim() || "",
    sections: [
      {
        sectionType: "main",
        title: mainSource?.title || DEFAULT_SECTION_TITLES.main,
        description: mainSource?.description || "",
        sortOrder: 10,
        isActive: mainSource?.isActive !== false,
        items: mergedItems.map(({ item, itemIndex, section }, index) => ({
          title: item.title || `${section.title || DEFAULT_SECTION_TITLES[section.sectionType]} block ${itemIndex + 1}`,
          description: item.description || "",
          assetType: item.assetType,
          activityType: item.activityType ?? (item.assetType === "notebook" ? "assignment" : "text"),
          language: normalizeLanguage(item.language),
          bodyMarkdown: item.bodyMarkdown || "",
          externalUrl: item.externalUrl || "",
          sourceLibraryItemId: item.sourceLibraryItemId ?? null,
          linkedTrainingContentId: item.linkedTrainingContentId ?? null,
          audienceIds: item.audienceIds ?? [],
          structuredData: item.structuredData ?? {},
          sortOrder: index + 1,
          isActive: item.isActive !== false,
        })),
      },
    ],
  };
};

const parseJsonLessonDocument = (raw: string): ImportedLessonDocument => {
  const payload = JSON.parse(raw) as Record<string, unknown>;
  const rawSections = Array.isArray(payload.sections) ? payload.sections : [];
  const sections: ImportedLessonSection[] = [];

  rawSections.forEach((section, sectionIndex) => {
    if (!section || typeof section !== "object") return;
    const objectSection = section as Record<string, unknown>;
    const sectionTypeValue = objectSection.sectionType;
    const sectionType: CourseBuilderSectionType =
      sectionTypeValue === "introduction" || sectionTypeValue === "main" || sectionTypeValue === "conclusion"
        ? sectionTypeValue
        : "main";
    const rawItems = Array.isArray(objectSection.items) ? objectSection.items : [];
    const items: ImportedLessonItem[] = [];

    rawItems.forEach((item, itemIndex) => {
      if (!item || typeof item !== "object") return;
      const objectItem = item as Record<string, unknown>;
      const assetTypeValue = objectItem.assetType;
      const assetType: CourseBuilderAssetType =
        assetTypeValue === "document" || assetTypeValue === "link" || assetTypeValue === "notebook" || assetTypeValue === "text"
          ? assetTypeValue
          : "text";
      const activityTypeValue = objectItem.activityType;
      const activityType =
        activityTypeValue === "video" || activityTypeValue === "quiz" || activityTypeValue === "assignment" || activityTypeValue === "text"
          ? activityTypeValue
          : assetType === "notebook"
            ? "assignment"
            : "text";
      items.push({
        title: asText(objectItem.title),
        description: asText(objectItem.description),
        assetType,
        activityType,
        language: normalizeLanguage(objectItem.language as CourseBuilderLanguage | undefined),
        bodyMarkdown: normalizeWhitespace(asText(objectItem.bodyMarkdown) || asText(objectItem.body) || asText(objectItem.markdown)),
        externalUrl: asText(objectItem.externalUrl) || asText(objectItem.url) || "",
        sourceLibraryItemId:
          typeof objectItem.sourceLibraryItemId === "number"
            ? objectItem.sourceLibraryItemId
            : null,
        linkedTrainingContentId:
          typeof objectItem.linkedTrainingContentId === "number"
            ? objectItem.linkedTrainingContentId
            : typeof objectItem.trainingContentId === "number"
              ? objectItem.trainingContentId
              : null,
        audienceIds: Array.isArray(objectItem.audienceIds)
          ? objectItem.audienceIds.filter((value): value is number => typeof value === "number")
          : [],
        structuredData:
          objectItem.structuredData && typeof objectItem.structuredData === "object" && !Array.isArray(objectItem.structuredData)
            ? (objectItem.structuredData as CourseBuilderStructuredData)
            : {},
        sortOrder: typeof objectItem.sortOrder === "number" ? objectItem.sortOrder : itemIndex + 1,
        isActive: objectItem.isActive !== false,
      });
    });

    sections.push({
      sectionType,
      title: asText(objectSection.title),
      description: asText(objectSection.description),
      sortOrder: typeof objectSection.sortOrder === "number" ? objectSection.sortOrder : (sectionIndex + 1) * 10,
      isActive: objectSection.isActive !== false,
      items,
    });
  });

  return finalizeImportedDocument({
    title: asText(payload.title),
    description: asText(payload.description),
    sections,
  });
};

const resolveNotebookSectionType = (
  _cell: NotebookCell,
  _currentSection: CourseBuilderSectionType,
): CourseBuilderSectionType => {
  return "main";
};

const outputSummary = (outputs?: NotebookCell["outputs"]) => {
  if (!Array.isArray(outputs) || outputs.length === 0) return "";
  const first = outputs[0] ?? {};
  const text = asText((first as Record<string, unknown>).text ?? (first as Record<string, unknown>).data);
  return normalizeWhitespace(text);
};

const parseNotebookLessonDocument = (raw: string, fileName: string): ImportedLessonDocument => {
  const notebook = JSON.parse(raw) as Record<string, unknown>;
  const cells = Array.isArray(notebook.cells) ? (notebook.cells as NotebookCell[]) : [];
  const sections = new Map<CourseBuilderSectionType, ImportedLessonSection>();
  let currentSection: CourseBuilderSectionType = "main";
  let lessonTitle = fileName.replace(/\.ipynb$/i, "").replace(/[-_]+/g, " ");
  let lessonDescription = "Imported from a notebook file. Review the generated lesson document and link a managed notebook runtime where needed.";
  let sawCodeCell = false;

  SECTION_ORDER.forEach((sectionType, index) => {
    sections.set(sectionType, emptySection(sectionType, (index + 1) * 10));
  });

  cells.forEach((cell) => {
    const source = normalizeWhitespace(asText(cell.source));
    if (!source) return;
    currentSection = resolveNotebookSectionType(cell, currentSection);
    const targetSection = sections.get(currentSection);
    if (!targetSection) return;

    if (!lessonTitle && cell.cell_type === "markdown") {
      lessonTitle = markdownHeadingTitle(source) || lessonTitle;
    }

    if (cell.cell_type === "markdown" && !lessonDescription && source.length > 0) {
      lessonDescription = source.slice(0, 240);
    }

    if (cell.cell_type === "markdown") {
      const title = markdownHeadingTitle(source) || `${DEFAULT_SECTION_TITLES[currentSection]} note ${targetSection.items.length + 1}`;
      targetSection.items.push({
        title,
        description: currentSection === "main" ? "Imported markdown block from notebook." : "Imported orientation block from notebook.",
        assetType: "text",
        activityType: "text",
        language: "en",
        bodyMarkdown: source,
        externalUrl: "",
        sourceLibraryItemId: null,
        linkedTrainingContentId: null,
        audienceIds: [],
        structuredData: {},
        sortOrder: targetSection.items.length + 1,
        isActive: true,
      });
      return;
    }

    if (cell.cell_type === "code") {
      sawCodeCell = true;
      const output = outputSummary(cell.outputs);
      const bodyMarkdown = [
        "```python",
        source,
        "```",
        output ? `\n**Expected output preview**\n\n\`\`\`\n${output}\n\`\`\`` : "",
      ]
        .filter(Boolean)
        .join("\n");
      targetSection.items.push({
        title: `Code walkthrough ${targetSection.items.length + 1}`,
        description: "Imported code cell from notebook. Review and convert to a managed runtime notebook if this should stay executable.",
        assetType: "text",
        activityType: "text",
        language: "en",
        bodyMarkdown,
        externalUrl: "",
        sourceLibraryItemId: null,
        linkedTrainingContentId: null,
        audienceIds: [],
        structuredData: {},
        sortOrder: targetSection.items.length + 1,
        isActive: true,
      });
    }
  });

  if (sawCodeCell) {
    const mainSection = sections.get("main");
    if (mainSection) {
      mainSection.items.push({
        title: `${slugSafeTitle(lessonTitle, "Imported lesson")} notebook assignment`,
        description: "Placeholder notebook block created from the uploaded .ipynb. Attach an internal notebook runtime in the notebook reference field before publishing.",
        assetType: "notebook",
        activityType: "assignment",
        language: "en",
        bodyMarkdown: "### Action required\n\nLink this lesson to a managed academy notebook so learners can open JupyterLab from the lesson document.",
        externalUrl: "",
        sourceLibraryItemId: null,
        linkedTrainingContentId: null,
        audienceIds: [],
        structuredData: {},
        sortOrder: mainSection.items.length + 1,
        isActive: true,
      });
    }
  }

  return finalizeImportedDocument({
    title: slugSafeTitle(lessonTitle, "Imported lesson"),
    description: lessonDescription,
    sections: [...sections.values()],
  });
};

export const parseLessonDocumentFile = async (file: File): Promise<ImportedLessonDocument> => {
  const raw = await file.text();
  if (/\.ipynb$/i.test(file.name)) {
    return parseNotebookLessonDocument(raw, file.name);
  }
  return parseJsonLessonDocument(raw);
};

export const lessonDocumentPresets: LessonDocumentPreset[] = [
  {
    id: "programming_guided_lab",
    label: "Programming guided lab",
    summary: "Intro, theory, guided coding, notebook task, and recap for a standard technical lesson.",
    document: {
      title: "Guided programming lab",
      description: "Reusable lesson document for a guided coding session with a notebook handoff.",
      sections: [
        {
          sectionType: "introduction",
          title: "Introduction",
          description: "Frame the lesson, expected outcomes, and prerequisites.",
          sortOrder: 10,
          isActive: true,
          items: [
            {
              title: "Lesson objective",
              description: "Learner-facing introduction.",
              assetType: "text",
              activityType: "text",
              language: "en",
              bodyMarkdown:
                "## Objective\n\nExplain what will be built in this lesson, which concepts are required, and how the learner should navigate the document before opening JupyterLab.",
              externalUrl: "",
              sourceLibraryItemId: null,
              linkedTrainingContentId: null,
              audienceIds: [],
              structuredData: {},
              sortOrder: 1,
              isActive: true,
            },
            {
              title: "Orientation deck",
              description: "Attach a PDF or internal briefing asset here.",
              assetType: "document",
              activityType: "text",
              language: "en",
              bodyMarkdown: "",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 2,
              isActive: true,
            },
          ],
        },
        {
          sectionType: "main",
          title: "Main content",
          description: "Primary teaching flow with theory, examples, and the managed notebook task.",
          sortOrder: 20,
          isActive: true,
          items: [
            {
              title: "Theory block",
              description: "Core concept explanation.",
              assetType: "text",
              activityType: "text",
              language: "en",
              bodyMarkdown:
                "## Core concept\n\nDocument the theory, formulas, constraints, and expected output. Use short paragraphs and code fences so the same block renders well in student and instructor workspaces.",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 1,
              isActive: true,
            },
            {
              title: "Reference video",
              description: "Lecture or walkthrough video.",
              assetType: "link",
              activityType: "video",
              language: "en",
              bodyMarkdown: "",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 2,
              isActive: true,
            },
            {
              title: "Guided practice notebook",
              description: "Managed notebook assignment linked to the academy runtime.",
              assetType: "notebook",
              activityType: "assignment",
              language: "en",
              bodyMarkdown:
                "### Notebook brief\n\nDescribe the expected coding task, success criteria, and what the learner must submit after finishing the notebook.",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 3,
              isActive: true,
            },
            {
              title: "Quick checkpoint",
              description: "Short knowledge check embedded in the lesson document.",
              assetType: "text",
              activityType: "quiz",
              language: "en",
              bodyMarkdown:
                "## Quick check\n\n- What is the main objective of this step?\n- Which input matters most?\n- Which mistake should be avoided before submission?",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 4,
              isActive: true,
            },
          ],
        },
        {
          sectionType: "conclusion",
          title: "Conclusion",
          description: "Recap, follow-up tasks, and delivery expectations.",
          sortOrder: 30,
          isActive: true,
          items: [
            {
              title: "Recap and next steps",
              description: "Closing summary block.",
              assetType: "text",
              activityType: "text",
              language: "en",
              bodyMarkdown:
                "## Wrap-up\n\nSummarize what was learned, where the learner should go next, and what to check before the next module.",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 1,
              isActive: true,
            },
          ],
        },
      ],
    },
  },
  {
    id: "programming_api_walkthrough",
    label: "Programming API walkthrough",
    summary: "Lesson pattern for external APIs, JSON inputs, validation, and a reproducible notebook workflow.",
    document: {
      title: "API walkthrough",
      description: "Reusable lesson document for API, JSON, and automation-oriented classes.",
      sections: [
        {
          sectionType: "introduction",
          title: "Introduction",
          description: "Explain the scenario and expected API/data flow.",
          sortOrder: 10,
          isActive: true,
          items: [
            {
              title: "Scenario overview",
              description: "Open the use case and explain what business problem is being solved.",
              assetType: "text",
              activityType: "text",
              language: "en",
              bodyMarkdown:
                "## Scenario\n\nDescribe the API or structured data flow, the expected payload, and what the learner should validate before coding.",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 1,
              isActive: true,
            },
          ],
        },
        {
          sectionType: "main",
          title: "Main content",
          description: "Show the endpoint, the payload shape, and the practice task.",
          sortOrder: 20,
          isActive: true,
          items: [
            {
              title: "Reference material",
              description: "Attach internal docs or an external API reference.",
              assetType: "link",
              activityType: "text",
              language: "en",
              bodyMarkdown: "",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 1,
              isActive: true,
            },
            {
              title: "Validation checklist",
              description: "Show which checks must be present in the learner solution.",
              assetType: "text",
              activityType: "text",
              language: "en",
              bodyMarkdown:
                "## Validation checklist\n\n- Parse the payload deterministically\n- Store the summary in named variables\n- Keep the notebook rerunnable from top to bottom",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 2,
              isActive: true,
            },
            {
              title: "Notebook assignment",
              description: "Link the managed notebook runtime for this lesson.",
              assetType: "notebook",
              activityType: "assignment",
              language: "en",
              bodyMarkdown:
                "### Practice task\n\nAttach the notebook used for the API or JSON exercise. Learners should complete the notebook, save it, and submit it from the lesson document.",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 3,
              isActive: true,
            },
          ],
        },
        {
          sectionType: "conclusion",
          title: "Conclusion",
          description: "Explain how to hand off the result.",
          sortOrder: 30,
          isActive: true,
          items: [
            {
              title: "Delivery note",
              description: "What the learner should provide after finishing the notebook.",
              assetType: "text",
              activityType: "text",
              language: "en",
              bodyMarkdown:
                "## Handoff\n\nWrite a short release note, summarize the key output, and state what a reviewer should inspect first.",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 1,
              isActive: true,
            },
          ],
        },
      ],
    },
  },
  {
    id: "programming_final_exam",
    label: "Programming final exam",
    summary: "Final project / exam lesson with brief, managed notebook, rubric, and submission checklist.",
    document: {
      title: "Final project / exam",
      description: "Reusable final assessment lesson document.",
      sections: [
        {
          sectionType: "introduction",
          title: "Introduction",
          description: "Describe the scope and evaluation logic.",
          sortOrder: 10,
          isActive: true,
          items: [
            {
              title: "Exam brief",
              description: "High-level expectations and constraints.",
              assetType: "text",
              activityType: "text",
              language: "en",
              bodyMarkdown:
                "## Final brief\n\nState the business scenario, scoring logic, submission rules, and how the learner should structure the final notebook.",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 1,
              isActive: true,
            },
          ],
        },
        {
          sectionType: "main",
          title: "Main content",
          description: "Show the final task and grading criteria.",
          sortOrder: 20,
          isActive: true,
          items: [
            {
              title: "Scoring rubric",
              description: "Attach PDF rubric or checklist.",
              assetType: "document",
              activityType: "text",
              language: "en",
              bodyMarkdown: "",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 1,
              isActive: true,
            },
            {
              title: "Final project notebook",
              description: "Managed runtime notebook for the final submission.",
              assetType: "notebook",
              activityType: "assignment",
              language: "en",
              bodyMarkdown:
                "### Final task\n\nAttach the final project notebook. Learners should complete it in JupyterLab and submit the `.ipynb` from this lesson document.",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 2,
              isActive: true,
            },
          ],
        },
        {
          sectionType: "conclusion",
          title: "Conclusion",
          description: "Submission checklist and handoff.",
          sortOrder: 30,
          isActive: true,
          items: [
            {
              title: "Submission checklist",
              description: "Final steps before sending the notebook to the grader.",
              assetType: "text",
              activityType: "text",
              language: "en",
              bodyMarkdown:
                "## Before submitting\n\n- Ensure the notebook runs from top to bottom\n- Add a concise summary cell\n- State one improvement or follow-up idea in the closing note",
              externalUrl: "",
              linkedTrainingContentId: null,
              audienceIds: [],
              sortOrder: 1,
              isActive: true,
            },
          ],
        },
      ],
    },
  },
];

export const getLessonDocumentPreset = (presetId: string): ImportedLessonDocument | null => {
  const preset = lessonDocumentPresets.find((candidate) => candidate.id === presetId);
  return preset ? cloneDocument(preset.document) : null;
};
