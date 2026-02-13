
import pytest
from pathlib import Path
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

def test_analyze_batch_success(mock_requests_post, tmp_path):
    # Create a real file so _call_api can read its contents
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello():\n    return 'world'", encoding="utf-8")

    # Mock successful response from Ollama
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "Summary: This is a summary.\n\nKey Insights:\n- Insight 1\n- Insight 2\n\nQuestions:\n- Question 1"
    }
    mock_requests_post.return_value = mock_response

    backend = OllamaBackend()
    result = backend.analyze_batch(files=[str(test_file)], context="", prompt="Analyze this")

    assert isinstance(result, AnalysisResult)
    assert "This is a summary" in result.summary
    assert "Insight 1" in result.key_insights
    assert "Question 1" in result.questions

    # Verify file CONTENTS were included in the prompt, not just the filename
    call_args = mock_requests_post.call_args
    sent_prompt = call_args[1]["json"]["prompt"] if "json" in call_args[1] else call_args[0][1]["prompt"]
    assert "def hello():" in sent_prompt
    assert "return 'world'" in sent_prompt

def test_analyze_batch_failure(mock_requests_post):
    # Mock failure response
    mock_requests_post.side_effect = Exception("Connection error")

    backend = OllamaBackend()
    result = backend.analyze_batch(files=["test.py"], context="", prompt="Analyze this")

    assert "Error calling Ollama" in result.summary
    assert "Connection error" in result.raw_output

def test_analyze_file_delegates_to_batch(mock_requests_post, tmp_path):
    """Test that analyze_file (inherited from base) calls analyze_batch with single file."""
    test_file = tmp_path / "single.py"
    test_file.write_text("x = 1", encoding="utf-8")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "Summary: Single file analysis.\n\nKey Insights:\n- Simple assignment"
    }
    mock_requests_post.return_value = mock_response

    backend = OllamaBackend()
    result = backend.analyze_file(file=str(test_file), context="", prompt="Analyze")

    assert isinstance(result, AnalysisResult)
    assert "Single file analysis" in result.summary

