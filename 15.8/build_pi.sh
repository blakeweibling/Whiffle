#!/usr/bin/env bash
# build_pi.sh
# One-shot build script for the Raspberry Pi PyInstaller bundle.
# Run this ON THE PI (Pi 5 / Bookworm 64-bit / Python 3.13 expected; 3.11 also supported).
# Produces dist/Whiffle/ -- copy that whole folder to any matching Pi and run ./Whiffle.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

# --- Sanity checks -----------------------------------------------------------

if [[ "$(uname -m)" != "aarch64" ]]; then
    echo "WARNING: this script is intended for aarch64 (Pi 4/5 64-bit)."
    echo "         You appear to be on $(uname -m). The PyInstaller bundle will"
    echo "         only run on machines with the same architecture as this one."
    read -r -p "Continue anyway? [y/N] " ans
    [[ "${ans,,}" == "y" || "${ans,,}" == "yes" ]] || exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is not installed. Try: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

PY_VERSION="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
PY_MAJOR="${PY_VERSION%%.*}"
PY_MINOR="${PY_VERSION##*.}"
echo "[1/5] Using Python $PY_VERSION at $(command -v python3)"

# Game requires Python >= 3.10. Hard-fail on anything older so we don't waste
# 20 minutes of build time before discovering the version is unsupported.
if (( PY_MAJOR < 3 )) || { (( PY_MAJOR == 3 )) && (( PY_MINOR < 10 )); }; then
    echo "ERROR: Python >= 3.10 is required (found $PY_VERSION)."
    echo "       On Bookworm: sudo apt install python3.13 python3.13-venv python3.13-dev"
    exit 1
fi

# --- System packages PyInstaller will end up bundling ------------------------
# These give us a working OpenCV + pygame + camera + display stack on Bookworm.
# Safe to re-run (apt is idempotent).
echo "[2/5] Ensuring required apt packages are installed..."
sudo apt update
sudo apt install -y \
    python3-venv python3-pip python3-dev \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    libatlas-base-dev libopenblas0 \
    libsdl2-2.0-0 libsdl2-mixer-2.0-0 libsdl2-image-2.0-0 libsdl2-ttf-2.0-0 \
    libcamera-apps v4l-utils \
    upx-ucl || true   # not used by spec but harmless

# --- Build venv --------------------------------------------------------------

VENV_DIR="$REPO_DIR/.build-venv"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "[3/5] Creating build venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
else
    echo "[3/5] Reusing build venv at $VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip wheel setuptools

echo "[4/5] Installing runtime + build dependencies into venv..."
# numpy ABI handling:
#   * Python 3.10/3.11: the prebuilt aarch64 Torch + OpenCV wheels published
#     for cp310/cp311 were built against the numpy 1.x ABI, so we pin <2.
#   * Python 3.12+: numpy 1.x publishes no cp312/cp313 aarch64 wheels, and the
#     current Torch (>=2.5) / opencv-python (>=4.10) ARM wheels are built
#     against numpy 2.x. Let pip resolve numpy from requirements.txt.
if (( PY_MINOR <= 11 )); then
    echo "       Python $PY_VERSION detected -- pinning numpy<2 for legacy ARM wheel ABI."
    pip install "numpy<2"
else
    echo "       Python $PY_VERSION detected -- using numpy 2.x (required by cp${PY_MAJOR}${PY_MINOR} aarch64 wheels)."
fi
pip install -r requirements.txt
pip install pyinstaller

# --- Run PyInstaller ---------------------------------------------------------

echo "[5/5] Running PyInstaller (this is the slow step -- 10-30 min on a Pi 5)..."
rm -rf build dist
pyinstaller --noconfirm --clean game.linux.spec

# --- Summary -----------------------------------------------------------------

OUTPUT_DIR="$REPO_DIR/dist/Whiffle"
if [[ ! -x "$OUTPUT_DIR/Whiffle" ]]; then
    echo
    echo "ERROR: build finished but $OUTPUT_DIR/Whiffle is missing or not executable."
    exit 2
fi

BUNDLE_SIZE="$(du -sh "$OUTPUT_DIR" | cut -f1)"

echo
echo "============================================================"
echo "  Build complete."
echo "  Bundle:  $OUTPUT_DIR"
echo "  Size:    $BUNDLE_SIZE"
echo
echo "  To test on this Pi:"
echo "      cd $OUTPUT_DIR && ./Whiffle"
echo
echo "  To deploy to another Pi (must be same arch / OS):"
echo "      tar -C dist -czf Whiffle-pi.tar.gz Whiffle"
echo "      scp Whiffle-pi.tar.gz pi@other-pi:~/"
echo "      ssh pi@other-pi 'tar -xzf Whiffle-pi.tar.gz && ./Whiffle/Whiffle'"
echo "============================================================"
