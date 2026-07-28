"""اختبارات الدفعة العشرين — المحركات الثمانية."""

from __future__ import annotations

import random

import pytest

from engines.fiqh.reasoner import FiqhReasoner, Ruling, Strength
from engines.graph.knowledge_graph import EdgeType, KnowledgeGraph, NodeType
from engines.ontology.concepts import Ontology
from engines.ranking.reranker_v2 import (
    ConfidenceCalibrator, CrossEncoderReranker, LearningToRank,
)
from engines.reasoning.contradiction import ContradictionEngine, ReconciliationKind
from engines.reasoning.temporal import (
    Contemporaneity, Lifespan, TemporalReasoner,
)


# ===========================================================================
#  Knowledge Graph
# ===========================================================================

@pytest.fixture
def graph():
    g = KnowledgeGraph()
    for nid, label in [("n011", "زرارة"), ("n016", "ابن أبي عمير"),
                       ("n014", "حماد"), ("n012", "محمد بن مسلم")]:
        g.add_node(nid, NodeType.NARRATOR, label)
    g.add_edge("n016", "n014", EdgeType.NARRATED_FROM, evidence=["e1"])
    g.add_edge("n014", "n011", EdgeType.NARRATED_FROM, evidence=["e1"])
    g.add_edge("n016", "n012", EdgeType.NARRATED_FROM, evidence=["e2"])
    return g


def test_multi_hop_question(graph):
    """
    "من روى عن زرارة وروى عنه ابن أبي عمير؟" — سؤال مسار لا مطابقة.
    """
    paths = graph.find_paths("n016", "n011")
    assert paths
    assert "n014" in paths[0].nodes and paths[0].hops == 2


def test_edges_carry_evidence(graph):
    """لا علاقة بلا دليل."""
    for edge in graph.neighbours("n016"):
        assert edge.evidence


def test_duplicate_edge_strengthens_not_duplicates(graph):
    before = len(graph.neighbours("n016", EdgeType.NARRATED_FROM))
    graph.add_edge("n016", "n014", EdgeType.NARRATED_FROM, evidence=["e9"])
    after = graph.neighbours("n016", EdgeType.NARRATED_FROM)
    assert len(after) == before
    assert "e9" in [e for edge in after for e in edge.evidence]


def test_no_cycles_in_paths(graph):
    graph.add_edge("n011", "n016", EdgeType.NARRATED_FROM)
    for p in graph.find_paths("n016", "n011"):
        assert len(p.nodes) == len(set(p.nodes))


def test_graph_roundtrip(graph, tmp_path):
    """الشبكة طبقة مشتقة: تُحفظ وتُعاد بناؤها كاملة."""
    path = tmp_path / "g.json"
    graph.save(path)
    loaded = KnowledgeGraph.load(path)
    assert loaded.stats()["nodes"] == graph.stats()["nodes"]
    assert loaded.stats()["edges"] == graph.stats()["edges"]


# ===========================================================================
#  Ontology
# ===========================================================================

@pytest.fixture(scope="module")
def ontology():
    return Ontology()


def test_ontology_loads(ontology):
    assert len(ontology) >= 20 and ontology.loaded


def test_expansion_by_concept_not_by_word(ontology):
    """"الطهارة" تجلب الوضوء والغسل — لأنها فروعها لا لتشابه اللفظ."""
    r = ontology.expand_query("الطهارة")
    terms = " ".join(r["expanded_terms"])
    assert "وضوء" in terms and "غسل" in terms and "تيمم" in terms


def test_exclusion_makes_negative_queries_possible(ontology):
    """"الوضوء عدا الجبيرة" سؤال علاقات لا ألفاظ."""
    r = ontology.expand_query("الوضوء")
    assert any("جبيرة" in t or "الجبيرة" in t for t in r["excluded_terms"])


def test_path_to_root(ontology):
    chain = ontology.path_to_root("c152")
    assert "طهارة" in chain and "فقه" in chain


def test_unknown_text_matches_nothing(ontology):
    assert ontology.expand_query("كلام لا صلة له بشيء")["concepts"] == []


# ===========================================================================
#  Temporal Reasoning
# ===========================================================================

@pytest.fixture
def temporal():
    return TemporalReasoner()


