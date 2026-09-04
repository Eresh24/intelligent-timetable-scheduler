"""
Initial automated test suite for the Intelligent Timetable Scheduler.

Written BEFORE any implementation exists (Task 1 of the AI-TDD workflow).
These tests are expected to fail with an ImportError / collection error until
`scheduler.py` (Task 2) provides:

    Room, Lecturer, Course, ScheduleResult, InvalidInputError, generate_timetable

Test IDs in the docstrings (EB#, BC#, II#) cross-reference the tables in
Task1_Requirements_and_Test_Design.md.
"""

import pytest

from scheduler import (
    Room,
    Lecturer,
    Course,
    generate_timetable,
    InvalidInputError,
)

ALL_SLOTS = [f"{day}-{p}" for day in ("Mon", "Tue", "Wed", "Thu", "Fri") for p in range(1, 9)]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def one_room():
    return [Room(id="R1", capacity=30, room_type="standard")]


@pytest.fixture
def two_rooms():
    return [
        Room(id="R1", capacity=30, room_type="standard"),
        Room(id="R2", capacity=20, room_type="standard"),
    ]


@pytest.fixture
def one_lecturer_full_availability():
    return [Lecturer(id="L1", name="Dr Smith", available_slots=set(ALL_SLOTS))]


# ---------------------------------------------------------------------------
# 1. Normal behaviour
# ---------------------------------------------------------------------------

def test_single_course_gets_assigned(one_room, one_lecturer_full_availability):
    """EB1: a small valid input with no shared resources — every course is assigned."""
    courses = [Course(id="C1", name="Intro CS", lecturer_id="L1", enrolled_students=25)]
    result = generate_timetable(courses, one_room, one_lecturer_full_availability, ALL_SLOTS)
    assert result.is_feasible
    assert "C1" in result.assignments


def test_same_lecturer_never_double_booked(two_rooms):
    """EB2: two courses with the same lecturer never share a time slot."""
    lecturers = [Lecturer(id="L1", name="Dr Smith", available_slots=set(ALL_SLOTS))]
    courses = [
        Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10),
        Course(id="C2", name="Course B", lecturer_id="L1", enrolled_students=10),
    ]
    result = generate_timetable(courses, two_rooms, lecturers, ALL_SLOTS)
    assert result.is_feasible
    _, slot_a = result.assignments["C1"]
    _, slot_b = result.assignments["C2"]
    assert slot_a != slot_b


def test_two_courses_never_share_room_and_slot(one_room, two_rooms):
    """EB3: courses competing for rooms are never both given the same room+slot."""
    lecturers = [
        Lecturer(id="L1", name="Dr Smith", available_slots=set(ALL_SLOTS)),
        Lecturer(id="L2", name="Dr Lee", available_slots=set(ALL_SLOTS)),
    ]
    courses = [
        Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10),
        Course(id="C2", name="Course B", lecturer_id="L2", enrolled_students=10),
    ]
    result = generate_timetable(courses, one_room, lecturers, ALL_SLOTS)
    assert result.is_feasible
    assert result.assignments["C1"] != result.assignments["C2"]


def test_prerequisite_scheduled_before_dependent(two_rooms, one_lecturer_full_availability):
    """EB6: a prerequisite course's slot index precedes its dependent's slot index."""
    courses = [
        Course(id="A", name="Foundations", lecturer_id="L1", enrolled_students=10),
        Course(id="B", name="Advanced", lecturer_id="L1", enrolled_students=10,
               prerequisite_ids=["A"]),
    ]
    result = generate_timetable(courses, two_rooms, one_lecturer_full_availability, ALL_SLOTS)
    assert result.is_feasible
    _, slot_a = result.assignments["A"]
    _, slot_b = result.assignments["B"]
    assert ALL_SLOTS.index(slot_a) < ALL_SLOTS.index(slot_b)


def test_preferred_slot_honoured_when_no_conflict(one_room, one_lecturer_full_availability):
    """EB7: a non-conflicting preferred slot is actually used."""
    courses = [Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10,
                       preferred_slots=["Mon-1"])]
    result = generate_timetable(courses, one_room, one_lecturer_full_availability, ALL_SLOTS)
    assert result.is_feasible
    _, slot = result.assignments["C1"]
    assert slot == "Mon-1"
    assert result.quality_score == 1.0


def test_deterministic_across_runs(two_rooms, one_lecturer_full_availability):
    """EB9: identical input produces identical feasibility and quality score."""
    courses = [
        Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10),
        Course(id="C2", name="Course B", lecturer_id="L1", enrolled_students=10),
    ]
    r1 = generate_timetable(courses, two_rooms, one_lecturer_full_availability, ALL_SLOTS)
    r2 = generate_timetable(courses, two_rooms, one_lecturer_full_availability, ALL_SLOTS)
    assert r1.is_feasible == r2.is_feasible
    assert r1.quality_score == r2.quality_score


def test_empty_course_list_is_trivially_feasible(one_room, one_lecturer_full_availability):
    """EB10: zero courses -> feasible with an empty assignment map."""
    result = generate_timetable([], one_room, one_lecturer_full_availability, ALL_SLOTS)
    assert result.is_feasible
    assert result.assignments == {}


