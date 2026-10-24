import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
home_env = Path.home() / ".celesto_env"
if home_env.exists():
    load_dotenv(dotenv_path=home_env)

CELESTO_PROVIDER = os.getenv("CELESTO_PROVIDER", "cloud")
CELESTO_API_KEY = os.getenv("CELESTO_API_KEY", "replace-me")
CELESTO_BACKEND = os.getenv("CELESTO_BACKEND", "firecracker")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "replace-me")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ledger:ledger@ledger:5432/ledger"
)
API_PORT = int(os.getenv("API_PORT", "8080"))
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "./reports"))
COMMAND_LOG_PATH = Path(os.getenv("COMMAND_LOG_PATH", "./logs/commands.jsonl"))
