# CLAUDE.md — LLM Inference Gateway

Operating instructions for a Claude Code session in this repo. Read `SPEC.md` before writing code —
especially §1 (two mechanisms, and why arm C can't run on this machine) and §4 (the semantic cache is a
correctness hazard). `ROADMAP.md` has the order.

## What this is

An OpenAI-compatible gateway in front of self-hosted models, with a layered exact + semantic Redis cache
and vLLM speculative decoding, measured as a four-arm ablation. It exists to prove one resume bullet,
quoted in `SPEC.md` §1.

## Hard rules

1. **Stay inside this directory.** Independent git repo; the parent is deliberately not a repo and seven
   sibling projects sit beside it. Never read, write, or `git` above `llm-inference-gateway/`.
2. **Never estimate a latency or cost number.** Especially not the speculative-decoding one. It requires a
   CUDA GPU this machine does not have; the number comes from a real EC2 run or it stays bracketed.
   Modelling it, extrapolating from published benchmarks, or citing vLLM's own numbers as if they were
   yours are all off the table.
3. **Measure arms separately.** A, B, C, D per `SPEC.md` §1. Never report a combined number without also
   reporting the per-mechanism attribution.
4. **A cache hit rate without a false-hit rate is not a result.** Never publish one alone.
5. **Cache keys carry full scope** — model, all sampling params, system-prompt hash, tool-schema hash, and
   tenant/API-key. Never share a cache namespace across API keys by default; that's a data leak, not an
   optimisation.
6. **Never touch the resume.** Different repo. Don't edit the `.tex`, don't uncomment the GitHub link.
7. **Cloud spend is the user's decision.** Never run `terraform apply` on a GPU instance without asking
   first, and never leave one running. `make bench-cloud` must destroy on failure paths too.
8. **Keys in `.env` only**, `.env.example` committed empty. Never log a key; never log a full prompt when
   redaction mode is on.

## Environment (this machine: arm64 macOS, 11 cores, 18 GB, no CUDA)

`python3` on the PATH is **3.8.10 and unusable here**. Use `uv` (0.12 installed):

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
```

**Do not `pip install vllm` locally.** It targets CUDA; on arm64 macOS it either fails to build or gives a
CPU path whose timings are meaningless for this benchmark. Keep vLLM in the EC2 image and behind a backend
adapter interface, so local runs use Ollama and nothing imports vLLM at module scope.

Local model backend — Ollama on Metal, a genuinely self-hosted model with an OpenAI-compatible API:

```bash
brew install ollama && ollama serve            # then point OLLAMA_BASE_URL at :7504 or 11434
ollama pull <a small instruct model>
```

Services:

```bash
docker compose -f docker-compose.dev.yml up -d      # redis-stack (vector search), prometheus, grafana
```

Redis **Stack** specifically — plain Redis has no vector index. Terraform 1.14.4 is installed.

## Ports — this project owns 7500–7599

Up to eight sibling projects may run at once. Never bind outside this block; never bind :3000, :6379,
:8000, :9090, or :3001.

| Port | Use |
| --- | --- |
| 7500 | `web/` Next.js ops console (`next dev -p 7500`) |
| 7501 | gateway API (FastAPI) |
| 7502 | Redis Stack (→ 6379) |
| 7503 | RedisInsight (→ 8001) |
| 7504 | model backend (Ollama proxy / vLLM tunnel) |
| 7505 | Prometheus (→ 9090) |
| 7506 | Grafana (→ 3000) |

## Commands

```bash
uvicorn gateway.api.app:app --reload --port 7501
python -m bench.run --arm A --workload mixed --concurrency 16 --duration 10m
python -m eval.sweep --tau 0.80:0.99:0.01        # hit rate + false-hit rate curve
python -m eval.equivalence --arms A,C            # greedy output diff, arm C only on GPU
make bench-cloud                                  # terraform apply → bench → fetch → destroy
terraform -chdir=infra fmt -check && terraform -chdir=infra validate
pytest -q
```

## Conventions

- Python 3.12, full type hints, `mypy --strict` on `gateway/cache`, `gateway/backends`, `gateway/usage`.
  Ruff for lint + format.
- Backends live behind one `Backend` protocol (`stream`, `complete`, `health`). Adding vLLM must not touch
  gateway logic, and no module may import a CUDA-only package at import time.
- Pydantic v2 for the OpenAI-compatible schemas — match the real field names, including `usage` and
  `finish_reason`, so off-the-shelf clients work unchanged.
- Cache key canonicalisation is one pure function with exhaustive unit tests. Every field in `SPEC.md` §4
  gets a test proving it changes the key. This is where silent wrong-answer bugs live.
- Every bench result writes a manifest: arm, workload, repeat ratio, concurrency, model ids, GPU/Metal,
  vLLM version, τ, embedding model, token totals, percentiles.
- Metrics before optimisation. If a latency claim has no histogram behind it, it isn't measured.
- Tests: pytest. Use the replay backend for deterministic gateway tests; use real Redis Stack for cache
  tests (no `fakeredis` — it has no vector index and would hide the actual behaviour).
- Commits: imperative, ≤ 72 chars, scoped — `cache: scope semantic keys by api key namespace`.
- Git identity is already set for this repo (`bravimpurohit1305@gmail.com`). Leave it.

## Definition of done, and when to stop

Milestones per `SPEC.md` §11. CI green on push; `terraform fmt`/`validate` run in CI, `plan` does not.

**Stop and ask the user** when:

- It's time to spend money on GPU EC2 (M5). Give the estimated cost and duration first.
- The false-hit rate is unacceptable at every threshold that yields a useful hit rate — that's a real
  finding and possibly a resume-wording change, not something to tune away.
- Speculative decoding shows no improvement or a regression on a workload. Report it; don't drop the
  workload.
- The cost figure depends on a repeat ratio you had to choose. Present the options and let the user pick a
  defensible one.
- A `SPEC.md` requirement looks wrong, or you want a dependency it doesn't name.

Report honestly, per arm and per metric: "arm B vs A on mixed/35 % repeat: TTFT p95 −71 %, cost −31 %;
arm C vs A: ITL −28 % at concurrency 1, −9 % at concurrency 16, acceptance 0.63" is the deliverable. A
single blended percentage is not.
