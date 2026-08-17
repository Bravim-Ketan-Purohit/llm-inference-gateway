# SPEC — LLM Inference Gateway with Semantic Caching & Speculative Decoding

**Authoritative technical specification.** `ROADMAP.md` gives the order; this gives the contents. Where
they disagree, this wins. If a requirement here looks wrong, say so and stop.

---

## 1. The claim

> Gateway between client apps and self-hosted models: Redis-backed semantic caching short-circuits repeat
> queries; speculative decoding via vLLM speeds generation. Cut token latency **[XX]%** and inference cost
> **[XX]%** in load benchmarks.

Resume stack string the build must match: *FastAPI, Redis, vLLM, AWS EC2, Terraform*
(`Bravim_Purohit_Backend_Engineer.tex:123`).

### Two mechanisms, two numbers, one hard constraint

**Two mechanisms.** Semantic caching and speculative decoding improve different things by different
routes. Caching eliminates work entirely (huge win on a hit, zero effect on a miss). Speculative decoding
makes each generated token cheaper in wall-clock terms (helps every miss, helps nothing on a hit). A single
blended number is unfalsifiable and an interviewer will ask which mechanism did what. So the benchmark is
an **ablation matrix**, not a before/after pair:

| Arm | Cache | Spec. decoding |
| --- | --- | --- |
| A baseline | off | off |
| B | **on** | off |
| C | off | **on** |
| D | on | on |

Every reported figure names its arms: "B vs A" for cache effect, "C vs A" for speculative decoding, "D vs
A" for the combined headline.

**One hard constraint: this laptop cannot measure arm C.** vLLM speculative decoding needs a CUDA GPU;
this is arm64 macOS with no NVIDIA device. There is no workaround, and estimating the number is not an
option. The resolution is already in the resume's own stack line — *AWS EC2, Terraform*:

> Terraform up a GPU instance (g5.xlarge or g6.xlarge), run the benchmark suite, pull the results,
> `terraform destroy`. A few hours at roughly $1/hr. The infrastructure claim and the latency claim need
> each other, which is convenient — one afternoon proves both.

Local development runs against **Ollama on Metal** (a real self-hosted model, OpenAI-compatible API) so
everything except arms C and D is fully testable here.

### "Token latency" must be defined

Ambiguous as written, and the three candidates behave differently:

- **TTFT** (time to first token) — cache hits crush this; speculative decoding barely moves it.
- **ITL** (inter-token latency) / tokens-per-second — what speculative decoding actually improves.
- **E2E** total request time.

Report all three per arm. Pick which one `[XX]%` refers to, and say which in the README and the resume
bullet. "Cut inter-token latency 34 %" is a real claim; "cut token latency 34 %" invites the reader to
assume whichever is most flattering, which is the kind of thing that unravels in an interview.

## 2. Non-goals

- Not a LiteLLM/OpenRouter clone. Provider breadth is not the point; the two mechanisms are.
- No fine-tuning, no model training, no custom kernels.
- No multi-tenant billing system. Per-key budgets and accounting, yes; invoicing, no.
- No Kubernetes. EC2 + Terraform, as the resume says.
- No prompt-injection defence or content moderation layer.

## 3. Architecture

```
 clients ──► gateway (FastAPI :7501)  OpenAI-compatible /v1/chat/completions
                 │
                 │ 1. auth + per-key budget check
                 │ 2. exact-match cache lookup   (SHA of canonical request)
                 │ 3. semantic cache lookup      (embed → Redis vector search)
                 │      hit  ⇒ stream cached response, log as HIT
                 │      miss ⇒ ↓
                 │ 4. router → backend pool, circuit breaker, retry
                 ▼
        ┌────────────────────────────────────────────┐
        │  backends                                  │
        │   • Ollama (Metal)      local dev :7504    │
        │   • vLLM + draft model  EC2 GPU, arms C/D  │
        │   • replay backend      deterministic tests│
        └────────────────────────────────────────────┘
                 │ stream tokens back, count usage
                 ▼
        write-back to cache (if cacheable) ──► Redis Stack :7502
                 │
                 └──► metrics :7505 / Grafana :7506 / ops console :7500
```

## 4. Semantic cache — where this project earns or loses credibility