def test_impossible_meeting_detected(temporal):
    """الكليني (ت329) لا يروي عن زرارة (ت150) — سند منقطع."""
    v = temporal.can_meet(Lifespan("الكليني", death=329),
                          Lifespan("زرارة", death=150))
    assert v.relation is Contemporaneity.IMPOSSIBLE and v.reason


def test_possible_meeting_accepted(temporal):
    v = temporal.can_meet(Lifespan("ابن أبي عمير", death=217),
                          Lifespan("حماد", death=209))
    assert v.relation in (Contemporaneity.CERTAIN, Contemporaneity.LIKELY)


def test_missing_dates_never_judged_as_broken(temporal):
    """الحكم بالانقطاع بلا بيانات أسوأ من الامتناع."""
    v = temporal.can_meet(Lifespan("مجهول"), Lifespan("زرارة", death=150))
    assert v.relation is Contemporaneity.UNKNOWN
    assert "لا يُحكم" in " ".join(v.assumptions)


def test_estimates_are_declared(temporal):
    v = temporal.can_meet(Lifespan("أ", death=250), Lifespan("ب", death=200))
    assert v.assumptions, "التقدير يجب أن يُعلَن"


def test_chain_continuity(temporal):
    chain = [Lifespan("الكليني", death=329), Lifespan("زرارة", death=150)]
    result = temporal.check_chain(chain)
    assert result["breaks"] == 1 and result["verdict"] == "منقطع"


# ===========================================================================
#  Contradiction Engine
# ===========================================================================

@pytest.fixture
def contradiction(ontology):
    return ContradictionEngine(ontology)


def test_real_contradiction_detected(contradiction):
    conflicts = contradiction.detect([
        {"id": "a", "text": "قال : لا يجوز المسح على الخفين"},
        {"id": "b", "text": "قال : يجوز المسح على الخفين إذا كان في سفر"},
    ])
    assert len(conflicts) == 1
    assert conflicts[0].trigger == ("يجوز", "لا يجوز")


def test_different_topics_are_not_contradictions(contradiction):
    """اختلاف الموضوع ليس تعارضاً."""
    conflicts = contradiction.detect([
        {"id": "a", "text": "لا يجوز المسح على الخفين في الوضوء"},
        {"id": "b", "text": "يجوز البيع بالتقسيط في المعاملات والتجارة"},
    ])
    assert not conflicts


def test_explanatory_sentence_is_not_a_contradiction(contradiction):
    """"الماء يطهر ولا يطهر" جملة واحدة مبيِّنة."""
    conflicts = contradiction.detect([
        {"id": "a", "text": "الماء يطهر ولا يطهر"},
        {"id": "b", "text": "الماء يطهر ولا يطهر أبدا"},
    ])
    assert not conflicts


def test_reconciliation_suggested_not_chosen(contradiction):
    """"لا حكم تلقائياً" — تُعرض الوجوه ولا يُرجَّح بينها."""
    conflicts = contradiction.detect([
        {"id": "a", "text": "قال : لا يجوز المسح على الخفين"},
        {"id": "b", "text": "قال : يجوز المسح على الخفين إذا كان في سفر"},
    ])
    c = conflicts[0]
    assert c.reconciliations
    assert any(r.kind is ReconciliationKind.GENERAL_SPECIFIC
               for r in c.reconciliations)
    assert "لمحقق" in c.note or "المحقق" in c.note
    assert all(r.confidence < 0.7 for r in c.reconciliations)


def test_report_declares_the_principle(contradiction):
    report = contradiction.report(contradiction.detect([]))
    assert "لا يرجّح" in report["principle"]


# ===========================================================================
#  Fiqh Engine
# ===========================================================================

@pytest.fixture
def fiqh(ontology, contradiction):
    return FiqhReasoner(ontology, contradiction)


def test_explicit_ruling_recognised(fiqh):
    r = fiqh.read_evidence("h1", "قال : لا يجوز المسح على الخفين",
                           ["المسح على الخفين", "الخفين"])
    assert r.ruling is Ruling.FORBIDDEN and r.strength is Strength.EXPLICIT


