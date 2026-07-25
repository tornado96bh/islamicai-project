from pathlib import Path

ROOT = Path(r"E:\IslamicAI_v3_full")

db = ROOT / "packages" / "database"
models = db / "models"

models.mkdir(parents=True, exist_ok=True)

(db / "__init__.py").write_text("", encoding="utf8")
(models / "__init__.py").write_text("", encoding="utf8")

(db / "base.py").write_text('''from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

class UUIDMixin:
    id: Mapped = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

class BaseModel(Base, UUIDMixin, TimestampMixin):
    __abstract__ = True
''', encoding="utf8")

(db / "session.py").write_text('''from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/islamicai"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)
''', encoding="utf8")

(db / "types.py").write_text("# Reserved for custom SQLAlchemy types\n", encoding="utf8")

print("=" * 50)
print("DATABASE FOUNDATION CREATED")
print("=" * 50)
print(db)
print(models)
