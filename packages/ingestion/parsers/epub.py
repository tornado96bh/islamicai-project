from __future__ import annotations
from pathlib import Path
class EPUBParser:
    def parse(self, path: Path): return {'type': 'epub', 'path': str(path)}
