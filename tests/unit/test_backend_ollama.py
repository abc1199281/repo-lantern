
import pytest
from unittest.mock import MagicMock, patch
from lantern_cli.backends.ollama import OllamaBackend
from lantern_cli.backends.base import AnalysisResult

@pytest.fixture
def mock_requests_post():
    with patch("requests.post") as mock_post:
        yield mock_post

def test_ollama_backend_init():
    backend = OllamaBackend(model="llama3", base_url="http://localhost:11434")
    assert backend.model == "llama3"
    assert backend.base_url == "http://localhost:11434"

def test_analyze_batch_success(mock_requests_post):
    # Mock successful response from Ollama
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "Summary: This is a summary.\n\nKey Insights:\n- Insight 1\n- Insight 2\n\nQuestions:\n- Question 1"
    }
    mock_requests_post.return_value = mock_response

    backend = OllamaBackend()
    result = backend.analyze_batch(files=["test.py"], context="", prompt="Analyze this")

    assert isinstance(result, AnalysisResult)
    assert "This is a summary" in result.summary
    assert "Insight 1" in result.key_insights
    assert "Question 1" in result.questions
    assert result.raw_output == "Summary: This is a summary.\n\nKey Insights:\n- Insight 1\n- Insight 2\n\nQuestions:\n- Question 1"

def test_analyze_batch_failure(mock_requests_post):
    # Mock failure response
    mock_requests_post.side_effect = Exception("Connection error")

    backend = OllamaBackend()
    result = backend.analyze_batch(files=["test.py"], context="", prompt="Analyze this")

    assert "Error calling Ollama" in result.summary
    assert "Connection error" in result.raw_output
