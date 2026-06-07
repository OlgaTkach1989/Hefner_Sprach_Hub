from __future__ import annotations

import textwrap


COURSE_SLUG = "financial-time-series-forecasting-lab"
COURSE_TITLE = "Financial Time-Series Forecasting Lab"
COURSE_SHORT_DESCRIPTION = (
    "Mini-course with a JupyterLab practice step for educational Bitcoin forecasting on a fixed historical snapshot."
)
COURSE_DESCRIPTION = (
    "A guided enterprise-style learning path for time-aware forecasting in JupyterLab. "
    "Learners review the theory, watch a short walkthrough, complete a quiz, build a small Bitcoin forecasting notebook, "
    "and document the main model risks and limitations."
)
COURSE_HERO_IMAGE_URL = (
    "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1200&q=80"
)

MODULE_TITLE = "Module 1 (Week 1) - Bitcoin Case"
MODULE_DESCRIPTION = "Time-aware validation, lag features, baseline comparison, and responsible interpretation."
LESSON_TITLE = "Bitcoin Case: Forecasting with JupyterLab"
LESSON_DESCRIPTION = "Build a compact time-series workflow and compare a baseline forecast with a smoothed forecast."
NOTEBOOK_CONTENT_SLUG = "financial-time-series-forecasting-lab-bitcoin-case"
NOTEBOOK_FILENAME = "bitcoin_case_forecasting_lab.ipynb"
NOTEBOOK_ASSIGNMENT_CODE = "bitcoin_case_forecasting_lab"
VIDEO_URL = "https://www.youtube.com/watch?v=rfscVS0vtbw"

THEORY_MARKDOWN = """
## Why this lesson matters

Forecasting is not only about producing a number. In enterprise teams, it is about:

- building a repeatable workflow
- keeping the dataset and assumptions explicit
- avoiding leakage between history and validation
- explaining why a result should or should not be trusted

This mini-course uses a Bitcoin price case because it is easy to understand visually, but the lesson is about
time-series discipline, not trading recommendations.

## What you will do

- load a fixed local BTC/USD dataset snapshot
- engineer historical features without leakage
- compare a naive baseline with a smoothed forecast
- run the notebook in JupyterLab
- submit the notebook back to the platform for grading
""".strip()


CONCEPT_MARKDOWN = """
## Core concept

For a small forecasting lab, the main controls matter more than model complexity.

### 1. Use a time-aware split

Do **not** shuffle the data. Validation must happen on the most recent observations.

### 2. Build features only from history

If the current target leaks into the feature set, the forecast is no longer trustworthy.

### 3. Start with a baseline

A simple baseline such as the previous close can be surprisingly strong. More complex smoothing is not
automatically better.

### 4. Interpret the result carefully

This lab is for **educational modeling only**. A forecast is not investment advice and should not be treated
as a trading signal.
""".strip()


PRACTICE_MARKDOWN = """
## Practice checklist

1. Open the notebook in **JupyterLab** and run the **Lab assistant** cell first.
2. Complete the `TODO` cells and run the notebook from top to bottom so the saved output shows all printed metrics.
3. Print these outputs:
   - `Rows: 18`
   - `Baseline MAE: 715.00`
   - `Rolling MAE: 1406.67`
   - `Next forecast: 50066.67`
4. Add a short conclusion that mentions **leakage** and **not investment advice**.
5. Use the **Lab assistant** inside JupyterLab to validate your work, request a hint, ask AI, and submit the result back to the lesson automatically.
""".strip()


SUMMARY_MARKDOWN = """
## Risks and limitations

- The dataset is a short local snapshot, not a production market feed.
- The lab compares a baseline forecast with a simple smoothed forecast, not a full research model.
- Forecast quality in a trending series can be unstable, and a stronger-looking method may still fail on new data.
- The result is **not investment advice**. The point of the lab is reproducibility, validation, and interpretation.

## Next step

If you extend the notebook later, add a wider validation window, more features, and a documented model-risk note.
""".strip()


