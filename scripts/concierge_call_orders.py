"""Concierge tester for the KIRANA pivot — turn a shop's call recordings into an order list.

Feed it a folder of phone-call recordings (the ones Android OEM dialers save), and it
runs each through transcribe (Whisper, Hindi) -> grocery-order extraction, then prints
the order list a shopkeeper would actually use (items / qty / flat / customer) plus an
accuracy report. NO app, NO hardware, NO telephony — this answers the two make-or-break
questions before you build anything:
  1. Does a real, noisy kirana call parse ACCURATELY enough to trust?
  2. Is the resulting order list something the shopkeeper would pay for?

How to get input: from the shopkeeper's phone, copy the "Call recordings" folder
(MIUI / One UI / ColorOS all save audio files — .m4a / .amr / .mp3) to your machine.

Usage:
    python scripts/concierge_call_orders.py /path/to/recordings
    python scripts/concierge_call_orders.py /path/to/recordings --out orders.csv --concurrency 4
    python scripts/concierge_call_orders.py one_call.m4a            # single file
    python scripts/concierge_call_orders.py /path/to/recordings --truth truth.json   # also score it

Scoring: write truth.json by listening to each call. Keyed by file name; "item" may be a
list of acceptable spellings (Whisper may print Devanagari, so give both). Omit quantity,
unit or payment_status to skip checking them. Non-orders only need "is_order": false.
    {
      "call1.m4a": {"is_order": true, "payment_status": "credit",
                    "items": [{"item": ["cheeni", "चीनी", "sugar"], "quantity": 2, "unit": "kg"}]},
      "call2.m4a": {"is_order": false}
    }
Anything not .flac/.m4a/.mp3/.mp4/.ogg/.wav/.webm (e.g. .amr, .3gp) is converted with ffmpeg first.

Note: this is a LOCAL validation tool run on your own data — it prints transcripts so
you can judge accuracy (unlike the production server, which never logs message content).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

# Make `app` importable when run as `python scripts/concierge_call_orders.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.ai.whisper import transcribe  # noqa: E402
from app.ai.openai_client import complete_json  # noqa: E402

AUDIO_EXT = {".mp3", ".m4a", ".wav", ".ogg", ".opus", ".mp4", ".mpeg", ".mpga",
             ".webm", ".aac", ".flac", ".amr", ".3gp"}
# Formats the Whisper API accepts as-is. OEM dialers often save .amr/.3gp (and some .aac/.opus),
# which it rejects, so anything else is converted to mp3 with ffmpeg first.
WHISPER_EXT = {".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".oga", ".ogg", ".wav", ".webm"}

EXTRACT_PROMPT = """You are reading a transcript of a phone call to a small Indian shop or trader
(kirana / general store / wholesaler / supplier). A customer is placing an order or discussing
payment. The language is Hindi / Hinglish, often with English words. Extract it as JSON.

Return EXACTLY this shape:
{{
  "is_order": true/false,              // false if not an order (wrong number, chit-chat)
  "items": [ {{"item": "...", "quantity": "...", "unit": "..."}} ],  // unit like kg, packet, dozen, bottle, piece; "" if unspecified
  "customer_name": "",                 // name if mentioned, else ""
  "delivery_location": "",             // flat/house/shop no. or landmark, e.g. "Flat 301, B wing"
  "amount": null,                      // total order value in rupees as a NUMBER if stated/derivable, else null
  "payment_note": "",                  // what was said about payment: "cash", "paytm/upi", "add to monthly / udhaar", "paid", "pay later" — else ""
  "payment_status": "unknown",         // one of: "paid" | "credit" (owes / monthly / baad mein) | "unknown"
  "confidence": 0.0,                   // 0-1: how sure you are the extraction is correct & complete
  "notes": ""                          // anything ambiguous the shopkeeper should double-check
}}

