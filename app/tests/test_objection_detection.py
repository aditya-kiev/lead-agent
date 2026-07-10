from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.tools.objection_detection import detect_objection, OBJECTION_TYPES


@pytest.fixture
def mock_model():
    model = MagicMock()
    model.ainvoke = AsyncMock()
    return model


async def test_detect_pricing_objection(mock_model):
    mock_model.ainvoke.return_value.content = "pricing"
    result = await detect_objection("This is too expensive for us", mock_model)
    assert result.has_objection is True
    assert result.objection_type == "pricing"


async def test_detect_no_objection(mock_model):
    mock_model.ainvoke.return_value.content = "none"
    result = await detect_objection("This sounds great, tell me more!", mock_model)
    assert result.has_objection is False
    assert result.objection_type is None


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


async def test_detect_objection_calls_model_with_prompt(mock_model):
    mock_model.ainvoke.return_value.content = "timing"
    await detect_objection("Not the right time", mock_model)
    assert mock_model.ainvoke.call_count == 1
    messages = mock_model.ainvoke.call_args[0][0]
    sys_msg = [m for m in messages if m.type == "system"][0]
    assert "timing" in sys_msg.content
    assert "pricing" in sys_msg.content


async def test_detect_all_objection_types(mock_model):
    for ot in [t for t in OBJECTION_TYPES if t != "none"]:
        mock_model.ainvoke.return_value.content = ot
        result = await detect_objection("Some message", mock_model)
        assert result.has_objection is True
        assert result.objection_type == ot
