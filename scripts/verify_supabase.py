from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Env file not found: {path}")
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _mask_url(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    auth, host = rest.split("@", 1)
    user = auth.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Supabase/Postgres connection and shared RAG tables.")
    parser.add_argument("--env-file", default=".env.supabase", help="Path to env file containing DATABASE_URL.")
    parser.add_argument("--create-tables", action="store_true", help="Create tables if they do not exist.")
    parser.add_argument("--seed", action="store_true", help="Run demo seed_data after table creation.")
    args = parser.parse_args()

    load_env_file(ROOT / args.env_file)
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url or "sqlite" in database_url:
        raise SystemExit("DATABASE_URL must be a Supabase/Postgres URI.")
    if "<db-password>" in database_url or "password@" in database_url:
        raise SystemExit("Replace the placeholder database password in DATABASE_URL first.")

    from sqlalchemy import text

    from shared import models
    from shared.database import Base, engine

    print(f"Using DATABASE_URL={_mask_url(database_url)}")
    if args.create_tables:
        Base.metadata.create_all(bind=engine)
        print("Tables checked/created.")

    if args.seed:
        from scripts.seed_data import main as seed_main

        seed_main()

    with engine.connect() as conn:
        conn.execute(text("select 1"))
        counts = {
            "knowledge_documents": conn.execute(text(f"select count(*) from {models.KnowledgeDocument.__tablename__}")).scalar_one(),
            "policy_rules": conn.execute(text(f"select count(*) from {models.PolicyRule.__tablename__}")).scalar_one(),
            "historical_cases": conn.execute(text(f"select count(*) from {models.HistoricalCase.__tablename__}")).scalar_one(),
            "customer_tags": conn.execute(text(f"select count(*) from {models.CustomerTag.__tablename__}")).scalar_one(),
        }
    print("Supabase verification passed.")
    print(counts)


if __name__ == "__main__":
    main()
