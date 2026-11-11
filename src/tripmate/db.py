"""Postgres: connection pool, LangGraph checkpointer (per-thread state) + store (cross-thread preferences),
and the `trips` table (final itineraries, so /trips never replays a graph)."""

import json
from contextlib import contextmanager
from datetime import UTC, datetime

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sqlalchemy import JSON, DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from tripmate.config import settings


class Base(DeclarativeBase):
    pass


class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, default="demo")
    destination: Mapped[str] = mapped_column(String(120))
    origin: Mapped[str] = mapped_column(String(120))
    start_date: Mapped[str] = mapped_column(String(10))
    days: Mapped[int] = mapped_column(Integer)
    travellers: Mapped[list] = mapped_column(JSON)
    total_inr: Mapped[int] = mapped_column(Integer)
    bookings: Mapped[list] = mapped_column(JSON)
    itinerary: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "user_id": self.user_id,
            "destination": self.destination,
            "origin": self.origin,
            "start_date": self.start_date,
            "days": self.days,
            "travellers": self.travellers,
            "total_inr": self.total_inr,
            "references": [b.get("reference") for b in self.bookings],
            "itinerary": self.itinerary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def ping(timeout_s: float = 2.0) -> bool:
    try:
        with psycopg.connect(settings.database_url, connect_timeout=timeout_s) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


class Memory:
    """Everything stateful behind one object so the API can swap it for in-memory in tests."""

    def __init__(self, url: str | None = None, pool_size: int = 8):
        self.url = url or settings.database_url
        self.pool = ConnectionPool(
            self.url,
            min_size=1,
            max_size=pool_size,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
            open=True,
        )
        self.checkpointer = PostgresSaver(self.pool)
        self.store = PostgresStore(self.pool)
        self.engine = create_engine(
            self.url.replace("postgresql://", "postgresql+psycopg://"), pool_pre_ping=True
        )

    def setup(self) -> None:
        self.checkpointer.setup()
        self.store.setup()
        migrate(self.url)

    def close(self) -> None:
        self.pool.close()
        self.engine.dispose()

    # ---- preferences (cross-thread) ----
    def load_prefs(self, user_id: str) -> list[str]:
        item = self.store.get(("prefs", user_id), "travel")
        return list(item.value.get("preferences", [])) if item else []

    def save_prefs(self, user_id: str, prefs: list[str]) -> None:
        self.store.put(("prefs", user_id), "travel", {"preferences": prefs})

    # ---- trips ----
    @contextmanager
    def session(self):
        with Session(self.engine) as s:
            yield s

    def save_trip(self, thread_id: str, user_id: str, state: dict) -> dict:
        c, p = state["constraints"], state["proposal"]
        with self.session() as s:
            existing = s.scalar(select(Trip).where(Trip.thread_id == thread_id))
            if existing:
                return existing.as_dict()
            t = Trip(
                thread_id=thread_id,
                user_id=user_id,
                destination=c["destination"],
                origin=c["origin"],
                start_date=c["start_date"],
                days=c["days"],
                travellers=c["travellers"],
                total_inr=int(p["total_inr"]),
                bookings=json.loads(json.dumps(state["bookings"], default=str)),
                itinerary=state.get("itinerary") or {},
            )
            s.add(t)
            s.commit()
            s.refresh(t)
            return t.as_dict()

    def list_trips(self, user_id: str | None = None) -> list[dict]:
        with self.session() as s:
            q = select(Trip).order_by(Trip.id.desc())
            if user_id:
                q = q.where(Trip.user_id == user_id)
            return [t.as_dict() for t in s.scalars(q)]


def migrate(url: str) -> None:
    from pathlib import Path

    from alembic.config import Config

    from alembic import command

    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("postgresql://", "postgresql+psycopg://"))
    command.upgrade(cfg, "head")
