class IngestionError(Exception):
    """Base ingestion error."""


class UnsupportedFileTypeError(IngestionError):
    """Raised when a file type is not supported."""


class PDFImportError(IngestionError):
    """Raised when PDF import fails."""
