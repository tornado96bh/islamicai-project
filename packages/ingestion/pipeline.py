from __future__ import annotations

from .extractors.metadata import MetadataExtractor
from .extractors.toc import TOCExtractor
from .extractors.pages import PagesExtractor
from .extractors.images import ImagesExtractor
from .extractors.text import TextExtractor
from .extractors.blocks import BlockExtractor
from .extractors.words import WordExtractor
from .extractors.links import LinkExtractor
from .extractors.drawings import DrawingExtractor
from .extractors.chunk import ChunkExtractor


class IngestionPipeline:

    def __init__(self):

        self.metadata_extractor = MetadataExtractor()
        self.toc_extractor = TOCExtractor()
        self.pages_extractor = PagesExtractor()
        self.images_extractor = ImagesExtractor()
        self.text_extractor = TextExtractor()
        self.blocks_extractor = BlockExtractor()
        self.words_extractor = WordExtractor()
        self.links_extractor = LinkExtractor()
        self.drawings_extractor = DrawingExtractor()
        self.chunk_extractor = ChunkExtractor()

    def run(self, pdf):

        pages = self.pages_extractor.extract(pdf)

        text = self.text_extractor.extract(pdf)

        return {

            "metadata": self.metadata_extractor.extract(pdf),

            "toc": self.toc_extractor.extract(pdf),

            "pages": pages,

            "text": text,

            "chunks": self.chunk_extractor.extract(text),

            "blocks": self.blocks_extractor.extract(pdf),

            "words": self.words_extractor.extract(pdf),

            "links": self.links_extractor.extract(pdf),

            "drawings": self.drawings_extractor.extract(pdf),

            "images": self.images_extractor.extract(pdf),

        }
