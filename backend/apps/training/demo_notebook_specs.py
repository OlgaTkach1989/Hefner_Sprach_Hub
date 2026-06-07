from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DemoNotebookAssignmentSpec:
    slug: str
    name: str
    description: str
    body_markdown: str
    asset_class_slug: str
    asset_class_name: str
    topic_slug: str
    topic_name: str
    assignment_code: str
    notebook_filename: str
    lesson_title: str
    lesson_description: str
    introduction_title: str
    introduction_body: str
    conclusion_title: str
    conclusion_body: str
    starter_notebook: dict
    grader_config: dict
    hints: tuple[dict, ...]


def finance_demo_assignment_specs() -> tuple[DemoNotebookAssignmentSpec, ...]:
    return (
        DemoNotebookAssignmentSpec(
            slug="cva-discounted-loss-lab",
            name="CVA discounted loss notebook",
            description="Compute a first-pass discounted CVA estimate from exposure, LGD, and hazard assumptions.",
            body_markdown=(
                "## Goal\n"
                "Estimate a clean first-pass CVA number using a compact discounted-loss formula.\n\n"
                "Use the notebook to compute the 2-year discount factor and the final CVA estimate.\n\n"
                "MathJax reference: $\\mathrm{CVA} = \\mathrm{EAD} \\times \\mathrm{LGD} \\times \\lambda \\times T \\times DF(T)$."
            ),
            asset_class_slug="credit",
            asset_class_name="Credit",
            topic_slug="cva",
            topic_name="CVA",
            assignment_code="cva_discounted_loss",
            notebook_filename="cva_discounted_loss.ipynb",
            lesson_title="CVA discounted loss walkthrough",
            lesson_description="Introduce the basic discounted-loss approach before moving into richer exposure modelling.",
            introduction_title="Why this lab matters",
            introduction_body=(
                "Review the role of EAD, LGD, hazard assumptions, and discounting before opening the notebook. "
                "The goal is not a production model, but a reliable first-pass estimate and a clean explanation."
            ),
            conclusion_title="After the lab",
            conclusion_body=(
                "Capture what changed the result most, note the sensitivity of the estimate to hazard and maturity, "
                "and prepare one follow-up question for the course owner."
            ),
            starter_notebook={
                "cells": [
                    _markdown_cell(
                        "# CVA discounted loss\n"
                        "Use the simple approximation below and keep the explanatory note in markdown.\n\n"
                        "$$\\mathrm{CVA} = \\mathrm{EAD} \\times \\mathrm{LGD} \\times \\lambda \\times T \\times DF(T)$$"
                    ),
                    _code_cell(
                        "ead = 5_000_000\n"
                        "loss_given_default = 0.6\n"
                        "hazard_rate = 0.018\n"
                        "maturity_years = 2\n"
                        "risk_free_rate = 0.04\n"
                    ),
                    _markdown_cell(
                        "Explain in one short paragraph why discounting still matters even in a simplified CVA approximation."
                    ),
                    _code_cell(
                        "# TODO: compute the 2-year discount factor\n"
                        "discount_factor_2y = 0\n\n"
                        "# TODO: compute the final CVA estimate\n"
                        "cva_value = 0\n"
                    ),
                ],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4,
                "nbformat_minor": 5,
            },
            grader_config={
                "mode": "custom_rules",
                "maxScore": "100",
                "checks": [
                    {
                        "id": "discount-factor",
                        "label": "2Y discount factor",
                        "kind": "numeric_assignment",
                        "variable": "discount_factor_2y",
                        "expected": "0.923116",
                        "tolerance": "0.001",
                        "points": "35",
                        "hintIds": [1],
                        "failureMessage": "Compute `discount_factor_2y` from the 4% risk-free rate and 2-year tenor.",
                    },
                    {
                        "id": "cva-value",
                        "label": "Discounted CVA estimate",
                        "kind": "numeric_assignment",
                        "variable": "cva_value",
                        "expected": "99696.528",
                        "tolerance": "1.0",
                        "points": "45",
                        "hintIds": [2, 3],
                        "failureMessage": "Rebuild the CVA estimate from EAD, LGD, hazard, maturity, and the discount factor.",
                    },
                    {
                        "id": "markdown-rationale",
                        "label": "Discounting rationale",
                        "kind": "markdown_contains",
                        "needle": "discount",
                        "points": "20",
                        "hintIds": [3],
                        "failureMessage": "Add a short markdown explanation of why discounting still matters.",
                    },
                ],
            },
            hints=(
                {
                    "id": 1,
                    "title": "Discount factor hint",
                    "bodyMarkdown": "Use the continuous-discounting shortcut $DF(T)=e^{-rT}$ with $r=0.04$ and $T=2$.",
                    "availabilityMode": "after_attempt",
                    "minAttemptNumber": 1,
                    "maxScorePercent": 100,
                    "sortOrder": 10,
                },
                {
                    "id": 2,
                    "title": "CVA assembly hint",
                    "bodyMarkdown": "Multiply the already prepared inputs step by step to avoid missing one multiplier.",
                    "availabilityMode": "after_failure",
                    "minAttemptNumber": 1,
                    "maxScorePercent": 100,
                    "sortOrder": 20,
                },
                {
                    "id": 3,
                    "title": "Interpretation hint",
                    "bodyMarkdown": "Your explanation should mention time value, not just default probability.",
                    "availabilityMode": "after_score_below",
                    "minAttemptNumber": 1,
                    "maxScorePercent": 70,
                    "sortOrder": 30,
                },
            ),
        ),
        DemoNotebookAssignmentSpec(
            slug="bond-duration-shock-lab",
            name="Bond duration shock notebook",
            description="Measure the first-order price impact of a parallel yield shock on a fixed-income position.",
            body_markdown=(
                "## Goal\n"
                "Estimate the shocked bond price using duration-based approximation and document the sign of the move.\n\n"
                "MathJax reference: $\\Delta P / P \\approx -D_\\mathrm{mod} \\times \\Delta y$."
            ),
            asset_class_slug="rates",
            asset_class_name="Rates",
            topic_slug="duration",
            topic_name="Duration",
            assignment_code="bond_duration_shock",
            notebook_filename="bond_duration_shock.ipynb",
            lesson_title="Bond duration under a parallel rate shock",
            lesson_description="Use modified duration to estimate how a yield move translates into price change.",
            introduction_title="Before you start",
            introduction_body=(
                "Confirm whether the scenario is a yield increase or decrease and how that changes the sign of the price move."
            ),
            conclusion_title="Follow-up",
            conclusion_body=(
                "Compare the duration approximation with what could change in a convexity-aware version of the exercise."
            ),
            starter_notebook={
                "cells": [
                    _markdown_cell(
                        "# Bond duration shock\n"
                        "Use the modified-duration approximation for a parallel +50bp move."
                    ),
                    _code_cell(
                        "price_today = 101.2\n"
                        "modified_duration = 4.3\n"
                        "yield_shock = 0.005\n"
                    ),
                    _code_cell(
                        "# TODO: compute the percentage move\n"
                        "price_move_pct = 0\n\n"
                        "# TODO: compute the shocked bond price\n"
                        "shocked_price = 0\n"
                    ),
                    _markdown_cell("Write one sentence that explains why the sign of the price move is negative in this scenario."),
                ],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4,
                "nbformat_minor": 5,
            },
            grader_config={
                "mode": "custom_rules",
                "maxScore": "100",
                "checks": [
                    {
                        "id": "duration-move",
                        "label": "Duration move",
                        "kind": "numeric_assignment",
                        "variable": "price_move_pct",
                        "expected": "-0.0215",
                        "tolerance": "0.0002",
                        "points": "45",
                        "hintIds": [1],
                    },
                    {
                        "id": "shocked-price",
                        "label": "Shocked price",
                        "kind": "numeric_assignment",
                        "variable": "shocked_price",
                        "expected": "99.0242",
                        "tolerance": "0.05",
                        "points": "35",
                        "hintIds": [2],
                    },
                    {
                        "id": "sign-explanation",
                        "label": "Sign explanation",
                        "kind": "markdown_contains",
                        "needle": "negative",
                        "points": "20",
                        "hintIds": [2],
                    },
                ],
            },
            hints=(
                {
                    "id": 1,
                    "title": "Percentage move hint",
                    "bodyMarkdown": "Multiply modified duration by the yield shock and remember the minus sign.",
                    "availabilityMode": "after_attempt",
                    "minAttemptNumber": 1,
                    "maxScorePercent": 100,
                    "sortOrder": 10,
                },
                {
                    "id": 2,
                    "title": "Price translation hint",
                    "bodyMarkdown": "Convert the percentage move into a price by multiplying it by `price_today` and adding the result back to the starting price.",
                    "availabilityMode": "after_failure",
                    "minAttemptNumber": 1,
                    "maxScorePercent": 100,
                    "sortOrder": 20,
                },
            ),
        ),
        DemoNotebookAssignmentSpec(
            slug="fx-forward-parity-lab",
            name="FX forward parity notebook",
            description="Compute a 6M FX forward rate from covered-interest-parity inputs.",
            body_markdown=(
                "## Goal\n"
                "Price a forward rate from spot and carry inputs, then write one note about which rate should be larger.\n\n"
                "MathJax reference: $F=S\\times\\frac{1+r_d T}{1+r_f T}$."
            ),
            asset_class_slug="fx",
            asset_class_name="FX",
            topic_slug="forward-pricing",
            topic_name="Forward pricing",
            assignment_code="fx_forward_parity",
            notebook_filename="fx_forward_parity.ipynb",
            lesson_title="FX forward parity sanity check",
            lesson_description="Use covered-interest parity to sanity check the forward level for a short tenor trade.",
            introduction_title="Spot, carry, tenor",
            introduction_body=(
                "Identify which rate is domestic and which is foreign before pricing the forward."
            ),
            conclusion_title="Risk note",
            conclusion_body=(
                "Capture how the forward would move if the domestic rate dropped below the foreign rate."
            ),
            starter_notebook={
                "cells": [
                    _markdown_cell("# FX forward parity\nUse covered-interest parity for a 6-month tenor."),
                    _code_cell(
                        "spot_rate = 1.084\n"
                        "domestic_rate = 0.032\n"
                        "foreign_rate = 0.018\n"
                        "tenor_years = 0.5\n"
                    ),
                    _code_cell(
                        "# TODO: compute the 6M forward rate\n"
                        "forward_rate = 0\n"
                    ),
                    _markdown_cell("Add one line that states whether the forward should be above spot in this setup."),
                ],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4,
                "nbformat_minor": 5,
            },
            grader_config={
                "mode": "custom_rules",
                "maxScore": "100",
                "checks": [
                    {
                        "id": "forward-rate",
                        "label": "6M forward rate",
                        "kind": "numeric_assignment",
                        "variable": "forward_rate",
                        "expected": "1.091474",
                        "tolerance": "0.001",
                        "points": "70",
                        "hintIds": [1, 2],
                    },
                    {
                        "id": "above-spot-note",
                        "label": "Forward direction note",
                        "kind": "markdown_contains",
                        "needle": "above",
                        "points": "30",
                        "hintIds": [2],
                    },
                ],
            },
            hints=(
                {
                    "id": 1,
                    "title": "Parity formula hint",
                    "bodyMarkdown": "Scale the spot by the domestic carry leg divided by the foreign carry leg over the same tenor.",
                    "availabilityMode": "after_attempt",
                    "minAttemptNumber": 1,
                    "maxScorePercent": 100,
                    "sortOrder": 10,
                },
                {
                    "id": 2,
                    "title": "Interpretation hint",
                    "bodyMarkdown": "The domestic rate is higher than the foreign rate, so the forward should price above spot.",
                    "availabilityMode": "after_failure",
                    "minAttemptNumber": 1,
                    "maxScorePercent": 100,
                    "sortOrder": 20,
                },
            ),
        ),
    )


def _markdown_cell(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [source],
    }


def _code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [source],
    }
