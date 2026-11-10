"""显式学生模型测试：掌握度、错题本、跨会话读取。"""

from __future__ import annotations

from core.student import (
    get_profile,
    mastery,
    record_attempt,
    record_mistake,
    resolve_mistake,
)


def test_mastery_cold_start_is_not_certain():
    # 0 次尝试时不应该显示 100% 掌握
    assert mastery(0, 0) == 0.5
    assert mastery(3, 3) < 1.0
    assert mastery(10, 10) > mastery(3, 3)


def test_attempt_accumulates(student_conn):
    for _ in range(3):
        record_attempt(student_conn, student_id="s1", subject="数学一", kp="导数", correct=True)

    profile = get_profile(student_conn, student_id="s1", subject="数学一")
    kp = profile.kps[0]
    assert kp["attempts"] == 3
    assert kp["correct"] == 3
    assert kp["mastery"] > 0.5


def test_mistake_record_and_resolve(student_conn):
    record_attempt(student_conn, student_id="s1", subject="数学一", kp="导数", correct=False)
    record_mistake(
        student_conn,
        student_id="s1",
        subject="数学一",
        kp="导数",
        question="平均速度是多少？",
        student_answer="2",
        correct_answer="0.5",
    )

    profile = get_profile(student_conn, student_id="s1", subject="数学一")
    assert len(profile.mistakes) == 1
    assert profile.mistakes[0]["kp"] == "导数"
    assert profile.weak_points == ["导数"]

    changed = resolve_mistake(student_conn, student_id="s1", subject="数学一", kp="导数")
    assert changed == 1
    profile = get_profile(student_conn, student_id="s1", subject="数学一")
    assert profile.mistakes[0]["resolved_at"] is not None


def test_profile_is_namespaced_by_student_and_subject(student_conn):
    record_attempt(student_conn, student_id="s1", subject="数学一", kp="导数", correct=True)
    record_attempt(student_conn, student_id="s2", subject="数学一", kp="极限", correct=False)
    record_attempt(student_conn, student_id="s1", subject="物理", kp="速度", correct=True)

    p1 = get_profile(student_conn, student_id="s1", subject="数学一")
    p2 = get_profile(student_conn, student_id="s2", subject="数学一")
    p3 = get_profile(student_conn, student_id="s1", subject="物理")

    assert [k["kp"] for k in p1.kps] == ["导数"]
    assert [k["kp"] for k in p2.kps] == ["极限"]
    assert [k["kp"] for k in p3.kps] == ["速度"]
