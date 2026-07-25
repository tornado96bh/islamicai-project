"""
العقود المشتركة — المصدر الوحيد لتعريف البيانات في IslamicAI.

قاعدة Contract-First (الماستر §3): لا يُعرَّف نموذج بيانات محلياً داخل
router أو خدمة. كل ما يعبر حدود وحدة يُعرَّف هنا.

الفحص أظهر أن الحزمة السابقة كانت **ملفاً ميتاً** — لا يستوردها أحد،
وتغطي 6 عقود فقط من المطلوب. هذه النسخة تكملها.

الإصدار
-------
كل عقد يحمل SCHEMA_VERSION. أي تغيير غير متوافق يرفع الرقم الأوسط،
وأي إضافة اختيارية ترفع الأخير. المستهلكون يتحققون من التوافق قبل
معالجة أي حمولة مخزَّنة.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "2.0.0"


# ===========================================================================
#  الأساس
# ===========================================================================

class Contract(BaseModel):
    """أساس كل العقود: منع الحقول غير المعرّفة، وتثبيت الإصدار."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    schema_version: str = Field(default=SCHEMA_VERSION)


class ElementType(str, Enum):
    """
    أنواع عناصر الصفحة.

    الفحص أظهر أن الاستيعاب يكتب "text" لكل عنصر بلا استثناء، أي أن
    فصل المتن عن السند عن الحاشية غير منفَّذ. هذا التعداد هو العقد
    الذي يجب أن يحققه Layout Engine.
    """

    MATN = "matn"                # المتن
    SANAD = "sanad"              # السند
    HASHIYA = "hashiya"          # الحاشية
    TAALEEQ = "taaleeq"          # التعليق
    FOOTNOTE = "footnote"        # الهامش
    HEADING = "heading"          # العنوان
    CITATION = "citation"        # الإحالة
    PAGE_NUMBER = "page_number"  # رقم الصفحة
    RUNNING_HEAD = "running_head"
    TABLE = "table"
    UNKNOWN = "unknown"          # لم يُصنَّف بعد


class TextQuality(str, Enum):
    """جودة النص بعد OCR والتنظيف — يحدد ما يدخل الفهرس."""

    CLEAN = "clean"
    NOISY = "noisy"
    BLANK = "blank"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


# ===========================================================================
#  الهندسة والنص
# ===========================================================================

class BoundingBox(Contract):
    """
    موضع على الصفحة، بالنقاط، الأصل أعلى اليسار.

    ملاحظة توافق: مستخرج الكتل الحالي يخرج {x0,y0,x1,y1} بينما هذا
    العقد {x,y,w,h}. استعمل from_xyxy للتحويل بدل التحويل اليدوي.
    """

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)

    @classmethod
    def from_xyxy(cls, x0: float, y0: float, x1: float, y1: float) -> "BoundingBox":
        return cls(x=min(x0, x1), y=min(y0, y1),
                   width=abs(x1 - x0), height=abs(y1 - y0))

    def to_xyxy(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)


class TextSpan(Contract):
    """
    مدى نصي داخل عنصر، مربوط بموضعه الأصلي.

    هذا هو ما يجعل الاستشهاد قابلاً للتحقق: الفهرسة تتم على الصيغة
    المطبّعة، والعرض والاستشهاد من raw عبر هذه الإزاحات. بدونه ينكسر
    الربط بين نتيجة البحث وموضعها على الصفحة، لأن التطبيع يغيّر
    أطوال السلاسل.
    """

    element_id: UUID
    start_raw: int = Field(ge=0)
    end_raw: int = Field(gt=0)
    text_raw: str
    bounding_box: BoundingBox | None = None

    @field_validator("end_raw")
    @classmethod
    def _end_after_start(cls, v: int, info) -> int:
        start = info.data.get("start_raw", 0)
        if v <= start:
            raise ValueError("end_raw يجب أن يكون بعد start_raw")
        return v


# ===========================================================================
#  الببليوغرافيا
# ===========================================================================

