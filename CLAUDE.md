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
- Provider API keys are **placeholders** (`placeholder-pending`) until Greg
  funds Meta + Moonshot accounts — real completions don't work yet; everything
  else (auth, routing config, budgets, 429 budget_exceeded, key persistence)
  is verified live.

## Rules

- Never commit anything under `keys/` or any real API key; log key prefixes only.
- Don't upgrade the LiteLLM image after Nov 1 (PLAN §9); it's pinned in fly.toml.
- `model_max_budget` is LiteLLM-enterprise-only — that's why two keys per team.
- Routing/pricing changes go in `config/litellm-config.yaml` then
  `fly deploy -a ohack-ai-gateway` (config ships via fly.toml `[[files]]`).
- Scripts are Python 3.11+, stdlib + requests (+qrcode/reportlab for cards),
  all with `--dry-run`.
