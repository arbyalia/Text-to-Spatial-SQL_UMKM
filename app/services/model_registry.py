from dataclasses import dataclass, field
from typing import Literal

from app.core.config import settings


@dataclass(frozen=True)
class ModelSpec:
    key: str
    provider: Literal["groq", "gemini", "openai", "deepseek"]
    model_id: str
    params: dict = field(default_factory=dict)
    note: str = ""


MODELS: dict[str, ModelSpec] = {
    spec.key: spec
    for spec in (
        ModelSpec(
            "qwen3.8-27b",
            "groq",
            "qwen/qwen3.8-27b",
            {"reasoning_effort": "none"},
            note="reasoning disabled",
        ),
        ModelSpec(
            "gpt-oss-120b",
            "groq",
            "openai/gpt-oss-120b",
            {"reasoning_effort": "low", "include_reasoning": False},
            note="reasoning cannot be disabled; lowest effort",
        ),
        ModelSpec(
            "gpt-oss-20b",
            "groq",
            "openai/gpt-oss-20b",
            {"reasoning_effort": "low", "include_reasoning": False},
            note="reasoning cannot be disabled; lowest effort",
        ),
        ModelSpec(
            "gemini-flash",
            "gemini",
            "gemini-3-flash-preview",
            {"thinking_level": "minimal"},
            note="minimal thinking",
        ),
        ModelSpec("gpt-4o-mini", "openai", "gpt-4o-mini"),
        ModelSpec(
            "deepseek",
            "deepseek",
            "deepseek-v4-flash",
            {"thinking": {"type": "disabled"}},
            note="thinking disabled",
        ),
    )
}

PROVIDER_KEYS = {
    "groq": lambda: settings.GROQ_API_KEY,
    "gemini": lambda: settings.GEMINI_API_KEY,
    "openai": lambda: settings.OPENAI_API_KEY,
    "deepseek": lambda: settings.DEEPSEEK_API_KEY,
}


def enabled_models() -> list[ModelSpec]:
    return [MODELS[key] for key in settings.enabled_models if key in MODELS]


def has_api_key(spec: ModelSpec) -> bool:
    return bool(PROVIDER_KEYS[spec.provider]())
