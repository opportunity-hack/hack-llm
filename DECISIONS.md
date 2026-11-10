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

Note: contributor tier is rate-limited (100 RPM + 3M TPM as of Sep 2026; was 60
RPM in Aug) — the fallback chain to `kimi-k2.7-code` is what absorbs event-scale
burst, exactly as the spec's Lane 3 intends.

## D3 — 2026-09-10 audit deltas

Re-verified everything (live gateway + upstream releases + provider docs + an
adversarial code review). D1/D1a/D2 all still stand: LiteLLM latest is v1.100.1
but no CVE affects our pinned v1.97.0 (keep the pin, re-check advisories ~Nov 1);
OmniRoute v3.8.50 still lacks lifetime per-key USD budgets. Changes applied:

- Lane 1 model: `muse-spark-1.2-contributor` → `muse-spark-1.3-contributor`
  (same price, agentic/coding-tuned, Meta's new docs default; verified live).
- `ohack-free` Cerebras entry: `zai-glm-4.7` (deprecated by Cerebras 2026-08-17)
  → `gpt-oss-120b`. Cerebras treated as burst overflow only (strict ToS, $5 trial).
- Runbook teardown reordered: spend report export BEFORE key revocation
  (revocation hard-deletes the rows the report reads), and `/global/spend/report`
  replaced with `/spend/logs` (the former is enterprise-only).
- Load-test pass gate now judges TTFT ≤5s p95 (total ≤30s) — a 256-token
  streaming completion legitimately takes 5–9s end-to-end.
- Ops fact: LITELLM_MASTER_KEY was rotated Aug 17 after provisioning (Fly
  releases v2–v6); `keys/gateway-admin.env` is stale for admin creds. Team keys
  unaffected. Meta key live+funded; Moonshot key set but account unfunded;
  Groq/Cerebras still placeholders.

## D4 — Muse Wonder added as a second frontier model (2026-10-13)

Meta released the Muse Wonder family on 2026-10-12. Verified facts
(Meta developer docs for the Meta Model API - models and pricing pages -
cross-checked against launch coverage on 2026-10-13):

| Model | Available via API? | API model ID | Price (per M tokens) |
|---|---|---|---|
| Muse Wonder | Yes - Meta Model API + Muse Code | `muse-wonder-1.0` | $4 in / $0.20 cached in / $20 out |
| Muse Wonder Full | No - Muse Code subscription only (Power $50/mo, Maximum $200/mo) | none | n/a |

- Wonder uses the same `https://api.meta.ai/v1` base URL and the same
  `META_MODEL_API_KEY` as `muse-spark`, has a 1M-token context, and is
  positioned for long-horizon agentic and coding work.
- There is **no Contributor tier for Wonder** (that discount exists only for
  Muse Spark). Wonder is standard-priced, so it does not belong on the
  $15 Key 1 lane: at $4/$20 it would burn that budget roughly 40x/100x
  faster than Spark Contributor on input/output.

Decisions:

- **Add `muse-wonder` on Key 2, alongside `kimi-k3`.** Key 2 stays $20/team
  and the per-team total stays $35. Teams now choose between two frontier
  models on the same key and budget: Wonder (Meta, 1M context) or Kimi K3
  (cheaper per token at $3/$15).
- **`muse-spark` stays the default.** Wonder is a premium tier, not a
  Spark replacement. Spark Contributor remains the cheap default lane.
- **No `muse-wonder-full` entry.** It has no API, so a config block for it
  could only fail. The guide says this explicitly so teams do not go
  looking for the model behind most of the launch-benchmark headlines.
- **No fallback for `muse-wonder`, and no alias remap.** Like `kimi-k3`,
  it fails closed on `budget_exceeded`. The existing `ohack-frontier`
  alias still points at `kimi-k3` — remapping it would silently change
  the model and price for anyone still using the old name.

Still to verify after this merges (not established by this change):

1. The live Meta key is entitled and billed for `muse-wonder-1.0`
   (preview model, no Contributor tier — billing must be on). Smoke test
   is in runbook.md, morning-of step 3.
2. Existing Key 2 keys were provisioned with `models: [kimi-k3]` only.
   LiteLLM checks the requested name against the key's allow-list, so
   existing frontier keys must be updated (`/key/update`) to add
   `muse-wonder`, or re-provisioned — the config change alone does not
   grant them access. New keys from `scripts/provision_keys.py` already
   include it.
3. After `fly deploy`, confirm `/v1/models` lists `muse-wonder` and the
   guide at `/ui/guide/` shows the new table.

## D5 — Keys expire via `duration`; overflow lane funded; Claude Code flag committed (2026-11-08)

Found while validating two backend-minted team keys against the live gateway:

- `/key/info` returned `expires: None` for every key. LiteLLM v1.97.0's
  `/key/generate` has **no `expires` field** — the ohack.dev backend sent one
  and it was silently dropped; the card provisioner sent nothing. The only
  supported knob is `duration` (`"<n>s|m|h|d"`), which LiteLLM turns into
  `expires = now + duration` on both `/key/generate` and `/key/update`.
  **Decision:** every key expires at `2026-11-16T07:00:00Z` (midnight
  Arizona after the event) — **superseded Nov 10 2026: `2026-11-16T01:00:00Z`
  = Sun Nov 15, 6:00 PM Arizona, right after the awards** (Greg). `provision_keys.py` sends `duration`; the new
  `scripts/set_key_expiry.py` fixes live keys; the backend sends `duration`
  (backend PR #325). `revoke_all.py` stays as the teardown backstop.
- `gpt-oss-120b` failed "Wrong API Key" until Nov 8 — Groq/Cerebras secrets
  were placeholders. Now set and verified from both providers.
- The `use_chat_completions_url_for_anthropic_messages: true` fix that makes
  Claude Code + Moonshot tool calls work had been deployed from a laptop on
  Oct 4 but never committed; with CI deploying `main` on push, any merge
  would have reverted it. It is in the committed config now.
- `muse-spark` spends ~400 hidden reasoning tokens per tool turn and only
  supports `tool_choice: "auto"`; documented for teams rather than worked
  around (no prompt rewriting per PLAN §Phase 2).

## D6 — Frontier lane moves to Kimi K3.1 Pro; reasoning_effort only where safe; overflow lane on native providers (2026-11-08)

Verified facts (platform.kimi.ai thinking-models guide + Nov 2026 price sheet,
dev.meta.ai reasoning docs, console.groq.com reasoning docs, live probes
against ai.ohack.dev):

| Model | `reasoning_effort` values | Default | Rejects |
|---|---|---|---|
| kimi-k3.1-pro / kimi-k3 | low, high, max (also tolerates none/minimal/medium/xhigh) | max | nothing |
| kimi-k2.7-code | none — thinking always on | n/a | n/a |
| muse-spark-1.3-contributor, muse-wonder-1.0 | minimal, low, medium, high, xhigh | model-chosen | `none` (400) |
| gpt-oss-120b (Groq, Cerebras) | low, medium, high | medium | none, minimal, max, xhigh (400) |

- Kimi K3.1 Pro (launched 2026-10-24) is $2 / $0.20 cached / $10 per M vs
  Kimi K3 at $3 / $0.30 / $15, same 1M context and effort values.
- LiteLLM v1.97.0 silently drops `reasoning_effort` for model IDs not in its
  catalog when `drop_params: true` (probe: Meta returned 200 for `none`,
  which it rejects when it actually arrives). The Anthropic adapter maps
  `thinking.type: disabled` to `none` and `budget_tokens` to
  minimal/low/medium/high, so a passthrough exposes every backend to values
  Claude Code can legitimately send.
- With `model: openai/openai/gpt-oss-120b` (Groq's id has its own `openai/`
  prefix) the `/v1/messages` path mangled the model and both overflow
  deployments 404'd; `/v1/chat/completions` was unaffected.

Decisions:

- **`kimi-k3` is now served by `openai/kimi-k3.1-pro`.** The public name
  stays `kimi-k3`: it sits in every frontier key's allow-list (frontend-minted
  keys included), and the alias `ohack-frontier` still resolves to it.
- **Forward `reasoning_effort` only on `kimi-k3`** (`allowed_openai_params`
  + `supports_reasoning`). Moonshot's default is `max`, the most expensive
  setting, so teams gain a real cost lever and nothing can 400. Not enabled on
  `muse-spark`/`muse-wonder` (Meta 400s on `none`; for `muse-spark` that
  became a silent fallback to `kimi-k2.7-code` at ~20x the price) nor on
  `gpt-oss-120b` (a fallback lane must accept whatever the primary carried).
- **Overflow lane uses native `groq/` and `cerebras/` providers** with
  `additional_drop_params: ["reasoning_effort"]`, so Claude Code can reach it
  and any effort value is tolerated.
- **Skip `muse-wonder` effort control and Muse Wonder as a default lane**
  (unchanged from D4); `muse-wonder` keeps the same model-chosen reasoning.

Same day, the card-key pool (50 `team-NN(-frontier)` + 10 `spare-NN(-frontier)`)
was deleted: teams are minted from the frontend as `fall26-<team_id>(-frontier)`,
which already carry `muse-wonder`. `mentors-frontier` still allows only kimi-k3.