QUIZ_PAYLOAD = {
    "prompt": "Which statement best describes the goal of this lab?",
    "successMessage": "Correct. The lesson is about disciplined forecasting workflow, not market advice.",
    "errorMessage": "Not quite. Re-check the lesson framing before moving to practice.",
    "questions": [
        {
            "id": "btc-q1",
            "prompt": "Why should the validation split stay time-based instead of random?",
            "options": [
                {
                    "id": "btc-q1-a",
                    "label": "Because a time-based split reduces leakage from future observations",
                    "isCorrect": True,
                },
                {
                    "id": "btc-q1-b",
                    "label": "Because random splits are only allowed for image data",
                    "isCorrect": False,
                },
                {
                    "id": "btc-q1-c",
                    "label": "Because random splits make charts render too slowly in JupyterLab",
                    "isCorrect": False,
                },
            ],
            "successMessage": "Correct. Validation should reflect the order in which new market data arrives.",
            "errorMessage": "Incorrect. The key reason is to avoid future information leaking into the evaluation.",
            "explanationMarkdown": "A time series should be validated on later observations, not randomly mixed rows.",
        },
        {
            "id": "btc-q2",
            "prompt": "What is the baseline forecast in this notebook?",
            "options": [
                {
                    "id": "btc-q2-a",
                    "label": "The previous close, carried forward as a naive baseline",
                    "isCorrect": True,
                },
                {
                    "id": "btc-q2-b",
                    "label": "A random forest ensemble trained on thousands of features",
                    "isCorrect": False,
                },
                {
                    "id": "btc-q2-c",
                    "label": "A live market prediction from an exchange API",
                    "isCorrect": False,
                },
            ],
            "successMessage": "Correct. The baseline uses the previous observed close.",
            "errorMessage": "Incorrect. This lab starts with a very simple naive baseline.",
            "explanationMarkdown": "A strong baseline is part of good model discipline.",
        },
        {
            "id": "btc-q3",
            "prompt": "How should the final forecast be interpreted in this lesson?",
            "options": [
                {
                    "id": "btc-q3-a",
                    "label": "As an educational result that is not investment advice",
                    "isCorrect": True,
                },
                {
                    "id": "btc-q3-b",
                    "label": "As a direct recommendation to buy or sell Bitcoin immediately",
                    "isCorrect": False,
                },
                {
                    "id": "btc-q3-c",
                    "label": "As a guaranteed production forecast for treasury teams",
                    "isCorrect": False,
                },
            ],
            "successMessage": "Correct. The notebook demonstrates workflow and interpretation, not trading advice.",
            "errorMessage": "Incorrect. The lesson is explicitly educational and non-advisory.",
            "explanationMarkdown": "Use the forecast as a modeling artifact, not as an investment recommendation.",
        },
    ],
}


BTC_USD_DAILY_DATASET_CSV = """date,close,volume_usd_m
2026-03-01,41820,1820
2026-03-02,42110,1915
2026-03-03,42780,2060
2026-03-04,43120,2145
2026-03-05,42890,2085
2026-03-06,43540,2205
2026-03-07,44110,2320
2026-03-08,44680,2410
2026-03-09,45220,2485
2026-03-10,45890,2570
2026-03-11,46250,2645
2026-03-12,46840,2720
2026-03-13,47210,2795
2026-03-14,47920,2880
2026-03-15,48610,2975
2026-03-16,49280,3055
2026-03-17,50140,3140
2026-03-18,50780,3215
""".strip()


