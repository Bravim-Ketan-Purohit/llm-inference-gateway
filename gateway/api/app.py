"""FastAPI application with all routes."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.api.schemas import (
    ChatCompletionRequest,
    ModelInfo,
    ModelListResponse,
)
from gateway.backends.ollama import OllamaBackend
from gateway.backends.openrouter import OpenRouterBackend
from gateway.backends.pool import BackendPool
from gateway.backends.vllm import VLLMBackend
from gateway.config import Settings, get_settings
from gateway.limits.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    settings = get_settings()

    # Initialize backends
    backends: list[Any] = []
    ollama = OllamaBackend(settings.ollama_base_url, settings.ollama_model)
    if ollama.is_available:
        backends.append(ollama)

    vllm = VLLMBackend(settings.vllm_base_url, settings.vllm_model)
    if vllm.is_available:
        backends.append(vllm)

    openrouter = OpenRouterBackend(
        settings.openrouter_base_url,
        settings.openrouter_api_key,
        settings.openrouter_model,
    )
    if openrouter.is_available:
        backends.append(openrouter)

    app.state.backend_pool = BackendPool(backends)
    app.state.rate_limiter = TokenBucketRateLimiter(capacity=100.0, refill_rate=10.0)
    app.state.settings = settings

    logger.info(
        "Gateway started: env=%s backends=%s",
        settings.gateway_env,
        [b.name for b in backends],
    )
    yield
    logger.info("Gateway shutting down")


app = FastAPI(
    title="LLM Inference Gateway",
    version="0.1.0",
    description="OpenAI-compatible gateway with semantic caching",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_tenant_id(request: Request) -> str:
    """Extract tenant ID from API key or header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return "anonymous"


def _validate_api_key(request: Request, settings: Settings) -> bool:
    """Validate the API key against configured keys."""
    if settings.gateway_env == "development" and not settings.api_keys.strip():
        return True
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        key = auth[7:]
        return key in settings.api_key_set
    return False


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models(request: Request) -> ModelListResponse:
    """List available models."""
    settings: Settings = request.app.state.settings
    models = [
        ModelInfo(id=settings.ollama_model, owned_by="ollama"),
    ]
    if settings.vllm_model:
        models.append(ModelInfo(id=settings.vllm_model, owned_by="vllm"))
    if settings.openrouter_model:
        models.append(ModelInfo(id=settings.openrouter_model, owned_by="openrouter"))
    return ModelListResponse(data=models)


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    body: ChatCompletionRequest,
) -> Response:
    """OpenAI-compatible chat completions endpoint."""
    settings: Settings = request.app.state.settings

    # Auth check
    if not _validate_api_key(request, settings):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Rate limiting
    tenant_id = _get_tenant_id(request)
    rate_limiter: TokenBucketRateLimiter = request.app.state.rate_limiter
    if not rate_limiter.allow(tenant_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    pool: BackendPool = request.app.state.backend_pool
    backend = pool.get_available_backend()
    if backend is None:
        raise HTTPException(status_code=503, detail="No available backends")

    # Streaming
    if body.stream:
        try:
            stream = backend.chat_stream(body)
            return StreamingResponse(
                stream,
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        except Exception as e:
            logger.error("Stream error: %s", e)
            raise HTTPException(status_code=502, detail=str(e)) from e

    # Non-streaming
    try:
        response = await pool.chat(body)
        return JSONResponse(content=response.model_dump())
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.get("/v1/backends/health")
async def backends_health(request: Request) -> dict[str, Any]:
    """Check health of all backends."""
    pool: BackendPool = request.app.state.backend_pool
    results = await pool.health_check_all()
    circuit_states = {
        name: cb.state.value for name, cb in pool.circuit_breakers.items()
    }
    return {"backends": results, "circuit_breakers": circuit_states}
