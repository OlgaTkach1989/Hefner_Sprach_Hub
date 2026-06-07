from __future__ import annotations

import io
import traceback
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LessonCheckResult:
    name: str
    passed: bool
    expected: str | None = None
    actual: str | None = None


@dataclass(frozen=True)
class LessonGraderResult:
    status: str
    message: str
    checks: list[LessonCheckResult]


SAFE_BUILTINS = {
    "abs": abs,
    "bool": bool,
    "dict": dict,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "str": str,
    "sum": sum,
}


def _execute_user_code(code: str) -> tuple[dict[str, Any], str]:
    stdout_buffer = io.StringIO()
    local_vars: dict[str, Any] = {}
    restricted_globals = {"__builtins__": SAFE_BUILTINS}

    with redirect_stdout(stdout_buffer):
        exec(code, restricted_globals, local_vars)

    return local_vars, stdout_buffer.getvalue()


def grade_lesson_code(*, code: str, grader_config: dict[str, Any]) -> LessonGraderResult:
    grader_type = str(grader_config.get("type") or "").strip()
    if grader_type not in {"python_variable_check", "python_function_check"}:
        return LessonGraderResult(
            status="error",
            message="Unknown grader type.",
            checks=[
                LessonCheckResult(
                    name="Grader lookup",
                    passed=False,
                    expected="python_variable_check or python_function_check",
                    actual=grader_type or "missing",
                )
            ],
        )

    try:
        local_vars, stdout_text = _execute_user_code(code)
    except Exception:
        return LessonGraderResult(
            status="error",
            message="Your code raised an error during execution.",
            checks=[
                LessonCheckResult(
                    name="Execution",
                    passed=False,
                    actual=traceback.format_exc(limit=2),
                )
            ],
        )

    checks: list[LessonCheckResult] = []

    if grader_type == "python_function_check":
        function_name = str(grader_config.get("function_name") or "").strip()
        function_value = local_vars.get(function_name)
        if not function_name or not callable(function_value):
            checks.append(
                LessonCheckResult(
                    name=f"{function_name or 'target'} function exists",
                    passed=False,
                    expected="callable function",
                    actual=str(type(function_value)),
                )
            )
            return LessonGraderResult(
                status="fail",
                message="Your solution did not define the required function yet.",
                checks=checks,
            )

        for index, raw_case in enumerate(grader_config.get("cases") or [], start=1):
            if not isinstance(raw_case, dict):
                continue
            case_args = raw_case.get("args") if isinstance(raw_case.get("args"), list) else []
            case_kwargs = raw_case.get("kwargs") if isinstance(raw_case.get("kwargs"), dict) else {}
            expected_value = raw_case.get("expected")
            case_label = str(raw_case.get("label") or f"Case {index}").strip() or f"Case {index}"
            try:
                actual_value = function_value(*case_args, **case_kwargs)
                passed = actual_value == expected_value
                actual_display = str(actual_value)
            except Exception:
                passed = False
                actual_display = traceback.format_exc(limit=2)
            checks.append(
                LessonCheckResult(
                    name=case_label,
                    passed=passed,
                    expected=str(expected_value),
                    actual=actual_display,
                )
            )

        if not checks:
            checks.append(
                LessonCheckResult(
                    name="Function grader configuration",
                    passed=False,
                    expected="at least one case",
                    actual="missing",
                )
            )

        status = "success" if all(check.passed for check in checks) else "fail"
        message = (
            "Great job. Your solution passed all checks."
            if status == "success"
            else "Your solution did not pass all checks yet."
        )
        return LessonGraderResult(status=status, message=message, checks=checks)

    expected_variables = grader_config.get("expected_variables", {}) or {}
    required_functions = grader_config.get("required_functions", []) or []
    expected_stdout = grader_config.get("expected_stdout")

    for variable_name, expected_value in expected_variables.items():
        actual_value = local_vars.get(variable_name)
        checks.append(
            LessonCheckResult(
                name=f"{variable_name} has expected value",
                passed=actual_value == expected_value,
                expected=str(expected_value),
                actual=str(actual_value),
            )
        )

    for function_name in required_functions:
        value = local_vars.get(function_name)
        checks.append(
            LessonCheckResult(
                name=f"{function_name} function exists",
                passed=callable(value),
                expected="callable function",
                actual=str(type(value)),
            )
        )

    if expected_stdout is not None:
        actual_output = stdout_text.strip()
        checks.append(
            LessonCheckResult(
                name="stdout output is correct",
                passed=actual_output == str(expected_stdout).strip(),
                expected=str(expected_stdout).strip(),
                actual=actual_output,
            )
        )

    status = "success" if all(check.passed for check in checks) else "fail"
    message = (
        "Great job. Your solution passed all checks."
        if status == "success"
        else "Your solution did not pass all checks yet."
    )
    return LessonGraderResult(status=status, message=message, checks=checks)
