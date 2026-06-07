"""Central config loaded from env. See .env.example."""
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
WEAVE_PROJECT = os.getenv("WEAVE_PROJECT", "blast-radius")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")  # fall back to gpt-4o if unavailable
AGENT_NAME = os.getenv("AGENT_NAME", "infra_orchestrator")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Comma-separated browser origins allowed to call the API (the cockpit).
ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]

# Circuit-breaker demo tuning
BREAKER_THRESHOLD = int(os.getenv("BREAKER_THRESHOLD", "5"))       # trip at N failures
BREAKER_WINDOW_SECONDS = int(os.getenv("BREAKER_WINDOW_SECONDS", "10"))
BREAKER_OPEN_TTL_SECONDS = int(os.getenv("BREAKER_OPEN_TTL_SECONDS", "10"))
DLQ_REDELIVERY_THRESHOLD = int(os.getenv("DLQ_REDELIVERY_THRESHOLD", "3"))

# We trip the breaker well below LangGraph's default recursion_limit (25) so the
# red-pulse animation fires BEFORE an uncaught GraphRecursionError. See docs/RISKS.md #3.
RECURSION_LIMIT = int(os.getenv("RECURSION_LIMIT", "50"))