NOTEBOOK_GRADER_CONFIG = {
    "mode": "custom_rules",
    "maxScore": "100",
    "checks": [
        {
            "id": "historical-lag",
            "label": "Lag feature",
            "kind": "code_contains",
            "needle": "shift(1)",
            "points": "10",
            "failureMessage": "Use `shift(1)` so the feature set only sees historical closes.",
            "hintIds": [1],
        },
        {
            "id": "rolling-feature",
            "label": "Rolling mean feature",
            "kind": "code_contains",
            "needle": "rolling(3)",
            "points": "10",
            "failureMessage": "Create a 3-step rolling mean feature from historical values.",
            "hintIds": [1],
        },
        {
            "id": "rows-output",
            "label": "Dataset row count",
            "kind": "output_contains",
            "needle": "Rows: 18",
            "points": "10",
            "failureMessage": "Run the notebook and keep the dataset row count visible in the saved output.",
            "hintIds": [2],
        },
        {
            "id": "baseline-output",
            "label": "Baseline MAE",
            "kind": "output_contains",
            "needle": "Baseline MAE: 715.00",
            "points": "15",
            "failureMessage": "Print the baseline MAE with two decimals after the validation step.",
            "hintIds": [2],
        },
        {
            "id": "rolling-output",
            "label": "Rolling MAE",
            "kind": "output_contains",
            "needle": "Rolling MAE: 1406.67",
            "points": "15",
            "failureMessage": "Print the rolling-mean MAE with two decimals after the validation step.",
            "hintIds": [2],
        },
        {
            "id": "forecast-output",
            "label": "Next-day forecast",
            "kind": "output_contains",
            "needle": "Next forecast: 50066.67",
            "points": "15",
            "failureMessage": "Print the next-day forecast with two decimals and keep it in the saved notebook output.",
            "hintIds": [2],
        },
        {
            "id": "leakage-note",
            "label": "Leakage note",
            "kind": "markdown_contains",
            "needle": "leakage",
            "points": "10",
            "failureMessage": "Add a markdown conclusion that explicitly mentions leakage risk.",
            "hintIds": [3],
        },
        {
            "id": "advice-note",
            "label": "Non-advisory note",
            "kind": "markdown_contains",
            "needle": "investment advice",
            "points": "10",
            "failureMessage": "Add a markdown note that this notebook is not investment advice.",
            "hintIds": [3],
        },
        {
            "id": "todo-cleanup",
            "label": "TODO cleanup",
            "kind": "forbidden_text",
            "needle": "TODO",
            "points": "5",
            "failureMessage": "Remove the TODO placeholders before you submit the notebook.",
            "hintIds": [1, 2],
        },
    ],
    "textSubmissionChecks": [
        {
            "id": "rows-output-text",
            "label": "Dataset row count",
            "kind": "output_contains",
            "needle": "Rows: 18",
            "points": "20",
            "failureMessage": "Paste the dataset row count into your quick answer.",
        },
        {
            "id": "baseline-output-text",
            "label": "Baseline MAE",
            "kind": "output_contains",
            "needle": "Baseline MAE: 715.00",
            "points": "20",
            "failureMessage": "Paste the baseline MAE into your quick answer.",
        },
        {
            "id": "rolling-output-text",
            "label": "Rolling MAE",
            "kind": "output_contains",
            "needle": "Rolling MAE: 1406.67",
            "points": "20",
            "failureMessage": "Paste the rolling MAE into your quick answer.",
        },
        {
            "id": "forecast-output-text",
            "label": "Next-day forecast",
            "kind": "output_contains",
            "needle": "Next forecast: 50066.67",
            "points": "20",
            "failureMessage": "Paste the next-day forecast into your quick answer.",
        },
        {
            "id": "leakage-note-text",
            "label": "Leakage note",
            "kind": "markdown_contains",
            "needle": "leakage",
            "points": "10",
            "failureMessage": "Mention leakage in your short conclusion.",
        },
        {
            "id": "advice-note-text",
            "label": "Non-advisory note",
            "kind": "markdown_contains",
            "needle": "investment advice",
            "points": "10",
            "failureMessage": "State clearly that the lab is not investment advice.",
        },
    ],
}


