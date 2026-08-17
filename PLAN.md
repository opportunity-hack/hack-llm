# SPEC: OHack Fall 2026 AI Gateway ("hack-llm")

**Owner:** Greg Vannoni, Opportunity Hack (ohack.dev)
**Event:** Fall 2026 Hackathon, Nov 14-15, ASU Tempe, ~100 participants, ~25 teams
**Status:** Ready for implementation
**Executor:** Claude (Fable/Opus/Sonnet via Claude Code). Work phase by phase. Do not start a phase until the prior phase's acceptance criteria pass. Ask Greg only when a DECISION marker is unresolved or a credential is missing.

---

## 1. Goal

One OpenAI-compatible endpoint that every hackathon team points their coding tool (Claude Code, Cursor, Cline, Continue, etc.) at. Tiered model routing keeps total event cost under $700 with a hard ceiling of $1,000, while giving every team frontier-model access.

```
Team's coding tool ──> https://ai.ohack.dev/v1 (OmniRoute on Fly.io)
                          ├─ Lane 1 (default): Muse Spark 1.2 Contributor  (~$0.10/$0.20 per M)
                          ├─ Lane 2 (frontier, capped): Kimi K3            ($3/$15 per M, $20/team cap)
                          ├─ Lane 3 (mid fallback): Kimi K2.7 Code         ($0.95/$4 per M)
                          └─ Lane 4 (overflow): stacked free tiers         ($0, rate-limited)
```

## 2. Non-goals

- No self-hosted model weights, no GPUs (Fly.io GPUs are discontinued).
- No per-individual accounts. Keys are per-team (25 keys + 5 spares + 1 mentor key + 1 admin key).
- No handling of private/sensitive code guarantees. Contributor tier data may be used by Meta for training; this is acceptable because all OHack code is open source. State this clearly on the docs page (Phase 4).

## 3. Hard constraints and guardrails

| Constraint | Value | Enforcement |
|---|---|---|
| Total event budget | $700 target, $1,000 hard stop | Per-key USD quotas + provider-side spend limits |
| Per-team Kimi K3 budget | $20 | OmniRoute per-key spend quota on the K3 combo lane |
| Per-team total budget | $35 | OmniRoute per-key spend quota (all lanes) |
| Gateway uptime window | Nov 14 07:00 - Nov 15 20:00 MST | 2 Fly machines, different regions optional |
| Key rotation | All keys revoked Nov 16 | Teardown script (Phase 6) |
| Provider-side ceilings | Set $400 limit on Meta Model API account, $600 on Moonshot account | Manual, in each provider dashboard, BEFORE event |

Provider-side spend limits are the true backstop. OmniRoute caps are the first line; never rely on them alone.

## 4. Repos and infrastructure

| Item | Value |
|---|---|
| New repo | `opportunity-hack/hack-llm` (config, scripts, runbook; NO secrets committed) |
| Gateway software | OmniRoute (MIT), https://github.com/diegosouzapw/OmniRoute — deploy from official Docker image, pin an exact version tag |
| Host | Fly.io, app name `ohack-ai-gateway`, region `phx` |
| Domain | `ai.ohack.dev` CNAME -> Fly app (Cloudflare DNS, proxy OFF for streaming) |
| Persistence | Fly volume `omniroute_data`, 3GB, mounted at OmniRoute's data dir |
| Docs page | `ohack.dev` Next.js route `/hack/[event_id]/ai` (follows existing `/hack/[event_id]/letters` pattern) |

## 5. Secrets inventory (Greg provides; store as Fly secrets, never in git)

