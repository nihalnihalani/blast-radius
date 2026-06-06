# Setup

## Prereqs
- Node 20+, Python 3.12, Docker (for local Redis), a W&B account, OpenAI key.

## 1. Redis (pick one)
```bash
# Local (recommended for dev — includes RedisJSON + Search)
docker run -d --name redis -p 6379:6379 redis/redis-stack:latest
# OR Redis Cloud: https://redis.io/login  -> create DB -> Billing -> Credits -> coupon WEAVEHACKS_4
```

## 2. Backend (Python agent)
```bash
cd services/agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# verify the risky imports on-site:
python -c "from langgraph.types import Send, Command, interrupt; print('langgraph ok')"
python -c "from copilotkit import CopilotKitState; from ag_ui.core import CustomEvent, EventType; print('agui ok')"
cp .env.example .env   # fill OPENAI_API_KEY, WANDB_API_KEY, REDIS_URL
uvicorn main:app --reload --port 8000
```

## 3. Frontend (Next.js cockpit)
```bash
cd apps/web
npm install
npm ls @copilotkit/react-core            # confirm 1.59.x and that /v2 subpath resolves
cp .env.local.example .env.local         # NEXT_PUBLIC + OPENAI_API_KEY
npm run dev                               # http://localhost:3000
```

## 4. Enable Redis keyspace notifications
```bash
redis-cli config set notify-keyspace-events KE$x
```

## 5. Weave Online Monitor (UI, ~15 min)
In the Weave web UI for project `blast-radius`: **Add Monitor** → pick the `executor_run` op → attach the runaway scorer → set sample rate. (No Python API exists for this.)

## Sponsor credits (get Saturday morning)
- W&B Inference $50 + OpenAI $50 + Cursor $100: fill the form, see Alex/Anna. Redis Cloud $100: coupon `WEAVEHACKS_4`.
