from __future__ import annotations
from typing import Any, Generic, Sequence, TypeVar
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")

class BaseRepository(Generic[ModelType]):
    model_cls: type[ModelType]

    def __init__(self, db: Session):
        self.db = db

    def create(self, commit: bool = True, **kwargs: Any) -> ModelType:
        obj = self.model_cls(**kwargs)
        self.db.add(obj)
        if commit:
            self.db.commit()
            self.db.refresh(obj)
        else:
            self.db.flush()
            self.db.refresh(obj)
        return obj

    def add(self, obj: ModelType, commit: bool = True) -> ModelType:
        self.db.add(obj)
        if commit:
            self.db.commit()
            self.db.refresh(obj)
        else:
            self.db.flush()
            self.db.refresh(obj)
        return obj

    def bulk_add(self, objects: Sequence[ModelType], commit: bool = True) -> None:
        self.db.add_all(objects)
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def get(self, object_id: Any) -> ModelType | None:
        return self.db.scalar(select(self.model_cls).where(self.model_cls.id == object_id))

    def first(self) -> ModelType | None:
        return self.db.scalar(select(self.model_cls).limit(1))

    def all(self) -> list[ModelType]:
        return list(self.db.scalars(select(self.model_cls)).all())

    def count(self) -> int:
        return int(self.db.scalar(select(func.count()).select_from(self.model_cls)) or 0)

    def exists(self, object_id: Any) -> bool:
        return self.get(object_id) is not None

    def paginate(self, page: int = 1, page_size: int = 50) -> list[ModelType]:
        page = max(page, 1)
        page_size = max(page_size, 1)
        stmt = select(self.model_cls).offset((page - 1) * page_size).limit(page_size)
        return list(self.db.scalars(stmt).all())

    def update(self, obj: ModelType, commit: bool = True, **kwargs: Any) -> ModelType:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        if commit:
            self.db.commit()
            self.db.refresh(obj)
        else:
            self.db.flush()
            self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelType, commit: bool = True) -> None:
        self.db.delete(obj)
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def delete_by_id(self, object_id: Any, commit: bool = True) -> bool:
        result = self.db.execute(delete(self.model_cls).where(self.model_cls.id == object_id))
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return result.rowcount > 0
