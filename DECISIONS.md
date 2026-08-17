# Decision log

## D1 — Gateway software: LiteLLM, not OmniRoute (2026-08-17)

PLAN.md §9 pre-authorized this fallback: *"If a required feature (per-key USD quota)
doesn't exist or is broken in the pinned version, STOP and propose the fallback:
LiteLLM proxy, which has mature per-key budgets, keeping everything else in this
spec identical."*

We audited OmniRoute v3.8.49/3.8.50 source (commit `fb25855`) before Phase 1. The
per-key USD quota requirement is not met, and several deployment assumptions in the
spec don't hold:

**Budget/quota gaps (the disqualifier):**
- No lifetime/total per-key USD cap exists — only daily/weekly/monthly windows.
  The $35/team event-total cap is not expressible. Daily windows reset at a
  hardcoded 03:00 UTC (UTC-3 calendar day); weekly is rolling-7-day or snaps to
  provider resets.
- No per-route/per-lane USD cap at all. The closest thing (per-key-per-model cap)
  has no HTTP API, no UI (raw SQLite inserts only), and its window is hardcoded
  to *hourly* — so "$20 frontier for the event" cannot be enforced.
- Quota enforcement in the "quota pools" system is fail-open by design: a DB
  hiccup means unlimited spend.
- Models with no pricing row silently cost $0 and consume no budget.
- Budget-exceeded responses are inconsistent (400 vs 429 depending on subsystem).
- Its own quota guide documents an API (`quotaLimit`/`quotaCheck`) that does not
  exist in the codebase.
- Moonshot and Meta models ship with no pricing entries, so per-key USD budgets
  would silently never trip for exactly the lanes we're metering (must PATCH
  pricing per model by hand).
- Moonshot native context caching is not implemented at all, and Moonshot/Meta/
  Groq/Cerebras/NVIDIA are absent from the cache-control passthrough allowlists —
  PLAN.md §Phase 2 calls cache economics "the whole cost model."

**Deployment gaps that also mattered:**
- Provider API keys cannot be provisioned via env vars/config (removed in v3.8.0);
  they must be entered through the dashboard into encrypted SQLite. No
  reproducible/declarative deploys.
- SQLite single-writer storage: cannot scale to the 2 Fly machines the spec
  requires for event weekend.
- `REQUIRE_API_KEY` defaults to false (open /v1), and with no `INITIAL_PASSWORD`
  the onboarding page is publicly reachable on first boot.

**Why LiteLLM matches the spec directly:**
- `/key/generate` with `max_budget` = true cumulative USD cap per key ($35).
- `model_max_budget` = per-key per-model-group USD cap ($20 on `ohack-frontier`).
- Postgres-backed keys/spend → survives restarts, works across 2+ replicas.
- Declarative `config.yaml` (providers, model groups, fallbacks, pricing) that
  lives in this repo; secrets via env.
- OpenAI `/v1/chat/completions` + Anthropic `/v1/messages` endpoints, so Claude
  Code, Cursor, Cline, Continue, and raw SDKs all work.
- Custom per-model pricing (`input_cost_per_token`/`output_cost_per_token`) so
  budget math is correct for Meta/Moonshot models.

Everything else in PLAN.md (lanes, budgets, Fly hosting, domain, scripts, docs
page, runbook) is unchanged.

## D1a — Two keys per team (2026-08-17)

Tested live: LiteLLM's `model_max_budget` (per-key per-model USD cap) is
**enterprise-license-only** — the OSS proxy returns
`"You must have an enterprise license to set model_max_budget"`. PLAN §Phase 3
pre-approved the fallback for exactly this: a second key per team.

- `team-NN` — max_budget **$15** lifetime, models `ohack`, `ohack-mid`, `ohack-free`
- `team-NN-frontier` — max_budget **$20** lifetime, model `ohack-frontier` only

$15 + $20 = the $35/team cap from PLAN §3, enforced exactly (no shared-pot
approximation). $15 on the cheap lanes is generous: at Muse Contributor prices
it buys ~75M+ input tokens, and PLAN §7 estimated all-team default-lane spend
at only $30–60 total. Both keys print on one card (Phase 4 already planned for
this layout).

## D1b — Region: lax, not phx (2026-08-17)

Fly.io no longer offers a Phoenix region. `lax` (Los Angeles) is the closest to
ASU Tempe (~10 ms). Postgres and the app both live there.

## D2 — Verified provider facts (2026-08-17)

| Lane | Provider / model | Base URL | Pricing (per M tokens) |
|---|---|---|---|
| 1 default | Meta Model API `muse-spark-1.2-contributor` | `https://api.meta.ai/v1` (OpenAI-compatible) | $0.10 in / $0.20 out; 60 RPM limit on contributor tier |
| 2 frontier | Moonshot `kimi-k3` | `https://api.moonshot.ai/v1` (OpenAI-compatible) | $3 in ($0.30 cache-hit) / $15 out |
| 3 mid | Moonshot `kimi-k2.7-code` | `https://api.moonshot.ai/v1` | $0.95 in ($0.19 cache-hit) / $4 out |
| 4 overflow | Groq / Cerebras / NVIDIA NIM free tiers | OpenAI-compatible | $0 — pending ToS check (PLAN §5) |

Note: contributor tier is rate-limited to 60 requests/min (vs 3,000 standard) —
the fallback chain to `kimi-k2.7-code` is what absorbs event-scale burst, exactly
as the spec's Lane 3 intends.
