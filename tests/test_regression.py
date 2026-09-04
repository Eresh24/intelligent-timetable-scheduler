"""
Regression tests for the Intelligent Timetable Scheduler.

Each test below documents a real defect found during development (Task 2/3),
reproduces the exact failing scenario, and asserts the corrected behaviour.
Both entries were found by manual code review AFTER the full official suite
(test_scheduler.py) was already green — the official suite did not catch
either one, which is itself documented as a testing-gap finding in Task 3.
"""

from scheduler import Room, Lecturer, Course, generate_timetable

ALL_SLOTS = [f"{day}-{p}" for day in ("Mon", "Tue", "Wed", "Thu", "Fri") for p in range(1, 9)]


def test_regression_prerequisite_ordering_independent_of_input_list_order():
    """
    Bug: the first working draft scheduled courses in whatever order they
    appeared in the input list, with no topological sort. The official test
    (test_prerequisite_scheduled_before_dependent) happened to list the
    prerequisite before the dependent, so it passed even though prerequisite
    ordering was not actually enforced anywhere in the algorithm.
    Found: manual review — reversing the input list order (dependent listed
    before its prerequisite) produced a schedule that violated FR11.
    Fix: added `_topological_order()` so prerequisites are always processed
    (and therefore assigned) before their dependents, regardless of input
    list order, plus an explicit `min_start_index` constraint per course.
    """
    rooms = [Room(id="R1", capacity=30), Room(id="R2", capacity=30)]
    lecturers = [Lecturer(id="L1", name="Dr Smith", available_slots=set(ALL_SLOTS))]
    # Dependent ("B") deliberately listed BEFORE its prerequisite ("A").
    courses = [
        Course(id="B", name="Advanced", lecturer_id="L1", enrolled_students=10,
               prerequisite_ids=["A"]),
        Course(id="A", name="Foundations", lecturer_id="L1", enrolled_students=10),
    ]
    result = generate_timetable(courses, rooms, lecturers, ALL_SLOTS)
    assert result.is_feasible
    index_a = ALL_SLOTS.index(result.assignments["A"][1])
    index_b = ALL_SLOTS.index(result.assignments["B"][1])
    assert index_a < index_b


def test_regression_adversarial_infeasible_case_does_not_time_out():
    """
    Bug: the naive backtracking draft had no early exit for obviously
    overcommitted instances. A single lecturer with 15 usable slots given
    20 courses (all requiring that lecturer) forced the search to exhaust
    an exponential number of dead-end branches before concluding
    infeasibility — measured at >15 seconds (test timed out) against the
    NFR1 target of <10s for much larger (50-course) instances.
    Found: manual NFR1 performance testing with an adversarial, tightly
    overcommitted scenario (not covered by the official suite, whose
    infeasible cases are all small).
    Fix: added a cheap O(n) necessary-condition pre-check (room capacity
    and per-lecturer slot-vs-course counts) that short-circuits before the
    expensive search when it can already prove infeasibility. This is not
    a complete fix for every adversarial shape, just the specific pattern
    found — see the Reflection section for the remaining limitation.
    """
    import time
    rooms = [Room(id=f"R{i}", capacity=30) for i in range(5)]
    lecturers = [Lecturer(id="L1", name="Dr Solo", available_slots=set(ALL_SLOTS[:15]))]
    courses = [Course(id=f"C{i}", name=f"Course {i}", lecturer_id="L1", enrolled_students=10)
               for i in range(20)]

    start = time.perf_counter()
    result = generate_timetable(courses, rooms, lecturers, ALL_SLOTS)
    elapsed = time.perf_counter() - start

    assert not result.is_feasible
    assert elapsed < 2.0  # was >15s (timeout) before the fix; now near-instant
    assert any("L1" in c for c in result.conflicts)


def test_regression_quality_score_reflects_unmet_preferences():
    """
    Bug: the first working draft returned a hard-coded quality_score of 1.0
    on every feasible result, regardless of whether any preferred slot was
    actually used. The official test for preferred slots
    (test_preferred_slot_honoured_when_no_conflict) only covers the case
    where the preference IS honoured, so it could not have caught this.
    Found: manual review — constructing a case where the preference cannot
    possibly be honoured (lecturer only free at a different slot) still
    reported quality_score == 1.0.
    Fix: quality_score is now computed from the actual assignments as
    (courses whose assigned slot matches a stated preference) / (courses
    that stated a preference at all).
    """
    rooms = [Room(id="R1", capacity=30)]
    lecturers = [Lecturer(id="L1", name="Dr Rare", available_slots={"Wed-3"})]
    courses = [Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10,
                       preferred_slots=["Mon-1"])]
    result = generate_timetable(courses, rooms, lecturers, ALL_SLOTS)
    assert result.is_feasible
    assert result.assignments["C1"] == ("R1", "Wed-3")
    assert result.quality_score == 0.0
