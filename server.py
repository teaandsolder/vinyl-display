#!/usr/bin/env python3
"""
Flask web server — Vinyl Display control panel.
Access at http://raspberrypi3b.local:5000
"""

import logging
import threading
import json
import os
import glob
import hashlib
import io
from flask import Flask, jsonify, request, render_template_string, send_file
from state import state
from art import AlbumArtFetcher
import stats as vstats
from PIL import Image

log = logging.getLogger(__name__)
app = Flask(__name__)
logging.getLogger("werkzeug").setLevel(logging.ERROR)
art_fetcher = AlbumArtFetcher()

COVERS_DIR = os.path.expanduser("~/vinyl-display-covers")
PREF_FILE  = os.path.expanduser("~/.vinyl-display/preferences.json")


def _load_prefs() -> dict:
    if os.path.exists(PREF_FILE):
        try:
            with open(PREF_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover">
  <title>Vinyl Display</title>
  <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #111110;
      --surface: #1c1c1a;
      --border: #2a2a28;
      --text: #f0f0ee;
      --muted: #66665f;
      --green: #4d9e6f;
      --green-dim: rgba(77,158,111,0.15);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    html, body { height: 100%; background: var(--bg); color: var(--text);
      font-family: 'DM Sans', sans-serif; overflow: hidden; }

    #shell { display: flex; flex-direction: column; height: 100dvh; max-width: 480px; margin: 0 auto; }
    #pages { flex: 1; overflow: hidden; order: 1; position: relative; min-height: 0; }
    .page { position: absolute; inset: 0; overflow-y: auto; display: none; }
    .page.active { display: block; }

    /* Tab bar */
    #tabbar {
      display: flex; border-top: 1px solid var(--border);
      background: var(--bg);
      padding-bottom: max(env(safe-area-inset-bottom), 12px);
      flex-shrink: 0; order: 2;
    }
    .tab {
      flex: 1; display: flex; flex-direction: column; align-items: center;
      gap: 4px; padding: 10px 0; cursor: pointer; color: var(--muted);
      font-size: 10px; letter-spacing: 0.06em; text-transform: uppercase;
      border: none; background: none; font-family: 'DM Sans', sans-serif;
      transition: color 0.2s;
    }
    .tab.active { color: var(--green); }
    .tab svg { width: 22px; height: 22px; }

    /* Page header */
    .page-header {
      padding: 12px 20px 0;
      font-size: 11px; font-weight: 600; letter-spacing: 0.14em;
      text-transform: uppercase; color: var(--text);
    }

    /* ── NOW PLAYING ── */
    #np-content { padding: 20px 20px 24px; }

    .art-card {
      width: calc(100% - 80px); margin: 0 auto 20px;
      border-radius: 16px; overflow: hidden;
      background: var(--surface);
      box-shadow: 0 16px 40px rgba(0,0,0,0.5); aspect-ratio: 1;
    }
    .art-card img { width: 100%; height: 100%; object-fit: cover; display: block; }

    #hero-title {
      font-family: 'DM Serif Display', serif; font-size: 22px; line-height: 1.1;
      color: var(--text); margin-bottom: 6px;
    }
    .artist-row {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 8px;
    }
    #hero-artist { font-size: 14px; color: var(--text); font-weight: 400; }
    .badge-cached {
      font-size: 9px; font-weight: 600; letter-spacing: 0.1em;
      padding: 3px 8px; border-radius: 20px; text-transform: uppercase;
      border: 1px solid currentColor;
    }
    .badge-cached.is-cached { color: var(--green); background: var(--green-dim); }
    .badge-cached.not-cached { color: var(--muted); background: transparent; border-color: var(--border); }
    .playing-row {
      display: flex; align-items: center; gap: 8px;
      font-size: 12px; color: var(--green); margin-bottom: 28px;
    }
    .playing-dot {
      width: 6px; height: 6px; background: var(--green);
      border-radius: 50%; flex-shrink: 0;
      animation: blink 1.5s ease-in-out infinite;
    }
    @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

    /* Settings */
    .section-label {
      font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase;
      color: var(--muted); margin-bottom: 12px;
    }
    .settings-toggle {
      display: flex; align-items: center; justify-content: space-between;
      cursor: pointer; margin-bottom: 8px; user-select: none;
    }
    .settings-toggle-label {
      font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase;
      color: var(--muted);
    }
    .settings-chevron { color: var(--muted); font-size: 11px; transition: transform 0.2s; }
    .settings-chevron.open { transform: rotate(180deg); }
    .settings-block {
      background: var(--surface); border-radius: 12px; padding: 0 14px;
      border: 1px solid var(--border); overflow: hidden;
      max-height: 0; opacity: 0;
      transition: max-height 0.3s ease, opacity 0.2s ease, padding 0.3s ease;
    }
    .settings-block.open {
      max-height: 220px; opacity: 1; padding: 12px 14px;
    }
    .ctrl { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
    .ctrl:last-of-type { margin-bottom: 0; }
    .clabel { font-size: 12px; color: var(--muted); width: 72px; flex-shrink: 0; }
    input[type=range] {
      flex: 1; -webkit-appearance: none; height: 3px;
      background: var(--border); border-radius: 2px; outline: none;
    }
    input[type=range]::-webkit-slider-thumb {
      -webkit-appearance: none; width: 18px; height: 18px;
      background: var(--green); border-radius: 50%; cursor: pointer;
    }
    .cval { font-size: 12px; color: var(--text); width: 36px; text-align: right; }
    .reset-btn {
      display: block; margin: 10px 0 0 auto; padding: 6px 16px;
      background: none; border: 1px solid var(--border);
      color: var(--muted); border-radius: 6px; font-size: 11px; cursor: pointer;
      font-family: 'DM Sans', sans-serif; letter-spacing: 0.05em;
    }
    .reset-btn:active { border-color: var(--green); color: var(--green); }

    /* Sleep state */
    #sleep-state {
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      height: 75vh; text-align: center; padding: 40px;
    }
    .turntable-icon { font-size: 56px; margin-bottom: 20px; opacity: 0.15; }
    #sleep-state h2 {
      font-family: 'DM Serif Display', serif; font-size: 26px;
      margin-bottom: 8px; font-weight: 400;
    }
    #sleep-state p { font-size: 14px; color: var(--muted); }

    /* ── SAVED COVERS ── */
    #page-covers { padding: 0 16px 16px; }
    .covers-toolbar {
      display: flex; align-items: center; justify-content: space-between;
      margin: 12px 0 8px;
    }
    .covers-toolbar .hint { font-size: 11px; color: var(--muted); }
    .upload-btn {
      display: flex; align-items: center; gap: 6px;
      background: var(--surface); border: 1px solid var(--border);
      color: var(--text); border-radius: 8px; padding: 8px 14px;
      font-size: 13px; font-family: 'DM Sans', sans-serif; cursor: pointer;
      transition: border-color 0.2s;
    }
    .upload-btn:active { border-color: var(--green); color: var(--green); }
    #upload-input { display: none; }
    .covers-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 8px; }
    .cover-thumb {
      position: relative; border-radius: 10px; overflow: hidden;
      border: 2px solid transparent; cursor: pointer; aspect-ratio: 1;
      background: var(--surface);
    }
    .cover-thumb.selected { border-color: var(--green); }
    .cover-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .cover-thumb .tick {
      position: absolute; top: 5px; right: 5px; background: var(--green);
      color: #fff; font-size: 9px; border-radius: 3px; padding: 2px 5px; font-weight: 600;
    }
    .empty-state { text-align: center; color: var(--muted); padding: 60px 0; font-size: 14px; }

    /* ── STATS ── */
    #page-stats { padding: 0 16px 16px; }
    .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 16px 0 24px; }
    .stat-card {
      background: var(--surface); border-radius: 14px; padding: 18px;
      border: 1px solid var(--border);
    }
    .stat-card.full { grid-column: 1 / -1; }
    .stat-value {
      font-family: 'DM Serif Display', serif; font-size: 36px; color: var(--text);
      line-height: 1; margin-bottom: 6px;
    }
    .stat-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }

    .top-covers { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 8px; margin-bottom: 24px; }
    .top-cover { flex-shrink: 0; position: relative; }
    .top-cover img { width: 72px; height: 72px; border-radius: 8px; object-fit: cover; display: block; }
    .top-cover .play-count {
      position: absolute; bottom: 4px; right: 4px; background: rgba(0,0,0,0.8);
      color: #fff; font-size: 9px; border-radius: 3px; padding: 2px 4px;
    }

    .history-day { margin-bottom: 20px; }
    .history-date {
      font-size: 11px; color: var(--muted); text-transform: uppercase;
      letter-spacing: 0.1em; margin-bottom: 8px; padding-bottom: 6px;
      border-bottom: 1px solid var(--border);
    }
    .history-entry {
      display: flex; align-items: center; gap: 12px; padding: 10px 0;
      border-bottom: 1px solid var(--border);
    }
    .history-entry:last-child { border-bottom: none; }
    .history-thumb { width: 40px; height: 40px; border-radius: 6px; object-fit: cover; flex-shrink: 0; background: var(--surface); }
    .history-time { font-size: 11px; color: var(--muted); width: 44px; flex-shrink: 0; }
    .history-artist { font-size: 13px; font-weight: 500; }
    .history-title { font-size: 11px; color: var(--muted); }
  </style>
