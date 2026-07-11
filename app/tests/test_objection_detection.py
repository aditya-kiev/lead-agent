from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.tools.objection_detection import detect_objection, OBJECTION_TYPES


@pytest.fixture
def mock_model():
    model = MagicMock()
    model.ainvoke = AsyncMock()
    return model


async def test_detect_pricing_objection_via_keyword(mock_model):
    """Pricing keywords should be caught by the pre-filter, no LLM call."""
    result = await detect_objection("This is too expensive for us", mock_model)
    assert result.has_objection is True
    assert result.objection_type == "pricing"
    assert result.source == "keyword"
    mock_model.ainvoke.assert_not_called()


async def test_detect_no_objection_via_safe_phrase(mock_model):
    """Safe messages should skip the LLM entirely."""
    result = await detect_objection("Hello, I'm interested in your services", mock_model)
    assert result.has_objection is False
    assert result.objection_type is None
    assert result.source == "safe"
    mock_model.ainvoke.assert_not_called()


async def test_detect_empty_message(mock_model):
    result = await detect_objection("", mock_model)
    assert result.has_objection is False
    assert result.objection_type is None
    mock_model.ainvoke.assert_not_called()


async def test_detect_trims_whitespace(mock_model):
    result = await detect_objection("   ", mock_model)
    assert result.has_objection is False
    assert result.objection_type is None
    mock_model.ainvoke.assert_not_called()


async def test_ambiguous_message_escalates_to_llm(mock_model):
    """Messages that aren't clearly safe or clearly objections go to the LLM."""
    mock_model.ainvoke.return_value.content = "timing"
    result = await detect_objection("I'm wondering about the implementation timeline", mock_model)
    assert result.source == "llm"
    assert mock_model.ainvoke.call_count == 1
    messages = mock_model.ainvoke.call_args[0][0]
    sys_msg = [m for m in messages if m.type == "system"][0]
    assert "timing" in sys_msg.content


async def test_llm_returns_no_objection(mock_model):
    """LLM returning 'none' should be treated as no objection."""
    mock_model.ainvoke.return_value.content = "none"
    result = await detect_objection("I'm wondering about the implementation timeline", mock_model)
    assert result.has_objection is False
    assert result.objection_type is None
    assert result.source == "llm"


async def test_llm_list_content_does_not_crash(mock_model):
    """Regression: Gemini sometimes returns AIMessage.content as a
    list[dict] (e.g. content=[{"type": "text", "text": "pricing"}])
    rather than a plain string. The function must handle this without
    raising AttributeError('list' object has no attribute 'strip')."""
    mock_model.ainvoke.return_value.content = [{"type": "text", "text": "pricing"}]
    result = await detect_objection("I'm wondering about the implementation timeline", mock_model)
    assert result.has_objection is True
    assert result.objection_type == "pricing"
    assert result.source == "llm"
