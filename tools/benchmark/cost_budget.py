"""Fail-closed provider-cost accounting for deterministic benchmark runs.

The budget is intentionally checked before every request and charged immediately
after a provider response. A response can still cross a ceiling (its price is
not known until it completes), but no later request is sent. A shared JSONL
ledger lets sequential benchmark stages enforce one ceiling together.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


class CostBudgetExceeded(RuntimeError):
    """Raised when a run cannot safely make another paid provider request."""


def _reported_cost(usage: Mapping[str, Any] | None) -> float | None:
    if not usage or "cost" not in usage or usage.get("cost") is None:
        return None
    try:
        cost = float(usage["cost"])
    except (TypeError, ValueError) as exc:
        raise CostBudgetExceeded(f"Provider returned a non-numeric usage.cost: {usage.get('cost')!r}") from exc
    if cost < 0:
        raise CostBudgetExceeded(f"Provider returned a negative usage.cost: {cost}")
    return cost


@dataclass
class CostBudget:
    max_cost_usd: float | None = None
    usage_log: Path | None = None
    require_reported_cost: bool = False
    spent_usd: float = field(init=False, default=0.0)
    recorded_requests: int = field(init=False, default=0)
    initial_spent_usd: float = field(init=False, default=0.0)
    initial_recorded_requests: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if self.max_cost_usd is not None and self.max_cost_usd <= 0:
            raise ValueError("max_cost_usd must be greater than zero")
        if self.usage_log is not None:
            self.usage_log.parent.mkdir(parents=True, exist_ok=True)
            if self.usage_log.exists():
                for raw in self.usage_log.read_text(encoding="utf-8").splitlines():
                    if not raw.strip():
                        continue
                    try:
                        record = json.loads(raw)
                        cost = float(record.get("cost_usd", 0.0) or 0.0)
                    except (json.JSONDecodeError, TypeError, ValueError) as exc:
                        raise CostBudgetExceeded(
                            f"Cannot safely resume with malformed provider-cost ledger: {self.usage_log}"
                        ) from exc
                    if cost < 0:
                        raise CostBudgetExceeded(f"Provider-cost ledger contains a negative cost: {self.usage_log}")
                    self.spent_usd += cost
                    self.recorded_requests += 1
        self.initial_spent_usd = self.spent_usd
        self.initial_recorded_requests = self.recorded_requests

    @property
    def session_spent_usd(self) -> float:
        """Provider-reported cost added by this runner invocation."""
        return self.spent_usd - self.initial_spent_usd

    @property
    def session_recorded_requests(self) -> int:
        return self.recorded_requests - self.initial_recorded_requests

    def authorize_request(self, *, model: str, workload: str) -> None:
        if self.max_cost_usd is not None and self.spent_usd >= self.max_cost_usd:
            raise CostBudgetExceeded(
                f"Provider-reported spend ${self.spent_usd:.6f} has reached the "
                f"${self.max_cost_usd:.6f} ceiling; no {workload} request for {model} was sent."
            )

    def record_response(
        self,
        usage: Mapping[str, Any] | None,
        *,
        model: str,
        workload: str,
    ) -> float:
        cost = _reported_cost(usage)
        if cost is None and self.require_reported_cost:
            raise CostBudgetExceeded(
                f"{workload} response for {model} had no provider-reported usage.cost; "
                "stopping before another paid request."
            )
        charge = cost or 0.0
        self.spent_usd += charge
        self.recorded_requests += 1
        record = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "workload": workload,
            "cost_usd": charge,
            "usage": dict(usage or {}),
            "cumulative_cost_usd": self.spent_usd,
        }
        if self.usage_log is not None:
            with self.usage_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        if self.max_cost_usd is not None and self.spent_usd > self.max_cost_usd:
            raise CostBudgetExceeded(
                f"Provider-reported spend ${self.spent_usd:.6f} crossed the "
                f"${self.max_cost_usd:.6f} ceiling during {workload}; remaining requests were halted."
            )
        return charge

    def metadata(self) -> dict[str, Any]:
        return {
            "max_cost_usd": self.max_cost_usd,
            "provider_reported_cost_usd": round(self.session_spent_usd, 8),
            "recorded_requests": self.session_recorded_requests,
            "cumulative_provider_reported_cost_usd": round(self.spent_usd, 8),
            "cumulative_recorded_requests": self.recorded_requests,
            "require_reported_cost": self.require_reported_cost,
            "usage_log": str(self.usage_log) if self.usage_log is not None else "",
        }
