import asyncio
import json
import re
import time
from dataclasses import dataclass
from functools import lru_cache

from google import genai
from google.genai import types as genai_types
from openai import AsyncOpenAI

from app.core.config import settings
from app.services.model_registry import ModelSpec, has_api_key

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)

BASE_URLS = {
    "groq": lambda: settings.GROQ_BASE_URL,
    "openai": lambda: "https://api.openai.com/v1",
    "deepseek": lambda: settings.DEEPSEEK_BASE_URL,
}


@dataclass
class LLMResponse:
    sql: str | None = None
    error: str | None = None
    json_strict: bool = False
    raw: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0


def parse_sql_response(content: str | None) -> LLMResponse:
    """Parse {"sql": ...} from model output; json_strict marks output that needed no repair."""
    if not content:
        return LLMResponse(error="invalid_json", raw=content)
    strict = True
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        strict = False
        match = _JSON_OBJECT.search(content)
        try:
            data = json.loads(match.group(0)) if match else None
        except json.JSONDecodeError:
            data = None
    sql = data.get("sql") if isinstance(data, dict) else None
    if not isinstance(sql, str) or not sql.strip():
        return LLMResponse(error="invalid_json", raw=content)
    return LLMResponse(sql=sql.strip(), json_strict=strict, raw=content)


@lru_cache
def _openai_client(provider: str) -> AsyncOpenAI:
    key = {
        "groq": settings.GROQ_API_KEY,
        "openai": settings.OPENAI_API_KEY,
        "deepseek": settings.DEEPSEEK_API_KEY,
    }[provider]
    return AsyncOpenAI(
        api_key=key, base_url=BASE_URLS[provider](), timeout=settings.LLM_TIMEOUT_S, max_retries=0
    )


@lru_cache
def _gemini_client() -> genai.Client:
    return genai.Client(api_key=settings.GEMINI_API_KEY)


async def _call_openai_compatible(spec: ModelSpec, system: str, user: str) -> LLMResponse:
    response = await _openai_client(spec.provider).chat.completions.create(
        model=spec.model_id,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0,
        response_format={"type": "json_object"},
        extra_body=spec.params or None,
    )
    result = parse_sql_response(response.choices[0].message.content)
    if response.usage:
        result.input_tokens = response.usage.prompt_tokens
        result.output_tokens = response.usage.completion_tokens
    return result


async def _call_gemini(spec: ModelSpec, system: str, user: str) -> LLMResponse:
    config = genai_types.GenerateContentConfig(
        system_instruction=system,
        temperature=0,
        response_mime_type="application/json",
        thinking_config=genai_types.ThinkingConfig(**spec.params) if spec.params else None,
    )
    response = await asyncio.wait_for(
        _gemini_client().aio.models.generate_content(
            model=spec.model_id, contents=user, config=config
        ),
        timeout=settings.LLM_TIMEOUT_S,
    )
    result = parse_sql_response(response.text)
    if response.usage_metadata:
        result.input_tokens = response.usage_metadata.prompt_token_count
        result.output_tokens = response.usage_metadata.candidates_token_count
    return result


async def generate_sql(spec: ModelSpec, system: str, user: str) -> LLMResponse:
    """Call one model and measure its wall-clock latency."""
    if not has_api_key(spec):
        return LLMResponse(error="model unavailable: no API key")
    call = _call_gemini if spec.provider == "gemini" else _call_openai_compatible
    start = time.perf_counter()
    try:
        result = await call(spec, system, user)
    except TimeoutError:
        result = LLMResponse(error="timeout")
    except Exception as e:
        result = LLMResponse(error=f"{e.__class__.__name__}: {str(e)[:200]}")
    result.latency_ms = int((time.perf_counter() - start) * 1000)
    return result
