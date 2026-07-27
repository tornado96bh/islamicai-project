"""
اختبارات الدفعة السابعة عشرة — الربط الكامل.

تغطي العطب الذي أوقف E2E عندك، وأربعة أعطاب من مخرجاتك، وخط
الأنابيب الموحَّد من النية إلى التقرير.
"""

from __future__ import annotations

import json
import sys
import types

import pytest

from engines.evidence.bundle import EvidenceBuilder
from engines.evidence.verifier import Verdict, Verifier
from engines.report.builder import ReportBuilder
from packages.ingestion.ocr_corrector import Lexicon, OcrCorrector, fix_diacritic_splits
from packages.layout.hadith_number import parse_hadith_number, to_western_digits
from packages.search.signals import ocr_quality

_T = "\u0640"


# ===========================================================================
#  1) العطب الذي أوقف E2E: حزمة engines غير مثبَّتة
# ===========================================================================

@pytest.mark.parametrize("module", [
    "engines.evidence.bundle", "engines.evidence.verifier",
    "engines.narrator.gazetteer", "engines.planner.planner",
    "engines.memory.memory", "engines.pipeline.orchestrator",
    "engines.report.builder",
])
def test_every_engine_is_importable(module):
    """
    ModuleNotFoundError: No module named 'engines'

    السبب أن pyproject كان يعرّف الحزم بـ ["apps*", "packages*"]
    فقط، فلا تُثبَّت engines ولا تُستورَد.
    """
    __import__(module)


# ===========================================================================
#  2) المسافة بعد الحركة — العطب القاتل في أسماء الرواة
# ===========================================================================

@pytest.fixture
def corrector(tmp_path):
    words = {"محمد": 2651, "يعقوب": 900, "الله": 19673, "عن": 15000,
             "من": 9000, "بن": 12000, "د": 16359, "محم": 13427}
    p = tmp_path / "d.json"
    p.write_text(json.dumps(
        {"entries": [{"word": w, "frequency": f} for w, f in words.items()]},
        ensure_ascii=False), encoding="utf-8")
    return OcrCorrector(Lexicon(p))


@pytest.mark.parametrize("broken,expected", [
    ("محمّ د بن يحيى", "محمّد"),
    ("عن عدّ ة من أصحابنا", "عدّة"),
    ("إنّ ه ليصوم اليوم", "إنّه"),
    ("محمّ د بن يعقوب", "محمّد"),
])
def test_diacritic_split_is_rejoined(broken, expected):
    """
    "محمّ د" لا تتطابق مع "محمد" في الفهرسة، فينكسر ربط الرواة.
    القاعدة قاطعة بذاتها ولا تحتاج معجماً: لا تبدأ كلمة عربية
    بحرف واحد بعد شدّة.
    """
    out, n = fix_diacritic_splits(broken)
    assert expected in out and n >= 1


@pytest.mark.parametrize("safe", [
    "قال رسول الله ، الماء يطهر",
    "عن أبيه ، عن سعد بن عبد الله",
    "في الحديث ١ من الباب ٤",
])
def test_valid_text_untouched_by_diacritic_fix(safe):
    out, n = fix_diacritic_splits(safe)
    assert out == safe and n == 0


def test_corrector_applies_the_fix(corrector):
    out, stats = corrector.correct("محمّ د بن يعقوب")
    assert "محمّد" in out and stats.words_merged >= 1


# ===========================================================================
#  3) إشارة الجودة: تمديد طباعي ليس فشل قراءة
# ===========================================================================

def test_tatweel_is_not_treated_as_failure():
    """
    "محمّـــــ د بـــــن يحـــــيى" مقروء تماماً، لكنه نال 0.00
    فاستُبعد من حزمة الأدلة. التمديد تنسيق صفحة لا خطأ بصري.
    """
    stretched = "محمّـــــ د بـــــن يحـــــيى".replace("ـ", _T)
    assert ocr_quality(stretched) >= 0.6


