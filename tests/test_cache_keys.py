"""Tests for canonical_cache_key proving each scoping field changes the key.

21 tests covering: model, temperature, top_p, max_tokens, stop sequences,
system prompt hash, tool schema hash, response format, tenant_id, content,
and edge cases.
"""


from gateway.cache.keys import canonical_cache_key

BASE_MESSAGES = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is Python?"},
]


def _base_key(**overrides):
    """Generate a key with base parameters and optional overrides."""
    kwargs = {
        "model": "llama3.2:1b",
        "messages": BASE_MESSAGES,
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 100,
        "stop": None,
        "tools": None,
        "response_format": None,
        "tenant_id": "tenant-1",
    }
    kwargs.update(overrides)
    return canonical_cache_key(**kwargs)


class TestModelScope:
    """Model name affects cache key."""

    def test_different_model_different_key(self):
        k1 = _base_key(model="llama3.2:1b")
        k2 = _base_key(model="llama3.2:3b")
        assert k1 != k2

    def test_same_model_same_key(self):
        k1 = _base_key(model="llama3.2:1b")
        k2 = _base_key(model="llama3.2:1b")
        assert k1 == k2


class TestTemperatureScope:
    """Temperature affects cache key."""

    def test_different_temperature_different_key(self):
        k1 = _base_key(temperature=0.0)
        k2 = _base_key(temperature=0.7)
        assert k1 != k2

    def test_none_vs_zero_temperature(self):
        k1 = _base_key(temperature=None)
        k2 = _base_key(temperature=0.0)
        assert k1 != k2


class TestTopPScope:
    """top_p affects cache key."""

    def test_different_top_p_different_key(self):
        k1 = _base_key(top_p=1.0)
        k2 = _base_key(top_p=0.9)
        assert k1 != k2


class TestMaxTokensScope:
    """max_tokens affects cache key."""

    def test_different_max_tokens_different_key(self):
        k1 = _base_key(max_tokens=100)
        k2 = _base_key(max_tokens=500)
        assert k1 != k2

    def test_none_vs_value_max_tokens(self):
        k1 = _base_key(max_tokens=None)
        k2 = _base_key(max_tokens=100)
        assert k1 != k2


class TestStopScope:
    """Stop sequences affect cache key."""

    def test_different_stop_different_key(self):
        k1 = _base_key(stop=None)
        k2 = _base_key(stop=["\\n"])
        assert k1 != k2

    def test_string_vs_list_stop(self):
        k1 = _base_key(stop="\\n")
        k2 = _base_key(stop=["\\n"])
        # Should be the same since a single string is normalized to a list
        assert k1 == k2

    def test_different_stop_sequences_order_invariant(self):
        k1 = _base_key(stop=["a", "b"])
        k2 = _base_key(stop=["b", "a"])
        # Sorted, so order shouldn't matter
        assert k1 == k2


class TestSystemPromptScope:
    """System prompt hash affects cache key."""

    def test_different_system_prompt_different_key(self):
        msgs1 = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        msgs2 = [
            {"role": "system", "content": "You are a pirate."},
            {"role": "user", "content": "Hello"},
        ]
        k1 = _base_key(messages=msgs1)
        k2 = _base_key(messages=msgs2)
        assert k1 != k2

    def test_no_system_prompt_different_from_empty(self):
        msgs_with = [
            {"role": "system", "content": ""},
            {"role": "user", "content": "Hello"},
        ]
        msgs_without = [
            {"role": "user", "content": "Hello"},
        ]
        k1 = _base_key(messages=msgs_with)
        k2 = _base_key(messages=msgs_without)
        assert k1 != k2


class TestToolSchemaScope:
    """Tool schemas affect cache key."""

    def test_different_tools_different_key(self):
        tools1 = [{"type": "function", "function": {"name": "get_weather"}}]
        tools2 = [{"type": "function", "function": {"name": "get_time"}}]
        k1 = _base_key(tools=tools1)
        k2 = _base_key(tools=tools2)
        assert k1 != k2

    def test_no_tools_vs_tools(self):
        tools = [{"type": "function", "function": {"name": "get_weather"}}]
        k1 = _base_key(tools=None)
        k2 = _base_key(tools=tools)
        assert k1 != k2


class TestResponseFormatScope:
    """Response format affects cache key."""

    def test_different_format_different_key(self):
        fmt1 = {"type": "text"}
        fmt2 = {"type": "json_object"}
        k1 = _base_key(response_format=fmt1)
        k2 = _base_key(response_format=fmt2)
        assert k1 != k2


class TestTenantScope:
    """Tenant ID affects cache key."""

    def test_different_tenant_different_key(self):
        k1 = _base_key(tenant_id="tenant-1")
        k2 = _base_key(tenant_id="tenant-2")
        assert k1 != k2

    def test_none_tenant_uses_default(self):
        k1 = _base_key(tenant_id=None)
        k2 = _base_key(tenant_id="default")
        # None → "default", so these should be equal
        assert k1 == k2


class TestContentScope:
    """Message content affects cache key."""

    def test_different_content_different_key(self):
        msgs1 = [{"role": "user", "content": "What is Python?"}]
        msgs2 = [{"role": "user", "content": "What is Java?"}]
        k1 = _base_key(messages=msgs1)
        k2 = _base_key(messages=msgs2)
        assert k1 != k2


class TestDeterminism:
    """Keys are deterministic for identical inputs."""

    def test_same_inputs_same_key(self):
        k1 = _base_key()
        k2 = _base_key()
        assert k1 == k2

    def test_key_is_hex_sha256(self):
        k = _base_key()
        assert len(k) == 64
        assert all(c in "0123456789abcdef" for c in k)
