"""
System instruction building functions.
"""

from typing import List


def build_system_instruction(
    base_instruction: str,
    business_instruction: str | None = None,
) -> str:
    """
    Combines the global guardrails with any business- or tenant-specific
    instructions. This lets multiple businesses share the same backend while
    customizing tone, offerings, and domain knowledge.
    """
    parts: List[str] = [base_instruction.strip()]
    if business_instruction:
        parts.append(
            "BUSINESS / TENANT SPECIFIC INSTRUCTIONS:\n"
            + business_instruction.strip()
        )
    return "\n\n".join(parts)
