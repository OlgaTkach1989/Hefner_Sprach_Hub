from __future__ import annotations

import os


def _resolve_default_language_model() -> str:
    raw_model = str(os.getenv("TRAINING_AI_CHAT_MODEL") or os.getenv("JUPYTER_AI_DEFAULT_MODEL") or "gpt-5-mini").strip()
    if ":" in raw_model:
        return raw_model
    return f"openai-chat:{raw_model}"


c = get_config()  # noqa: F821
default_language_model = _resolve_default_language_model()
c.AiMagics.default_language_model = default_language_model
