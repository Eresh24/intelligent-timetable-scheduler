# Intelligent Timetable Scheduler

AI-assisted TDD coursework submission. See `Software_Unit_Testing_Report.docx` for the full
report (requirements, test design, development process, evaluation, testing results, reflection).

## Structure

```
.
├── README.md
├── pytest.ini                          # lets tests import source/scheduler.py directly
├── Software_Unit_Testing_Report.docx   # the full report
├── source/
│   └── scheduler.py                    # the application
└── tests/
    ├── test_scheduler.py               # 28 tests: normal, boundary, invalid, exceptional
    └── test_regression.py              # 3 tests: real defects found during development
```

## Requirements

- Python 3.10+
- `pytest`, `pytest-cov`

```bash
pip install pytest pytest-cov
```

## Running the tests

From this folder:

```bash
python3 -m pytest tests/ -v
python3 -m pytest tests/ --cov=scheduler --cov-report=term-missing
```

Expected result: **31 passed**, **95% coverage** on `scheduler.py` (the three small gaps are
explained in Section 14 of the report — they're a documented limitation, not an oversight).

## Using the scheduler

```python
from scheduler import Room, Lecturer, Course, generate_timetable

rooms = [Room(id="R1", capacity=30)]
lecturers = [Lecturer(id="L1", name="Dr Smith", available_slots={"Mon-1", "Mon-2"})]
courses = [Course(id="C1", name="Intro CS", lecturer_id="L1", enrolled_students=25)]
timeslots = [f"{d}-{p}" for d in ("Mon", "Tue", "Wed", "Thu", "Fri") for p in range(1, 9)]

result = generate_timetable(courses, rooms, lecturers, timeslots)
print(result.is_feasible, result.assignments, result.conflicts, result.quality_score)
```

## Publishing this to GitHub

This wasn't pushed to a repository automatically — that needs your own GitHub account. From
this folder:

```bash
git init
git add .
git commit -m "Intelligent Timetable Scheduler: AI-assisted TDD submission"
```

Then create an empty repository on github.com (no README/license, so it stays empty), and:

```bash
git remote add origin https://github.com/<your-username>/<your-repo-name>.git
git branch -M main
git push -u origin main
```

Copy the resulting `https://github.com/<your-username>/<your-repo-name>` URL into the report
wherever it asks for the GitHub repository link (Section 14, Testing Results, and the
submission coversheet if your course uses one) before you hand it in.