</head>
<body>
<div id="shell">
  <div id="pages">

    <div class="page active" id="page-now">
      <div class="page-header">Now Playing</div>
      <div id="np-content"></div>
    </div>

    <div class="page" id="page-covers">
      <div class="page-header">Saved Covers</div>
      <div style="padding:0 16px">
        <div class="covers-toolbar">
          <span class="hint">Tap any cover to use it</span>
          <button class="upload-btn" onclick="document.getElementById('upload-input').click()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            Add Cover
          </button>
          <input type="file" id="upload-input" accept="image/*" onchange="uploadFile(this)">
        </div>
        <div class="upload-feedback" id="upload-feedback">Cover added ✓</div>
      </div>
      <div id="covers-grid-container" style="padding:0 16px"></div>
    </div>

    <div class="page" id="page-stats">
      <div class="page-header">Stats</div>
      <div id="stats-content"></div>
    </div>

  </div>

  <nav id="tabbar">
    <button class="tab active" onclick="showTab('now')" id="tab-now">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/>
      </svg>
      Now Playing
    </button>
    <button class="tab" onclick="showTab('covers')" id="tab-covers">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <rect x="3" y="3" width="7" height="7" rx="1"/>
        <rect x="14" y="3" width="7" height="7" rx="1"/>
        <rect x="3" y="14" width="7" height="7" rx="1"/>
        <rect x="14" y="14" width="7" height="7" rx="1"/>
      </svg>
      Saved Covers
    </button>
    <button class="tab" onclick="showTab('stats')" id="tab-stats">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
      Stats
    </button>
  </nav>
