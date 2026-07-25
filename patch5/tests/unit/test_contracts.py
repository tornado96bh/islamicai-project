import sys; sys.path.insert(0,'.')
from uuid import uuid4
import pytest
from packages.schemas import *

def test_bbox_conversion():
    b = BoundingBox.from_xyxy(10, 20, 110, 70)
    assert (b.x, b.y, b.width, b.height) == (10, 20, 100, 50)
    assert b.to_xyxy() == (10, 20, 110, 70)

def test_extra_fields_rejected():
    with pytest.raises(Exception):
        BoundingBox(x=0, y=0, width=1, height=1, oops=1)

def test_span_validates_order():
    with pytest.raises(Exception):
        TextSpan(element_id=uuid4(), start_raw=10, end_raw=5, text_raw="x")

def test_element_requires_raw_only():
    e = PageElement(id=uuid4(), page_id=uuid4(), element_order=0, text_raw="قال")
    assert e.element_type is ElementType.UNKNOWN
    assert e.text_normalized is None
    assert e.quality is TextQuality.CLEAN

def test_final_answer_requires_source():
    with pytest.raises(Exception):
        FinalAnswer(question="س", answer_text="ج")

def test_final_answer_can_decline_without_source():
    a = FinalAnswer(question="س", answer_text="لا أستطيع الجزم",
                    declined=True, decline_reason="أدلة غير كافية")
    assert a.declined and not a.sources

def test_source_citation_format():
    s = Source(book_id=uuid4(), book_title="وسائل الشيعة",
               volume_number=1, page_number=311)
    assert s.citation() == "وسائل الشيعة ج1 ص311"

def test_all_element_types_present():
    for t in ["matn","sanad","hashiya","footnote","heading","citation"]:
        assert ElementType(t)

def test_schema_version_on_every_contract():
    assert PageElement(id=uuid4(), page_id=uuid4(), element_order=0,
                       text_raw="x").schema_version == SCHEMA_VERSION

def test_confidence_bounds_enforced():
    with pytest.raises(Exception):
        Narrator(id=uuid4(), canonical_name="زرارة", confidence=1.5)
