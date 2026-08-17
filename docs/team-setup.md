# Your AI endpoint — OHack Fall 2026

> This file is the source content for the ohack.dev docs page at
> `/hack/[event_id]/ai` (PLAN.md Phase 4). Port it into the Next.js app
> following the `/hack/[event_id]/letters` pattern. Keep it phone-readable.

Your printed card from check-in has **two API keys** and one endpoint. It works
with Claude Code, Cursor, Cline, Continue, and any OpenAI or Anthropic SDK.

- **Base URL:** `https://ai.ohack.dev/v1`
- **Key 1** (use this one by default) — **$15 budget**, models:
  - `ohack` — the default. Fast, cheap, auto-falls-back if a provider is down.
  - `ohack-free` — free-tier providers. Rate-limited but costs nothing.
- **Key 2** — **$20 budget**, one model:
  - `ohack-frontier` — the big gun (Kimi K3). Spend it on hard problems, not boilerplate.
- That's **$35 per team total**. When a budget is gone, requests return a clear
  `budget_exceeded` error — find an organizer.

Examples below use Key 1. To use `ohack-frontier`, swap in Key 2 **and** set the
model to `ohack-frontier` — the frontier model only works with Key 2.

## Claude Code

```bash
export ANTHROPIC_BASE_URL="https://ai.ohack.dev"   # no /v1 — Claude Code adds it
export ANTHROPIC_AUTH_TOKEN="sk-YOUR-KEY-1"
export ANTHROPIC_MODEL="ohack"
claude
```

Frontier session instead: `ANTHROPIC_AUTH_TOKEN` = Key 2 and `ANTHROPIC_MODEL=ohack-frontier`.

Or put it in `~/.claude/settings.json` so it sticks:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://ai.ohack.dev",
    "ANTHROPIC_AUTH_TOKEN": "sk-YOUR-KEY-1",
    "ANTHROPIC_MODEL": "ohack"
  }
}
```

## Cursor

Settings → Models → API Keys → **OpenAI API Key**:
1. Paste Key 1.
2. Enable **Override OpenAI Base URL** and set it to `https://ai.ohack.dev/v1`.
3. Add a custom model named `ohack`. (For `ohack-frontier`, switch the API key to Key 2 and add that model name.)

## Cline (VS Code)

Settings → API Provider → **OpenAI Compatible**:
- Base URL: `https://ai.ohack.dev/v1`
- API Key: Key 1
- Model ID: `ohack`

## Continue

`~/.continue/config.yaml`:

```yaml
models:
  - name: ohack
    provider: openai
    model: ohack
    apiBase: https://ai.ohack.dev/v1
    apiKey: sk-YOUR-KEY-1
```

## Python (OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(base_url="https://ai.ohack.dev/v1", api_key="sk-YOUR-KEY-1")
r = client.chat.completions.create(
    model="ohack",
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
  model: "ohack",
  messages: [{ role: "user", content: "Hello from OHack!" }],
});
console.log(r.choices[0].message.content);
```

## Data notice

The default `ohack` model uses Meta's Contributor tier. Your prompts and
generated code may be used by Meta to train its models. All OHack projects are
open source, so this matches how your code will be published anyway. If your
team objects, use `ohack-free`.

## Troubleshooting

| Symptom | Meaning | Fix |
|---|---|---|
| `401` | Bad or missing key | Re-copy the key from your card; check for stray spaces |
| `429` with `budget_exceeded` | That key's budget is spent | Find an organizer |
| "model not allowed" / access error | Wrong key for the model | `ohack-frontier` needs Key 2; everything else needs Key 1 |
| Slow responses | Default lane is saturated | Switch to `ohack-free`, or take a walk — it's a hackathon |
| Tool insists on a `claude-*` model name | Some tools filter model pickers | Set the model name manually to `ohack` (env var or custom model entry) |

Your keys are shared by your whole team. Don't commit it, don't post it, don't
paste it into public demos. Leaked keys get revoked and you'll have to fetch a
spare from an organizer.