| Secret | Source | Notes |
|---|---|---|
| `META_MODEL_API_KEY` | dev.meta.ai / Meta Model API | Contributor-tier model access; verify `muse-spark-1.2-contributor` SKU is selectable per-request |
| `MOONSHOT_API_KEY` | platform.kimi.ai (api.moonshot.ai intl billing) | Fund $600; set hard spend limit |
| `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `NVIDIA_NIM_API_KEY` | Free-tier signups | Overflow lane. Verify current ToS permits shared/pooled use before enabling; drop any provider whose ToS forbids it |
| `OMNIROUTE_ADMIN_PASSWORD` | Generate 32-char random | Dashboard login |
| `OPENROUTER_API_KEY` (optional) | openrouter.ai, fund $50 | Escape hatch if a direct provider fails day-of |

**DECISION (Greg):** Sponsor credits. Before funding accounts, send credit requests to Moonshot (OSS/community program), Meta (Muse Code beta/community), and Anthropic. If any lands, adjust lane priorities to burn granted credits first. Do not block implementation on this; the paid path is the default plan.

---

## 6. Phases

### Phase 1 — Deploy OmniRoute on Fly.io

Tasks:
1. Create `opportunity-hack/hack-llm` repo with: `fly.toml`, `README.md`, `scripts/`, `runbook.md`, `.gitignore` (exclude `.env*`, `keys/`).
2. `fly.toml`: use OmniRoute's official Docker image at a pinned version; internal port matching OmniRoute default (20128); `shared-cpu-2x`, 2GB RAM; mount volume `omniroute_data`; `min_machines_running = 1` now, scale to 2 for event weekend; health check on OmniRoute's health endpoint (consult OmniRoute docs for path).
3. Set all Fly secrets from §5.
4. Deploy. Add `ai.ohack.dev` cert via `fly certs add`; create CNAME in Cloudflare (DNS-only mode).
5. Enable OmniRoute's dashboard auth (password login) so the admin UI is not public. Consult OmniRoute security docs; if the dashboard cannot be safely locked down, restrict it to Fly private networking + WireGuard and expose only `/v1` publicly.

Acceptance criteria:
- `curl https://ai.ohack.dev/v1/models` returns a model list over HTTPS.
- Dashboard unreachable without password.
- Machine restart preserves config (volume works).
- A chat completion round-trips through at least one provider.

### Phase 2 — Providers, lanes, routing

Consult OmniRoute docs (`docs/routing/AUTO-COMBO.md`, provider reference) for exact config syntax. Requirements, not syntax, are normative here:

1. Connect providers: Meta Model API (Muse Spark 1.2 Contributor), Moonshot (kimi-k3 and kimi-k2.7-code), free-tier providers from §5.
2. Create three virtual model names teams will use:

| Model name teams see | Routes to | Strategy |
|---|---|---|
| `ohack` (the default we advertise) | Muse Spark 1.2 Contributor -> K2.7 Code -> free tiers | `priority` with auto-fallback on 429/5xx |
| `ohack-frontier` | Kimi K3 only | Direct; fails closed when team's K3 budget exhausted, with clear error message |
| `ohack-free` | Free-tier combo | `headroom` or `auto/offline` strategy |

3. Enable prompt caching passthrough wherever supported (Moonshot cache-hit input is $0.30 vs $3.00; Muse Contributor cached input is $0.002 — cache economics are the whole cost model).
4. Do NOT enable OmniRoute's token compression engines for the event (unproven interaction with agent harnesses; correctness > cost here).
5. Disable OmniRoute memory and any telemetry upload features. Local-first only.

Acceptance criteria:
- Completion against `ohack` returns and dashboard attributes it to Muse Spark Contributor.
- Kill test: with Meta provider manually disabled, `ohack` transparently falls back to K2.7 Code.
- `ohack-frontier` routes to Kimi K3 and cost telemetry shows correct pricing.

### Phase 3 — Team keys and budget caps

1. Write `scripts/provision_keys.py` (or use OmniRoute CLI if it supports batch key ops):
   - Creates 32 keys: `team-01`..`team-25`, `spare-01`..`spare-05`, `mentors`, `admin`.
   - Per key: total spend quota $35; per-lane quota $20 on `ohack-frontier`. If OmniRoute supports only one quota per key, implement the K3 cap as a second key per team (`team-01-frontier`) and document both on the team's card.
   - Outputs `keys/keys.csv` (gitignored): `team_id,key,frontier_key,quota`.
2. Write `scripts/check_spend.py`: polls OmniRoute analytics/cost endpoints, prints per-team spend table, warns at 80% of any quota. Runnable via cron or manually during event.
3. Write `scripts/revoke_all.py` for teardown.

Acceptance criteria:
- A test key stops working (clear 4xx with human-readable message) after its quota is exhausted (test with a $0.05 quota key).
- `check_spend.py` shows live per-key spend matching dashboard.
- Keys survive gateway restart.

### Phase 4 — Team-facing docs page on ohack.dev

Add `/hack/[event_id]/ai` to the ohack.dev Next.js app (mirror the letters page pattern):

