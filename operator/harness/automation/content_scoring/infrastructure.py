from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class ModelResponse:
    payload: dict[str, Any]
    cost: float
    usage: dict[str, Any]


class Telemetry:
    def __init__(self, path: Path, verbose: bool = False) -> None:
        self.path = path
        self.verbose = verbose
        path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **fields: Any) -> None:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        if self.verbose or event in {"run_started", "artifact_scored", "retry", "run_failed", "run_completed"}:
            detail = " ".join(f"{key}={value}" for key, value in fields.items() if key in {"case_study", "artifact", "model", "attempt", "cost", "reason"})
            print(f"[content-score] {event} {detail}".rstrip())


class OpenRouterEvaluator:
    def __init__(self, api_key: str, telemetry: Telemetry, timeout_seconds: float = 120, attempts: int = 4) -> None:
        self.api_key = api_key
        self.telemetry = telemetry
        self.timeout_seconds = timeout_seconds
        self.attempts = attempts

    def complete(self, *, model: str, prompt: str, schema: dict[str, Any], run_id: str, stage: str, case_study: str, artifact: str) -> ModelResponse:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "content_score", "strict": True, "schema": schema}},
            "provider": {"require_parameters": True},
            "max_tokens": 5000,
        }
        last_error: Exception | None = None
        with httpx.Client(timeout=self.timeout_seconds) as client:
            for attempt in range(1, self.attempts + 1):
                started = time.monotonic()
                try:
                    response = client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                    if response.status_code in {408, 429, 500, 502, 503, 504}:
                        raise httpx.HTTPStatusError("retryable provider status", request=response.request, response=response)
                    response.raise_for_status()
                    data = response.json()
                    choice = data["choices"][0]
                    content = choice["message"]["content"]
                    if not isinstance(content, str):
                        raise ValueError("Evaluator response did not contain text JSON")
                    parsed = json.loads(content)
                    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                    cost = float(usage.get("cost", 0) or 0)
                    self.telemetry.emit("model_completed", run_id=run_id, stage=stage, case_study=case_study, artifact=artifact, model=model, attempt=attempt, duration_ms=round((time.monotonic() - started) * 1000), cost=cost, usage=usage, finish_reason=choice.get("finish_reason"), response_characters=len(content))
                    return ModelResponse(parsed, cost, usage)
                except (httpx.TransportError, httpx.HTTPStatusError, ValueError, json.JSONDecodeError, KeyError) as exc:
                    last_error = exc
                    retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in {408, 429, 500, 502, 503, 504}
                    if not retryable or attempt >= self.attempts:
                        self.telemetry.emit("model_failed", run_id=run_id, stage=stage, case_study=case_study, artifact=artifact, model=model, attempt=attempt, reason=type(exc).__name__)
                        raise RuntimeError(f"{model} {stage} failed: {exc}") from exc
                    delay = min(16, 2 ** (attempt - 1))
                    self.telemetry.emit("retry", run_id=run_id, stage=stage, case_study=case_study, artifact=artifact, model=model, attempt=attempt, reason=type(exc).__name__, delay_seconds=delay)
                    time.sleep(delay)
        raise RuntimeError(f"Evaluator failed unexpectedly: {last_error}")
