"""model_router.py — Intelligent model selection based on query complexity."""
import re
import logging

logger = logging.getLogger("cost-router")

NOVA_LITE = "us.amazon.nova-lite-v1:0"    # $0.06/1M input
NOVA_PRO = "us.amazon.nova-pro-v1:0"      # $0.80/1M input

SIMPLE_PATTERNS = [
    r"^list\b", r"^show\b", r"^get\b", r"^what (is|are)\b",
    r"^status\b", r"^health\b", r"^count\b", r"^describe\b",
    r"^how many\b", r"^tell me about\b"
]

COMPLEX_PATTERNS = [
    r"diagnose", r"troubleshoot", r"why.*fail", r"root cause",
    r"fix\b", r"remediate", r"investigate", r"compare.*and",
    r"analyze", r"recommend", r"optimize", r"what should",
    r"step.by.step", r"full.*check"
]


def select_model(prompt: str) -> tuple:
    """Returns (model_id, reason, tier) based on query complexity."""
    prompt_lower = prompt.lower().strip()

    for pattern in COMPLEX_PATTERNS:
        if re.search(pattern, prompt_lower):
            return NOVA_PRO, "complex_reasoning", "pro"

    for pattern in SIMPLE_PATTERNS:
        if re.search(pattern, prompt_lower):
            return NOVA_LITE, "simple_query", "lite"

    if len(prompt) > 200:
        return NOVA_PRO, "long_prompt", "pro"

    return NOVA_LITE, "default_simple", "lite"
