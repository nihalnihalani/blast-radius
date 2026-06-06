# Redis design — beyond cache (for Best Redis / Guy Royse)

> Five Redis capabilities doing real distributed-systems work. **None of this is caching.** All commands verified against redis-py 8.x in the research phase.

## 0. Setup

```python
import redis.asyncio as redis
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
# Enable keyspace notifications: K=keyspace, E=keyevent, $=string cmds, x=expired
await r.config_set("notify-keyspace-events", "KE$x")
```
Use **redis-stack** locally (RedisJSON + Search built in) or Redis Cloud paid tier with the `WEAVEHACKS_4` coupon. **Do not use the free tier** — 30 connections is too few for 4 consumers + pubsub + JSON reads.

## 1. RedisJSON — the DAG document (state, not cache)

```python
# at run start
await r.json().set(f"dag:run:{run_id}", "$", {
  "run_id": run_id, "request": text,
  "nodes": { "scale-payments": {"status":"pending","agent":None,"deps":[]}, ... },
  "edges": [["validate-iam","scale-payments"], ...],   # arrays at leaves only!
})
# per-node status update (RFC 7396 merge — preserves other keys)
await r.json().merge(f"dag:run:{run_id}", f"$.nodes.{node_id}", {"status":"running","agent":agent_id})
```
**Gotcha:** `JSON.MERGE` replaces whole **arrays**. Keep `edges` on the root and never merge a path that contains an array you want to preserve element-wise; use `JSON.ARRAPPEND` for lists.

## 2. Streams + consumer groups — the work bus & dead-letter queue

```python
await r.xgroup_create("agents:tasks", "workers", id="$", mkstream=True)
# producer (executor): enqueue a unit of work
await r.xadd("agents:tasks", {"node_id": node_id, "action": "scale", "run_id": run_id})
# consumer (worker): claim new work
msgs = await r.xreadgroup("workers", consumer_name, {"agents:tasks": ">"}, count=10, block=2000)
# ... do mock work ...
await r.xack("agents:tasks", "workers", msg_id)
# DEAD-LETTER: reclaim stuck work and route to DLQ if redelivered too often
next_id, claimed, _ = await r.xautoclaim("agents:tasks", "workers", consumer_name, min_idle_time=2000, start_id="0")
for mid, fields in claimed:
    pend = await r.xpending_range("agents:tasks", "workers", min=mid, max=mid, count=1)
    if pend and pend[0]["times_delivered"] >= 3:        # NB: field is 'times_delivered'
        await r.xadd("agents:dlq", fields); await r.xack("agents:tasks", "workers", mid)
```
**Demo:** pre-seed one DLQ message before the demo so **"Resume with safe fallback"** instantly has something to consume. Use `min_idle_time=2000` (2s) for demo speed; narrate "configurable per-agent, 30s+ in prod."

## 3. Circuit breaker — the real kill switch (INCR + EXPIRE + SET EX)

```python
BREAKER = r.register_script("""
  local n = redis.call('INCR', KEYS[1])
  if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
  if n >= tonumber(ARGV[2]) then redis.call('SET', KEYS[2], '1', 'EX', ARGV[3]) end
  return n
""")  # atomic: removes the INCR/EXPIRE race
# on each agent failure:
n = await BREAKER(keys=[f"cb:{agent}:failures", f"cb:{agent}:open"], args=[10, 5, 10])
open = await r.exists(f"cb:{agent}:open")   # short-circuit the agent if open
```
- Window 10s, threshold **5**, open-TTL 10s. We trip at 5 **before** LangGraph's `recursion_limit=25` raises.
- A **Lua script** makes INCR+EXPIRE+SET atomic (no counter-leak race). `SET key v EX n` is preferred over deprecated `SETEX`.
- A **"Force Reset"** button calls `r.delete("cb:{agent}:open")` to fire the expired keyevent on demand during Q&A.

## 4. Keyspace Notifications — zero-polling control plane

```python
pubsub = r.pubsub()
await pubsub.subscribe("__keyevent@0__:set", "__keyevent@0__:expired")
async def listen():
    async for m in pubsub.listen():
        key = m["data"]
        if m["channel"].endswith(":set")     and key.endswith(":open"): await trip_queue.put(("TRIPPED", key))
        if m["channel"].endswith(":expired") and key.endswith(":open"): await trip_queue.put(("RESET",   key))
```
- Subscribe to **`:set`** for the **instant** trip signal (the `:expired` event lags under load — it fires when Redis actually deletes the key, not at TTL=0).
- The listener pushes onto an `asyncio.Queue` (`trip_queue`); the orchestrator drains it at a step boundary and yields the AG-UI `CustomEvent`. **Do not call `adispatch_custom_event` from the background task** — it needs the LangGraph run context and will silently no-op.

## 5. RedisVL — semantic recovery memory (`redisvl==0.20.0`)

```python
from redisvl.extensions.message_history import SemanticMessageHistory
hist = SemanticMessageHistory(name="recovery_context", redis_url=REDIS_URL)
hist.add_message({"role":"system","content":failure_summary}, session_tag=agent_id)
similar = hist.get_relevant(prompt=current_failure, top_k=3)   # feed recovery agent
```
The recovery agent retrieves *similar past failures* to choose a safe fallback — memory, not cache.

## Key schema summary

| Key / stream | Type | Purpose |
|---|---|---|
| `dag:run:{id}` | RedisJSON | the live DAG document |
| `agents:tasks` | Stream + group `workers` | work bus |
| `agents:dlq` | Stream | dead-letter queue |
| `cb:{agent}:failures` | String (INCR, TTL) | failure counter (window) |
| `cb:{agent}:open` | String (SET EX) | breaker-open flag (fires keyevents) |
| `recovery_context` | RedisVL index | semantic recovery memory |
