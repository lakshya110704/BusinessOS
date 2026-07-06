"""Registry of pre-approved WhatsApp message templates.

WhatsApp requires templates to be created and APPROVED in the Meta dashboard
before they can be sent (used to (re)open a conversation outside the 24h session
window). This maps our internal names to the approved template name + the ordered
params it expects, so callers reference a constant instead of hardcoding strings.

To add one: create + get it approved in Meta, then register it here.
"""
from __future__ import annotations

# Internal names → approved template config.
ORDER_CONFIRMATION = "order_confirmation"
PAYMENT_REMINDER = "payment_reminder"
DAILY_SUMMARY = "daily_summary"

TEMPLATES: dict[str, dict] = {
    ORDER_CONFIRMATION: {
        # e.g. "📦 {vendor} ka order: {qty} pieces, delivery {date}"
        "params": ["vendor_name", "quantity", "delivery_date"],
        "language": "en",
    },
    PAYMENT_REMINDER: {
        "params": ["contact_name", "amount", "due_date"],
        "language": "en",
    },
    DAILY_SUMMARY: {
        "params": ["summary_text"],
        "language": "en",
    },
}
