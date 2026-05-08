"""LLM Health Check — tests all 4 models used by the platform.

Run from backend/ directory (conda intel env):
    python debug_gemini.py
"""
import asyncio
import os
import sys
import time

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.path.insert(0, os.path.dirname(__file__))

from config import settings

PROBE = "Reply with exactly ONE word: Ready"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(label, latency_ms, reply):
    snippet = reply[:60].replace("\n", " ")
    print(f"  {GREEN}✓ {label:<28}{RESET}  {latency_ms:>5}ms  {CYAN}{snippet}{RESET}")

def fail(label, error):
    print(f"  {RED}✗ {label:<28}{RESET}  ERROR: {error}")

async def test_claude(svc):
    label = f"Claude ({settings.primary_model})"
    try:
        t0 = time.time()
        r = await svc.call_claude(
            messages=[{"role": "user", "content": PROBE}],
            max_tokens=20,
        )
        ok(label, int((time.time()-t0)*1000), r["content"])
    except Exception as e:
        fail(label, e)

async def test_gpt52(svc):
    label = f"GPT-5.2 ({settings.gpt52_deployment})"
    try:
        t0 = time.time()
        r = await svc.call_gpt52(PROBE, max_tokens=20)
        ok(label, int((time.time()-t0)*1000), r["content"])
    except Exception as e:
        fail(label, e)

async def test_grok4(svc):
    label = f"Grok-4 ({settings.grok_deployment})"
    try:
        t0 = time.time()
        r = await svc.call_grok4(PROBE, max_tokens=20)
        ok(label, int((time.time()-t0)*1000), r["content"])
    except Exception as e:
        fail(label, e)

async def test_gemini(svc):
    label = f"Gemini 2.5 Pro ({settings.gemini_deployment})"
    try:
        t0 = time.time()
        r = await svc.call_gemini25(PROBE, max_tokens=8000)
        ok(label, int((time.time()-t0)*1000), r["content"])
    except Exception as e:
        fail(label, e)

async def main():
    # Import here so the singleton is created after sys.path is set
    from services.llm_service import llm as svc

    print(f"\n{BOLD}{'═'*60}")
    print(f"  LLM Health Check — Mobility Intelligence Platform")
    print(f"{'═'*60}{RESET}")
    print(f"  LLM Farm:   {settings.llm_farm_base_url}")
    print(f"  Grok base:  {settings.grok_base_url}")
    print(f"{'─'*60}\n")

    # Run all 4 in parallel — same as validation_agent does
    await asyncio.gather(
        test_claude(svc),
        test_gpt52(svc),
        test_grok4(svc),
        test_gemini(svc),
        return_exceptions=False,
    )

    await svc.close()
    print(f"\n{BOLD}{'─'*60}{RESET}\n")

asyncio.run(main())
