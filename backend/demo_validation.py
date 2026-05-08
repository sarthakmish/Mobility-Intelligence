"""
Quick demo: 4-model parallel validation on a single BYD data point.
Run with: python demo_validation.py
Outputs the full validation chain to the terminal for a screenshot.
"""
import asyncio
import logging

# Clean, readable log format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(message)s",
    datefmt="%H:%M:%S",
)
# Suppress httpx noise, keep the models we care about
logging.getLogger("httpx").setLevel(logging.WARNING)


async def run():
    from agents.validation_agent import validation_agent

    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║   4-MODEL PARALLEL VALIDATION DEMO — Mobility Intelligence Platform ║")
    print("║   Primary: Claude Sonnet 4.6                                        ║")
    print("║   Validators (parallel): GPT-5.2  │  Grok 4 Fast  │  Gemini 2.5 Pro║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print()
    print("  Data Point : BYD India EV market penetration FY2025")
    print("  Claim      : 3,468 units sold in 2024; targeting 10,000 units in 2025")
    print("  Source     : ET Auto / BYD India press release")
    print()
    print("  ── Running primary check (Sonnet 4.6) ... ──────────────────────────")
    print()

    result = await validation_agent.validate_data_point(
        data_point="BYD India EV sales FY2025",
        claimed_value="3,468 units (Jan-Dec 2024), targeting 10,000 units in 2025",
        context=(
            "BYD entered India premium EV segment with Seal and Atto 3. "
            "Expanding dealer network from 24 to 100+ touchpoints by end 2025. "
            "Competing with Tata Nexon EV and MG ZS EV in the sub-Rs 35L segment. "
            "Government PLI scheme supports domestic EV manufacturing, but import "
            "duties on CBU units remain at 100%+ which pressures BYD's pricing."
        ),
        source_cited="ET Auto, BYD India press release March 2025",
        entity_type="pestel_factor",
    )

    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║                        VALIDATION RESULT                            ║")
    print("╠══════════════════════════════════════════════════════════════════════╣")
    print(f"║  Data Point   : {result['data_point'][:54]:<54}║")
    print(f"║  Claim        : {result['claimed_value'][:54]:<54}║")
    print(f"║  Primary      : {result['primary_model'][:20]:<20} → {result['primary_verdict']:<10} ({result['primary_confidence']})  ║")
    print(f"║  Validators   : {result['validator_model'][:54]:<54}║")
    print(f"║  Validator ✓  : {result['validator_verdict']:<10} confidence                               ║")
    print(f"║  CONSENSUS    : {result['consensus']:<54}║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print()
    print("  Primary reasoning (truncated):")
    print(f"  {result['primary_reasoning'][:200]}...")
    print()


if __name__ == "__main__":
    asyncio.run(run())
