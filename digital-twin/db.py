import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

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

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str]
    user_message: Mapped[str]
    assistant_response: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


def create_tables():
    Base.metadata.create_all(engine)

def log_conversation(session_id, user_message, assistant_response):
    with Session(engine) as session:
        session.add(Conversation(session_id=session_id, user_message=user_message, assistant_response=assistant_response))
        session.commit()
