"""
Startup script: runs migrations, seeds data, then launches uvicorn.
Using Python avoids Windows CRLF line-ending issues with shell scripts.
"""
import asyncio
import glob
import os
import sys

# Force line-buffered stdout so Railway captures every print() immediately,
# even though the process is replaced by os.execvp() at the end.
sys.stdout.reconfigure(line_buffering=True)


def log(msg: str):
    print(msg, flush=True)


async def run_migrations(db_url: str):
    import asyncpg
    # asyncpg needs plain postgresql:// not postgresql+asyncpg://
    url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgres://", "postgresql://")
    log("▶ Connecting to database...")
    conn = await asyncpg.connect(url)
    files = sorted(glob.glob("db/migrations/*.sql"))
    log(f"▶ Running {len(files)} migration files...")
    for f in files:
        name = os.path.basename(f)
        try:
            # Explicit transaction so a failure in one file (e.g. 007 creating
            # indexes on a not-yet-existing table) is fully rolled back and the
            # connection is left in a clean state for the next migration.
            async with conn.transaction():
                await conn.execute(open(f).read())
            log(f"  ✅ {name}")
        except Exception as e:
            log(f"  ⚠️  {name}: {e}")
    await conn.close()
    log("▶ Migrations complete.")


def run_seeds():
    import subprocess
    seeds = [
        "scripts.seed_competitors",
        "scripts.seed_solutions_techs",
        "scripts.seed_competitors_solutions",
        "scripts.seed_competitors_remaining",
        "scripts.seed_cloud_competitors",
        "scripts.seed_oem_sourcing",
        "scripts.seed_tech_shares_complete",
    ]
    log(f"▶ Running {len(seeds)} seed scripts...")
    for seed in seeds:
        result = subprocess.run(
            [sys.executable, "-m", seed],
            capture_output=True, text=True, timeout=300
        )
        last_line = (result.stdout + result.stderr).strip().split("\n")[-1]
        log(f"  {'✅' if result.returncode == 0 else '⚠️ '} {seed.split('.')[-1]}: {last_line}")
    log("▶ Seeding complete.")


if __name__ == "__main__":
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        log("ERROR: DATABASE_URL not set — skipping migrations")
    else:
        asyncio.run(run_migrations(db_url))
        run_seeds()

    # Flush stdout before replacing the process — buffered prints are lost on execvp
    sys.stdout.flush()

    # Hand off to uvicorn
    port = os.environ.get("PORT", "8001")
    log(f"▶ Starting uvicorn on port {port}...")
    os.execvp(sys.executable, [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", port])
