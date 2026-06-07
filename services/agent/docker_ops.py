"""REAL infrastructure operations against Docker — no mocks.

The agent manages a live "payments service" (a pool of traefik/whoami containers) behind a real
nginx load balancer. DAG steps perform real operations: scaling containers, rewriting + reloading
the LB, real HTTP health checks, and a real `docker kill` kill-switch for a runaway container.

SAFETY: every operation is scoped to containers carrying the label `blast.managed=true` and the
`blast-` name prefix on the dedicated `blast-net` network. It never inspects or touches anything
else. Replica count is hard-capped (MAX_REPLICAS).
"""
import os
import shlex
import socket
import subprocess
import time
import urllib.request

import docker

from logging_setup import get_logger

log = get_logger("blast.docker")

NETWORK = "blast-net"
LABELS = {"blast.managed": "true"}
PAY_IMAGE = os.getenv("PAY_IMAGE", "traefik/whoami:latest")
LB_IMAGE = os.getenv("LB_IMAGE", "nginx:alpine")
LB_NAME = "blast-lb"
LB_PORT = int(os.getenv("LB_PORT", "8090"))
PAY_PREFIX = "blast-pay-"
RUNAWAY_NAME = "blast-runaway"
MAX_REPLICAS = int(os.getenv("MAX_REPLICAS", "5"))
DEFAULT_REPLICAS = int(os.getenv("DEFAULT_REPLICAS", "3"))

_client = None


def _docker_host() -> str | None:
    if os.getenv("DOCKER_HOST"):
        return os.getenv("DOCKER_HOST")
    for sock in (os.path.expanduser("~/.colima/default/docker.sock"), "/var/run/docker.sock",
                 os.path.expanduser("~/.docker/run/docker.sock")):
        if os.path.exists(sock):
            return f"unix://{sock}"
    try:
        out = subprocess.run(["docker", "context", "inspect"], capture_output=True, text=True, timeout=5)
        import json
        return json.loads(out.stdout)[0]["Endpoints"]["docker"]["Host"]
    except Exception:
        return None


def client() -> docker.DockerClient:
    global _client
    if _client is None:
        host = _docker_host()
        _client = docker.DockerClient(base_url=host) if host else docker.from_env()
        log.info("docker client connected (%s)", host or "default")
    return _client


# ----- network / lifecycle ---------------------------------------------------
def ensure_network() -> None:
    c = client()
    try:
        c.networks.get(NETWORK)
    except docker.errors.NotFound:
        c.networks.create(NETWORK, driver="bridge")
        log.info("created network %s", NETWORK)


def _managed(name_prefix: str = "blast-"):
    c = client()
    return [ct for ct in c.containers.list(all=True, filters={"label": "blast.managed=true"})
            if ct.name.startswith(name_prefix)]


def cleanup() -> int:
    """Remove every blast-managed container (used on startup/reset). Returns count removed."""
    n = 0
    for ct in _managed():
        with _suppress():
            ct.remove(force=True)
            n += 1
    if n:
        log.info("cleaned up %d managed containers", n)
    return n


# ----- validation steps (real preconditions) ---------------------------------
def validate_iam() -> dict:
    try:
        client().ping()
        return {"safe": True, "reason": "docker daemon reachable"}
    except Exception as e:
        return {"safe": False, "reason": f"docker unreachable: {e}"}


def check_deps() -> dict:
    c = client()
    ensure_network()
    for img in (PAY_IMAGE, LB_IMAGE):
        try:
            c.images.get(img)
        except docker.errors.ImageNotFound:
            log.info("pulling %s", img)
            c.images.pull(img)
    return {"safe": True, "reason": f"network + images ready ({PAY_IMAGE}, {LB_IMAGE})"}


# ----- payments service (real container pool) --------------------------------
def list_replicas() -> list[str]:
    return sorted(ct.name for ct in _managed(PAY_PREFIX) if ct.status == "running")


def scale_payments(n: int) -> dict:
    n = max(0, min(int(n), MAX_REPLICAS))
    c = client()
    ensure_network()
    current = {ct.name: ct for ct in _managed(PAY_PREFIX)}
    desired = {f"{PAY_PREFIX}{i}" for i in range(1, n + 1)}
    # start missing
    for name in sorted(desired - set(current)):
        c.containers.run(PAY_IMAGE, name=name, hostname=name, labels=LABELS,
                         network=NETWORK, detach=True, restart_policy={"Name": "no"})
    # stop extra
    for name in sorted(set(current) - desired):
        with _suppress():
            current[name].remove(force=True)
    time.sleep(0.5)
    reps = list_replicas()
    log.info("scaled payments -> %d replicas: %s", len(reps), reps)
    return {"replicas": reps, "count": len(reps)}


