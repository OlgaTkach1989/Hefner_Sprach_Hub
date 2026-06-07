from __future__ import annotations

from copy import deepcopy
from typing import Any


GETTING_STARTED_WITH_PYTHON_THEORY_MARKDOWN = """
## Introduction

Welcome to the world of Python programming!

Python is one of the most popular programming languages in the world. It is used:

- to build web applications
- in data analysis and machine learning
- to automate tasks
- to create servers and APIs

Python is known for simple, readable code. Even if you have never programmed before, you can start writing your first programs quickly.

In this lesson, you will take your first steps:

- learn what variables are
- work with basic data types
- write your first code
- complete a short practical task

Important: programming is a skill that grows through practice. Do not be afraid of mistakes. They are part of learning.
""".strip()


GETTING_STARTED_WITH_PYTHON_CONCEPT_MARKDOWN = """
## What is a variable?

A variable is a named place in memory where a value is stored.

In simple terms, a variable is a "box" where we put data.

```python
name = "Anna"
```

Here, `name` is the variable name and `"Anna"` is the value.

## How to create variables

In Python, you do not need to declare the variable type in advance. You simply assign a value:

```python
age = 25
city = "Berlin"
```

Python automatically understands the data type.

## Basic data types

### String

```python
text = "Hello"
```

### Integer

```python
a = 10
```

### Float

```python
b = 3.14
```

### Boolean

```python
is_active = True
```

## Operations and output

Python can perform mathematical operations and print the result with `print()`:

```python
a = 5
b = 3

print(a + b)
print(a - b)
print(a * b)
print(a / b)
```

Strings can be combined:

```python
name = "Anna"
print("Hello, " + name)
```

## Conditions

```python
age = 20

if age >= 18:
    print("You are an adult")
else:
    print("You are a minor")
```

Variables and data types are the foundation of programming. Without them, you cannot store information, process data, or build program logic.
""".strip()


GETTING_STARTED_WITH_PYTHON_PRACTICE_MARKDOWN = """
## Practical task

Write a short Python script where you:

- work with variables
- use a string, a number, and a boolean value
- create a simple function
- print the result with `print()`

What you need to do:

1. Create a variable `student_name` with the value `"Anna"`.
2. Create a variable `student_age` with the value `25`.
3. Create a function `build_profile(name, age)` that returns a string like `"Anna (25)"`.
4. Save the function result into a variable named `profile`.
5. Create a variable `is_adult` that should be `True` when the age is greater than or equal to 18.
6. Print `profile` first and then `is_adult`.

After that, click `Run & Check` to validate your solution.
""".strip()


GETTING_STARTED_WITH_PYTHON_SUMMARY_MARKDOWN = """
## Why this matters

Variables and data types are the foundation of all programming.

Without them, you cannot:

- store information
- process data
- build program logic

Everything you build next, from APIs and frontend features to AI tools and backend services, depends on these basics.
""".strip()


GETTING_STARTED_WITH_PYTHON_STARTER_CODE = """student_name = "Anna"
student_age = 25


def build_profile(name, age):
    # TODO: return a formatted string like "Anna (25)"
    return ""


profile = build_profile(student_name, student_age)
is_adult = False

print(profile)
print(is_adult)
"""


GETTING_STARTED_WITH_PYTHON_SOLUTION = """student_name = "Anna"
student_age = 25


def build_profile(name, age):
    return f"{name} ({age})"


profile = build_profile(student_name, student_age)
is_adult = student_age >= 18

print(profile)
print(is_adult)
"""


GETTING_STARTED_WITH_PYTHON_QUIZ_QUESTIONS = [
    {
        "id": "q1",
        "prompt": "What is a variable in Python?",
        "options": [
            {"id": "q1-a", "label": "A named place in memory where a value is stored", "isCorrect": True},
            {"id": "q1-b", "label": "A command used to delete data from a program", "isCorrect": False},
            {"id": "q1-c", "label": "A tool for automatically compiling Python code", "isCorrect": False},
        ],
        "successMessage": "Correct. A variable stores a value that you can reference by name.",
        "errorMessage": "Incorrect. A variable stores data. It does not delete data or compile code.",
        "explanationMarkdown": "A variable is a named place in memory where Python stores a value.",
    },
    {
        "id": "q2",
        "prompt": "Which data type is used for text?",
        "options": [
            {"id": "q2-a", "label": "bool", "isCorrect": False},
            {"id": "q2-b", "label": "string", "isCorrect": True},
            {"id": "q2-c", "label": "float", "isCorrect": False},
        ],
        "successMessage": "Correct. Text uses the string type.",
        "errorMessage": "Incorrect. In Python, text is stored in a string (`string`).",
        "explanationMarkdown": "A string stores text. Example: `text = \"Hello\"`.",
    },
    {
        "id": "q3",
        "prompt": "Which function is used to print data to the screen?",
        "options": [
            {"id": "q3-a", "label": "show()", "isCorrect": False},
            {"id": "q3-b", "label": "print()", "isCorrect": True},
            {"id": "q3-c", "label": "echo()", "isCorrect": False},
        ],
        "successMessage": "Correct. The `print()` function outputs data to the console.",
        "errorMessage": "Incorrect. In Python, `print()` is used to display output.",
        "explanationMarkdown": "Example: `print(name)` will display the value stored in the variable `name`.",
    },
]