1. Content sections:
   - "Your AI endpoint": base URL `https://ai.ohack.dev/v1`, model names `ohack`, `ohack-frontier`, `ohack-free`, and the team's budget ($35 total, $20 frontier).
   - Copy-paste setup blocks for: Claude Code (`ANTHROPIC_BASE_URL` env override per OmniRoute's CLI-INTEGRATIONS doc), Cursor, Cline, Continue, and generic OpenAI SDK (Python + Node).
   - Data notice (verbatim requirement): "The default `ohack` model uses Meta's Contributor tier. Your prompts and generated code may be used by Meta to train its models. All OHack projects are open source, so this matches how your code will be published anyway. If your team objects, use `ohack-free`."
   - Troubleshooting: 401 = bad key, 402/429 with quota message = budget hit (find an organizer), slow = switch to `ohack-free`.
2. Keys are NOT on this page. Distribution: printed cards at check-in (QR + key string), generated by `scripts/make_key_cards.py` producing a print-ready PDF from `keys.csv` (one card per team: team ID, both keys as text + QR, endpoint URL, budget, docs page QR).

Acceptance criteria:
- Page renders on mobile (participants will read it on phones).
- Every setup block copy-pastes and works against the live gateway (test each tool for real, minimum: Claude Code, Cursor, generic Python SDK).
- Key cards PDF generates for all 32 keys.

### Phase 5 — Load test and dry run (complete by Nov 7)

1. `scripts/load_test.py`: simulate 25 concurrent agent sessions (streaming chat completions, 8K-token prompts, 60% repeated prefix to exercise cache) for 10 minutes. Record p50/p95 latency and error rate.
2. Scale check: if p95 > 5s or errors > 1%, bump Fly machine size and/or count; re-run.
3. Full dry run with 3-5 OHack volunteers using real coding tools on a sample nonprofit repo for one hour. Collect friction notes; fix docs page accordingly.
4. Set Fly to 2 machines for Nov 13-16; calendar reminder to scale down after.

Acceptance criteria:
- Load test passes thresholds.
- All dry-run volunteers complete setup in under 5 minutes using only the docs page.

### Phase 6 — Event runbook + teardown (`runbook.md` in repo)

Must contain:
- Morning-of checklist: health check, provider balance check, run `check_spend.py`, verify both Fly machines healthy.
- Every-3-hours during event: run `check_spend.py`; if event-wide spend > $500, announce `ohack-free` as preferred lane; if > $800, disable `ohack-frontier` lane globally (document the exact OmniRoute command/config toggle to do this).
- Incident playbooks: provider outage (toggle lane priority), gateway down (Fly restart + status Slack message template), key leaked publicly (revoke + issue spare).
- Teardown (Nov 16): `revoke_all.py`, export final spend report (per team + total) to `reports/fall-2026-spend.md`, scale Fly to 1 machine or destroy app, remove provider spend, close the loop with any sponsor (usage report for credit grantors).

Acceptance criteria: a volunteer who has never seen the system can execute the morning checklist from the runbook alone.

---

## 7. Budget model (reference)

| Line | Est. | Ceiling mechanism |
|---|---|---|
| Muse Spark Contributor (default lane, all teams) | $30-60 | Meta account limit $400 |
| Kimi K3 frontier lane | $300-500 | 25 x $20 key caps; Moonshot limit $600 |
| K2.7 Code fallback | $50-100 | Included in $35/team caps |
| Free tiers | $0 | n/a |
| Fly.io (2 machines x 1 month + volume) | ~$35 | n/a |
| OpenRouter escape hatch | $0-50 | Prefund $50 max |
| **Total** | **~$450-750** | **Hard stop ~$1,000** |

## 8. Open items for Greg (not blocking Phases 1-3)

1. Send sponsor credit emails (Moonshot, Meta, Anthropic). I can draft these.
2. Confirm `ai.ohack.dev` DNS access.
3. Fund Meta Model API and Moonshot accounts, set provider-side spend limits per §3.
4. Decide whether mentors get an uncapped or $50-capped key (spec assumes $50 cap).

## 9. Executor notes for Claude

- Pin the OmniRoute version at Phase 1 and never upgrade after Nov 1. Re-verify config syntax against the pinned version's docs, not the README's latest.
- OmniRoute is a fast-moving community project: treat its admin/key/quota API as "verify before use." If a required feature (per-key USD quota) doesn't exist or is broken in the pinned version, STOP and propose the fallback: LiteLLM proxy, which has mature per-key budgets, keeping everything else in this spec identical.
- Never print or log full API keys; log key prefixes only.
- All scripts: Python 3.11+, stdlib + `requests` + `qrcode`/`reportlab` for cards, each with `--dry-run`.

