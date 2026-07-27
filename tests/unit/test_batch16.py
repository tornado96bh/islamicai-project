"""
اختبارات الدفعة السادسة عشرة — محركات المواصفة.

تغطي: Evidence + Verifier + FinalAnswer (القسم 6.2)، Narrator
Engine (القسم 8)، Planner، Memory، والحوكمة (القسم 9).
"""

from __future__ import annotations

import pytest

from engines.evidence.bundle import EvidenceBuilder, EvidenceKind
from engines.evidence.verifier import Verdict, Verifier, compose
from engines.memory.memory import MemoryEngine
from engines.narrator.gazetteer import NarratorGazetteer, Resolution
from engines.planner.planner import Planner, Route
from packages.governance.audit import (
    AuditAction, AuditLog, Budget, BudgetExceeded, CircuitBreaker,
    Permission, PermissionDenied, Role, has_permission, require_permission,
)
from packages.learning.entity_dedup import deduplicate
from packages.learning.entity_filter import classify_entity


def _row(eid, page, quality, text="قال رسول الله : الماء يطهر", book="b1"):
    return {
        "element_id": eid, "book_id": book, "book_title": "وسائل الشيعة",
        "page_number": page, "volume_number": 1, "text": text,
        "text_display": text, "best_element_type": "matn", "score": 0.1,
        "matn_text": text, "ranking_version": "2.3.0",
        "score_explain": {"sig_ocr_quality": quality},
    }


def _payload(rows, intent="hadith", conf=0.81, query="الماء يطهر"):
    return {"query": query, "intent": {"label": intent, "confidence": conf},
            "results": rows}


# ===========================================================================
#  Evidence Engine — القسم 6.2
# ===========================================================================

def test_bundle_rejects_low_quality_with_a_reason():
    """
    الحذف الصامت يخالف "كل قرار قابل للتفسير" — لكل مرفوض سبب.
    """
    b = EvidenceBuilder().build(_payload([_row("a", 10, 0.9), _row("b", 11, 0.0)]))
    assert len(b.items) == 1
    assert b.rejected and "جودة" in b.rejected[0][1]


def test_provenance_is_complete_for_citation():
    b = EvidenceBuilder().build(_payload([_row("a", 10, 0.9)]))
    item = b.items[0]
    assert item.provenance.is_complete()
    assert "ج1" in item.provenance.citation() and "ص10" in item.provenance.citation()


def test_bad_scan_is_not_citable_however_high_it_ranks():
    """النص الرديء المسح ليس مرجعاً علمياً مهما علا ترتيبه."""
    b = EvidenceBuilder(min_ocr_quality=0.0).build(_payload([_row("a", 10, 0.1)]))
    assert b.items and not b.items[0].is_citable


def test_distinct_sources_counts_positions_not_items():
    """دليلان من صفحة واحدة ليسا مستقلين."""
    b = EvidenceBuilder().build(_payload([_row("a", 10, 0.9), _row("b", 10, 0.9)]))
    assert len(b.citable) == 2 and b.distinct_sources == 1


# ===========================================================================
#  Verifier + FinalAnswer
# ===========================================================================

def test_sufficient_evidence_is_answerable():
    b = EvidenceBuilder().build(_payload([_row("a", 10, 0.9), _row("b", 20, 0.85)]))
    r = Verifier().verify(b)
    assert r.verdict is Verdict.ANSWERABLE and r.confidence >= 0.7


def test_single_weak_source_is_refused():
    """
    "لا تخمين عند نقص الأدلة" — الرفض المعلَّل نتيجة صحيحة.
    """
    b = EvidenceBuilder().build(
        _payload([_row("a", 10, 0.3)], intent="general", conf=0.2, query="الله")
    )
    r = Verifier().verify(b)
    a = compose(b, r)
    assert not a.answered
    assert a.refusal_reason and r.missing


def test_no_answer_without_citation():
    """لا إجابة بلا استشهاد، مهما كانت الدرجة."""
    b = EvidenceBuilder().build(_payload([]))
    a = compose(b, Verifier().verify(b))
    assert not a.answered and not a.citations


def test_every_check_is_named_and_scored():
    b = EvidenceBuilder().build(_payload([_row("a", 10, 0.9), _row("b", 20, 0.9)]))
    r = Verifier().verify(b)
    assert len(r.checks) == 5
    for c in r.checks:
        assert c.name and c.detail and 0.0 <= c.score <= 1.0


