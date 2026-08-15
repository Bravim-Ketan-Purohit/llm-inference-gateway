"""Benchmark load generator for gateway performance testing.

Supports multiple workload patterns and concurrency levels.
Arms:
  A = Gateway with cache (local)
  B = Direct backend (no cache)
  C = vLLM on GPU (remote)
  D = vLLM + speculative decoding (remote)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

GATEWAY_URL = "http://localhost:7501"

# Workload templates
PROMPTS_REPEAT = [
    "What is Python?",
    "Explain recursion",
    "How does a hash table work?",
    "What is Docker?",
    "Explain REST APIs",
]

PROMPTS_UNIQUE = [
    f"Explain concept number {i} in computer science" for i in range(100)
]


@dataclass
class BenchResult:
    """Results from a single benchmark run."""

    arm: str
    workload: str
    concurrency: int
    duration_sec: float
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    cache_hits: int = 0

    @property
    def p50_ms(self) -> float:
        if not self.latencies_ms:
            return 0
        s = sorted(self.latencies_ms)
        return s[len(s) // 2]

    @property
    def p95_ms(self) -> float:
        if not self.latencies_ms:
            return 0
        s = sorted(self.latencies_ms)
        return s[int(len(s) * 0.95)]

    @property
    def p99_ms(self) -> float:
        if not self.latencies_ms:
            return 0
        s = sorted(self.latencies_ms)
        return s[int(len(s) * 0.99)]

    @property
    def rps(self) -> float:
        if self.duration_sec == 0:
            return 0
        return self.successful_requests / self.duration_sec


def get_workload_prompts(workload: str) -> list[str]:
    """Get prompts for the given workload type."""
    if workload == "repeat-heavy":
        return PROMPTS_REPEAT
    elif workload == "unique":
        return PROMPTS_UNIQUE
    elif workload == "mixed":
        return PROMPTS_REPEAT + PROMPTS_UNIQUE[:20]
    else:
        return PROMPTS_REPEAT


async def send_request(
    client: httpx.AsyncClient,
    prompt: str,
    model: str = "llama3.2:1b",
    api_key: str = "dev-key-1",
) -> tuple[float, bool, bool]:
    """Send a single chat completion request.

    Returns (latency_ms, success, was_cache_hit).
    """
    start = time.perf_counter()
    try:
        response = await client.post(
            f"{GATEWAY_URL}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        if response.status_code == 200:
            data = response.json()
            is_cache_hit = data.get("system_fingerprint") == "cache-hit"
            return elapsed_ms, True, is_cache_hit
        else:
            return elapsed_ms, False, False
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return elapsed_ms, False, False


async def run_benchmark(
    arm: str,
    workload: str,
    concurrency: int,
    duration: float,
    remote: bool = False,
) -> BenchResult:
    """Run a benchmark with the given parameters."""
    prompts = get_workload_prompts(workload)
    result = BenchResult(
        arm=arm, workload=workload, concurrency=concurrency, duration_sec=duration
    )

    print(f"[Bench] arm={arm} workload={workload} concurrency={concurrency} duration={duration}s")

    async with httpx.AsyncClient(timeout=120.0) as client:
        end_time = time.time() + duration
        semaphore = asyncio.Semaphore(concurrency)

        async def worker():
            while time.time() < end_time:
                prompt = random.choice(prompts)
                async with semaphore:
                    latency, success, cache_hit = await send_request(client, prompt)
                    result.total_requests += 1
                    if success:
                        result.successful_requests += 1
                        result.latencies_ms.append(latency)
                        if cache_hit:
                            result.cache_hits += 1
                    else:
                        result.failed_requests += 1

        tasks = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await asyncio.gather(*tasks)

    print(f"[Results] requests={result.total_requests} success={result.successful_requests} "
          f"rps={result.rps:.1f} p50={result.p50_ms:.1f}ms p95={result.p95_ms:.1f}ms "
          f"cache_hits={result.cache_hits}")

    return result


def save_results(result: BenchResult) -> None:
    """Save benchmark results to JSON."""
    out_dir = Path("bench/results")
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{result.arm}_{result.workload}_{int(time.time())}.json"
    data = {
        "arm": result.arm,
        "workload": result.workload,
        "concurrency": result.concurrency,
        "duration_sec": result.duration_sec,
        "total_requests": result.total_requests,
        "successful_requests": result.successful_requests,
        "failed_requests": result.failed_requests,
        "cache_hits": result.cache_hits,
        "p50_ms": result.p50_ms,
        "p95_ms": result.p95_ms,
        "p99_ms": result.p99_ms,
        "rps": result.rps,
    }

    (out_dir / filename).write_text(json.dumps(data, indent=2))
    print(f"Results saved: {out_dir / filename}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Gateway benchmark runner")
    parser.add_argument("--arm", required=True, choices=["A", "B", "C", "D"])
    parser.add_argument(
        "--workload", required=True, choices=["repeat-heavy", "unique", "mixed"]
    )
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--remote", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(
        run_benchmark(
            arm=args.arm,
            workload=args.workload,
            concurrency=args.concurrency,
            duration=args.duration,
            remote=args.remote,
        )
    )
    save_results(result)


if __name__ == "__main__":
    main()