# ---------------------------------------------------------------------------
# 2. Boundary conditions
# ---------------------------------------------------------------------------

def test_capacity_exactly_equals_enrolled(one_room, one_lecturer_full_availability):
    """BC1: room capacity == enrolled students must be accepted."""
    courses = [Course(id="C1", name="Full Room", lecturer_id="L1", enrolled_students=30)]
    result = generate_timetable(courses, one_room, one_lecturer_full_availability, ALL_SLOTS)
    assert result.is_feasible


def test_capacity_one_below_enrolled_is_rejected(one_room, one_lecturer_full_availability):
    """BC2: room capacity == enrolled students - 1 must not use that room / must be infeasible."""
    courses = [Course(id="C1", name="Overfull", lecturer_id="L1", enrolled_students=31)]
    result = generate_timetable(courses, one_room, one_lecturer_full_availability, ALL_SLOTS)
    assert not result.is_feasible
    assert any("C1" in c for c in result.conflicts)


def test_last_slot_of_week_is_usable(one_room, one_lecturer_full_availability):
    """BC3: a course confined to the last slot of the week can still be scheduled."""
    courses = [Course(id="C1", name="Late Friday", lecturer_id="L1", enrolled_students=10,
                       preferred_slots=["Fri-8"])]
    result = generate_timetable(courses, one_room, one_lecturer_full_availability, ["Fri-8"])
    assert result.is_feasible
    assert result.assignments["C1"] == ("R1", "Fri-8")


def test_lecturer_with_single_available_slot(one_room):
    """BC4: a lecturer available for exactly one slot constrains the course to that slot."""
    lecturers = [Lecturer(id="L1", name="Dr Rare", available_slots={"Wed-3"})]
    courses = [Course(id="C1", name="Rare Course", lecturer_id="L1", enrolled_students=10)]
    result = generate_timetable(courses, one_room, lecturers, ALL_SLOTS)
    assert result.is_feasible
    assert result.assignments["C1"] == ("R1", "Wed-3")


def test_multi_slot_course_does_not_spill_past_day_end(one_room, one_lecturer_full_availability):
    """BC7: a 2-slot course cannot be placed starting at the last period of a day."""
    courses = [Course(id="C1", name="Double Period", lecturer_id="L1", enrolled_students=10,
                       duration_slots=2, preferred_slots=["Fri-8"])]
    result = generate_timetable(courses, one_room, one_lecturer_full_availability, ALL_SLOTS)
    if result.is_feasible:
        _, slot = result.assignments["C1"]
        assert slot != "Fri-8"


# ---------------------------------------------------------------------------
# 3. Invalid inputs
# ---------------------------------------------------------------------------

def test_zero_capacity_room_is_rejected(one_lecturer_full_availability):
    """II1: a room with capacity <= 0 is invalid input."""
    rooms = [Room(id="R1", capacity=0, room_type="standard")]
    courses = [Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10)]
    with pytest.raises(InvalidInputError):
        generate_timetable(courses, rooms, one_lecturer_full_availability, ALL_SLOTS)


def test_zero_enrolled_students_is_rejected(one_room, one_lecturer_full_availability):
    """II2: a course with enrolled_students <= 0 is invalid input."""
    courses = [Course(id="C1", name="Empty Course", lecturer_id="L1", enrolled_students=0)]
    with pytest.raises(InvalidInputError):
        generate_timetable(courses, one_room, one_lecturer_full_availability, ALL_SLOTS)


def test_unknown_lecturer_reference_is_rejected(one_room, one_lecturer_full_availability):
    """II3: a course referencing a nonexistent lecturer_id is invalid input."""
    courses = [Course(id="C1", name="Orphan Course", lecturer_id="L99", enrolled_students=10)]
    with pytest.raises(InvalidInputError):
        generate_timetable(courses, one_room, one_lecturer_full_availability, ALL_SLOTS)


def test_no_room_matches_required_type_is_rejected(one_room, one_lecturer_full_availability):
    """II4: a course requiring a room type that no room provides is invalid input."""
    courses = [Course(id="C1", name="Lab Course", lecturer_id="L1", enrolled_students=10,
                       required_room_type="lab")]
    with pytest.raises(InvalidInputError):
        generate_timetable(courses, one_room, one_lecturer_full_availability, ALL_SLOTS)


def test_circular_prerequisite_is_rejected(two_rooms, one_lecturer_full_availability):
    """II5: a circular prerequisite chain (A -> B -> A) is invalid input."""
    courses = [
        Course(id="A", name="Course A", lecturer_id="L1", enrolled_students=10,
               prerequisite_ids=["B"]),
        Course(id="B", name="Course B", lecturer_id="L1", enrolled_students=10,
               prerequisite_ids=["A"]),
    ]
    with pytest.raises(InvalidInputError):
        generate_timetable(courses, two_rooms, one_lecturer_full_availability, ALL_SLOTS)


