# hack-llm — context for Claude

OHack Fall 2026 (Nov 14-15) AI gateway: a **LiteLLM proxy** (pinned
`ghcr.io/berriai/litellm-database:v1.97.0`) on Fly.io serving one endpoint for
all hackathon teams' coding tools. PLAN.md is the spec; DECISIONS.md explains
why LiteLLM replaced OmniRoute (its pre-approved fallback) and the dual-key
budget design; runbook.md is event ops.

## State (2026-11-08)

- **Key expiry was a no-op everywhere.** LiteLLM `/key/generate` has no
  `expires` field (silently dropped — `GenerateKeyRequest` v1.97.0); expiry
  is `duration` ("<n>s|m|h|d") → `expires = now + duration`, same on
  `/key/update`. `provision_keys.py` now sends `duration` (`--expires`,
  default `2026-11-16T01:00:00Z` = Sun Nov 15 6 PM AZ, moved from 07:00Z on Nov 10); new `scripts/set_key_expiry.py` sweeps
  live `team-*`/`spare-*`/`mentors*`/`fall26-*` keys via `/key/update`
  (dry-run default, `--yes` applies; run before doors — runbook). The
  ohack.dev backend (`api/teams/gateway_keys.py`, backend PR #325) had the
  same bug and now sends `duration` too.
- **Groq + Cerebras secrets set** — `gpt-oss-120b` verified live from both
  providers (`x-litellm-model-api-base` header). Overflow lane is real now.
- **Claude Code + Kimi fix is now COMMITTED** (was deployed 2026-10-04 as
  machine v10 straight from a laptop, never pushed — CI deploys `main` on
  push, so the next merge would have reverted it): `litellm_settings:
  use_chat_completions_url_for_anthropic_messages: true`. Re-verified Nov 8:
  `/v1/messages` tool-call turns 200 on muse-spark, kimi-k2.7-code,
  muse-wonder, kimi-k3.
- **muse-spark reasoning gotcha (live probe):** hidden reasoning (~350–400
  tokens on a tool turn) counts against `max_tokens`; ≤ ~600 → empty content
  + `finish_reason: length`; 4000 → fine. Only `tool_choice: "auto"` works
  (`required` → 400, and the kimi fallback rejects it the same way).
  Documented in the guide, team-setup.md and runbook.
- `kimi-k3` reports ~5x the input tokens of the prompt (Moonshot counts its
  reasoning scaffold); budgets bill what Moonshot reports — expected.
- Two key pools exist: the 63 card keys from `provision_keys.py` AND
  backend-minted `fall26-<team_id>(-frontier)` keys on team approval (same
  budgets, metadata `ohack_team_id`/`event`/`provisioned_by`/`key_label`).
  A team with both holds $70, not $35 — pick one story before doors.
- Carried over from Greg's Oct 4 laptop notes (never committed): PR #1 rename
  deployed (machine v9), `ai.ohack.dev` DNS live, all 63 keys grant old+new
  names (`/key/info` sweep), `keys/key_cards.pdf` reprinted with two-line key
  labels (`make_key_cards.py` now matches), `keys/gateway-admin.env` refreshed
  from Fly secrets. Master key is a weak non-`sk-` value — rotate before Nov 13.

- **Frontier lane `kimi-k3` now backed by kimi-k3.1-pro** (public name kept so key
  allow-lists + printed cards stay valid): $2/$0.20cache/$10 vs k3 $3/$0.30/$15,
  same 1M ctx + effort values. Guide row updated. Live since release v21 (DECISIONS D6).
  K2 series (kimi-k2.7-code) closed to new accounts Oct 31, retires end Dec 2026.
- **reasoning_effort passthrough ONLY on kimi-k3** (`allowed_openai_params` +
  `model_info.supports_reasoning`); LiteLLM otherwise drops it (drop_params + IDs not
  in its catalog — verified: Meta accepted "none" with 200 before the change).
  Moonshot takes any value, default "max" (costliest). NOT enabled on muse-spark /
  muse-wonder (Meta 400s on "none" = Anthropic `thinking:disabled`; for muse-spark that
  meant a silent fallback to kimi-k2.7-code at ~20x price) nor gpt-oss-120b (Groq/
  Cerebras 400 on none/minimal/max/xhigh → would break the overflow lane). Claude Code
  `thinking.budget_tokens` → minimal(<1024)/low/medium/high(>=4096); `output_config.effort`
  with adaptive. Effort support: muse-spark/wonder minimal..xhigh (no off), kimi-k3
  low|high|max, gpt-oss low|medium|high, kimi-k2.7-code none (thinking always on).
- **gpt-oss-120b was unreachable from Claude Code**: with `openai/openai/gpt-oss-120b`
  the `/v1/messages` path mangled the id and BOTH deployments 404'd (chat/completions
  fine). Now native `groq/openai/gpt-oss-120b` + `cerebras/gpt-oss-120b` with
  `additional_drop_params: [reasoning_effort]`; 200 on both paths, all thinking modes.
