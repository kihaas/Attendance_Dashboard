from datetime import date, datetime

from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    teacher_name: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="active")  # active / completed
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    completed_at: Mapped[datetime | None]
    # Итоги фиксируются в момент завершения
    final_present: Mapped[int | None]
    final_absent: Mapped[int | None]

    lessons: Mapped[list["Lesson"]] = relationship(back_populates="subject")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    external_id: Mapped[str] = mapped_column(unique=True)
    lesson_date: Mapped[date]
    lesson_number: Mapped[int | None]
    teacher_name: Mapped[str | None]
    topic: Mapped[str | None]
    attendance_status: Mapped[str]  # present / absent / unknown / cancelled
    grade: Mapped[str | None]  # JSON с оценками
    raw_data: Mapped[str | None]  # исходный ответ API
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    subject: Mapped[Subject] = relationship(back_populates="lessons")


class Meta(Base):
    """Простое key-value хранилище (время последней синхронизации)."""

    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db():
    with SessionLocal() as db:
        yield db