def test_contradiction_escalates_to_review_not_a_verdict():
    """
    "لا حكم تلقائياً" — التعارض يُعرض للمحقق ولا يُرجَّح آلياً.
    """
    rows = [
        _row("a", 10, 0.9, "قال : يجوز المسح على الخفين"),
        _row("b", 20, 0.9, "قال : لا يجوز المسح على الخفين"),
    ]
    r = Verifier().verify(EvidenceBuilder().build(_payload(rows)))
    assert r.verdict is Verdict.NEEDS_REVIEW and r.conflicts


def test_answer_carries_citations_with_positions():
    b = EvidenceBuilder().build(_payload([_row("a", 10, 0.9), _row("b", 20, 0.9)]))
    a = compose(b, Verifier().verify(b))
    assert a.answered
    for c in a.citations:
        assert c["citation"] and c["element_id"]


# ===========================================================================
#  Narrator Engine — القسم 8
# ===========================================================================

@pytest.fixture(scope="module")
def gazetteer():
    return NarratorGazetteer()


def test_gazetteer_loads_seed_narrators(gazetteer):
    assert len(gazetteer) >= 25 and gazetteer.loaded


@pytest.mark.parametrize("name,canonical", [
    ("محمد بن يعقوب", "محمد بن يعقوب الكليني"),
    ("الكليني", "محمد بن يعقوب الكليني"),
    ("ابن ابي عمير", "محمد بن أبي عمير"),
    ("علي بن ابراهيم", "علي بن إبراهيم القمي"),
    ("زرارة", "زرارة بن أعين"),
])
def test_resolves_real_narrators_from_your_output(gazetteer, name, canonical):
    r = gazetteer.resolve(name)
    assert r.resolved and r.narrator.canonical_name == canonical


def test_unknown_narrator_is_declared_not_invented(gazetteer):
    """"لا تخمين عند نقص الأدلة" — لا يُخترع معرّف لاسم مجهول."""
    r = gazetteer.resolve("فلان بن فلان الذي لا وجود له")
    assert r.resolution is Resolution.UNRESOLVED
    assert r.narrator is None and r.reason


def test_chain_coverage_is_measured(gazetteer):
    cov = gazetteer.coverage(["محمد بن يعقوب", "علي بن ابراهيم", "مجهول"])
    assert 0.5 <= cov < 1.0


# ===========================================================================
#  Planner Engine — القسم 8
# ===========================================================================

def test_semantic_is_skipped_for_a_single_common_word():
    """
    البحث الدلالي عن "الله" أرجع 60 نتيجة أُقصيت كلها — زمن بلا فائدة.
    """
    p = Planner().plan("الله", "general", 0.20)
    assert Route.SEMANTIC not in p.routes
    assert p.ask_clarification and p.clarification


def test_narrator_query_skips_semantic(gazetteer):
    p = Planner().plan("زرارة بن أعين", "narrator", 0.9)
    assert Route.GAZETTEER in p.routes and Route.SEMANTIC not in p.routes


def test_concept_query_leads_with_semantic():
    p = Planner().plan("ما معنى البر والتقوى", "concept", 0.79)
    assert p.routes[0] is Route.SEMANTIC


def test_plan_states_its_reasons():
    for label, conf in [("narrator", 0.9), ("chapter", 0.85), ("general", 0.2)]:
        assert Planner().plan("س", label, conf).reasons


# ===========================================================================
#  Memory Engine — Safe Learning، القسم 9
# ===========================================================================

def test_memory_stores_only_verified_results(tmp_path):
    m = MemoryEngine(tmp_path / "m.json")
    assert m.remember("q", "hadith", "answerable", 0.9, {}, {"ocr": "1.3.0"})
    assert not m.remember("q2", "hadith", "insufficient", 0.9, {}, {})
    assert not m.remember("q3", "hadith", "answerable", 0.4, {}, {})


def test_memory_invalidates_on_version_change(tmp_path):
    """نتيجة بُنيت بمصحّح قديم لم تعد صالحة بعد ترقيته."""
    m = MemoryEngine(tmp_path / "m.json")
    m.remember("q", "hadith", "answerable", 0.9, {"x": 1}, {"ocr": "1.2.0"})
    assert m.recall("q", "hadith", {"ocr": "1.2.0"}) is not None
    assert m.recall("q", "hadith", {"ocr": "1.3.0"}) is None


