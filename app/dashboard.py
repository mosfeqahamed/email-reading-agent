"""FastAPI dashboard — shows important emails as notification cards.

Run with:  uvicorn app.dashboard:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from . import db

load_dotenv()

log = logging.getLogger("dashboard")


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist even if the dashboard starts before the agent.
    db.init_db()

    # Single-process mode (e.g. Render free tier, where the agent can't run as a
    # separate service): start the agent poll loop in a background thread so one
    # web service does both jobs. Docker/local keep them as two services.
    if _truthy(os.getenv("RUN_AGENT_IN_PROCESS")):
        from .agent import run_forever

        log.info("RUN_AGENT_IN_PROCESS set — starting agent loop in background thread")
        threading.Thread(target=run_forever, name="agent-loop", daemon=True).start()

    yield


app = FastAPI(title="AI Email Reading Agent — Dashboard", lifespan=lifespan)


@app.get("/api/notifications")
def api_notifications() -> JSONResponse:
    return JSONResponse(
        {"notifications": db.get_notifications(), "stats": db.stats()}
    )


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>AI Email Reading Agent</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
    background: #0d1117; color: #e6edf3;
  }
  header {
    padding: 24px 32px; border-bottom: 1px solid #21262d;
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;
  }
  h1 { font-size: 20px; margin: 0; }
  h1 span { color: #58a6ff; }
  .stats { display: flex; gap: 20px; font-size: 13px; color: #8b949e; }
  .stats b { color: #e6edf3; font-size: 16px; }
  main { padding: 24px 32px; max-width: 980px; margin: 0 auto; }
  .grid { display: grid; gap: 16px; }
  .card {
    background: #161b22; border: 1px solid #21262d; border-left-width: 4px;
    border-radius: 10px; padding: 16px 18px;
  }
  .card.HIGH   { border-left-color: #f85149; }
  .card.MEDIUM { border-left-color: #d29922; }
  .card.LOW    { border-left-color: #3fb950; }
  .row { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
  .subject { font-size: 16px; font-weight: 600; margin: 0 0 4px; }
  .from { font-size: 13px; color: #8b949e; }
  .badges { display: flex; gap: 8px; flex-shrink: 0; }
  .badge { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 999px; letter-spacing: .3px; }
  .pri.HIGH   { background: #f8514922; color: #ff7b72; }
  .pri.MEDIUM { background: #d2992222; color: #e3b341; }
  .pri.LOW    { background: #3fb95022; color: #56d364; }
  .cat { background: #1f6feb22; color: #79c0ff; }
  .reason { margin: 10px 0 0; font-size: 14px; color: #c9d1d9; line-height: 1.45; }
  .meta { margin-top: 10px; font-size: 12px; color: #6e7681; display: flex; gap: 14px; flex-wrap: wrap; }
  .empty { text-align: center; color: #8b949e; padding: 60px 0; }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:#3fb950; margin-right:6px; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:.3;} }
</style>
</head>
<body>
<header>
  <h1>📥 AI Email Reading Agent — <span>Important Notifications</span></h1>
  <div class="stats">
    <div><span class="dot"></span>live</div>
    <div><b id="n-important">0</b> important</div>
    <div><b id="n-processed">0</b> processed</div>
  </div>
</header>
<main>
  <div id="grid" class="grid"></div>
  <div id="empty" class="empty" style="display:none">
    No important emails yet. The agent is watching the inbox…
  </div>
</main>
<script>
async function refresh() {
  try {
    const res = await fetch('/api/notifications');
    const data = await res.json();
    const notes = data.notifications || [];
    document.getElementById('n-important').textContent = data.stats.important;
    document.getElementById('n-processed').textContent = data.stats.processed;

    const grid = document.getElementById('grid');
    const empty = document.getElementById('empty');
    empty.style.display = notes.length ? 'none' : 'block';

    grid.innerHTML = notes.map(n => `
      <div class="card ${n.priority}">
        <div class="row">
          <div>
            <p class="subject">${esc(n.subject) || '(no subject)'}</p>
            <div class="from">From: ${esc(n.sender)}</div>
          </div>
          <div class="badges">
            <span class="badge pri ${n.priority}">${n.priority}</span>
            <span class="badge cat">${esc(n.category)}</span>
          </div>
        </div>
        <p class="reason">${esc(n.reason)}</p>
        <div class="meta">
          <span>🕒 ${esc(n.received_at) || 'unknown time'}</span>
          <span>🤖 decided by ${esc(n.decided_by)}</span>
        </div>
      </div>
    `).join('');
  } catch (e) {
    console.error('refresh failed', e);
  }
}
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""
