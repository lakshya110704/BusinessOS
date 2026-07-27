"""Batch-test the AI pipeline on REAL trader messages — a validation report.

Feed it a file of real WhatsApp messages and it runs each through classify → extract,
then prints an accuracy report (and an optional CSV). No Meta, no DB writes — this is
for answering "does the AI actually work on real Hindi/Hinglish orders?" before you
build the live product.

Input formats (auto-detected):
- .txt  : a WhatsApp chat export, OR one message per line
- .json : a list of message strings

Usage:
    python scripts/batch_test_messages.py trader_chat.txt
    python scripts/batch_test_messages.py messages.txt --out report.csv --concurrency 5

How to get input: in WhatsApp, open the trader's chat → ⋮ / contact → Export chat →
"Without media" → save the .txt and pass it here.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Make `app` importable when run as `python scripts/batch_test_messages.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.core.entity_extractor import extract  # noqa: E402
from app.core.intent_classifier import classify  # noqa: E402

# WhatsApp export line formats → capture the message body after "Sender:".
_ANDROID = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}\s*(?:[AaPp][Mm])?\s+-\s+[^:]+:\s+(.*)$")
_IOS = re.compile(r"^\[\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp][Mm])?\]\s+[^:]+:\s+(.*)$")
_SKIP = ("<Media omitted>", "This message was deleted", "Messages and calls are end-to-end")


def load_messages(path: Path) -> list:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return [str(m).strip() for m in json.loads(text) if str(m).strip()]

    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    bodies, matched = [], 0
    for ln in lines:
        m = _ANDROID.match(ln) or _IOS.match(ln)
        if m:
            bodies.append(m.group(1).strip())
            matched += 1
    # Looks like an export → use parsed bodies (skip media/system lines); else raw lines.
    source = bodies if matched >= max(3, len(lines) * 0.3) else [ln.strip() for ln in lines]
    return [b for b in source if b and not any(b.startswith(s) for s in _SKIP)]


async def _analyze(message: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        intent = await classify(message)
        entities = None
        if intent.intent != "unknown":
            entities = await extract(message, intent=intent.intent)
        return {
            "message": message,
            "intent": intent.intent,
            "confidence": round(intent.confidence, 2),
            "escalate": intent.escalate,
            "quantity": entities.quantity if entities else None,
            "unit": entities.unit if entities else None,
            "amount": entities.amount if entities else None,
            "delivery_date": entities.delivery_date if entities else None,
            "payment_terms": entities.payment_terms if entities else None,
        }


async def run(args) -> int:
    messages = load_messages(Path(args.file))
    if not messages:
        print("No messages found in file.")
        return 1
    print(f"Loaded {len(messages)} messages — running pipeline (concurrency {args.concurrency})…\n")

    sem = asyncio.Semaphore(args.concurrency)
    rows = await asyncio.gather(*[_analyze(m, sem) for m in messages])

    print("=== per message ===")
    for r in rows:
        flag = "⚠ " if r["escalate"] else "  "
        qty = f"qty={r['quantity']}" if r["quantity"] is not None else ""
        print(f"  {flag}{r['intent']:15} {r['confidence']:.2f}  {qty:9} | {r['message'][:50]}")

    n = len(rows)
    intents = Counter(r["intent"] for r in rows)
    escalated = sum(1 for r in rows if r["escalate"])
    orders = intents.get("order_placed", 0)
    orders_with_qty = sum(1 for r in rows if r["intent"] == "order_placed" and r["quantity"])
    avg_conf = sum(r["confidence"] for r in rows) / n

    print("\n=== summary ===")
    print(f"  total messages          : {n}")
    for k, v in intents.most_common():
        print(f"  {k:22}: {v}  ({v / n:.0%})")
    print(f"  avg intent confidence   : {avg_conf:.2f}")
    print(f"  escalated (uncertain)   : {escalated}  ({escalated / n:.0%})")
    if orders:
        print(f"  orders w/ quantity found: {orders_with_qty}/{orders}  ({orders_with_qty / orders:.0%})")

    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nCSV report written → {args.out}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help=".txt (WhatsApp export or one message per line) or .json list")
    ap.add_argument("--out", help="write a CSV report to this path")
    ap.add_argument("--concurrency", type=int, default=5)
    sys.exit(asyncio.run(run(ap.parse_args())))


if __name__ == "__main__":
    main()
