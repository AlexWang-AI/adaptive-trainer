from eval_passk import run_once


def test_correct_case_agreement():
    case = {"id": "case-ok", "kp_id": "der.basic", "answers": ["B", "2x"], "expected": [True, True]}
    result = run_once(case, mutate=False)
    assert result["agreement"] == 1.0


def test_wrong_case_agreement():
    case = {"id": "case-bad", "kp_id": "der.basic", "answers": ["A", "2x"], "expected": [False, True]}
    result = run_once(case, mutate=False)
    assert result["agreement"] == 1.0


def test_independent_key_survives_mutation():
    case = {"id": "case-mut", "kp_id": "der.basic", "answers": ["B", "2x"], "expected": [True, True]}
    result = run_once(case, mutate=True)
    assert result["agreement"] == 1.0
