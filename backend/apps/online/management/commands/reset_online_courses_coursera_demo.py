from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.employees.models import Lehrer
from apps.online.models import (
    OnlineCohort,
    OnlineCourse,
    OnlineCourseContentLibraryItem,
    OnlineCourseMaterial,
    OnlineEnrollment,
    OnlineSession,
    OnlineStudentProfile,
    OnlineWorkspace,
    OnlineWorkspaceContentItem,
)
from apps.online.services.course_structure import (
    ensure_default_course_templates,
    sync_course_instructor_assignments,
    sync_course_workspace_placements,
    upsert_course_structure,
)
from apps.training.models import TrainingContentItem, TrainingNotebookLabHint, TrainingNotebookLabProfile
from apps.training.services.notebook_assignments import sync_course_library_for_notebook_content
from apps.training.services.notebook_storage import store_runtime_notebook_text

User = get_user_model()


@dataclass(frozen=True)
class LessonSeed:
    title: str
    description: str
    topic: str
    notebook_prompt: str
    reflection_prompt: str
    quiz_points: tuple[str, ...]
    reading_points: tuple[str, ...]


@dataclass(frozen=True)
class ModuleSeed:
    title: str
    description: str
    week_number: int
    video_url: str
    document_title: str
    document_subtitle: str
    document_points: tuple[str, ...]
    lessons: tuple[LessonSeed, ...]


@dataclass(frozen=True)
class CourseSeed:
    slug: str
    title_en: str
    title_de: str
    short_description_en: str
    short_description_de: str
    description_en: str
    description_de: str
    modules: tuple[ModuleSeed, ...]
    final_title: str
    final_description: str
    final_instruction: str


