from decimal import Decimal

from experiments.metrics import cochran_q, compare_results, mcnemar_exact

GOLD = [{"id": 1, "jarak_meter": 10.0}, {"id": 2, "jarak_meter": 20.0}]


def test_id_match_ignores_extra_columns_and_order():
    pred = [{"id": 2, "nama": "b"}, {"id": 1, "nama": "a"}]
    assert compare_results(pred, GOLD)["execution_match"]
    assert not compare_results(pred, GOLD, order_matters=True)["execution_match"]


def test_partial_match_scores():
    r = compare_results([{"id": 1}, {"id": 3}], GOLD)
    assert not r["execution_match"]
    assert r["precision"] == 0.5 and r["recall"] == 0.5


def test_row_match_without_id():
    assert compare_results([{"total": 19}], [{"jumlah": 19}])["execution_match"]
    assert compare_results([{"avg": 4.7412}], [{"rata": 4.74}])["execution_match"]
    assert not compare_results([{"total": 18}], [{"jumlah": 19}])["execution_match"]


def test_numbers_normalized_across_types():
    assert compare_results([{"total": 19}], [{"jumlah": 19.0}])["execution_match"]
    assert compare_results([{"avg": Decimal("4.741")}], [{"rata": 4.74}])["execution_match"]
    assert compare_results([{"n": 3, "r": Decimal("4.50")}], [{"r": 4.5, "n": 3.0}])[
        "execution_match"
    ]
    assert not compare_results([{"flag": True}], [{"flag": 1}])["execution_match"]


def test_empty_results():
    assert compare_results([], [])["execution_match"]
    assert compare_results([], GOLD)["recall"] == 0


def test_statistics():
    assert cochran_q([[1, 1], [0, 0]])["p_value"] == 1.0
    assert mcnemar_exact([1] * 10, [0] * 10)["p_value"] < 0.01
