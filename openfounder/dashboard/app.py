"""Mission Control Dashboard — FastAPI backend for OpenFounder.

Provides a real-time status page showing venture state, decisions, crew outputs,
approvals, metrics, and system health. Phase 2 interaction layer.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from openfounder.config import config
from openfounder.state import (
    get_state,
    get_venture,
    list_ventures,
    list_decisions,
    list_features,
    list_bugs,
    list_campaigns,
    list_content,
    list_crew_outputs,
    list_pending_approvals,
    get_latest_metrics,
    resolve_approval,
)

logger = logging.getLogger("openfounder.dashboard")

app = FastAPI(
    title="OpenFounder Mission Control",
    description="AI Co-Founder Dashboard",
    version="0.1.0",
)

STATIC_DIR = Path(__file__).parent / "static"


# ── API Routes ───────────────────────────────────────────────────────────────

@app.get("/api/ventures")
def api_ventures():
    """List all active ventures."""
    return list_ventures()


@app.get("/api/ventures/{venture}/state")
def api_venture_state(venture: str):
    """Get full state for a venture."""
    try:
        return get_state(venture)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/ventures/{venture}/decisions")
def api_decisions(venture: str, days: int = 7, decision_type: str = None):
    """List recent decisions."""
    try:
        return list_decisions(venture, days=days, decision_type=decision_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/ventures/{venture}/features")
def api_features(venture: str, status: str = None):
    """List features."""
    try:
        return list_features(venture, status=status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/ventures/{venture}/bugs")
def api_bugs(venture: str, status: str = None):
    """List bugs."""
    try:
        return list_bugs(venture, status=status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/ventures/{venture}/metrics")
def api_metrics(venture: str):
    """Get latest metrics."""
    try:
        return get_latest_metrics(venture)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/ventures/{venture}/crew-outputs")
def api_crew_outputs(venture: str, crew: str = None, days: int = 7):
    """List recent crew outputs."""
    try:
        return list_crew_outputs(venture, crew_name=crew, days=days)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/ventures/{venture}/approvals")
def api_approvals(venture: str):
    """List pending approvals."""
    try:
        return list_pending_approvals(venture)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/approvals/{approval_id}/resolve")
async def api_resolve_approval(approval_id: int, request: Request):
    """Approve or reject an approval."""
    body = await request.json()
    status = body.get("status")
    if status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be 'approved' or 'rejected'")
    try:
        result = resolve_approval(approval_id, status, resolved_by="dashboard")
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/ventures/{venture}/content")
def api_content(venture: str, status: str = None, channel: str = None, days: int = 30):
    """List content calendar entries."""
    try:
        return list_content(venture, status=status, channel=channel, days=days)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/ventures/{venture}/campaigns")
def api_campaigns(venture: str, status: str = None):
    """List campaigns."""
    try:
        return list_campaigns(venture, status=status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/health")
def api_health():
    """System health check."""
    from openfounder.state import get_db
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
    }


# ── HTML Dashboard ───────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve the Mission Control dashboard."""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse(_EMBEDDED_DASHBOARD)


# Embedded dashboard HTML — no external dependencies, pure vanilla JS
_EMBEDDED_DASHBOARD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenFounder Mission Control</title>
<style>
:root {
  --bg: #0a0a0f;
  --surface: #12121a;
  --border: #1e1e2e;
  --text: #e4e4ef;
  --text-dim: #8888a0;
  --accent: #6366f1;
  --accent-dim: #4f46e5;
  --green: #22c55e;
  --yellow: #eab308;
  --red: #ef4444;
  --blue: #3b82f6;
  --orange: #f97316;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', monospace;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  font-size: 13px;
}

.container { max-width: 1400px; margin: 0 auto; padding: 20px; }

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
}

header h1 {
  font-size: 18px;
  font-weight: 600;
  color: var(--accent);
}

header .status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-dim);
}

header .dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--green);
}

header .dot.error { background: var(--red); }

