#!/bin/bash
set -euo pipefail

usage() {
    echo "Usage: $0 /path/to/input.slf [data_root]"
    echo
    echo "Environment overrides:"
    echo "  PYTHON_BIN=python"
    echo "  CONDA_ENV=fastapi"
    echo "  CONDA_EXE=/home1/ncloud/miniconda3/bin/conda"
    echo "  UV_TIME_INDICES=all"
    echo "  FLOOD_TIME_INDICES=all"
    echo "  UV_MIN_ZOOM=6 UV_MAX_ZOOM=10"
    echo "  FLOOD_MIN_ZOOM=11 FLOOD_MAX_ZOOM=13"
    echo "  CLEAN_SUBSET_CACHE=0"
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
    usage
    exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SLF_PATH="$1"
DATA_ROOT="${2:-$HOME/data}"

PYTHON_BIN="${PYTHON_BIN:-python}"
CONDA_ENV="${CONDA_ENV:-}"
CONDA_EXE="${CONDA_EXE:-/home1/ncloud/miniconda3/bin/conda}"
UV_TIME_INDICES="${UV_TIME_INDICES:-all}"
FLOOD_TIME_INDICES="${FLOOD_TIME_INDICES:-all}"
UV_MIN_ZOOM="${UV_MIN_ZOOM:-6}"
UV_MAX_ZOOM="${UV_MAX_ZOOM:-10}"
FLOOD_MIN_ZOOM="${FLOOD_MIN_ZOOM:-11}"
FLOOD_MAX_ZOOM="${FLOOD_MAX_ZOOM:-13}"
CLEAN_SUBSET_CACHE="${CLEAN_SUBSET_CACHE:-0}"

UV_OUTPUT="$DATA_ROOT/tiles_uv_time"
FLOOD_OUTPUT="$DATA_ROOT/flood_tiles_time"

run_python_module() {
    if [[ -n "$CONDA_ENV" ]]; then
        "$CONDA_EXE" run -n "$CONDA_ENV" --no-capture-output python -m "$@"
    else
        "$PYTHON_BIN" -m "$@"
    fi
}

if [[ ! -f "$SLF_PATH" ]]; then
    echo "SLF file not found: $SLF_PATH" >&2
    exit 1
fi

mkdir -p "$DATA_ROOT"

if [[ "$CLEAN_SUBSET_CACHE" == "1" ]]; then
    echo "[subset] cleaning generated time-based UV/Flood cache"
    rm -rf "$UV_OUTPUT" "$FLOOD_OUTPUT"
fi

cd "$ROOT_DIR"

echo "[subset] source: $SLF_PATH"
echo "[subset] data root: $DATA_ROOT"
echo "[subset] building UV tiles -> $UV_OUTPUT"
run_python_module app.scripts.build_uv_tiles \
    --slf "$SLF_PATH" \
    --output "$UV_OUTPUT" \
    --min-z "$UV_MIN_ZOOM" \
    --max-z "$UV_MAX_ZOOM" \
    --time-indices "$UV_TIME_INDICES"

echo "[subset] building flood tiles -> $FLOOD_OUTPUT"
run_python_module app.scripts.build_flood_tiles \
    --slf "$SLF_PATH" \
    --output "$FLOOD_OUTPUT" \
    --min-z "$FLOOD_MIN_ZOOM" \
    --max-z "$FLOOD_MAX_ZOOM" \
    --time-indices "$FLOOD_TIME_INDICES"

echo "[subset] complete"
