"""
Embeddings حقيقية — نموذج متعدد اللغات بدل الـ hashing.

لماذا الآن
----------
كل ما بُني في الدفعات السابقة (RRF، الإشارات، التخطيط) قواعدُ فوق
فضاء متجهات **وهمي**: `EmbeddingBuilder` هو hashing-trick بـ256 بُعداً،
تشابهه بين "النبي محمد" و"الرسول الكريم" يساوي **صفراً**، وقاموسك
15 ألف كلمة على 256 خانة أي 59 كلمة تتصادم في البُعد الواحد.

لهذا لم تظهر أي نتيجة دلالية في العشرين الأولى قط، رغم وجود 60
نتيجة في `source_counts`. البحث الدلالي كان يضيف ضجيجاً لا معنى.

المنهج
------
واجهة **مطابقة** لـ EmbeddingBuilder، فتُستبدل بلا تعديل في المستدعين:

    vectorize_text(text) -> list[float]
    similarity(a, b)     -> float
    dimension            -> int

وإن تعذّر تحميل النموذج (غير مثبَّت، بلا إنترنت، ذاكرة غير كافية)
**يتراجع تلقائياً** إلى الطريقة القديمة مع تحذير مسجَّل — لا انهيار
ولا فشل صامت.

النماذج المقترحة
----------------
    paraphrase-multilingual-MiniLM-L12-v2   384 بُعد   ~470MB   سريع
    intfloat/multilingual-e5-base           768 بُعد   ~1.1GB   أدق
    BAAI/bge-m3                            1024 بُعد   ~2.2GB   الأفضل عربياً

ابدأ بالأول على المعالج، وانتقل صعوداً بعد القياس. لا تختر بالسمعة —
قِسْ على مجموعتك الذهبية.

schema_version: 2.0.0
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from typing import Any

logger = logging.getLogger(__name__)

EMBEDDINGS_VERSION = "2.0.0"

DEFAULT_MODEL = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
DEFAULT_BATCH = int(os.getenv("EMBEDDING_BATCH", "32"))

# نماذج معروفة وأبعادها، للتحقق دون تحميل
KNOWN_MODELS = {
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": 384,
    "intfloat/multilingual-e5-base": 768,
    "intfloat/multilingual-e5-large": 1024,
    "BAAI/bge-m3": 1024,
}


class HashingEmbedder:
    """
    الطريقة القديمة، مُبقاة كتراجع فقط.

    ليست دلالية: hashing للكلمات وثلاثيات الحروف. تُستعمل حين يتعذّر
    تحميل نموذج حقيقي، حتى لا يتوقف النظام. ومساهمتها في الترتيب
    يجب أن تبقى بوزن صفر (انظر reranker.py).
    """

    def __init__(self, dimension: int = 256):
        self.dimension = int(dimension)
        self.is_semantic = False
        self.model_name = "hashing"

    def _bucket(self, token: str) -> int:
        digest = hashlib.sha1(token.encode("utf-8")).digest()[:4]
        return int.from_bytes(digest, "big") % self.dimension

    def vectorize_text(self, text: str | None) -> list[float]:
        vec = [0.0] * self.dimension
        for token in (text or "").split():
            vec[self._bucket(token)] += 1.0
            for i in range(len(token) - 2):
                vec[self._bucket("tri:" + token[i : i + 3])] += 0.35
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec] if norm else vec

    def vectorize_many(self, texts: list[str]) -> list[list[float]]:
        return [self.vectorize_text(t) for t in texts]

    @staticmethod
    def similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        return float(sum(x * y for x, y in zip(a, b)))


class SemanticEmbedder:
    """
    Embeddings حقيقية عبر sentence-transformers.

    التحميل كسول: النموذج لا يُحمَّل إلا عند أول استعمال، فلا يبطئ
    الاستيراد ولا الاختبارات.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        *,
        batch_size: int = DEFAULT_BATCH,
        device: str | None = None,
    ):
        self.model_name = model_name
        self.batch_size = int(batch_size)
        self.device = device
        self._model: Any = None
        self._dimension: int | None = KNOWN_MODELS.get(model_name)
        self.is_semantic = True

    # -----------------------------------------------------------------
    @property
    def model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("تحميل نموذج التمثيل: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name, device=self.device)
            self._dimension = int(self._model.get_sentence_embedding_dimension())
        return self._model

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            _ = self.model  # يفرض التحميل لمعرفة البُعد
        return int(self._dimension or 0)

    # -----------------------------------------------------------------
    def vectorize_text(self, text: str | None) -> list[float]:
        cleaned = (text or "").strip()
        if not cleaned:
            return [0.0] * self.dimension
        vec = self.model.encode(
            cleaned, normalize_embeddings=True, show_progress_bar=False
        )
        return [float(x) for x in vec]

    def vectorize_many(self, texts: list[str]) -> list[list[float]]:
        """الدفعات أسرع كثيراً من الاستدعاء المفرد."""
        cleaned = [(t or "").strip() or " " for t in texts]
        if not cleaned:
            return []
        vecs = self.model.encode(
            cleaned,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [[float(x) for x in v] for v in vecs]

    @staticmethod
    def similarity(a: list[float], b: list[float]) -> float:
        """المتجهات مطبَّعة، فجداء النقطة هو جيب التمام."""
        if not a or not b or len(a) != len(b):
            return 0.0
        return float(sum(x * y for x, y in zip(a, b)))


# ---------------------------------------------------------------------------
# المصنع
# ---------------------------------------------------------------------------

def build_embedder(
    model_name: str | None = None,
    *,
    allow_fallback: bool = True,
    dimension: int = 256,
) -> HashingEmbedder | SemanticEmbedder:
    """
    يرجّع نموذجاً حقيقياً إن أمكن، وإلا يتراجع مع تحذير مسجَّل.

    allow_fallback=False يرفع الاستثناء بدل التراجع — استعمله في
    السكربتات التي يجب ألا تعمل على متجهات وهمية بصمت.
    """
    name = model_name or DEFAULT_MODEL

    try:
        import sentence_transformers  # noqa: F401
    except ImportError as exc:
        message = (
            "sentence-transformers غير مثبَّت. شغّل:\n"
            "    pip install sentence-transformers\n"
            "أو: python scripts/setup_embeddings.py --install"
        )
        if not allow_fallback:
            raise RuntimeError(message) from exc
        logger.warning("%s — التراجع إلى hashing (غير دلالي)", message)
        return HashingEmbedder(dimension=dimension)

    embedder = SemanticEmbedder(name)
    try:
        _ = embedder.dimension  # يفرض التحميل الآن لا وقت البحث
    except Exception as exc:
        if not allow_fallback:
            raise
        logger.warning(
            "تعذّر تحميل النموذج %s: %s — التراجع إلى hashing (غير دلالي)",
            name,
            exc,
        )
        return HashingEmbedder(dimension=dimension)

    logger.info("نموذج دلالي جاهز: %s (%d بُعد)", name, embedder.dimension)
    return embedder


# التوافق مع الاسم القديم: أي كود يستورد EmbeddingBuilder يبقى يعمل
EmbeddingBuilder = HashingEmbedder


__all__ = [
    "DEFAULT_MODEL",
    "EMBEDDINGS_VERSION",
    "KNOWN_MODELS",
    "EmbeddingBuilder",
    "HashingEmbedder",
    "SemanticEmbedder",
    "build_embedder",
]