NOTEBOOK_HINTS = (
    {
        "title": "Feature engineering hint",
        "bodyMarkdown": "Use `shift(1)` for the lag feature and `shift(1).rolling(3).mean()` for the smoothed feature to keep the workflow leak-free.",
        "availabilityMode": "after_attempt",
        "minAttemptNumber": 1,
        "maxScorePercent": 100,
        "sortOrder": 10,
    },
    {
        "title": "Metric output hint",
        "bodyMarkdown": "Print the metrics with `:.2f` so the grader can read the exact saved output from the notebook.",
        "availabilityMode": "after_failure",
        "minAttemptNumber": 1,
        "maxScorePercent": 100,
        "sortOrder": 20,
    },
    {
        "title": "Interpretation hint",
        "bodyMarkdown": "The final markdown note should mention leakage risk and clearly state that the notebook is educational, not investment advice.",
        "availabilityMode": "after_score_below",
        "minAttemptNumber": 1,
        "maxScorePercent": 80,
        "sortOrder": 30,
    },
)


def bitcoin_case_starter_notebook() -> dict:
    return {
        "cells": [
            _markdown_cell(
                "# Financial Time-Series Forecasting Lab\n"
                "## Bitcoin case\n\n"
                "This notebook uses a fixed BTC/USD snapshot to demonstrate a small, reviewable forecasting workflow.\n\n"
                "**Important:** the notebook is educational and not investment advice."
            ),
            _markdown_cell(
                "### Objectives\n"
                "- load the local dataset snapshot\n"
                "- build historical features without leakage\n"
                "- compare a naive baseline with a rolling-mean forecast\n"
                "- print the validation metrics and the next-day forecast\n"
                "- finish with a short markdown interpretation"
            ),
            _code_cell(
                _lab_assistant_cell_source(),
                metadata={
                    "jupyter": {"source_hidden": True},
                    "tags": ["hide-input", "lab-assistant-helper"],
                },
            ),
            _code_cell(
                "from pathlib import Path\n"
                "import pandas as pd\n"
                "import matplotlib.pyplot as plt\n\n"
                "data_path = Path(\"btc_usd_daily.csv\")\n"
                "btc_df = pd.read_csv(data_path)\n"
                "btc_df[\"date\"] = pd.to_datetime(btc_df[\"date\"])\n"
                "btc_df = btc_df.sort_values(\"date\").reset_index(drop=True)\n"
                "dataset_rows = len(btc_df)\n\n"
                "btc_df.head()"
            ),
            _markdown_cell(
                "### Task 1\n"
                "Create a helper that engineers two historical features:\n"
                "- `lag_1`\n"
                "- `rolling_mean_3`\n\n"
                "Use only historical closes so the workflow stays free of **leakage**."
            ),
            _code_cell(
                "def build_features(dataframe: pd.DataFrame) -> pd.DataFrame:\n"
                "    feature_frame = dataframe.copy()\n"
                "    # TODO: add a lag feature based on historical closes only\n"
                "    feature_frame[\"lag_1\"] = 0.0\n"
                "    # TODO: add a 3-step rolling mean from historical closes only\n"
                "    feature_frame[\"rolling_mean_3\"] = 0.0\n"
                "    return feature_frame.dropna().reset_index(drop=True)\n\n"
                "feature_df = build_features(btc_df)\n"
                "feature_rows = len(feature_df)\n\n"
                "feature_df.tail()"
            ),
            _markdown_cell(
                "### Task 2\n"
                "Use the last 4 rows as a validation window. Compare:\n"
                "- a naive baseline that reuses `lag_1`\n"
                "- a smoothed forecast based on `rolling_mean_3`\n\n"
                "Then build a one-step next-day forecast from the last 3 closes."
            ),
            _code_cell(
                "validation_window = 4\n"
                "train_df = feature_df.iloc[:-validation_window].copy()\n"
                "validation_df = feature_df.iloc[-validation_window:].copy()\n"
                "train_rows = len(train_df)\n"
                "validation_rows = len(validation_df)\n\n"
                "# TODO: compute the naive baseline MAE\n"
                "baseline_mae = 0.0\n"
                "# TODO: compute the rolling forecast MAE\n"
                "rolling_mae = 0.0\n\n"
                "def forecast_next_close(dataframe: pd.DataFrame) -> float:\n"
                "    # TODO: return the next-day forecast from the latest 3 closes\n"
                "    return 0.0\n\n"
                "next_day_forecast = forecast_next_close(btc_df)\n\n"
                "print(f\"Rows: {dataset_rows}\")\n"
                "print(f\"Feature rows: {feature_rows}\")\n"
                "print(f\"Train rows: {train_rows}\")\n"
                "print(f\"Validation rows: {validation_rows}\")\n"
                "print(f\"Baseline MAE: {baseline_mae:.2f}\")\n"
                "print(f\"Rolling MAE: {rolling_mae:.2f}\")\n"
                "print(f\"Next forecast: {next_day_forecast:.2f}\")"
            ),
            _code_cell(
                "ax = btc_df.plot(x=\"date\", y=\"close\", figsize=(10, 4), title=\"BTC/USD close snapshot\")\n"
                "ax.set_ylabel(\"Close\")\n"
                "plt.tight_layout()"
            ),
            _markdown_cell(
                "## Interpretation\n"
                "Replace this note with 2-3 sentences that explain:\n"
                "- where **leakage** could appear in a time-series workflow\n"
                "- why this notebook is **not investment advice**\n"
                "- what you would improve before using a richer model\n\n"
                "TODO"
            ),
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def _markdown_cell(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [source],
    }


def _code_cell(source: str, *, metadata: dict | None = None) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": metadata or {},
        "outputs": [],
        "source": [source],
    }


def _lab_assistant_cell_source() -> str:
    return textwrap.dedent(
        """
        # Lab assistant helper cell. Run once; do not edit it as part of the assignment.
        import hashlib
        import os
        from pathlib import Path

        import requests
        from IPython.display import Javascript, Markdown, clear_output, display

        try:
            import ipywidgets as widgets
        except ImportError:
            widgets = None

        LAB_ACTIONS_BASE_URL = str(os.getenv("TRAINING_NOTEBOOK_ACTIONS_BASE_URL") or "").rstrip("/")
        LAB_ACTION_TOKEN = str(os.getenv("TRAINING_NOTEBOOK_ACTION_TOKEN") or "").strip()
        LAB_NOTEBOOK_PATH = str(os.getenv("TRAINING_NOTEBOOK_PATH") or "").strip().lstrip("/")
        LAB_CONTENT_NAME = str(os.getenv("TRAINING_CONTENT_NAME") or "Notebook lab").strip()
        LAB_NOTEBOOK_ROOT = str(os.getenv("JUPYTERHUB_NOTEBOOK_DIR") or "").strip()

        def _lab_current_notebook_path() -> Path:
            if not LAB_NOTEBOOK_PATH:
                raise RuntimeError("Notebook path is not configured for this runtime.")
            candidates = []
            if LAB_NOTEBOOK_ROOT:
                candidates.append((Path(LAB_NOTEBOOK_ROOT) / LAB_NOTEBOOK_PATH).resolve())
            candidates.append((Path.cwd() / LAB_NOTEBOOK_PATH).resolve())
            for candidate in candidates:
                if candidate.exists():
                    return candidate
            raise FileNotFoundError(f"Notebook file was not found: {candidates[0]}")

        def _lab_read_notebook():
            notebook_path = _lab_current_notebook_path()
            notebook_bytes = notebook_path.read_bytes()
            checksum = hashlib.sha256(notebook_bytes).hexdigest()
            return notebook_path, notebook_bytes, checksum

        def _lab_headers() -> dict:
            if not LAB_ACTION_TOKEN:
                raise RuntimeError("Notebook action token is missing from the runtime.")
            return {"Authorization": f"Bearer {LAB_ACTION_TOKEN}"}

        def _lab_post(path_suffix: str, *, files=None, data=None, json_payload=None):
            if not LAB_ACTIONS_BASE_URL:
                raise RuntimeError("Notebook actions base URL is not configured.")
            response = requests.post(
                f"{LAB_ACTIONS_BASE_URL}/{path_suffix.lstrip('/')}",
                headers=_lab_headers(),
                files=files,
                data=data,
                json=json_payload,
                timeout=90,
            )
            try:
                payload = response.json()
            except Exception:
                payload = {"detail": response.text.strip() or "Notebook action failed."}
            if response.status_code >= 400:
                raise RuntimeError(str(payload.get("detail") or "Notebook action failed."))
            return payload

        def lab_validate():
            notebook_path, notebook_bytes, _checksum = _lab_read_notebook()
            return _lab_post(
                "validate/",
                files={"notebook": (notebook_path.name, notebook_bytes, "application/x-ipynb+json")},
            )

        def lab_get_hint():
            notebook_path, notebook_bytes, _checksum = _lab_read_notebook()
            return _lab_post(
                "hint/",
                files={"notebook": (notebook_path.name, notebook_bytes, "application/x-ipynb+json")},
            )

        def lab_ask_ai(question: str):
            normalized_question = str(question or "").strip()
            if not normalized_question:
                raise RuntimeError("Enter a question for the lab assistant first.")
            return _lab_post("ask/", json_payload={"question": normalized_question})

        def lab_submit():
            notebook_path, notebook_bytes, checksum = _lab_read_notebook()
            return _lab_post(
                "submit/",
                files={"notebook": (notebook_path.name, notebook_bytes, "application/x-ipynb+json")},
                data={"client_checksum": checksum},
            )

        def _render_validation(payload: dict) -> str:
            validation = payload.get("validation") or payload
            feedback = validation.get("feedbackPayload") or {}
            summary = feedback.get("summary") or {}
            highlights = feedback.get("feedbackHighlights") or []
            rubric = feedback.get("rubric") or []
            tests = feedback.get("tests") or {}
            lines = [
                f"### Validation for {LAB_CONTENT_NAME}",
                f"- Passed: {'Yes' if validation.get('passed') else 'No'}",
                f"- Score: {validation.get('score') or '-'} / {validation.get('maxScore') or '-'}",
                f"- Passing threshold: {summary.get('passThresholdPercent') or '-'}%",
                f"- Checks passed: {tests.get('passed', 0)} of {tests.get('total', len(rubric))}",
            ]
            if highlights:
                lines.append("\\n**Key feedback**")
                lines.extend(f"- {item}" for item in highlights[:5])
            hint_payload = payload.get("hint")
            if hint_payload and hint_payload.get("bodyMarkdown"):
                lines.append("\\n**Recommended hint**")
                lines.append(hint_payload.get("bodyMarkdown"))
            return "\\n".join(lines)

        def _status_card_html(*, tone: str, title: str, body: str) -> str:
            palette = {
                "ready": {"bg": "#f7fafc", "border": "#d7e1ea", "title": "#173444", "body": "#577083"},
                "working": {"bg": "#fff8ea", "border": "#eed39a", "title": "#8d6515", "body": "#7a6750"},
                "success": {"bg": "#ecfdf3", "border": "#9ad6b3", "title": "#1f7a48", "body": "#305f43"},
                "error": {"bg": "#fff1f1", "border": "#f0b0b0", "title": "#9d2f2f", "body": "#7c4b4b"},
            }
            token = palette.get(tone, palette["ready"])
            return (
                "<div style='padding:12px 14px;border-radius:14px;"
                f"border:1px solid {token['border']};background:{token['bg']};margin:10px 0 14px;'>"
                f"<div style='font-weight:700;color:{token['title']};margin-bottom:4px;'>{title}</div>"
                f"<div style='color:{token['body']};line-height:1.5;'>{body}</div>"
                "</div>"
            )

        def _render_ai_answer(payload: dict) -> str:
            answer = payload.get("answer") or {}
            lines = [
                "### Lab assistant reply",
                answer.get("shortAnswer") or "",
                "",
                answer.get("detailedAnswer") or "",
            ]
            citations = answer.get("citations") or []
            if citations:
                lines.append("\\n**References**")
                lines.extend(f"- {item.get('label') or item.get('title') or 'Lesson context'}" for item in citations[:4])
            return "\\n".join(part for part in lines if part is not None)

        def _hide_authoring_ui():
            script = '''
            (() => {
              const hide = () => {
                const menuLabels = document.querySelectorAll('.lm-MenuBar-itemLabel, .jp-MenuBar-itemLabel, [role="menuitem"]');
                menuLabels.forEach((node) => {
                  const text = (node.textContent || '').trim().toLowerCase();
                  if (text === 'nbgrader') {
                    const menuItem = node.closest('.lm-MenuBar-item') || node.closest('[role="menuitem"]') || node.parentElement;
                    if (menuItem) {
                      menuItem.style.display = 'none';
                    }
                  }
                  if (text === 'create assignment') {
                    const actionItem = node.closest('.lm-Menu-item') || node.closest('[role="menuitem"]') || node.parentElement;
                    if (actionItem) {
                      actionItem.style.display = 'none';
                    }
                  }
                });
              };
              hide();
              if (!window.__onlineLessonsLearnerObserver) {
                const observer = new MutationObserver(() => hide());
                observer.observe(document.body, { childList: true, subtree: true });
                window.__onlineLessonsLearnerObserver = observer;
              }
            })();
            '''
            try:
                display(Javascript(script))
            except Exception:
                return

        if widgets is None:
            display(Markdown(
                "### Lab assistant\\n"
                "- Run `lab_validate()` to check the current notebook.\\n"
                "- Run `lab_get_hint()` for the next hint.\\n"
                "- Run `lab_ask_ai('your question')` for a short explanation.\\n"
                "- Run `lab_submit()` after validation passes.\\n\\n"
                "Ignore **Nbgrader → Create assignment** in this learner runtime."
            ))
        else:
            _hide_authoring_ui()
            helper_intro = widgets.HTML(
                value=(
                    "<div style='padding:12px 14px;border:1px solid #d9e2ea;border-radius:14px;"
                    "background:#f7fafc;margin:6px 0 14px;'>"
                    "<strong>Lab assistant</strong><br/>"
                    "This first cell is helper code, not part of the assignment. "
                    "Run it once, then use Validate, Get hint, Ask AI, and Submit result from here."
                    "<br/><span style='color:#577083;'>Run this helper once, then save the notebook before Validate, Get hint, or Submit so the latest file is used.</span>"
                    "<br/><span style='color:#577083;'>Ignore <strong>Nbgrader → Create assignment</strong>; "
                    "that menu is for authoring, not for learner submissions.</span>"
                    "</div>"
                )
            )
            status_html = widgets.HTML(
                value=_status_card_html(
                    tone="ready",
                    title="Ready to work",
                    body="Run the notebook, keep the required outputs visible, then validate your work here.",
                )
            )
            question_box = widgets.Textarea(
                placeholder="Ask about leakage, the expected metrics, or how to interpret the forecast.",
                layout=widgets.Layout(width="100%", height="88px"),
            )
            validate_button = widgets.Button(
                description="Validate notebook",
                button_style="info",
                layout=widgets.Layout(width="170px", height="40px"),
                tooltip="Check the current notebook outputs and rubric.",
            )
            hint_button = widgets.Button(
                description="Get hint",
                layout=widgets.Layout(width="120px", height="40px"),
                tooltip="Show the next recommended hint for failed checks.",
            )
            ask_button = widgets.Button(
                description="Ask AI",
                layout=widgets.Layout(width="110px", height="40px"),
                tooltip="Ask the built-in AI assistant about the notebook.",
            )
            submit_button = widgets.Button(
                description="Submit result",
                button_style="success",
                layout=widgets.Layout(width="140px", height="40px"),
                tooltip="Send the notebook for grading and update the lesson automatically if it passes.",
            )
            output = widgets.Output(layout=widgets.Layout(border="1px solid #e2e8f0", padding="10px"))

            def _show_markdown(markdown_text: str):
                with output:
                    clear_output()
                    display(Markdown(markdown_text))

            def _set_status_from_validation(payload: dict):
                validation = payload.get("validation") or payload
                feedback = validation.get("feedbackPayload") or {}
                tests = feedback.get("tests") or {}
                score = validation.get("score") or "-"
                max_score = validation.get("maxScore") or "-"
                if validation.get("passed"):
                    status_html.value = _status_card_html(
                        tone="success",
                        title="Passed",
                        body=(
                            f"Notebook validation passed. Score: {score} / {max_score}. "
                            "You can submit the result now and the Practice step will update automatically."
                        ),
                    )
                    return
                status_html.value = _status_card_html(
                    tone="working",
                    title="Needs another pass",
                    body=(
                        f"Current score: {score} / {max_score}. "
                        f"Checks passed: {tests.get('passed', 0)} of {tests.get('total', 0)}. "
                        "Use Get hint or Ask AI, then validate again."
                    ),
                )

            def _safe_action(action, renderer, success_handler=None, failure_title="Action failed"):
                try:
                    payload = action()
                except Exception as exc:
                    status_html.value = _status_card_html(
                        tone="error",
                        title=failure_title,
                        body=str(exc),
                    )
                    _show_markdown(f"### {failure_title}\\n- {exc}")
                    return
                if success_handler is not None:
                    success_handler(payload)
                _show_markdown(renderer(payload))

            validate_button.on_click(
                lambda _event: _safe_action(
                    lab_validate,
                    _render_validation,
                    success_handler=_set_status_from_validation,
                    failure_title="Validation failed",
                )
            )
            hint_button.on_click(
                lambda _event: _safe_action(
                    lab_get_hint,
                    _render_validation,
                    success_handler=_set_status_from_validation,
                    failure_title="Hint lookup failed",
                )
            )
            ask_button.on_click(
                lambda _event: _safe_action(
                    lambda: lab_ask_ai(question_box.value),
                    _render_ai_answer,
                    success_handler=lambda _payload: status_html.__setattr__(
                        "value",
                        _status_card_html(
                            tone="ready",
                            title="AI answer ready",
                            body="Review the explanation below, then continue in the notebook and validate again.",
                        ),
                    ),
                    failure_title="AI assistant failed",
                )
            )
            submit_button.on_click(
                lambda _event: _safe_action(
                    lab_submit,
                    lambda payload: (
                        "### Submission received\\n"
                        f"- Passed: {'Yes' if payload.get('passed') else 'No'}\\n"
                        f"- Score: {payload.get('score') or '-'} / {payload.get('max_score') or payload.get('maxScore') or '-'}\\n"
                        "- If this passed, the Practice step in the lesson workspace will update automatically."
                    ),
                    success_handler=lambda payload: status_html.__setattr__(
                        "value",
                        _status_card_html(
                            tone="success" if payload.get("passed") else "working",
                            title="Submission complete" if payload.get("passed") else "Submission recorded",
                            body=(
                                "Passed. Return to the lesson page and you should see Practice marked complete."
                                if payload.get("passed")
                                else "The notebook was submitted, but it still needs corrections before the lesson can mark Practice complete."
                            ),
                        ),
                    ),
                    failure_title="Submission failed",
                )
            )

            display(helper_intro)
            display(status_html)
            display(widgets.HBox([validate_button, hint_button, ask_button, submit_button], layout=widgets.Layout(gap="10px")))
            display(question_box)
            display(output)
        """
    ).strip()
