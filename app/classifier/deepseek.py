"""DeepSeek AI classifier — refines the rule-based decision with an LLM.

DeepSeek exposes an OpenAI-compatible API, so we reuse the openai SDK pointed at
DeepSeek's base URL. Returns None if no key is configured or the call fails, so
the caller can fall back to the rule-based result. Mock mode never needs a key.
"""
from __future__ import annotations

import json
import logging
import os

from ..models import Decision, Email

log = logging.getLogger("agent.deepseek")

VALID_PRIORITIES = {"HIGH", "MEDIUM", "LOW"}

SYSTEM_PROMPT = """You are an email triage assistant for a software company.
Read the email and decide whether it is IMPORTANT enough to alert a human.

Flag as important: client complaints or urgent customer requests, payment or
billing failures, security alerts, and production outages. Treat newsletters,
promotions, social notifications, and routine automated mail as NOT important.

Respond with ONLY a JSON object, no markdown, with exactly these keys:
{
  "important": boolean,
  "priority": "HIGH" | "MEDIUM" | "LOW",
  "category": "SHORT_UPPER_SNAKE_CASE label e.g. PAYMENT_ISSUE, SERVER_DOWN, CLIENT_COMPLAINT, SECURITY_ALERT, URGENT_REQUEST, SPAM, NEWSLETTER",
  "reason": "one clear sentence justifying the decision"
}"""


def _client():
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return None
    # Imported lazily so the agent runs even if openai isn't needed/installed.
    from openai import OpenAI

    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )


def is_enabled() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY", "").strip())


def classify_deepseek(email: Email) -> Decision | None:
    client = _client()
    if client is None:
        return None

    user_content = (
        f"From: {email.sender}\n"
        f"Subject: {email.subject}\n\n"
        f"Body:\n{email.body[:4000]}"
    )

    try:
        resp = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0,
            response_format={"type": "json_object"},
            timeout=30,
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        return _normalise(data)
    except Exception as exc:  # network error, bad JSON, auth, etc.
        log.warning("DeepSeek classification failed, falling back to rules: %s", exc)
        return None


def _normalise(data: dict) -> Decision:
    priority = str(data.get("priority", "LOW")).upper()
    if priority not in VALID_PRIORITIES:
        priority = "LOW"
    important = bool(data.get("important", False))
    category = str(data.get("category", "GENERAL")).upper().replace(" ", "_")
    reason = str(data.get("reason", "Classified by DeepSeek.")).strip()
    return Decision(
        important=important,
        priority=priority,
        category=category or "GENERAL",
        reason=reason,
        source="deepseek",
    )
