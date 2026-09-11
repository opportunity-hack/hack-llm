# hack-llm — context for Claude

OHack Fall 2026 (Nov 14-15) AI gateway: a **LiteLLM proxy** (pinned
`ghcr.io/berriai/litellm-database:v1.97.0`) on Fly.io serving one endpoint for
all hackathon teams' coding tools. PLAN.md is the spec; DECISIONS.md explains
why LiteLLM replaced OmniRoute (its pre-approved fallback) and the dual-key
budget design; runbook.md is event ops.

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
