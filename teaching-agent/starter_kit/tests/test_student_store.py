from student_store import (
    connect, count_attempts, due_reviews, get_profile, get_state, mastery, record_attempt,
)


def test_mastery_formula():
    assert mastery(0, 0, 0, 0) == 0.0
    assert mastery(2, 2, 1, 1) == 0.8  # 0.4*0.5 + 0.4*1 + 0.2*1
    assert mastery(4, 4, 2, 1) == 1.0


def test_idempotent_attempt():
    conn = connect(":memory:")
    kwargs = dict(
        attempt_id="s1:q1", student_id="s1", kp_id="der.basic", question_id="q1",
        correct=True, layer="choice", is_variant=False,
    )
    assert record_attempt(conn, **kwargs) is True
    assert record_attempt(conn, **kwargs) is False
    assert count_attempts(conn, "s1") == 1
    assert get_state(conn, "s1", "der.basic")["attempts"] == 1


def test_wrong_answer_creates_mistake():
    conn = connect(":memory:")
    record_attempt(
        conn, attempt_id="s2:q1", student_id="s2", kp_id="der.basic", question_id="q1",
        correct=False, layer="choice", is_variant=False, answer="A", correct_answer="B",
    )
    profile = get_profile(conn, "s2")
    assert len(profile["mistakes"]) == 1
    assert profile["mistakes"][0]["correct_answer"] == "B"


def test_review_due():
    conn = connect(":memory:")
    record_attempt(
        conn, attempt_id="s3:q1", student_id="s3", kp_id="der.basic", question_id="q1",
        correct=True, layer="choice", is_variant=False, now=1000.0,
    )
    assert due_reviews(conn, "s3", now=1000.0) == []
    assert len(due_reviews(conn, "s3", now=1000.0 + 3 * 86400)) == 1