</div>

<script>
let d = null;
let countdown = 30;
let countdownTimer = null;
let currentTab = 'now';
let settingsOpen = false;

function toggleSettings() {
  settingsOpen = !settingsOpen;
  const block = document.getElementById('settings-block');
  const chevron = document.getElementById('settings-chevron');
  if (block) block.classList.toggle('open', settingsOpen);
  if (chevron) chevron.classList.toggle('open', settingsOpen);
}

function showTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('page-' + tab).classList.add('active');
  document.getElementById('tab-' + tab).classList.add('active');
  if (tab === 'covers') renderCovers();
  if (tab === 'stats') fetchStats();
}

function startCountdown(seconds) {
  countdown = seconds;
  clearInterval(countdownTimer);
  countdownTimer = setInterval(() => {
    countdown = Math.max(0, countdown - 1);
    const el = document.getElementById('hero-countdown');
    if (el) el.textContent = 'Playing \u2022 Re-identify in ' + countdown + 's';
  }, 1000);
}

async function fetchState() {
  const r = await fetch('/api/state');
  d = await r.json();
  renderNowPlaying(d);
  if (currentTab === 'covers') renderCovers();
}

function renderNowPlaying(d) {
  const el = document.getElementById('np-content');
  if (!d.playing) {
    el.innerHTML = `
      <div id="sleep-state">
        <div class="turntable-icon">&#9673;</div>
        <h2>Drop the needle</h2>
        <p>to start listening</p>
      </div>`;
    return;
  }
  const prefs = d.prefs || {};
  const prefKey = (d.artist + '|' + d.title).toLowerCase();
  const isCached = !!prefs[prefKey];
  const brightness = d.brightness;
  const saturation = Math.round(d.saturation * 100);

  el.innerHTML = `
    <div class="art-card">
      <img src="${d.current_artwork_url || ''}" onerror="this.style.opacity='0.05'">
    </div>
    <div id="hero-title">${d.title || ''}</div>
    <div class="artist-row">
      <div id="hero-artist">${d.artist || ''}</div>
      ${isCached ? '<span class="badge-cached is-cached">Cached</span>' : '<span class="badge-cached not-cached">Cached</span>'}
    </div>
    <div class="playing-row">
      <div class="playing-dot"></div>
      <span id="hero-countdown">Playing \u2022 Re-identify in ${countdown}s</span>
    </div>
    <div class="settings-toggle" onclick="toggleSettings()">
      <span class="settings-toggle-label">Display Settings</span>
      <span class="settings-chevron" id="settings-chevron">▼</span>
    </div>
    <div class="settings-block" id="settings-block">
      <div class="ctrl">
        <span class="clabel">Brightness</span>
        <input type="range" min="10" max="100" value="${brightness}"
          oninput="setSetting('brightness',+this.value);this.nextElementSibling.textContent=this.value">
        <span class="cval">${brightness}</span>
      </div>
      <div class="ctrl">
        <span class="clabel">Saturation</span>
        <input type="range" min="0" max="100" value="${saturation}"
          oninput="setSetting('saturation',this.value/100);this.nextElementSibling.textContent=this.value+'%'">
        <span class="cval">${saturation}%</span>
      </div>
      <div class="ctrl">
        <span class="clabel">Gamma</span>
        <input type="range" min="0" max="200" value="${Math.round(d.gamma*100)}"
          oninput="setSetting('gamma',this.value/100);this.nextElementSibling.textContent=(this.value/100).toFixed(2)">
        <span class="cval">${d.gamma ? d.gamma.toFixed(2) : '1.00'}</span>
      </div>
      <button class="reset-btn" onclick="resetSettings()">Reset to Default</button>
    </div>`;

  startCountdown(d.next_identify_in || 30);

  // Restore settings open state after re-render
  if (settingsOpen) {
    const block = document.getElementById('settings-block');
    const chevron = document.getElementById('settings-chevron');
    if (block) block.classList.add('open');
    if (chevron) chevron.classList.add('open');
  }
}