def test_off_topic_marker_is_weak(fiqh):
    """لفظ حكمي في غير موضوع المسألة لا يُعتدّ به."""
    r = fiqh.read_evidence("h3", "يجب غسل الوجه في الوضوء", ["الخفين"])
    assert r.strength is Strength.WEAK


def test_no_marker_is_irrelevant(fiqh):
    r = fiqh.read_evidence("h4", "الماء إذا بلغ كرا لم ينجسه شيء", ["الخفين"])
    assert r.strength is Strength.IRRELEVANT


def test_analysis_never_issues_a_fatwa(fiqh):
    """الحدّ المعلن: عرض الأدلة لا الإفتاء."""
    a = fiqh.analyse("ما حكم المسح على الخفين", [
        {"id": "h1", "text": "قال : لا يجوز المسح على الخفين"},
        {"id": "h2", "text": "قال : يجوز المسح على الخفين إذا كان في سفر"},
    ]).as_dict()
    assert "ليس فتوى" in a["disclaimer"]
    assert "final_ruling" not in a
    assert a["missing"], "ما ينقص للحسم يجب أن يُقال"


def test_divergent_evidence_is_flagged(fiqh):
    a = fiqh.analyse("ما حكم المسح على الخفين", [
        {"id": "h1", "text": "قال : لا يجوز المسح على الخفين"},
        {"id": "h2", "text": "قال : يجوز المسح على الخفين إذا كان في سفر"},
    ])
    assert len(a.distribution) >= 2
    assert any("ترجيح" in m for m in a.missing)


# ===========================================================================
#  Cross-Encoder / LTR / Calibration
# ===========================================================================

def test_cross_encoder_degrades_safely():
    """غياب النموذج لا يوقف الترتيب ولا يغيّره."""
    ce = CrossEncoderReranker()
    results = [{"element_id": "a", "text": "س", "score": 0.1},
               {"element_id": "b", "text": "ص", "score": 0.09}]
    out, report = ce.rerank("سؤال", results)
    assert [r["element_id"] for r in out] == ["a", "b"]
    assert len(report) == 2


def test_cross_encoder_weight_starts_at_zero():
    """
    "لا يُقبل تحسين إلا إذا أثبت رقمياً أنه أفضل" — فالوزن صفر
    حتى يُقاس على المجموعة الذهبية.
    """
    assert CrossEncoderReranker().weight == 0.0


def test_ltr_respects_the_rrf_scale():
    """درس الدفعة الثالثة: أي وزن يتجاوز حجم RRF يبتلع الترتيب."""
    samples = [({"rrf_base": 0.02, "sig_ocr_quality": 0.9, "sig_coverage": 1.0},
                {"rrf_base": 0.01, "sig_ocr_quality": 0.1, "sig_coverage": 0.5})] * 20
    model = LearningToRank().train(samples)
    assert all(abs(w) <= 0.03 for w in model.weights.values())


def test_ltr_learns_the_right_direction():
    samples = [({"sig_ocr_quality": 0.9}, {"sig_ocr_quality": 0.1})] * 20
    model = LearningToRank().train(samples)
    assert model.weights["sig_ocr_quality"] > 0


def test_ltr_with_no_data_is_neutral():
    model = LearningToRank().train([])
    assert all(w == 0.0 for w in model.weights.values())


def test_calibration_detects_overconfidence():
    """0.9 يجب أن تعني 90% فعلاً، وإلا فالرقم يضلّل."""
    random.seed(3)
    observations = [(c, random.random() < c * 0.65)
                    for c in (random.random() for _ in range(300))]
    cal = ConfidenceCalibrator().fit(observations)
    assert cal.fitted
    assert cal.expected_calibration_error() > 0.05
    assert cal.calibrate(0.9) < 0.9


def test_calibration_is_monotonic():
    random.seed(7)
    observations = [(c, random.random() < c) for c in
                    (random.random() for _ in range(400))]
    cal = ConfidenceCalibrator().fit(observations)
    values = [cal.calibrate(x / 10) for x in range(11)]
    assert values == sorted(values)


def test_calibration_without_data_returns_input():
    cal = ConfidenceCalibrator()
    assert cal.calibrate(0.87) == 0.87
    assert "المجموعة الذهبية" in cal.report()["note"]
