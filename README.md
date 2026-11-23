# Falco

Falco is a local voice dictation app for Linux. Hold a dictation key, speak,
and the text is typed into the application you are using. Speech recognition
runs on your machine, with optional local transcript cleanup; models are
downloaded once.

It is an experimental community app built on
[TuxTalk](https://github.com/ronb1964/TuxTalk), in a fork of the
[Phonon](https://github.com/Infatoshi/phonon) repository. It uses Phonon's
separately distributed
[refiner](https://huggingface.co/Infatoshi/phonon-refiner-1.7b) for optional
cleanup and adds a Rune dashboard and recording overlay. Falco is not an
official Phonon or TuxTalk release.

[Website](https://falco.lothnic.dev) · [Full Linux guide](linux/README.md) · [Upstream Phonon README](UPSTREAM-README.md)

## Features

- **Dictate anywhere.** Hold a configurable key to talk, or use a toggle key.
  Falco types into the focused app on Wayland and X11.
- **On-device speech recognition.** Parakeet Ultra v3 is the default and runs
  on the CPU or through Vulkan. Whisper models cover more languages and can
  use CUDA.
- **Optional local cleanup.** The Phonon refiner fixes self-corrections,
  removes fillers and false starts, and tidies capitalization. The refiner is
  English-only, and dictation uses the raw transcript until it is installed.
  Choose a writing mode in Preferences → Advanced, or let Falco match
  supported chat, mail, terminal, and coding apps.
- **Your vocabulary.** Custom words steer recognition, and voice commands
  handle punctuation, formatting, undo, and "fix that word". Falco Labs adds
  optional voice editing, selection, and app, window, key, and mouse control.
- **Rune dashboard and overlay.** Overview, Recent, Your words, and Settings
  pages, plus a sound-responsive recording overlay. Search the current
  session's dictations in Recent. An optional live transcript shows the
  latest words while you speak with Parakeet on the CPU. The GTK tray and
  recording indicator remain the fallback.
- **Private by design.** Audio and transcripts stay on the machine. No account
  is required, and dictation needs no network once the models are downloaded.
- **Short wait after the key.** With **Start typing sooner** on (Preferences →
  Audio → Customize), Falco hears each phrase as you pause, so releasing the
  key only transcribes the last one. A long dictation no longer means a long
  wait. The text is spliced at the pauses you made, and the whole recording is
  transcribed as before if a splice can't be vouched for. With the refiner on,
  the cleaned-up text is worked out during the recording too, so the refiner
  no longer runs after the key.
- **A command line.** `falco transcribe talk.mp4` writes a file's text or
  subtitles, with no window and no running app, so it works in a script or
  over SSH. `falco --toggle` and `falco --start`/`--stop` drive the running
  app.

## How it works

```text
microphone → Parakeet Ultra or Whisper → cleanup rules → optional refiner → focused app
```

On first run, Falco downloads the default speech model (about **670 MB**)
and offers a test dictation. To add cleanup, open
**Preferences → Advanced** and enable **Refine dictation with Phonon's local
model**; the app offers a one-time download of about 1 GB for the refiner and
its llama.cpp engine.

Recent dictations in the Rune dashboard are session data, kept only in memory
for the current login; they are not saved as a permanent history.

## Requirements

- Linux with Python 3.10–3.14 and GTK 3. Ubuntu is the primary tested
  distribution; GNOME and KDE Plasma on Wayland or X11 are the intended
  environments.
- PyGObject, D-Bus, evdev, PortAudio, and `wl-clipboard`. The apt command
  below installs these.
- Rust 1.99.1 or newer only for the optional Rune dashboard and overlay.
  Without it, Falco uses the GTK tray interface.
- About 670 MB to download the default speech model. The optional refiner
  and its engine add about 1 GB.

Falco needs access to keyboard events and virtual input to read the dictation
key and type into other applications. The first-run screens guide you through
the permissions it needs.

## Install

The quick installer handles the system packages and the app in one command:

```bash
curl -fsSL https://falco.lothnic.dev/install.sh | bash
```

It supports apt, dnf, pacman, and zypper, installs the dependencies with
`sudo`, and then installs Falco under your user account. Add
`--with-rune` (with Rust 1.99.1 or newer already installed) to build the Rune
dashboard and overlay first:

```bash
curl -fsSL https://falco.lothnic.dev/install.sh | bash -s -- --with-rune
```

The installer uses the latest published release tag. Until a release is
published, it uses the preview from `main`. Use `--ref` to choose a specific
tag, branch, or commit. Use `--no-deps` if you manage the system packages
yourself. You can download and read the Bash script before running it.

Run the same command again to upgrade. Include `--with-rune` if you use
the dashboard and overlay. If an install fails, you can retry it. Falco
keeps the existing launcher active until the new release is ready and
keeps previous releases in `~/.local/share/falco-app/releases`.

### Manual install

Install the system packages (package names vary by distribution):

```bash
sudo apt install python3 python3-venv python3-pip python3-gi python3-gi-cairo \
  python3-dbus python3-evdev gir1.2-gtk-3.0 \
  gir1.2-ayatanaappindicator3-0.1 libportaudio2 wl-clipboard
```

Clone and install:

```bash
git clone https://github.com/Lothnic/falco.git
cd falco

# Optional: build the Rune dashboard and recording overlay.
cargo build --release --locked --manifest-path linux/rune-overlay/Cargo.toml

# Installs under ~/.local/share/falco-app and adds ~/.local/bin/falco.
./linux/install.sh
```

Start **Falco** from your application menu, or run `falco` (use
`~/.local/bin/falco` if that directory is not on your `PATH`). The first-run
screens configure permissions, a dictation key, and a speech model, then
offer a field to check that your words are typed. If both
Rune binaries are present, the launcher opens the Rune dashboard; otherwise
it opens the GTK tray interface.

To upgrade a checkout install, check out the desired revision, rebuild Rune
if you use it, and rerun `./linux/install.sh`.

## Development

Set up a development environment from a checkout:

```bash
cd linux
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e .
.venv/bin/python -m localdictation.tray
```

Run the Linux tests (from `linux/`):

```bash
.venv/bin/pip install pytest
PYTHONPATH=src .venv/bin/python -m pytest tests
```

To include the setup screen's X11 typing test, run the suite with
`GDK_BACKEND=x11 xvfb-run -a` before the Python command. This test uses
`xvfb`, `xauth`, and `xdotool`.

Build and test the Rune UI (from the repository root):

```bash
cargo build --release --locked --manifest-path linux/rune-overlay/Cargo.toml
cargo test --manifest-path linux/rune-overlay/Cargo.toml
```

Build and test the website:

```bash
cd website
npm install
npm test
```

`localdictation` is Falco's internal Python package name, retained from
TuxTalk.

## Repository layout

Only `linux/` is the Falco application. `website/` is the Falco landing page and
browser demo. The remaining code is the upstream Phonon source, kept for
history and reference under its own licenses.

| Path | Contents |
| --- | --- |
| `linux/` | Falco: Python dictation service, tray and preferences, Rune dashboard and overlay |
| `crates/` | Phonon Rust workspace: audio, ASR, refiner, pipeline, CLI, and Windows app |
| `bar/` | Phonon macOS Swift app and capsule |
| `sidecar/` | Phonon speech and refiner sidecars |
| `engine/` | Phonon native refiner engine |
| `ml/` | Phonon refiner training and evaluation pipeline |
| `android/` | Phonon Android keyboard (development build) |
| `ios/` | Phonon iPhone keyboard (development build) |
| `website/` | Falco landing page, browser dictation demo, and hosted `install.sh` |

`UPSTREAM-README.md` holds the Phonon README this fork started from. `SPEC.md`
and `DISTRIBUTION.md` document the upstream macOS and Windows projects and do
not describe Falco.

## Status

Falco is an early source package. Transcription and cleanup have been tested
on Ubuntu, but the packaged app still needs broader end-to-end testing across
desktop environments. The Rune dashboard and overlay, type-at-pause, and voice
editing are experimental. Falco is not a port of the full upstream Phonon
pipeline; it uses the refiner as an optional cleanup stage.

## License

The Falco code in `linux/` is MIT-licensed, based on TuxTalk, copyright
2024–2026 Ron Brand. See [`linux/LICENSE`](linux/LICENSE). The upstream Phonon
source elsewhere in the repository remains GPL-3.0 under the root
[`LICENSE`](LICENSE); `linux/` does not relicense it.

Model weights are downloaded separately and keep their own licenses. The
Phonon refiner is under the LFM Open License, which restricts commercial use
by larger organizations; Parakeet is CC-BY-4.0; llama.cpp is MIT. See the
[Phonon refiner model card](https://huggingface.co/Infatoshi/phonon-refiner-1.7b),
[`linux/README.md`](linux/README.md), and [`THIRD_PARTY.md`](THIRD_PARTY.md).