def _find_step_by_eyebrow(interactive_lesson: dict[str, Any], eyebrow: str) -> dict[str, Any] | None:
    target = str(eyebrow or "").strip().casefold()
    for step in interactive_lesson.get("steps") or []:
        if str(step.get("eyebrow") or "").strip().casefold() == target:
            return step
    return None


def apply_interactive_lesson_override(
    *,
    lesson_payload: dict[str, Any],
    interactive_lesson: dict[str, Any],
) -> dict[str, Any]:
    normalized_title = str(lesson_payload.get("title") or "").strip().casefold()
    if normalized_title != "getting started with python":
        return interactive_lesson

    payload = deepcopy(interactive_lesson)

    theory_step = _find_step_by_eyebrow(payload, "theory")
    if theory_step is not None:
        theory_step.update(
            {
                "title": "Welcome to Python",
                "description": "Orientation for the lesson and the first programming concepts you will use.",
                "contentMarkdown": GETTING_STARTED_WITH_PYTHON_THEORY_MARKDOWN,
            }
        )

    concept_step = _find_step_by_eyebrow(payload, "concept")
    if concept_step is not None:
        concept_step.update(
            {
                "title": "Variables and Data Types",
                "description": "Core lesson notes about variables, data types, print, and simple conditions.",
                "contentMarkdown": GETTING_STARTED_WITH_PYTHON_CONCEPT_MARKDOWN,
            }
        )

    quiz_step = _find_step_by_eyebrow(payload, "quiz")
    if quiz_step is not None:
        first_question = GETTING_STARTED_WITH_PYTHON_QUIZ_QUESTIONS[0]
        quiz_step.update(
            {
                "title": "Knowledge Check",
                "description": "Answer all quiz questions before moving to practice.",
                "contentMarkdown": "Check your understanding of variables, data types, and output.",
                "quiz": {
                    "prompt": first_question["prompt"],
                    "options": first_question["options"],
                    "questions": deepcopy(GETTING_STARTED_WITH_PYTHON_QUIZ_QUESTIONS),
                    "successMessage": "All answers are correct. You can move on to practice.",
                    "errorMessage": "There are still mistakes. Review the lesson and try again.",
                    "explanationMarkdown": "Focus on variables, strings, data types, and the `print()` function.",
                },
            }
        )

    practice_step = _find_step_by_eyebrow(payload, "practice")
    if practice_step is not None:
        practice_step.update(
            {
                "title": "Practice Lab",
                "description": "Write a short Python script and validate it automatically.",
                "contentMarkdown": GETTING_STARTED_WITH_PYTHON_PRACTICE_MARKDOWN,
                "practiceMode": "code_editor",
                "starterCode": GETTING_STARTED_WITH_PYTHON_STARTER_CODE,
                "hint": "Return the formatted string from `build_profile` first, then calculate `is_adult` by comparing the age.",
                "solution": GETTING_STARTED_WITH_PYTHON_SOLUTION,
                "grader": {
                    "type": "python_variable_check",
                    "expected_variables": {
                        "profile": "Anna (25)",
                        "is_adult": True,
                    },
                    "required_functions": ["build_profile"],
                    "expected_stdout": "Anna (25)\nTrue",
                },
            }
        )

    summary_step = _find_step_by_eyebrow(payload, "summary")
    if summary_step is not None:
        summary_step.update(
            {
                "title": "Wrap-Up",
                "description": "Reinforce why variables and data types matter before the next lesson.",
                "contentMarkdown": GETTING_STARTED_WITH_PYTHON_SUMMARY_MARKDOWN,
            }
        )

    payload["estimatedMinutes"] = 35
    payload["outcomes"] = [
        "Understand what a variable is and how it stores a value.",
        "Recognize the core data types: string, int, float, and bool.",
        "Use print() for output and if / else for simple logic.",
        "Write your first working Python script with automatic validation.",
    ]
    return payload
