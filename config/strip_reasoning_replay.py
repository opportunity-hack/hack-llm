"""Strip replayed reasoning from assistant turns before Groq / Cerebras.

Claude Code sends every earlier assistant turn back with its `thinking` blocks.
LiteLLM's /v1/messages bridge turns those into `thinking_blocks` (and
`reasoning_content`) on the OpenAI-format assistant message, and both Groq and
Cerebras reject the request outright:

    messages.2.assistant.thinking_blocks: property ... is unsupported

So every Claude Code session on gpt-oss-120b failed on its second turn, and so
did any muse-spark / kimi-k2.7-code session that fell back to gpt-oss-120b.
`additional_drop_params` can't fix it: in v1.97.0 it only drops request
parameters, never fields inside `messages`.

This runs per deployment (after the router picks Groq or Cerebras, including
on a fallback) and removes only those two fields. The visible text and tool
calls of earlier turns are untouched. Other providers are left alone.
"""

from litellm.integrations.custom_logger import CustomLogger

STRIP_PROVIDERS = ("groq", "cerebras")
REPLAY_FIELDS = ("thinking_blocks", "reasoning_content")


def _provider(kwargs):
    provider = kwargs.get("custom_llm_provider")
    if provider:
        return provider
    model = kwargs.get("model") or ""
    return model.split("/", 1)[0] if "/" in model else ""


def strip_replayed_reasoning(messages):
    """Return a copy of `messages` without reasoning on assistant turns.

    Returns None when nothing needed stripping, so callers can skip the copy.
    """
    if not isinstance(messages, list):
        return None
    changed = False
    cleaned = []
    for message in messages:
        if (
            isinstance(message, dict)
            and message.get("role") == "assistant"
            and any(field in message for field in REPLAY_FIELDS)
        ):
            message = {k: v for k, v in message.items() if k not in REPLAY_FIELDS}
            changed = True
        cleaned.append(message)
    return cleaned if changed else None


class StripReasoningReplay(CustomLogger):
    async def async_pre_call_deployment_hook(self, kwargs, call_type):
        if _provider(kwargs) not in STRIP_PROVIDERS:
            return None
        cleaned = strip_replayed_reasoning(kwargs.get("messages"))
        if cleaned is None:
            return None
        return {**kwargs, "messages": cleaned}


proxy_handler_instance = StripReasoningReplay()
