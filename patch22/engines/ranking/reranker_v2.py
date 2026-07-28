"""
Cross-Encoder + Learning to Rank + Confidence Calibration.

ثلاثتها في وحدة واحدة لأنها طبقة واحدة: تحويل الترتيب من قواعد
ثابتة إلى نظام يتعلّم ويعرف مقدار يقينه.

الحدّ المعلن
------------
**لا يُفعَّل أيٌّ منها بلا قياس.** كل واحد يبدأ بوزن صفر، ولا
يُرفع إلا بعد أن يُثبت على المجموعة الذهبية أنه حسّن. وهذا نصّ
المواصفة: "لا يُقبل أي تحسين جديد إلا إذا أثبت رقمياً أنه أفضل".

فالمكتوب هنا **الهيكل جاهزاً للتشغيل**، والتفعيل قرار قياس لا قرار كود.

schema_version: 1.0.0
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

RERANKER_V2_VERSION = "1.0.0"


# ===========================================================================
#  Cross-Encoder
# ===========================================================================

@dataclass(slots=True)
class RerankResult:
    element_id: str
    original_rank: int
    new_rank: int
    original_score: float
    cross_score: float
    moved: int = 0

    def as_dict(self) -> dict:
        return {"element_id": self.element_id, "original_rank": self.original_rank,
                "new_rank": self.new_rank, "cross_score": round(self.cross_score, 5),
                "moved": self.moved}


class CrossEncoderReranker:
    """
    إعادة ترتيب عميقة لأعلى N نتيجة.

    الفرق عن الـ bi-encoder: يقرأ السؤال والنص **معاً** فيفهم
    العلاقة بينهما، بدل مقارنة متجهين بُنيا منفصلين.

    التكلفة عالية، ولهذا يُطبَّق على أعلى 50–100 فقط بعد الاسترجاع
    لا قبله.

    النماذج المقترحة:
        BAAI/bge-reranker-v2-m3       متعدد اللغات، جيد عربياً
        jinaai/jina-reranker-v2-base  أخف
    """

    DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"

    def __init__(self, model_name: str | None = None, *, top_n: int = 50,
                 weight: float = 0.0, batch_size: int = 16):
        self.model_name = model_name or self.DEFAULT_MODEL
        self.top_n = int(top_n)
        # الوزن صفر افتراضاً: مبني لكن غير مفعَّل حتى يُقاس
        self.weight = float(weight)
        self.batch_size = int(batch_size)
        self._model = None
        self.version = RERANKER_V2_VERSION
        self.available = False

    def load(self) -> bool:
        """يحاول تحميل النموذج. يرجّع هل نجح."""
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            return False
        try:
            self._model = CrossEncoder(self.model_name, max_length=512)
            self.available = True
            return True
        except Exception:
            return False

    def score_pairs(self, query: str, texts: list[str]) -> list[float]:
        if not self.available or self._model is None or not texts:
            return [0.0] * len(texts)
        pairs = [(query, t or "") for t in texts]
        raw = self._model.predict(pairs, batch_size=self.batch_size)
        return [float(x) for x in raw]

    def rerank(self, query: str, results: list[dict]) -> tuple[list[dict], list[RerankResult]]:
        """
        يعيد الترتيب ويرجّع تقرير الحركة.

        الوزن صفر يعني: تُحسب الدرجات وتُسجَّل للقياس، ولا تُغيّر
        الترتيب. فيمكن قياس أثرها قبل تفعيلها.
        """
        if not results:
            return results, []

        head = results[: self.top_n]
        tail = results[self.top_n :]
        texts = [r.get("search_text") or r.get("text") or "" for r in head]
        scores = self.score_pairs(query, texts)

        for r, s in zip(head, scores):
            explain = r.setdefault("score_explain", {})
            explain["cross_encoder_raw"] = round(s, 5)
            if self.weight > 0:
                bonus = self.weight * _sigmoid(s)
                explain["cross_encoder"] = round(bonus, 5)
                r["score"] = float(r.get("score", 0.0)) + bonus

        original_order = {id(r): i for i, r in enumerate(head)}
        if self.weight > 0:
            head.sort(key=lambda r: -float(r.get("score", 0.0)))

        report = [
            RerankResult(
                element_id=str(r.get("element_id", "")),
                original_rank=original_order[id(r)],
                new_rank=i,
                original_score=float(r.get("score", 0.0)),
                cross_score=r.get("score_explain", {}).get("cross_encoder_raw", 0.0),
                moved=original_order[id(r)] - i,
            )
            for i, r in enumerate(head)
        ]
        return head + tail, report


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


# ===========================================================================
#  Learning to Rank
# ===========================================================================

FEATURE_NAMES = (
    "rrf_base", "sig_ocr_quality", "sig_coverage", "sig_completeness",
    "sig_density", "sig_length_prior", "sig_informativeness",
    "exact_raw", "layout", "cross_encoder_raw",
)


@dataclass(slots=True)
class LTRModel:
    """
    نموذج خطي بأوزان قابلة للتعلّم.

    خطي عمداً: قابل للتفسير. كل وزن يمكن قراءته ومساءلته، وهو شرط
    المواصفة "كل قرار مرفق بأسبابه". الشجري (LightGBM) أقوى رقمياً
    وأعتم تفسيراً — يُنتقل إليه بعد أن تكفي البيانات.
    """

    weights: dict[str, float] = field(default_factory=dict)
    trained_on: int = 0
    schema_version: str = RERANKER_V2_VERSION

    def score(self, features: dict) -> float:
        return sum(
            self.weights.get(name, 0.0) * float(features.get(name, 0.0) or 0.0)
            for name in FEATURE_NAMES
        )

    def as_dict(self) -> dict:
        return {"weights": {k: round(v, 6) for k, v in self.weights.items()},
                "trained_on": self.trained_on, "schema_version": self.schema_version}


class LearningToRank:
    """
    يتعلّم أوزان الإشارات من أحكام المجموعة الذهبية.

    الطريقة: انحدار على أزواج (نتيجة صحيحة، نتيجة خاطئة) بخطوات
    صغيرة. لا يحتاج مكتبة خارجية، ويكفي لعشرات الأسئلة.

    **لا يُدرَّب على النقرات**: النقرة تعني «بدا مفيداً» لا «كان
    صحيحاً»، والفرق جوهري في نصّ علمي.
    """

    def __init__(self, *, learning_rate: float = 0.05, epochs: int = 40,
                 max_weight: float = 0.03):
        self.learning_rate = float(learning_rate)
        self.epochs = int(epochs)
        # سقف الوزن يحفظ الدرس: أي إشارة تتجاوز حجم أساس RRF تبتلعه
        self.max_weight = float(max_weight)
        self.version = RERANKER_V2_VERSION

    def train(self, samples: list[tuple[dict, dict]]) -> LTRModel:
        """
        samples: أزواج (features_relevant, features_irrelevant)
        """
        model = LTRModel(weights={name: 0.0 for name in FEATURE_NAMES})
        if not samples:
            return model

        for _ in range(self.epochs):
            for good, bad in samples:
                margin = model.score(good) - model.score(bad)
                if margin >= 0.01:
                    continue  # مرتَّبان صحيحاً بهامش كافٍ
                for name in FEATURE_NAMES:
                    delta = (
                        float(good.get(name, 0.0) or 0.0)
                        - float(bad.get(name, 0.0) or 0.0)
                    )
                    w = model.weights[name] + self.learning_rate * delta
                    model.weights[name] = max(-self.max_weight,
                                              min(self.max_weight, w))

        model.trained_on = len(samples)
        return model

    @staticmethod
    def save(model: LTRModel, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(model.as_dict(), ensure_ascii=False, indent=2),
                     encoding="utf-8")

    @staticmethod
    def load(path: str | Path) -> LTRModel | None:
        p = Path(path)
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        return LTRModel(weights=data.get("weights", {}),
                        trained_on=data.get("trained_on", 0))


# ===========================================================================
#  Confidence Calibration
# ===========================================================================

@dataclass(slots=True)
class CalibrationBin:
    lower: float
    upper: float
    predicted: float
    observed: float
    count: int


class ConfidenceCalibrator:
    """
    يجعل 0.9 تعني 90% فعلاً.

    المشكلة: الثقة المحسوبة من قواعد ليست احتمالاً. قد يكون كل ما
    نال 0.9 صحيحاً في 60% فقط من الحالات — فالرقم يضلّل.

    الطريقة: انحدار رتيب (isotonic) مبسَّط — نقسّم الثقات إلى شرائح،
    ونقيس الصحة الفعلية في كل شريحة، ثم نفرض الرتابة (شريحة أعلى لا
    تقلّ عن أدنى منها). لا يحتاج scikit-learn.

    **يحتاج بيانات حقيقية**: أزواج (ثقة متوقَّعة، هل كانت صحيحة).
    وهي تأتي من المجموعة الذهبية لا من مكان آخر.
    """

    def __init__(self, *, n_bins: int = 10, min_per_bin: int = 5):
        self.n_bins = int(n_bins)
        self.min_per_bin = int(min_per_bin)
        self.bins: list[CalibrationBin] = []
        self.fitted = False
        self.version = RERANKER_V2_VERSION

    def fit(self, observations: list[tuple[float, bool]]) -> "ConfidenceCalibrator":
        if len(observations) < self.min_per_bin:
            self.fitted = False
            return self

        width = 1.0 / self.n_bins
        raw: list[CalibrationBin] = []
        for i in range(self.n_bins):
            lo, hi = i * width, (i + 1) * width
            inside = [
                (c, ok) for c, ok in observations
                if lo <= c < hi or (i == self.n_bins - 1 and c == 1.0)
            ]
            if len(inside) < self.min_per_bin:
                continue
            predicted = sum(c for c, _ in inside) / len(inside)
            observed = sum(1 for _, ok in inside if ok) / len(inside)
            raw.append(CalibrationBin(lo, hi, predicted, observed, len(inside)))

        # فرض الرتابة: الثقة الأعلى لا تعني صحةً أقل
        for i in range(1, len(raw)):
            if raw[i].observed < raw[i - 1].observed:
                merged = (raw[i].observed * raw[i].count
                          + raw[i - 1].observed * raw[i - 1].count)
                total = raw[i].count + raw[i - 1].count
                value = merged / total
                raw[i].observed = value
                raw[i - 1].observed = value

        self.bins = raw
        self.fitted = bool(raw)
        return self

    def calibrate(self, confidence: float) -> float:
        """يحوّل الثقة الخام إلى احتمال معايَر."""
        if not self.fitted:
            return round(float(confidence), 4)
        c = max(0.0, min(1.0, float(confidence)))
        for b in self.bins:
            if b.lower <= c < b.upper or (b.upper >= 1.0 and c == 1.0):
                return round(b.observed, 4)
        # خارج الشرائح المقاسة: أقرب شريحة
        nearest = min(self.bins, key=lambda b: abs(b.predicted - c))
        return round(nearest.observed, 4)

    def expected_calibration_error(self) -> float:
        """
        ECE — الفجوة بين المتوقَّع والملاحَظ.

        صفر يعني معايرة تامة. فوق 0.1 يعني أن الأرقام تضلّل.
        """
        if not self.bins:
            return 0.0
        total = sum(b.count for b in self.bins)
        return round(
            sum(b.count / total * abs(b.predicted - b.observed) for b in self.bins), 4
        )

    def report(self) -> dict:
        return {
            "fitted": self.fitted,
            "bins": [
                {"range": f"{b.lower:.1f}-{b.upper:.1f}",
                 "predicted": round(b.predicted, 3),
                 "observed": round(b.observed, 3), "count": b.count}
                for b in self.bins
            ],
            "ece": self.expected_calibration_error(),
            "note": "المعايرة تحتاج بيانات المجموعة الذهبية؛ بدونها تُرجَّع الثقة كما هي",
        }


__all__ = [
    "FEATURE_NAMES", "RERANKER_V2_VERSION", "CalibrationBin",
    "ConfidenceCalibrator", "CrossEncoderReranker", "LTRModel",
    "LearningToRank", "RerankResult",
]