A semantic cache is a correctness hazard wearing a performance costume. The failure mode is returning the
answer to a *different* question because two embeddings were close. Cache-hit rate hides it completely;
only a false-hit measurement exposes it.

### Layered lookup

1. **Exact match.** `sha256` of the canonical request. Zero false positives, near-zero cost. Always first.
2. **Semantic match.** Embed the normalised user turn, vector search in Redis (RediSearch HNSW, cosine),
   accept if `similarity >= τ`.

### Cache key scoping — get this wrong and it returns wrong answers

The key namespace **must** include: model id, temperature, top_p, max_tokens, stop sequences, system-prompt
hash, tool/function schema hash, response-format, and **tenant/API-key scope**.

Two of those are not merely correctness issues:

- **Temperature.** Caching a `temperature=0.9` response and replaying it makes the API silently
  deterministic. Default policy: only cache `temperature <= 0.2`; above that, opt-in per request.
- **Tenant scope.** A cache shared across API keys is a cross-user data leak — user A's prompt returns
  user B's cached completion. Default to per-key scoping, with an explicit opt-in shared namespace for
  genuinely public content. Write this in the README; it's the kind of design judgement worth showing.

Never semantically cache: streaming tool calls, responses whose prompt contains a nonce/timestamp,
requests with `n > 1`, or anything the caller marks `no-store`.

### False-hit measurement — the headline safety metric

Build a labelled evaluation set:

- **Paraphrase pairs** (should hit): same question, different wording — ~150 pairs.
- **Near-miss pairs** (must NOT hit): high lexical/embedding similarity, different correct answer. These
  are the interesting ones and must be constructed deliberately:
  - "What is the capital of Australia?" / "What is the capital of Austria?"
  - "How do I *enable* two-factor auth?" / "How do I *disable* two-factor auth?"
  - "Convert 100 USD to EUR" / "Convert 100 EUR to USD"
  - "List employees hired *before* 2020" / "…*after* 2020"
  - negation, unit swaps, off-by-one dates, plural vs singular entity
  Target ~150 pairs. Negation and argument-order swaps are near-invisible to embeddings, which is exactly
  why this set is the project's best artefact.

Sweep `τ` from 0.80 to 0.99 and publish the curve: hit rate and **false-hit rate** on the same axes.
Choose the operating threshold from that curve and state it in the README with its measured false-hit rate.
"92 % hit rate" alongside an unstated 6 % false-hit rate is a broken cache; "78 % hit rate at 0.4 %
false-hit, τ = 0.94" is an engineering result.

Optional, and a strong addition if time allows: a cheap **verification pass** on borderline hits (a small
model or cross-encoder judging "does this cached answer answer this question?"), reported as its own arm.

## 5. Speculative decoding

vLLM with a draft/target pair (e.g. a small draft model against a larger target), or prompt-lookup /
n-gram speculation for a no-extra-weights variant. Requirements:

- Record **draft acceptance rate** per workload. This is the mechanism's efficiency and it varies wildly by
  task — high on templated or repetitive output, low on open-ended prose. A low acceptance rate can make
  generation *slower* than baseline; if a workload shows that, report it. A benchmark that only shows the
  favourable workload is a marketing chart.
- Verify **output equivalence**: speculative decoding with greedy sampling should be distribution-lossless.
  Run a fixed prompt set with `temperature=0` in arms A and C and diff the outputs. Any divergence is a bug
  or a configuration error — investigate before reporting a speedup.
- Record: draft model, target model, speculative token count, acceptance rate, GPU type, vLLM version,
  batch size, and concurrency for every run.
- Measure at **multiple concurrency levels**. Speculative decoding trades extra compute for latency; its
  benefit shrinks as batching saturates the GPU. A single-stream number is the best case and must be
  labelled as such.

## 6. Gateway requirements

- **OpenAI-compatible** `/v1/chat/completions` (streaming + non-streaming), `/v1/embeddings`,
  `/v1/models`. Compatibility means existing clients work unchanged, which is the point of a gateway.
- Streaming via SSE, with cache hits streamed too (replayed at a configurable rate) so hits and misses are
  indistinguishable to clients.
