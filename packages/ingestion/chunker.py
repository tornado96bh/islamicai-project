from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TextChunk:

    page: int

    order: int

    text: str

    start: int

    end: int

    characters: int

    words: int


class TextChunker:

    def __init__(

        self,

        chunk_size: int = 1000,

        overlap: int = 200,

    ):

        self.chunk_size = chunk_size

        self.overlap = overlap

    def split(self, pages):

        chunks = []

        order = 0

        for page in pages:

            text = page["text"]

            start = 0

            while start < len(text):

                end = min(

                    start + self.chunk_size,

                    len(text),

                )

                part = text[start:end]

                if part.strip():

                    order += 1

                    chunks.append(

                        TextChunk(

                            page=page["page"],

                            order=order,

                            text=part,

                            start=start,

                            end=end,

                            characters=len(part),

                            words=len(part.split()),

                        )

                    )

                if end >= len(text):

                    break

                start = end - self.overlap

        return chunks
