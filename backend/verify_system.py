"""
SYSTEM VERIFICATION SCRIPT
Run: conda activate intel && cd backend && python verify_system.py
This checks every import, every module connection, and reports any issues.
"""

import sys
import os
import importlib
import traceback

# Ensure we're in the backend directory
if not os.path.exists("main.py"):
    print("ERROR: Run this from the backend/ directory")
    print("  cd mobility-intelligence/backend && python verify_system.py")
    sys.exit(1)

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

results = {"pass": [], "fail": []}

def check(name, func):
    try:
        func()
        results["pass"].append(name)
        print(f"  ✅ {name}")
    except Exception as e:
        results["fail"].append((name, str(e)))
        print(f"  ❌ {name}: {e}")

print("\n" + "="*60)
print("  MOBILITY INTELLIGENCE — SYSTEM VERIFICATION")
print("="*60)

# ── 1. DEPENDENCY IMPORTS ─────────────────────────────────
print("\n📦 Checking dependencies...")
check("fastapi", lambda: importlib.import_module("fastapi"))
check("uvicorn", lambda: importlib.import_module("uvicorn"))
check("pydantic", lambda: importlib.import_module("pydantic"))
check("pydantic_settings", lambda: importlib.import_module("pydantic_settings"))
check("httpx", lambda: importlib.import_module("httpx"))
check("asyncpg", lambda: importlib.import_module("asyncpg"))
check("sqlalchemy", lambda: importlib.import_module("sqlalchemy"))
check("sqlalchemy.ext.asyncio", lambda: importlib.import_module("sqlalchemy.ext.asyncio"))
check("redis", lambda: importlib.import_module("redis"))
check("bs4 (BeautifulSoup)", lambda: importlib.import_module("bs4"))
check("lxml", lambda: importlib.import_module("lxml"))
check("apscheduler", lambda: importlib.import_module("apscheduler"))
check("tenacity", lambda: importlib.import_module("tenacity"))
check("dotenv", lambda: importlib.import_module("dotenv"))

# ── 2. CONFIG MODULE ─────────────────────────────────────
print("\n⚙️  Checking config...")
check("config.py loads", lambda: importlib.import_module("config"))
def check_settings():
    from config import settings
    assert settings.primary_model == "claude-sonnet-4-6", f"Expected claude-sonnet-4-6, got {settings.primary_model}"
    assert settings.validator_model == "claude-haiku-4-5", f"Expected claude-haiku-4-5, got {settings.validator_model}"
    assert settings.auto_refresh_hours > 0
check("config.settings values", check_settings)

# ── 3. DATABASE MODULE ────────────────────────────────────
print("\n🗄️  Checking database modules...")
check("db.connection", lambda: importlib.import_module("db.connection"))
def check_db_exports():
    from db.connection import engine, async_session, get_db
    assert engine is not None
    assert async_session is not None
check("db exports (engine, async_session, get_db)", check_db_exports)

# ── 4. SERVICES ───────────────────────────────────────────
print("\n🔧 Checking services...")
check("services.llm_service", lambda: importlib.import_module("services.llm_service"))
def check_llm():
    from services.llm_service import llm, LLMService, PRICING
    assert isinstance(llm, LLMService)
    assert "claude-sonnet-4-6" in PRICING
    assert "claude-haiku-4-5" in PRICING
    assert "gpt-5-mini" in PRICING
    assert "text-embedding-3-small" in PRICING
check("llm_service exports (llm, PRICING)", check_llm)

check("services.cache_service", lambda: importlib.import_module("services.cache_service"))
def check_cache():
    from services.cache_service import CacheService
    c = CacheService()
    assert hasattr(c, "get")
    assert hasattr(c, "set")
    assert hasattr(c, "invalidate_pestel_cache")
check("CacheService methods", check_cache)

check("services.web_intelligence", lambda: importlib.import_module("services.web_intelligence"))
def check_web():
    from services.web_intelligence import WebIntelligenceService, NEWS_SOURCES
    assert len(NEWS_SOURCES) >= 5, f"Expected 5+ news sources, got {len(NEWS_SOURCES)}"
check("WebIntelligenceService + NEWS_SOURCES", check_web)

check("services.source_tracker", lambda: importlib.import_module("services.source_tracker"))
def check_tracker():
    from services.source_tracker import source_tracker
    assert hasattr(source_tracker, "create_source")
    assert hasattr(source_tracker, "get_source_trail")
check("source_tracker methods", check_tracker)

# ── 5. AGENT SYSTEM ───────────────────────────────────────
print("\n🤖 Checking agents...")
check("agents.prompts.system_context", lambda: importlib.import_module("agents.prompts.system_context"))
def check_prompts():
    from agents.prompts.system_context import (
        SYSTEM_CONTEXT, PESTEL_DISCOVERY_PROMPT,
        VALIDATION_PROMPT, TECH_ANALYSIS_PROMPT, PESTEL_DETAIL_PROMPT
    )
    assert len(SYSTEM_CONTEXT) > 2000, f"System context too short: {len(SYSTEM_CONTEXT)} chars"
    assert "{news_content}" in PESTEL_DISCOVERY_PROMPT
    assert "{data_point}" in VALIDATION_PROMPT
    assert "{segment}" in TECH_ANALYSIS_PROMPT
    assert "{factor_name}" in PESTEL_DETAIL_PROMPT
check("All prompts exported and templated", check_prompts)

check("agents.validation_agent", lambda: importlib.import_module("agents.validation_agent"))
def check_validator():
    from agents.validation_agent import validation_agent, ValidationAgent
    assert isinstance(validation_agent, ValidationAgent)
    assert hasattr(validation_agent, "validate_data_point")
    assert hasattr(validation_agent, "validate_batch")
    assert hasattr(validation_agent, "_compute_consensus")
