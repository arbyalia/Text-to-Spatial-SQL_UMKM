"""Score benchmark results against gold SQL and write summary tables.

Example:
    python -m experiments.evaluate --dataset experiments/dataset/pilot_questions.jsonl \
        --results experiments/results/pilot.jsonl --out experiments/results/pilot_eval
"""

import argparse
import asyncio
import json
from pathlib import Path

import pandas as pd

from app.core.security import execute_ai_sql, validate_sql
from app.services.search_pipeline import json_safe
from experiments.metrics import cochran_q, compare_results, pairwise_mcnemar, percentile
from experiments.run_benchmark import load_jsonl


async def gold_results(questions: list[dict]) -> dict[str, list[dict]]:
    gold = {}
    for q in questions:
        if not q.get("gold_sql"):
            continue
        check = validate_sql(q["gold_sql"])
        if not check.valid:
            raise ValueError(f"gold SQL for {q['id']} rejected: {check.reason}")
        rows, _ = await execute_ai_sql(check.sql)
        gold[q["id"]] = [{k: json_safe(v) for k, v in r.items()} for r in rows]
    return gold


def score(questions: list[dict], results: list[dict], gold: dict) -> pd.DataFrame:
    by_id = {q["id"]: q for q in questions}
    rows = []
    for r in results:
        q = by_id.get(r["question_id"])
        if q is None:
            continue
        row = {
            "question_id": r["question_id"],
            "category": q.get("category"),
            "difficulty": q.get("difficulty"),
            "model": r["model"],
            "prompt_strategy": r["prompt_strategy"],
            "repeat": r["repeat"],
            "status": r["status"],
            "valid_sql": r["status"] in ("success", "db_execution_error"),
            "executed": r["status"] == "success",
            "json_strict": r.get("json_strict"),
            "llm_ms": r["latency"]["llm_ms"],
            "db_ms": r["latency"]["db_ms"],
            "total_ms": r["latency"]["total_ms"],
            "http_ms": r.get("http_ms"),
            "input_tokens": r.get("input_tokens"),
            "output_tokens": r.get("output_tokens"),
        }
        if q["id"] in gold:
            pred = r["data"] if r["status"] == "success" else []
            cmp = compare_results(pred, gold[q["id"]], q.get("order_matters", False))
            if r["status"] != "success":
                cmp.update(execution_match=False, precision=0.0, recall=0.0, f1=0.0)
            row.update(cmp)
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    def agg(g: pd.DataFrame) -> pd.Series:
        ok = g[g["status"] != "error"]
        return pd.Series(
            {
                "attempts": len(g),
                "execution_accuracy": g["execution_match"].mean()
                if "execution_match" in g
                else None,
                "mean_f1": g["f1"].mean() if "f1" in g else None,
                "valid_sql_rate": g["valid_sql"].mean(),
                "json_strict_rate": g["json_strict"].mean(),
                "llm_ms_median": percentile(ok["llm_ms"].tolist(), 0.5),
                "llm_ms_p95": percentile(ok["llm_ms"].tolist(), 0.95),
                "total_ms_median": percentile(ok["total_ms"].tolist(), 0.5),
                "total_ms_p95": percentile(ok["total_ms"].tolist(), 0.95),
                "db_ms_median": percentile(ok["db_ms"].dropna().tolist(), 0.5),
                "input_tokens_mean": g["input_tokens"].mean(),
                "output_tokens_mean": g["output_tokens"].mean(),
            }
        )

    return df.groupby(["model", "prompt_strategy"]).apply(agg, include_groups=False).reset_index()


def significance(df: pd.DataFrame) -> dict:
    """Majority-vote correctness per question (correct in more than half of the repeats).

    Models are compared per strategy, strategies per model.
    """
    out = {}
    for strategy, g in df.groupby("prompt_strategy"):
        votes = (
            g.groupby(["question_id", "model"])["execution_match"]
            .mean()
            .gt(0.5)
            .astype(int)
            .unstack()
        ).dropna()
        if votes.shape[1] < 2:
            continue
        out[strategy] = {
            "questions": len(votes),
            "cochran_q": cochran_q(votes.values.tolist()),
            "mcnemar": pairwise_mcnemar({m: votes[m].tolist() for m in votes.columns}),
        }
    strategies = sorted(df["prompt_strategy"].unique())
    if len(strategies) == 2:
        out["strategy_per_model"] = {}
        for model, g in df.groupby("model"):
            votes = (
                g.groupby(["question_id", "prompt_strategy"])["execution_match"]
                .mean()
                .gt(0.5)
                .astype(int)
                .unstack()
            ).dropna()
            if votes.shape[1] == 2:
                out["strategy_per_model"][model] = pairwise_mcnemar(
                    {s: votes[s].tolist() for s in votes.columns}
                )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    questions = load_jsonl(args.dataset)
    results = load_jsonl(args.results)
    gold = asyncio.run(gold_results(questions))
    df = score(questions, results, gold)
    if df.empty:
        print("no results to score")
        return

    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "attempts.csv", index=False)
    summary = summarize(df)
    summary.to_csv(args.out / "summary.csv", index=False)
    df.groupby(["model", "prompt_strategy", "status"]).size().unstack(fill_value=0).to_csv(
        args.out / "status_counts.csv"
    )
    if "execution_match" in df:
        df.pivot_table(
            index=["model", "prompt_strategy"], columns="category", values="execution_match"
        ).to_csv(args.out / "accuracy_by_category.csv")
        (args.out / "significance.json").write_text(json.dumps(significance(df), indent=2))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
