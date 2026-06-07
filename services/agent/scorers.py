"""Weave scorer for runaway/failed agent steps -- the 'Bug signal' surfaced to Weave Monitors.

Attach in the W&B UI (Monitors -> Add Monitor -> select op + this scorer). Defined here so the
scoring logic lives in code even though Monitor wiring is UI-only.
"""
try:
    import weave

    class RunawayScorer(weave.Scorer):
        """Flags an executor step that failed under an open circuit breaker."""

        @weave.op
        def score(self, output: dict) -> dict:  # output = node result dict
            status = (output or {}).get("status")
            failed = status == "failed"
            return {"runaway": failed, "status": status}
except Exception:  # weave not installed
    RunawayScorer = None  # type: ignore