COURSE_SEEDS: tuple[CourseSeed, ...] = (
    CourseSeed(
        slug="python-core-fundamentals",
        title_en="Python Core Fundamentals",
        title_de="Python Core Fundamentals",
        short_description_en="Programming foundations with notebook practice, guided lessons, and delivery checkpoints.",
        short_description_de="Programming foundations with notebook practice, guided lessons, and delivery checkpoints.",
        description_en=(
            "Internal academy programming track for learners who need structured Python fluency. "
            "Every lesson includes a lecture video, a briefing PDF, a reading checklist, a quiz, and a notebook assignment."
        ),
        description_de=(
            "Internal academy programming track for learners who need structured Python fluency. "
            "Every lesson includes a lecture video, a briefing PDF, a reading checklist, a quiz, and a notebook assignment."
        ),
        modules=(
            ModuleSeed(
                title="Module 1 (Week 1) - Python Basics",
                description="Runtime setup, syntax, and the first computational habits.",
                week_number=1,
                video_url="https://www.youtube.com/watch?v=kqtD5dpn9C8",
                document_title="Python setup deck",
                document_subtitle="Notebook workflow, interpreter setup, and learning expectations",
                document_points=(
                    "Verify the interpreter and notebook runtime before you start coding",
                    "Use markdown and short code cells to make every notebook review-ready",
                    "Restart and re-run the notebook to prove the workflow is reproducible",
                ),
                lessons=(
                    LessonSeed(
                        "Getting Started with Python",
                        "Kernel setup, syntax basics, and the first notebook run.",
                        "environment",
                        "Confirm the runtime, capture the interpreter version, and create a clear run label.",
                        "Write one short markdown note about why reproducibility matters before coding.",
                        (
                            "Kernel is active",
                            "Run label is created",
                            "The first notebook output is visible",
                        ),
                        (
                            "Notebook setup is complete",
                            "Review the deck before coding",
                            "Keep the output trace clean",
                        ),
                    ),
                    LessonSeed(
                        "Variables, Types, and I/O",
                        "Primitive values, string formatting, and controlled console output.",
                        "variables",
                        "Build a small pricing summary using variables and formatted strings.",
                        "Explain why explicit variable names improve review quality.",
                        (
                            "Price, quantity, and total should line up",
                            "Formatted output should show the expected summary",
                            "The result should read like a report line",
                        ),
                        (
                            "Variables drive all downstream calculations",
                            "Think in terms of inputs and outputs",
                            "Use a short notebook note to explain your choices",
                        ),
                    ),
                ),
            ),
            ModuleSeed(
                title="Module 2 (Week 2) - Functions and Data Structures",
                description="Reusable logic, collections, and safe transformations.",
                week_number=2,
                video_url="https://www.youtube.com/watch?v=rfscVS0vtbw",
                document_title="Python data structures brief",
                document_subtitle="Patterns for functions, collections, and reusable calculations",
                document_points=(
                    "Prefer small functions over repeated code",
                    "Use dictionaries for named business context",
                    "Use lists for ordered slices and checkpoints",
                ),
                lessons=(
                    LessonSeed(
                        "Functions and Scope",
                        "Reusable helpers, return values, and simple control flow.",
                        "functions",
                        "Define a helper that normalizes a raw amount and use it in a short calculation.",
                        "Document the function with one sentence that explains the intent.",
                        (
                            "The helper function exists",
                            "The normalized amount is computed",
                            "The result is easy to read",
                        ),
                        (
                            "Use functions when the same transformation appears twice",
                            "Return values are easier to grade than screenshots",
                            "Keep the explanation concise",
                        ),
                    ),
                    LessonSeed(
                        "Lists, Tuples, and Dictionaries",
                        "Collect structured values and summarize them without losing the key labels.",
                        "collections",
                        "Summarize a small set of trade-like records and keep the strongest signal visible.",
                        "Explain which collection type you used and why it fits the task.",
                        (
                            "A summary variable is defined",
                            "The strongest item can be identified",
                            "The response remains readable",
                        ),
                        (
                            "Collections should match the shape of the data",
                            "Dictionaries carry business meaning well",
                            "Write one note about the chosen representation",
                        ),
                    ),
                ),
            ),
            ModuleSeed(
                title="Module 3 (Week 3) - Files and Testing",
                description="Text files, validation, and review-ready delivery habits.",
                week_number=3,
                video_url="https://www.youtube.com/watch?v=rfscVS0vtbw",
                document_title="Delivery and testing checklist",
                document_subtitle="How to keep notebooks readable, auditable, and easy to review",
                document_points=(
                    "Every submission should include a clear summary cell",
                    "Tests and assertions reduce manual review time",
                    "File handling should be explicit and reproducible",
                ),
                lessons=(
                    LessonSeed(
                        "Working with Files",
                        "Read a small text payload and extract a summary metric from it.",
                        "files",
                        "Count the meaningful lines in a short file-like text block and store the result.",
                        "Add one markdown note about why file parsing belongs in notebooks.",
                        (
                            "The line count is stored in a variable",
                            "The notebook shows a readable parse result",
                            "The summary is easy to verify",
                        ),
                        (
                            "File content should be summarized, not dumped",
                            "A short note helps reviewers understand the intent",
                            "Keep the parsing logic simple",
                        ),
                    ),
                    LessonSeed(
                        "Unit Tests and Debugging",
                        "Write a small validation helper and explain how you would test it.",
                        "testing",
                        "Define a validation helper and record a short debug note for the reviewer.",
                        "Mention assertions or tests in the reflection cell.",
                        (
                            "The validation helper is defined",
                            "The notebook includes a test-style check",
                            "The result stays within the expected range",
                        ),
                        (
                            "Think like a reviewer and keep the checks explicit",
                            "Explain the debugging approach in one sentence",
                            "Show the expected result clearly",
                        ),
                    ),
                ),
            ),
        ),
        final_title="Final Project / Exam",
        final_description="Build a small command-line analytics tool and explain the design choices.",
        final_instruction="Submit the final notebook, include a concise release note, and summarize the result in your own words.",
    ),
    CourseSeed(
        slug="python-data-workflows",
        title_en="Python Data Workflows",
        title_de="Python Data Workflows",
        short_description_en="Data-centric programming track with notebooks, reusable analysis blocks, and final delivery tasks.",
        short_description_de="Data-centric programming track with notebooks, reusable analysis blocks, and final delivery tasks.",
        description_en=(
            "Internal academy programming track for data handling, analysis, and reproducible notebook delivery. "
            "Every lesson includes video, PDF notes, guided reading, a quiz, and a notebook assignment."
        ),
        description_de=(
            "Internal academy programming track for data handling, analysis, and reproducible notebook delivery. "
            "Every lesson includes video, PDF notes, guided reading, a quiz, and a notebook assignment."
        ),
        modules=(
            ModuleSeed(
                title="Module 1 (Week 1) - Numerical Thinking",
                description="Arrays, vectorization, and the first data workflow habits.",
                week_number=1,
                video_url="https://www.youtube.com/watch?v=QUT1VHiLmmI",
                document_title="Numerical thinking deck",
                document_subtitle="Array thinking, vectorization, and notebook-led analysis",
                document_points=(
                    "Prefer vectorized operations when possible",
                    "Track shapes and missing values explicitly",
                    "Explain the step before you execute it",
                ),
                lessons=(
                    LessonSeed(
                        "NumPy Arrays and Vectorization",
                        "Array operations, numeric summaries, and vectorized thinking.",
                        "numpy",
                        "Build a compact summary of returns using array operations and store the key metric.",
                        "Write one sentence about why vectorization is easier to review than manual loops.",
                        (
                            "A NumPy import or equivalent array workflow is present",
                            "The mean-like summary is computed",
                            "The notebook is structured with a short explanation",
                        ),
                        (
                            "Array code should be concise and repeatable",
                            "Shapes and dtypes matter in analysis work",
                            "Keep the notebook easy to rerun",
                        ),
                    ),
                    LessonSeed(
                        "Pandas DataFrames",
                        "Tabular data, indexing, and short aggregations.",
                        "pandas",
                        "Load or build a tiny table, aggregate it, and capture the clean result in one variable.",
                        "Write a note that explains which table operation you used and why.",
                        (
                            "A Pandas import or equivalent table workflow is present",
                            "The aggregation result is stored",
                            "The notebook shows a readable summary line",
                        ),
                        (
                            "Tabular operations should read like business logic",
                            "Aggregation beats manual counting",
                            "Document the workflow in one brief note",
                        ),
                    ),
                ),
            ),
            ModuleSeed(
                title="Module 2 (Week 2) - Data Quality and Visualization",
                description="Cleaning, inspection, and visual communication.",
                week_number=2,
                video_url="https://www.youtube.com/watch?v=r-uOLxNrNk8",
                document_title="Data quality brief",
                document_subtitle="Missing values, charting, and communication for notebooks",
                document_points=(
                    "Clean inputs before drawing conclusions",
                    "Use charts to support a short story",
                    "Write notes that explain the transformation steps",
                ),
                lessons=(
                    LessonSeed(
                        "Missing Data and Cleaning",
                        "Inspect gaps, normalize values, and keep the result tidy.",
                        "data_cleaning",
                        "Count missing rows, clean the sample table, and save the cleaned-row count.",
                        "Explain which cleaning rule you chose and why it is safe.",
                        (
                            "The cleaned row count is stored",
                            "Missing values are discussed",
                            "The notebook shows the cleaning decision",
                        ),
                        (
                            "Cleaning rules should be explicit",
                            "Short notebooks are easier to validate",
                            "State the assumption behind the cleanup",
                        ),
                    ),
                    LessonSeed(
                        "Visualization Basics",
                        "Communicate a small result with a simple chart and a concise narrative.",
                        "visualization",
                        "Create a chart-ready summary and describe the main pattern in a short paragraph.",
                        "Mention the chart title or takeaway in the reflection cell.",
                        (
                            "A chart-oriented summary variable is defined",
                            "The main takeaway is documented",
                            "The notebook is readable from top to bottom",
                        ),
                        (
                            "Charts should support the point, not replace it",
                            "Keep the takeaway in one sentence",
                            "Match the chart to the data shape",
                        ),
                    ),
                ),
            ),
            ModuleSeed(
                title="Module 3 (Week 3) - Reproducibility and Delivery",
                description="JSON inputs, scenario analysis, and notebook handoff habits.",
                week_number=3,
                video_url="https://www.youtube.com/watch?v=r-uOLxNrNk8",
                document_title="Delivery automation brief",
                document_subtitle="How to package analysis notebooks for review and reuse",
                document_points=(
                    "Always add a run label and a clean summary cell",
                    "Treat JSON and configuration as first-class inputs",
                    "Include a short handoff note for reviewers",
                ),
                lessons=(
                    LessonSeed(
                        "JSON Inputs and Lightweight APIs",
                        "Read structured input and summarize the payload in a deterministic way.",
                        "json_inputs",
                        "Count the records in a JSON-style payload and keep the summary visible.",
                        "Explain why JSON is useful when notebooks need structured inputs.",
                        (
                            "Payload count is stored",
                            "The summary is deterministic",
                            "The notebook reflects structured input handling",
                        ),
                        (
                            "JSON data should be parsed before analysis",
                            "A deterministic summary helps grading",
                            "Describe the input shape in one note",
                        ),
                    ),
                    LessonSeed(
                        "Scenario Analysis and Delivery Automation",
                        "Combine what you learned into a reproducible analysis summary.",
                        "delivery_automation",
                        "Build a compact scenario summary and record the release note for the notebook.",
                        "Mention the delivery checklist and the reviewer handoff in the reflection cell.",
                        (
                            "Scenario summary is stored",
                            "A release note is visible",
                            "The delivery story is clear",
                        ),
                        (
                            "Delivery automation is about repeatability",
                            "Keep the handoff short but explicit",
                            "Document the result for the next reviewer",
                        ),
                    ),
                ),
            ),
        ),
        final_title="Final Project / Exam",
        final_description="Deliver a reproducible data analysis notebook and explain the pipeline decisions.",
        final_instruction="Submit the final notebook together with a one-page summary of your workflow and result interpretation.",
    ),
    CourseSeed(
        slug="python-web-and-apis",
        title_en="Python Web and APIs",
        title_de="Python Web and APIs",
        short_description_en="Web-oriented programming track with HTTP, payload handling, endpoint logic, and delivery-ready notebook exercises.",
        short_description_de="Web-oriented programming track with HTTP, payload handling, endpoint logic, and delivery-ready notebook exercises.",
        description_en=(
            "Internal academy web track focused on HTTP workflows, structured payload handling, "
            "endpoint logic, and review-ready notebook delivery. Every lesson includes video, PDF notes, "
            "guided reading, a quiz, and a notebook assignment."
        ),
        description_de=(
            "Internal academy web track focused on HTTP workflows, structured payload handling, "
            "endpoint logic, and review-ready notebook delivery. Every lesson includes video, PDF notes, "
            "guided reading, a quiz, and a notebook assignment."
        ),
        modules=(
            ModuleSeed(
                title="Module 1 (Week 1) - HTTP and Payload Basics",
                description="Requests, responses, and structured payload review.",
                week_number=1,
                video_url="https://www.youtube.com/watch?v=tb8gHvYlCFs",
                document_title="HTTP and payload deck",
                document_subtitle="How to inspect API responses and keep notebook evidence clean",
                document_points=(
                    "Treat every payload as structured input",
                    "Capture the key fields before deeper analysis",
                    "Document the response assumptions in one sentence",
                ),
                lessons=(
                    LessonSeed(
                        "HTTP Requests and Responses",
                        "Read a compact API-style exchange and document the key response facts.",
                        "json_inputs",
                        "Parse a small payload and keep the record count visible in the notebook.",
                        "Explain why structured payload review is safer than manual inspection.",
                        (
                            "The payload count is computed",
                            "The notebook shows a deterministic result",
                            "The response note is easy to review",
                        ),
                        (
                            "Structured inputs should be summarized first",
                            "Keep the notebook trace deterministic",
                            "Describe the payload shape in one note",
                        ),
                    ),
                    LessonSeed(
                        "Tabular API Payload Review",
                        "Convert a response into a table-friendly summary for operational review.",
                        "pandas",
                        "Build a tiny summary table from a response-like payload and store the row count.",
                        "Write one sentence about why table views help reviewers validate payloads faster.",
                        (
                            "A small table summary is produced",
                            "The row count is visible",
                            "The notebook reads like an operational review",
                        ),
                        (
                            "Table summaries reduce manual review time",
                            "Keep the transformation steps short",
                            "Document the chosen aggregation in one note",
                        ),
                    ),
                ),
            ),
            ModuleSeed(
                title="Module 2 (Week 2) - Routing and Validation",
                description="Functions, endpoint logic, and validation routines.",
                week_number=2,
                video_url="https://www.youtube.com/watch?v=Z1RJmh_OqeA",
                document_title="Routing and validation brief",
                document_subtitle="Small endpoint thinking, clean handlers, and simple checks",
                document_points=(
                    "Small functions map well to endpoint handlers",
                    "Validation should be explicit and reviewable",
                    "Keep examples small enough to rerun quickly",
                ),
                lessons=(
                    LessonSeed(
                        "Functions and Routing",
                        "Design a tiny handler-style function and make the intent obvious.",
                        "functions",
                        "Define a helper that normalizes request-like input and returns a clean result.",
                        "Document the function signature and explain what it protects against.",
                        (
                            "The helper is defined",
                            "A normalized result is produced",
                            "The notebook explains the intent clearly",
                        ),
                        (
                            "Endpoint logic should stay explicit",
                            "Use one helper instead of repeated code",
                            "Add a short note about the returned value",
                        ),
                    ),
                    LessonSeed(
                        "Validation and Debugging",
                        "Add a lightweight validation layer before the result is accepted.",
                        "testing",
                        "Create a minimal validation helper and show one assertion-style check.",
                        "Explain how this validation step would support a production review.",
                        (
                            "Validation logic exists",
                            "A check or assertion is visible",
                            "The review note stays concise",
                        ),
                        (
                            "Validation should fail loudly and clearly",
                            "Keep the example small and deterministic",
                            "Note how a reviewer would confirm the result",
                        ),
                    ),
                ),
            ),
            ModuleSeed(
                title="Module 3 (Week 3) - Configuration and Delivery",
                description="Configuration files, service notes, and reproducible release handoff.",
                week_number=3,
                video_url="https://www.youtube.com/watch?v=6tNS--WetLI",
                document_title="Service delivery deck",
                document_subtitle="Configuration handling, file-based inputs, and handoff structure",
                document_points=(
                    "Configuration belongs next to the execution story",
                    "Files and JSON should be parsed, not eyeballed",
                    "Every notebook should end with a handoff note",
                ),
                lessons=(
                    LessonSeed(
                        "Configuration Files and Inputs",
                        "Review small config-like inputs and summarize what matters for runtime behavior.",
                        "files",
                        "Count the meaningful configuration lines and keep the summary cell visible.",
                        "Write one sentence about why config inspection belongs in delivery notebooks.",
                        (
                            "A deterministic count is produced",
                            "The notebook highlights the input assumptions",
                            "The summary is easy to validate",
                        ),
                        (
                            "Configuration should be treated as structured evidence",
                            "Keep the summary concise",
                            "End with one note for the reviewer",
                        ),
                    ),
                    LessonSeed(
                        "Release Handoffs for Services",
                        "Package the result as a short service handoff that another reviewer can follow.",
                        "delivery_automation",
                        "Create a compact release summary and store the delivery-ready flag.",
                        "Mention what the next reviewer should inspect first.",
                        (
                            "The release flag is explicit",
                            "A short handoff note exists",
                            "The final result is easy to scan",
                        ),
                        (
                            "A handoff should tell the next reviewer where to start",
                            "Keep the release note short and operational",
                            "Summaries should be deterministic",
                        ),
                    ),
                ),
            ),
        ),
        final_title="Final Project / Exam",
        final_description="Build a small API review notebook and package it as a clean operational handoff.",
        final_instruction="Submit the final notebook together with a short release note and a compact reviewer checklist.",
    ),
    CourseSeed(
        slug="python-testing-and-automation",
        title_en="Python Testing and Automation",
        title_de="Python Testing and Automation",
        short_description_en="Automation-focused programming track with validation, cleanup, repeatability, and final delivery checkpoints.",
        short_description_de="Automation-focused programming track with validation, cleanup, repeatability, and final delivery checkpoints.",
        description_en=(
            "Internal academy automation track focused on validation, repeatable routines, "
            "cleanup flows, and reviewer-friendly notebook delivery. Every lesson includes video, PDF notes, "
            "guided reading, a quiz, and a notebook assignment."
        ),
        description_de=(
            "Internal academy automation track focused on validation, repeatable routines, "
            "cleanup flows, and reviewer-friendly notebook delivery. Every lesson includes video, PDF notes, "
            "guided reading, a quiz, and a notebook assignment."
        ),
        modules=(
            ModuleSeed(
                title="Module 1 (Week 1) - Testing Foundations",
                description="Assertions, helper functions, and reviewer-friendly notebook habits.",
                week_number=1,
                video_url="https://www.youtube.com/watch?v=YbpKMIUjvK8",
                document_title="Testing foundations deck",
                document_subtitle="Validation helpers, assertions, and compact debug notes",
                document_points=(
                    "Assertions make notebook review faster",
                    "Helpers keep repeated checks readable",
                    "A short debug note often matters more than raw output",
                ),
                lessons=(
                    LessonSeed(
                        "Assertions and Validation Checks",
                        "Create a lightweight validation step and show how a reviewer would read it.",
                        "testing",
                        "Define a validation helper and record a short debug note for the reviewer.",
                        "Explain how this check reduces manual rework during review.",
                        (
                            "The validation helper is present",
                            "A notebook check is visible",
                            "The reviewer note is explicit",
                        ),
                        (
                            "Checks should be easy to rerun",
                            "Debug notes should stay brief",
                            "Validation belongs near the result",
                        ),
                    ),
                    LessonSeed(
                        "Reusable Automation Helpers",
                        "Package repeated logic into a helper that supports a cleaner automation flow.",
                        "functions",
                        "Create a helper that normalizes an automation input before it is passed downstream.",
                        "Write one sentence about why helper boundaries make review easier.",
                        (
                            "The helper exists",
                            "The normalized value is computed",
                            "The notebook communicates the intent clearly",
                        ),
                        (
                            "Helpers reduce repeated logic",
                            "Keep the boundary between steps explicit",
                            "Document the returned value briefly",
                        ),
                    ),
                ),
            ),
            ModuleSeed(
                title="Module 2 (Week 2) - Cleanup and File Handling",
                description="Data cleanup, deterministic outputs, and file-oriented automation.",
                week_number=2,
                video_url="https://www.youtube.com/watch?v=rfscVS0vtbw",
                document_title="Cleanup and file workflow brief",
                document_subtitle="Deterministic cleaning rules and explicit file parsing patterns",
                document_points=(
                    "Cleanup rules should be visible before execution",
                    "File handling must stay deterministic",
                    "Reviewers need one clear summary cell",
                ),
                lessons=(
                    LessonSeed(
                        "Cleanup Rules and Exceptions",
                        "Make a small cleanup decision visible and explain why it is safe.",
                        "data_cleaning",
                        "Clean a small frame-like sample and keep the cleaned-row count visible.",
                        "Explain the cleanup rule and why a reviewer should trust it.",
                        (
                            "The cleaned-row count is explicit",
                            "The cleanup rule is documented",
                            "The notebook remains deterministic",
                        ),
                        (
                            "Cleanup must be justified",
                            "Short deterministic flows are easier to grade",
                            "Keep assumptions visible",
                        ),
                    ),
                    LessonSeed(
                        "File Parsing for Automation",
                        "Count a small file-style payload and package the result for a reviewer.",
                        "files",
                        "Count the meaningful lines in a short text payload and store the result cleanly.",
                        "Add one note about why file parsing belongs in automation notebooks.",
                        (
                            "The count result is stored",
                            "The parse step is easy to review",
                            "The note explains the intent",
                        ),
                        (
                            "Automation notebooks should summarize file inputs",
                            "Avoid noisy intermediate output",
                            "State the parsing rule clearly",
                        ),
                    ),
                ),
            ),
            ModuleSeed(
                title="Module 3 (Week 3) - Reporting and Release Automation",
                description="Structured inputs, summary variables, and final release packaging.",
                week_number=3,
                video_url="https://www.youtube.com/watch?v=QUT1VHiLmmI",
                document_title="Automation delivery deck",
                document_subtitle="How to turn notebook work into repeatable release output",
                document_points=(
                    "Structured inputs should lead to structured summaries",
                    "Release notes belong in the notebook handoff",
                    "The final metric should be visible without scrolling through code",
                ),
                lessons=(
                    LessonSeed(
                        "Structured Inputs for Reports",
                        "Ingest a compact payload and expose the key operational count clearly.",
                        "json_inputs",
                        "Parse a small payload and keep the summary visible in one deterministic cell.",
                        "Explain how structured inputs improve repeatable reporting.",
                        (
                            "The payload summary is visible",
                            "The result is deterministic",
                            "The note explains the reporting value",
                        ),
                        (
                            "Structured inputs should drive deterministic summaries",
                            "Keep the reporting logic small",
                            "Note what the reviewer should confirm first",
                        ),
                    ),
                    LessonSeed(
                        "Release Notes and Automation Handoff",
                        "Package the final result as an automation handoff that can be reviewed quickly.",
                        "delivery_automation",
                        "Create a release-ready summary and keep the delivery flag explicit.",
                        "Mention what a reviewer should validate before sign-off.",
                        (
                            "The release-ready flag is explicit",
                            "The handoff note exists",
                            "The notebook ends with a clear reviewer path",
                        ),
                        (
                            "Release notes should be operational, not narrative-heavy",
                            "Summaries should stay deterministic",
                            "End with the next reviewer action",
                        ),
                    ),
                ),
            ),
        ),
        final_title="Final Project / Exam",
        final_description="Build an automation review notebook that validates, summarizes, and packages a final release handoff.",
        final_instruction="Submit the final notebook with a release checklist, explicit validation notes, and a concise reviewer handoff.",
    ),
)