def test_misread_alef_is_penalised():
    """"االله" خطأ قراءة يغيّر الحروف — أخطر من التمديد."""
    assert ocr_quality("االله علـيهم ( قال : قال رسول االله".replace("ـ", _T)) < 0.5


def test_real_fragmentation_still_penalised():
    assert ocr_quality("عمير ، عن حم ، اد عن الحلبي") < 0.5


def test_short_real_words_are_not_fragments():
    """
    "عن" و"من" كلمتان صحيحتان. عدّهما شظيتين عاقب كل سند سليم.
    """
    assert ocr_quality("عن أبيه ، عن سعد بن عبد الله") >= 0.8


def test_clean_text_scores_full():
    assert ocr_quality("قال رسول الله : الماء يطهر ولا يطهر") >= 0.95


# ===========================================================================
#  4) رقم الرواية
# ===========================================================================

@pytest.mark.parametrize("raw,hadith,sequence", [
    ("] ٠٢٦ [ ٦", 26, 6),
    ("] ٧٣١ [ ١", 731, 1),
    ("] ٨١١ ١ [", 811, 1),
    ("[ 29214 ] 1", 29214, 1),
])
def test_hadith_number_parsed(raw, hadith, sequence):
    """"] ٠٢٦ [ ٦" أرقام هندية بأقواس ورقمين مختلطين."""
    p = parse_hadith_number(raw)
    assert p.hadith == hadith and p.sequence == sequence


def test_arabic_indic_digits_converted():
    assert to_western_digits("٠٢٦") == "026"


def test_empty_number_is_declared_not_guessed():
    p = parse_hadith_number("")
    assert p.hadith is None and p.confidence == 0.0 and p.reason


# ===========================================================================
#  5) كشف التعارض: الجملة المبيِّنة ليست تعارضاً
# ===========================================================================

def _row(eid, page, quality, text):
    return {
        "element_id": eid, "book_id": "b1", "book_title": "وسائل",
        "page_number": page, "volume_number": 1, "text": text,
        "text_display": text, "best_element_type": "matn", "score": 0.1,
        "matn_text": text, "score_explain": {"sig_ocr_quality": quality},
    }


def _bundle(rows, intent="hadith", conf=0.81):
    return EvidenceBuilder().build(
        {"query": "س", "intent": {"label": intent, "confidence": conf},
         "results": rows}
    )


def test_explanatory_phrase_is_not_a_contradiction():
    """
    "الماء يطهر ولا يطهر" جملة واحدة تفيد أنه مطهِّر لا متطهِّر.
    عدّها تعارضاً أرسل أحاديث سليمة إلى المراجعة بلا سبب.
    """
    r = Verifier().verify(_bundle([
        _row("a", 1, 0.9, "الماء يطهر ولا يطهر"),
        _row("b", 2, 0.9, "الماء يطهر ولا يطهر أبدا"),
    ]))
    assert r.verdict is Verdict.ANSWERABLE and not r.conflicts


def test_real_contradiction_still_detected():
    r = Verifier().verify(_bundle([
        _row("a", 1, 0.9, "قال : يجوز المسح على الخفين"),
        _row("b", 2, 0.9, "قال : لا يجوز المسح على الخفين"),
    ], intent="ruling"))
    assert r.verdict is Verdict.NEEDS_REVIEW and r.conflicts


# ===========================================================================
#  6) خط الأنابيب الموحَّد
# ===========================================================================

