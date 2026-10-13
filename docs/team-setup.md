# Your AI endpoint — OHack Fall 2026

> This file is the source content for the ohack.dev docs page at
> `/hack/[event_id]/ai` (PLAN.md Phase 4). Port it into the Next.js app
> following the `/hack/[event_id]/letters` pattern. Keep it phone-readable.
>
> Synced 2026-10-13 to the model names the gateway actually serves
> (the 2026-10-04 rename, plus `muse-wonder` added in DECISIONS.md D4).
> The live gateway guide at `https://ai.ohack.dev/ui/guide` is the same
> content in HTML (`web/guide/index.html`).

Your printed card from check-in has **two API keys** and one endpoint. It works
with Claude Code, Cursor, Cline, Continue, and any OpenAI or Anthropic SDK.

- **Base URL:** `https://ai.ohack.dev/v1`
- **Key 1** (use this one by default) — **$15 budget**, models:
  - `muse-spark` — the default. Fast, cheap, auto-falls-back if a provider is down.
  - `kimi-k2.7-code` — stronger coding help; also the automatic fallback.
  - `gpt-oss-120b` — free-tier providers. Rate-limited but costs nothing.
- **Key 2** — **$20 budget**, frontier models:
  - `muse-wonder` — Muse Wonder (Meta, released Oct 12, 2026). The new big
    gun for long, hard agentic and coding jobs; 1M-token context, frontier
    prices ($4 in / $20 out per M), so spend it deliberately.
  - `kimi-k3` — Kimi K3. The other big gun, cheaper per token ($3 / $15).
- That's **$35 per team total**. When a budget is gone, requests return a clear
  `budget_exceeded` error — find an organizer.

Heard about **Muse Wonder Full**? It is the larger model from the same
Oct 12 launch, but it is only in Muse Code subscriptions — there is no API
for it, so the gateway cannot offer it. Use `muse-wonder`.

The old names `ohack`, `ohack-mid`, `ohack-frontier`, `ohack-free` still
work as aliases. Note `ohack-frontier` still means `kimi-k3`, not
`muse-wonder`.

Examples below use Key 1. To use a frontier model, swap in Key 2 **and** set
the model to `muse-wonder` or `kimi-k3` — frontier models only work with Key 2.

## Claude Code

```bash
export ANTHROPIC_BASE_URL="https://ai.ohack.dev"   # no /v1 — Claude Code adds it
export ANTHROPIC_AUTH_TOKEN="sk-YOUR-KEY-1"
export ANTHROPIC_MODEL="muse-spark"
export ANTHROPIC_SMALL_FAST_MODEL="muse-spark"          # background calls too
export ANTHROPIC_DEFAULT_HAIKU_MODEL="muse-spark"       # (newer Claude Code versions)
claude
```

Frontier session instead: `ANTHROPIC_AUTH_TOKEN` = Key 2 and all three model
vars = `muse-wonder` (or `kimi-k3`).

Or put it in `~/.claude/settings.json` so it sticks:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://ai.ohack.dev",
    "ANTHROPIC_AUTH_TOKEN": "sk-YOUR-KEY-1",
    "ANTHROPIC_MODEL": "muse-spark",
    "ANTHROPIC_SMALL_FAST_MODEL": "muse-spark",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "muse-spark"
  }
}
```

## Cursor

Settings → Models → API Keys → **OpenAI API Key**:
1. Paste Key 1.
2. Enable **Override OpenAI Base URL** and set it to `https://ai.ohack.dev/v1`.
3. Add a custom model named `muse-spark`. (For `muse-wonder` or `kimi-k3`, switch the API key to Key 2 and add that model name.)

## Cline (VS Code)

Settings → API Provider → **OpenAI Compatible**:
- Base URL: `https://ai.ohack.dev/v1`
- API Key: Key 1
- Model ID: `muse-spark`

## Continue

`~/.continue/config.yaml`:

```yaml
models:
  - name: muse-spark
    provider: openai
    model: muse-spark
    apiBase: https://ai.ohack.dev/v1
    apiKey: sk-YOUR-KEY-1
```

## Python (OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(base_url="https://ai.ohack.dev/v1", api_key="sk-YOUR-KEY-1")
r = client.chat.completions.create(
    model="muse-spark",
    messages=[{"role": "user", "content": "Hello from OHack!"}],
)
print(r.choices[0].message.content)
```

## Node (OpenAI SDK)

```js
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://ai.ohack.dev/v1",
  apiKey: "sk-YOUR-KEY-1",
});
const r = await client.chat.completions.create({
  model: "muse-spark",
  messages: [{ role: "user", content: "Hello from OHack!" }],
});
console.log(r.choices[0].message.content);
```

## Data notice

The default `muse-spark` model uses Meta's Contributor tier. Your prompts and
generated code may be used by Meta to train its models. All OHack projects are
open source, so this matches how your code will be published anyway. If your
team objects, use `gpt-oss-120b`. `muse-wonder` has no Contributor tier and
is billed at Meta's standard rates.

## Troubleshooting

| Symptom | Meaning | Fix |
|---|---|---|
| `401` | Bad or missing key | Re-copy the key from your card; check for stray spaces |
| `429` with `budget_exceeded` | That key's budget is spent | Find an organizer |
| "model not allowed" / access error | Wrong key for the model | `muse-wonder` and `kimi-k3` need Key 2; everything else needs Key 1 |
| `muse-wonder-full` not found | Wonder Full has no API (Muse Code subscription only) | Use `muse-wonder` with Key 2 |
| Slow responses | Default lane is saturated | Switch to `gpt-oss-120b`, or take a walk — it's a hackathon |
| Tool insists on a `claude-*` model name | Some tools filter model pickers | Set the model name manually to `muse-spark` (env var or custom model entry) |

Your keys are shared by your whole team. Don't commit it, don't post it, don't
paste it into public demos. Leaked keys get revoked and you'll have to fetch a
spare from an organizer.
