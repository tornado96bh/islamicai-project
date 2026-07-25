from __future__ import annotations

from packages.ingestion.chunker import TextChunker


class ChunkExtractor:

    def __init__(self):

        self.chunker = TextChunker()

    def extract(self,pages):

        return self.chunker.split(pages)
