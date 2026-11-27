"""Transactional removal of the identifiable 0.1.0 app before a fresh install.

Run directly with the system Python: this must work before the new venv exists.
User configuration, model caches and all other application versions are outside
the removal set. Quarantine lives beside each original file, for atomic moves
and rollback if the replacement cannot be installed.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import tempfile
import time
import uuid


def _owned(path):
    info = path.lstat()
    return info.st_uid == os.getuid() and not path.is_symlink()


def is_010(path):
    """Two independent version markers and the original package identity."""
    try:
        if not re.fullmatch(r"0\.1\.0(?:\.[A-Za-z0-9_-]+)?", path.name) or not _owned(path):
            return False
        metadata = (path / "pyproject.toml").read_text()
        section = re.search(r"(?ms)^\[tool\.poetry\]\s*\n(.*?)(?=^\[|\Z)", metadata)
        if not section:
            return False
        fields = dict(re.findall(r'^\s*(name|version)\s*=\s*"([^"]+)"\s*$', section[1], re.M))
        if fields.get("version") != "0.1.0" or fields.get("name") not in (
                "falco-dictation", "phonon-linux-community"):
            return False
        module = ast.parse((path / "src/localdictation/__init__.py").read_text())
        return any(isinstance(node, ast.Assign) and
                   any(isinstance(target, ast.Name) and target.id == "__version__"
                       for target in node.targets) and
                   isinstance(node.value, ast.Constant) and node.value.value == "0.1.0"
                   for node in module.body)
    except (OSError, ValueError, SyntaxError):
        return False


def _under(program, roots):
    # Do not resolve the venv Python symlink: that leads to /usr/bin/python.
    path = Path(os.path.abspath(program))
    return any(path.is_relative_to(root) for root in roots)


def _old_processes(roots):
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            argv = (entry / "cmdline").read_bytes().decode().strip("\0").split("\0")
            if not argv or not _under(argv[0], roots):
                continue
            native = Path(argv[0]).name in ("phonon-window", "phonon-overlay", "falco", "phonon-linux")
            module = "-m" in argv and argv.index("-m") + 1 < len(argv) and \
                argv[argv.index("-m") + 1].startswith("localdictation.")
            if native or module:
                yield int(entry.name)
        except (OSError, UnicodeError):
            continue


def stop_old_processes(roots):
    """Graceful SIGTERM, restricted to this user's identified old app paths."""
    pids = list(_old_processes(roots))
    for pid in pids:
        try:
            descriptor = os.pidfd_open(pid)
        except ProcessLookupError:
            continue
        try:
            if pid in _old_processes(roots):
                signal.pidfd_send_signal(descriptor, signal.SIGTERM)
        finally:
            os.close(descriptor)
    deadline = time.monotonic() + 10
    while list(_old_processes(roots)):
        if time.monotonic() >= deadline:
            raise RuntimeError("Falco 0.1.0 is still running. Quit its tray and Preferences, then retry.")
        time.sleep(0.1)


def _entry_owned(path, roots):
    try:
        if path.is_symlink():
            return _under(str(path.resolve()), roots)
        if not path.is_file() or not _owned(path) or path.suffix != ".desktop":
            return False
        for line in path.read_text().splitlines():
            if line.startswith("Exec="):
                args = shlex.split(line[5:])
                if args and _under(args[0], roots):
                    return True
        return False
    except (OSError, ValueError, UnicodeError):
        return False


