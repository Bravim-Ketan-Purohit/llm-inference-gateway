"""Application configuration via environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Gateway configuration loaded from environment variables."""

    # Server
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 7501
    gateway_env: str = "development"
    gateway_log_level: str = "info"
    gateway_redact_prompts: bool = False

    # Auth
    api_keys: str = "dev-key-1,dev-key-2"

    # Redis
    redis_url: str = "redis://localhost:7502"

    # Backends
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"
    vllm_base_url: str = ""
    vllm_model: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct"

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Cache
    cache_semantic_threshold: float = 0.92
    cache_ttl_seconds: int = 3600
    cache_max_temperature: float = 0.2
    cache_replay_rate_tokens_per_sec: int = 200

    # PGVector
    pgvector_url: str = "postgresql://postgres:postgres@localhost:7507/gateway"

    # DynamoDB
    dynamodb_table: str = "llm-gateway-usage"
    dynamodb_endpoint_url: str = "http://localhost:7509"
    dynamodb_region: str = "us-east-1"
    aws_access_key_id: str = "local"
    aws_secret_access_key: str = "local"

    # Observability
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://localhost:7511"
    otel_service_name: str = "llm-inference-gateway"

    @property
    def api_key_set(self) -> set[str]:
        """Split API_KEYS into a set."""
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def get_settings() -> Settings:
    """Singleton settings loader."""
    return Settings()
