"""Hybrid classifier: rules first, DeepSeek refinement when available.

Strategy
--------
1. Always compute the deterministic rule-based decision (the safety net).
2. If a DeepSeek key is configured, ask the LLM too. When it returns a valid
   decision, trust it (better natural-language understanding). Otherwise keep
   the rule result.

This gives full AI reasoning when a key is present and graceful, offline
behaviour when it is not.
"""
from __future__ import annotations

from ..models import Decision, Email
from .deepseek import classify_deepseek, is_enabled
from .rules import classify_rules


def classify(email: Email) -> Decision:
    rule_decision = classify_rules(email)

    if is_enabled():
        ai_decision = classify_deepseek(email)
        if ai_decision is not None:
            return ai_decision

    return rule_decision
