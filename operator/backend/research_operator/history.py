"""Read-only event history service with replay and server-sent events."""

from __future__ import annotations

import asyncio
import os
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from psycopg import connect
from psycopg.rows import dict_row

from .config import Settings
from .cqrs import CommandStore
from .repository import _plain


PAGE = """<!doctype html><html><head><meta charset='utf-8'><title>Research event history</title>
<style>body{margin:0;background:#08111f;color:#e5edf7;font:14px system-ui;padding:24px}main{max-width:1200px;margin:auto}header{display:flex;justify-content:space-between;align-items:center}input,select{background:#111d30;color:inherit;border:1px solid #38506f;padding:8px;border-radius:6px}button{padding:8px 12px;border:0;border-radius:6px;background:#4f8cff;color:#fff;cursor:pointer}#events{margin-top:18px;border:1px solid #263a56;border-radius:8px;overflow:auto;max-height:75vh}article{padding:12px;border-bottom:1px solid #1c2d44;display:grid;grid-template-columns:110px 190px 1fr;gap:12px}.muted{color:#9eb0c6}.error{color:#ff9a9a}</style></head><body><main><header><div><h1>Research event history</h1><p class='muted'>Live PostgreSQL event stream with durable cursor replay.</p></div><a href='http://localhost:8090'>Operator</a></header><p><input id='filter' placeholder='Run, job, or event type'><button id='pause'>Pause</button> <span id='state' class='muted'>Connecting</span></p><section id='events'></section></main><script>
let cursor=0,source,paused=false;const root=document.querySelector('#events'),state=document.querySelector('#state'),filter=document.querySelector('#filter');
function eventCard(e){cursor=Math.max(cursor,e.event_id);const x=document.createElement('article');x.innerHTML=`<span class='muted'>#${e.event_id}<br>${new Date(e.occurred_at).toLocaleTimeString()}</span><strong>${e.event_type}<br><small class='muted'>${e.producer}</small></strong><code>${JSON.stringify(e.payload)}</code>`;root.prepend(x)}
function connect(){if(paused)return;source=new EventSource('/api/events/stream?after='+cursor);source.onopen=()=>state.textContent='Live';source.onmessage=x=>eventCard(JSON.parse(x.data));source.onerror=()=>state.textContent='Reconnecting…'}
document.querySelector('#pause').onclick=()=>{paused=!paused;document.querySelector('#pause').textContent=paused?'Resume':'Pause';if(paused){source?.close();state.textContent='Paused'}else connect()};
filter.onchange=async()=>{root.replaceChildren();cursor=0;const q=filter.value.trim();const d=await fetch('/api/events?limit=250&event_type='+encodeURIComponent(q)).then(r=>r.json());d.events.reverse().forEach(eventCard)};connect();</script></body></html>"""


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime = settings or Settings.from_env()
    store = CommandStore(runtime.database_dsn)
    app = FastAPI(title="Research Event History", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "latest_event_id": store.latest_event_id()}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return PAGE

    @app.get("/api/events")
    def events(after: int = 0, limit: int = 200, correlation_id: str = "", event_type: str = "",
               producer: str = "", aggregate_id: str = "") -> dict[str, Any]:
        rows = store.events(after=max(0, after), limit=max(1, min(limit, 1000)), filters={
            "correlation_id": correlation_id, "event_type": event_type,
            "producer": producer, "aggregate_id": aggregate_id,
        })
        return {"events": rows, "next_cursor": rows[-1]["event_id"] if rows else after,
                "latest_event_id": store.latest_event_id()}

    @app.get("/api/events/stream")
    async def stream(request: Request, after: int = 0) -> StreamingResponse:
        header = request.headers.get("last-event-id")
        cursor = max(after, int(header)) if header and header.isdigit() else after

        async def generate() -> AsyncIterator[str]:
            nonlocal cursor
            while True:
                if await request.is_disconnected():
                    return
                rows = store.events(after=cursor, limit=250)
                if rows:
                    for item in rows:
                        cursor = int(item["event_id"])
                        yield f"id: {cursor}\nevent: domain-event\ndata: {__import__('json').dumps(item)}\n\n"
                else:
                    yield ": keepalive\n\n"
                    await asyncio.sleep(1)

        return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.get("/api/timeline/runs/{run_id}")
    def run_timeline(run_id: str) -> dict[str, Any]:
        events = store.events(after=0, limit=1000, filters={"correlation_id": run_id})
        return {"run_id": run_id, "events": events}

    @app.get("/api/operations")
    def operations() -> dict[str, Any]:
        with connect(runtime.database_dsn, row_factory=dict_row) as connection:
            checkpoints = connection.execute("SELECT * FROM projection_checkpoints ORDER BY projection_name").fetchall()
            services = connection.execute("SELECT * FROM service_activity_read ORDER BY service_name").fetchall()
        latest = store.latest_event_id()
        return {"latest_event_id": latest, "checkpoints": [_plain(dict(row)) for row in checkpoints],
                "services": [_plain(dict(row)) for row in services]}

    return app


app = create_app()


def main() -> int:
    import uvicorn
    settings = Settings.from_env()
    uvicorn.run("research_operator.history:app", host="0.0.0.0", port=settings.event_history_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
