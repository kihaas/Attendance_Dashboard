import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import config, services  # noqa: F401  (config настраивает логирование)
from app.database import get_db, init_db
from app.journal import JournalError

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Attendance Dashboard", lifespan=lifespan)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    return services.get_dashboard(db)


@app.post("/api/sync")
def sync(db: Session = Depends(get_db)):
    try:
        return services.sync(db)
    except JournalError as e:
        log.error("Ошибка журнала: %s", e)
        raise HTTPException(401, str(e))
    except (httpx.HTTPError, KeyError, ValueError) as e:
        log.exception("Синхронизация не удалась")
        raise HTTPException(502, "Не удалось обновить данные журнала. Показаны последние сохранённые данные.")


@app.post("/api/subjects/{subject_id}/complete")
def complete_subject(subject_id: int, db: Session = Depends(get_db)):
    if not services.complete_subject(db, subject_id):
        raise HTTPException(404, "Активная дисциплина не найдена.")
    return {"status": "completed", "subject_id": subject_id}


@app.get("/api/archive")
def archive(db: Session = Depends(get_db)):
    return services.get_archive(db)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)