Transcript:
\"\"\"{transcript}\"\"\"
"""


async def whisper_audio(path: Path) -> tuple[str, bytes]:
    """(filename, bytes) in a format Whisper accepts, converting via ffmpeg when needed."""
    if path.suffix.lower() in WHISPER_EXT:
        return path.name, path.read_bytes()
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "mp3", "pipe:1",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except FileNotFoundError:
        raise RuntimeError(f"{path.suffix} needs ffmpeg to convert (brew install ffmpeg)") from None
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0 or not stdout:
        raise RuntimeError(f"ffmpeg could not convert {path.name}: {stderr.decode(errors='ignore')[:100]}")
    return path.stem + ".mp3", stdout


async def process(path: Path, sem: asyncio.Semaphore) -> dict:
    out = {"file": path.name, "ok": False, "transcript": "", "order": None, "error": ""}
    async with sem:
        try:
            filename, audio = await whisper_audio(path)
            transcript = await transcribe(audio, filename=filename, language="hi")
            out["transcript"] = transcript.strip()
            if not out["transcript"]:
                out["error"] = "empty transcript"
                return out
            order = await complete_json(EXTRACT_PROMPT.format(transcript=out["transcript"]))
            out["order"] = order
            out["ok"] = True
        except Exception as exc:  # noqa: BLE001 — per-file resilience; report and move on
            out["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return out


def gather_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in AUDIO_EXT)


def fmt_items(items: list) -> str:
    if not items:
        return "(no items parsed)"
    parts = []
    for it in items:
        q = (str(it.get("quantity", "")) + " " + str(it.get("unit", ""))).strip()
        parts.append((q + " " + str(it.get("item", ""))).strip() if q else str(it.get("item", "")))
    return ", ".join(parts)


def print_report(results: list[dict]) -> None:
    orders = [r for r in results if r["ok"] and r["order"] and r["order"].get("is_order")]
    failed = [r for r in results if not r["ok"]]
    not_order = [r for r in results if r["ok"] and r["order"] and not r["order"].get("is_order")]

    print("\n" + "=" * 68)
    print("ORDER LIST  (what the shopkeeper would see)")
    print("=" * 68)
    for i, r in enumerate(orders, 1):
        o = r["order"]
        conf = float(o.get("confidence") or 0)
        flag = "  ⚠ CHECK" if conf < 0.70 else ""
        loc = o.get("delivery_location") or "?"
        who = o.get("customer_name") or "?"
        print(f"\n{i}. {loc}  ·  {who}{flag}   [{r['file']}]")
        print(f"   {fmt_items(o.get('items') or [])}")
        if o.get("payment_note"):
            print(f"   payment: {o['payment_note']}")
        if o.get("notes"):
            print(f"   note: {o['notes']}")
        # show the transcript so YOU can judge whether the extraction is right
        print(f"   heard: \"{r['transcript'][:160]}\"")

    print("\n" + "=" * 68)
    print("ACCURACY REPORT  (judge these yourself against the 'heard' lines)")
    print("=" * 68)
    n = len(results)
    with_items = [r for r in orders if (r["order"].get("items") or [])]
    confs = [float(r["order"].get("confidence") or 0) for r in orders]
    loc_found = [r for r in orders if r["order"].get("delivery_location")]
    avg = sum(confs) / len(confs) if confs else 0
    low = [r for r in orders if float(r["order"].get("confidence") or 0) < 0.70]

    def pct(a, b):
        return f"{(100*a/b):.0f}%" if b else "—"

    print(f"  recordings processed      : {n}")
    print(f"  detected as orders        : {len(orders)}  ({pct(len(orders), n)})")
    print(f"  not an order / chit-chat  : {len(not_order)}")
    print(f"  failed to process         : {len(failed)}")
    print(f"  orders with ≥1 item parsed: {len(with_items)}/{len(orders)}  ({pct(len(with_items), len(orders))})")
    print(f"  orders with delivery loc  : {len(loc_found)}/{len(orders)}  ({pct(len(loc_found), len(orders))})")
    print(f"  avg confidence            : {avg:.2f}")
    print(f"  low-confidence (<0.70)    : {len(low)}  ← the ones he'd have to double-check")
    if failed:
        print("\n  failures (.amr/.3gp/.aac/.opus are auto-converted, which needs ffmpeg installed):")
        for r in failed:
            print(f"    - {r['file']}: {r['error']}")
    print("\n  The number that decides the pivot: of the orders above, how many are")
    print("  FULLY correct (right items, qty, flat)? If he can trust the list without")
    print("  re-listening, you have a product. If not, capture isn't ready yet.\n")


def _customer_key(o: dict) -> str:
    return (o.get("customer_name") or "").strip() or (o.get("delivery_location") or "").strip() or "(unidentified)"


def print_khata(results: list[dict]) -> None:
    """Roll the extracted orders up into a per-customer khata — the actual product view:
    who ordered, how much, and who still owes (udhaar)."""
    orders = [r["order"] for r in results if r["ok"] and r["order"] and r["order"].get("is_order")]
    if not orders:
        return
    book: dict[str, dict] = {}
    for o in orders:
        k = _customer_key(o)
        b = book.setdefault(k, {"orders": 0, "amount": 0.0, "amount_known": False,
                                "credit_amt": 0.0, "credit_orders": 0, "items": []})
        b["orders"] += 1
        amt = o.get("amount")
        try:
            amt = float(amt) if amt is not None else None
        except (TypeError, ValueError):
            amt = None
        if amt is not None:
            b["amount"] += amt
            b["amount_known"] = True
        status = (o.get("payment_status") or "unknown").lower()
        if status == "credit":
            b["credit_orders"] += 1
            if amt is not None:
                b["credit_amt"] += amt
        b["items"].extend(i.get("item", "") for i in (o.get("items") or []))

    print("\n" + "=" * 68)
    print("KHATA  (auto-built per customer — this is the product)")
    print("=" * 68)
    total_outstanding = 0.0
    any_amt = any(b["amount_known"] for b in book.values())
    for who, b in sorted(book.items(), key=lambda kv: kv[1]["credit_amt"], reverse=True):
        amt = f"₹{b['amount']:,.0f}" if b["amount_known"] else "₹?"
        line = f"\n  {who}\n    {b['orders']} order(s) · {amt} ordered"
        if b["credit_orders"]:
            owed = f"₹{b['credit_amt']:,.0f}" if b["credit_amt"] else "amount unclear"
            line += f"  ·  ⚠ UDHAAR: {b['credit_orders']} unpaid ({owed})"
            total_outstanding += b["credit_amt"]
        print(line)
        uniq = [i for i in dict.fromkeys(b["items"]) if i][:8]
        if uniq:
            print(f"    usually: {', '.join(uniq)}")
    print("\n  " + "-" * 50)
    if any_amt:
        print(f"  TOTAL OUTSTANDING (udhaar to collect): ₹{total_outstanding:,.0f}")
    else:
        print("  (No rupee amounts were stated on these calls — so outstanding can't be")
        print("   totalled. In the real product, prices come from the shop's rate list.)")
    print("  This is what a shopkeeper would pay for: 'who owes me, built automatically.'\n")


def write_csv(results: list[dict], out: Path) -> None:
    rows = [r for r in results if r["ok"] and r["order"] and r["order"].get("is_order")]
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "customer", "delivery_location", "items", "amount", "payment_status",
                    "payment_note", "confidence", "notes", "transcript"])
        for r in rows:
            o = r["order"]
            w.writerow([r["file"], o.get("customer_name", ""), o.get("delivery_location", ""),
                        fmt_items(o.get("items") or []), o.get("amount", ""), o.get("payment_status", ""),
                        o.get("payment_note", ""), o.get("confidence", ""), o.get("notes", ""), r["transcript"]])
    print(f"  wrote {len(rows)} orders → {out}")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _name_match(got, names) -> bool:
    # shortcut: substring match either way, so a wrong-but-overlapping item can pass; tighten if scores look too kind.
    got = str(got or "").strip().lower()
    return bool(got) and any(n in got or got in n for n in names)


def score_call(r: dict, truth: dict) -> dict:
    """Compare one extracted result with what was really said. Counts only; no judgement calls."""
    o = r["order"] if r["ok"] and r["order"] else {}
    s = {"order_ok": r["ok"] and bool(o.get("is_order")) == truth["is_order"],
         "n_items": 0, "found": 0, "qty_ok": 0, "unit_ok": 0, "extras": 0, "pay_ok": None}
    if truth["is_order"]:
        got = list(o.get("items") or [])
        for t in truth.get("items", []):
            s["n_items"] += 1
            names = [n.strip().lower() for n in ([t["item"]] if isinstance(t["item"], str) else t["item"]) if n.strip()]
            m = next((g for g in got if _name_match(g.get("item"), names)), None)
            if m is None:
                continue
            got.remove(m)
            s["found"] += 1
            s["qty_ok"] += _num(m.get("quantity")) == _num(t.get("quantity"))
            s["unit_ok"] += (m.get("unit") or "").strip().lower() == (t.get("unit") or "").strip().lower()
        s["extras"] = len(got)
        if truth.get("payment_status"):
            s["pay_ok"] = (o.get("payment_status") or "unknown").lower() == truth["payment_status"].lower()
    s["full"] = (s["order_ok"] and s["found"] == s["n_items"] == s["qty_ok"] == s["unit_ok"]
                 and s["extras"] == 0 and s["pay_ok"] is not False)
    return s


def print_scores(results: list[dict], truth: dict) -> None:
    by_file = {r["file"]: r for r in results}
    scored = [(name, by_file[name], score_call(by_file[name], t)) for name, t in truth.items() if name in by_file]
    missing = [n for n in truth if n not in by_file]
    print("=" * 68)
    print("SCORE vs WHAT WAS ACTUALLY SAID  (from your truth file)")
    print("=" * 68)
    for name, r, s in scored:
        if s["full"]:
            print(f"  PASS  {name}")
            continue
        why = []
        if not s["order_ok"]:
            why.append("failed to process" if not r["ok"] else "order/non-order detected wrongly")
        if s["found"] < s["n_items"]:
            why.append(f"{s['n_items'] - s['found']} item(s) missed")
        if s["found"] > s["qty_ok"]:
            why.append(f"{s['found'] - s['qty_ok']} wrong qty")
        if s["found"] > s["unit_ok"]:
            why.append(f"{s['found'] - s['unit_ok']} wrong unit")
        if s["extras"]:
            why.append(f"{s['extras']} extra item(s)")
        if s["pay_ok"] is False:
            why.append("wrong payment status")
        print(f"  FAIL  {name}: {', '.join(why)}")
        print(f"        heard: \"{r['transcript'][:160]}\"")

    def pct(a, b):
        return f"{a}/{b} ({100 * a // b}%)" if b else "n/a"

    n = len(scored)
    items = sum(s["n_items"] for _, _, s in scored)
    found = sum(s["found"] for _, _, s in scored)
    paid = [s["pay_ok"] for _, _, s in scored if s["pay_ok"] is not None]
    print(f"\n  calls scored         : {n}")
    print(f"  order vs not-order   : {pct(sum(s['order_ok'] for _, _, s in scored), n)}")
    print(f"  items found          : {pct(found, items)}")
    print(f"  qty right (of found) : {pct(sum(s['qty_ok'] for _, _, s in scored), found)}")
    print(f"  unit right (of found): {pct(sum(s['unit_ok'] for _, _, s in scored), found)}")
    print(f"  extra items invented : {sum(s['extras'] for _, _, s in scored)}")
    print(f"  payment status right : {pct(sum(paid), len(paid))}")
    print(f"  FULLY correct calls  : {pct(sum(s['full'] for _, _, s in scored), n)}   <- the number that decides it")
    if missing:
        print(f"\n  in truth file but not run: {', '.join(missing)}")
    unscored = [r["file"] for r in results if r["file"] not in truth]
    if unscored:
        print(f"  run but not in truth file (not scored): {', '.join(unscored)}")
    print()


async def main() -> int:
    ap = argparse.ArgumentParser(description="Turn kirana call recordings into an order list (concierge validation).")
    ap.add_argument("path", help="folder of recordings, or a single audio file")
    ap.add_argument("--out", help="also write orders to this CSV")
    ap.add_argument("--truth", help="JSON of what was really said per file; scores the extraction (see docstring)")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    root = Path(args.path).expanduser()
    if not root.exists():
        print(f"✗ path not found: {root}")
        return 1
    truth = None
    if args.truth:  # load before any paid API call so a bad file fails fast
        try:
            truth = json.loads(Path(args.truth).expanduser().read_text(encoding="utf-8"))
            for name, t in truth.items():
                assert isinstance(t["is_order"], bool), "is_order must be true or false"
                for it in t.get("items", []):
                    assert it["item"], "each item needs an 'item' name"
        except (OSError, ValueError, KeyError, AssertionError, AttributeError) as exc:
            print(f"✗ bad truth file {args.truth}: {type(exc).__name__}: {exc}")
            return 1
    files = gather_files(root)
    if not files:
        print(f"✗ no audio files found under {root} (looked for: {', '.join(sorted(AUDIO_EXT))})")
        return 1

    print(f"Found {len(files)} recording(s) — transcribing + extracting (concurrency {args.concurrency})…")
    sem = asyncio.Semaphore(args.concurrency)
    results = await asyncio.gather(*(process(p, sem) for p in files))

    print_report(results)
    print_khata(results)
    if truth is not None:
        print_scores(results, truth)
    if args.out:
        write_csv(results, Path(args.out).expanduser())
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
