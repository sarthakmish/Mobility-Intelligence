#!/bin/sh
# ============================================================
# STARTUP SCRIPT — runs migrations then seeds, then starts app
# ============================================================
set -e

echo "▶ Running database migrations..."
python -c "
import asyncio, asyncpg, glob, os, sys

async def run():
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print('ERROR: DATABASE_URL not set')
        sys.exit(1)
    # asyncpg needs postgresql:// not postgresql+asyncpg://
    db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
    conn = await asyncpg.connect(db_url)
    files = sorted(glob.glob('db/migrations/*.sql'))
    for f in files:
        name = os.path.basename(f)
        try:
            await conn.execute(open(f).read())
            print(f'  ✅ {name}')
        except Exception as e:
            print(f'  ⚠️  {name}: {e}')
    await conn.close()

asyncio.run(run())
"

echo "▶ Running seed scripts..."
python -m scripts.seed_competitors 2>&1 | tail -3 || true
python -m scripts.seed_solutions_techs 2>&1 | tail -3 || true
python -m scripts.seed_competitors_solutions 2>&1 | tail -3 || true
python -m scripts.seed_competitors_remaining 2>&1 | tail -3 || true
python -m scripts.seed_cloud_competitors 2>&1 | tail -3 || true
python -m scripts.seed_oem_sourcing 2>&1 | tail -3 || true
python -m scripts.seed_tech_shares_complete 2>&1 | tail -3 || true
echo "▶ Seeding complete."

echo "▶ Starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001}
