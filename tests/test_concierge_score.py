"""Concierge call tester: scoring harness + audio conversion (offline, no API)."""
import asyncio
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import concierge_call_orders as cco  # noqa: E402

TRUTH = {"is_order": True, "payment_status": "credit",
         "items": [{"item": ["cheeni", "चीनी"], "quantity": 2, "unit": "kg"}]}


def result(items, is_order=True, status="credit", ok=True):
    return {"file": "c.m4a", "ok": ok, "transcript": "",
            "order": {"is_order": is_order, "items": items, "payment_status": status} if ok else None}


def test_perfect_match_passes_with_alias():
    s = cco.score_call(result([{"item": "चीनी", "quantity": "2", "unit": "KG"}]), TRUTH)
    assert s["full"] and s["found"] == 1


def test_wrong_quantity_and_extra_item_fail():
    s = cco.score_call(result([{"item": "cheeni", "quantity": "3", "unit": "kg"},
                               {"item": "maggi", "quantity": "1", "unit": "packet"}]), TRUTH)
    assert not s["full"] and s["found"] == 1 and s["qty_ok"] == 0 and s["extras"] == 1


def test_missed_item_and_wrong_payment_fail():
    s = cco.score_call(result([], status="paid"), TRUTH)
    assert not s["full"] and s["found"] == 0 and s["pay_ok"] is False


def test_non_order_scored_on_detection_only():
    assert cco.score_call(result([], is_order=False), {"is_order": False})["full"]
    assert not cco.score_call(result([], is_order=True), {"is_order": False})["full"]


def test_failed_processing_is_never_a_pass():
    assert not cco.score_call(result([], ok=False), {"is_order": False})["full"]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_unsupported_format_is_converted_and_supported_passes_through(tmp_path):
    src = ROOT / "tests" / "fixtures" / "sample_voice_notes" / "order.ogg"
    name, data = asyncio.run(cco.whisper_audio(src))
    assert name == "order.ogg" and data == src.read_bytes()

    aac = tmp_path / "call.aac"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(src), str(aac)], check=True)
    name, data = asyncio.run(cco.whisper_audio(aac))
    assert name == "call.mp3" and len(data) > 1000
