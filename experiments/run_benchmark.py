"""Run a question set against the API and append one JSON line per attempt.

Example:
    python -m experiments.run_benchmark --dataset experiments/dataset/pilot_questions.jsonl \
        --strategies zero_shot,few_shot --repeats 3 --out experiments/results/pilot.jsonl

Each request asks for a single model so models never compete for the network or
rate limit within one measurement. Finished attempts are skipped on rerun.
"""

import argparse
import json
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.core.config import settings

MAX_RATE_LIMIT_ATTEMPTS = 5
MAX_CONNECTION_RETRIES = 3
CONNECTION_RETRY_DELAY_S = 5


class RetriesExhausted(Exception):
    pass


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def request_attempt(
    client: httpx.Client, payload: dict, model: str, sleep: Callable[[float], None] = time.sleep
) -> tuple[dict, int, int]:
    """POST one attempt; return (response body, http_ms, connection_retries).

    Rate limits and provider connection failures (no answer from the model) are retried
    instead of being recorded as model answers.
    """
    rate_limited = connection_retries = 0
    while True:
        start = time.perf_counter()
        resp = client.post("/api/v1/search/ai", json=payload)
        http_ms = int((time.perf_counter() - start) * 1000)
        if resp.status_code == 429:
            rate_limited += 1
            if rate_limited >= MAX_RATE_LIMIT_ATTEMPTS:
                raise RetriesExhausted("still rate limited")
            sleep(int(resp.headers.get("Retry-After", 60)))
            continue
        resp.raise_for_status()
        body = resp.json()
        error = body["results"][model]["error_message"] or ""
        if "RateLimit" in error:
            rate_limited += 1
            if rate_limited >= MAX_RATE_LIMIT_ATTEMPTS:
                raise RetriesExhausted("still rate limited")
            sleep(20 * rate_limited)
            continue
        if error.startswith("APIConnectionError"):
            if connection_retries >= MAX_CONNECTION_RETRIES:
                raise RetriesExhausted(f"connection failed after {connection_retries} retries")
            connection_retries += 1
            sleep(CONNECTION_RETRY_DELAY_S)
            continue
        return body, http_ms, connection_retries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--models", default="", help="comma separated; default: API's enabled models"
    )
    parser.add_argument("--strategies", default="zero_shot,few_shot")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument(
        "--delay",
        type=float,
        default=12.0,
        help="seconds between requests (Groq free tier: 8K TPM)",
    )
    parser.add_argument("--api-url", default=settings.BACKEND_API_URL)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.repeats % 2 == 0:
        print(
            f"warning: --repeats {args.repeats} is even; majority vote can tie. "
            "Use an odd number (see docs/protokol_eksperimen.md)."
        )

    headers = {"X-API-Key": settings.API_KEY} if settings.API_KEY else {}
    client = httpx.Client(base_url=args.api_url, headers=headers, timeout=120)
    models = [m for m in args.models.split(",") if m] or [
        m["key"] for m in client.get("/api/v1/models").raise_for_status().json() if m["available"]
    ]
    strategies = [s for s in args.strategies.split(",") if s]
    questions = load_jsonl(args.dataset)

    done = {
        (r["question_id"], r["model"], r["prompt_strategy"], r["repeat"])
        for r in load_jsonl(args.out)
    }
    jobs = [
        (q, m, s, rep)
        for rep in range(1, args.repeats + 1)
        for q in questions
        for m in models
        for s in strategies
        if (q["id"], m, s, rep) not in done
    ]
    random.Random(args.seed).shuffle(jobs)
    print(f"{len(jobs)} attempts to run ({len(done)} already done)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a", encoding="utf-8") as out:
        for i, (q, model, strategy, rep) in enumerate(jobs, 1):
            payload = {
                "query": q["question"],
                "latitude": q.get("latitude"),
                "longitude": q.get("longitude"),
                "models": [model],
                "prompt_strategy": strategy,
            }
            try:
                body, http_ms, connection_retries = request_attempt(client, payload, model)
            except RetriesExhausted as e:
                print(f"{q['id']} {model} {strategy} r{rep}: {e}, skipped")
                continue
            result = body["results"][model]

            out.write(
                json.dumps(
                    {
                        "run_at": datetime.now(UTC).isoformat(),
                        "question_id": q["id"],
                        "category": q.get("category"),
                        "model": model,
                        "model_id": result["model_id"],
                        "prompt_strategy": strategy,
                        "prompt_version": body["prompt_version"],
                        "repeat": rep,
                        "http_ms": http_ms,
                        "connection_retries": connection_retries,
                        **{k: v for k, v in result.items() if k not in ("model", "model_id")},
                    },
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )
            out.flush()
            print(f"[{i}/{len(jobs)}] {q['id']} {model} {strategy} r{rep}: {result['status']}")
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
