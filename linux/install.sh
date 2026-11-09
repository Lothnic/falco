#!/usr/bin/env bash
# Install the community Linux app in the current user's account.
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_base="${PHONON_INSTALL_BASE:-$HOME/.local/share/phonon-linux-app}"
bin_dir="${PHONON_BIN_DIR:-$HOME/.local/bin}"
desktop_dir="${PHONON_DESKTOP_DIR:-$HOME/.local/share/applications}"
release_dir="$install_base/releases/0.1.0"
if [[ -e "$release_dir" ]]; then
    printf 'Install directory already exists: %s\nRemove or move it before reinstalling.\n' "$release_dir" >&2
    exit 1
fi
if [[ -e "$bin_dir/phonon-linux" || -L "$bin_dir/phonon-linux" || -e "$desktop_dir/phonon-linux-community.desktop" ]]; then
    printf 'A phonon-linux command or launcher already exists. Move it before installing.\n' >&2
    exit 1
fi
for module in gi dbus; do
    if ! /usr/bin/python3 -c "import $module" 2>/dev/null; then
        printf 'Missing system Python module %s; see README.md for system packages.\n' "$module" >&2
        exit 1
    fi
done
mkdir -p "$release_dir" "$bin_dir" "$desktop_dir"
cp -a "$source_dir/src" "$source_dir/pyproject.toml" "$source_dir/README.md" "$source_dir/LICENSE" "$release_dir/"
/usr/bin/python3 -m venv --system-site-packages "$release_dir/.venv"
if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$release_dir/.venv/bin/python" "$release_dir"
else
    "$release_dir/.venv/bin/python" -m pip install "$release_dir"
fi
mkdir -p "$release_dir/bin"
for binary in phonon-overlay phonon-window; do
    if [[ -x "$source_dir/rune-overlay/target/release/$binary" ]]; then
        install -m 755 "$source_dir/rune-overlay/target/release/$binary" "$release_dir/bin/$binary"
    fi
done
cat > "$release_dir/run.sh" <<RUNNER
#!/usr/bin/env bash
export DEV_MODE=1
if [[ -x "$release_dir/bin/phonon-overlay" ]]; then
    export PHONON_RUNE_OVERLAY="\${PHONON_RUNE_OVERLAY:-$release_dir/bin/phonon-overlay}"
fi
exec "$release_dir/.venv/bin/python" -m localdictation.tray "\$@"
RUNNER
chmod 755 "$release_dir/run.sh"
launcher="$release_dir/run.sh"
if [[ -x "$release_dir/bin/phonon-window" ]]; then
    cat > "$release_dir/run-ui.sh" <<RUNNER
#!/usr/bin/env bash
if ! "$release_dir/.venv/bin/python" -c 'import dbus,sys; sys.exit(0 if dbus.SessionBus().name_has_owner("local.PhononLinux.App") else 1)' 2>/dev/null; then
    "$release_dir/run.sh" </dev/null >/dev/null 2>&1 &
fi
export PHONON_PYTHON="$release_dir/.venv/bin/python"
export PHONON_BRIDGE_MODULE=localdictation.ui_bridge
exec "$release_dir/bin/phonon-window" "\$@"
RUNNER
    chmod 755 "$release_dir/run-ui.sh"
    launcher="$release_dir/run-ui.sh"
fi
ln -sfn "$launcher" "$bin_dir/phonon-linux"
cat > "$desktop_dir/phonon-linux-community.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Phonon Linux
Comment=Local voice dictation and transcript cleanup
Exec="$launcher"
Icon=audio-input-microphone
Terminal=false
Categories=Utility;Accessibility;
StartupNotify=false
DESKTOP
printf '\nInstalled Phonon Linux. Start it from your applications or run %s/phonon-linux.\n' "$bin_dir"
printf 'On first run, download a speech model, then enable the Phonon refiner in Preferences → Advanced.\n'
