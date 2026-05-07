import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_DB = ROOT / ".pytest_cache" / "pytest_demo.db"
TEST_DB.parent.mkdir(exist_ok=True)
if TEST_DB.exists():
    TEST_DB.unlink()

# Tests must never read the developer's local .env and write to real Supabase.
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

# Keep pytest deterministic: normal unit tests should not call live LLM providers from local .env.
os.environ["DEEPSEEK_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = "openai"
os.environ["LLM_BASE_URL"] = ""
os.environ["LLM_CHAT_MODEL"] = ""
