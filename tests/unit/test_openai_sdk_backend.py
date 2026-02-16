"""Tests for OpenAI SDK backend."""

from unittest.mock import MagicMock, patch

import pytest

from lantern_cli.config.models import BackendConfig, LanternConfig
from lantern_cli.llm.backends.openai_sdk_backend import (
    OpenAISDKBackend,
    _extract_json,
)


# ---------------------------------------------------------------------------
# _extract_json helper
# ---------------------------------------------------------------------------


class TestExtractJson:

    def test_plain_json(self) -> None:
        assert _extract_json('{"a": 1}') == '{"a": 1}'

    def test_fenced_json(self) -> None:
        result = _extract_json('```json\n{"a": 1}\n```')
        assert '"a": 1' in result

    def test_json_in_prose(self) -> None:
        result = _extract_json('Here is the result:\n{"key": "value"}\nDone.')
        assert '"key"' in result

    def test_no_json_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not extract"):
            _extract_json("no json here at all")


# ---------------------------------------------------------------------------
# OpenAISDKBackend construction
# ---------------------------------------------------------------------------


class TestOpenAISDKBackendInit:

    @patch("lantern_cli.llm.backends.openai_sdk_backend.OpenAI")
    def test_basic_init(self, mock_openai_cls: MagicMock) -> None:
        backend = OpenAISDKBackend(api_key="sk-test", model="gpt-4o")
        assert backend.model_name == "gpt-4o"
        mock_openai_cls.assert_called_once_with(api_key="sk-test")

    @patch("lantern_cli.llm.backends.openai_sdk_backend.OpenAI")
    def test_init_with_base_url(self, mock_openai_cls: MagicMock) -> None:
        backend = OpenAISDKBackend(
            api_key="sk-test",
            model="gpt-4o-mini",
            base_url="https://custom.api/v1",
        )
        assert backend.model_name == "gpt-4o-mini"
        mock_openai_cls.assert_called_once_with(
            api_key="sk-test",
            base_url="https://custom.api/v1",
        )

    @patch("lantern_cli.llm.backends.openai_sdk_backend.OpenAI")
    def test_client_property(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        backend = OpenAISDKBackend(api_key="sk-test")
        assert backend.client is mock_client


# ---------------------------------------------------------------------------
# OpenAISDKBackend.invoke
# ---------------------------------------------------------------------------


class TestOpenAISDKBackendInvoke:

    @patch("lantern_cli.llm.backends.openai_sdk_backend.OpenAI")
    def test_invoke_returns_content(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Simulate a Chat Completions response
        mock_message = MagicMock()
        mock_message.content = "Hello, world!"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client.chat.completions.create.return_value = mock_response

        backend = OpenAISDKBackend(api_key="sk-test", model="gpt-4o-mini")
        result = backend.invoke("Say hi")

        assert result.content == "Hello, world!"
        assert result.usage_metadata == {"input_tokens": 10, "output_tokens": 5}

        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say hi"}],
            temperature=0,
        )

    @patch("lantern_cli.llm.backends.openai_sdk_backend.OpenAI")
    def test_invoke_none_content_returns_empty_string(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = None
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        mock_client.chat.completions.create.return_value = mock_response

        backend = OpenAISDKBackend(api_key="sk-test")
        result = backend.invoke("test")

        assert result.content == ""
        assert result.usage_metadata is None

    @patch("lantern_cli.llm.backends.openai_sdk_backend.OpenAI")
    def test_invoke_strips_whitespace(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = "  hello  \n"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        mock_client.chat.completions.create.return_value = mock_response

        backend = OpenAISDKBackend(api_key="sk-test")
        result = backend.invoke("test")

        assert result.content == "hello"


# ---------------------------------------------------------------------------
# OpenAISDKBackend.batch_invoke_structured
# ---------------------------------------------------------------------------


class TestOpenAISDKBackendStructured:

    @patch("lantern_cli.llm.backends.openai_sdk_backend.OpenAI")
    def test_structured_with_native_json_schema(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = '{"summary": "test summary", "key_insights": ["a"], "language": "en"}'
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        backend = OpenAISDKBackend(api_key="sk-test")
        schema = {
            "name": "test_schema",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
            },
        }
        prompts = {"system": "You are a helpful assistant.", "user": "Analyze: {file_content}"}
        items = [{"file_content": "def foo(): pass", "language": "en"}]

        results = backend.batch_invoke_structured(items, schema, prompts)

        assert len(results) == 1
        assert results[0]["summary"] == "test summary"

    @patch("lantern_cli.llm.backends.openai_sdk_backend.OpenAI")
    def test_structured_fallback_chain(self, mock_openai_cls: MagicMock) -> None:
        """When native json_schema fails, falls back to json_object, then plain prompt."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # First call (native json_schema) → raises error
        # Second call (json_object) → raises error
        # Third call (plain prompt) → returns valid JSON
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Unsupported response_format")
            mock_msg = MagicMock()
            mock_msg.content = '{"summary": "fallback"}'
            mock_choice = MagicMock()
            mock_choice.message = mock_msg
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            return mock_resp

        mock_client.chat.completions.create.side_effect = side_effect

        backend = OpenAISDKBackend(api_key="sk-test")
        schema = {"name": "test", "parameters": {"type": "object"}}
        prompts = {"system": "sys", "user": "{file_content}"}

        results = backend.batch_invoke_structured(
            [{"file_content": "code"}], schema, prompts
        )

        assert results[0]["summary"] == "fallback"
        assert call_count == 3


# ---------------------------------------------------------------------------
# Factory integration: create_backend with openai_sdk type
# ---------------------------------------------------------------------------


class TestFactoryOpenAISDK:

    @patch("lantern_cli.llm.factory.os.environ", {"TEST_KEY": "sk-test-123"})
    @patch("lantern_cli.llm.backends.openai_sdk_backend.OpenAI")
    def test_create_openai_sdk_backend(self, mock_openai_cls: MagicMock) -> None:
        from lantern_cli.llm.factory import create_backend

        config = LanternConfig(
            backend=BackendConfig(
                type="openai_sdk",
                openai_sdk_model="gpt-4o",
                openai_sdk_api_key_env="TEST_KEY",
            )
        )
        backend = create_backend(config)
        assert isinstance(backend, OpenAISDKBackend)
        assert backend.model_name == "gpt-4o"

    @patch("lantern_cli.llm.factory.os.environ", {})
    def test_create_openai_sdk_missing_key_raises(self) -> None:
        from lantern_cli.llm.factory import create_backend

        config = LanternConfig(
            backend=BackendConfig(
                type="openai_sdk",
                openai_sdk_api_key_env="MISSING_KEY",
            )
        )
        with pytest.raises(RuntimeError, match="API key not found"):
            create_backend(config)

    @patch("lantern_cli.llm.factory.os.environ", {"OPENAI_API_KEY": "sk-default"})
    @patch("lantern_cli.llm.backends.openai_sdk_backend.OpenAI")
    def test_create_openai_sdk_with_base_url(self, mock_openai_cls: MagicMock) -> None:
        from lantern_cli.llm.factory import create_backend

        config = LanternConfig(
            backend=BackendConfig(
                type="openai_sdk",
                openai_sdk_model="openai/gpt-4o",
                openai_sdk_base_url="https://openrouter.ai/api/v1",
            )
        )
        backend = create_backend(config)
        assert isinstance(backend, OpenAISDKBackend)
        assert backend.model_name == "openai/gpt-4o"

        # Verify OpenAI was initialized with base_url
        mock_openai_cls.assert_called_once_with(
            api_key="sk-default",
            base_url="https://openrouter.ai/api/v1",
        )

    @patch("lantern_cli.llm.factory.os.environ", {"OPENAI_API_KEY": "sk-default"})
    @patch("lantern_cli.llm.backends.openai_sdk_backend.OpenAI")
    def test_create_openai_sdk_defaults(self, mock_openai_cls: MagicMock) -> None:
        from lantern_cli.llm.factory import create_backend

        config = LanternConfig(
            backend=BackendConfig(type="openai_sdk")
        )
        backend = create_backend(config)
        assert isinstance(backend, OpenAISDKBackend)
        assert backend.model_name == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Config model: openai_sdk type validation
# ---------------------------------------------------------------------------


class TestConfigOpenAISDK:

    def test_openai_sdk_type_valid(self) -> None:
        config = BackendConfig(type="openai_sdk")
        assert config.type == "openai_sdk"

    def test_openai_sdk_defaults(self) -> None:
        config = BackendConfig(type="openai_sdk")
        assert config.openai_sdk_model == "gpt-4o-mini"
        assert config.openai_sdk_base_url is None
        assert config.openai_sdk_api_key_env == "OPENAI_API_KEY"

    def test_openai_sdk_custom_values(self) -> None:
        config = BackendConfig(
            type="openai_sdk",
            openai_sdk_model="gpt-4o",
            openai_sdk_base_url="https://custom.api/v1",
            openai_sdk_api_key_env="MY_API_KEY",
        )
        assert config.openai_sdk_model == "gpt-4o"
        assert config.openai_sdk_base_url == "https://custom.api/v1"
        assert config.openai_sdk_api_key_env == "MY_API_KEY"
