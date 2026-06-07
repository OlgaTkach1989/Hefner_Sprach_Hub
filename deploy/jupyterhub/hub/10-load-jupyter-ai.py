from __future__ import annotations

import os

from IPython import get_ipython


def _resolve_default_language_model() -> str:
    raw_model = str(
        os.getenv("TRAINING_AI_CHAT_MODEL")
        or os.getenv("JUPYTER_AI_DEFAULT_MODEL")
        or "gpt-5-mini"
    ).strip()
    if ":" in raw_model:
        return raw_model
    return f"openai-chat:{raw_model}"


def _load_jupyter_ai_magics() -> None:
    shell = get_ipython()
    if shell is None:
        return
    try:
        shell.run_line_magic("load_ext", "jupyter_ai_magics")
    except Exception:
        # Do not break kernel startup if the extension cannot be loaded.
        return

    magic = shell.find_cell_magic("ai")
    owner = getattr(magic, "__self__", None)
    if owner is None or not hasattr(owner, "default_language_model"):
        return

    if not getattr(owner, "default_language_model", None):
        owner.default_language_model = _resolve_default_language_model()


_load_jupyter_ai_magics()
