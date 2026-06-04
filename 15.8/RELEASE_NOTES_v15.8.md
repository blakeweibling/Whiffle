# Whiffle Tracker — v15.8 Release Notes

**Release date:** May 2026  
**Previous public release:** [v15.7 — Showtime Ready Final Release](https://github.com/blakeweibling/Whiffle/releases/tag/v15.7) (March 26, 2026)

Whiffle Tracker is a computer-vision scoring system for Whiffle and Five Star playfields. Version **15.8** builds on the showtime-ready **15.7** feature set with a focus on **reliable Raspberry Pi deployment**, **stronger edge-case ball detection**, and **packaging fixes** for frozen Windows and Linux builds.

---

## At a glance: v15.8 vs v15.7

| Area | v15.7 (Showtime Ready) | v15.8 |
|------|------------------------|-------|
| **Primary platform** | Windows installer + source | Windows installer + **production Pi bundle** (`build_pi.sh`, `game.linux.spec`) |
| **Python on Pi** | Documented 3.10+; Pi profile basic | **Python 3.13** on Bookworm; numpy ABI handling in `build_pi.sh` |
| **Pi ball detection** | Platform-aware camera; generic low-power notes | **Automatic Pi detection** with tuned YOLO profile (`imgsz=960`, scale `0.5`, every 4th frame) and env overrides |
| **Edge / hole detection** | Strong on desktop (`imgsz=1920`) | Refined pipeline: near-zone bypass, HSV gates, temporal ghost filter; Pi profile avoids double letterbox decimation |
| **PyInstaller (frozen)** | Windows onedir + hiddenimports | **Linux/Pi spec**; `path_utils` bootstrap; expanded hiddenimports; conditional `.env` bundling |
| **Dependencies** | Broader `requirements.txt` | Trimmed unused packages; **cp313 / aarch64** version floors |

All **15.7 gameplay features** remain: playfield selection at launch, layout switching, operator remote (LAN PWA), per-player achievements, replays, Supabase leaderboard, versus mode, XP, and Inno Setup Windows installer.

---

## What’s new in v15.8

### Raspberry Pi — installable bundle

- **`build_pi.sh`** — One-shot build script for Pi 4/5 (aarch64, Bookworm). Creates a venv, installs dependencies with Python-version-aware numpy handling, removes **Triton** (crashes on ARM at import), validates `.env` and YOLO models, runs PyInstaller, and copies `.env` beside the executable for easy editing.
- **`game.linux.spec`** — Dedicated Linux/Pi PyInstaller spec: no strip/UPX on ARM (avoids silent Torch/OpenCV segfaults), explicit hiddenimports (`dotenv`, `requests`, `urllib3`, `httplib2`, `pygame.mixer`, etc.), **Triton excluded**, matplotlib kept for Ultralytics import chain.
- **`path_utils.py`** — Resolves bundled models/assets from `_internal/` when frozen; seeds writable `data/`, `configs/`, and `assets/` next to the binary; sets working directory so relative paths match dev layout.

### Raspberry Pi — detection profile

- **Automatic Pi detection** via `/proc/device-tree/model`, `/proc/cpuinfo`, with overrides:
  - `WHIFFLE_LOW_POWER=1|0` — force low-power profile on or off
  - `WHIFFLE_PI_IMGSZ=<int>` — YOLO letterbox size (default **960**; try **1280** for edge-case testing, **800** on Pi 4 if slow)
  - `WHIFFLE_PI_DETECTION_INTERVAL=<int>` — run detection every Nth frame (default **4**)
- **Balanced defaults** (vs the old Pi `imgsz=640` squeeze): half-resolution inference (`YOLO_INFERENCE_SCALE=0.5`) plus **`imgsz=960`** so YOLO’s letterbox matches the pre-resized frame width—recovering far-edge and leftmost-hole balls without the ~10× slowdown of full desktop settings.
- **Performance levers unchanged** at default: scale `0.5`, detect every **4th** frame—tune only via env vars when testing.

### Ball detection improvements (all platforms)

Refinements in `detection.py` and `constants.py` improve reliability for balls that were easy to miss in **15.7**, especially near table edges and in scoring holes:

- **Lower raw YOLO confidence** (`0.15`) with stricter downstream gates—surfaces dim / foreshortened balls, then filters false positives.
- **Near-zone bypass** (`NEAR_ZONE_BYPASS_MARGIN_PX=100`) — white/silver balls just outside a tightly drawn zone still report when YOLO confidence dips.
- **In-zone bypass** for unique balls (red / half-red) in holes—skips ghost and aspect filters that wrongly rejected resting balls.
- **HSV saturated-red gate** — separates real red plastic from brown wood / dial art, including inside zones.
- **Temporal ghost suppression** — locks wood-grain false positives seen from session start; **does not** lock real balls that land mid-game.
- **Half-red relabeling** — perspective-skewed white balls mislabeled as half-red are relabeled to white when HSV shows no saturated red.
- **Small-ball confirmation** bypass near zones so in-hole balls are not dropped after one flickering frame.
- **Debug audit trail** — set `WHIFFLE_DEBUG=1` for per-box `RAW YOLO` / rejection reasons and optional detection overlay.

### Packaging and build (Windows)

- **`game.spec`** — Conditional `.env` bundling (build no longer fails on fresh clones without `.env`); added hiddenimports: `dotenv`, `requests`, `urllib3`, `httplib2`, `pygame.mixer`; `operator_remote.py` and `path_utils.py` in analysis list.
- **`game.py`** — `bootstrap_frozen_paths()` at startup; `_resolve_env_path()` loads `.env` from `_MEIPASS` then beside the executable (Pi-friendly overrides without rebuild).
- **`WhiffleSetup.iss`** — Application version **15.8**.

### Dependencies

- **`requirements.txt`** — Floors raised for **Python 3.13** and **aarch64** wheels (`opencv-python>=4.10`, `pygame>=2.6`, `ultralytics>=8.3`, `scipy>=1.14`).
- Removed unused build-only / dead entries: `cx_Freeze`, `pickle-mixin`, `supabase` Python SDK (app uses REST via `requests`).

---

## Unchanged from v15.7 (still included)

- Playfield selection at launch (Whiffle / Five Star) and hot-swappable layouts with correct model + zones
- Game modes: Classic, Timed, Survival, Retro, Fun, Practice, Versus
- Operator Remote: LAN web UI, PIN auth, PWA install, session stats, heatmap access
- Replay system with YouTube, Google Drive, Discord sharing; delete confirmation
- Per-player achievements (scrollable) and play history
- Supabase online leaderboard + local fallback
- High-score proof screenshots (last 5 retained)
- 1080p / 720p display toggle
- Windows: PyInstaller onedir + Inno Setup installer

---

## Upgrade from v15.7

### Windows

1. Build with `pyinstaller game.spec --clean` (or use your existing pipeline).
2. Point Inno Setup at `dist/Whiffle/` and compile `WhiffleSetup.iss`.
3. Copy your existing `configs/`, scores, and zones from the old install directory—they remain compatible.

### Raspberry Pi (new in 15.8)

1. On the Pi (64-bit Bookworm, Python 3.11 or 3.13):
   ```bash
   cd 15.8
   chmod +x build_pi.sh
   ./build_pi.sh
   ```
2. Ensure repo root has `.env` (Supabase) and both models under `data/`.
3. Run: `cd dist/Whiffle && ./Whiffle`
4. Optional tuning without rebuild:
   ```bash
   WHIFFLE_PI_IMGSZ=1280 WHIFFLE_DEBUG=1 ./Whiffle
   ```

### Source / dev

```bash
pip install -r requirements.txt
python game.py
```

---

## Environment variables (reference)

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL`, `SUPABASE_KEY` | Online leaderboard (`.env` or environment) |
| `WHIFFLE_DEBUG=1` | Verbose detection logging + debug overlay |
| `WHIFFLE_LOW_POWER=0` | Disable Pi low-power profile (desktop-like detection on Pi) |
| `WHIFFLE_PI_IMGSZ` | Pi YOLO letterbox size (default `960`) |
| `WHIFFLE_PI_DETECTION_INTERVAL` | Pi detect every N frames (default `4`) |
| `WHIFFLE_CAMERA_INDEX`, `WHIFFLE_CAMERA_BACKEND` | Camera selection on Linux/Pi |

---

## Known limitations

- **PyInstaller bundles are arch-specific** — a Pi `dist/Whiffle/` build runs only on matching aarch64 Linux; Windows builds are for Windows only.
- **Pi detection trade-off** — default profile favors playable frame rate; edge holes that still miss on `imgsz=960` may need `WHIFFLE_PI_IMGSZ=1280` testing or `WHIFFLE_LOW_POWER=0` (much slower).
- **Operator Remote** — LAN/private network only; not exposed to the public internet by design.

---

## Links

- **Repository:** https://github.com/blakeweibling/Whiffle  
- **Previous release:** https://github.com/blakeweibling/Whiffle/releases/tag/v15.7  
- **Website:** https://www.whiffle.co  

---

## Suggested GitHub release title

**Whiffle Tracker v15.8 — Pi bundle, edge detection, packaging**

## Suggested GitHub release tag

`v15.8`
