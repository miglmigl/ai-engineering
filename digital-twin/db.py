import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///twin.db")
engine = create_engine(DATABASE_URL)


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str]
    name: Mapped[str]
    notes: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class UnknownQuestion(Base):
    __tablename__ = "unknown_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


def create_tables():
    Base.metadata.create_all(engine)