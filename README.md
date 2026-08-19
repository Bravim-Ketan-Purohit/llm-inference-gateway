# LLM Inference Gateway — Semantic Caching & Speculative Decoding

Gateway between client apps and self-hosted models: **Redis-backed semantic caching** short-circuits
repeat queries, and **speculative decoding via vLLM** speeds generation.

**Stack:** FastAPI · Redis · vLLM · AWS EC2 · Terraform
**Resume target:** `Bravim_Purohit_Backend_Engineer.tex` → Projects & Publications
**Role:** Backend Engineer

---

## The claim this repo must prove

> Gateway between client apps and self-hosted models: Redis-backed semantic caching short-circuits
> repeat queries; speculative decoding via vLLM speeds generation. Cut token latency **[XX]%** and
> inference cost **[XX]%** in load benchmarks.

Two independent mechanisms, two independent numbers. Measure them **separately** — caching and
speculative decoding improve latency for completely different reasons, and a combined figure hides
which one is doing the work. An interviewer will ask you to decompose it.

## Benchmarks this repo owes the resume

| Metric | Resume placeholder | No cache, no spec | + semantic cache | + spec decoding | Method |
| --- | --- | --- | --- | --- | --- |
| Token latency | `[XX]%` reduction | — | — | — | TBD |
| Inference cost | `[XX]%` reduction | — | — | — | TBD |

Report properly, or the numbers mean nothing:

- **Latency:** separate **TTFT** (time to first token) from **inter-token latency**. Report p50/p95/p99,
  never means alone. A cache hit is a different distribution, not a faster point on the same one.
- **Cache hit rate is the honest denominator.** A 90% latency cut at a 5% hit rate is a 4.5% real-world
  improvement. Report both, and state the workload's query-repetition profile — that profile is what
  makes the cache number legitimate or misleading.
- **Semantic cache false-hit rate.** This is the metric everyone skips and the one that matters most:
  how often does the cache return a semantically-similar-but-wrong answer? Measure it, publish it, and
  document the similarity threshold you chose and why.
- **Speculative decoding:** report the **acceptance rate** of draft tokens. Speedup follows directly
  from it, and it varies enormously by workload — a low acceptance rate can make it *slower*.
- **Cost:** show the arithmetic. GPU-hours × instance price ÷ tokens served, with the assumed
  utilization stated.

**Do not uncomment** the GitHub link at `Bravim_Purohit_Backend_Engineer.tex:126` until this is filled
and the repo is public.

## Architecture

```
 clients (OpenAI-compatible requests)
    │
    ▼
 ┌────────────────── FastAPI gateway ──────────────────┐
 │                                                     │
 │  auth ─► rate limit ─► embed prompt                 │
 │                            │                        │
 │                            ▼                        │
 │                    ┌───────────────┐                │
 │                    │ semantic cache│  Redis         │
 │                    │ vector lookup │  + vectors     │
 │                    └───────┬───────┘                │
 │                  HIT ──────┴────── MISS             │
 │                   │                 │               │
 │                   ▼                 ▼               │
 │              return       ┌──────────────────┐      │
 │                           │ router:          │      │
 │                           │ load balance,    │      │
 │                           │ fallback, retry  │      │
 │                           └────────┬─────────┘      │
 └────────────────────────────────────┼────────────────┘
                                      ▼
                      ┌───────────────────────────────┐
                      │ vLLM backends (EC2 GPU)       │
                      │ continuous batching           │
                      │ speculative decoding          │
                      └───────────────────────────────┘
```

## The hard part: semantic cache correctness

Exact-match caching is trivially safe. Semantic caching is a **correctness/latency tradeoff** and needs
to be treated as one:

- Two prompts embedding closely can still require different answers ("what's the capital of Georgia?"
  — the state or the country?).
- The similarity threshold is a tunable with a real false-hit cost. Sweep it, plot hit rate against
  false-hit rate, and pick a point deliberately.
- Some requests must **never** be cache-served — anything with a nondeterminism requirement, high
  temperature, or per-user private context. Make bypass explicit.
- Cache invalidation: what happens when the backing model version changes? Key the cache on model
  identity, or you'll serve answers from a model you no longer run.

## Getting started

```bash
python -m venv .venv && source .venv/bin/activate   # needs Python 3.11+
pip install -r requirements.txt
cp .env.example .env
docker run -p 6379:6379 redis/redis-stack:latest    # needs vector search
pytest -q
uvicorn gateway.main:app --reload
```

Terraform for the EC2 GPU backends lives in `infra/`. `terraform fmt` and `validate` run in CI;
apply is manual and deliberate.

## Layout

```
gateway/       FastAPI app, auth, rate limiting, OpenAI-compatible surface
cache/         embedding, vector lookup, threshold policy, bypass rules
router/        load balancing, fallback, retry, circuit breaking
backends/      vLLM client, speculative decoding config
infra/         Terraform: EC2 GPU, security groups, Redis
bench/         load generator, latency + cost measurement
docs/STUDY.md  notes from BerriAI/litellm
```

## Documents

| File | What it's for |
| --- | --- |
| [SPEC.md](SPEC.md) | **Authoritative** technical specification — what to build, the data model, the measurement protocol, and the honest-claims register |
| [ROADMAP.md](ROADMAP.md) | Build order, milestone by milestone |
| [CLAUDE.md](CLAUDE.md) | Operating rules for a coding session here: environment, ports, conventions, when to stop and ask |
| [docs/STUDY.md](docs/STUDY.md) | What to read in the reference implementations before writing code |

Where `SPEC.md` and any other document disagree, `SPEC.md` wins.

## Status

Implemented, with a published negative result. The gateway, semantic cache, embedding and backend
adapters, rate limits, routing, and circuit breaker are all built. The committed similarity sweep
([`eval/results/sweep_redis.json`](eval/results/sweep_redis.json)) found that across the whole threshold
range, adversarial near-miss query pairs sit *closer* in embedding space than genuine paraphrases do — so no
single τ makes this cache both useful and safe (τ=0.86 gives a 47.5% hit rate against a 45% false-hit rate).
That is a real finding about semantic caching, and it is the most interesting thing in this repo. Latency and
cost reductions remain unmeasured: speculative decoding needs a GPU host. This repo reserves ports **7500–7599**; up to eight sibling
projects may run at the same time, so nothing here binds outside that block.
