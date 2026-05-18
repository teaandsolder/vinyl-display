# Vinyl Display

Drop the needle. Walk away.

Vinyl Display listens to your turntable via USB, identifies what's playing using Shazam, and displays the album artwork on a 64×64 LED matrix panel. A mobile web interface lets you browse your artwork library, correct any mismatches, and tune the display to your taste.

No phone required. No streaming. No subscriptions. Just your records.

---

## How It Looks

The matrix displays full-colour album artwork with a smooth crossfade between tracks. A web interface at `http://raspberrypi3b.local:5000` gives you full control from your phone.

---

## Hardware

| Component | Notes |
|---|---|
| Raspberry Pi 3B or 4 | Pi 3B tested and working |
| Fluance RT85 (or any turntable) | Any turntable with a phono output |
| Rega Fono Mini A2D | USB phono preamp — digitises the signal cleanly |
| Adafruit RGB Matrix Bonnet #3211 | Requires two solder mods (see below) |
| 64×64 HUB75 P4 LED matrix panel | P3-2121-64×64 or similar |
| 5V 4A PSU with barrel jack | Powers the matrix — do not power from Pi USB |
| USB-A to USB-B cable | Rega to Pi |

**Total cost:** ~£150–200 depending on sourcing.

---

## Bonnet Solder Mods

Two modifications are required for correct operation:

### 1. E Address Jumper (required for 64×64 panels)
Solder the E address jumper on the bonnet. Without this, only the top half of the panel will display.

### 2. PWM Quality Mod (eliminates flicker)
Solder a short wire between the **OE/GPIO4** and **GPIO18** pads on the bonnet header. This enables hardware PWM for the matrix clock, eliminating the scan-line flicker present without the mod.

After soldering, the Pi's onboard audio module must be disabled — it shares the same hardware PWM channel. Add to `/etc/modprobe.d/blacklist-rgb-matrix.conf`:

```
blacklist snd_bcm2835
```

This has no effect on USB audio devices like the Rega.

---

## Software Setup

### 1. OS
Install **Raspberry Pi OS Lite** (32-bit, Bookworm or Trixie) on a microSD card. Enable SSH and configure WiFi via Raspberry Pi Imager before first boot.

### 2. Python 3.11
ShazamIO requires Python 3.11. Raspberry Pi OS ships with an older version, so compile from source:

```bash
sudo apt update && sudo apt install -y build-essential libssl-dev libffi-dev \
  libsqlite3-dev zlib1g-dev libbz2-dev libreadline-dev libncurses-dev

wget https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tgz
tar xf Python-3.11.9.tgz && cd Python-3.11.9
./configure --enable-optimizations
make -j4   # takes ~2 hours on Pi 3B, ~30 mins on Pi 4
sudo make altinstall
```

Create a virtual environment:

```bash
python3.11 -m venv ~/venv311
```

### 3. rpi-rgb-led-matrix
Build the matrix library from source:

```bash
sudo apt install -y git
git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
cd rpi-rgb-led-matrix
git checkout 59a5e05
make build-python PYTHON=$(which python3.11)
cd bindings/python
~/venv311/bin/pip install -e .
```

### 4. Python Dependencies
```bash
~/venv311/bin/pip install sounddevice numpy requests Pillow flask shazamio
```

### 5. Disable Onboard Audio
```bash
echo "dtparam=audio=off" | sudo tee -a /boot/firmware/config.txt
sudo reboot
```

### 6. Clone and Configure
```bash
git clone https://github.com/teaandsolder/vinyl-display.git ~/vinyl-display
```

Edit `config.py` to match your setup — at minimum set `DEVICE_NAME` to match your USB audio device. Run `arecord -l` to list available devices.

### 7. Run
```bash
sudo -E ~/venv311/bin/python3 ~/vinyl-display/main.py
```

Add an alias to `~/.bashrc` for convenience:
```bash
alias vinyl='sudo -E ~/venv311/bin/python3 ~/vinyl-display/main.py'
```

### 8. Autostart on Boot (optional)
To start Vinyl Display automatically when the Pi powers on:

```bash
sudo nano /etc/systemd/system/vinyl.service
```

Paste:
```ini
[Unit]
Description=Vinyl Display
After=network.target sound.target

[Service]
ExecStart=/home/pi/venv311/bin/python3 /home/pi/vinyl-display/main.py
WorkingDirectory=/home/pi/vinyl-display
User=root
Environment="HOME=/home/pi"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable vinyl
sudo systemctl start vinyl
```

Check status:
```bash
sudo systemctl status vinyl
```

View live logs:
```bash
sudo journalctl -u vinyl -f
```

Stop the service (e.g. to run manually for debugging):
```bash
sudo systemctl stop vinyl
```

---

## Configuration

All user settings live in `config.py`. No other files need editing.

