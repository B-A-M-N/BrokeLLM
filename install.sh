#!/usr/bin/env bash
# =================================================================
# BrokeLLM — Installer
# =================================================================
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BIN="$DIR/bin/broke"
MAPPING_PY="$DIR/bin/_mapping.py"

# ── helpers ──────────────────────────────────────────────────────
ok()   { echo "  [ok]  $*"; }
info() { echo "  [--]  $*"; }
warn() { echo "  [!!]  $*"; }
die()  { echo "  [ERR] $*" >&2; exit 1; }

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

# ── litellm ──────────────────────────────────────────────────────
if command -v litellm &>/dev/null; then
    ok "litellm $(litellm --version 2>/dev/null | head -1 || echo 'installed')"
else
    info "Installing litellm[proxy]..."
    "$PY" -m pip install -r "$DIR/requirements.txt" --quiet || \
        die "pip install failed. Try: pip install 'litellm[proxy]' manually."
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
    warn ".env created from template — fill in your API keys:"
    warn "    $DIR/.env"
else
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
echo "  7. Full help:           broke help"
echo ""
