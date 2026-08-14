"""OpenTelemetry tracing setup."""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

logger = logging.getLogger(__name__)


def setup_tracing(
    service_name: str = "llm-inference-gateway",
    otlp_endpoint: str = "http://localhost:7511",
    enabled: bool = False,
) -> trace.Tracer:
    """Configure OpenTelemetry tracing with OTLP exporter.

    Returns a tracer instance for creating spans.
    """
    if not enabled:
        # Return a no-op tracer
        return trace.get_tracer(service_name)

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        logger.info("OTLP tracing enabled: endpoint=%s", otlp_endpoint)
    except Exception as e:
        logger.warning("Failed to configure OTLP exporter: %s", e)

    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)


def get_tracer(name: str = "llm-inference-gateway") -> trace.Tracer:
    """Get a tracer instance."""
    return trace.get_tracer(name)
