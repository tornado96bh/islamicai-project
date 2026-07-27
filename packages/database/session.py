"""
جلسة قاعدة البيانات — بناء كسول.

المشكلة التي يحلها
------------------
كان المحرك يُبنى **عند الاستيراد**:

    engine = create_engine(settings.database_url, ...)

فأي استيراد بسيط يوقظ سلسلة كاملة:

    packages.learning  ->  LearningTrainer  ->  SessionLocal  ->  engine

والنتيجة أن جمع الاختبارات ينهار إن لم يكن مشغّل PostgreSQL متاحاً،
وتفشل السكربتات المساعدة التي لا تحتاج قاعدة بيانات أصلاً.

الآن: المحرك يُبنى عند أول استعمال فعلي ويُخزَّن. و SessionLocal
كائن وسيط يمرّر النداء عند الحاجة، فيبقى الاستيراد خفيفاً بلا تغيير
في أي مستدعٍ.
"""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """يبني المحرك مرة واحدة عند أول طلب فعلي."""
    from packages.config.settings import settings

    return create_engine(
        settings.database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=40,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


class _LazySessionFactory:
    """
    وسيط يحافظ على الواجهة القديمة `SessionLocal()`.

    لا يلمس قاعدة البيانات حتى يُستدعى فعلاً، فالاستيراد يبقى مجانياً.
    """

    def __call__(self, **kwargs: Any) -> Session:
        return get_sessionmaker()(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(get_sessionmaker(), name)


SessionLocal = _LazySessionFactory()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_engine() -> None:
    """يُستعمل في الاختبارات بعد تغيير الإعدادات."""
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()


__all__ = ["SessionLocal", "get_db", "get_engine", "get_sessionmaker", "reset_engine"]
