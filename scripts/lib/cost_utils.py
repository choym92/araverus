"""
Shared LLM cost tracking utilities for the news pipeline.

Single source of truth for Gemini / TTS pricing.
All prices: USD per 1M tokens (or 1M characters for TTS).
"""

# Prices as of Feb 2026 (Google official)
COST_PER_1M: dict[str, float] = {
    "gemini-2.5-pro-input": 1.25,
    "gemini-2.5-pro-output": 10.0,
    "gemini-2.5-pro-thinking": 3.75,
    "gemini-2.5-flash-input": 0.30,
    "gemini-2.5-flash-output": 2.50,
    "gemini-2.5-flash-lite-input": 0.10,
    "gemini-2.5-flash-lite-output": 0.40,
    "chirp3-hd-per-1m-chars": 16.0,
}


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str,
    thinking_tokens: int = 0,
) -> float:
    """Return estimated cost in USD for a single LLM call.

    Args:
        input_tokens: Prompt token count.
        output_tokens: Candidate (output) token count.
        model: Model name fragment — must contain 'pro', 'flash-lite', or 'flash'.
        thinking_tokens: Thinking token count (Pro only).
    """
    if "pro" in model:
        tag = "gemini-2.5-pro"
    elif "flash-lite" in model:
        tag = "gemini-2.5-flash-lite"
    elif "flash" in model:
        tag = "gemini-2.5-flash"
    else:
        tag = "gemini-2.5-flash-lite"  # safe fallback

    cost = input_tokens / 1e6 * COST_PER_1M[f"{tag}-input"]
    cost += output_tokens / 1e6 * COST_PER_1M[f"{tag}-output"]
    if thinking_tokens and "pro" in model:
        cost += thinking_tokens / 1e6 * COST_PER_1M["gemini-2.5-pro-thinking"]
    return cost


def print_cost_line(
    label: str,
    input_tokens: int,
    output_tokens: int,
    model: str,
    *,
    thinking_tokens: int = 0,
    calls: int | None = None,
) -> float:
    """Print a formatted cost line and return the cost in USD.

    Example output:
        Preprocess (Flash-Lite): in=12,345, out=6,789 (60 calls)
    """
    cost = estimate_cost(input_tokens, output_tokens, model, thinking_tokens)
    parts = f"{label}: in={input_tokens:,}, out={output_tokens:,}"
    if thinking_tokens:
        parts += f", think={thinking_tokens:,}"
    if calls is not None:
        parts += f" ({calls} calls)"
    print(parts)
    return cost