- Per-key auth, rate limiting (token bucket, Redis-backed), per-key token budgets with 429 on exhaustion.
- Backend pool with health checks, circuit breaker (open on consecutive failures, half-open probe), retry
  with jittered backoff on idempotent failures only.
- Usage accounting per request: prompt tokens, completion tokens, cached bool, backend, latency
  breakdown (auth, cache lookup, queue, TTFT, generation), and computed cost.
- `/metrics` Prometheus: latency histograms by arm and route, cache hit/miss/false-hit-suspected counters,
  acceptance-rate gauge, backend health, queue depth.
- Structured request logs with an opt-in redaction mode; never log a full prompt when redaction is on.

## 7. Module layout

```
gateway/
  api/         FastAPI routes, OpenAI-compatible schemas, SSE streaming
  cache/       exact + semantic layers, key canonicalisation, scoping, write-back, eviction
  embed/       embedding providers for cache keys
  backends/    ollama, vllm, replay adapters; pool, health, circuit breaker
  routing/     model selection, fallbacks
  limits/      token bucket, per-key budgets
  usage/       token counting, cost model
  observability/  metrics, structured logs, tracing
bench/         load generator, ablation runner, results/*.json
eval/          paraphrase + near-miss sets, threshold sweep, equivalence check
infra/         Terraform: GPU EC2, SG, IAM, S3 results bucket, auto-destroy guardrails
web/           ops console (Next.js)
```

## 8. Ops console (`web/`)

Next.js + TypeScript + Tailwind + shadcn/ui + Recharts.

1. **Live.** Request stream with cache HIT/MISS badges, per-request latency breakdown bars.
2. **Latency.** TTFT / ITL / E2E histograms, switchable by arm, with p50/p95/p99 markers.
3. **Cache.** The threshold sweep chart — hit rate and false-hit rate vs τ, operating point marked. Plus
   the near-miss set with pass/fail per pair. This is the screen to show an interviewer.
4. **Cost.** Measured tokens × configurable prices, arms side by side, savings attributed per mechanism.
5. **Playground.** Send a prompt, pick arm, see whether it hit and why (nearest neighbour + similarity).

## 9. Benchmark protocol

`bench/` load generator: `--arm A|B|C|D`, `--concurrency`, `--duration`, `--workload`, `--repeat-ratio`.

Workloads (they produce different answers, so run all three):

- **`repeat-heavy`** — realistic FAQ traffic with a Zipf-distributed repeat pattern. Where caching wins.
- **`unique`** — no repeats. Isolates speculative decoding; cache contributes nothing by construction.
- **`mixed`** — a stated repeat ratio, and the honest headline workload.

**The repeat ratio is the whole ballgame for the cost number.** A cache in front of 90 %-repeat traffic
"cuts cost 85 %" and means nothing, because the workload was chosen to produce that. State the repeat ratio
next to every cost figure, and pick a defensible one (production FAQ/support traffic is commonly cited
around 30–40 %; if you use a specific figure, cite where it came from or label it as an assumption).

Record per run: arm, workload + repeat ratio, concurrency, duration, model ids, GPU type or "Metal/Ollama",
vLLM version, τ, embedding model, prompt/completion token totals, and the full latency percentile set.

Cost = measured tokens × price, with the price source recorded. For self-hosted, cost is instance $/hr ÷
tokens/hr — so throughput and instance type must be in the same result file. Include cache infrastructure
cost (Redis + embedding calls) in the cached arms; a cache isn't free and subtracting its cost is what makes
the number trustworthy.

## 10. Terraform requirements

`infra/` must be genuinely runnable, not decorative — it is a resume claim on its own:

- GPU instance (g5.xlarge / g6.xlarge), security group locked to the operator's IP, IAM instance profile,
  S3 bucket for benchmark results, user-data that installs vLLM and pulls pinned models.
- `terraform output` gives the endpoint the bench runner targets.
- **Cost guardrails, non-negotiable:** a mandatory `auto_destroy_after_hours` variable wired to a shutdown
  timer, plus a `make bench-cloud` target that runs `apply` → benchmark → fetch results → `destroy` and
  destroys even on failure (`trap`). A forgotten g5 instance is roughly $700/month; the guardrail is part
  of the deliverable.