async function renderCovers() {
  const r = await fetch('/api/covers');
  const covers = await r.json();
  const el = document.getElementById('covers-grid-container');
  if (covers.length === 0) {
    el.innerHTML = '<div class="empty-state">No covers saved yet</div>';
    return;
  }
  el.innerHTML = '<div class="covers-grid">' + covers.map(c => `
    <div class="cover-thumb ${d && c.url === d.current_artwork_url ? 'selected' : ''}" onclick="pick('${c.url}')">
      <img src="${c.url}" onerror="this.parentElement.style.display='none'">
      ${d && c.url === d.current_artwork_url ? '<div class="tick">\u2713</div>' : ''}
    </div>`).join('') + '</div>';
}

async function fetchStats() {
  const r = await fetch('/api/stats');
  const s = await r.json();
  const el = document.getElementById('stats-content');

  const topCoversHtml = s.top_covers.length === 0
    ? '<p style="color:var(--muted);font-size:13px;margin-bottom:24px">No data yet</p>'
    : '<div class="top-covers">' + s.top_covers.map(c => `
        <div class="top-cover">
          <img src="${c.url}" onerror="this.parentElement.style.display='none'">
          <div class="play-count">${c.count}\u00d7</div>
        </div>`).join('') + '</div>';

  const historyHtml = s.history_by_day.length === 0
    ? '<p style="color:var(--muted);font-size:13px">No history yet</p>'
    : s.history_by_day.map(day => `
        <div class="history-day">
          <div class="history-date">${formatDate(day.date)}</div>
          ${day.entries.map(e => `
            <div class="history-entry">
              <img class="history-thumb" src="${e.artwork_url || ''}" onerror="this.style.display='none'">
              <div class="history-time">${e.ts.split(' ')[1]}</div>
              <div>
                <div class="history-artist">${e.artist}</div>
                <div class="history-title">${e.title}</div>
              </div>
            </div>`).join('')}
        </div>`).join('');

  el.innerHTML = `
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-value">${s.needle_drops}</div>
        <div class="stat-label">Needle Drops</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${s.unique_covers}</div>
        <div class="stat-label">Unique Covers</div>
      </div>
      <div class="stat-card full">
        <div class="stat-value" style="font-size:28px">${s.unique_artists}</div>
        <div class="stat-label">Unique Artists</div>
      </div>
    </div>
    <div class="section-label" style="margin-bottom:12px">Most Played</div>
    ${topCoversHtml}
    <div class="section-label" style="margin-bottom:12px">Listening History</div>
    ${historyHtml}
  `;
}

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const today = new Date();
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
  if (dateStr === today.toISOString().slice(0,10)) return 'Today';
  if (dateStr === yesterday.toISOString().slice(0,10)) return 'Yesterday';
  return d.toLocaleDateString('en-GB', {weekday:'long', day:'numeric', month:'long'});
}

