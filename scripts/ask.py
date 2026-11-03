"""Ask the owner assistant a question against the live DB (BOS-49 dev tool).

Usage: python scripts/ask.py "aaj ki sales kitni hui?"
Resolves the business automatically (the single active one).
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # repo root on path

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app.core.assistant import answer  # noqa: E402 — after load_dotenv
from app.db.repositories import business_repo  # noqa: E402


async def main() -> None:
    question = " ".join(sys.argv[1:]) or "aaj ki sales kitni hui?"
    businesses = await business_repo.get_active()
    if not businesses:
        sys.exit("No active business in DB — onboard one first.")
    biz = businesses[0]
    print(f"[{biz['business_name']}] Q: {question}")
    print("A:", await answer(biz["id"], question))


asyncio.run(main())
