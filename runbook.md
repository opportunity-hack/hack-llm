# Event runbook — OHack Fall 2026 AI Gateway

Audience: any volunteer, no prior context needed. The gateway is a LiteLLM
proxy on Fly.io (app `ohack-ai-gateway`, org `opportunity-hack`, region `phx`),
keys and spend live in Fly Postgres (app `ohack-ai-gateway-db`).

You need: `flyctl` logged into the `opportunity-hack` org, Python 3.11+ with
`requests`, and the **master key** (in the organizer password vault — never in git).

```bash
export MK="sk-..."   # master key, from the vault
export GW="https://ai.ohack.dev"
```

## Morning-of checklist (Nov 14 and Nov 15, ~06:30)

1. **Gateway up?**
   ```bash
   curl -s $GW/health/liveliness        # expect: "I'm alive!"
   curl -s $GW/health/readiness         # expect: JSON with "status":"connected"
   curl -s $GW/v1/models -H "Authorization: Bearer $MK" | python3 -m json.tool
   # expect: ohack, ohack-frontier, ohack-free, ohack-mid
   ```
2. **Both machines healthy?**
   ```bash
   fly status -a ohack-ai-gateway       # expect 2 machines, state=started, checks passing
   ```
3. **One real completion round-trips:**
   ```bash
   curl -s $GW/v1/chat/completions -H "Authorization: Bearer $MK" \
     -H 'Content-Type: application/json' \
     -d '{"model":"ohack","messages":[{"role":"user","content":"say ok"}]}'
   ```
4. **Provider balances** (manual): Meta dashboard (dev.meta.ai) and Moonshot
   (platform.moonshot.ai) — confirm remaining credit and that the provider-side
   spend limits from PLAN §3 ($400 Meta / $600 Moonshot) are still set.
5. **Spend snapshot:** `python scripts/check_spend.py --base-url $GW --master-key $MK`

## Every 3 hours during the event

Run `python scripts/check_spend.py --base-url $GW --master-key $MK`.

- **Event total > $500** → announce in the event Slack: "Heads up teams — for
  routine work please use model `ohack-free`; save `ohack`/`ohack-frontier` for
  the hard stuff."
- **Event total > $800** → disable the frontier lane globally:
  1. Edit `config/litellm-config.yaml`: comment out the entire
     `ohack-frontier` block under `model_list`.
  2. `fly deploy -a ohack-ai-gateway` (takes ~1 min; rolling, no downtime).
  3. Announce: "`ohack-frontier` is closed for the rest of the event; `ohack`
     still works for everyone."

## Incident playbooks

### A provider is down / erroring
`ohack` auto-falls back (Muse → K2.7 → free tiers) — usually no action needed.
To take a provider out of rotation explicitly: comment its block out of
`config/litellm-config.yaml` and `fly deploy -a ohack-ai-gateway`.

### Gateway down
```bash
fly status -a ohack-ai-gateway
fly logs -a ohack-ai-gateway            # look for crash loops / DB errors
fly machine restart <machine-id> -a ohack-ai-gateway
```
If Postgres is the problem: `fly status -a ohack-ai-gateway-db`, then
`fly machine restart <id> -a ohack-ai-gateway-db`.
Slack template: "⚠️ The AI gateway is having a moment — we're on it. Meanwhile
your tools may error; nothing is wrong with your key. Update in 15 min."

### A team's key leaked publicly
Revoke BOTH of the team's keys (they're printed on the same card):
```bash
curl -X POST $GW/key/delete -H "Authorization: Bearer $MK" \
  -H 'Content-Type: application/json' \
  -d '{"key_aliases":["team-07","team-07-frontier"]}'
```
Then hand the team a spare card (spare-01..spare-05) and note the swap in the
organizer channel. Spares are pre-provisioned with the same budgets.

### A team hit its budget and it's legitimate
Raise one team's cap (organizer judgment call, keep it small):
```bash
# find the key hash: GET /key/list, then:
curl -X POST $GW/key/update -H "Authorization: Bearer $MK" \
  -H 'Content-Type: application/json' \
  -d '{"key":"<key-or-hash>","max_budget":45}'
```

## Scale up for the event / down after

```bash
fly scale count 2 -a ohack-ai-gateway   # Nov 13, before doors
fly scale count 1 -a ohack-ai-gateway   # Nov 16, teardown
```

## Teardown (Nov 16)

1. `python scripts/revoke_all.py --base-url $GW --master-key $MK --yes`
2. Export the final spend report before wiping anything:
   ```bash
   python scripts/check_spend.py --base-url $GW --master-key $MK \
     > reports/fall-2026-spend.md
   curl -s "$GW/global/spend/report?start_date=2026-11-13&end_date=2026-11-16" \
     -H "Authorization: Bearer $MK" >> reports/fall-2026-spend.md
   ```
3. `fly scale count 1 -a ohack-ai-gateway` (or `fly apps destroy` both apps if done for good).
4. Remove/zero the spend limits and unused credit at Meta + Moonshot dashboards.
5. If any sponsor granted credits: send them the usage numbers from step 2.
6. Rotate `LITELLM_MASTER_KEY` (`fly secrets set LITELLM_MASTER_KEY=... -a ohack-ai-gateway`).

## One-time setup still pending (Greg)

1. **DNS** — in Cloudflare, for `ai.ohack.dev`, **DNS-only (gray cloud, proxy
   OFF — Cloudflare proxying breaks streaming)**, either:
   - `CNAME ai → ohack-ai-gateway.fly.dev`, or
   - `A ai → 66.241.125.248` and `AAAA ai → 2a09:8280:1::174:a9d5:0`
   Then `fly certs check ai.ohack.dev -a ohack-ai-gateway` until it says issued.
   Until DNS lands, everything works at `https://ohack-ai-gateway.fly.dev`.
2. **Provider keys** — currently placeholders. When funded (PLAN §5, with
   provider-side spend limits set FIRST):
   ```bash
   fly secrets set -a ohack-ai-gateway META_MODEL_API_KEY=... MOONSHOT_API_KEY=... \
     GROQ_API_KEY=... CEREBRAS_API_KEY=...
   ```
   (`fly secrets set` triggers a rolling restart automatically.) Then verify a
   real completion per the morning checklist, and re-check the free-tier model
   IDs in `config/litellm-config.yaml` against each provider's `/v1/models`.
3. **Master key + UI login** are in `keys/gateway-admin.env` on the provisioning
   laptop — move them into the organizer password vault.

## Known gotchas

- Budget checks read spend that flushes to Postgres in ~10s batches: a team
  can overshoot its cap by a few cents on a burst. Provider-side limits
  (PLAN §3) are the real ceiling — never remove those.
- Budget-exhausted requests return HTTP 429 with `"type": "budget_exceeded"`
  and a human-readable message naming the key and amounts.
- Muse Contributor lane is limited to 60 requests/min account-wide; under
  burst, teams transparently fall back to `ohack-mid` (K2.7) — that's by design,
  not an incident.
- The LiteLLM admin UI is at `https://ai.ohack.dev/ui` (login = `UI_USERNAME` /
  `UI_PASSWORD` Fly secrets). Handy for eyeballing keys and spend graphs.