class Book(Contract):
    """كتاب — الوحدة الببليوغرافية الأعلى."""

    id: UUID
    title: str = Field(min_length=1)
    short_title: str | None = None
    original_title: str | None = None
    author_id: UUID | None = None
    author_name: str | None = None
    language: str = Field(default="ar", min_length=2, max_length=8)
    category: str | None = None
    description: str | None = None
    # بصمة المحتوى — تمنع استيراد النسخة نفسها مرتين (الماستر §2)
    content_fingerprint: str | None = None
    is_public: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Edition(Contract):
    """طبعة محددة من كتاب. الاستشهاد العلمي يلزمه تحديد الطبعة."""

    id: UUID
    book_id: UUID
    edition_number: int = Field(default=1, ge=1)
    publisher_name: str | None = None
    publication_year: int | None = None
    editor_name: str | None = None
    isbn: str | None = None
    notes: str | None = None


class Volume(Contract):
    """مجلد داخل طبعة."""

    id: UUID
    edition_id: UUID
    volume_number: int = Field(ge=1)
    title: str | None = None
    total_pages: int | None = Field(default=None, ge=0)


class Page(Contract):
    """صفحة داخل مجلد."""

    id: UUID
    volume_id: UUID
    page_number: int = Field(ge=0)
    printed_page_label: str | None = None  # رقم الصفحة كما طُبع
    image_path: str | None = None
    dpi: int | None = Field(default=None, ge=1)
    ocr_engine: str | None = None
    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class PageElement(Contract):
    """
    عنصر على صفحة — الوحدة الذرية للفهرسة والاستشهاد.

    فصل النص ثلاثي وإلزامي:
      text_raw        الأصل كما استُخرج، بحركاته وهمزاته ونقاطه.
                      هذا ما يُعرض ويُستشهد به. لا يُكتب فوقه أبداً.
      text_normalized الصيغة البحثية. هذا ما يُفهرَس.
      text_display    نسخة مقروءة (تمديد مُزال، رباطات مصححة) مع
                      إبقاء التشكيل. اختيارية، للواجهة فقط.
    """

    id: UUID
    page_id: UUID
    element_type: ElementType = ElementType.UNKNOWN
    element_order: int = Field(ge=0)

    text_raw: str
    text_normalized: str | None = None
    text_display: str | None = None

    bounding_box: BoundingBox | None = None
    quality: TextQuality = TextQuality.CLEAN

    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    layout_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    canonicalizer_version: str | None = None
    speaker: str | None = None


# ===========================================================================
#  المحتوى العلمي
# ===========================================================================

