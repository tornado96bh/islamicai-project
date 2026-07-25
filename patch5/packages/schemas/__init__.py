"""
packages.schemas — المصدر الوحيد لعقود البيانات.

الاستيراد من هنا لا من الملفات الداخلية:
    from packages.schemas import PageElement, Hadith, FinalAnswer
"""

from .contracts import (  # noqa: F401
    SCHEMA_VERSION,
    Book,
    BoundingBox,
    Commentary,
    Contract,
    Edition,
    ElementType,
    EvidenceBundle,
    FinalAnswer,
    Footnote,
    Hadith,
    Isnad,
    IsnadLink,
    Narrator,
    Page,
    PageElement,
    RetrievalHit,
    Source,
    TextQuality,
    TextSpan,
    VerificationResult,
    Volume,
)

__all__ = [
    "SCHEMA_VERSION", "Book", "BoundingBox", "Commentary", "Contract",
    "Edition", "ElementType", "EvidenceBundle", "FinalAnswer", "Footnote",
    "Hadith", "Isnad", "IsnadLink", "Narrator", "Page", "PageElement",
    "RetrievalHit", "Source", "TextQuality", "TextSpan",
    "VerificationResult", "Volume",
]
