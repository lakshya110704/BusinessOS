"""Interactive CLI to register a new business in the `businesses` table.

Usage:
    python scripts/onboard_business.py

Prompts for the owner + WhatsApp details and inserts an active business row.
"""
import asyncio

from dotenv import load_dotenv

load_dotenv()

from app.db.supabase_client import get_supabase  # noqa: E402
from app.utils.phone import normalize_phone  # noqa: E402


def _ask(label: str, required: bool = True) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value or not required:
            return value
        print("  (required)")


async def main() -> int:
    print("=== Onboard a new BusinessOS business ===")
    owner_name = _ask("Owner name")
    try:
        phone = normalize_phone(_ask("Owner WhatsApp number (+91…)"))
    except ValueError as exc:
        print(f"✗ {exc}")
        return 1
    business_name = _ask("Business name")
    vertical = _ask("Vertical (textile/pharma/fmcg…)", required=False) or None
    city = _ask("City", required=False) or None
    phone_number_id = _ask("WhatsApp phone_number_id (from Meta)", required=False) or None

    client = await get_supabase()
    row = (await client.table("businesses").insert({
        "owner_name": owner_name,
        "phone_number": phone,
        "business_name": business_name,
        "vertical": vertical,
        "city": city,
        "whatsapp_phone_number_id": phone_number_id,
        "is_active": True,
    }).execute()).data[0]

    print(f"\n✓ Business created: {row['id']}  ({business_name}, owner {phone})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
