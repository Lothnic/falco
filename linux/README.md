# Falco

An experimental community Linux dictation app built on [TuxTalk](https://github.com/ronb1964/TuxTalk), using the separately distributed [Phonon refiner](https://huggingface.co/Infatoshi/phonon-refiner-1.7b) for local transcript cleanup. This is not an official Phonon or TuxTalk release. Its tray and service are adapted from TuxTalk, with a Rune dashboard and recording overlay.

The default speech model is Parakeet Ultra v3. The Phonon refiner is the default cleanup model and is English-only. It is downloaded separately when enabled; until its download is installed and it is loaded, dictation uses the unrefined transcript. The speech and cleanup model downloads total roughly 1.7 GB. Processing is local after downloading.

## Ubuntu setup

Install the system dependencies (package names vary on other distributions):

```sh
sudo apt install python3 python3-venv python3-pip python3-gi python3-gi-cairo python3-dbus python3-evdev gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 libportaudio2 wl-clipboard
```

To include the Rune window and overlay, first build both binaries from the repository root with `cargo build --release --locked --manifest-path linux/rune-overlay/Cargo.toml` (Rust 1.99.1 or newer is required). Then run `./install.sh` from this directory. It installs the source, Python dependencies, a `falco` command, and an application launcher in your user account. If the Rune binaries are present, the launcher opens the new dashboard; otherwise it starts the existing tray interface. Then start **Falco** from your applications. The first-run screens configure typing permissions, a hotkey and a speech model. In Preferences → Advanced, enable **Refine dictation with Phonon’s local model** to download and activate the refiner. Do not run this package at the same time as the earlier prototype: both can listen for the same hotkeys. The app needs access to keyboard events and virtual input on Wayland; the first-run screens can guide you through those permissions.

For development, create a virtual environment with system site packages and run `python -m localdictation.tray`. The `localdictation` Python module name is an internal implementation detail.

## License and origin

The code in **this `linux/` directory** is based on TuxTalk, copyright 2024–2026 Ron Brand, and is available under the MIT license in this directory. The existing Phonon source elsewhere in this repository remains GPL-3.0 under the repository's root `LICENSE`; this directory does not relicense it.

Models and inference engines are downloaded separately and have their own licenses. The Phonon refiner uses the LFM Open License, which restricts commercial use by larger organizations; see its [model card and license](https://huggingface.co/Infatoshi/phonon-refiner-1.7b). Parakeet Ultra and its ONNX export are CC-BY-4.0. llama.cpp is MIT. Other bundled assets retain their own notices in `src/localdictation/fonts/LICENSE` and `src/localdictation/models/LICENSE`.

## Status

This is an early source package. Its transcription and cleanup components have been tested on Ubuntu, but the packaged application still needs broader end-to-end testing across desktop environments. The experimental type-at-pause and voice-editing features do not provide the full Phonon refinement pipeline.

## Experimental Rune recording overlay

The existing GTK recording indicator remains the default. The optional Rune
sidecar shows a sound-responsive **Listening** indicator and a **Finishing…**
state while a dictation is processed. If the sidecar cannot start or cannot
show an overlay, the existing GTK recording indicator remains available.

To try it, install Rust 1.99.1 or newer and build the pinned Rune revision:

```sh
cargo build --release --locked --manifest-path linux/rune-overlay/Cargo.toml
# Install the app after building, or run the overlay alongside an existing installation:
PHONON_RUNE_OVERLAY="$PWD/linux/rune-overlay/target/release/phonon-overlay" falco
```

Run these commands from the repository root, after installing the app with
`linux/install.sh`. Quit any already-running copy first. The first build
fetches Rune and its Rust dependencies. The overlay uses XWayland when a
`DISPLAY` is present, which keeps it non-activating on GNOME Wayland. It is
currently anchored at the bottom of the primary display; the GTK position,
style, and size settings do not apply to Rune. This is an experimental opt-in,
not yet a replacement for the established indicator on every desktop.
