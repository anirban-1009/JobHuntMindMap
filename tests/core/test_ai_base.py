from src.core.ai.base import LLMClient


class MockLLMClient(LLMClient):
    def __init__(self, response_text):
        self.response_text = response_text

    def generate(self, prompt, system_instruction=None, max_tokens=None):
        return self.response_text


def test_generate_json_object():
    text = '{"key": "value"}'
    client = MockLLMClient(text)
    assert client.generate_json("prompt") == {"key": "value"}


def test_generate_json_list():
    text = '[{"item": 1}, {"item": 2}]'
    client = MockLLMClient(text)
    assert client.generate_json("prompt") == [{"item": 1}, {"item": 2}]


def test_generate_json_markdown_object():
    text = 'Here is the result:\n```json\n{"key": "value"}\n```'
    client = MockLLMClient(text)
    assert client.generate_json("prompt") == {"key": "value"}


def test_generate_json_markdown_list():
    text = 'Here is the result:\n```json\n[{"item": 1}]\n```'
    client = MockLLMClient(text)
    assert client.generate_json("prompt") == [{"item": 1}]


def test_generate_json_fallback_object():
    text = 'Some noise before { "key": "value" } and some noise after'
    client = MockLLMClient(text)
    assert client.generate_json("prompt") == {"key": "value"}


def test_generate_json_fallback_list():
    text = 'Some noise before [ {"item": 1} ] and some noise after'
    client = MockLLMClient(text)
    assert client.generate_json("prompt") == [{"item": 1}]


def test_generate_json_invalid():
    text = "This is not JSON"
    client = MockLLMClient(text)
    assert client.generate_json("prompt") == {}


def test_generate_json_mixed_fallback():
    # Should prefer the larger structure or the first one that works
    # My implementation prefers object if it's larger or the only one
    text = 'Noise { "obj": 1 } Noise [ "list" ] Noise'
    client = MockLLMClient(text)
    result = client.generate_json("prompt")
    assert result == {"obj": 1} or result == ["list"]