@pytest.fixture
def wired_pipeline(monkeypatch):
    """يركّب محرك بحث وهمياً بشكل مخرجاتك الفعلية."""
    def mk(eid, page, q, text, isnad=None, etype="matn"):
        d = _row(eid, page, q, text)
        d["isnad_text"] = isnad
        d["best_element_type"] = etype
        d["ranking_version"] = "2.3.0"
        return d

    class FakeEngine:
        def __init__(self, db):
            pass

        def search(self, q, limit=20):
            return {
                "query": q,
                "results": [
                    mk("e1", 134, 0.88, "قال رسول الله : الماء يطهر",
                       "محمد بن يعقوب ، عن علي بن ابراهيم", "sanad"),
                    mk("e2", 240, 0.75, "عن ابي عبد الله : الماء يطهر",
                       "محمد بن يحيى ، عن احمد بن محمد", "sanad"),
                    mk("e3", 70, 0.0, "االله علـيهم"),
                ],
                "source_counts": {"fts": 320, "semantic": 60},
                "entity_suggestions": [
                    {"label": "احمد بن محمد", "original_label": "عن احمد بن محمد عن",
                     "kind": "person", "score": 7.8, "frequency": 160},
                    {"label": "احمد بن محمد", "original_label": "عن احمد بن محمد بن",
                     "kind": "person", "score": 7.1, "frequency": 88},
                ],
            }

    fake = types.ModuleType("packages.search.engine")
    fake.SearchEngine = FakeEngine
    monkeypatch.setitem(sys.modules, "packages.search.engine", fake)

    from engines.pipeline.orchestrator import Pipeline

    return Pipeline(None, use_memory=False)


def test_pipeline_runs_every_stage(wired_pipeline):
    out = wired_pipeline.run("الماء يطهر ولا يطهر").as_dict()
    stages = {s["stage"] for s in out["trace"]}
    for expected in ("intent", "planner", "search", "entities",
                     "narrator", "evidence", "verifier", "answer"):
        assert expected in stages, f"الخطوة {expected} غائبة"


def test_pipeline_deduplicates_entities(wired_pipeline):
    """"احمد بن محمد" كان يظهر مرتين بترددين منفصلين."""
    out = wired_pipeline.run("س").as_dict()
    labels = [e["label"] for e in out["entity_suggestions"]]
    assert len(labels) == len(set(labels))


def test_pipeline_resolves_narrators(wired_pipeline):
    out = wired_pipeline.run("س").as_dict()
    resolved = [n for n in out["narrators"]
                if n["resolution"] in ("exact", "alias")]
    assert len(resolved) >= 3


def test_pipeline_rejects_bad_scans_with_a_reason(wired_pipeline):
    out = wired_pipeline.run("س").as_dict()
    assert out["evidence"]["rejected"]
    assert out["evidence"]["rejected"][0]["reason"]


def test_pipeline_trace_explains_every_stage(wired_pipeline):
    out = wired_pipeline.run("س").as_dict()
    for s in out["trace"]:
        assert s["stage"]
        assert s["skipped"] or s["ms"] >= 0


def test_pipeline_records_versions_for_reproducibility(wired_pipeline):
    versions = wired_pipeline._versions()
    assert "pipeline" in versions and "ocr" in versions


# ===========================================================================
#  7) التقرير الشامل
# ===========================================================================

def test_report_has_all_sections(wired_pipeline):
    out = wired_pipeline.run("الماء يطهر").as_dict()
    report = ReportBuilder().build(out)
    titles = {s.title for s in report.sections}
    assert "الخلاصة" in titles
    assert "أساس الحكم" in titles
    assert "مسار المعالجة" in titles


def test_report_never_adjudicates_conflicts():
    """"لا حكم تلقائياً" — التعارض يُعرض ولا يُرجَّح."""
    payload = {
        "query": "س", "answer": {"answered": False, "refusal_reason": "تعارض"},
        "verification": {"verdict": "needs_review", "confidence": 0.6,
                         "conflicts": ["تعارض ظاهر بين «يجوز» و«لا يجوز»"],
                         "checks": [], "missing": []},
        "evidence": {}, "narrators": [], "trace": [],
    }
    report = ReportBuilder().build(payload)
    section = next(s for s in report.sections if "تعارض" in s.title)
    assert "لا يرجّح" in section.body or "المحقق" in section.note


def test_report_renders_as_text(wired_pipeline):
    out = wired_pipeline.run("س").as_dict()
    text = ReportBuilder().build(out).to_text()
    assert "تقرير:" in text and len(text) > 100