.venture-selector {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.venture-selector button {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-family: inherit;
  font-size: 12px;
  transition: all 0.15s;
}

.venture-selector button:hover { border-color: var(--accent); }
.venture-selector button.active {
  background: var(--accent-dim);
  border-color: var(--accent);
  color: white;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
  gap: 16px;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
}

.card h2 {
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-dim);
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card h2 .count {
  background: var(--accent-dim);
  color: white;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 11px;
}

.item {
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.item:last-child { border-bottom: none; }

.item .title { font-weight: 500; }

.item .meta {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 2px;
}

.badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
}

.badge.critical { background: var(--red); color: white; }
.badge.high { background: var(--orange); color: white; }
.badge.medium { background: var(--yellow); color: #000; }
.badge.low { background: var(--blue); color: white; }
.badge.strategic { background: var(--accent); color: white; }
.badge.feature { background: var(--green); color: white; }
.badge.delegation { background: var(--orange); color: white; }
.badge.marketing { background: var(--blue); color: white; }
.badge.resource { background: var(--yellow); color: #000; }
.badge.bug { background: var(--red); color: white; }
.badge.success { background: var(--green); color: white; }
.badge.completed { background: var(--green); color: white; }
.badge.failed { background: var(--red); color: white; }
.badge.pending { background: var(--yellow); color: #000; }
.badge.approved { background: var(--green); color: white; }

.confidence-bar {
  display: inline-block;
  width: 60px;
  height: 6px;
  background: var(--border);
  border-radius: 3px;
  overflow: hidden;
  vertical-align: middle;
}

.confidence-bar .fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
}

.metric-box {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px;
  text-align: center;
}

.metric-box .value {
  font-size: 20px;
  font-weight: 700;
  color: var(--accent);
}

.metric-box .label {
  font-size: 10px;
  color: var(--text-dim);
  text-transform: uppercase;
  margin-top: 2px;
}

.approval-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.btn {
  padding: 4px 12px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-family: inherit;
  font-size: 11px;
  font-weight: 600;
  transition: opacity 0.15s;
}

.btn:hover { opacity: 0.85; }
.btn.approve { background: var(--green); color: white; }
.btn.reject { background: var(--red); color: white; }

.empty { color: var(--text-dim); font-style: italic; padding: 12px 0; }

.refresh-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-dim);
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  font-size: 11px;
}

.refresh-btn:hover { border-color: var(--accent); color: var(--text); }

@media (max-width: 900px) {
  .grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>OpenFounder Mission Control</h1>
    <div class="status">
      <div class="dot" id="health-dot"></div>
      <span id="health-text">Connecting...</span>
      <button class="refresh-btn" onclick="refresh()">Refresh</button>
    </div>
  </header>

  <div class="venture-selector" id="venture-tabs"></div>

  <div id="dashboard-content">
    <div class="empty" style="text-align:center;padding:40px">Loading...</div>
  </div>
</div>

<script>
let currentVenture = null;
let ventures = [];

async function api(path) {
  const resp = await fetch('/api' + path);
  if (!resp.ok) throw new Error(resp.statusText);
  return resp.json();
}

function badge(text, cls) {
  return `<span class="badge ${cls || text}">${text}</span>`;
}

function confidenceBar(val) {
  const pct = Math.round((val || 0) * 100);
  const color = pct >= 70 ? 'var(--green)' : pct >= 40 ? 'var(--yellow)' : 'var(--red)';
  return `<span class="confidence-bar"><span class="fill" style="width:${pct}%;background:${color}"></span></span> ${pct}%`;
}

function timeAgo(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff/60) + 'm ago';
  if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
  return Math.floor(diff/86400) + 'd ago';
}

async function checkHealth() {
  try {
    const h = await api('/health');
    const dot = document.getElementById('health-dot');
    const text = document.getElementById('health-text');
    dot.className = 'dot' + (h.status === 'ok' ? '' : ' error');
    text.textContent = h.status === 'ok' ? 'System Online' : 'Degraded';
  } catch {
    document.getElementById('health-dot').className = 'dot error';
    document.getElementById('health-text').textContent = 'Offline';
  }
}

async function loadVentures() {
  ventures = await api('/ventures');
  const tabs = document.getElementById('venture-tabs');
  tabs.innerHTML = ventures.map(v =>
    `<button onclick="selectVenture('${v.name}')" class="${v.name === currentVenture ? 'active' : ''}">${v.name}</button>`
  ).join('');
  if (ventures.length && !currentVenture) {
    selectVenture(ventures[0].name);
  }
}

async function selectVenture(name) {
  currentVenture = name;
  document.querySelectorAll('.venture-selector button').forEach(b => {
    b.className = b.textContent === name ? 'active' : '';
  });
  await renderDashboard(name);
}

async function renderDashboard(venture) {
  const el = document.getElementById('dashboard-content');
  try {
    const [state, decisions, crewOutputs, approvals] = await Promise.all([
      api(`/ventures/${venture}/state`),
      api(`/ventures/${venture}/decisions?days=7`),
      api(`/ventures/${venture}/crew-outputs?days=7`),
      api(`/ventures/${venture}/approvals`),
    ]);

    const v = state.venture;
    const metrics = state.metrics || [];
    const features = state.features || [];
    const bugs = state.bugs || [];
    const content = state.content_calendar || [];

    el.innerHTML = `
      <div class="grid">
        <!-- Venture Overview -->
        <div class="card">
          <h2>Venture Overview</h2>
          <div style="margin-bottom:10px">
            <strong style="font-size:16px">${v.name}</strong>
            ${badge(v.stage)}
          </div>
          <div class="meta">${v.description || 'No description'}</div>
          <div class="meta" style="margin-top:6px">Goal: ${v.goal || 'Not set'}</div>
        </div>

        <!-- Metrics -->
        <div class="card">
          <h2>Metrics <span class="count">${metrics.length}</span></h2>
          ${metrics.length ? `<div class="metric-grid">
            ${metrics.map(m => `
              <div class="metric-box">
                <div class="value">${typeof m.value === 'number' ? m.value.toLocaleString() : m.value}</div>
                <div class="label">${m.name}${m.unit ? ' (' + m.unit + ')' : ''}</div>
              </div>
            `).join('')}
          </div>` : '<div class="empty">No metrics recorded yet</div>'}
        </div>

        <!-- Decisions -->
        <div class="card">
          <h2>Recent Decisions <span class="count">${decisions.length}</span></h2>
          ${decisions.length ? decisions.slice(0, 8).map(d => `
            <div class="item">
              <div class="title">${badge(d.decision_type)} ${d.title}</div>
              <div class="meta">${d.reasoning ? d.reasoning.substring(0, 120) : ''}</div>
              <div class="meta">${confidenceBar(d.confidence)} &middot; ${d.source} &middot; ${timeAgo(d.created_at)}</div>
            </div>
          `).join('') : '<div class="empty">No decisions in the last 7 days</div>'}
        </div>

        <!-- Pending Approvals -->
        <div class="card">
          <h2>Pending Approvals <span class="count">${approvals.length}</span></h2>
          ${approvals.length ? approvals.map(a => `
            <div class="item">
              <div class="title">${badge(a.action_type)} ${a.title}</div>
              <div class="meta">${a.description ? a.description.substring(0, 100) : ''}</div>
              <div class="meta">By: ${a.requested_by} &middot; ${timeAgo(a.created_at)}</div>
              <div class="approval-actions">
                <button class="btn approve" onclick="resolveApproval(${a.id}, 'approved')">Approve</button>
                <button class="btn reject" onclick="resolveApproval(${a.id}, 'rejected')">Reject</button>
              </div>
            </div>
          `).join('') : '<div class="empty">No pending approvals</div>'}
        </div>

        <!-- Features -->
        <div class="card">
          <h2>Features <span class="count">${features.length}</span></h2>
          ${features.length ? features.slice(0, 10).map(f => `
            <div class="item">
              <div class="title">${badge(f.priority)} ${f.title}</div>
              <div class="meta">${f.status}${f.assigned_crew ? ' → ' + f.assigned_crew : ''}</div>
            </div>
          `).join('') : '<div class="empty">No features tracked</div>'}
        </div>

        <!-- Bugs -->
        <div class="card">
          <h2>Bugs <span class="count">${bugs.length}</span></h2>
          ${bugs.length ? bugs.slice(0, 10).map(b => `
            <div class="item">
              <div class="title">${badge(b.severity)} ${b.title}</div>
              <div class="meta">${b.status}${b.assigned_crew ? ' → ' + b.assigned_crew : ''}</div>
            </div>
          `).join('') : '<div class="empty">No bugs tracked</div>'}
        </div>

        <!-- Crew Outputs -->
        <div class="card">
          <h2>Crew Activity <span class="count">${crewOutputs.length}</span></h2>
          ${crewOutputs.length ? crewOutputs.slice(0, 8).map(c => `
            <div class="item">
              <div class="title">${badge(c.crew_name)} ${c.task ? c.task.substring(0, 80) : '?'}</div>
              <div class="meta">
                ${badge(c.status, c.status)}
                ${c.model ? ' &middot; ' + c.model : ''}
                ${c.duration_s ? ' &middot; ' + c.duration_s + 's' : ''}
                ${c.input_tokens ? ' &middot; ' + c.input_tokens + ' in' : ''}
                &middot; ${timeAgo(c.created_at)}
              </div>
            </div>
          `).join('') : '<div class="empty">No crew activity in the last 7 days</div>'}
        </div>

        <!-- Content Calendar -->
        <div class="card">
          <h2>Content Calendar <span class="count">${content.length}</span></h2>
          ${content.length ? content.slice(0, 8).map(c => `
            <div class="item">
              <div class="title">${badge(c.channel || '?')} ${c.title || 'Untitled'}</div>
              <div class="meta">${badge(c.status, c.status)} &middot; ${timeAgo(c.created_at)}</div>
            </div>
          `).join('') : '<div class="empty">No content scheduled</div>'}
        </div>
      </div>
    `;
  } catch (e) {
    el.innerHTML = `<div class="empty" style="text-align:center;padding:40px;color:var(--red)">
      Error loading dashboard: ${e.message}</div>`;
  }
}

async function resolveApproval(id, status) {
  try {
    await fetch(`/api/approvals/${id}/resolve`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status}),
    });
    await renderDashboard(currentVenture);
  } catch (e) {
    alert('Failed: ' + e.message);
  }
}

async function refresh() {
  await checkHealth();
  if (currentVenture) await renderDashboard(currentVenture);
}

// Boot
(async () => {
  await checkHealth();
  await loadVentures();
  // Auto-refresh every 30s
  setInterval(refresh, 30000);
})();
</script>
</body>
</html>
""";
