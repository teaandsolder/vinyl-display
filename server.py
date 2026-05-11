#!/usr/bin/env python3
"""
Flask web server — mobile control panel for Vinyl Display.
Access at http://raspberrypi3b.local:5000
"""

import logging
import threading
import json
import os
import glob
from flask import Flask, jsonify, request, render_template_string, send_file
from state import state
from art import AlbumArtFetcher

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


HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
  <title>Vinyl Display</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #111; color: #eee;
      font-family: -apple-system, BlinkMacSystemFont, sans-serif;
      padding: 16px; max-width: 480px; margin: 0 auto;
    }
    h1 { font-size: 20px; font-weight: 700; color: #fff; margin-bottom: 2px; }
    .sub { font-size: 13px; color: #666; margin-bottom: 20px; }
    .section { font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
               color: #555; margin-bottom: 10px; }

    /* Artwork grids */
    .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 24px; }
    .cover {
      position: relative; cursor: pointer; border-radius: 6px;
      overflow: hidden; border: 2px solid transparent; aspect-ratio: 1;
      background: #1a1a1a;
    }
    .cover.selected { border-color: #e06060; }
    .cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .cover .tick {
      position: absolute; top: 4px; right: 4px; background: #e06060;
      color: #fff; font-size: 10px; font-weight: 700;
      border-radius: 3px; padding: 2px 5px;
    }

    /* Settings dropdown */
    .dropdown { background: #1a1a1a; border-radius: 10px; margin-bottom: 10px; overflow: hidden; }
    .dh { display: flex; align-items: center; justify-content: space-between;
          padding: 14px; cursor: pointer; }
    .dt { font-size: 14px; font-weight: 600; color: #888; }
    .ch { color: #555; transition: transform 0.2s; }
    .ch.open { transform: rotate(90deg); }
    .db { display: none; padding: 0 14px 14px; }
    .db.open { display: block; }
    .ctrl { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
    .clabel { font-size: 13px; color: #888; width: 80px; flex-shrink: 0; }
    input[type=range] { flex: 1; accent-color: #e06060; }
    .cval { font-size: 13px; color: #eee; width: 40px; text-align: right; }

    .idle { text-align: center; color: #444; padding: 80px 0; font-size: 15px; }
    .empty { font-size: 13px; color: #444; padding: 8px 0; }
  </style>
</head>
<body>
  <div id="app"><div class="idle">Loading...</div></div>
<script>
let d = null;
let settingsOpen = false;

async function fetchState() {
  const r = await fetch('/api/state');
  d = await r.json();
  render(d);
}

function render(d) {
  const app = document.getElementById('app');
  if (!d.playing) {
    app.innerHTML = '<div class="idle">🎵 Drop the needle to begin</div>';
    return;
  }

  // Current candidates grid
  const candidates = d.artwork_candidates || [];
  const candGrid = candidates.length === 0
    ? '<div class="empty">Gathering artwork...</div>'
    : '<div class="grid">' + candidates.map(c => `
        <div class="cover ${c.url === d.current_artwork_url ? 'selected' : ''}"
             onclick="pick('${c.url}')">
          <img src="${c.url}" onerror="this.parentElement.style.display='none'">
          ${c.url === d.current_artwork_url ? '<div class="tick">✓</div>' : ''}
        </div>`).join('') + '</div>';

  // Saved covers grid
  const saved = d.saved_covers || [];
  const savedGrid = saved.length === 0
    ? '<div class="empty">No saved covers yet</div>'
    : '<div class="grid">' + saved.map(c => `
        <div class="cover ${c.url === d.current_artwork_url ? 'selected' : ''}"
             onclick="pick('${c.url}')">
          <img src="${c.url}" onerror="this.parentElement.style.display='none'">
          ${c.url === d.current_artwork_url ? '<div class="tick">✓</div>' : ''}
        </div>`).join('') + '</div>';

  app.innerHTML = `
    <h1>${d.artist}</h1>
    <div class="sub">${d.album || d.title}</div>

    <div class="section">Now Playing</div>
    ${candGrid}

    <div class="section">Saved Covers</div>
    ${savedGrid}

    <div class="dropdown" style="margin-top:20px">
      <div class="dh" onclick="toggleSettings()">
        <span class="dt">⚙ Display Settings</span>
        <span class="ch ${settingsOpen ? 'open' : ''}">▶</span>
      </div>
      <div class="db ${settingsOpen ? 'open' : ''}">
        <div class="ctrl">
          <span class="clabel">Brightness</span>
          <input type="range" min="10" max="100" value="${d.brightness}"
            oninput="setSetting('brightness',+this.value);this.nextElementSibling.textContent=this.value">
          <span class="cval">${d.brightness}</span>
        </div>
        <div class="ctrl">
          <span class="clabel">Saturation</span>
          <input type="range" min="0" max="100" value="${Math.round(d.saturation*100)}"
            oninput="setSetting('saturation',this.value/100);this.nextElementSibling.textContent=this.value+'%'">
          <span class="cval">${Math.round(d.saturation*100)}%</span>
        </div>
      </div>
    </div>
  `;
}

function toggleSettings() {
  settingsOpen = !settingsOpen;
  render(d);
}

async function pick(url) {
  await fetch('/api/select', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({url})});
  fetchState();
}

async function setSetting(key, value) {
  await fetch('/api/settings', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({[key]: value})});
}

fetchState();
setInterval(fetchState, 15000);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/covers/<filename>")
def serve_cover(filename):
    """Serve saved cover images."""
    path = os.path.join(COVERS_DIR, filename)
    if os.path.exists(path):
        return send_file(path, mimetype="image/jpeg")
    return "", 404


@app.route("/api/state")
def api_state():
    s = state.get()
    # List saved covers as local URLs
    saved_covers = []
    if os.path.exists(COVERS_DIR):
        files = sorted(glob.glob(os.path.join(COVERS_DIR, "*.jpg")), 
                      key=os.path.getmtime, reverse=True)
        for f in files[:30]:  # last 30
            filename = os.path.basename(f)
            saved_covers.append({"url": f"/covers/{filename}"})

    return jsonify({
        "playing": s.playing,
        "artist": s.artist,
        "title": s.title,
        "album": s.album,
        "current_artwork_url": s.current_artwork_url,
        "artwork_candidates": s.artwork_candidates,
        "brightness": s.brightness,
        "saturation": s.saturation,
        "saved_covers": saved_covers,
    })


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
    return jsonify({"ok": True})


def start_server():
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False),
        daemon=True
    ).start()
    log.info("Web interface at http://raspberrypi3b.local:5000")
