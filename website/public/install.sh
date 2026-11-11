#!/usr/bin/env bash
# Falco installer for Linux.
#
#   curl -fsSL https://falco.lothnic.dev/install.sh | bash
#
# Installs system dependencies, then Falco itself under the current user's
# account. See --help for options.
set -euo pipefail

REPO="Lothnic/falco"
REF="${FALCO_REF:-main}"
ASSUME_YES=0
SKIP_DEPS=0
WITH_RUNE=0
TMP_DIR=""

say() {
    printf '%s\n' "$*"
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Install Falco for the current user.

Usage: install.sh [options]

Options:
  -y, --yes        Install required system packages without asking.
      --no-deps    Skip system packages; install them yourself first.
      --with-rune  Build the optional Rune dashboard and overlay.
      --ref REF    Install a branch, tag, or commit (default: main).
  -h, --help       Show this help.

Environment:
  FALCO_REF             Same as --ref.
  PHONON_INSTALL_BASE   Install root (default: ~/.local/share/falco-app).
  PHONON_BIN_DIR        Command directory (default: ~/.local/bin).
  PHONON_DESKTOP_DIR    Desktop-entry directory.

Examples:
  curl -fsSL https://falco.lothnic.dev/install.sh | bash
  curl -fsSL https://falco.lothnic.dev/install.sh | bash -s -- --with-rune
EOF
}

parse_args() {
    while (($#)); do
        case "$1" in
            -y | --yes) ASSUME_YES=1 ;;
            --no-deps) SKIP_DEPS=1 ;;
            --with-rune) WITH_RUNE=1 ;;
            --ref)
                (($# >= 2)) || die "--ref needs a value"
                REF="$2"
                shift
                ;;
            --ref=*) REF="${1#*=}" ;;
            -h | --help)
                usage
                exit 0
                ;;
            *) die "unknown option: $1 (try --help)" ;;
        esac
        shift
    done

    [[ "$REF" =~ ^[A-Za-z0-9][A-Za-z0-9._/~-]*$ ]] ||
        die "invalid --ref value: $REF"
    [[ "$REF" != *..* ]] || die "invalid --ref value: $REF"
}

require_user() {
    [[ "$(uname -s)" == "Linux" ]] || die "Falco is a Linux app."
    ((EUID != 0)) ||
        die "Run this as your normal user, not root; Falco installs into your home directory."
    for command in curl tar; do
        command -v "$command" >/dev/null 2>&1 ||
            die "$command is required but was not found."
    done
}

check_existing() {
    local install_base="${PHONON_INSTALL_BASE:-$HOME/.local/share/falco-app}"
    local bin_dir="${PHONON_BIN_DIR:-$HOME/.local/bin}"
    local desktop_dir="${PHONON_DESKTOP_DIR:-$HOME/.local/share/applications}"

    if [[ -e "$install_base/releases/0.1.0" || -e "$bin_dir/falco" ||
        -L "$bin_dir/falco" || -e "$desktop_dir/falco.desktop" ]]; then
        die "Falco already appears to be installed.
Remove $bin_dir/falco, $desktop_dir/falco.desktop, and $install_base
before reinstalling."
    fi
}

apt_missing_packages() {
    local package
    for package in \
        python3 python3-venv python3-pip python3-gi python3-gi-cairo \
        python3-dbus python3-evdev gir1.2-gtk-3.0 \
        gir1.2-ayatanaappindicator3-0.1 libportaudio2 wl-clipboard; do
        if ! dpkg-query -W -f='${Status}' "$package" 2>/dev/null |
            grep -q 'ok installed'; then
            printf '%s\n' "$package"
        fi
    done
}

confirm_packages() {
    local manager="$1"
    shift

    if ((ASSUME_YES)); then
        return 0
    fi
    if [[ ! -r /dev/tty ]]; then
        die "No terminal is available to confirm package installation.
Re-run with --yes, or install the packages yourself and use --no-deps."
    fi

    printf 'Install system packages with %s?\n  %s\n[Y/n] ' \
        "$manager" "$*"
    local answer
    read -r answer < /dev/tty || answer=""
    case "$answer" in
        "" | y | Y | yes | YES | Yes) ;;
        *)
            die "Cancelled. Install the packages from linux/README.md and rerun with --no-deps."
            ;;
    esac
}

