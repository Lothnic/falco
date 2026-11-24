#!/usr/bin/env bash
# Install or upgrade the Linux app in the current user's account.
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_base="$(realpath -m -- "${PHONON_INSTALL_BASE:-$HOME/.local/share/falco-app}")"
bin_dir="$(realpath -m -- "${PHONON_BIN_DIR:-$HOME/.local/bin}")"
desktop_dir="$(realpath -m -- "${PHONON_DESKTOP_DIR:-$HOME/.local/share/applications}")"
bin_path="$bin_dir/falco"
desktop_path="$desktop_dir/falco.desktop"
release_dir=""
launcher=""
link_stage=""
desktop_stage=""
desktop_existed=0

desktop_exec() {
    local path="$1"
    path="${path//\\/\\\\}"
    path="${path//\"/\\\"}"
    path="${path//\$/\\\$}"
    path="${path//\`/\\\`}"
    path="${path//%/%%}"
    path="${path//\\/\\\\}"
    printf 'Exec="%s"' "$path"
}

cleanup() {
    if [[ -n "$release_dir" && ( -z "$launcher" ||
        "$(readlink -- "$bin_path" || true)" != "$launcher" ) ]]; then
        rm -rf -- "$release_dir"
        if [[ "$desktop_existed" == 0 && -n "$desktop_stage" && ! -e "$desktop_stage" ]]; then
            rm -f -- "$desktop_path"
        fi
    fi
    if [[ -n "$link_stage" ]]; then
        rm -rf -- "$link_stage"
    fi
    if [[ -n "$desktop_stage" ]]; then
        rm -f -- "$desktop_stage"
    fi
}

for module in gi dbus; do
    if ! /usr/bin/python3 -c "import $module" 2>/dev/null; then
        printf 'Missing system Python module %s; see README.md for system packages.\n' "$module" >&2
        exit 1
    fi
done

mkdir -p -- "$install_base/releases" "$bin_dir" "$desktop_dir"
exec 9>"$install_base/install.lock"
flock -x 9

old_launcher=""
if [[ -e "$bin_path" || -L "$bin_path" ]]; then
    if [[ ! -L "$bin_path" ]]; then
        printf 'Move the existing command %s before installing.\n' "$bin_path" >&2
        exit 1
    fi
    old_launcher="$(readlink -f -- "$bin_path" || true)"
    case "$old_launcher" in
        "$install_base"/releases/*/run.sh | "$install_base"/releases/*/run-ui.sh) ;;
        *)
            printf 'The command %s belongs to another installation. Move it before installing.\n' "$bin_path" >&2
            exit 1
            ;;
    esac
fi

exec_line="$(desktop_exec "$bin_path")"
if [[ -e "$desktop_path" || -L "$desktop_path" ]]; then
    desktop_existed=1
    if [[ ! -f "$desktop_path" || -L "$desktop_path" ]] ||
        { ! grep -Fxq -- "$exec_line" "$desktop_path" &&
          { [[ -z "$old_launcher" ]] ||
            ! grep -Fxq -- "Exec=\"$old_launcher\"" "$desktop_path"; }; }; then
        printf 'Move the existing desktop entry %s before installing.\n' "$desktop_path" >&2
        exit 1
    fi
fi

version="$(sed -n 's/^version = "\([0-9A-Za-z][0-9A-Za-z.+-]*\)"$/\1/p' "$source_dir/pyproject.toml")"
if [[ ! "$version" =~ ^[0-9A-Za-z][0-9A-Za-z.+-]*$ ]]; then
    printf 'Could not read the Falco package version.\n' >&2
    exit 1
fi

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# A venv contains absolute paths, so build it at its final path. The command
# continues to point to the previous release until the new one is complete.
release_dir="$(mktemp -d "$install_base/releases/$version.XXXXXX")"
cp -a "$source_dir/src" "$source_dir/pyproject.toml" "$source_dir/README.md" "$source_dir/LICENSE" "$release_dir/"
/usr/bin/python3 -m venv --system-site-packages "$release_dir/.venv"
if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$release_dir/.venv/bin/python" "$release_dir"
else
    "$release_dir/.venv/bin/python" -m pip install "$release_dir"
fi

mkdir -p -- "$release_dir/bin"
# Each Python release gets its matching UI. Never mix a new service with an
# old dashboard merely because a binary was cached by an earlier installer.
shared_rune="$install_base/rune/$version"
if /usr/bin/python3 "$source_dir/src/localdictation/ui_bundle.py" \
    --version "$version" --cache "$shared_rune" \
    --built "$source_dir/rune-overlay/target/release"; then
    for binary in phonon-overlay phonon-window VERSION; do
        ln -sfn -- "$shared_rune/$binary" "$release_dir/bin/$binary"
    done
fi
cat > "$release_dir/run.sh" <<'RUNNER'
#!/usr/bin/env bash
set -e
release_dir="$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")"
if [[ -x "$release_dir/bin/phonon-overlay" ]]; then
    export PHONON_RUNE_OVERLAY="${PHONON_RUNE_OVERLAY:-$release_dir/bin/phonon-overlay}"
fi
exec "$release_dir/.venv/bin/python" -m localdictation.cli "$@"
RUNNER
chmod 755 "$release_dir/run.sh"
launcher="$release_dir/run.sh"
if [[ -x "$release_dir/bin/phonon-window" ]]; then
    cat > "$release_dir/run-ui.sh" <<'RUNNER'
#!/usr/bin/env bash
set -e
release_dir="$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")"
if ! "$release_dir/.venv/bin/python" -c 'import dbus,sys; sys.exit(0 if dbus.SessionBus().name_has_owner("local.PhononLinux.App") else 1)' 2>/dev/null; then
    "$release_dir/run.sh" </dev/null >/dev/null 2>&1 &
fi
export PHONON_PYTHON="$release_dir/.venv/bin/python"
export PHONON_BRIDGE_MODULE=localdictation.ui_bridge
exec "$release_dir/bin/phonon-window" "$@"
RUNNER
    chmod 755 "$release_dir/run-ui.sh"
    launcher="$release_dir/run-ui.sh"
fi

link_stage="$(mktemp -d "$bin_dir/.falco-command.XXXXXX")"
ln -s -- "$launcher" "$link_stage/falco"
desktop_stage="$(mktemp "$desktop_dir/.falco-desktop.XXXXXX")"
cat > "$desktop_stage" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Falco
Comment=Local voice dictation and transcript cleanup
$exec_line
Icon=audio-input-microphone
Terminal=false
Categories=Utility;Accessibility;
StartupNotify=false
DESKTOP
chmod 644 "$desktop_stage"
mv -Tf -- "$desktop_stage" "$desktop_path"
mv -Tf -- "$link_stage/falco" "$bin_path"

printf '\nInstalled Falco %s. Start it from your applications or run %s.\n' "$version" "$bin_path"
printf 'On first run, download the default speech model (about 670 MB).\n'
printf 'The optional refiner in Preferences → Advanced adds about 1 GB.\n'
