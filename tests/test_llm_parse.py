from types import SimpleNamespace

from app.services import llm_service
from app.services.llm_service import parse_sql_response
from app.services.model_registry import MODELS, ModelSpec


def test_strict_json():
    r = parse_sql_response('{"sql": "SELECT 1"}')
    assert r.sql == "SELECT 1" and r.json_strict and r.error is None


def test_fenced_json_is_repaired_but_flagged():
    r = parse_sql_response('```json\n{"sql": "SELECT 1"}\n```')
    assert r.sql == "SELECT 1" and not r.json_strict


def test_invalid_outputs():
    for content in (None, "", "SELECT 1", '{"query": "SELECT 1"}', '{"sql": ""}', "[1, 2]"):
        assert parse_sql_response(content).error == "invalid_json"


class _Recorder:
    def __init__(self, response):
        self.kwargs = None
        self.response = response

    async def __call__(self, **kwargs):
        self.kwargs = kwargs
        return self.response


async def test_shared_generation_params(monkeypatch):
    message = SimpleNamespace(content='{"sql": "SELECT 1"}')
    chat = _Recorder(SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None))
    gemini = _Recorder(SimpleNamespace(text='{"sql": "SELECT 1"}', usage_metadata=None))
    openai_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=chat)))
    models = SimpleNamespace(generate_content=gemini)
    gemini_client = SimpleNamespace(aio=SimpleNamespace(models=models))
    monkeypatch.setattr(llm_service, "_openai_client", lambda provider: openai_client)
    monkeypatch.setattr(llm_service, "_gemini_client", lambda: gemini_client)
    spec = ModelSpec(key="m", provider="groq", model_id="m")
    await llm_service._call_openai_compatible(spec, "s", "u")
    await llm_service._call_gemini(spec, "s", "u")

    assert chat.kwargs["temperature"] == 0
    assert chat.kwargs["max_completion_tokens"] == llm_service.MAX_OUTPUT_TOKENS == 1024
    assert chat.kwargs["seed"] == llm_service.SEED == 42
    config = gemini.kwargs["config"]
    assert config.temperature == 0
    assert config.max_output_tokens == 1024 and config.seed == 42


async def test_generate_sql_error_includes_cause(monkeypatch):
    async def failing_call(spec, system, user):
        try:
            raise ConnectionResetError("peer reset")
        except ConnectionResetError as cause:
            raise RuntimeError("Connection error.") from cause

    monkeypatch.setattr(llm_service, "_call_openai_compatible", failing_call)
    result = await llm_service.generate_sql(MODELS["gpt-oss-20b"], "system", "user")
    assert result.error == (
        "RuntimeError: Connection error. (cause: ConnectionResetError: peer reset)"
    )
