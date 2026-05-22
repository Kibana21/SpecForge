"""Skill-engine array→object coercion + PageIndex headingless-text fallback."""
from app.services.corpus_index.pageindex_provider import _fallback_tree
from app.services.skills.skill_engine import _coerce_to_schema


def test_coerce_bare_array_into_single_array_prop():
    schema = {"type": "object", "required": ["facts"],
              "properties": {"facts": {"type": "array"}}}
    parsed = [{"kind": "limitation", "text": "x", "confidence": "high"}]
    out = _coerce_to_schema(parsed, schema)
    assert out == {"facts": parsed}


def test_coerce_leaves_object_untouched():
    schema = {"type": "object", "properties": {"selections": {"type": "array"}}}
    parsed = {"selections": [{"doc": "D0", "node_id": "0001"}]}
    assert _coerce_to_schema(parsed, schema) is parsed


def test_coerce_skips_multi_array_schema():
    # requirement_extractor-style: multiple array props, none uniquely targetable
    schema = {"type": "object", "properties": {
        "functional_requirements": {"type": "array"},
        "non_functional_requirements": {"type": "array"},
    }}
    parsed = [{"id": "x"}]
    assert _coerce_to_schema(parsed, schema) == parsed  # unchanged


def test_fallback_tree_builds_page_nodes():
    page_texts = {"1": "first page about pricing", "2": "second page about limits"}
    tree = _fallback_tree(page_texts, "doc.txt")
    assert len(tree["nodes"]) == 2
    assert tree["nodes"][0]["node_id"] == "0001"
    assert tree["nodes"][0]["start_index"] == 1
    assert "pricing" in tree["nodes"][0]["summary"]
