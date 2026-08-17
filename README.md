# hack-llm — OHack Fall 2026 AI Gateway

One OpenAI-compatible (and Anthropic-compatible) endpoint every hackathon team
points their coding tool at: **`https://ai.ohack.dev/v1`**.

Teams use three virtual model names; the gateway (LiteLLM proxy on Fly.io)
routes, falls back, meters cost, and enforces per-team budgets:

| Model teams use | Routes to | Key / budget |
|---|---|---|
| `ohack` (default) | Muse Spark 1.2 Contributor → Kimi K2.7 Code → free tiers | Key 1 — $15/team |
| `ohack-free` | stacked free tiers (Groq/Cerebras/NVIDIA) | Key 1 — $0 cost |
| `ohack-frontier` | Kimi K3, no fallback (fails closed on budget) | Key 2 — $20/team |

Each team gets two keys ($35 total) because per-key-per-model USD caps are
enterprise-only in LiteLLM OSS — the dual-key pattern PLAN §Phase 3 pre-approved.

Full spec: [PLAN.md](PLAN.md). Why LiteLLM and not OmniRoute: [DECISIONS.md](DECISIONS.md).
Event-day operations: [runbook.md](runbook.md). Team-facing setup instructions
(source for the ohack.dev docs page): [docs/team-setup.md](docs/team-setup.md).

## Layout

```
fly.toml                  Fly.io app config (app: ohack-ai-gateway, region: phx)
config/litellm-config.yaml  Providers, lanes, fallbacks, pricing — the whole routing brain
scripts/provision_keys.py Create the 32 team/spare/mentor/admin keys with budgets
scripts/check_spend.py    Live per-team spend table, warns at 80% of quota
scripts/revoke_all.py     Teardown: revoke every key
scripts/make_key_cards.py Print-ready PDF key cards from keys/keys.csv
scripts/load_test.py      25-session streaming load test (Phase 5)
keys/                     Generated keys + cards — gitignored, never commit
runbook.md                Morning checklist, incident playbooks, teardown
```

## Operator quickstart

```bash
# Secrets (one time; values from Greg — see PLAN.md §5)
fly secrets set -a ohack-ai-gateway \
  LITELLM_MASTER_KEY=sk-... \
  META_MODEL_API_KEY=... MOONSHOT_API_KEY=... \
  GROQ_API_KEY=... CEREBRAS_API_KEY=... NVIDIA_NIM_API_KEY=... \
  UI_USERNAME=admin UI_PASSWORD=...

# Deploy
fly deploy -a ohack-ai-gateway

# Verify
curl https://ai.ohack.dev/v1/models -H "Authorization: Bearer $ANY_TEAM_KEY"

# Provision team keys (writes keys/keys.csv)
python scripts/provision_keys.py --master-key $LITELLM_MASTER_KEY

# Watch spend during the event
python scripts/check_spend.py --master-key $LITELLM_MASTER_KEY
```

Python scripts need: `pip install requests qrcode reportlab`.

## Never commit

`keys/`, `.env*`, any file containing an API key. The `.gitignore` enforces this;
don't fight it.
