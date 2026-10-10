import math
from collections import Counter
from itertools import combinations


def _norm(value):
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _row_key(row: dict) -> tuple:
    return tuple(sorted(repr(_norm(v)) for v in row.values()))


def compare_results(pred: list[dict], gold: list[dict], order_matters: bool = False) -> dict:
    """Execution-based comparison between predicted and gold result rows.

    Rows with an `id` column are compared by UMKM id (extra columns ignored);
    otherwise rows are compared as multisets of their values, ignoring column names and order.
    """
    use_id = bool(gold) and all("id" in r for r in gold) and all("id" in r for r in pred)
    if use_id:
        pred_keys = [r["id"] for r in pred]
        gold_keys = [r["id"] for r in gold]
    else:
        pred_keys = [_row_key(r) for r in pred]
        gold_keys = [_row_key(r) for r in gold]

    pred_count, gold_count = Counter(pred_keys), Counter(gold_keys)
    overlap = sum((pred_count & gold_count).values())
    precision = overlap / len(pred_keys) if pred_keys else float(not gold_keys)
    recall = overlap / len(gold_keys) if gold_keys else float(not pred_keys)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    exact = pred_keys == gold_keys if order_matters else pred_count == gold_count
    return {
        "match_by": "id" if use_id else "rows",
        "execution_match": exact,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def _chi2_sf(x: float, df: int) -> float:
    """Survival function of the chi-square distribution (regularized upper gamma)."""
    a, z = df / 2, x / 2
    if z <= 0:
        return 1.0
    if z < a + 1:
        term = total = 1 / a
        n = a
        for _ in range(500):
            n += 1
            term *= z / n
            total += term
        return max(0.0, 1 - total * math.exp(-z + a * math.log(z) - math.lgamma(a)))
    b, c, d = z + 1 - a, 1e300, 1 / (z + 1 - a)
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1 / d if abs(d) > 1e-300 else 1e300
        c = b + an / c if abs(c) > 1e-300 else 1e-300
        h *= d * c
    return math.exp(-z + a * math.log(z) - math.lgamma(a)) * h


def cochran_q(table: list[list[int]]) -> dict:
    """Cochran's Q test; rows are questions, columns are models (1 = correct)."""
    k = len(table[0]) if table else 0
    if k < 2:
        return {"q": None, "df": None, "p_value": None}
    col = [sum(r[j] for r in table) for j in range(k)]
    row = [sum(r) for r in table]
    n_total = sum(row)
    denom = k * n_total - sum(r * r for r in row)
    if denom == 0:
        return {"q": 0.0, "df": k - 1, "p_value": 1.0}
    q = (k - 1) * (k * sum(c * c for c in col) - n_total**2) / denom
    return {"q": q, "df": k - 1, "p_value": _chi2_sf(q, k - 1)}


def mcnemar_exact(a: list[int], b: list[int]) -> dict:
    """Exact two-sided McNemar test on paired binary outcomes."""
    only_a = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    only_b = sum(1 for x, y in zip(a, b, strict=True) if y and not x)
    n = only_a + only_b
    if n == 0:
        return {"only_a": 0, "only_b": 0, "p_value": 1.0}
    k = min(only_a, only_b)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return {"only_a": only_a, "only_b": only_b, "p_value": min(1.0, 2 * p)}


def pairwise_mcnemar(outcomes: dict[str, list[int]]) -> list[dict]:
    return [
        {"model_a": a, "model_b": b, **mcnemar_exact(outcomes[a], outcomes[b])}
        for a, b in combinations(sorted(outcomes), 2)
    ]