```python
# Audio
DEVICE_NAME = "CODEC"       # partial name of USB audio device
CAPTURE_SECONDS = 10        # audio capture duration for identification
SETTLE_SECONDS = 3          # settle time after needle drop

# Signal
SIGNAL_THRESHOLD = 150      # RMS below this = no signal

# Display
BRIGHTNESS = 50             # matrix brightness (0-100)
GPIO_SLOWDOWN = 2           # Pi 3B: 2, Pi 4: try 1
HARDWARE_MAPPING = "adafruit-hat-pwm"  # with PWM mod
SATURATION = 0.8            # colour saturation (1.0 = unchanged)
GAMMA = 1.0                 # gamma correction (1.0 = linear)

# Stats
STATS_ENABLED = True        # master switch for all stats
```

---

## Features

### Automatic Identification
- Listens continuously via USB audio
- Detects needle drop within 3 seconds
- Identifies tracks using ShazamIO — unlimited, no API key required
- Re-identifies every 30 seconds to update artwork between tracks
- Mono 16kHz capture minimises CPU/DMA load
- Three-state model: Sleeping → Listening → Playing

### Unidentified Tracks
- If Shazam can't match a track, the display shows a listening animation
- Web UI shows "Listening..." with instructions to manually push artwork
- Go to Saved Covers tab and tap any cover to display it immediately
- System keeps trying to identify — if it eventually matches, preference is saved automatically

### Artwork
- Fetches high-resolution artwork from Shazam and Cover Art Archive
- Saves all artwork locally — consistent colours, no URL expiry
- Same-artist rule: artwork stays stable across tracks on the same side
- Side-end detection resets cleanly for next record

### Artwork Preferences
- Tap any artwork in the web UI to set it as your preference
- Preferences saved by artist + track title — remembered forever
- Upload your own artwork from camera roll or paste from clipboard (desktop)
- Cached artwork loads instantly on subsequent plays

### Web Interface
Access at `http://vinyl.local:5000` (or whatever hostname you set)

- **Now Playing** — full artwork, track info, cached status, re-identify countdown, display settings
- **Saved Covers** — browse your full artwork library, tap to apply, upload your own
- **Stats** — needle drops, unique covers, unique artists, most played, listening history
- **Log** — live system log, colour coded by level — no SSH needed

### Display Controls
Live controls via the web interface:
- Brightness (0–100)
- Saturation (0–100%)
- Gamma (0–2.0)
- Reset to Default

### Stats Tracking
- All-time needle drop counter
- Listening history by day (artist changes only)
- Most played artwork
- Unique covers and artists

---

## Side-End Detection

The system uses a two-stage check to detect the end of a side:

1. RMS drops below threshold → wait 5 seconds → recheck
2. If truly silent (RMS < 50): reset immediately — needle lifted
3. If in run-out groove range: wait 25 seconds → recheck → reset

This handles quiet passages between tracks without false resets, and responds instantly when you lift the needle.

---

## File Structure

```
vinyl-display/
├── main.py           # Main loop — SLEEPING, LISTENING, PLAYING states
├── listener.py       # Audio capture (mono 16kHz)
├── identifier.py     # ShazamIO integration
├── art.py            # Artwork fetching and processing
├── display.py        # LED matrix driver
├── server.py         # Flask web interface (4 tabs)
├── state.py          # Shared state (thread-safe)
├── stats.py          # Stats tracking and persistence
└── config.py         # All user settings
```

Data is stored in:
```
~/vinyl-display-covers/          # saved artwork (JPEG, 800×800)
~/.vinyl-display/preferences.json  # artwork preferences by track
~/.vinyl-display/stats.json        # listening stats
```

---

## Troubleshooting

**Matrix shows nothing / only top half**
Check the E address jumper is soldered on the bonnet.

**Flickering / scan lines**
Ensure the GPIO4→GPIO18 PWM mod is soldered, `snd_bcm2835` is blacklisted, and `HARDWARE_MAPPING = "adafruit-hat-pwm"` in config.py.

**Audio device not found**
Run `arecord -l` on the Pi and check the device name matches `DEVICE_NAME` in config.py.

**ShazamIO not identifying**
Check your Pi has internet access. ShazamIO requires an outbound HTTPS connection.

**Permission denied on covers folder**
The app runs with sudo, so the covers folder is owned by root. Use `sudo rm` to delete files if needed.

**Saved covers disappear when running as systemd service**
The service runs as root, so `~` resolves to `/root/` instead of `/home/pi/`. Ensure `Environment="HOME=/home/pi"` is in the service file.

**Python version errors**
Ensure you're running with `~/venv311/bin/python3` — the system Python will not work.

---

## Credits

Built with:
- [ShazamIO](https://github.com/dotX12/ShazamIO) — track identification
- [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) — matrix driver
- [MusicBrainz](https://musicbrainz.org) — album metadata
- [Cover Art Archive](https://coverartarchive.org) — album artwork
- [Flask](https://flask.palletsprojects.com) — web interface

---

## Licence

MIT
