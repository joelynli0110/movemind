"""
LLM abstraction layer — supports Anthropic (Claude) and Ollama local models.

Config via .env:
  LLM_PROVIDER=anthropic      # or: ollama
  ANTHROPIC_API_KEY=sk-ant-...
  OLLAMA_BASE_URL=http://localhost:11434   # default
  OLLAMA_MODEL=llama3.2                   # any model pulled in Ollama
"""
import json
import os
import re

import httpx
from dotenv import load_dotenv

load_dotenv()

_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
_OLLAMA_TIMEOUT_S = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))
_OLLAMA_THINKING_BUDGET = int(os.getenv("OLLAMA_THINKING_BUDGET", "512"))
_CLAUDE_MODEL = "claude-sonnet-4-6"


def is_llm_available() -> bool:
    if _PROVIDER == "anthropic":
        return bool(_ANTHROPIC_KEY) and not _ANTHROPIC_KEY.startswith("your_")
    if _PROVIDER == "ollama":
        return True  # optimistically true; failure detected at call time
    return False


async def call_llm(
    system: str,
    user_prompt: str,
    max_tokens: int = 1024,
    model: str | None = None,
    force_no_think: bool = False,
) -> str:
    """
    Call the configured LLM and return the raw text response.
    Raises on any failure so the caller can decide how to handle it.
    """
    if _PROVIDER == "ollama":
        return await _call_ollama(
            system,
            user_prompt,
            max_tokens,
            model=model,
            force_no_think=force_no_think,
        )
    return await _call_anthropic(system, user_prompt, max_tokens)


# ── Anthropic ────────────────────────────────────────────────────────────────

async def _call_anthropic(system: str, user_prompt: str, max_tokens: int) -> str:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=_ANTHROPIC_KEY)
    resp = await client.messages.create(
        model=_CLAUDE_MODEL,
        max_tokens=max_tokens,
        # Cache the large system prompt — saves cost on repeated calls
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_prompt}],
    )
    return resp.content[0].text


# ── Ollama ───────────────────────────────────────────────────────────────────

# Models that use <think>…</think> reasoning blocks before their answer.
# The block is stripped; only the text after it is returned.
_THINKING_MODELS = ("qwen3", "deepseek-r1", "qwq", "marco-o1")

def _is_thinking_model(name: str) -> bool:
    n = name.lower()
    return any(n.startswith(prefix) for prefix in _THINKING_MODELS)


async def _call_ollama(
    system: str,
    user_prompt: str,
    max_tokens: int,
    model: str | None = None,
    force_no_think: bool = False,
) -> str:
    model_name = model or _OLLAMA_MODEL
    # Thinking models (qwen3, deepseek-r1, …) emit thinking tokens that count
    # against num_predict before the actual answer is generated.
    # Ollama surfaces these in message.thinking (separate from message.content).
    thinking = _is_thinking_model(model_name) and not force_no_think
    # Give thinking models some reasoning headroom, but keep local calls bounded.
    # Non-thinking models use max_tokens directly.
    num_predict = (_OLLAMA_THINKING_BUDGET + max_tokens) if thinking else max_tokens

    payload: dict = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"num_predict": num_predict, "temperature": 0.1},
    }
    # format:"json" suppresses thinking output on some models — skip it for thinkers
    if not thinking:
        payload["format"] = "json"
    if force_no_think:
        payload["think"] = False

    timeout = httpx.Timeout(_OLLAMA_TIMEOUT_S, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{_OLLAMA_BASE}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.ReadTimeout as exc:
        raise TimeoutError(
            f"Ollama model {model_name!r} did not finish within "
            f"{_OLLAMA_TIMEOUT_S:.0f}s. Try a faster model, increase "
            "OLLAMA_TIMEOUT_SECONDS, or disable LLM explanations."
        ) from exc

    msg = data.get("message", {})
        # For thinking models Ollama puts the answer in message.content and
        # the reasoning in message.thinking (already separated — no stripping needed).
        # For non-thinking models content holds the full response.
    content = msg.get("content") or data.get("response") or ""
    content = content.strip()

    if not content:
        done_reason = data.get("done_reason", "unknown")
        thinking_preview = str(msg.get("thinking", ""))[:120]
        raise ValueError(
            f"Empty content from Ollama model {model_name!r} "
            f"(done_reason={done_reason!r}). "
            f"Thinking preview: {thinking_preview!r}. "
            f"Try increasing max_tokens or check the model."
        )

        # Still strip think tags in case an older Ollama version embeds them in content
    return _strip_thinking(content)


def _strip_thinking(text: str) -> str:
    """Remove <think>…</think> reasoning blocks emitted by thinking models."""
    import re
    # Strip the entire think block (may span many lines)
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()


# ── JSON parsing helper (shared) ─────────────────────────────────────────────

def parse_llm_json(text: str) -> dict:
    """Strip optional markdown fences / think blocks and parse JSON."""
    text = _strip_thinking(text).strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
    text = text.strip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = _repair_json_text(text)
        return json.loads(repaired)


def _repair_json_text(text: str) -> str:
    """Repair common LLM JSON issues without changing valid JSON."""
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    # Some local models emit invalid backslash escapes, especially bad \u forms.
    # Valid JSON escapes are: \" \\ \/ \b \f \n \r \t and \u1234.
    return re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r"\\\\", text)
