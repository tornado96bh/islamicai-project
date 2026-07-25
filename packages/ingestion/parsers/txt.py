from __future__ import annotations
from pathlib import Path
class TXTParser:
    def parse(self, path: Path): return {'type': 'txt', 'path': str(path), 'text': path.read_text(encoding='utf8', errors='ignore')}