- **Incident 2026-11-08:** releases v17–v20 were deployed from a STALE local main
  (pre-PR #2–#4) → muse-wonder + Greg's guide/config changes were off prod ~25 min.
  Fixed at v21 (ff to origin/main + re-applied). Always `git fetch && git status -sb`
  before `fly deploy`. Greg's uncommitted `make_key_cards.py` diff was superseded by
  PR #4's version and dropped.
- **Card-key pool RETIRED 2026-11-08**: all 50 `team-NN(-frontier)` and 10
  `spare-NN(-frontier)` keys deleted (Greg: teams are minted from the frontend now as
  `fall26-<team_id>(-frontier)`; spend on the deleted keys was ~$0.79 total, all
  organizer tests). Remaining 6 keys: admin, mentors, mentors-frontier, 3 fall26.
  `keys/keys.csv` + `keys/key_cards.pdf` are entirely dead — don't hand out cards;
  `provision_keys.py`/`make_key_cards.py`/`revoke_all.py` are legacy. `start_claude.sh`
  pointed at `spare-05` (deleted) — needs a fall26 or new key. Oct 13 "add muse-wonder
  to existing Key 2 allow-lists" TODO is moot (fall26 frontier keys mint with it);
  `mentors-frontier` still allows only kimi-k3 + ohack-frontier.
- muse-wonder-1.0 pricing $4/$20 reconfirmed 2026-11-08; `/health` = 6 deployments OK.

## State (2026-10-13)

- Muse Wonder (Meta, released 2026-10-12) added as a second Key 2 frontier
  model (`muse-wonder` → `muse-wonder-1.0`, $4/$0.20 cached/$20 per M, no
  Contributor tier, no fallback); `kimi-k3` kept, $35/team total unchanged.
  Muse Wonder Full is Muse Code subscription-only with no API - do not add
  it to the config. See DECISIONS.md D4. Still to verify post-merge: live
  Meta key entitlement/billing for Wonder, `/key/update` on existing Key 2
  keys to add `muse-wonder` to their allow-lists, and a live smoke test.

## State (2026-10-04)

- LiteLLM: stable v1.104.0; **GHSA-7hp6 (Critical, 2026-09-30, salt-reuse priv-esc)
  affects pinned v1.97.0 — fix in 1.100.4**. Upgrade before Nov 1 freeze.
- Team guide (`web/guide/index.html`) + key cards now label underlying models
  (muse-spark=Muse Spark 1.3, kimi-k3=Kimi K3, gpt-oss-120b=GPT-OSS pool); redeploy to ship.

## State (2026-08-17)

- Deployed: Fly app `ohack-ai-gateway` + Postgres `ohack-ai-gateway-db`
  (org `opportunity-hack`, region `lax` — Fly retired `phx`).
  Live at https://ohack-ai-gateway.fly.dev; cert for `ai.ohack.dev` created,
  waiting on Greg's Cloudflare DNS (DNS-only mode, proxy OFF).
- 63 keys provisioned (2/team: `team-NN` $15 for ohack/ohack-mid/ohack-free,
  `team-NN-frontier` $20 for ohack-frontier; + spares, mentors, admin).
  Full keys in `keys/keys.csv` + printable `keys/key_cards.pdf` (both gitignored).
  Master key/UI login: `keys/gateway-admin.env`.
- Provider keys (verified 2026-09-10): **Meta live and funded** (`ohack` works
  end-to-end); **Moonshot key set but account unfunded** (suspended — recharge
  at platform.kimi.ai); Groq/Cerebras still `placeholder-pending`. Greg rotated
  LITELLM_MASTER_KEY on Aug 17 (releases v2–v6) — `keys/gateway-admin.env` is
  STALE for admin creds; team keys unaffected. Auth, routing, budgets (429
  budget_exceeded), and key persistence all verified live.

## Audit 2026-09-10 (web-verified)

- LiteLLM: latest stable v1.100.1; **no published CVE affects v1.97.0** (all 2026
  advisories patched by <=1.84.0). v1.98.0 fixed multi-pod budget accuracy —
  only matters if >1 Fly machine. Recheck advisories ~Nov 1 before freeze.
- OmniRoute v3.8.50 (latest): still no lifetime per-key USD budgets — rejection stands.
- Moonshot: docs moved to platform.kimi.ai; base URL still `api.moonshot.ai/v1`.
  Prices/IDs confirmed: `kimi-k3` $3/$0.30cache/$15; `kimi-k2.7-code` $0.95/$0.19/$4.
- Meta: contributor tier is now **100 RPM** (not 60) + 3M TPM; `muse-spark-1.3-contributor`
  exists at identical pricing with better coding — consider swapping in for 1.2.
- Overflow lane: Groq `openai/gpt-oss-120b` still production (free: 30 RPM/1K req/day/
  8K TPM/200K TPD, org-level). Cerebras `zai-glm-4.7` deprecated 2026-08-17; current
  public models: `gpt-oss-120b`, `qwen-3.8-27b`. Both ToS ban key transfer/sharing —
  keep provider keys server-side in the gateway only.

## Rules

- Never commit anything under `keys/` or any real API key; log key prefixes only.
- Don't upgrade the LiteLLM image after Nov 1 (PLAN §9); it's pinned in fly.toml.
- `model_max_budget` is LiteLLM-enterprise-only — that's why two keys per team.
- Routing/pricing changes go in `config/litellm-config.yaml` then
  `fly deploy -a ohack-ai-gateway` (config ships via fly.toml `[[files]]`).
- Scripts are Python 3.11+, stdlib + requests (+qrcode/reportlab for cards),
  all with `--dry-run`.
- Key expiry goes through `duration`, never an `expires` field (LiteLLM drops
  it). Any new key-minting code must send `duration`.
