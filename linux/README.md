# Falco

An experimental community Linux dictation app built on [TuxTalk](https://github.com/ronb1964/TuxTalk), using the separately distributed [Phonon refiner](https://huggingface.co/Infatoshi/phonon-refiner-1.7b) for local transcript cleanup. This is not an official Phonon or TuxTalk release. Its tray and service are adapted from TuxTalk, with a Rune dashboard and recording overlay.

[Website](https://falco.lothnic.dev) · [Main README](../README.md)

The default speech model is Parakeet Ultra v3 (about **670 MB**). The optional Phonon refiner and its engine add about **1 GB** when enabled. The refiner is English-only. Falco uses the unrefined transcript until the refiner is ready. Processing is local after downloading.

With the refiner active, **Preferences → Advanced → Refiner writing mode**
offers Minimal, Casual, Formal, AI prompt, and Match the focused app. App
matching uses the desktop's application ID and defaults to Minimal when
Falco can't identify the app.

## Quick install

On a supported Linux desktop, the hosted installer handles the dependencies
and the app in one command:

```sh
curl -fsSL https://falco.lothnic.dev/install.sh | bash
```

It uses apt, dnf, pacman, or zypper for the system packages, then installs
Falco under `~/.local/share/falco-app` and adds `~/.local/bin/falco`. To build
the optional Rune dashboard and overlay first (Rust 1.99.1 or newer required),
use:

```sh
curl -fsSL https://falco.lothnic.dev/install.sh | bash -s -- --with-rune
```

The installer uses the latest published release tag and falls back to the
preview from `main` until a release is published. Pass `--no-deps` to skip
system packages, or `--ref` to choose a branch, tag, or commit.

Rerun the installer to upgrade, with `--with-rune` if you use the dashboard
and overlay. The existing launcher stays active until the new release is
ready. Failed installs can be retried with the same command.

Once a day, at startup, Falco also checks GitHub for a newer release and
installs it by itself, then restarts. Your settings and downloaded models
live outside the release folder, so they are kept, and first-run setup is
not shown again. Install **Falco 2.1.0 or newer** to get this; an older
copy has to be upgraded once by running the installer.

If an older Phonon Linux prototype is installed, its settings and models
are carried over the first time Falco starts, so the upgrade does not ask
you to set everything up again.

### A .deb, for package-managed systems

`packaging/build-deb.sh` builds a `.deb` that installs under `/usr` and is
owned by your package manager, so upgrades and removal go through `apt`. Its
dependencies are declared, so `apt` names anything missing instead of the app
failing to start later.

```sh
./packaging/build-deb.sh          # add --with-rune once Rune is built
sudo apt install ./dist/falco_*.deb
```

The package carries a Python environment built on the machine that builds it,
so build it on the oldest distribution release it should run on (Ubuntu, per
above). Continuous integration builds and installs it on every push.

## Ubuntu setup

Install the system dependencies (package names vary on other distributions):

```sh
sudo apt install python3 python3-venv python3-pip python3-gi python3-gi-cairo python3-dbus python3-evdev gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 libportaudio2 wl-clipboard
```

To include the Rune window and overlay, first build both binaries from the repository root with `cargo build --release --locked --manifest-path linux/rune-overlay/Cargo.toml` (Rust 1.99.1 or newer is required). Then run `./install.sh` from this directory. It installs the source, Python dependencies, a `falco` command, and an application launcher in your user account. If the Rune binaries are present, the launcher opens the new dashboard; otherwise it starts the existing tray interface. Then start **Falco** from your applications. The first-run screens configure typing permissions, a hotkey, and a speech model, then offer a test dictation. In Preferences → Advanced, enable **Refine dictation with Phonon’s local model** to download and activate the refiner. Do not run this package at the same time as the earlier prototype: both can listen for the same hotkeys. The app needs access to keyboard events and virtual input on Wayland; the first-run screens can guide you through those permissions.

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

To show provisional words while recording, enable **Show a live transcript
in Rune** under **Preferences → Audio → Customize**. This setting is off by
default. It uses Parakeet on the CPU and applies to dictations inserted at
release. The overlay keeps a short draft in memory for the current recording.
Falco runs the usual full transcription and optional refinement at release.

Search your session's dictations in the Rune dashboard's **Recent** tab.

## Start typing sooner

Long dictations can be heard while you speak instead of after you stop, so the
wait at release does not grow with how long you talked. Enable **Start typing
sooner** under **Preferences → Audio → Customize**. It is off by default.

What happens: at each pause you make, the phrase so far is transcribed and
kept. At release only the audio after the last pause is transcribed, and the
two are joined. Pauses, not volume, decide the cuts, so no word is split. The
release hears a little before the last pause as well, and the words it hears
twice are dropped by lining the two sides up.

When the two sides can't be lined up — a phrase heard very differently with and
without the words after it, or a failed intermediate pass — the whole
recording is transcribed as before. A slower dictation is preferred to a
wrongly joined one, and the log says which happened.

It needs the CPU Parakeet model: Whisper and the GPU engine have no
in-recording recognition, so their dictations are transcribed whole at
release. It also stays off with **Type at pause**, which types each phrase as
it is cut, and for voice edits.

With the refiner on, the refined text is worked out during the recording too
(`refiner_prefetch.py`): the transcript so far is refined in the background at
each pause, and at release the answer is reused when it was made for exactly
the finished transcript, character for character. Otherwise the release refines
as usual, so this can only save time, never change the words.

## The command line

`falco` is more than the launcher. `falco transcribe` turns a file into text
without a window and without the app running, so it works in a script or over
SSH:

```sh
falco transcribe talk.mp3                    # the text, to standard output
falco transcribe talk.mp4 -o talk.txt        # to a file
falco transcribe talk.mp4 --srt              # subtitles
falco transcribe talk.mp4 --clean            # ums and repeats removed
falco transcribe a.wav b.m4a                 # several files, in order
```

It reads WAV, MP3, M4A, OGG, FLAC and the sound of MP4, MKV and WebM videos,
using the model you dictate with. Nothing is sent anywhere. `--quiet` drops the
progress line, and progress always goes to standard error so standard output
stays the transcript.

`falco --toggle`, `--start`, `--stop`, `--open NAME` and `--quit` control a
running Falco, as before. With no arguments it starts the app.

The entry point is `cli.py`, which answers `transcribe` without importing GTK
and hands everything else to the tray unchanged. That is why it works over SSH
and in a container with no display.

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