- `terraform fmt` and `validate` in CI. `plan` requires credentials, so keep it out of CI.

## 11. Milestone acceptance criteria

- **M1 Gateway core.** OpenAI-compatible streaming passthrough to Ollama, auth, rate limits, usage
  accounting, `/metrics`. Replay backend for deterministic tests.
- **M2 Exact cache.** Canonical key with full scoping from §4; write-back; TTL/eviction; per-key scoping
  test proving no cross-key leakage.
- **M3 Semantic cache.** Redis vector search, τ configurable, paraphrase + near-miss sets built, **sweep
  published with false-hit rate**. Operating τ chosen from data.
- **M4 Ablation locally.** Arms A, B, D-without-specdec measured on Ollama across all three workloads;
  results committed.
- **M5 Cloud + speculative decoding.** Terraform applies; vLLM with draft model; arms C and D measured;
  acceptance rate recorded; output-equivalence check passes; results in S3 and committed to `bench/results/`;
  instance destroyed. **README Benchmarks table filled.**
- **M6 Presentable.** Ops console with the threshold sweep and cost attribution; README diagram accurate;
  CI green.

## 12. Honest-claims register

| Claim | Status | Backed by |
| --- | --- | --- |
| gateway between clients and self-hosted models | ☐ | OpenAI-compatible API in front of Ollama and vLLM |
| Redis-backed semantic caching | ☐ | layered cache, scoped keys, sweep published |
| cache is safe, not just fast | ☐ | false-hit rate at operating τ, near-miss set results |
| speculative decoding via vLLM | ☐ | arm C on real GPU, acceptance rate recorded |
| speculative decoding is lossless | ☐ | greedy output diff A vs C |
| cut token latency `[XX]%` | ☐ | named metric (TTFT/ITL/E2E), named arms, committed result |
| cut inference cost `[XX]%` | ☐ | measured tokens × prices, repeat ratio stated, cache cost included |
| Terraform / EC2 | ☐ | `apply` → bench → `destroy` executed, with auto-destroy guardrail |

Any unchecked row ⇒ `Bravim_Purohit_Backend_Engineer.tex:126` stays commented and both `[XX]`s stay
bracketed.

---

## 13. Extended stack (added 2026-08-17)

### 13.1 TensorRT-LLM as a second inference backend

