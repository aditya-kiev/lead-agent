import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["GEMINI_API_KEY"] = "test-fake-key"
os.environ["LANGSMITH_API_KEY"] = "ls-test-fake"


@pytest.fixture(autouse=True)
def mock_openai():
    mock_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "This is a mock response from the AI assistant."
    mock_instance.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.agent.graph.ChatGoogleGenerativeAI", return_value=mock_instance):
        yield


@pytest.fixture(autouse=True)
def mock_db_session():
    with patch("app.database.session.async_session_factory"):
        yield
