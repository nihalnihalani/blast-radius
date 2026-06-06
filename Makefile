.PHONY: redis backend web setup

# Local Redis (RedisJSON + Search) for dev
redis:
	docker run -d --name redis -p 6379:6379 redis/redis-stack:latest || docker start redis
	redis-cli config set notify-keyspace-events KE$$x || true

setup:
	cd services/agent && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
	cd apps/web && npm install

backend:
	cd services/agent && . .venv/bin/activate && uvicorn main:app --reload --port 8000

web:
	cd apps/web && npm run dev