vLLM stays primary (it's the resume commitment). TensorRT-LLM lands behind the same `Backend` protocol, and
the point is the comparison — these two are the real production choice in 2026, and having measured both is
worth more than having an opinion about both.

Measure on the **same GPU, same session, same model**, or the comparison is worthless:

| Axis | Why it matters |
| --- | --- |
| TTFT / ITL / tokens-per-sec at concurrency 1, 8, 32 | TensorRT-LLM's advantage is usually at low concurrency; vLLM's paged attention wins as batching saturates |
| engine build time | TensorRT-LLM compiles ahead of time — minutes to hours. That's a real deployment cost vLLM doesn't have |
| speculative decoding support + acceptance rate | both support it; the implementations differ |
| memory footprint at equal throughput | |
| output equivalence vs greedy baseline | a faster backend that changes outputs is not a faster backend |

Write it up in `docs/BACKENDS.md`. Be explicit that the engine-build step makes TensorRT-LLM worse for
iteration and better for a pinned production model — that trade is the interesting part.

### 13.2 pgvector as a second semantic-cache store

Redis Stack stays primary. pgvector lands behind a `CacheStore` protocol, and the comparison is genuinely
informative because the two make opposite trades:

- **Redis Stack** — in-memory HNSW, sub-millisecond lookup, cache is volatile by nature (which is fine).
- **pgvector** — durable, transactional, joins against usage/accounting rows in the same query, and it
  collapses two services into one. Slower per lookup, and IVFFlat vs HNSW index choice matters.

Report: p95 cache-lookup latency, recall against a brute-force ground truth at the operating τ, memory/disk
footprint, and cold-start behaviour after a restart. That last one is the honest argument for pgvector — a
Redis cache restart means a fully cold cache and a cost spike, and being able to quantify that is a real
operational insight.

Run the §4 threshold sweep against **both** stores. If the false-hit rate differs between them at the same
τ, the index configuration differs — find out which, and say so.

### 13.3 DynamoDB for usage and accounting

Usage records are high-write, append-only, time-ordered, queried by key and range, and never updated. That
is the shape DynamoDB is actually for, so the usage log moves there while Postgres/pgvector keeps the
relational and vector work:

- PK `api_key`, SK `timestamp#request_id`. GSI on `model#timestamp` for per-model rollups.
- On-demand billing; TTL attribute for automatic expiry of raw records after N days.
- Batch writes, and **never a synchronous write on the request path** — buffer and flush async, because
  billing telemetry must not add latency to inference.

The README should note Cassandra as the self-hosted equivalent and why DynamoDB was chosen here (already on
AWS, no cluster to operate, on-demand pricing suits bursty benchmark traffic).

### 13.4 llama.cpp, continuous batching, CUDA profiling

- **llama.cpp** — a second local backend beside Ollama (which wraps it). Direct use gives control over GGUF
  quantisation level, so you can measure the quantisation/quality trade on Metal. Useful because it's the
  one axis you *can* measure without renting a GPU.
- **Continuous batching** becomes an explicit measured axis, not a word in a README: sweep concurrency 1 →
  64 and plot throughput and per-request latency together. The crossover — where added concurrency stops
  buying throughput and only adds latency — is the number an infrastructure interviewer wants, and it's
  also where speculative decoding's benefit disappears. Same chart, two findings.
- **CUDA memory profiling** during the GPU session: `nvidia-smi` sampling, `torch.profiler` or `nsys` for a
  representative run. Report KV-cache size vs batch size vs context length, and the point where memory
  forces a batch-size cap. This is what makes "I served models" concrete.

### 13.5 OpenRouter fallback tier

The routing layer gains a final fallback: if every self-hosted backend is unhealthy or the circuit breaker
is open, route to OpenRouter. Real gateways need an escape hatch, and it makes the circuit breaker
demonstrable — kill the vLLM backend mid-load-test and watch traffic shift with no dropped requests.

Requirements: fallback is explicit per-key policy, never silent; the response records which backend served
it; cost accounting distinguishes self-hosted from API spend, since the cost claim depends on that split.

### 13.6 OpenTelemetry

Spans: `auth`, `cache_lookup_exact`, `cache_lookup_semantic`, `embed`, `route`, `backend_call`, `stream`,
`cache_writeback`. Attributes: arm, cache hit/miss, similarity score, τ, backend, model, tokens, cost,
acceptance rate.

This makes the §1 latency breakdown a **measured attribution** rather than an assertion — you can point at a
trace and show that a cache hit spends 4 ms in embedding and 1 ms in lookup, while a miss spends 380 ms in
the backend. The ops console's latency-breakdown bars read from these spans.

Tracing must be **off during benchmark runs**, and its overhead measured once and recorded. Instrumenting a
latency benchmark with an exporter enabled is a way to measure your exporter.

## 14. Additional milestones

- **M7 Second inference backend.** TensorRT-LLM behind the `Backend` protocol; both engines measured on one
  GPU session across concurrency 1/8/32; engine build time recorded; output equivalence verified;
  `docs/BACKENDS.md` written.
- **M8 Cache-store comparison.** pgvector behind `CacheStore`; §4 threshold sweep run against both stores;
  latency, recall, footprint, and cold-start reported. DynamoDB usage log live with async flush.
- **M9 Batching + profiling.** Concurrency sweep 1→64 with the throughput/latency crossover identified;
  CUDA memory profile committed; llama.cpp quantisation trade measured on Metal.
- **M10 Resilience + observability.** OpenRouter fallback with a demonstrated failover under load; OTel end
  to end with measured overhead documented.

### Honest-claims additions

| Claim | Status | Backed by |
| --- | --- | --- |
| serving stack is a decision, not a default | ☐ | vLLM vs TensorRT-LLM on one GPU, `docs/BACKENDS.md` |
| cache store is a decision | ☐ | Redis vs pgvector: latency, recall, cold start |
| continuous batching understood | ☐ | concurrency sweep with the crossover point identified |
| GPU memory behaviour understood | ☐ | KV-cache vs batch vs context profile |
| graceful degradation | ☐ | backend killed mid-load-test, zero dropped requests |