check("ValidationAgent methods", check_validator)

check("agents.pestel_agent", lambda: importlib.import_module("agents.pestel_agent"))
def check_pestel():
    from agents.pestel_agent import pestel_agent, PESTELAgent
    assert isinstance(pestel_agent, PESTELAgent)
    assert hasattr(pestel_agent, "discover_factors")
    assert hasattr(pestel_agent, "filter_factors")
    assert hasattr(pestel_agent, "validate_factor_data")
    assert hasattr(pestel_agent, "generate_detail_analysis")
    assert hasattr(pestel_agent, "run_full_refresh")
check("PESTELAgent methods", check_pestel)

check("agents.orchestrator", lambda: importlib.import_module("agents.orchestrator"))
def check_orch():
    from agents.orchestrator import orchestrator, Orchestrator
    assert isinstance(orchestrator, Orchestrator)
    assert hasattr(orchestrator, "run_scheduled_refresh")
    assert hasattr(orchestrator, "get_pestel_analysis")
    assert hasattr(orchestrator, "get_tech_analysis")
check("Orchestrator methods", check_orch)

# ── 6. API ROUTES ─────────────────────────────────────────
print("\n🌐 Checking API routes...")
check("api.pestel", lambda: importlib.import_module("api.pestel"))
def check_pestel_api():
    from api.pestel import router
    routes = [r.path for r in router.routes]
    assert "/" in routes, f"Missing / route, got: {routes}"
    assert "/{factor_code}" in routes, f"Missing /:code route, got: {routes}"
check("PESTEL API routes (/, /{code})", check_pestel_api)

check("api.technology", lambda: importlib.import_module("api.technology"))
def check_tech_api():
    from api.technology import router
    routes = [r.path for r in router.routes]
    assert "/" in routes
    assert "/pillars" in routes
check("Tech API routes (/, /pillars)", check_tech_api)

check("api.analysis", lambda: importlib.import_module("api.analysis"))
def check_analysis_api():
    from api.analysis import router
    routes = [r.path for r in router.routes]
    assert "/pestel/{factor_code}" in routes
    assert "/tech/{tech_code}" in routes
    assert "/validation/{entity_type}/{entity_id}" in routes
check("Analysis API routes", check_analysis_api)

check("api.refresh", lambda: importlib.import_module("api.refresh"))
def check_refresh_api():
    from api.refresh import router
    routes = [r.path for r in router.routes]
    assert "/full" in routes
    assert "/cache/clear" in routes
    assert "/status" in routes
    assert "/logs" in routes
check("Refresh API routes", check_refresh_api)

# ── 7. MAIN APP ASSEMBLY ─────────────────────────────────
print("\n🚀 Checking main app assembly...")
def check_main():
    # This is the ultimate test — if main.py imports cleanly,
    # the entire dependency chain works
    from main import app
    from fastapi.testclient import TestClient
    # Verify all routers are registered
    route_paths = [r.path for r in app.routes]
    assert "/api/health" in route_paths, f"/api/health missing. Routes: {route_paths}"
    assert any("/api/pestel" in p for p in route_paths), "PESTEL routes missing"
    assert any("/api/techs" in p for p in route_paths), "Tech routes missing"
    assert any("/api/analysis" in p for p in route_paths), "Analysis routes missing"
    assert any("/api/refresh" in p for p in route_paths), "Refresh routes missing"
check("main.py app assembly + all routes registered", check_main)

# ── 8. SQL MIGRATION FILE ────────────────────────────────
print("\n📋 Checking SQL migration...")
def check_sql():
    with open("db/migrations/001_initial.sql") as f:
        sql = f.read()
    for table in ["sources", "pestel_factors", "technologies", "validation_logs", "refresh_logs", "analysis_cache"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql, f"Table {table} missing from migration"
check("001_initial.sql has all 6 tables", check_sql)

# ── 9. SEED SCRIPT ────────────────────────────────────────
print("\n🌱 Checking seed script...")
def check_seed():
    seed_path = os.path.join("..", "scripts", "seed_initial_data.py")
    assert os.path.exists(seed_path), f"Seed script not found at {seed_path}"
    with open(seed_path) as f:
        content = f.read()
    assert "seed_sources" in content
    assert "seed_pestel_factors" in content
    assert "seed_technologies" in content
    assert "ACMA FY2025" in content
check("seed_initial_data.py exists and has all seed functions", check_seed)

# ── FINAL REPORT ──────────────────────────────────────────
print("\n" + "="*60)
passed = len(results["pass"])
failed = len(results["fail"])
total = passed + failed
print(f"  RESULTS: {passed}/{total} checks passed")

if failed:
    print(f"\n  ❌ {failed} FAILURES:")
    for name, err in results["fail"]:
        print(f"     → {name}: {err}")
    print("\n  Fix these issues, then run this script again.")
else:
    print(f"\n  ✅ ALL {total} CHECKS PASSED — SYSTEM IS READY")
    print(f"\n  Next steps:")
    print(f"  1. Start Docker services:")
    print(f"     docker-compose up -d")
    print(f"  2. Seed baseline data:")
    print(f"     docker-compose exec api python scripts/seed_initial_data.py")
    print(f"  3. Start API server (for local dev without Docker):")
    print(f"     conda activate intel")
    print(f"     cd backend")
    print(f"     uvicorn main:app --reload --port 8000")
    print(f"  4. Open API docs:")
    print(f"     http://localhost:8000/docs")

print("="*60 + "\n")