class Narrator(Contract):
    """راوٍ."""

    id: UUID
    canonical_name: str = Field(min_length=1)
    kunya: str | None = None
    nisba: str | None = None
    laqab: str | None = None
    aliases: list[str] = Field(default_factory=list)
    death_year_hijri: int | None = None
    birth_year_hijri: int | None = None
    generation: str | None = None
    # لا يُحسم التوثيق آلياً: يُنقل عن مصادره مع الإسناد
    gradings: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class IsnadLink(Contract):
    """حلقة في السند: من روى عمّن."""

    from_narrator_id: UUID | None = None
    to_narrator_id: UUID | None = None
    from_name_raw: str
    to_name_raw: str
    transmission_term: str | None = None  # عن، حدثنا، أخبرنا، سمعت
    position: int = Field(ge=0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class Isnad(Contract):
    """سند كامل مربوط بموضعه في النص."""

    id: UUID
    hadith_id: UUID | None = None
    span: TextSpan
    links: list[IsnadLink] = Field(default_factory=list)
    is_complete: bool = False
    parse_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    unresolved_names: list[str] = Field(default_factory=list)


class Hadith(Contract):
    """
    حديث — سند ومتن مربوطان بموضعهما.

    matn_span و isnad_id يحفظان الربط بالصفحة الأصلية، فلا يُقتبس
    نص بلا موضع يمكن الرجوع إليه.
    """

    id: UUID
    book_id: UUID
    matn_span: TextSpan
    isnad_id: UUID | None = None
    number_in_source: str | None = None
    chapter_title: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    parallel_hadith_ids: list[UUID] = Field(default_factory=list)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class Commentary(Contract):
    """شرح أو تعليق على نص أصلي."""

    id: UUID
    target_kind: Literal["hadith", "verse", "passage", "narrator"]
    target_id: UUID
    span: TextSpan
    commentator_name: str | None = None
    commentary_type: Literal["sharh", "taaleeq", "hashiya", "tahqiq"] = "sharh"


class Footnote(Contract):
    """هامش مربوط بمرجعه في المتن."""

    id: UUID
    page_id: UUID
    marker: str | None = None          # الرمز المطبوع: (١) أو *
    span: TextSpan
    references_span: TextSpan | None = None  # موضع الإحالة في المتن
    footnote_type: Literal["citation", "variant", "explanation", "other"] = "other"


class Source(Contract):
    """مرجع قابل للتحقق — كل ادعاء يجب أن يُسنَد إلى واحد."""

    book_id: UUID
    book_title: str
    edition_id: UUID | None = None
    volume_number: int | None = None
    page_number: int | None = None
    element_id: UUID | None = None
    span: TextSpan | None = None
    quotation: str | None = None

    def citation(self) -> str:
        parts = [self.book_title]
        if self.volume_number is not None:
            parts.append(f"ج{self.volume_number}")
        if self.page_number is not None:
            parts.append(f"ص{self.page_number}")
        return " ".join(parts)


# ===========================================================================
#  الاسترجاع والإجابة
# ===========================================================================

class RetrievalHit(Contract):
    """
    نتيجة استرجاع واحدة، مع تفسير كامل لدرجتها.

    score_explain إلزامي لا اختياري: القياس كشف أن معيد الترتيب كان
    يضيف 1.235 فوق أساس RRF البالغ 0.016 دون أن يظهر ذلك في أي مكان،
    فكان الترتيب الظاهر لا علاقة له بالترتيب المُفسَّر.
    """

    element_id: UUID | None = None
    page_id: UUID | None = None
    source_engine: Literal["fts", "fuzzy", "semantic", "graph"] = "fts"
    score: float
    score_explain: dict[str, float] = Field(default_factory=dict)
    ranks_per_engine: dict[str, int] = Field(default_factory=dict)
    text_raw: str | None = None
    text_display: str | None = None
    source: Source | None = None


class EvidenceBundle(Contract):
    """
    حزمة الأدلة التي بُنيت عليها الإجابة.

    sufficient=False يعني أن النظام يجب أن يعتذر عن الجزم لا أن يخمّن.
    """

    query: str
    query_normalized: str
    hits: list[RetrievalHit] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    sufficient: bool = False
    coverage_score: float = Field(default=0.0, ge=0.0, le=1.0)
    built_at: datetime | None = None


class VerificationResult(Contract):
    """نتيجة التحقق قبل إخراج أي إجابة."""

    passed: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    failures: list[str] = Field(default_factory=list)
    requires_human_review: bool = False


class FinalAnswer(Contract):
    """
    الإجابة النهائية.

    كل ادعاء يجب أن يقابله مصدر. answer_text بلا sources مخالفة عقد
    لا مجرد نقص جودة.
    """

    question: str
    answer_text: str
    sources: list[Source] = Field(default_factory=list)
    evidence: EvidenceBundle | None = None
    verification: VerificationResult | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    caveats: list[str] = Field(default_factory=list)
    declined: bool = False
    decline_reason: str | None = None

    @model_validator(mode="after")
    def _sources_required(self) -> "FinalAnswer":
        """
        يُنفَّذ بعد بناء النموذج كاملاً حتى يرى declined.

        field_validator على sources لا يكفي: declined معرَّف بعده فلا
        يظهر في info.data، والقيمة الافتراضية تتخطى التحقق أصلاً.
        """
        if not self.declined and not self.sources:
            raise ValueError(
                "الإجابة غير المعتذَر عنها يجب أن تحمل مصدراً واحداً على الأقل"
            )
        if self.declined and not self.decline_reason:
            raise ValueError("الاعتذار يجب أن يُذكر سببه")
        return self


__all__ = [
    "SCHEMA_VERSION",
    "Book", "BoundingBox", "Commentary", "Contract", "Edition", "ElementType",
    "EvidenceBundle", "FinalAnswer", "Footnote", "Hadith", "Isnad", "IsnadLink",
    "Narrator", "Page", "PageElement", "RetrievalHit", "Source", "TextQuality",
    "TextSpan", "VerificationResult", "Volume",
]
