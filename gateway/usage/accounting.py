"""Usage accounting with DynamoDB backend."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class UsageAccountant:
    """Tracks token usage per tenant in DynamoDB.

    Records are keyed by (tenant_id, timestamp) for efficient
    time-range queries. Writes are async and non-blocking.
    """

    def __init__(
        self,
        table_name: str = "llm-gateway-usage",
        endpoint_url: str = "http://localhost:7509",
        region: str = "us-east-1",
        aws_access_key_id: str = "local",
        aws_secret_access_key: str = "local",
    ) -> None:
        self._table_name = table_name
        self._endpoint_url = endpoint_url
        self._region = region
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._client: Any = None
        self._table: Any = None

    def _get_client(self) -> Any:
        """Lazy-initialize DynamoDB resource."""
        if self._client is None:
            import boto3

            self._client = boto3.resource(
                "dynamodb",
                endpoint_url=self._endpoint_url,
                region_name=self._region,
                aws_access_key_id=self._aws_access_key_id,
                aws_secret_access_key=self._aws_secret_access_key,
            )
            self._table = self._client.Table(self._table_name)
        return self._table

    async def record_usage(
        self,
        *,
        tenant_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached: bool = False,
        backend: str = "",
        latency_ms: float = 0.0,
    ) -> None:
        """Record a usage event to DynamoDB.

        Non-blocking: logs and continues on failure.
        """
        try:
            table = self._get_client()
            now = datetime.now(UTC)
            item = {
                "tenant_id": tenant_id,
                "timestamp": now.isoformat(),
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "cached": cached,
                "backend": backend,
                "latency_ms": int(latency_ms),
                "epoch": int(time.time()),
            }
            table.put_item(Item=item)
        except Exception as e:
            logger.warning("Failed to record usage: %s", e)

    async def get_usage(
        self, tenant_id: str, start_time: str | None = None, end_time: str | None = None
    ) -> list[dict[str, Any]]:
        """Query usage records for a tenant."""
        try:
            table = self._get_client()
            kwargs: dict[str, Any] = {
                "KeyConditionExpression": "tenant_id = :tid",
                "ExpressionAttributeValues": {":tid": tenant_id},
            }

            if start_time and end_time:
                kwargs["KeyConditionExpression"] += (
                    " AND #ts BETWEEN :start AND :end"
                )
                kwargs["ExpressionAttributeNames"] = {"#ts": "timestamp"}
                kwargs["ExpressionAttributeValues"][":start"] = start_time
                kwargs["ExpressionAttributeValues"][":end"] = end_time

            response = table.query(**kwargs)
            return response.get("Items", [])
        except Exception as e:
            logger.warning("Failed to query usage: %s", e)
            return []

    async def ensure_table(self) -> None:
        """Create the DynamoDB table if it doesn't exist."""
        try:
            self._get_client()
            # Table already accessible if _get_client succeeds
        except Exception:
            import boto3

            client = boto3.client(
                "dynamodb",
                endpoint_url=self._endpoint_url,
                region_name=self._region,
                aws_access_key_id=self._aws_access_key_id,
                aws_secret_access_key=self._aws_secret_access_key,
            )
            try:
                client.create_table(
                    TableName=self._table_name,
                    KeySchema=[
                        {"AttributeName": "tenant_id", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    AttributeDefinitions=[
                        {"AttributeName": "tenant_id", "AttributeType": "S"},
                        {"AttributeName": "timestamp", "AttributeType": "S"},
                    ],
                    BillingMode="PAY_PER_REQUEST",
                )
                logger.info("Created DynamoDB table: %s", self._table_name)
            except client.exceptions.ResourceInUseException:
                pass
