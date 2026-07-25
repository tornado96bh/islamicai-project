from __future__ import annotations
from pathlib import Path
class DJVUParser:
    def parse(self, path: Path): return {'type': 'djvu', 'path': str(path)}
