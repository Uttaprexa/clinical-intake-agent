"""
Postgres connection and a thin repository layer over IntakeRecord.

We store the record as JSONB rather than a fully normalized schema --
this is a deliberate simplification for a portfolio project. In a
production system, extracted_fields would likely be normalized into
its own table so you can query/aggregate on individual fields.
"""
import json
import os
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import Column, DateTime, String, create_engine, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker

from models import IntakeRecord

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/clinical_intake"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class IntakeRow(Base):
    __tablename__ = "intake_records"

    id = Column(String, primary_key=True)
    status = Column(String, nullable=False, index=True)
    data = Column(JSONB, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class IntakeRepository:
    """Repository wrapping IntakeRecord <-> IntakeRow (de)serialization."""

    @staticmethod
    def save(record: IntakeRecord) -> None:
        with get_session() as session:
            payload = json.loads(record.model_dump_json())
            row = session.get(IntakeRow, record.id)
            if row is None:
                row = IntakeRow(id=record.id, status=record.status.value, data=payload)
                session.add(row)
            else:
                row.status = record.status.value
                row.data = payload

    @staticmethod
    def get(record_id: str) -> Optional[IntakeRecord]:
        with get_session() as session:
            row = session.get(IntakeRow, record_id)
            if row is None:
                return None
            return IntakeRecord.model_validate(row.data)

    @staticmethod
    def list(status: Optional[str] = None) -> list[IntakeRecord]:
        with get_session() as session:
            query = session.query(IntakeRow)
            if status:
                query = query.filter(IntakeRow.status == status)
            rows = query.order_by(IntakeRow.created_at.desc()).all()
            return [IntakeRecord.model_validate(r.data) for r in rows]