async function pick(url) {
  await fetch('/api/select', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify({url})});
  fetchState();
}

async function setSetting(key, value) {
  await fetch('/api/settings', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify({[key]:value})});
}

async function resetSettings() {
  await fetch('/api/settings', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify({brightness:50, saturation:0.8, gamma:1.0})});
  fetchState();
}

async function uploadFile(input) {
  const file = input.files[0];
  if (!file) return;
  await sendImage(file);
  input.value = '';
}

async function sendImage(blob) {
  const feedback = document.getElementById('upload-feedback');
  const formData = new FormData();
  formData.append('image', blob);
  const r = await fetch('/api/upload_cover', {method: 'POST', body: formData});
  if (r.ok) {
    if (feedback) { feedback.style.display = 'block'; setTimeout(() => feedback.style.display = 'none', 2000); }
    renderCovers();
  }
}

// Paste from clipboard — works on desktop browsers
document.addEventListener('paste', async (e) => {
  if (currentTab !== 'covers') return;
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const blob = item.getAsFile();
      if (blob) await sendImage(blob);
      break;
    }
  }
});

fetchState();
setInterval(fetchState, 30000);
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/covers/<filename>")
def serve_cover(filename):
    path = os.path.join(COVERS_DIR, filename)
    if os.path.exists(path):
        return send_file(path, mimetype="image/jpeg")
    return "", 404


@app.route("/api/state")
def api_state():
    s = state.get()
    prefs = _load_prefs()
    return jsonify({
        "playing": s.playing,
        "artist": s.artist,
        "title": s.title,
        "album": s.album,
        "current_artwork_url": s.current_artwork_url,
        "artwork_candidates": s.artwork_candidates,
        "brightness": s.brightness,
        "saturation": s.saturation,
        "gamma": s.gamma,
        "prefs": prefs,
        "next_identify_in": s.next_identify_in,
    })


@app.route("/api/covers")
def api_covers():
    covers = []
    if os.path.exists(COVERS_DIR):
        files = sorted(glob.glob(os.path.join(COVERS_DIR, "*.jpg")),
                      key=os.path.getmtime, reverse=True)
        for f in files[:60]:
            covers.append({"url": f"/covers/{os.path.basename(f)}"})
    return jsonify(covers)


@app.route("/api/stats")
def api_stats():
    return jsonify(vstats.get_stats(COVERS_DIR))


@app.route("/api/upload_cover", methods=["POST"])
def api_upload_cover():
    """Accept uploaded image, crop to square, save to covers folder."""
    if 'image' not in request.files:
        return jsonify({"error": "no image"}), 400
    file = request.files['image']
    try:
        img = Image.open(io.BytesIO(file.read())).convert("RGB")
        # Crop to centre square
        w, h = img.size
        size = min(w, h)
        left = (w - size) // 2
        top  = (h - size) // 2
        img = img.crop((left, top, left + size, top + size))
        # Save at 800x800
        img = img.resize((800, 800), Image.LANCZOS)
        os.makedirs(COVERS_DIR, exist_ok=True)
        url_hash = hashlib.md5(file.filename.encode() if file.filename else b'upload').hexdigest()[:12]
        import time as _time
        path = os.path.join(COVERS_DIR, f"upload_{int(_time.time())}_{url_hash}.jpg")
        img.save(path, "JPEG", quality=95)
        log.info(f"User uploaded cover: {path}")
        return jsonify({"ok": True, "path": path})
    except Exception as e:
        log.error(f"Upload failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/select", methods=["POST"])
def api_select():
    data = request.get_json()
    url = data.get("url") if data else None
    log.info(f"Artwork selected: {url}")
    if url:
        state.update(preferred_artwork_url=url)
    return jsonify({"ok": True})


@app.route("/api/settings", methods=["POST"])
def api_settings():
    data = request.get_json()
    if "brightness" in data:
        state.update(brightness=int(data["brightness"]))
    if "saturation" in data:
        state.update(saturation=float(data["saturation"]))
    if "gamma" in data:
        state.update(gamma=float(data["gamma"]))
    return jsonify({"ok": True})


def start_server():
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False),
        daemon=True
    ).start()
    log.info("Web interface at http://raspberrypi3b.local:5000")
