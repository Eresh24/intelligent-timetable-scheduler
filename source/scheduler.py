"""
Intelligent Timetable Scheduler — core module.

Implements the data model and input validation described in
Task1_Requirements_and_Test_Design.md, Sections 2, 5, 8-9.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Set, Optional


class InvalidInputError(ValueError):
    """Raised when scheduler input is structurally invalid, before scheduling starts."""


@dataclass
class Room:
    id: str
    capacity: int
    room_type: str = "standard"


@dataclass
class Lecturer:
    id: str
    name: str
    available_slots: Set[str] = field(default_factory=set)


@dataclass
class Course:
    id: str
    name: str
    lecturer_id: str
    enrolled_students: int
    duration_slots: int = 1
    required_room_type: str = "standard"
    prerequisite_ids: List[str] = field(default_factory=list)
    preferred_slots: List[str] = field(default_factory=list)


@dataclass
class ScheduleResult:
    is_feasible: bool
    assignments: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    conflicts: List[str] = field(default_factory=list)
    quality_score: float = 0.0


def _validate_input(courses: List[Course], rooms: List[Room],
                     lecturers: List[Lecturer], timeslots: List[str]) -> None:
    if courses and not rooms:
        raise InvalidInputError("Courses were provided but no rooms were supplied.")
    if courses and not lecturers:
        raise InvalidInputError("Courses were provided but no lecturers were supplied.")

    room_ids = [r.id for r in rooms]
    if len(room_ids) != len(set(room_ids)):
        raise InvalidInputError("Duplicate room IDs detected.")
    for r in rooms:
        if r.capacity <= 0:
            raise InvalidInputError(f"Room '{r.id}' has non-positive capacity ({r.capacity}).")

    lecturer_ids = [l.id for l in lecturers]
    if len(lecturer_ids) != len(set(lecturer_ids)):
        raise InvalidInputError("Duplicate lecturer IDs detected.")
    for l in lecturers:
        if not l.available_slots:
            raise InvalidInputError(f"Lecturer '{l.id}' has no available slots.")

    course_ids = [c.id for c in courses]
    if len(course_ids) != len(set(course_ids)):
        raise InvalidInputError("Duplicate course IDs detected.")
    course_id_set = set(course_ids)
    lecturer_id_set = set(lecturer_ids)
    room_types = {r.room_type for r in rooms}

    for c in courses:
        if c.enrolled_students <= 0:
            raise InvalidInputError(f"Course '{c.id}' has non-positive enrolled_students.")
        if c.duration_slots <= 0:
            raise InvalidInputError(f"Course '{c.id}' has non-positive duration_slots.")
        if c.lecturer_id not in lecturer_id_set:
            raise InvalidInputError(
                f"Course '{c.id}' references unknown lecturer_id '{c.lecturer_id}'.")
        if c.required_room_type not in room_types:
            raise InvalidInputError(
                f"Course '{c.id}' requires room_type '{c.required_room_type}', "
                f"which no supplied room provides.")
        for pid in c.prerequisite_ids:
            if pid not in course_id_set:
                raise InvalidInputError(
                    f"Course '{c.id}' references unknown prerequisite '{pid}'.")

    # Circular prerequisite detection (DFS with an on-stack marker).
    graph = {c.id: c.prerequisite_ids for c in courses}
    visiting: Set[str] = set()
    visited: Set[str] = set()

    def _dfs(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            raise InvalidInputError(
                f"Circular prerequisite dependency detected involving course '{node}'.")
        visiting.add(node)
        for dep in graph.get(node, []):
            _dfs(dep)
        visiting.discard(node)
        visited.add(node)

    for cid in graph:
        _dfs(cid)

def _occupied_slots(start: str, duration: int, timeslots: List[str]) -> Optional[List[str]]:
    day, period = start.split("-")
    period = int(period)
    slots = []
    for i in range(duration):
        s = f"{day}-{period + i}"
        if s not in timeslots:
            return None
        slots.append(s)
    return slots


def _topological_order(courses: List[Course]) -> List[str]:
    """Prerequisites-first ordering. Cycle-safety is guaranteed by _validate_input
    running (and raising) before this is ever called."""
    graph = {c.id: c.prerequisite_ids for c in courses}
    order: List[str] = []
    visited: Set[str] = set()

    def _dfs(node: str) -> None:
        if node in visited:
            return
        for dep in graph.get(node, []):
            _dfs(dep)
        visited.add(node)
        order.append(node)

    for cid in graph:
        _dfs(cid)
    return order


def _compute_quality_score(courses: List[Course], assignments: Dict[str, Tuple[str, str]]) -> float:
    prefs = [c for c in courses if c.preferred_slots]
    if not prefs:
        return 1.0
    satisfied = sum(1 for c in prefs if assignments[c.id][1] in c.preferred_slots)
    return satisfied / len(prefs)


def generate_timetable(courses: List[Course], rooms: List[Room],
                        lecturers: List[Lecturer], timeslots: List[str]) -> ScheduleResult:
    _validate_input(courses, rooms, lecturers, timeslots)

    # Cheap necessary-condition pre-check (NFR1 mitigation). Room-capacity and
    # lecturer-overcommitment conflicts are detectable in O(n) without ever
    # invoking the exponential backtracking search below. Performance testing
    # showed the naive draft could blow up (>15s) on tightly overcommitted
    # single-lecturer instances; this short-circuits exactly that pattern.
    # It is a NECESSARY, not sufficient, condition: a clean pre-check does
    # not guarantee backtrack() will succeed, only that it's worth trying.
    early_conflicts = _diagnose_infeasibility(courses, rooms, lecturers, timeslots)
    # Only the room-capacity / lecturer-overcommitment findings are trustworthy
    # pre-conditions; the generic fallback message is not, so it's excluded here.
    early_conflicts = [c for c in early_conflicts if "combined resource contention" not in c]
    if early_conflicts:
        return ScheduleResult(is_feasible=False, assignments={}, conflicts=early_conflicts, quality_score=0.0)

    courses_by_id = {c.id: c for c in courses}
    lecturers_by_id = {l.id: l for l in lecturers}
    order = _topological_order(courses)  # prerequisites processed before dependents

    assignments: Dict[str, Tuple[str, str]] = {}
    start_index: Dict[str, int] = {}
    room_slot_used: Set[Tuple[str, str]] = set()
    lecturer_slot_used: Set[Tuple[str, str]] = set()

    def backtrack(pos: int) -> bool:
        if pos == len(order):
            return True
        course = courses_by_id[order[pos]]
        lecturer = lecturers_by_id[course.lecturer_id]

        min_start_index = 0
        for pid in course.prerequisite_ids:
            min_start_index = max(min_start_index, start_index[pid] + 1)

        candidate_rooms = sorted(
            (r for r in rooms
             if r.room_type == course.required_room_type
             and r.capacity >= course.enrolled_students),
            key=lambda r: (r.capacity, r.id),
        )

        # Preferred slots are tried first (still subject to every hard constraint below),
        # so preferences are honoured whenever doing so doesn't break correctness.
        seen: Set[str] = set()
        candidate_starts = []
        for s in list(course.preferred_slots) + list(timeslots):
            if s in seen or s not in timeslots:
                continue
            seen.add(s)
            candidate_starts.append(s)

        for start in candidate_starts:
            if timeslots.index(start) < min_start_index:
                continue
            occupied = _occupied_slots(start, course.duration_slots, timeslots)
            if occupied is None:
                continue
            if not all(slot in lecturer.available_slots for slot in occupied):
                continue
            for room in candidate_rooms:
                if any((room.id, slot) in room_slot_used for slot in occupied):
                    continue
                if any((lecturer.id, slot) in lecturer_slot_used for slot in occupied):
                    continue
                for slot in occupied:
                    room_slot_used.add((room.id, slot))
                    lecturer_slot_used.add((lecturer.id, slot))
                assignments[course.id] = (room.id, start)
                start_index[course.id] = timeslots.index(start)
                if backtrack(pos + 1):
                    return True
                for slot in occupied:
                    room_slot_used.discard((room.id, slot))
                    lecturer_slot_used.discard((lecturer.id, slot))
                del assignments[course.id]
                del start_index[course.id]
        return False

    if not backtrack(0):
        # Passed the cheap necessary-condition pre-check but still infeasible:
        # a subtler multi-resource contention the O(n) heuristic can't isolate.
        conflicts = _diagnose_infeasibility(courses, rooms, lecturers, timeslots)
        return ScheduleResult(is_feasible=False, assignments={}, conflicts=conflicts, quality_score=0.0)

    quality_score = _compute_quality_score(courses, assignments)
    return ScheduleResult(is_feasible=True, assignments=assignments, conflicts=[], quality_score=quality_score)


def _diagnose_infeasibility(courses: List[Course], rooms: List[Room],
                             lecturers: List[Lecturer], timeslots: List[str]) -> List[str]:
    """Best-effort, named diagnostics (NFR4) rather than a bare 'no solution' message."""
    conflicts: List[str] = []
    lecturers_by_id = {l.id: l for l in lecturers}

    for c in courses:
        matching = [r for r in rooms
                    if r.room_type == c.required_room_type
                    and r.capacity >= c.enrolled_students]
        if not matching:
            same_type = [r.capacity for r in rooms if r.room_type == c.required_room_type]
            best = max(same_type, default=0)
            conflicts.append(
                f"Course '{c.id}' needs a room with capacity >= {c.enrolled_students}, "
                f"but the best matching room only offers {best}.")

    by_lecturer: Dict[str, List[Course]] = {}
    for c in courses:
        by_lecturer.setdefault(c.lecturer_id, []).append(c)

    for lid, clist in by_lecturer.items():
        lecturer = lecturers_by_id.get(lid)
        if lecturer is None:
            continue
        usable = [s for s in timeslots if s in lecturer.available_slots]
        if len(clist) > len(usable):
            names = ", ".join(c.id for c in clist)
            conflicts.append(
                f"Lecturer '{lid}' has only {len(usable)} available slot(s) but is assigned "
                f"{len(clist)} course(s) ({names}); at least one cannot be scheduled.")

    if not conflicts:
        conflicts.append(
            "No feasible timetable found due to combined resource contention "
            "(room/lecturer/slot conflicts); no single course could be isolated as the cause.")
    return conflicts
