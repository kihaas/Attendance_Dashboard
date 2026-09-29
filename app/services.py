import math
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import REQUIRED_PERCENT
from app.database import Lesson, Meta, Subject
from app.journal import fetch_visits, normalize

LESSON_FIELDS = ("lesson_date", "lesson_number", "teacher_name", "topic", "attendance_status", "grade", "raw_data")


# ---------- расчёт посещаемости ----------

def calc_percent(present: int, absent: int) -> float:
    total = present + absent
    return round(present / total * 100, 1) if total else 0.0


def calc_status(percent: float, total: int) -> str:
    if total == 0:
        return "no_data"
    if percent < 55:
        return "critical"
    if percent < REQUIRED_PERCENT:
        return "below"
    if percent < 65:
        return "reached"
    return "good"


def lessons_to_attend(present: int, total: int, required: float = REQUIRED_PERCENT) -> int:
    """Сколько занятий подряд нужно посетить, чтобы достичь required %."""
    r = required / 100
    # round убирает погрешность float (0.6 * 5 = 3.0000000000000004)
    return max(0, math.ceil(round((r * total - present) / (1 - r), 9)))


def plural_pairs(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} пару"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} пары"
    return f"{n} пар"


def recommendation(present: int, absent: int) -> str:
    total = present + absent
    if total == 0:
        return "Пока нет учтённых занятий."
    x = lessons_to_attend(present, total)
    if x == 0:
        return "Минимальный порог достигнут."
    return f"Для достижения {REQUIRED_PERCENT:g}% желательно посетить следующие {plural_pairs(x)} подряд."


# ---------- dashboard / архив ----------

def _counts(db: Session) -> dict[int, dict[str, int]]:
    rows = db.execute(
        select(Lesson.subject_id, Lesson.attendance_status, func.count())
        .where(Lesson.attendance_status.in_(("present", "absent")))
        .group_by(Lesson.subject_id, Lesson.attendance_status)
    )
    counts: dict[int, dict[str, int]] = {}
    for subject_id, status, n in rows:
        counts.setdefault(subject_id, {})[status] = n
    return counts


def _card(subject: Subject, present: int, absent: int) -> dict:
    percent = calc_percent(present, absent)
    return {
        "id": subject.id,
        "name": subject.name,
        "teacher": subject.teacher_name,
        "present_count": present,
        "absent_count": absent,
        "total_count": present + absent,
        "attendance_percent": percent,
        "status": calc_status(percent, present + absent),
        "recommendation": recommendation(present, absent),
    }


def get_last_updated(db: Session) -> str | None:
    meta = db.get(Meta, "last_updated")
    return meta.value if meta else None


def get_dashboard(db: Session) -> dict:
    counts = _counts(db)
    subjects = db.scalars(select(Subject).where(Subject.status == "active").order_by(Subject.name))
    return {
        "last_updated": get_last_updated(db),
        "subjects": [_card(s, counts.get(s.id, {}).get("present", 0), counts.get(s.id, {}).get("absent", 0)) for s in subjects],
    }


def get_archive(db: Session) -> list[dict]:
    subjects = db.scalars(select(Subject).where(Subject.status == "completed").order_by(Subject.completed_at.desc()))
    return [
        {**_card(s, s.final_present, s.final_absent), "completed_at": s.completed_at.isoformat()}
        for s in subjects
    ]


def complete_subject(db: Session, subject_id: int) -> bool:
    subject = db.get(Subject, subject_id)
    if subject is None or subject.status == "completed":
        return False
    counts = _counts(db).get(subject.id, {})
    subject.status = "completed"
    subject.completed_at = datetime.now()
    subject.final_present = counts.get("present", 0)
    subject.final_absent = counts.get("absent", 0)
    db.commit()
    return True


# ---------- синхронизация ----------

def sync(db: Session) -> dict:
    items = [normalize(raw) for raw in fetch_visits()]
    subjects = {s.name: s for s in db.scalars(select(Subject))}
    lessons = {l.external_id: l for l in db.scalars(select(Lesson))}
    result = {"new_lessons": 0, "updated_lessons": 0, "new_subjects": 0}

    for item in items:
        subject = subjects.get(item["subject_name"])
        if subject is None:
            subject = Subject(name=item["subject_name"])
            db.add(subject)
            db.flush()
            subjects[subject.name] = subject
            result["new_subjects"] += 1
        subject.teacher_name = item["teacher_name"] or subject.teacher_name

        values = {k: item[k] for k in LESSON_FIELDS}
        lesson = lessons.get(item["external_id"])
        if lesson is None:
            lesson = Lesson(subject_id=subject.id, external_id=item["external_id"], **values)
            db.add(lesson)
            lessons[lesson.external_id] = lesson
            result["new_lessons"] += 1
        elif any(getattr(lesson, k) != v for k, v in values.items() if k != "raw_data"):
            for k, v in values.items():
                setattr(lesson, k, v)
            result["updated_lessons"] += 1

    last_updated = datetime.now().astimezone().isoformat(timespec="seconds")
    db.merge(Meta(key="last_updated", value=last_updated))
    db.commit()
    return {"status": "success", **result, "last_updated": last_updated}