def _write(path, value):
    fd, temporary = tempfile.mkstemp(prefix=".legacy-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _remove(path):
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def finish(manifest, commit=False):
    if not manifest.exists():
        return
    record = json.loads(manifest.read_text())
    launcher = Path(record["launcher"])
    activated = False
    if launcher.is_symlink() and os.readlink(launcher) != record["previous_launcher"]:
        target = launcher.resolve()
        activated = (target.parent.parent == manifest.parent / "releases" and
                     (target.parent / ".venv/bin/python").is_file() and
                     (target.parent / "run.sh").is_file())
    commit = commit or record["committing"] or activated
    if commit and not record["committing"]:
        record["committing"] = True
        _write(manifest, json.dumps(record))
    for item in reversed(record["entries"]):
        original, staged = Path(item["original"]), Path(item["staged"])
        if staged.parent != original.parent or not staged.name.startswith(".falco-0.1.0-"):
            raise ValueError("Invalid legacy migration record; nothing was removed.")
        if not staged.exists() and not staged.is_symlink():
            continue
        if not commit:
            if not original.exists() and not original.is_symlink():
                os.replace(staged, original)
                if item.get("directory"):
                    original.chmod(item["mode"])
            else:
                raise RuntimeError(f"Cannot restore {original}; its backup remains at {staged}.")
        else:
            if item.get("autostart") and not original.exists():
                text = item["autostart_text"]
                lines = ["Exec=" + item["autostart"] if line.startswith("Exec=") else
                         "TryExec=" + item["autostart"] if line.startswith("TryExec=") else line
                         for line in text.splitlines()]
                _write(original, "\n".join(lines) + "\n")
            _remove(staged)
    manifest.unlink()


def begin(base, bin_dir, desktop_dir, autostart_dir, legacy_base):
    manifest = base / ".legacy-0.1.0.json"
    finish(manifest)  # Recover an interrupted attempt before planning another.
    roots = []
    for parent in {base.resolve(), legacy_base.resolve()}:
        releases = parent / "releases"
        if releases.is_symlink():
            continue
        if releases.is_dir():
            roots.extend(path for path in releases.iterdir() if is_010(path))
    if not roots:
        return
    print("Preparing a clean reinstall of verified Falco 0.1.0; stopping its old processes…", flush=True)
    stop_old_processes(roots)
    entries = []
    for folder in (bin_dir, desktop_dir, autostart_dir):
        if folder.is_dir():
            entries.extend(path for path in folder.iterdir() if _entry_owned(path, roots))
    token = uuid.uuid4().hex
    plan = []
    for path in [*dict.fromkeys(entries), *roots]:
        item = {"original": str(path), "staged": str(path.with_name(f".falco-0.1.0-{token}-{path.name}"))}
        if path.parent == autostart_dir:
            item["autostart_text"] = path.read_text()
            launcher = str(bin_dir / "falco").replace("%", "%%")
            launcher = launcher.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
            item["autostart"] = '"' + launcher.replace("\\", "\\\\") + '"'
        item["directory"] = path.is_dir() and not path.is_symlink()
        if item["directory"]:
            item["mode"] = path.stat().st_mode & 0o777
        plan.append(item)
    launcher = bin_dir / "falco"
    record = {"committing": False, "entries": plan, "launcher": str(launcher),
              "previous_launcher": os.readlink(launcher) if launcher.is_symlink() else None}
    _write(manifest, json.dumps(record))
    try:
        for item in plan:
            os.replace(item["original"], item["staged"])
            if item["directory"]:
                Path(item["staged"]).chmod(0o700)
    except OSError:
        finish(manifest)
        raise
    print("Removed the verified Falco 0.1.0 app and its old launchers before reinstalling.")
    print("Settings, words and model downloads are retained; a failed install restores the old app.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("begin", "commit", "rollback"))
    for key in ("install-base", "bin-dir", "desktop-dir", "autostart-dir", "legacy-base"):
        parser.add_argument("--" + key, required=True, type=lambda value: Path(os.path.abspath(value)))
    args = parser.parse_args()
    try:
        if args.action == "begin":
            begin(args.install_base, args.bin_dir, args.desktop_dir, args.autostart_dir, args.legacy_base)
        else:
            finish(args.install_base / ".legacy-0.1.0.json", commit=args.action == "commit")
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Legacy 0.1.0 migration: {error}\n")


if __name__ == "__main__":
    main()
