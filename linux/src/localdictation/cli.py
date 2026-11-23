"""`falco` from a terminal: transcribe a file, and ask a running Falco to
start or stop dictating.

The tray's own command line is handled by control.py, which needs a running
Falco and reports over D-Bus. This module is the part that works with nothing
running: it is the console script, and it imports no GTK, so it works over
SSH, in a script, and on a machine with no display.

    falco transcribe talk.mp3              # the text, to standard output
    falco transcribe talk.mp4 -o talk.txt
    falco transcribe talk.mp4 --srt        # subtitles, to standard output
    falco transcribe talk.mp4 --clean      # ums and repeats removed
    falco transcribe a.wav b.m4a           # several files, in order
    falco --toggle / --start / --stop      # control the running app

Everything else (`falco` with no arguments, `--open preferences`) is the tray's
and is handed to it unchanged, so the desktop launcher and old shortcuts keep
working.
"""
import argparse
import os
import sys

from .logger import setup_logger

logger = setup_logger(__name__)

# What the tray understands (control.py). Handed to it unchanged.
_TRAY_OPTIONS = ("--toggle", "--start", "--stop", "--open", "--quit", "--uninstall",
                 "--help", "-h", "--version")

# What `transcribe` writes when no output file is given.
FORMATS = {"text", "srt"}


def transcribe_command(argv):
    """The `transcribe` subcommand's own arguments, without it: it is a
    separate parser so a file named like an option can follow --."""
    parser = argparse.ArgumentParser(
        prog="falco transcribe",
        description="Turn an audio or video file into text, on this machine.")
    parser.add_argument("files", nargs="+", metavar="FILE",
                        help="audio or video to transcribe (mp3, m4a, wav, flac, mp4, ...)")
    parser.add_argument("-o", "--output", metavar="FILE",
                        help="write here instead of standard output "
                             "(one file per input, numbered, when several are given)")
    parser.add_argument("--srt", action="store_true",
                        help="subtitle timing instead of plain paragraphs")
    parser.add_argument("--times", action="store_true",
                        help="start each paragraph with where it is in the file")
    parser.add_argument("--clean", action="store_true",
                        help="remove ums, uhs and repeated words (no AI)")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="no progress on standard error")
    return parser.parse_args(argv)


def _progress_writer(quiet):
    """A progress line on standard error, rewritten in place: standard output
    is the transcript, so nothing but it may go there."""
    if quiet or not sys.stderr.isatty():
        return None
    state = {"last": -1}

    def show(done, total):
        percent = int(100 * done / total) if total else 0
        if percent != state["last"]:
            state["last"] = percent
            sys.stderr.write(f"\rTranscribing… {percent}%")
            sys.stderr.flush()
    return show


def _finish_progress(quiet):
    if not quiet and sys.stderr.isatty():
        sys.stderr.write("\r" + " " * 24 + "\r")
        sys.stderr.flush()


