# Study notes — LLM Inference Gateway

Reference material, carried over from `projects-ref.md`.

## Reference

### [`BerriAI/litellm`](https://github.com/BerriAI/litellm)

An incredibly successful open-source FastAPI proxy that standardizes inputs and outputs across 100+
different LLM providers.

**What to study:** `litellm/router.py`. Specifically:

1. **Load balancing** — how they fall back to an Azure endpoint when OpenAI rate-limits them
2. **Redis caching** — how duplicate questions avoid costing API money

Read how they track per-deployment health and cooldowns. The pattern of "this backend just 429'd, take
it out of rotation for N seconds" is simple and it is most of what a production router does.

Also study their **streaming** implementation. Proxying SSE while transforming the payload between
provider formats is fiddly, and getting it wrong shows up as buffered output — the single most obvious
tell of an amateur gateway.

Their caching is largely exact-match/normalized-key. The semantic layer is the thing this repo adds on
top, and it's where the real design work is.

## Also worth reading

- **vLLM docs** — continuous batching and PagedAttention (why throughput is high in the first place),
  and the speculative-decoding configuration options.
- **Speculative decoding** — the original paper, or vLLM's write-up. The mechanism is simple: a small
  draft model proposes k tokens, the large model verifies them in one forward pass. Speedup is entirely
  a function of acceptance rate, which is why that metric must be reported.
- **GPTCache** — prior art for semantic caching. Look at how they structure the eviction and similarity
  evaluation, and at the failure modes they document.

## Questions to answer before coding

1. Where exactly does the latency go in a single request — queueing, prefill, decode, network? Which of
   those does each optimization actually touch?
2. Two prompts with cosine similarity 0.97 — is that a cache hit? What's the cost of being wrong, and
   who pays it?
3. What is the false-hit rate of the semantic cache, and how is it measured rather than assumed?
4. Why does a cache key need the model version in it?
5. Why can speculative decoding make generation *slower*? At what acceptance rate does it break even?
6. When a backend returns 429, what does the router do — and how does it avoid stampeding the next one?

## Trap to avoid

Reporting a single blended "latency down [XX]%" figure. The cache and speculative decoding improve
different things for different reasons, and blending them makes the claim unfalsifiable. Decompose the
measurement — it's more work and a much stronger result.

## Deliberate divergences from the reference

| Area | litellm does | This repo does | Why |
| --- | --- | --- | --- |
| | | | |
