# Roadmap — LLM Inference Gateway

The measurement harness comes early. Both resume numbers are *reductions*, which means an unoptimized
baseline has to exist and be measured before any optimization lands.

## M1 — Pass-through gateway

- [ ] FastAPI app with an OpenAI-compatible `/v1/chat/completions` surface
- [ ] Streaming (SSE) proxied correctly — token-by-token, not buffered
- [ ] API key auth + per-key rate limiting
- [ ] One vLLM backend, single instance
- [ ] Structured request logging: tokens in/out, latency, backend

## M2 — Benchmark harness, before optimizing

- [ ] Load generator with configurable concurrency and a realistic prompt-length distribution
- [ ] Measure **TTFT** and **inter-token latency** separately, p50/p95/p99
- [ ] Token accounting and cost model (GPU-hours × price ÷ tokens, utilization stated)
- [ ] **Record the unoptimized baseline.** Both resume numbers are measured against this

## M3 — Semantic cache

- [ ] Embed incoming prompts; vector search in Redis
- [ ] Similarity threshold as an explicit, configurable policy
- [ ] Bypass rules: high temperature, per-user private context, explicit no-cache header
- [ ] Cache key includes **model identity + version** so a model swap invalidates
- [ ] TTL and eviction policy
- [ ] **False-hit measurement**: a labeled set of near-miss prompt pairs that must *not* share an answer
- [ ] Threshold sweep: plot hit rate vs. false-hit rate, choose a point and justify it
- [ ] Re-benchmark: latency and cost delta from caching **alone**

## M4 — Router

- [ ] Multiple backends with load balancing
- [ ] Health checks and automatic failover
- [ ] Retry with backoff; circuit breaker on a persistently failing backend
- [ ] Test: kill a backend mid-stream and verify graceful behavior

## M5 — Speculative decoding

- [ ] Configure vLLM speculative decoding (draft model or n-gram)
- [ ] Measure **draft-token acceptance rate** — the number that explains the speedup
- [ ] Re-benchmark: latency delta from speculative decoding **alone**
- [ ] Check whether it *hurts* on any workload shape, and report that if so

## M6 — Infrastructure

- [ ] Terraform: EC2 GPU instances, security groups, Redis, IAM roles
- [ ] `terraform fmt -check` and `validate` green in CI
- [ ] Deployment runbook

## M7 — Fill in the numbers

- [ ] Full comparison run: baseline → +cache → +spec → both
- [ ] **Fill the Benchmarks table** with the mechanisms decomposed
- [ ] Publish cache hit rate, false-hit rate, and acceptance rate alongside the headline numbers

## M8 — Presentable

- [ ] README architecture diagram matches the code
- [ ] CI green
- [ ] Flip repo public, then uncomment `Bravim_Purohit_Backend_Engineer.tex:126`

## Gate before the resume link goes live

Both `[XX]%` placeholders measured and **attributed to the right mechanism** · cache hit rate and
false-hit rate published · acceptance rate published · cost arithmetic shown, not asserted.