def transcribe_files(argv):
    """`falco transcribe`: write each file's text to its output, and say what
    went wrong for a file that couldn't be read. Returns the exit code: 0 when
    every file gave text, 1 when any didn't."""
    args = transcribe_command(argv)
    from . import config, file_transcribe

    # Every path is checked before the model is loaded: a mistyped name should
    # say so at once, not after a speech model has been read into memory.
    missing = [path for path in args.files if not os.path.isfile(path)]
    for path in missing:
        sys.stderr.write(f"{path}: no such file\n")
    present = [path for path in args.files if path not in missing]
    if not present:
        return 1

    cfg = config.load_config()
    try:
        engine = file_transcribe.load_engine(cfg)
    except file_transcribe.NotDownloaded as e:
        # Not an error in the file: the speech model isn't here yet, and the
        # app says how to get it.
        sys.stderr.write(
            f"{e}\nOpen Falco once and let it download a speech model, then try again.\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"Could not load the speech model: {e}\n")
        return 1

    failure = bool(missing)
    try:
        for number, path in enumerate(present, start=1):
            failure |= not _transcribe_one(path, engine, args, number, len(present))
    except KeyboardInterrupt:
        # Ctrl-C during a long file: stop quietly, the way a command-line tool
        # should, rather than with a traceback.
        sys.stderr.write("\nCancelled.\n")
        return 130
    finally:
        engine.close()
    return 1 if failure else 0


def _transcribe_one(path, engine, args, number, count):
    """One file, written where asked. False when it gave no text."""
    from . import file_transcribe

    if not os.path.isfile(path):
        sys.stderr.write(f"{path}: no such file\n")
        return False
    if not args.quiet:
        sys.stderr.write(f"{path}\n")
    try:
        audio = file_transcribe.decode(path)
    except file_transcribe.NoSound as e:
        sys.stderr.write(f"{path}: {e}\n")
        return False
    except Exception as e:
        sys.stderr.write(f"{path}: could not be read ({e})\n")
        return False

    try:
        pieces = file_transcribe.transcribe(audio, engine,
                                            progress=_progress_writer(args.quiet))
    except KeyboardInterrupt:
        # Cancelled from the terminal: no half transcript is written.
        _finish_progress(args.quiet)
        sys.stderr.write("\nCancelled.\n")
        raise
    except Exception as e:
        _finish_progress(args.quiet)
        sys.stderr.write(f"{path}: transcription failed ({e})\n")
        return False
    _finish_progress(args.quiet)

    if not pieces:
        sys.stderr.write(f"{path}: no speech was found in it\n")
        return False
    if args.clean:
        pieces = file_transcribe.cleaned(pieces)
    text = (file_transcribe.to_srt(pieces) if args.srt
            else file_transcribe.to_text(pieces, times=args.times))
    if not text:
        sys.stderr.write(f"{path}: no speech was found in it\n")
        return False

    destination = _output_path(args.output, path, number, count, args.srt)
    if destination is None:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
        return True
    try:
        with open(destination, "w", encoding="utf-8") as f:
            f.write(text if text.endswith("\n") else text + "\n")
    except OSError as e:
        sys.stderr.write(f"{destination}: could not be written ({e})\n")
        return False
    if not args.quiet:
        sys.stderr.write(f"Wrote {destination}\n")
    return True


def _output_path(output, source, number, count, srt):
    """Where one file's transcript goes: None for standard output.

    A single file writes exactly where --output says. Several files sharing
    one --output are all numbered beside it ("talk.1.txt", "talk.2.txt"), so
    none of them overwrites another and the numbering says which is which."""
    if not output:
        return None
    if count == 1:
        return output
    root, extension = os.path.splitext(output)
    if not extension:
        extension = ".srt" if srt else ".txt"
        root = output
    return f"{root}.{number}{extension}"


def main(argv=None):
    """`falco`: the console script. Transcribe and control run here; anything
    else is the tray's, which is handed the same arguments."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "transcribe":
        return transcribe_files(argv[1:])
    if any(option in argv for option in _TRAY_OPTIONS):
        return _tray_main(argv)
    if argv and argv[0] in ("help", "--help", "-h"):
        _print_usage()
        return 0
    # No arguments: start the app, as the desktop launcher does.
    return _tray_main(argv)


def _tray_main(argv):
    """The tray process. Imported here, on this path only: the tray pulls in
    GTK and the indicator, which a transcription job has no use for.

    The tray reads sys.argv itself (tray._handle_command_line), so the
    arguments this process was given are already in place."""
    from . import tray
    return tray.main()


def _print_usage():
    sys.stdout.write(
        "Falco: local voice dictation for Linux.\n"
        "\n"
        "  falco                       start dictation\n"
        "  falco transcribe FILE...    turn audio or video into text\n"
        "  falco --toggle               start recording, or stop it\n"
        "  falco --start | --stop       start or stop recording\n"
        "  falco --open NAME            open a window (menu, preferences, transcribe)\n"
        "  falco --quit                 quit\n"
        "\n"
        "falco transcribe --help explains the transcription options.\n")


if __name__ == "__main__":
    sys.exit(main())