def test_human_correction_clears_memory(tmp_path):
    m = MemoryEngine(tmp_path / "m.json")
    m.remember("q", "hadith", "answerable", 0.9, {}, {})
    assert m.invalidate_all("تصحيح بشري") == 1


# ===========================================================================
#  الحوكمة — القسم 9
# ===========================================================================

@pytest.mark.parametrize("role,perm,allowed", [
    (Role.GUEST, Permission.SEARCH, True),
    (Role.GUEST, Permission.REINDEX, False),
    (Role.RESEARCHER, Permission.PROPOSE_CORRECTION, True),
    (Role.RESEARCHER, Permission.APPROVE_CORRECTION, False),
    (Role.VERIFIER, Permission.APPROVE_CORRECTION, True),
    (Role.ADMIN, Permission.MANAGE_USERS, True),
])
def test_rbac_matrix(role, perm, allowed):
    assert has_permission(role, perm) is allowed


def test_denied_permission_states_the_reason():
    with pytest.raises(PermissionDenied) as exc:
        require_permission(Role.GUEST, Permission.MANAGE_USERS)
    assert "guest" in str(exc.value)


def test_circuit_breaker_trips_on_result_budget():
    cb = CircuitBreaker(Budget(max_results=50))
    with cb.guard():
        with pytest.raises(BudgetExceeded):
            for _ in range(4):
                cb.add_results(20)
    assert cb.tripped and cb.trip_reason


def test_circuit_breaker_trips_on_expansion_budget():
    cb = CircuitBreaker(Budget(max_expansions=3))
    with cb.guard():
        with pytest.raises(BudgetExceeded):
            for _ in range(5):
                cb.add_expansion()


def test_audit_records_carry_actor_and_reason():
    log = AuditLog()
    log.record(AuditAction.ANSWER_REFUSED, "salim", Role.RESEARCHER,
               {"query": "الله"}, "أدلة غير كافية")
    rec = log.records[0]
    assert rec.actor and rec.reason and rec.at and rec.record_id


def test_audit_is_append_only(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    log.record(AuditAction.SEARCH, "a", Role.GUEST)
    assert log.flush() == 1
    log.record(AuditAction.SEARCH, "b", Role.GUEST)
    log.flush()
    assert len((tmp_path / "a.jsonl").read_text(encoding="utf-8").strip().split("\n")) == 2


# ===========================================================================
#  تنظيف الكيانات وتوحيدها
# ===========================================================================

@pytest.mark.parametrize("label,cleaned", [
    ("، عن ابن ابي عمير", "ابن ابي عمير"),
    ("، عن الحسين بن سعيد ،", "الحسين بن سعيد"),
    ("ابن محبوب", "ابن محبوب"),
])
def test_entity_boundaries_are_sanitised(label, cleaned):
    """"، عن ابن ابي عمير" ظهرت كياناً في مخرجاتك."""
    v = classify_entity(label)
    assert v.accepted and v.cleaned_label == cleaned


def test_pure_punctuation_rejected():
    assert not classify_entity("، ، ،").accepted


def test_duplicate_entities_are_merged():
    """"احمد بن محمد" ظهر مرتين بترددين منفصلين."""
    out = deduplicate([
        {"label": "احمد بن محمد", "original_label": "عن احمد بن محمد عن",
         "kind": "person", "score": 7.84, "frequency": 160, "document_frequency": 160},
        {"label": "احمد بن محمد", "original_label": "عن احمد بن محمد بن",
         "kind": "person", "score": 7.16, "frequency": 88, "document_frequency": 88},
    ])
    assert len(out) == 1
    assert out[0]["frequency"] == 248
    assert out[0]["merged_count"] == 2
    assert len(out[0]["variants"]) == 2


def test_dedup_keeps_max_score_not_sum():
    """الدرجة قياس صلة لا كمية، فلا تُجمع."""
    out = deduplicate([
        {"label": "س", "kind": "person", "score": 5.0, "frequency": 1},
        {"label": "س", "kind": "person", "score": 8.0, "frequency": 1},
    ])
    assert out[0]["score"] == 8.0
