#!/usr/bin/env bash
# =================================================================
# BrokeLLM — Installer
# =================================================================
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BIN="$DIR/bin/broke"
MAPPING_PY="$DIR/bin/_mapping.py"
LOCKFILE="$DIR/requirements.lock"
WHEEL_DIR="$DIR/vendor/wheels"
USE_WHEEL_MIRROR=0
OFFLINE_INSTALL=0
REFRESH_MIRROR=0

# ── helpers ──────────────────────────────────────────────────────
ok()   { echo "  [ok]  $*"; }
info() { echo "  [--]  $*"; }
warn() { echo "  [!!]  $*"; }
die()  { echo "  [ERR] $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
    case "$1" in
        --mirror-wheels) REFRESH_MIRROR=1 ;;
        --use-wheel-mirror) USE_WHEEL_MIRROR=1 ;;
        --offline) OFFLINE_INSTALL=1; USE_WHEEL_MIRROR=1 ;;
        *)
            die "Unknown option: $1
  Supported: --mirror-wheels | --use-wheel-mirror | --offline"
            ;;
    esac
    shift
done

echo ""
echo "  BrokeLLM Installer"
echo "  ══════════════════"
echo ""

# ── Python ───────────────────────────────────────────────────────
PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)
[ -z "$PY" ] && die "Python 3.8+ required. Install it then re-run."

PY_VERSION=$("$PY" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
[ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]; } && \
    die "Python 3.8+ required (found $PY_VERSION)."
ok "Python $PY_VERSION"

[ -f "$LOCKFILE" ] || die "Missing lockfile: $LOCKFILE"
EXPECTED_LITELLM_VERSION="$(awk -F'==' '/^litellm\[proxy\]==/ {print $2; exit}' "$DIR/requirements.txt")"
[ -n "$EXPECTED_LITELLM_VERSION" ] || die "requirements.txt must pin litellm[proxy] exactly"

install_litellm() {
    local -a pip_args
    pip_args=(-m pip install --require-hashes -r "$LOCKFILE" --quiet)
    if [ "$USE_WHEEL_MIRROR" -eq 1 ]; then
        [ -d "$WHEEL_DIR" ] || die "Wheel mirror requested but missing: $WHEEL_DIR"
        pip_args+=(--find-links "$WHEEL_DIR")
    fi
    if [ "$OFFLINE_INSTALL" -eq 1 ]; then
        pip_args+=(--no-index)
    fi
    "$PY" "${pip_args[@]}" || die "pip install failed. Check $LOCKFILE and wheel mirror state."
}

mirror_wheels() {
    mkdir -p "$WHEEL_DIR"
    info "Mirroring locked wheels into $WHEEL_DIR ..."
    "$PY" -m pip download --require-hashes -r "$LOCKFILE" -d "$WHEEL_DIR" --quiet || \
        die "wheel mirroring failed. Try again with network access or refresh the lockfile."
    ok "Wheel mirror refreshed"
}

[ "$REFRESH_MIRROR" -eq 1 ] && mirror_wheels

# ── litellm ──────────────────────────────────────────────────────
if command -v litellm &>/dev/null; then
    INSTALLED_LITELLM_VERSION=$("$PY" -m pip show litellm 2>/dev/null | awk -F': ' '/^Version:/ {print $2; exit}')
    if [ "$INSTALLED_LITELLM_VERSION" = "$EXPECTED_LITELLM_VERSION" ]; then
        ok "litellm $INSTALLED_LITELLM_VERSION"
    else
        info "Reinstalling LiteLLM to pinned version $EXPECTED_LITELLM_VERSION ..."
        install_litellm
        ok "litellm pinned to $EXPECTED_LITELLM_VERSION"
    fi
else
    info "Installing locked LiteLLM dependencies..."
    install_litellm
    ok "litellm installed"
fi

# ── make executables ─────────────────────────────────────────────
chmod +x "$BIN" "$MAPPING_PY"

# ── symlink broke into PATH ───────────────────────────────────────
DEST=""
for d in "$HOME/.local/bin" "$HOME/bin" /usr/local/bin; do
    if [[ ":$PATH:" == *":$d:"* ]] || [ -d "$d" ]; then
        DEST="$d"
        break
    fi
done
[ -z "$DEST" ] && { mkdir -p "$HOME/.local/bin"; DEST="$HOME/.local/bin"; }

ln -sf "$BIN" "$DEST/broke"
ok "Linked broke → $DEST/broke"

# ── .env ─────────────────────────────────────────────────────────
if [ ! -f "$DIR/.env" ]; then
    cp "$DIR/.env.template" "$DIR/.env"
    chmod 600 "$DIR/.env" 2>/dev/null || true
    warn ".env created from template — fill in your API keys:"
    warn "    $DIR/.env"
else
    chmod 600 "$DIR/.env" 2>/dev/null || true
    ok ".env already exists"
fi

# ── initialise mapping ───────────────────────────────────────────
python3 "$MAPPING_PY" init
ok "Default routing initialised"

# ── verify ───────────────────────────────────────────────────────
echo ""
if command -v broke &>/dev/null; then
    ok "broke is on PATH"
else
    warn "broke not found on PATH. Add this to your shell profile:"
    warn "    export PATH=\"$DEST:\$PATH\""
fi

echo ""
echo "  ── Next steps ─────────────────────────────────────────"
echo "  1. Fill in API keys:    $DIR/.env"
echo "  2. Start:               broke"
echo "  3. Change routing:      broke swap"
echo "  4. Save a config:       broke team save <name> [cli|route]"
echo "  5. Share a config:      broke export myconfig.json"
echo "  6. Import a config:     broke import myconfig.json"
echo "  7. Mirror wheels:       ./install.sh --mirror-wheels"
echo "  8. Offline install:     ./install.sh --offline"
echo "  9. Full help:           broke help"
echo ""