COURSE_WORKSPACE_SLUGS: dict[str, tuple[str, ...]] = {
    "python-core-fundamentals": ("berlin", "it", "academy-resources"),
    "python-data-workflows": ("berlin", "finance", "london", "academy-resources"),
    "python-web-and-apis": ("berlin", "new-york", "academy-resources"),
    "python-testing-and-automation": ("berlin", "prague", "academy-resources"),
}

COURSE_HERO_IMAGE_URLS: dict[str, str] = {
    "python-core-fundamentals": "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?auto=format&fit=crop&w=1200&q=80",
    "python-data-workflows": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1200&q=80",
    "python-web-and-apis": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=1200&q=80",
    "python-testing-and-automation": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80",
}


class Command(BaseCommand):
    help = (
        "Reset online courses and seed four programming demo courses with modules, lessons, "
        "video/text/quiz/assignment items, and final project modules."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-purge",
            action="store_true",
            help="Keep existing courses and append demo courses instead of removing all courses.",
        )
        parser.add_argument(
            "--confirm-reset",
            dest="confirm_reset",
            default="",
            help="Required safety token for destructive purge. Use: --confirm-reset RESET",
        )
        parser.add_argument(
            "--teacher-email",
            dest="teacher_email",
            default="teacher@learning-hub.local",
            help="Optional curator email to attach to seeded cohorts.",
        )
        parser.add_argument(
            "--student-email",
            dest="student_email",
            default="mailpit.student@example.com",
            help="Optional student email to enroll into the first seeded cohort.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        ensure_default_course_templates()

        if not options.get("skip_purge"):
            confirm_reset = str(options.get("confirm_reset") or "").strip().upper()
            if confirm_reset != "RESET":
                raise CommandError(
                    "Refusing to purge courses without explicit confirmation. "
                    "Use --confirm-reset RESET or pass --skip-purge."
                )
            removed_count = OnlineCourse.objects.count()
            enrollments_removed = OnlineEnrollment.objects.count()
            orders_removed = sum(profile.orders.count() for profile in OnlineStudentProfile.objects.all())
            workspace_cards_removed = OnlineWorkspaceContentItem.objects.filter(
                section=OnlineWorkspaceContentItem.SECTION_COURSES
            ).count()
            OnlineEnrollment.objects.all().delete()
            for profile in OnlineStudentProfile.objects.all():
                profile.orders.all().delete()
            OnlineCohort.objects.all().delete()
            OnlineCourse.objects.all().delete()
            OnlineWorkspaceContentItem.objects.filter(
                section=OnlineWorkspaceContentItem.SECTION_COURSES
            ).delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Removed existing courses: {removed_count}; "
                    f"enrollments: {enrollments_removed}; orders: {orders_removed}; "
                    f"workspace course cards: {workspace_cards_removed}"
                )
            )

        teacher = self._resolve_teacher(str(options.get("teacher_email") or "").strip())

        seeded_pairs: list[tuple[OnlineCourse, OnlineCohort]] = []
        berlin_tz = ZoneInfo("Europe/Berlin")
        start_anchor = date.today() + timedelta(days=7)

        for course_seed_index, course_seed in enumerate(COURSE_SEEDS, start=1):
            course_start = datetime.combine(
                start_anchor + timedelta(weeks=(course_seed_index - 1) * 3),
                time(9, 0, 0),
            ).replace(tzinfo=berlin_tz)
            course_end = course_start + timedelta(weeks=10)
            course = OnlineCourse.objects.update_or_create(
                slug=course_seed.slug,
                defaults={
                    "title_en": course_seed.title_en,
                    "title_de": course_seed.title_de,
                    "short_description_en": course_seed.short_description_en,
                    "short_description_de": course_seed.short_description_de,
                    "description_en": course_seed.description_en,
                    "description_de": course_seed.description_de,
                    "trial_available": False,
                    "price_amount": Decimal("0.00"),
                    "currency": "EUR",
                    "is_subscription": False,
                    "is_published": True,
                    "hero_image_url": COURSE_HERO_IMAGE_URLS.get(course_seed.slug, ""),
                    "seo_title_en": course_seed.title_en,
                    "seo_title_de": course_seed.title_de,
                    "seo_description_en": course_seed.short_description_en,
                    "seo_description_de": course_seed.short_description_de,
                    "geo_city": "Berlin",
                    "geo_country": "DE",
                    "starts_at": course_start,
                    "ends_at": course_end,
                    "lessons_count": sum(len(module.lessons) for module in course_seed.modules) + 1,
                },
            )[0]

            modules_payload = self._build_programming_modules_payload(
                course=course,
                course_seed=course_seed,
                course_start=course_start,
            )
            upsert_course_structure(course, None, modules_data=modules_payload)

            self._upsert_programming_materials(course)
            cohort = self._upsert_cohort(
                course=course,
                teacher=teacher,
                group_code=f"{course.slug.replace('-', '_').upper()}_G1",
                group_name=f"{course.title_en} - Group 1",
                start_date=start_anchor + timedelta(days=(course_seed_index - 1) * 7),
            )
            self._seed_sessions(course=course, cohort=cohort, timezone_value=berlin_tz)
            sync_course_instructor_assignments(
                course=course,
                teacher_ids=[teacher.id] if teacher else [],
            )
            sync_course_workspace_placements(
                course=course,
                workspace_ids=self._resolve_workspace_ids_for_course(course_seed.slug),
                linked_cohort=cohort,
            )
            seeded_pairs.append((course, cohort))
            self.stdout.write(self.style.SUCCESS(f"Seeded course: {course.slug}"))

        self._enroll_student_if_present(
            student_email=str(options.get("student_email") or "").strip(),
            cohort=seeded_pairs[0][1] if seeded_pairs else None,
        )
        call_command(
            "seed_training_bitcoin_case_demo",
            student_email=str(options.get("student_email") or "").strip(),
            teacher_email=str(options.get("teacher_email") or "").strip(),
        )
        self.stdout.write(self.style.SUCCESS("Programming demo course seeding completed."))

    def _resolve_teacher(self, teacher_email: str) -> Lehrer | None:
        if not teacher_email:
            return Lehrer.objects.select_related("user").order_by("id").first()
        teacher = Lehrer.objects.select_related("user").filter(user__email__iexact=teacher_email).first()
        if teacher:
            return teacher
        return Lehrer.objects.select_related("user").order_by("id").first()

    def _resolve_workspace_ids_for_course(self, course_slug: str) -> list[int]:
        requested_slugs = COURSE_WORKSPACE_SLUGS.get(course_slug, ("academy-resources",))
        workspaces = list(
            OnlineWorkspace.objects.filter(slug__in=requested_slugs, is_published=True).order_by("sort_order", "id")
        )
        if workspaces:
            return [workspace.id for workspace in workspaces]

        fallback_workspace = (
            OnlineWorkspace.objects.filter(kind=OnlineWorkspace.KIND_SHARED, is_published=True)
            .order_by("sort_order", "id")
            .first()
        )
        if fallback_workspace:
            return [fallback_workspace.id]
        return []

    def _attach_library_file(self, item: OnlineCourseContentLibraryItem, relative_path: str) -> None:
        source_path = Path(settings.BASE_DIR) / relative_path
        if not source_path.exists():
            return

        current_name = Path(item.file_asset.name).name if item.file_asset else ""
        if current_name == source_path.name:
            return

        with source_path.open("rb") as source_stream:
            item.file_asset.save(source_path.name, File(source_stream), save=False)

        item.save(update_fields=["file_asset", "updated_at"])

    @staticmethod
    def _escape_pdf_text(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    @classmethod
    def _build_simple_pdf_bytes(
        cls,
        *,
        title: str,
        subtitle: str,
        bullets: list[str],
    ) -> bytes:
        lines = [title.strip(), subtitle.strip(), *[f"- {item.strip()}" for item in bullets if item.strip()]]
        commands: list[str] = []
        cursor_y = 770
        for index, line in enumerate(lines):
            font_size = 24 if index == 0 else 14 if index == 1 else 12
            if not line:
                cursor_y -= 10
                continue
            commands.extend(
                [
                    "BT",
                    f"/F1 {font_size} Tf",
                    f"50 {cursor_y} Td",
                    f"({cls._escape_pdf_text(line)}) Tj",
                    "ET",
                ]
            )
            cursor_y -= 34 if index == 0 else 22

        stream = "\n".join(commands).encode("latin-1", errors="ignore")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            ),
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]

        pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets: list[int] = []
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(pdf))
            pdf.extend(f"{index} 0 obj\n".encode("ascii"))
            pdf.extend(obj)
            pdf.extend(b"\nendobj\n")

        xref_offset = len(pdf)
        pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets:
            pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        pdf.extend(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_offset}\n%%EOF\n"
            ).encode("ascii")
        )
        return bytes(pdf)

    def _topic_notebook_spec(self, topic: str, *, final_project: bool = False) -> dict[str, object]:
        topic_key = topic.strip().lower().replace(" ", "_")
        if final_project:
            return {
                "target_variable": "final_score",
                "expected_value": Decimal("100"),
                "required_function": "build_final_report",
                "required_code": "from pathlib import Path",
                "focus_needle": "final",
                "hint_primary": "Summarize the full workflow and keep the final score explicit.",
                "hint_secondary": "Add a short delivery note that explains what the reviewer should look at first.",
                "hint_ai": "Ask the assistant to help you write a compact handoff note.",
            }

        spec_map: dict[str, dict[str, object]] = {
            "environment": {
                "target_variable": "runtime_ready",
                "expected_value": Decimal("1"),
                "required_function": "describe_runtime",
                "required_code": "import sys",
                "focus_needle": "runtime",
                "hint_primary": "Confirm the kernel and keep the runtime label visible.",
                "hint_secondary": "Use a short note to explain why reproducibility matters.",
                "hint_ai": "Ask the assistant how to describe the runtime in one sentence.",
            },
            "variables": {
                "target_variable": "order_total",
                "expected_value": Decimal("72"),
                "required_function": "format_trade_line",
                "required_code": "",
                "focus_needle": "variables",
                "hint_primary": "Use simple arithmetic and keep the output readable.",
                "hint_secondary": "Make the formatting line easy to inspect.",
                "hint_ai": "Ask the assistant for a short formatting pattern.",
            },
            "functions": {
                "target_variable": "normalized_value",
                "expected_value": Decimal("225"),
                "required_function": "normalize_amount",
                "required_code": "",
                "focus_needle": "function",
                "hint_primary": "Define the helper first, then compute the result.",
                "hint_secondary": "Keep the function small and explicit.",
                "hint_ai": "Ask the assistant to explain the helper signature.",
            },
            "collections": {
                "target_variable": "top_price",
                "expected_value": Decimal("14"),
                "required_function": "summarize_positions",
                "required_code": "",
                "focus_needle": "collection",
                "hint_primary": "Use list and dictionary patterns to summarize the records.",
                "hint_secondary": "Write one short explanation about the data shape.",
                "hint_ai": "Ask the assistant how to summarize ordered records.",
            },
            "files": {
                "target_variable": "line_count",
                "expected_value": Decimal("4"),
                "required_function": "count_meaningful_lines",
                "required_code": "from pathlib import Path",
                "focus_needle": "file",
                "hint_primary": "Count only the meaningful lines in the text sample.",
                "hint_secondary": "Explain why file parsing belongs in a notebook.",
                "hint_ai": "Ask the assistant for a quick parsing pattern.",
            },
            "testing": {
                "target_variable": "validation_score",
                "expected_value": Decimal("1"),
                "required_function": "validate_sample",
                "required_code": "",
                "focus_needle": "test",
                "hint_primary": "Add a tiny validation helper and a small assertion-style check.",
                "hint_secondary": "Write one note about the debugging approach.",
                "hint_ai": "Ask the assistant what a minimal validation step looks like.",
            },
            "numpy": {
                "target_variable": "mean_return",
                "expected_value": Decimal("0.018"),
                "required_function": "summarize_returns",
                "required_code": "import numpy as np",
                "focus_needle": "array",
                "hint_primary": "Use vectorized operations and keep the code compact.",
                "hint_secondary": "Record one note about shape and dtype.",
                "hint_ai": "Ask the assistant about a vectorized mean calculation.",
            },
            "pandas": {
                "target_variable": "row_count",
                "expected_value": Decimal("5"),
                "required_function": "build_summary_table",
                "required_code": "import pandas as pd",
                "focus_needle": "table",
                "hint_primary": "Use a small table and a simple aggregation.",
                "hint_secondary": "Make the table summary easy to review.",
                "hint_ai": "Ask the assistant for a clean aggregation pattern.",
            },
            "data_cleaning": {
                "target_variable": "clean_rows",
                "expected_value": Decimal("4"),
                "required_function": "clean_frame",
                "required_code": "import pandas as pd",
                "focus_needle": "clean",
                "hint_primary": "Document the cleaning rule before the code.",
                "hint_secondary": "Make sure the cleaned result is deterministic.",
                "hint_ai": "Ask the assistant for a short cleaning checklist.",
            },
            "visualization": {
                "target_variable": "chart_points",
                "expected_value": Decimal("6"),
                "required_function": "prepare_chart",
                "required_code": "import matplotlib.pyplot as plt",
                "focus_needle": "chart",
                "hint_primary": "Keep the chart support code minimal and readable.",
                "hint_secondary": "Write the takeaway in one sentence.",
                "hint_ai": "Ask the assistant for a concise chart takeaway.",
            },
            "json_inputs": {
                "target_variable": "payload_count",
                "expected_value": Decimal("3"),
                "required_function": "parse_payload",
                "required_code": "import json",
                "focus_needle": "json",
                "hint_primary": "Treat JSON as structured input, not as text to eyeball.",
                "hint_secondary": "Summarize the payload before analyzing it.",
                "hint_ai": "Ask the assistant how to keep JSON parsing simple.",
            },
            "delivery_automation": {
                "target_variable": "release_ready",
                "expected_value": Decimal("1"),
                "required_function": "write_release_note",
                "required_code": "from pathlib import Path",
                "focus_needle": "delivery",
                "hint_primary": "Use a release note and a deterministic summary.",
                "hint_secondary": "The notebook should read like a handoff artifact.",
                "hint_ai": "Ask the assistant to help compress the handoff text.",
            },
        }
        return spec_map.get(
            topic_key,
            {
                "target_variable": "result_value",
                "expected_value": Decimal("1"),
                "required_function": "describe_step",
                "required_code": "",
                "focus_needle": topic_key or "lesson",
                "hint_primary": "Keep the result value explicit and easy to review.",
                "hint_secondary": "Add a brief note about the lesson topic.",
                "hint_ai": "Ask the assistant for a one-sentence summary.",
            },
        )

    def _build_programming_notebook_bundle(
        self,
        *,
        lesson_seed: LessonSeed,
        module_index: int,
        lesson_index: int,
        final_project: bool = False,
    ) -> tuple[dict, dict, tuple[dict, ...], str]:
        spec = self._topic_notebook_spec(lesson_seed.topic, final_project=final_project)
        target_variable = str(spec["target_variable"])
        expected_value = Decimal(str(spec["expected_value"]))
        required_function = str(spec["required_function"])
        required_code = str(spec["required_code"])
        focus_needle = str(spec["focus_needle"])

        code_seed = Decimal(module_index * 10 + lesson_index)
        starter_value = code_seed if not final_project else Decimal("99")

        notebook = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        f"# {lesson_seed.title}\n",
                        f"{lesson_seed.description}\n\n",
                        f"Topic: **{lesson_seed.topic}**.\n\n",
                        f"{lesson_seed.notebook_prompt}\n\n",
                        "The notebook follows the LMS lesson document: read the brief, work through the starter code, "
                        "and keep the final explanation concise enough for review.",
                    ],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        f"{required_code}\n" if required_code else "",
                        f"input_value = {starter_value}\n",
                        f"helper_scale = {Decimal('2') if not final_project else Decimal('5')}\n",
                        f"def {required_function}(value):\n",
                        "    return value\n\n",
                        f"{target_variable} = 0\n",
                    ],
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        f"Write one short explanation that uses the word `{focus_needle}`.\n\n",
                        f"{lesson_seed.reflection_prompt}",
                    ],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# TODO: replace the placeholder output with your final solution.\n",
                        f"# The grader expects `{target_variable}` to match the lesson target.\n",
                    ],
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "## Ask AI\n\n",
                        "Use the next cell to ask the AI assistant about this lesson. Edit the question if you want a different explanation.\n",
                    ],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "%%ai\n",
                        f"Question for AI: Explain the lesson topic '{lesson_seed.topic}' in one concise paragraph.\n",
                    ],
                },
            ],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        tolerance = "0.001" if expected_value != expected_value.to_integral() else "0"
        grader_config = {
            "mode": "custom_rules",
            "maxScore": "100",
            "checks": [
                {
                    "id": f"{target_variable}-value",
                    "label": f"{target_variable} value",
                    "kind": "numeric_assignment",
                    "variable": target_variable,
                    "expected": str(expected_value),
                    "tolerance": tolerance,
                    "points": "55",
                    "hintIds": [1],
                    "failureMessage": f"Set {target_variable} to the expected value for {lesson_seed.title}.",
                },
                {
                    "id": f"{required_function}-function",
                    "label": f"{required_function} function",
                    "kind": "required_function",
                    "functionName": required_function,
                    "points": "25",
                    "hintIds": [2],
                    "failureMessage": f"Define the helper function {required_function}.",
                },
                {
                    "id": f"{focus_needle}-note",
                    "label": f"{focus_needle} note",
                    "kind": "markdown_contains",
                    "needle": focus_needle,
                    "points": "20",
                    "hintIds": [3],
                    "failureMessage": f"Add a markdown explanation that explicitly references {focus_needle}.",
                },
            ],
        }
        hints = (
            {
                "title": "Primary hint",
                "bodyMarkdown": str(spec["hint_primary"]),
                "availabilityMode": "after_attempt",
                "minAttemptNumber": 1,
                "maxScorePercent": 100,
                "sortOrder": 10,
            },
            {
                "title": "Secondary hint",
                "bodyMarkdown": str(spec["hint_secondary"]),
                "availabilityMode": "after_failure",
                "minAttemptNumber": 1,
                "maxScorePercent": 100,
                "sortOrder": 20,
            },
            {
                "title": "AI helper hint",
                "bodyMarkdown": str(spec["hint_ai"]),
                "availabilityMode": "after_score_below",
                "minAttemptNumber": 1,
                "maxScorePercent": 75,
                "sortOrder": 30,
            },
        )
        body_markdown = (
            f"## {lesson_seed.title} Notebook\n"
            f"Use the notebook to practice **{lesson_seed.topic}**.\n\n"
            "- Read the lesson document first.\n"
            "- Work through the starter code and keep your explanation short.\n"
            "- Use the academy AI assistant or Jupyter AI for clarification when needed.\n"
            "- Submit the notebook back through the workspace once the checks pass."
        )
        return notebook, grader_config, hints, body_markdown

    def _ensure_pdf_asset_file(
        self,
        *,
        relative_path: str,
        title: str,
        subtitle: str,
        bullets: list[str],
    ) -> None:
        target_path = Path(settings.BASE_DIR) / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_bytes = self._build_simple_pdf_bytes(title=title, subtitle=subtitle, bullets=bullets)
        if target_path.exists() and target_path.read_bytes() == pdf_bytes:
            return
        target_path.write_bytes(pdf_bytes)

    def _build_seed_notebook_bundle(
        self,
        *,
        course: OnlineCourse,
        lesson_seed: LessonSeed,
        module_index: int,
        lesson_index: int,
        final_project: bool = False,
    ) -> tuple[dict, dict, tuple[dict, ...], str]:
        base_exposure = Decimal("1250000") + Decimal(module_index * 250000) + Decimal(lesson_index * 125000)
        volatility_buffer = Decimal("0.04") + Decimal(module_index) * Decimal("0.01") + Decimal(lesson_index) * Decimal("0.005")
        shock_multiplier = Decimal("1.12") + Decimal(module_index) * Decimal("0.03") + Decimal(lesson_index) * Decimal("0.02")
        hedge_ratio = Decimal("0.58") + Decimal(module_index) * Decimal("0.04") - Decimal(lesson_index) * Decimal("0.015")
        loss_factor = Decimal("0.28") + Decimal(lesson_index) * Decimal("0.03")
        if final_project:
            base_exposure += Decimal("450000")
            shock_multiplier += Decimal("0.06")
            loss_factor += Decimal("0.04")

        stressed_exposure = (base_exposure * (Decimal("1") + volatility_buffer) * shock_multiplier).quantize(
            Decimal("0.01")
        )
        control_buffer = (stressed_exposure * (Decimal("1") - hedge_ratio) * loss_factor).quantize(Decimal("0.01"))
        discussion_needle = lesson_seed.title.split()[0].lower() if lesson_seed.title else "risk"
        notebook_title = f"{lesson_seed.title} Notebook"
        notebook = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        f"# {lesson_seed.title}\\n",
                        f"{lesson_seed.description}\\n\\n",
                        "Use the starter variables below to compute the stressed exposure and the resulting control buffer.\\n\\n",
                        "$$\\mathrm{StressedExposure}=BaseExposure\\times(1+VolatilityBuffer)\\times ShockMultiplier$$\\n\\n",
                        "$$\\mathrm{ControlBuffer}=StressedExposure\\times(1-HedgeRatio)\\times LossFactor$$\\n\\n",
                        "If Jupyter AI is configured in the lab runtime, open the Jupyternaut chat panel or use `%%ai` magics to ask for clarification. "
                        "For graded hints and the academy AI assistant, open the linked training console from the platform.",
                    ],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        f"base_exposure = {base_exposure}\\n",
                        f"volatility_buffer = {volatility_buffer}\\n",
                        f"shock_multiplier = {shock_multiplier}\\n",
                        f"hedge_ratio = {hedge_ratio}\\n",
                        f"loss_factor = {loss_factor}\\n",
                    ],
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "Write a short note that explains which control matters most before delivery and why. "
                        f"Reference `{discussion_needle}` explicitly in your explanation.",
                    ],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# TODO: compute the stressed exposure\\n",
                        "stressed_exposure = 0\\n\\n",
                        "# TODO: compute the control buffer\\n",
                        "control_buffer = 0\\n",
                    ],
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "## Ask AI\\n\\n",
                        "Use the next cell to ask the AI assistant about this lab. Edit the question if you want a different explanation.\\n",
                    ],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "%%ai\\n",
                        f"Question for AI: Explain the strongest driver of {lesson_seed.title.lower()} and how it affects the control buffer.\\n",
                    ],
                },
            ],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        grader_config = {
            "mode": "custom_rules",
            "maxScore": "100",
            "checks": [
                {
                    "id": "stressed-exposure",
                    "label": "Stressed exposure",
                    "kind": "numeric_assignment",
                    "variable": "stressed_exposure",
                    "expected": str(stressed_exposure),
                    "tolerance": "0.5",
                    "points": "45",
                    "hintIds": [1],
                    "failureMessage": "Rebuild stressed_exposure from base_exposure, volatility_buffer, and shock_multiplier.",
                },
                {
                    "id": "control-buffer",
                    "label": "Control buffer",
                    "kind": "numeric_assignment",
                    "variable": "control_buffer",
                    "expected": str(control_buffer),
                    "tolerance": "0.5",
                    "points": "35",
                    "hintIds": [2],
                    "failureMessage": "Use stressed_exposure together with hedge_ratio and loss_factor.",
                },
                {
                    "id": "interpretation-note",
                    "label": "Interpretation note",
                    "kind": "markdown_contains",
                    "needle": discussion_needle,
                    "points": "20",
                    "hintIds": [3],
                    "failureMessage": f"Add a markdown note that explicitly references {discussion_needle}.",
                },
            ],
        }
        hints = (
            {
                "title": "Formula hint",
                "bodyMarkdown": "Compute the stressed exposure first, then derive the control buffer from that result.",
                "availabilityMode": "after_attempt",
                "minAttemptNumber": 1,
                "maxScorePercent": 100,
                "sortOrder": 10,
            },
            {
                "title": "Control buffer hint",
                "bodyMarkdown": "The hedge ratio reduces the stressed exposure before the loss factor is applied.",
                "availabilityMode": "after_failure",
                "minAttemptNumber": 1,
                "maxScorePercent": 100,
                "sortOrder": 20,
            },
            {
                "title": "AI helper hint",
                "bodyMarkdown": "Use the academy AI assistant to explain the main driver, then translate that explanation into your own markdown note.",
                "availabilityMode": "after_score_below",
                "minAttemptNumber": 1,
                "maxScorePercent": 75,
                "sortOrder": 30,
            },
        )
        body_markdown = (
            f"## {notebook_title}\n"
            f"Use the notebook to model a repeatable scenario for **{lesson_seed.title}**.\n\n"
            "- Review the attached briefing deck before you code.\n"
            "- Launch the notebook in JupyterHub for the starter environment.\n"
            "- Submit the completed `.ipynb` file back through the academy console for grading.\n"
            "- Use the academy AI assistant or Jupyter AI for guided clarification when needed."
        )
        return notebook, grader_config, hints, body_markdown

    def _sync_training_lab_profile(
        self,
        *,
        content_item: TrainingContentItem,
        course: OnlineCourse,
        lesson_seed: LessonSeed,
        module_index: int,
        lesson_index: int,
        final_project: bool = False,
    ) -> TrainingNotebookLabProfile:
        notebook_filename = f"{content_item.slug}.ipynb"
        notebook, grader_config, hints, body_markdown = self._build_programming_notebook_bundle(
            lesson_seed=lesson_seed,
            module_index=module_index,
            lesson_index=lesson_index,
            final_project=final_project,
        )
        stored_notebook = store_runtime_notebook_text(
            content_slug=content_item.slug,
            filename=notebook_filename,
            text=json.dumps(notebook, ensure_ascii=False, indent=2),
        )
        content_item.body_markdown = body_markdown
        content_item.source_url = ""
        content_item.save(update_fields=["body_markdown", "source_url", "updated_at"])

        lab_profile, _created = TrainingNotebookLabProfile.objects.update_or_create(
            content_item=content_item,
            defaults={
                "runtime_backend": TrainingNotebookLabProfile.RuntimeBackend.JUPYTERHUB,
                "grader_backend": TrainingNotebookLabProfile.GraderBackend.CUSTOM,
                "runtime_image": "",
                "notebook_path": stored_notebook.notebook_path,
                "launch_path": f"/lab/tree/{stored_notebook.notebook_path}",
                "assignment_code": content_item.slug.replace("-", "_"),
                "pass_threshold_percent": 70,
                "max_attempts": 5,
                "grader_config": grader_config,
                "allow_gpu": False,
                "allow_network": False,
                "max_session_minutes": 120 if not final_project else 180,
                "is_active": True,
            },
        )
        lab_profile.hints.all().delete()
        TrainingNotebookLabHint.objects.bulk_create(
            [
                TrainingNotebookLabHint(
                    lab_profile=lab_profile,
                    title=str(hint["title"]),
                    body_markdown=str(hint["bodyMarkdown"]),
                    availability_mode=str(hint["availabilityMode"]),
                    min_attempt_number=int(hint["minAttemptNumber"]),
                    max_score_percent=int(hint["maxScorePercent"]),
                    sort_order=int(hint["sortOrder"]),
                    is_active=True,
                )
                for hint in hints
            ]
        )
        return lab_profile

    def _ensure_module_library_assets(
        self,
        *,
        course: OnlineCourse,
        course_seed: CourseSeed,
        module_seed: ModuleSeed,
    ) -> dict[str, OnlineCourseContentLibraryItem]:
        shared_group = f"{course.slug}-week-{module_seed.week_number}"
        slug_safe = course.slug.replace("-", "_")
        pdf_prefix = f"media/online/course_library/{slug_safe}-week-{module_seed.week_number}"
        deck_path = f"{pdf_prefix}-deck.pdf"
        brief_path = f"{pdf_prefix}-brief.pdf"
        self._ensure_pdf_asset_file(
            relative_path=deck_path,
            title=module_seed.document_title,
            subtitle=module_seed.document_subtitle,
            bullets=list(module_seed.document_points),
        )
        self._ensure_pdf_asset_file(
            relative_path=brief_path,
            title=f"{module_seed.title} checklist",
            subtitle="Open course notes and notebook flow",
            bullets=[
                "Review the lesson document before opening the notebook",
                "Keep code cells compact and easy to re-run",
                "Use AI only as a helper, not as a replacement for reasoning",
            ],
        )
        intro = OnlineCourseContentLibraryItem.objects.update_or_create(
            section_type=OnlineCourseContentLibraryItem.SECTION_INTRODUCTION,
            library_group=shared_group,
            title=f"{module_seed.title} orientation",
            defaults={
                "description": module_seed.description,
                "asset_type": OnlineCourseContentLibraryItem.ASSET_DOCUMENT,
                "language": OnlineCourse.LOCALE_EN,
                "body_markdown": (
                    f"Open the lesson deck and align on scope before starting {course_seed.title_en}."
                ),
                "external_url": "",
                "is_active": True,
                "sort_order": 10,
            },
        )[0]
        self._attach_library_file(intro, deck_path)
        video = OnlineCourseContentLibraryItem.objects.update_or_create(
            section_type=OnlineCourseContentLibraryItem.SECTION_MAIN,
            library_group=shared_group,
            title=f"{module_seed.title} video",
            defaults={
                "description": "Primary lecture recording for this module.",
                "asset_type": OnlineCourseContentLibraryItem.ASSET_LINK,
                "language": OnlineCourse.LOCALE_EN,
                "body_markdown": "",
                "external_url": module_seed.video_url,
                "is_active": True,
                "sort_order": 20,
            },
        )[0]
        document = OnlineCourseContentLibraryItem.objects.update_or_create(
            section_type=OnlineCourseContentLibraryItem.SECTION_MAIN,
            library_group=shared_group,
            title=f"{module_seed.title} briefing PDF",
            defaults={
                "description": "Printable module brief with the key steps and notebook checks.",
                "asset_type": OnlineCourseContentLibraryItem.ASSET_DOCUMENT,
                "language": OnlineCourse.LOCALE_EN,
                "body_markdown": "",
                "external_url": "",
                "is_active": True,
                "sort_order": 25,
            },
        )[0]
        self._attach_library_file(document, brief_path)
        reading = OnlineCourseContentLibraryItem.objects.update_or_create(
            section_type=OnlineCourseContentLibraryItem.SECTION_MAIN,
            library_group=shared_group,
            title=f"{module_seed.title} reading pack",
            defaults={
                "description": "Reference notes and operational checklist.",
                "asset_type": OnlineCourseContentLibraryItem.ASSET_TEXT,
                "language": OnlineCourse.LOCALE_EN,
                "body_markdown": (
                    "## Reading focus\n"
                    f"- {module_seed.document_points[0]}\n"
                    f"- {module_seed.document_points[1]}\n"
                    f"- {module_seed.document_points[2]}"
                ),
                "external_url": "",
                "is_active": True,
                "sort_order": 30,
            },
        )[0]
        conclusion = OnlineCourseContentLibraryItem.objects.update_or_create(
            section_type=OnlineCourseContentLibraryItem.SECTION_CONCLUSION,
            library_group=shared_group,
            title=f"{module_seed.title} wrap-up",
            defaults={
                "description": "Recap and next-step checklist.",
                "asset_type": OnlineCourseContentLibraryItem.ASSET_TEXT,
                "language": OnlineCourse.LOCALE_EN,
                "body_markdown": "Summarize results and prepare for the next lesson.",
                "external_url": "",
                "is_active": True,
                "sort_order": 40,
            },
        )[0]
        return {
            "intro": intro,
            "video": video,
            "document": document,
            "reading": reading,
            "conclusion": conclusion,
        }

    def _ensure_shared_library_assets(self) -> dict[str, OnlineCourseContentLibraryItem]:
        self._ensure_pdf_asset_file(
            relative_path="media/online/course_library/lesson-orientation-deck.pdf",
            title="Lesson overview deck",
            subtitle="Internal academy orientation and learning objectives",
            bullets=[
                "Purpose of the lesson and expected outcomes",
                "Required prerequisite knowledge and formulas",
                "Live-session checkpoints and homework transition",
            ],
        )
        self._ensure_pdf_asset_file(
            relative_path="media/online/course_library/market-overview.pdf",
            title="Lesson briefing PDF",
            subtitle="Printable summary for formulas, assumptions, and review notes",
            bullets=[
                "Key pricing or risk assumptions",
                "Critical controls and validation checks",
                "Notebook submission expectations and escalation path",
            ],
        )
        shared_group = "coursera-demo-shared"
        intro = OnlineCourseContentLibraryItem.objects.update_or_create(
            section_type=OnlineCourseContentLibraryItem.SECTION_INTRODUCTION,
            library_group=shared_group,
            title="Lesson orientation",
            defaults={
                "description": "Overview deck with lesson context, outcomes, and prerequisites.",
                "asset_type": OnlineCourseContentLibraryItem.ASSET_DOCUMENT,
                "language": OnlineCourse.LOCALE_EN,
                "body_markdown": "Open the overview deck and align on scope before starting the lesson.",
                "external_url": "",
                "is_active": True,
                "sort_order": 10,
            },
        )[0]
        self._attach_library_file(intro, "media/online/course_library/lesson-orientation-deck.pdf")
        video = OnlineCourseContentLibraryItem.objects.update_or_create(
            section_type=OnlineCourseContentLibraryItem.SECTION_MAIN,
            library_group=shared_group,
            title="Video briefing",
            defaults={
                "description": "Primary lecture recording for this lesson.",
                "asset_type": OnlineCourseContentLibraryItem.ASSET_LINK,
                "language": OnlineCourse.LOCALE_EN,
                "body_markdown": "",
                "external_url": "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
                "is_active": True,
                "sort_order": 20,
            },
        )[0]
        document = OnlineCourseContentLibraryItem.objects.update_or_create(
            section_type=OnlineCourseContentLibraryItem.SECTION_MAIN,
            library_group=shared_group,
            title="Lesson briefing PDF",
            defaults={
                "description": "Printable PDF brief with formulas, assumptions, and delivery notes.",
                "asset_type": OnlineCourseContentLibraryItem.ASSET_DOCUMENT,
                "language": OnlineCourse.LOCALE_EN,
                "body_markdown": "",
                "external_url": "",
                "is_active": True,
                "sort_order": 25,
            },
        )[0]
        self._attach_library_file(document, "media/online/course_library/market-overview.pdf")
        reading = OnlineCourseContentLibraryItem.objects.update_or_create(
            section_type=OnlineCourseContentLibraryItem.SECTION_MAIN,
            library_group=shared_group,
            title="Reading pack",
            defaults={
                "description": "Reference notes and operational checklist.",
                "asset_type": OnlineCourseContentLibraryItem.ASSET_TEXT,
                "language": OnlineCourse.LOCALE_EN,
                "body_markdown": (
                    "## Reading focus\n"
                    "- Capture the pricing assumptions.\n"
                    "- Note the model inputs and control points.\n"
                    "- Prepare one clarification question for the live session."
                ),
                "external_url": "",
                "is_active": True,
                "sort_order": 30,
            },
        )[0]
        conclusion = OnlineCourseContentLibraryItem.objects.update_or_create(
            section_type=OnlineCourseContentLibraryItem.SECTION_CONCLUSION,
            library_group=shared_group,
            title="Lesson wrap-up",
            defaults={
                "description": "Recap and next-step checklist.",
                "asset_type": OnlineCourseContentLibraryItem.ASSET_TEXT,
                "language": OnlineCourse.LOCALE_EN,
                "body_markdown": "Summarize results and prepare for the next lesson.",
                "external_url": "",
                "is_active": True,
                "sort_order": 40,
            },
        )[0]
        return {
            "intro": intro,
            "video": video,
            "document": document,
            "reading": reading,
            "conclusion": conclusion,
        }

    def _build_programming_modules_payload(
        self,
        *,
        course: OnlineCourse,
        course_seed: CourseSeed,
        course_start: datetime,
    ) -> list[dict]:
        modules_payload: list[dict] = []

        for module_index, module_seed in enumerate(course_seed.modules, start=1):
            shared_library = self._ensure_module_library_assets(
                course=course,
                course_seed=course_seed,
                module_seed=module_seed,
            )
            module_start = course_start + timedelta(weeks=(module_index - 1) * 2)
            module_end = module_start + timedelta(days=13)
            lessons_payload: list[dict] = []
            for lesson_index, lesson_seed in enumerate(module_seed.lessons, start=1):
                lesson_start = module_start + timedelta(days=(lesson_index - 1) * 7)
                lesson_end = lesson_start + timedelta(hours=2)
                notebook_content = self._upsert_programming_notebook_content(
                    course=course,
                    course_seed=course_seed,
                    module_seed=module_seed,
                    lesson_seed=lesson_seed,
                    module_index=module_index,
                    lesson_index=lesson_index,
                )
                notebook_library_item = sync_course_library_for_notebook_content(content_item=notebook_content)
                lessons_payload.append(
                    self._build_programming_lesson_payload(
                        course_seed=course_seed,
                        module_seed=module_seed,
                        lesson_seed=lesson_seed,
                        shared_library=shared_library,
                        notebook_library_item=notebook_library_item,
                        module_index=module_index,
                        lesson_index=lesson_index,
                        lesson_start=lesson_start,
                        lesson_end=lesson_end,
                    )
                )

            modules_payload.append(
                {
                    "title": module_seed.title,
                    "description": module_seed.description,
                    "moduleType": "module",
                    "weekNumber": module_seed.week_number,
                    "startsAt": module_start,
                    "endsAt": module_end,
                    "sortOrder": module_seed.week_number * 10,
                    "isActive": True,
                    "lessons": lessons_payload,
                }
            )

        final_content = self._upsert_programming_final_notebook_content(course=course, course_seed=course_seed)
        final_library_item = sync_course_library_for_notebook_content(content_item=final_content)
        final_module_start = course_start + timedelta(weeks=len(course_seed.modules) * 2)
        final_module_end = final_module_start + timedelta(days=6)
        modules_payload.append(
            {
                "title": course_seed.final_title,
                "description": course_seed.final_description,
                "moduleType": "final_assessment",
                "weekNumber": None,
                "startsAt": final_module_start,
                "endsAt": final_module_end,
                "sortOrder": 999,
                "isActive": True,
                "lessons": [
                    {
                        "title": course_seed.final_title,
                        "description": course_seed.final_description,
                        "sortOrder": 1,
                        "startsAt": final_module_start,
                        "endsAt": final_module_start + timedelta(hours=3),
                        "isActive": True,
                        "sections": [
                            {
                                "sectionType": "introduction",
                                "title": "Introduction",
                                "description": "Final scope and acceptance criteria.",
                                "sortOrder": 10,
                                "isActive": True,
                                "items": [
                                    {
                                        "sourceLibraryItem": shared_library["intro"].id,
                                        "title": "Final scope",
                                        "description": "Objectives, timeline, and expected deliverables.",
                                        "assetType": "text",
                                        "activityType": "text",
                                        "language": "en",
                                        "bodyMarkdown": course_seed.final_instruction,
                                        "externalUrl": "",
                                        "sortOrder": 1,
                                        "isActive": True,
                                    }
                                ],
                            },
                            {
                                "sectionType": "main",
                                "title": "Main content",
                                "description": "Final assignment package.",
                                "sortOrder": 20,
                                "isActive": True,
                                "items": [
                                    {
                                        "sourceLibraryItem": final_library_item.id if final_library_item else None,
                                        "title": "Capstone notebook",
                                        "description": "Complete and submit the capstone notebook.",
                                        "assetType": "notebook",
                                        "activityType": "assignment",
                                        "language": "en",
                                        "bodyMarkdown": "",
                                        "externalUrl": final_content.source_url or "",
                                        "linkedTrainingContentId": final_content.id,
                                        "sortOrder": 1,
                                        "isActive": True,
                                    },
                                    {
                                        "title": "Final quiz",
                                        "description": "Knowledge check before project sign-off.",
                                        "assetType": "text",
                                        "activityType": "quiz",
                                        "language": "en",
                                        "bodyMarkdown": (
                                            "- Explain the main concept from the final project.\n"
                                            "- Name one repeatable improvement you added.\n"
                                            "- Describe how you would hand the notebook to another reviewer."
                                        ),
                                        "externalUrl": "",
                                        "sortOrder": 2,
                                        "isActive": True,
                                    },
                                ],
                            },
                            {
                                "sectionType": "conclusion",
                                "title": "Conclusion",
                                "description": "Submission checklist and handover instructions.",
                                "sortOrder": 30,
                                "isActive": True,
                                "items": [
                                    {
                                        "sourceLibraryItem": shared_library["conclusion"].id,
                                        "title": "Submission checklist",
                                        "description": "Attach notebook output and reviewer notes.",
                                        "assetType": "text",
                                        "activityType": "text",
                                        "language": "en",
                                        "bodyMarkdown": course_seed.final_instruction,
                                        "externalUrl": "",
                                        "sortOrder": 1,
                                        "isActive": True,
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        )
        return modules_payload

    def _build_programming_lesson_payload(
        self,
        *,
        course_seed: CourseSeed,
        module_seed: ModuleSeed,
        lesson_seed: LessonSeed,
        shared_library: dict[str, OnlineCourseContentLibraryItem],
        notebook_library_item: OnlineCourseContentLibraryItem | None,
        module_index: int,
        lesson_index: int,
        lesson_start: datetime,
        lesson_end: datetime,
    ) -> dict:
        overview_markdown = self._build_programming_lesson_overview_markdown(
            course_seed=course_seed,
            module_seed=module_seed,
            lesson_seed=lesson_seed,
            module_index=module_index,
            lesson_index=lesson_index,
        )
        briefing_markdown = self._build_programming_lesson_briefing_markdown(
            course_seed=course_seed,
            module_seed=module_seed,
            lesson_seed=lesson_seed,
            module_index=module_index,
            lesson_index=lesson_index,
        )
        reading_markdown = self._build_programming_lesson_reading_markdown(
            course_seed=course_seed,
            module_seed=module_seed,
            lesson_seed=lesson_seed,
            module_index=module_index,
            lesson_index=lesson_index,
        )
        quiz_markdown = self._build_programming_lesson_quiz_markdown(
            course_seed=course_seed,
            module_seed=module_seed,
            lesson_seed=lesson_seed,
            module_index=module_index,
            lesson_index=lesson_index,
        )
        conclusion_markdown = self._build_programming_lesson_conclusion_markdown(
            course_seed=course_seed,
            module_seed=module_seed,
            lesson_seed=lesson_seed,
            module_index=module_index,
            lesson_index=lesson_index,
        )
        return {
            "title": lesson_seed.title,
            "description": lesson_seed.description,
            "startsAt": lesson_start,
            "endsAt": lesson_end,
            "sortOrder": lesson_index,
            "isActive": True,
            "sections": [
                {
                    "sectionType": "introduction",
                    "title": "Introduction",
                    "description": "Orientation and expected outcomes.",
                    "sortOrder": 10,
                    "isActive": True,
                    "items": [
                        {
                            "sourceLibraryItem": shared_library["intro"].id,
                            "title": f"{lesson_seed.title} - Overview",
                            "description": "Presentation deck with context, prerequisites, and delivery notes.",
                            "assetType": "document",
                            "activityType": "text",
                            "language": "en",
                            "bodyMarkdown": overview_markdown,
                            "externalUrl": "",
                            "sortOrder": 1,
                            "isActive": True,
                        }
                    ],
                },
                {
                    "sectionType": "main",
                    "title": "Main content",
                    "description": "Video, reading, quiz, and assignment.",
                    "sortOrder": 20,
                    "isActive": True,
                    "items": [
                        {
                            "sourceLibraryItem": shared_library["video"].id,
                            "title": f"{lesson_seed.title} - Video",
                            "description": "Core lecture recording.",
                            "assetType": "link",
                            "activityType": "video",
                            "language": "en",
                            "bodyMarkdown": "",
                            "externalUrl": shared_library["video"].external_url,
                            "sortOrder": 1,
                            "isActive": True,
                        },
                        {
                            "sourceLibraryItem": shared_library["document"].id,
                            "title": f"{lesson_seed.title} - Briefing PDF",
                            "description": "Printable PDF with lesson notes and delivery points.",
                            "assetType": "document",
                            "activityType": "text",
                            "language": "en",
                            "bodyMarkdown": briefing_markdown,
                            "externalUrl": "",
                            "sortOrder": 2,
                            "isActive": True,
                        },
                        {
                            "sourceLibraryItem": shared_library["reading"].id,
                            "title": f"{lesson_seed.title} - Reading",
                            "description": "Reference notes and formulas.",
                            "assetType": "text",
                            "activityType": "text",
                            "language": "en",
                            "bodyMarkdown": reading_markdown,
                            "externalUrl": "",
                            "sortOrder": 3,
                            "isActive": True,
                        },
                        {
                            "title": f"{lesson_seed.title} - Quiz",
                            "description": "Short comprehension checkpoint.",
                            "assetType": "text",
                            "activityType": "quiz",
                            "language": "en",
                            "bodyMarkdown": quiz_markdown,
                            "externalUrl": "",
                            "sortOrder": 4,
                            "isActive": True,
                        },
                        {
                            "sourceLibraryItem": notebook_library_item.id if notebook_library_item else None,
                            "title": f"{lesson_seed.title} - Notebook Assignment",
                            "description": "Hands-on task in Jupyter Notebook.",
                            "assetType": "notebook",
                            "activityType": "assignment",
                            "language": "en",
                            "bodyMarkdown": "",
                            "externalUrl": notebook_library_item.external_url if notebook_library_item else "",
                            "linkedTrainingContentId": notebook_library_item.training_content_id if notebook_library_item else None,
                            "sortOrder": 5,
                            "isActive": True,
                        },
                    ],
                },
                {
                    "sectionType": "conclusion",
                    "title": "Conclusion",
                    "description": "Summary and follow-up.",
                    "sortOrder": 30,
                    "isActive": True,
                    "items": [
                        {
                            "sourceLibraryItem": shared_library["conclusion"].id,
                            "title": f"{lesson_seed.title} - Conclusion",
                            "description": "Recap and next-step actions.",
                            "assetType": "text",
                            "activityType": "text",
                            "language": "en",
                            "bodyMarkdown": conclusion_markdown,
                            "externalUrl": "",
                            "sortOrder": 1,
                            "isActive": True,
                        }
                    ],
                },
            ],
        }

    def _is_python_intro_lesson(
        self,
        *,
        course_seed: CourseSeed,
        module_index: int,
        lesson_index: int,
    ) -> bool:
        return course_seed.slug == "python-core-fundamentals" and module_index == 1 and lesson_index == 1

    def _build_programming_lesson_overview_markdown(
        self,
        *,
        course_seed: CourseSeed,
        module_seed: ModuleSeed,
        lesson_seed: LessonSeed,
        module_index: int,
        lesson_index: int,
    ) -> str:
        if self._is_python_intro_lesson(course_seed=course_seed, module_index=module_index, lesson_index=lesson_index):
            return (
                "## Why this lesson matters\n"
                "Before a learner writes business logic, the execution environment must be visible, stable, and easy to reproduce. "
                "The first lesson therefore focuses on the Python interpreter, the Jupyter kernel, and the basic workflow that makes a notebook review-ready.\n\n"
                "## Lesson storyline\n"
                "- Step 1. Confirm which Python interpreter is actually running.\n"
                "- Step 2. Check that the notebook kernel is attached to the expected environment.\n"
                "- Step 3. Run a minimal code cell and keep the output visible for audit.\n"
                "- Step 4. Add one markdown explanation so another reviewer understands what was verified.\n\n"
                "## Core vocabulary\n"
                "- **Interpreter**: the Python program that reads and executes your code.\n"
                "- **Runtime**: the active execution context, including the interpreter and loaded state.\n"
                "- **Kernel**: the notebook-side execution engine connected to your cells.\n"
                "- **Notebook**: the working document that combines code, output, and explanation.\n\n"
                "## Practical checks to perform\n"
                "- Run `python --version` or inspect `sys.version` to confirm the version.\n"
                "- Make sure the selected kernel matches the lesson environment.\n"
                "- Execute one short cell from a clean state and observe the output.\n"
                "- Restart and rerun the notebook once to prove the flow is reproducible.\n\n"
                "## Suggested live talking points\n"
                "- Why a hidden environment mismatch produces unreliable results.\n"
                "- Why markdown notes matter in addition to code output.\n"
                "- Why a reviewer should be able to rerun the notebook without extra explanation.\n\n"
                "## Source anchors\n"
                "- Python Tutorial: Using the Python Interpreter.\n"
                "- Python Tutorial: An Informal Introduction to Python.\n"
                "- Jupyter workflow: select kernel, run cells, restart and rerun."
            )

        return (
            f"## {lesson_seed.title}\n"
            f"{lesson_seed.description}\n\n"
            "Open the attached deck for a structured walk-through before the live session."
        )

    def _build_programming_lesson_briefing_markdown(
        self,
        *,
        course_seed: CourseSeed,
        module_seed: ModuleSeed,
        lesson_seed: LessonSeed,
        module_index: int,
        lesson_index: int,
    ) -> str:
        if self._is_python_intro_lesson(course_seed=course_seed, module_index=module_index, lesson_index=lesson_index):
            return (
                "## Setup checklist\n"
                "- Confirm that Python is installed and the version is visible.\n"
                "- Open the notebook with the correct kernel selected.\n"
                "- Keep one markdown note that explains what you verified.\n\n"
                "## Core commands\n"
                "```python\n"
                "import sys\n"
                "runtime_label = f\"python-{sys.version_info.major}.{sys.version_info.minor}\"\n"
                "sys.version\n"
                "runtime_label\n"
                "```\n\n"
                "## What the reviewer expects\n"
                "- The runtime is named clearly.\n"
                "- The first code output is visible and reproducible.\n"
                "- The explanation is short, specific, and easy to audit."
            )

        return (
            "## Briefing PDF\n"
            f"- Review the key delivery points for {lesson_seed.title.lower()}.\n"
            "- Keep the notebook structure clean before you submit.\n"
            "- Use the PDF as the short lesson checklist."
        )

    def _build_programming_lesson_reading_markdown(
        self,
        *,
        course_seed: CourseSeed,
        module_seed: ModuleSeed,
        lesson_seed: LessonSeed,
        module_index: int,
        lesson_index: int,
    ) -> str:
        if self._is_python_intro_lesson(course_seed=course_seed, module_index=module_index, lesson_index=lesson_index):
            return (
                "## Reading focus\n"
                "- The interpreter executes Python code and reports syntax or runtime errors immediately.\n"
                "- In Jupyter, the kernel is the execution engine attached to the notebook interface.\n"
                "- Reproducibility means the notebook can be restarted and run again with the same outcome.\n\n"
                "## Review lens\n"
                "- A strong first notebook shows both code and a short explanation.\n"
                "- The reviewer should understand which environment was used.\n"
                "- The output should still make sense after restart and rerun.\n\n"
                "## Practical reminders\n"
                "- Prefer short code cells with one clear purpose.\n"
                "- Name variables so another reviewer understands the business meaning.\n"
                "- Add one markdown note that explains why the notebook output is trustworthy."
            )

        return (
            f"## {lesson_seed.title}\n"
            f"- {lesson_seed.reading_points[0]}\n"
            f"- {lesson_seed.reading_points[1]}\n"
            f"- {lesson_seed.reading_points[2]}"
        )

    def _build_programming_lesson_quiz_markdown(
        self,
        *,
        course_seed: CourseSeed,
        module_seed: ModuleSeed,
        lesson_seed: LessonSeed,
        module_index: int,
        lesson_index: int,
    ) -> str:
        if self._is_python_intro_lesson(course_seed=course_seed, module_index=module_index, lesson_index=lesson_index):
            return (
                "## Knowledge check\n\n"
                "### Question 1\n"
                "Which command confirms the installed Python version before you start the notebook?\n"
                "- A. python --version\n"
                "- B. pip freeze\n"
                "- C. jupyter nbconvert\n\n"
                "Correct answer: A. It validates the interpreter version directly.\n\n"
                "### Question 2\n"
                "What is the notebook kernel responsible for?\n"
                "- A. Styling markdown cells\n"
                "- B. Executing code cells in the selected environment\n"
                "- C. Exporting the notebook to PDF\n\n"
                "Correct answer: B. The kernel is the execution engine behind the notebook.\n\n"
                "### Question 3\n"
                "Which habit improves reproducibility before submission?\n"
                "- A. Keep old outputs without rerunning\n"
                "- B. Restart, run all cells, and keep a short markdown summary\n"
                "- C. Rename variables differently in each cell\n\n"
                "Correct answer: B. A clean rerun proves the lesson works end to end.\n\n"
                "## Short reflection\n"
                "- In one sentence, explain why the runtime must be visible before review.\n"
                "- In one sentence, explain the difference between a notebook and a kernel."
            )

        return (
            "## Knowledge check\n"
            f"- {lesson_seed.quiz_points[0]}\n"
            f"- {lesson_seed.quiz_points[1]}\n"
            f"- {lesson_seed.quiz_points[2]}"
        )

    def _build_programming_lesson_conclusion_markdown(
        self,
        *,
        course_seed: CourseSeed,
        module_seed: ModuleSeed,
        lesson_seed: LessonSeed,
        module_index: int,
        lesson_index: int,
    ) -> str:
        if self._is_python_intro_lesson(course_seed=course_seed, module_index=module_index, lesson_index=lesson_index):
            return (
                "## Wrap-up\n"
                "- Confirm the runtime note is written in your own words.\n"
                "- Make sure the notebook can be restarted and rerun without hidden steps.\n"
                "- Prepare one short question for the live session if any part of the environment setup is still unclear."
            )

        return "Summarize outcomes and prepare next lesson."

    def _build_modules_payload(
        self,
        *,
        course: OnlineCourse,
        course_seed: CourseSeed,
        shared_library: dict[str, OnlineCourseContentLibraryItem],
    ) -> list[dict]:
        modules_payload: list[dict] = []

        for module_index, module_seed in enumerate(course_seed.modules, start=1):
            lessons_payload: list[dict] = []
            for lesson_index, lesson_seed in enumerate(module_seed.lessons, start=1):
                notebook_content = self._upsert_notebook_content(
                    course=course,
                    module_index=module_index,
                    lesson_index=lesson_index,
                    lesson_seed=lesson_seed,
                )
                notebook_library_item = sync_course_library_for_notebook_content(content_item=notebook_content)
                lessons_payload.append(
                    self._build_lesson_payload(
                        lesson_seed=lesson_seed,
                        shared_library=shared_library,
                        notebook_library_item=notebook_library_item,
                        module_index=module_index,
                        lesson_index=lesson_index,
                    )
                )

            modules_payload.append(
                {
                    "title": module_seed.title,
                    "description": module_seed.description,
                    "moduleType": "module",
                    "weekNumber": module_seed.week_number,
                    "sortOrder": module_seed.week_number * 10,
                    "isActive": True,
                    "lessons": lessons_payload,
                }
            )

        final_content = self._upsert_final_notebook_content(course=course)
        final_library_item = sync_course_library_for_notebook_content(content_item=final_content)
        modules_payload.append(
            {
                "title": "Final Project / Exam",
                "description": "Capstone validation and final assessment package.",
                "moduleType": "final_assessment",
                "weekNumber": None,
                "sortOrder": 999,
                "isActive": True,
                "lessons": [
                    {
                        "title": "Final Project / Exam",
                        "description": "Complete the final project and submit result evidence.",
                        "sortOrder": 1,
                        "isActive": True,
                        "sections": [
                            {
                                "sectionType": "introduction",
                                "title": "Introduction",
                                "description": "Final scope and acceptance criteria.",
                                "sortOrder": 10,
                                "isActive": True,
                                "items": [
                                    {
                                        "sourceLibraryItem": shared_library["intro"].id,
                                        "title": "Final scope",
                                        "description": "Objectives, timeline, and expected deliverables.",
                                        "assetType": "text",
                                        "activityType": "text",
                                        "language": "en",
                                        "bodyMarkdown": "Review scope and constraints before submission.",
                                        "externalUrl": "",
                                        "sortOrder": 1,
                                        "isActive": True,
                                    }
                                ],
                            },
                            {
                                "sectionType": "main",
                                "title": "Main content",
                                "description": "Final assignment package.",
                                "sortOrder": 20,
                                "isActive": True,
                                "items": [
                                    {
                                        "sourceLibraryItem": final_library_item.id if final_library_item else None,
                                        "title": "Capstone notebook",
                                        "description": "Complete and submit the capstone notebook.",
                                        "assetType": "notebook",
                                        "activityType": "assignment",
                                        "language": "en",
                                        "bodyMarkdown": "",
                                        "externalUrl": final_content.source_url or "",
                                        "linkedTrainingContentId": final_content.id,
                                        "sortOrder": 1,
                                        "isActive": True,
                                    },
                                    {
                                        "title": "Final quiz",
                                        "description": "Knowledge check before project sign-off.",
                                        "assetType": "text",
                                        "activityType": "quiz",
                                        "language": "en",
                                        "bodyMarkdown": "- Explain the primary risk control in your solution.",
                                        "externalUrl": "",
                                        "sortOrder": 2,
                                        "isActive": True,
                                    },
                                ],
                            },
                            {
                                "sectionType": "conclusion",
                                "title": "Conclusion",
                                "description": "Submission checklist and handover instructions.",
                                "sortOrder": 30,
                                "isActive": True,
                                "items": [
                                    {
                                        "sourceLibraryItem": shared_library["conclusion"].id,
                                        "title": "Submission checklist",
                                        "description": "Attach notebook output and reviewer notes.",
                                        "assetType": "text",
                                        "activityType": "text",
                                        "language": "en",
                                        "bodyMarkdown": "Confirm all criteria and submit evidence.",
                                        "externalUrl": "",
                                        "sortOrder": 1,
                                        "isActive": True,
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        )
        return modules_payload

    def _build_lesson_payload(
        self,
        *,
        lesson_seed: LessonSeed,
        shared_library: dict[str, OnlineCourseContentLibraryItem],
        notebook_library_item: OnlineCourseContentLibraryItem | None,
        module_index: int,
        lesson_index: int,
    ) -> dict:
        return {
            "title": lesson_seed.title,
            "description": lesson_seed.description,
            "sortOrder": lesson_index,
            "isActive": True,
            "sections": [
                {
                    "sectionType": "introduction",
                    "title": "Introduction",
                    "description": "Orientation and expected outcomes.",
                    "sortOrder": 10,
                    "isActive": True,
                    "items": [
                        {
                            "sourceLibraryItem": shared_library["intro"].id,
                            "title": f"{lesson_seed.title} - Overview",
                            "description": "Presentation deck with context, prerequisites, and delivery notes.",
                            "assetType": "document",
                            "activityType": "text",
                            "language": "en",
                            "bodyMarkdown": (
                                f"## {lesson_seed.title}\n"
                                f"{lesson_seed.description}\n\n"
                                "Open the attached deck for a structured walk-through before the live session."
                            ),
                            "externalUrl": "",
                            "sortOrder": 1,
                            "isActive": True,
                        }
                    ],
                },
                {
                    "sectionType": "main",
                    "title": "Main content",
                    "description": "Video, reading, quiz, and assignment.",
                    "sortOrder": 20,
                    "isActive": True,
                    "items": [
                        {
                            "sourceLibraryItem": shared_library["video"].id,
                            "title": f"{lesson_seed.title} - Video",
                            "description": "Core lecture recording.",
                            "assetType": "link",
                            "activityType": "video",
                            "language": "en",
                            "bodyMarkdown": "",
                            "externalUrl": shared_library["video"].external_url,
                            "sortOrder": 1,
                            "isActive": True,
                        },
                        {
                            "sourceLibraryItem": shared_library["document"].id,
                            "title": f"{lesson_seed.title} - Briefing PDF",
                            "description": "Printable PDF with formulas, reference tables, and delivery notes.",
                            "assetType": "document",
                            "activityType": "text",
                            "language": "en",
                            "bodyMarkdown": "",
                            "externalUrl": "",
                            "sortOrder": 2,
                            "isActive": True,
                        },
                        {
                            "sourceLibraryItem": shared_library["reading"].id,
                            "title": f"{lesson_seed.title} - Reading",
                            "description": "Reference notes and formulas.",
                            "assetType": "text",
                            "activityType": "text",
                            "language": "en",
                            "bodyMarkdown": (
                                f"## {lesson_seed.title}\n"
                                f"- Review the core definition for {lesson_seed.title.lower()}.\n"
                                "- Identify the main risk driver.\n"
                                "- Compare the worked example with the PDF briefing."
                            ),
                            "externalUrl": "",
                            "sortOrder": 3,
                            "isActive": True,
                        },
                        {
                            "title": f"{lesson_seed.title} - Quiz",
                            "description": "Short comprehension checkpoint.",
                            "assetType": "text",
                            "activityType": "quiz",
                            "language": "en",
                            "bodyMarkdown": (
                                f"## Knowledge check\n"
                                f"- What is the key objective of {lesson_seed.title}?\n"
                                "- Which assumption has the largest impact on the result?\n"
                                "- Which control should be reviewed before delivery?"
                            ),
                            "externalUrl": "",
                            "sortOrder": 4,
                            "isActive": True,
                        },
                        {
                            "sourceLibraryItem": notebook_library_item.id if notebook_library_item else None,
                            "title": f"{lesson_seed.title} - Notebook Assignment",
                            "description": "Hands-on task in Jupyter Notebook.",
                            "assetType": "notebook",
                            "activityType": "assignment",
                            "language": "en",
                            "bodyMarkdown": "",
                            "externalUrl": notebook_library_item.external_url if notebook_library_item else "",
                            "linkedTrainingContentId": notebook_library_item.training_content_id if notebook_library_item else None,
                            "sortOrder": 5,
                            "isActive": True,
                        },
                    ],
                },
                {
                    "sectionType": "conclusion",
                    "title": "Conclusion",
                    "description": "Summary and follow-up.",
                    "sortOrder": 30,
                    "isActive": True,
                    "items": [
                        {
                            "sourceLibraryItem": shared_library["conclusion"].id,
                            "title": f"{lesson_seed.title} - Conclusion",
                            "description": "Recap and next-step actions.",
                            "assetType": "text",
                            "activityType": "text",
                            "language": "en",
                            "bodyMarkdown": "Summarize outcomes and prepare next lesson.",
                            "externalUrl": "",
                            "sortOrder": 1,
                            "isActive": True,
                        }
                    ],
                },
            ],
        }

    def _upsert_programming_notebook_content(
        self,
        *,
        course: OnlineCourse,
        course_seed: CourseSeed,
        module_seed: ModuleSeed,
        lesson_seed: LessonSeed,
        module_index: int,
        lesson_index: int,
    ) -> TrainingContentItem:
        slug = f"{course.slug}-m{module_index}-l{lesson_index}-notebook"
        content = TrainingContentItem.objects.update_or_create(
            slug=slug,
            defaults={
                "name": f"{lesson_seed.title} Notebook",
                "description": f"Notebook assignment for {lesson_seed.title}.",
                "body_markdown": (
                    f"Implement the practical task for {lesson_seed.title} in {course_seed.title_en}.\n\n"
                    f"Module focus: {module_seed.description}"
                ),
                "content_kind": TrainingContentItem.ContentKind.NOTEBOOK,
                "status": TrainingContentItem.Status.PUBLISHED,
                "access_scope": TrainingContentItem.AccessScope.AUTHENTICATED,
                "difficulty": TrainingContentItem.Difficulty.INTERMEDIATE,
                "course": course,
                "source_url": "",
                "estimated_minutes": 35,
                "is_repeatable_on_demand": True,
                "supports_inline_lab": True,
                "published_at": timezone.now(),
            },
        )[0]
        self._sync_training_lab_profile(
            content_item=content,
            course=course,
            lesson_seed=lesson_seed,
            module_index=module_index,
            lesson_index=lesson_index,
        )
        return content

    def _upsert_programming_final_notebook_content(
        self,
        *,
        course: OnlineCourse,
        course_seed: CourseSeed,
    ) -> TrainingContentItem:
        slug = f"{course.slug}-final-project"
        final_lesson_seed = LessonSeed(
            title=course_seed.final_title,
            description=course_seed.final_description,
            topic="final_project",
            notebook_prompt=course_seed.final_instruction,
            reflection_prompt="Write a short handoff note that explains the final result and one improvement path.",
            quiz_points=(
                "The final scope is clear",
                "The notebook is self-contained",
                "The handoff note is readable",
            ),
            reading_points=(
                "Document the result for the next reviewer",
                "Summarize the main workflow before submission",
                "Keep the final artifact easy to rerun",
            ),
        )
        content = TrainingContentItem.objects.update_or_create(
            slug=slug,
            defaults={
                "name": f"{course.title_en} Final Project",
                "description": course_seed.final_description,
                "body_markdown": course_seed.final_instruction,
                "content_kind": TrainingContentItem.ContentKind.NOTEBOOK,
                "status": TrainingContentItem.Status.PUBLISHED,
                "access_scope": TrainingContentItem.AccessScope.AUTHENTICATED,
                "difficulty": TrainingContentItem.Difficulty.ADVANCED,
                "course": course,
                "source_url": "",
                "estimated_minutes": 90,
                "is_repeatable_on_demand": True,
                "supports_inline_lab": True,
                "published_at": timezone.now(),
            },
        )[0]
        self._sync_training_lab_profile(
            content_item=content,
            course=course,
            lesson_seed=final_lesson_seed,
            module_index=99,
            lesson_index=1,
            final_project=True,
        )
        return content

    def _upsert_programming_materials(self, course: OnlineCourse) -> None:
        OnlineCourseMaterial.objects.update_or_create(
            course=course,
            title="Programming handbook",
            language=OnlineCourse.LOCALE_EN,
            material_type=OnlineCourseMaterial.MATERIAL_RESOURCE,
            defaults={
                "description": "Course roadmap, weekly workflow, and notebook review checklist.",
                "link_url": "https://docs.python.org/3/tutorial/",
                "sort_order": 10,
                "is_active": True,
            },
        )
        OnlineCourseMaterial.objects.update_or_create(
            course=course,
            title="Notebook delivery policy",
            language=OnlineCourse.LOCALE_EN,
            material_type=OnlineCourseMaterial.MATERIAL_CONDITION,
            defaults={
                "description": "Delivery rules, attendance policy, and escalation route.",
                "link_url": "",
                "sort_order": 20,
                "is_active": True,
            },
        )
        OnlineCourseMaterial.objects.update_or_create(
            course=course,
            title="Reference docs and tooling",
            language=OnlineCourse.LOCALE_EN,
            material_type=OnlineCourseMaterial.MATERIAL_RESOURCE,
            defaults={
                "description": "Official docs for Python, NumPy, and pandas references.",
                "link_url": "https://docs.python.org/3/tutorial/",
                "sort_order": 30,
                "is_active": True,
            },
        )

    def _upsert_notebook_content(
        self,
        *,
        course: OnlineCourse,
        module_index: int,
        lesson_index: int,
        lesson_seed: LessonSeed,
    ) -> TrainingContentItem:
        slug = f"{course.slug}-m{module_index}-l{lesson_index}-notebook"
        content = TrainingContentItem.objects.update_or_create(
            slug=slug,
            defaults={
                "name": f"{lesson_seed.title} Notebook",
                "description": f"Notebook assignment for {lesson_seed.title}.",
                "body_markdown": f"Implement the practical task for {lesson_seed.title}.",
                "content_kind": TrainingContentItem.ContentKind.NOTEBOOK,
                "status": TrainingContentItem.Status.PUBLISHED,
                "access_scope": TrainingContentItem.AccessScope.AUTHENTICATED,
                "difficulty": TrainingContentItem.Difficulty.INTERMEDIATE,
                "course": course,
                "source_url": "",
                "estimated_minutes": 35,
                "is_repeatable_on_demand": True,
                "supports_inline_lab": True,
                "published_at": timezone.now(),
            },
        )[0]
        self._sync_training_lab_profile(
            content_item=content,
            course=course,
            lesson_seed=lesson_seed,
            module_index=module_index,
            lesson_index=lesson_index,
        )
        return content

    def _upsert_final_notebook_content(self, *, course: OnlineCourse) -> TrainingContentItem:
        slug = f"{course.slug}-final-project"
        final_lesson_seed = LessonSeed(
            title="Final Project / Exam",
            description="Consolidate the full course workflow into a final notebook submission and reviewer summary.",
            topic="final_project",
            notebook_prompt="Implement the final solution, keep the notebook reproducible, and summarize the final result for review.",
            reflection_prompt="Write a short handoff note that explains the final result, the validation path, and one next improvement.",
            quiz_points=(
                "The final scope is clearly defined",
                "The notebook can be re-run by another reviewer",
                "The closing summary explains the result",
            ),
            reading_points=(
                "Summarize the workflow before submission",
                "Keep the final artifact clean and reviewable",
                "Document the outcome and one follow-up step",
            ),
        )
        content = TrainingContentItem.objects.update_or_create(
            slug=slug,
            defaults={
                "name": f"{course.title_en} Final Project",
                "description": "Final project notebook for course completion.",
                "body_markdown": "Submit a final notebook and attach summary commentary.",
                "content_kind": TrainingContentItem.ContentKind.NOTEBOOK,
                "status": TrainingContentItem.Status.PUBLISHED,
                "access_scope": TrainingContentItem.AccessScope.AUTHENTICATED,
                "difficulty": TrainingContentItem.Difficulty.ADVANCED,
                "course": course,
                "source_url": "",
                "estimated_minutes": 90,
                "is_repeatable_on_demand": True,
                "supports_inline_lab": True,
                "published_at": timezone.now(),
            },
        )[0]
        self._sync_training_lab_profile(
            content_item=content,
            course=course,
            lesson_seed=final_lesson_seed,
            module_index=99,
            lesson_index=1,
            final_project=True,
        )
        return content

    def _upsert_materials(self, course: OnlineCourse) -> None:
        OnlineCourseMaterial.objects.update_or_create(
            course=course,
            title="Program handbook",
            language=OnlineCourse.LOCALE_EN,
            material_type=OnlineCourseMaterial.MATERIAL_RESOURCE,
            defaults={
                "description": "Course governance and weekly execution checklist.",
                "link_url": "",
                "sort_order": 10,
                "is_active": True,
            },
        )
        OnlineCourseMaterial.objects.update_or_create(
            course=course,
            title="Participation policy",
            language=OnlineCourse.LOCALE_EN,
            material_type=OnlineCourseMaterial.MATERIAL_CONDITION,
            defaults={
                "description": "Delivery rules, attendance policy, and escalation route.",
                "link_url": "",
                "sort_order": 20,
                "is_active": True,
            },
        )

    def _upsert_cohort(
        self,
        *,
        course: OnlineCourse,
        teacher: Lehrer | None,
        group_code: str,
        group_name: str,
        start_date: date,
    ) -> OnlineCohort:
        cohort = OnlineCohort.objects.update_or_create(
            group_code=group_code,
            defaults={
                "course": course,
                "teacher": teacher,
                "name": group_name,
                "capacity": 30,
                "timezone": "Europe/Berlin",
                "start_date": start_date,
                "end_date": start_date + timedelta(days=70),
                "status": OnlineCohort.STATUS_OPEN,
                "is_public": True,
            },
        )[0]
        return cohort

    def _seed_sessions(self, *, course: OnlineCourse, cohort: OnlineCohort, timezone_value: ZoneInfo) -> None:
        OnlineSession.objects.filter(cohort=cohort).delete()
        lessons = list(
            course.structured_lessons.filter(is_active=True)
            .select_related("module")
            .order_by("module__sort_order", "sort_order", "id")
        )
        anchor = cohort.start_date or date.today()
        for index, lesson in enumerate(lessons, start=1):
            starts_at = datetime.combine(anchor + timedelta(days=(index - 1) * 7), time(18, 0, 0)).replace(
                tzinfo=timezone_value
            )
            OnlineSession.objects.create(
                cohort=cohort,
                title=lesson.title,
                description=lesson.description or "Structured lesson delivery block.",
                starts_at=starts_at,
                ends_at=starts_at + timedelta(hours=2),
                status=OnlineSession.STATUS_SCHEDULED,
                join_url="https://teams.microsoft.com/",
                recording_url=self._resolve_recording_url_for_lesson(lesson),
                sort_order=index,
                is_completed=False,
            )

    def _resolve_recording_url_for_lesson(self, lesson) -> str:
        for section in lesson.sections.filter(is_active=True).order_by("sort_order", "id"):
            video_item = (
                section.items.filter(is_active=True, activity_type="video")
                .order_by("sort_order", "id")
                .first()
            )
            if video_item and video_item.external_url:
                return video_item.external_url
        return ""

    def _enroll_student_if_present(self, *, student_email: str, cohort: OnlineCohort | None) -> None:
        if not student_email or cohort is None:
            return
        user = User.objects.filter(email__iexact=student_email).first()
        if user is None:
            return
        profile, _created = OnlineStudentProfile.objects.get_or_create(
            user=user,
            defaults={
                "first_name": user.first_name or "Demo",
                "last_name": user.last_name or "Student",
                "preferred_language": OnlineCourse.LOCALE_EN,
            },
        )
        profile.enrollments.update_or_create(
            course=cohort.course,
            cohort=cohort,
            defaults={"status": OnlineEnrollment.STATUS_ACTIVE},
        )