def test_duplicate_course_ids_are_rejected(one_room, one_lecturer_full_availability):
    """II6: duplicate course IDs in the input list are invalid input."""
    courses = [
        Course(id="C1", name="First", lecturer_id="L1", enrolled_students=10),
        Course(id="C1", name="Duplicate", lecturer_id="L1", enrolled_students=10),
    ]
    with pytest.raises(InvalidInputError):
        generate_timetable(courses, one_room, one_lecturer_full_availability, ALL_SLOTS)


def test_unknown_prerequisite_reference_is_rejected(one_room, one_lecturer_full_availability):
    """II7: a prerequisite_id that doesn't match any course is invalid input."""
    courses = [Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10,
                       prerequisite_ids=["GHOST"])]
    with pytest.raises(InvalidInputError):
        generate_timetable(courses, one_room, one_lecturer_full_availability, ALL_SLOTS)


def test_lecturer_with_no_availability_is_rejected(one_room):
    """II8: a lecturer with an empty available_slots set is invalid input."""
    lecturers = [Lecturer(id="L1", name="Dr Busy", available_slots=set())]
    courses = [Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10)]
    with pytest.raises(InvalidInputError):
        generate_timetable(courses, one_room, lecturers, ALL_SLOTS)


def test_missing_rooms_list_is_rejected(one_lecturer_full_availability):
    """II9: an empty rooms list while courses is non-empty is invalid input."""
    courses = [Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10)]
    with pytest.raises(InvalidInputError):
        generate_timetable(courses, [], one_lecturer_full_availability, ALL_SLOTS)


def test_missing_lecturers_list_is_rejected(one_room):
    """Added after coverage review: mirror of II9 for an empty lecturers list."""
    courses = [Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10)]
    with pytest.raises(InvalidInputError):
        generate_timetable(courses, one_room, [], ALL_SLOTS)


def test_duplicate_room_ids_are_rejected(one_lecturer_full_availability):
    """Added after coverage review: duplicate room IDs are invalid input."""
    rooms = [Room(id="R1", capacity=30), Room(id="R1", capacity=20)]
    courses = [Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10)]
    with pytest.raises(InvalidInputError):
        generate_timetable(courses, rooms, one_lecturer_full_availability, ALL_SLOTS)


def test_duplicate_lecturer_ids_are_rejected(one_room):
    """Added after coverage review: duplicate lecturer IDs are invalid input."""
    lecturers = [
        Lecturer(id="L1", name="Dr Smith", available_slots=set(ALL_SLOTS)),
        Lecturer(id="L1", name="Dr Clone", available_slots=set(ALL_SLOTS)),
    ]
    courses = [Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10)]
    with pytest.raises(InvalidInputError):
        generate_timetable(courses, one_room, lecturers, ALL_SLOTS)


def test_zero_duration_slots_is_rejected(one_room, one_lecturer_full_availability):
    """Added after coverage review: duration_slots <= 0 is invalid input."""
    courses = [Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10,
                       duration_slots=0)]
    with pytest.raises(InvalidInputError):
        generate_timetable(courses, one_room, one_lecturer_full_availability, ALL_SLOTS)


# ---------------------------------------------------------------------------
# 4. Exceptional cases (valid input, no feasible solution)
# ---------------------------------------------------------------------------

def test_no_room_big_enough_is_reported_not_raised(one_room, one_lecturer_full_availability):
    """EB4: a course too large for every room is infeasible, not an exception."""
    courses = [Course(id="C1", name="Huge Course", lecturer_id="L1", enrolled_students=999)]
    result = generate_timetable(courses, one_room, one_lecturer_full_availability, ALL_SLOTS)
    assert not result.is_feasible
    assert any("C1" in c for c in result.conflicts)


def test_single_slot_lecturer_double_booked_is_infeasible(one_room):
    """EB5: two courses needing the same single-slot lecturer -> infeasible, no exception."""
    lecturers = [Lecturer(id="L1", name="Dr Rare", available_slots={"Wed-3"})]
    courses = [
        Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10),
        Course(id="C2", name="Course B", lecturer_id="L1", enrolled_students=10),
    ]
    result = generate_timetable(courses, one_room, lecturers, ALL_SLOTS)
    assert not result.is_feasible


def test_unsatisfiable_hard_constraints_do_not_raise(one_room, one_lecturer_full_availability):
    """EB12: an unsatisfiable but valid scenario returns is_feasible=False, never raises."""
    courses = [
        Course(id="C1", name="Course A", lecturer_id="L1", enrolled_students=10),
        Course(id="C2", name="Course B", lecturer_id="L1", enrolled_students=10),
        Course(id="C3", name="Course C", lecturer_id="L1", enrolled_students=10),
    ]
    lecturers = [Lecturer(id="L1", name="Dr Solo", available_slots={"Mon-1", "Mon-2"})]
    # 3 courses, same lecturer, only 2 available slots -> guaranteed infeasible.
    try:
        result = generate_timetable(courses, one_room, lecturers, ALL_SLOTS)
    except InvalidInputError:
        pytest.fail("Infeasibility must be reported via ScheduleResult, not InvalidInputError")
    assert not result.is_feasible
