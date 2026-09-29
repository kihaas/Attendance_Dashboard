"""Клиент API журнала и нормализация ответа в единый формат занятия."""
import json
import logging
import time
from datetime import date

import httpx

from app import config

log = logging.getLogger(__name__)

LOGIN_URL = "https://msapi.top-academy.ru/api/v2/auth/login"
VISITS_URL = "https://msapi.top-academy.ru/api/v2/progress/operations/student-visits"
HEADERS = {
    "origin": "https://journal.top-academy.ru",
    "referer": "https://journal.top-academy.ru/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    ),
}
STATUSES = {1: "present", 0: "absent"}
MARK_FIELDS = (
    "control_work_mark", "home_work_mark", "lab_work_mark",
    "class_work_mark", "practical_work_mark", "final_work_mark",
)


class JournalError(Exception):
    """Ошибка получения данных из журнала."""


def _login(client: httpx.Client) -> str:
    payload = {
        "application_key": config.APPLICATION_KEY,
        "username": config.JOURNAL_USERNAME,
        "password": config.JOURNAL_PASSWORD,
    }
    # Журнал иногда случайно отвечает 401 — повторяем до 3 раз
    for _ in range(3):
        response = client.post(LOGIN_URL, json=payload)
        if response.status_code != 401:
            response.raise_for_status()
            return response.json()["access_token"]
        time.sleep(0.3)
    raise JournalError("Неверный логин или пароль журнала.")


def fetch_visits() -> list[dict]:
    with httpx.Client(headers=HEADERS, timeout=20) as client:
        token = _login(client)
        response = client.get(VISITS_URL, headers={"authorization": f"Bearer {token}"})
        response.raise_for_status()
        return response.json()


def normalize(item: dict) -> dict:
    """Приводит запись API к модели занятия."""
    subject_id = item.get("spec_id") or item.get("subject_id")
    status = STATUSES.get(item.get("status_was"), "unknown")
    if status == "unknown":
        log.warning("Неизвестный статус посещения: %s", item)
    marks = {k: item[k] for k in MARK_FIELDS if item.get(k) is not None}
    return {
        "external_id": f"{item['date_visit']}_{item.get('lesson_number')}_{subject_id}",
        "subject_name": (item.get("spec_name") or "Без названия").strip(),
        "lesson_date": date.fromisoformat(item["date_visit"]),
        "lesson_number": item.get("lesson_number"),
        "teacher_name": item.get("teacher_name"),
        "topic": item.get("lesson_theme"),
        "attendance_status": status,
        "grade": json.dumps(marks) if marks else None,
        "raw_data": json.dumps(item, ensure_ascii=False),
    }