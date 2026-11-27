# Falco

Current release: **2.6.0 — Command Mode**.

An experimental community Linux dictation app built on [TuxTalk](https://github.com/ronb1964/TuxTalk), using the separately distributed [Phonon refiner](https://huggingface.co/Infatoshi/phonon-refiner-1.7b) for local transcript cleanup. This is not an official Phonon or TuxTalk release. Its tray and service are adapted from TuxTalk, with a Rune dashboard and recording overlay.

[Website](https://falco.lothnic.dev) · [Main README](../README.md)

The default speech model is Parakeet Ultra v3 (about **670 MB**). The optional Phonon refiner and its engine add about **1 GB** when enabled. The refiner is English-only. Falco uses the unrefined transcript until the refiner is ready. Processing is local after downloading.

With the refiner active, **Settings → Refiner → Writing style**
offers Minimal, Casual, Formal, AI prompt, and Match the focused app. App
matching uses the desktop's application ID and defaults to Minimal when
Falco can't identify the app.

## Falco 2.6.0 — Command Mode

Command Mode adds a dedicated shortcut for spoken edits and drafts. Select text,
press **Ctrl+Alt+C**, say **make this shorter**, and press it again to replace the
selection. With nothing selected, say what to write and the local AI drafts it at
the cursor. Voice commands such as **open Firefox** still run, and no text leaves
the machine.

Turn it on under **Settings → General** in Rune or GTK
Preferences. It is off by default, so existing dictation and voice editing keep
their current behaviour. Like voice editing, Command Mode needs a Wayland session
and does not automatically submit drafts.

Rune remains the primary dashboard for settings, words, usage, updates and
backups, with the dark slate-and-mint appearance. The GTK compatibility interface
is still available with `FALCO_LEGACY_UI=1`.

[2.6.0 release notes](../docs/releases/v2.6.0.md)

### Refiner edition features

**Settings → Refiner → Accelerate Phonon refinement**
downloads a matching DFlash2 drafter (215 MB) beside the existing refiner.
It proposes blocks of tokens that Phonon verifies before using them. This
option is off by default and applies only to Phonon; Gemma and Llama keep
their usual decoding. Speed varies with the device and transcript length.
Turn it off if slower. A startup or warm-up failure retries with ordinary
decoding automatically.

**Show a live transcript in Rune** now also shows the refiner's provisional
output during **Finishing…**. With **Start typing sooner** and CPU Parakeet,
refinement streams during speech pauses too. These previews can change as
more speech arrives. The focused app receives completed text after the usual
checks; a broken or truncated stream is never typed as a completed rewrite.
Previewing does not require the drafter.

Both weights stay pinned to the same Phonon revision and are checked against
their SHA256. No model download is made in the background when upgrading.

In the initial Linux/Vulkan benchmark on an RTX 4060 Laptop GPU (8 GB), the
drafter reduced total refiner-request time by **32% (1.47× faster)** across
four synthetic prompts measured twice after warm-up. The 60-token output
took **198 ms versus 371 ms**, or **1.87× faster**, with identical output.
The shortest output changed little. These measurements exclude speech
recognition, cold loading, UI rendering and text insertion; CPU-only and
very long outputs have not been measured.

[Benchmark results, raw data and reproduction](../docs/benchmarks/README.md) ·
[2.5.0 release notes](../docs/releases/v2.5.0.md)

## Quick install

On a supported Linux desktop, the hosted installer handles the dependencies
and the app in one command:

```sh
curl -fsSL https://falco.lothnic.dev/install.sh | bash
```

It uses apt, dnf, pacman, or zypper for the system packages, then installs
Falco under `~/.local/share/falco-app` and adds `~/.local/bin/falco`. Linux
x86_64 gets matching, checksum-verified Rune binaries (Ubuntu 24.04 / glibc
2.39 or newer). To build the UI locally instead (Rust 1.99.1 or newer), use:

```sh
curl -fsSL https://falco.lothnic.dev/install.sh | bash -s -- --with-rune
```

The installer uses the latest published release tag and falls back to the
preview from `main` until a release is published. Pass `--no-deps` to skip
system packages, or `--ref` to choose a branch, tag, or commit.

For a verified **0.1.0** installation, the installer removes the old app and
its owned launchers before a fresh install. Settings and models stay; other
versions use the normal upgrade path. A failed reinstall restores the old app.

Rerun the installer to upgrade, then quit and reopen Falco. The existing launcher stays active until the new release is
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

Run `./install.sh` from this directory. It downloads the exact release's Rune
bundle on Linux x86_64, then installs the source, Python dependencies, command
and application launcher in your user account. An unavailable or incompatible
bundle falls back to GTK. To build Rune locally, run
`./linux/packaging/build-rune-bundle.sh` from the repository root before installing.
Then start **Falco** from your applications. First-run setup configures typing
permissions, a hotkey and a speech model. In **Settings → Refiner**, enable
**Refine dictation** to download the local refiner. Avoid running an older
prototype at the same time, since both can listen for the same hotkeys.

For development, create a virtual environment with system site packages and run `python -m localdictation.tray`. The `localdictation` Python module name is an internal implementation detail.

## License and origin

The code in **this `linux/` directory** is based on TuxTalk, copyright 2024–2026 Ron Brand, and is available under the MIT license in this directory. The existing Phonon source elsewhere in this repository remains GPL-3.0 under the repository's root `LICENSE`; this directory does not relicense it.

Models and inference engines are downloaded separately and have their own licenses. The Phonon refiner uses the LFM Open License, which restricts commercial use by larger organizations; see its [model card and license](https://huggingface.co/Infatoshi/phonon-refiner-1.7b). Parakeet Ultra and its ONNX export are CC-BY-4.0. llama.cpp is MIT. Other bundled assets retain their own notices in `src/localdictation/fonts/LICENSE` and `src/localdictation/models/LICENSE`.

## Status

This is an early source package. Its transcription and cleanup components have been tested on Ubuntu, but the packaged application still needs broader end-to-end testing across desktop environments. The experimental type-at-pause and voice-editing features do not provide the full Phonon refinement pipeline.

## Experimental Rune recording overlay

With the Rune bundle installed, the Rune recording sidecar shows a sound-responsive **Listening** indicator and a **Finishing…**
state while a dictation is processed. If the sidecar cannot start or cannot
show an overlay, the existing GTK recording indicator remains available.

To show provisional words while recording, enable **Show a live transcript
transcript** under **Settings → Appearance**. This setting is off by
default. It uses Parakeet on the CPU and works alongside Type at pause as
well as with dictations inserted at release. The overlay keeps a short draft
in memory for the current recording. Falco runs the usual full transcription
and optional refinement at release.

The installer stores Rune under `~/.local/share/falco-app/rune/<version>` and
links each release to its matching UI. It never reuses an older dashboard.
Without compatible Rune binaries, the launcher uses the GTK tray.

Search your session's dictations in the Rune dashboard's **Recent** tab.

## Start typing sooner

Long dictations can be heard while you speak instead of after you stop, so the
wait at release does not grow with how long you talked. Enable **Start typing
sooner** under **Settings → Audio**. It is off by default.

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
the finished transcript, character for character, with the same writing mode,
engine and vocabulary. If that exact request is still running, release reuses
its result instead of queuing a duplicate. Otherwise the release refines as usual.

## Background music

Under **Settings → Audio**, **Pause music
and videos** stops the players that are playing so the microphone hears only
you. **Resume it after dictating** starts them again when the dictation ends;
turn it off to leave them paused. If a browser accepts the play request but
stays paused, Falco checks once and toggles it to recover.

## Developer mode

Under **Settings → Text → Developer mode**, spoken code is written as
code instead of prose. Choose **In code apps** (the default: code editors and
terminals) or **Always**.

- File names: "open main dot py" → `open main.py`; "edit src slash components
  slash button dot tsx" → `edit src/components/button.tsx`.
- Casing: "camel case get user id" → `getUserId`; "snake case get user id" →
  `get_user_id`; also pascal, kebab, constant, upper and lower.
- Symbols: "use backtick npm run build backtick" → ``use `npm run build` ``;
  "wrap it in open paren x close paren" → `wrap it in (x)`; "a fat arrow b" →
  `a => b`.
- Common developer spellings: GitHub, TypeScript, Node.js, Postgres,
  Kubernetes, T3 Code and more.

Code dictation keeps the transcript exact: the prose refiner and AI cleanup
are skipped so they cannot rewrite code. A word the model still mishears can
be taught in **Your words**.

## A dictionary that learns

**Your words → Learned automatically** shows the names Falco taught
itself. With **Learn names from the refiner** on, a word the refiner fixes
only in spelling or capitals, in the middle of a dictation ("github" →
"GitHub", "tux talk" → "TuxTalk"), is counted; on the second sighting it joins
Your Words, so the engine is steered towards it and the spelling pass gets it
right before the refiner is asked.

Rewrites ("gonna" → "going to") and a sentence's first capital are ignored,
so the list gains proper nouns, not grammar. **Clear learned words** forgets
them; Your Words itself is never changed.

## Refiner models and Hindi

**Settings → Refiner → Refiner model** chooses which local model cleans up
a transcript:

- **Automatic** (default): Phonon 1.7B for English, Gemma 3 1B when the
  dictation language is Hindi.
- **Phonon English** (1.7B, 1.0 GB).
- **Gemma 3 1B** or **Llama 3.2 1B** (both 0.8 GB, Hindi and other languages).

Only one model runs at a time, and the 1B models use less memory than Phonon.
Choosing a model downloads it; **Automatic** needs Gemma 3 1B downloaded once
before Hindi dictation uses it.

Hindi dictation also needs a **Whisper** speech model — Parakeet does not support
Hindi. Set the language to Hindi in **Settings → Speech**. The refiner keeps
the transcript's language and script and never translates it.

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