# ----- load balancer (real nginx) --------------------------------------------
def _nginx_conf(replicas: list[str]) -> str:
    servers = "\n".join(f"        server {r}:80 max_fails=1 fail_timeout=2s;" for r in replicas) \
        or "        server 127.0.0.1:1 down;"
    return (
        "upstream payments {\n" + servers + "\n}\n"
        "server {\n"
        "    listen 80;\n"
        "    location /healthz { return 200 'ok'; }\n"
        "    location / { proxy_pass http://payments; proxy_next_upstream error timeout http_502 http_503; }\n"
        "}\n"
    )


def _ensure_lb_container():
    c = client()
    ensure_network()
    try:
        lb = c.containers.get(LB_NAME)
        if lb.status != "running":
            lb.remove(force=True)
            raise docker.errors.NotFound("restart")
        return lb
    except docker.errors.NotFound:
        lb = c.containers.run(LB_IMAGE, name=LB_NAME, hostname=LB_NAME, labels=LABELS,
                              network=NETWORK, detach=True, restart_policy={"Name": "no"},
                              ports={"80/tcp": LB_PORT})
        time.sleep(1.0)
        log.info("started load balancer %s on :%d", LB_NAME, LB_PORT)
        return lb


def update_lb(replicas: list[str] | None = None, conf: str | None = None) -> dict:
    """Rewrite the nginx upstream to the given replicas and reload — for real."""
    lb = _ensure_lb_container()
    replicas = replicas if replicas is not None else list_replicas()
    conf = conf if conf is not None else _nginx_conf(replicas)
    cmd = f"printf %s {shlex.quote(conf)} > /etc/nginx/conf.d/default.conf && nginx -t && nginx -s reload"
    res = lb.exec_run(["sh", "-c", cmd])
    if res.exit_code != 0:
        raise RuntimeError(f"nginx reload failed: {res.output.decode()[:300]}")
    log.info("LB reconfigured to %d backends", len(replicas))
    return {"backends": replicas, "port": LB_PORT}


def healthcheck(timeout: float = 3.0) -> dict:
    """Real HTTP GET through the LB to a live backend. URL is configurable so a containerized
    agent can reach the host-published LB (e.g. http://host.docker.internal:8090/)."""
    url = os.getenv("LB_HEALTH_URL", f"http://localhost:{LB_PORT}/")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read().decode(errors="replace")
        backend = next((ln.split(":", 1)[1].strip() for ln in body.splitlines()
                        if ln.lower().startswith("hostname:")), "unknown")
        return {"ok": True, "status": 200, "served_by": backend, "url": url}
    except Exception as e:
        return {"ok": False, "error": str(e), "url": url}


# ----- runaway + real kill-switch --------------------------------------------
def start_runaway() -> None:
    """Start a REAL container that crash-loops (broken nginx) — the runaway agent's workload."""
    c = client()
    with _suppress():
        c.containers.get(RUNAWAY_NAME).remove(force=True)
    # nginx with an invalid config -> the container exits non-zero immediately, repeatedly.
    c.containers.run(LB_IMAGE, name=RUNAWAY_NAME, hostname=RUNAWAY_NAME, labels=LABELS,
                     network=NETWORK, detach=True, restart_policy={"Name": "on-failure", "MaximumRetryCount": 50},
                     command=["sh", "-c", "echo 'BROKEN CONFIG' > /etc/nginx/nginx.conf && nginx -g 'daemon off;'"])
    log.info("started runaway container %s (will crash-loop)", RUNAWAY_NAME)


def runaway_failures() -> int:
    """How many times the runaway container has restarted/failed (real Docker restart count)."""
    try:
        ct = client().containers.get(RUNAWAY_NAME)
        ct.reload()
        return int(ct.attrs.get("RestartCount", 0)) + (0 if ct.status == "running" else 1)
    except Exception:
        return 0


def kill_runaway() -> dict:
    """The real kill-switch: docker kill + remove the runaway container."""
    try:
        ct = client().containers.get(RUNAWAY_NAME)
        with _suppress():
            ct.kill()
        ct.remove(force=True)
        log.info("KILLED runaway container %s", RUNAWAY_NAME)
        return {"killed": RUNAWAY_NAME}
    except docker.errors.NotFound:
        return {"killed": None}


# ----- status (introspection) ------------------------------------------------
def infra_status() -> dict:
    return {"replicas": list_replicas(), "lb_port": LB_PORT, "health": healthcheck()}


class _suppress:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return True
