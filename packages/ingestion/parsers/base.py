from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path

class BaseParser(ABC):
    @abstractmethod
    def parse(self, path: Path):
        raise NotImplementedError
