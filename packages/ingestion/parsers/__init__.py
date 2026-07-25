from .pdf import PDFParser
from .djvu import DJVUParser
from .epub import EPUBParser
from .txt import TXTParser

__all__ = ["PDFParser", "DJVUParser", "EPUBParser", "TXTParser"]