install_deps() {
    local manager=""
    if command -v apt-get >/dev/null 2>&1; then
        manager="apt"
    elif command -v dnf >/dev/null 2>&1; then
        manager="dnf"
    elif command -v pacman >/dev/null 2>&1; then
        manager="pacman"
    elif command -v zypper >/dev/null 2>&1; then
        manager="zypper"
    fi

    [[ -n "$manager" ]] ||
        die "No supported package manager found.
Install the dependencies from https://github.com/$REPO/blob/main/linux/README.md
and rerun with --no-deps."

    command -v sudo >/dev/null 2>&1 ||
        die "sudo is required to install system packages.
Install the dependencies yourself and rerun with --no-deps."

    local -a packages=()
    case "$manager" in
        apt)
            mapfile -t packages < <(apt_missing_packages)
            if ((${#packages[@]} == 0)); then
                say "System packages already present."
                return 0
            fi
            confirm_packages "apt" "${packages[@]}"
            sudo apt-get update </dev/null
            sudo env DEBIAN_FRONTEND=noninteractive \
                apt-get install -y "${packages[@]}" </dev/null
            ;;
        dnf)
            packages=(
                python3 python3-pip python3-gobject python3-cairo
                python3-dbus python3-evdev gtk3
                libayatana-appindicator-gtk3 portaudio wl-clipboard
            )
            confirm_packages "dnf" "${packages[@]}"
            sudo dnf install -y "${packages[@]}" </dev/null
            ;;
        pacman)
            packages=(
                python python-pip python-gobject python-cairo python-dbus
                python-evdev gtk3 libayatana-appindicator portaudio
                wl-clipboard
            )
            confirm_packages "pacman" "${packages[@]}"
            sudo pacman -S --needed --noconfirm "${packages[@]}" </dev/null
            ;;
        zypper)
            packages=(
                python3 python3-pip python3-gobject python3-cairo
                python3-dbus-python python3-evdev gtk3
                libayatana-appindicator3-1 portaudio wl-clipboard
            )
            confirm_packages "zypper" "${packages[@]}"
            sudo zypper --non-interactive install "${packages[@]}" </dev/null
            ;;
    esac
}

check_python() {
    [[ -x /usr/bin/python3 ]] ||
        die "/usr/bin/python3 was not found; Falco needs Python 3.10-3.14."

    local version
    version="$(/usr/bin/python3 -c \
        'import sys; print("%d.%d" % sys.version_info[:2])')" ||
        die "Could not run /usr/bin/python3."

    case "$version" in
        3.10 | 3.11 | 3.12 | 3.13 | 3.14) ;;
        *) die "Python $version is not supported; Falco needs Python 3.10-3.14." ;;
    esac

    if ! /usr/bin/python3 -c 'import gi, dbus' 2>/dev/null; then
        die "Python modules gi and dbus are missing.
Install the dependencies from https://github.com/$REPO/blob/main/linux/README.md
and try again."
    fi
}

download_source() {
    TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/falco-install.XXXXXX")"
    trap 'rm -rf -- "$TMP_DIR"' EXIT

    local archive="$TMP_DIR/source.tar.gz"
    local url="https://github.com/$REPO/archive/$REF.tar.gz"

    say "Downloading Falco ($REF)…"
    curl -fL --proto '=https' --tlsv1.2 --retry 3 --connect-timeout 15 \
        --silent --show-error -o "$archive" "$url" ||
        die "Could not download $url"

    tar -xzf "$archive" -C "$TMP_DIR" ||
        die "Could not extract the source archive."

    SOURCE_DIR="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d -print -quit)"
    [[ -n "$SOURCE_DIR" && -x "$SOURCE_DIR/linux/install.sh" ]] ||
        die "The downloaded archive did not contain linux/install.sh."
}

build_rune() {
    ((WITH_RUNE)) || return 0

    command -v cargo >/dev/null 2>&1 ||
        die "--with-rune needs Rust 1.99.1 or newer.
Install Rust from https://rustup.rs, or rerun without --with-rune."

    say "Building the Rune dashboard and overlay (this can take a while)…"
    (
        cd "$SOURCE_DIR"
        cargo build --release --locked \
            --manifest-path linux/rune-overlay/Cargo.toml \
            --target-dir linux/rune-overlay/target
    ) </dev/null || die "The Rune build failed. Rerun without --with-rune for the GTK tray."
}

run_installer() {
    local bin_dir="${PHONON_BIN_DIR:-$HOME/.local/bin}"

    say "Installing Falco…"
    (cd "$SOURCE_DIR" && bash linux/install.sh) </dev/null

    say ""
    say "Falco is installed."
    say "Start it from your application menu, or run:"
    say "  $bin_dir/falco"
    say ""
    say "The first run guides you through permissions, a dictation key, and a"
    say "speech model download of about 1.7 GB."
}

main() {
    parse_args "$@"
    require_user
    check_existing
    if ((SKIP_DEPS)); then
        say "Skipping system packages (--no-deps)."
    else
        install_deps
    fi
    check_python
    download_source
    build_rune
    run_installer
}

main "$@"
