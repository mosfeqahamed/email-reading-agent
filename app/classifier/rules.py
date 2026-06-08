"""Rule-based classifier — the reliable baseline.

Runs with zero credentials, so mock mode works fully offline. Scores an email
across weighted signal groups, then maps the score to a priority and category.
This is the deterministic floor under the (optional) DeepSeek layer.
"""
from __future__ import annotations

import re

from ..models import Decision, Email

# Each category carries keyword signals and a base weight. Order matters only
# for category labelling — scoring sums every group that matches.
SIGNALS: list[dict] = [
    {
        "category": "PAYMENT_ISSUE",
        "weight": 5,
        "keywords": [
            "payment failed", "payment declined", "billing", "invoice",
            "could not be charged", "card declined", "refund", "overdue",
            "past due", "subscription suspended", "account suspended",
            "update your payment", "chargeback", "dispute the charge",
        ],
    },
    {
        "category": "SERVER_DOWN",
        "weight": 5,
        "keywords": [
            "is down", "outage", "500 error", "503", "downtime", "not responding",
            "cannot log in", "can't log in", "service interruption", "alert",
            "incident", "error rate", "pagerduty", "production api", "spiking",
        ],
    },
    {
        "category": "CLIENT_COMPLAINT",
        "weight": 4,
        "keywords": [
            "disappointed", "complaint", "cancelling", "cancel my", "unacceptable",
            "no one has replied", "nobody has replied", "still waiting",
            "frustrated", "angry", "leaving a review", "want a refund",
            "three times", "deleted my data",
        ],
    },
    {
        "category": "URGENT_REQUEST",
        "weight": 4,
        "keywords": [
            "urgent", "asap", "as soon as possible", "immediately", "today",
            "right away", "critical", "blocking", "deadline", "time sensitive",
            "jump on a call", "before contract", "renewal",
        ],
    },
    {
        "category": "SECURITY_ALERT",
        "weight": 4,
        "keywords": [
            "unusual sign-in", "unusual login", "suspicious", "password reset",
            "secure your account", "unauthorized", "breach", "blocked a sign-in",
            "new device",
        ],
    },
]

# Signals that strongly push an email toward "not important".
LOW_PRIORITY_SIGNALS = {
    "category": "SUBSCRIPTION",
    "keywords": [
        "unsubscribe", "newsletter", "digest", "weekly", "promotions", "% off",
        "sale", "deal", "discount", "stories for you", "appeared in",
        "searches this week", "upgrade to premium", "happy reading",
        "top launches", "limited stock",
    ],
}

NOREPLY_RE = re.compile(r"(no[-_.]?reply|newsletter|promotions?|notifications?)@", re.I)


def _count_hits(text: str, keywords: list[str]) -> int:
    return sum(1 for kw in keywords if kw in text)


def classify_rules(email: Email) -> Decision:
    text = f"{email.subject}\n{email.body}".lower()
    sender = email.sender.lower()

    # Score every important-signal group independently. The overall score drives
    # the importance/priority decision; the single highest-scoring category wins
    # the label (more keyword hits beats a higher base weight on a one-off match).
    score = 0
    best_category = "GENERAL"
    best_category_score = 0
    for group in SIGNALS:
        hits = _count_hits(text, group["keywords"])
        if hits:
            contribution = group["weight"] + (hits - 1)
            score += contribution
            if contribution > best_category_score:
                best_category_score = contribution
                best_category = group["category"]

    # Apply low-priority / noise signals.
    noise_hits = _count_hits(text, LOW_PRIORITY_SIGNALS["keywords"])
    is_noreply = bool(NOREPLY_RE.search(sender))
    if noise_hits:
        score -= 3 * noise_hits
    if is_noreply:
        score -= 2

    # Map score → decision.
    if score >= 5:
        priority = "HIGH"
        important = True
    elif score >= 2:
        priority = "MEDIUM"
        important = True
    elif score >= 1:
        priority = "LOW"
        important = True
    else:
        # Nothing important fired (or noise cancelled it out).
        priority = "LOW"
        important = False

    if not important:
        category = "SPAM" if (noise_hits or is_noreply) else "GENERAL"
        reason = (
            "No urgent, billing, outage, or complaint signals detected; "
            "looks like an automated, promotional, or low-priority message."
        )
    else:
        category = best_category
        reason = _build_reason(best_category, priority, noise_hits)

    return Decision(
        important=important,
        priority=priority,
        category=category,
        reason=reason,
        source="rules",
    )


def _build_reason(category: str, priority: str, noise_hits: int) -> str:
    base = {
        "PAYMENT_ISSUE": "Mentions a billing or payment failure that needs a quick response.",
        "SERVER_DOWN": "Reports a service outage or system failure affecting users.",
        "CLIENT_COMPLAINT": "Reads as a customer complaint or churn risk requiring attention.",
        "URGENT_REQUEST": "Contains time-sensitive language signalling an urgent request.",
        "SECURITY_ALERT": "Flags a possible security or account-access concern.",
        "GENERAL": "Matched importance signals worth surfacing.",
    }.get(category, "Matched importance signals worth surfacing.")
    return f"{base} (rule-based {priority} priority)"
