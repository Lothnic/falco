"""Falco updating itself.

The per-user install is a release folder under
``~/.local/share/falco-app/releases`` plus a link at ``~/.local/bin/falco``
(install.sh). An update downloads the new tag's source archive and runs its
``linux/install.sh``, which builds the new release and moves the link into
place. Settings and downloaded models live outside the release folder, so an
update keeps them and the first-run marker stays satisfied.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import urllib.request
from typing import Optional, Tuple

from .logger import setup_logger

logger = setup_logger(__name__)

REPO = "Lothnic/falco"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"
ARCHIVE_URL = f"https://github.com/{REPO}/archive/refs/tags/{{tag}}.tar.gz"
VERSION_RE = re.compile(r"^\d+(\.\d+)*$")


def _home() -> str:
    return os.path.expanduser("~")


def install_base() -> str:
    """The folder holding ``releases/``: read from where this copy runs."""
    if os.environ.get("PHONON_INSTALL_BASE"):
        return os.path.abspath(os.environ["PHONON_INSTALL_BASE"])
    # sys.prefix is <base>/releases/<version>/.venv (not resolved through the
    # venv's python symlink, which would lead to the system interpreter).
    prefix = os.path.abspath(sys.prefix)
    return os.path.dirname(os.path.dirname(os.path.dirname(prefix)))


def bin_dir() -> str:
    """Where the ``falco`` command lives."""
    if os.environ.get("PHONON_BIN_DIR"):
        return os.path.abspath(os.environ["PHONON_BIN_DIR"])
    found = shutil.which("falco")
    return os.path.dirname(os.path.abspath(found)) if found else os.path.join(_home(), ".local/bin")


def launcher() -> str:
    return os.path.join(bin_dir(), "falco")


def package_path() -> str:
    """Where this module runs from, for the managed-install check."""
    return os.path.realpath(__file__)


def is_managed_install() -> bool:
    """True for install.sh's per-user layout, which this module can update."""
    releases = os.path.join(os.path.realpath(install_base()), "releases") + os.sep
    return package_path().startswith(releases) and os.path.exists(launcher())


def _version_tuple(version: str) -> Tuple[int, ...]:
    return tuple(int(part) for part in version.lstrip("v").split(".") if part.isdigit())


def is_newer(latest: str, current: str) -> bool:
    return _version_tuple(latest) > _version_tuple(current)


def current_version() -> str:
    from . import __version__
    return __version__


def latest_release(timeout: int = 15) -> dict:
    """The newest published release, from GitHub's releases API."""
    request = urllib.request.Request(
        RELEASES_API,
        headers={"User-Agent": "Falco-Update", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    tag = data.get("tag_name", "")
    version = tag.lstrip("v")
    if not VERSION_RE.match(version):
        raise ValueError(f"unexpected release tag: {tag!r}")
    return {"tag_name": tag, "version": version,
            "html_url": data.get("html_url", ""), "body": data.get("body", ""),
            "published_at": data.get("published_at", "")}


def check() -> dict:
    """Same shape as update_checker.check_for_updates."""
    result = {"success": False, "error": None, "current_version": current_version(),
              "latest_version": None, "update_available": False, "release": None}
    try:
        release = latest_release()
    except Exception as e:
        result["error"] = str(e)
        return result
    result["release"] = release
    result["latest_version"] = release["version"]
    result["update_available"] = is_newer(release["version"], result["current_version"])
    result["success"] = True
    return result


def _download(tag: str, destination: str, progress=None) -> None:
    url = ARCHIVE_URL.format(tag=tag)
    with urllib.request.urlopen(url, timeout=120) as response, open(destination, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(f"Downloading Falco {done * 100 // total}%",
                         5 + 45 * done // total)


def _extract(archive: str, destination: str) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        root = os.path.realpath(destination)
        for member in tar.getmembers():
            target = os.path.realpath(os.path.join(destination, member.name))
            if target != root and not target.startswith(root + os.sep):
                raise ValueError(f"unsafe path in archive: {member.name}")
        if hasattr(tarfile, "data_filter"):
            tar.extractall(destination, filter="data")
        else:
            tar.extractall(destination)


def install(tag: str, progress=None) -> Tuple[bool, str]:
    """Download *tag* and run its installer. (ok, message)."""
    version = tag.lstrip("v")
    if not VERSION_RE.match(version):
        return (False, f"unexpected release tag: {tag!r}")
    work = tempfile.mkdtemp(prefix="falco-update.")
    try:
        archive = os.path.join(work, "falco.tar.gz")
        if progress:
            progress("Downloading Falco…", 5)
        _download(tag, archive, progress)
        if progress:
            progress("Unpacking Falco…", 55)
        source_root = os.path.join(work, "source")
        os.makedirs(source_root)
        _extract(archive, source_root)
        candidates = [os.path.join(source_root, name) for name in os.listdir(source_root)]
        source = next((path for path in candidates
                       if os.path.isfile(os.path.join(path, "linux/install.sh"))), None)
        if source is None:
            return (False, "The update archive had no linux/install.sh.")
        if progress:
            progress("Installing Falco…", 60)
        env = os.environ.copy()
        env["PHONON_INSTALL_BASE"] = install_base()
        env["PHONON_BIN_DIR"] = bin_dir()
        env.setdefault("PHONON_DESKTOP_DIR",
                       os.path.join(_home(), ".local/share/applications"))
        result = subprocess.run(
            ["bash", os.path.join(source, "linux/install.sh")],
            cwd=source, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            lines = (result.stderr or result.stdout).strip().splitlines()
            return (False, lines[-1] if lines else f"installer exited {result.returncode}")
        if progress:
            progress(f"Installed Falco {version}.", 100)
        _mark_updated(version)
        logger.info(f"Falco {version} installed")
        return (True, f"Falco {version} is installed.")
    except Exception as e:
        logger.warning(f"Update to {tag} failed: {e}")
        return (False, str(e))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _marker_path() -> str:
    from . import config
    return os.path.join(config.get_data_dir(), ".just_updated")


def _mark_updated(version: str) -> None:
    try:
        path = _marker_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(version)
    except OSError as e:
        logger.info(f"Could not write the update marker: {e}")


def check_just_updated() -> Optional[str]:
    """The version just installed, once, for the startup notice."""
    path = _marker_path()
    try:
        with open(path, encoding="utf-8") as f:
            version = f.read().strip()
    except OSError:
        return None
    try:
        os.remove(path)
    except OSError:
        pass
    return version or None


def restart_via_launcher() -> Tuple[bool, str]:
    """Start the new release once this process has exited, then quit."""
    path = launcher()
    if not os.access(path, os.X_OK):
        return (False, f"{path} is missing or not executable; restart Falco manually.")
    from .update_install import handover_script
    script = handover_script(os.getpid(), shlex.quote(path))
    try:
        subprocess.Popen(["/bin/sh", "-c", script], start_new_session=True, close_fds=True)
    except OSError as e:
        return (False, f"Could not start the new instance: {e}")
    return (True, "restarting")


def run_update_ui(parent, release: dict, restart, failed=None) -> None:
    """Install *release* behind a progress window, then call *restart()*."""
    from .progress_window import run_with_progress
    from .ui_style import show_message
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    tag = release.get("tag_name") or f"v{release.get('version', '')}"

    def work(progress):
        return install(tag, progress)

    def finish(result):
        ok, message = result if result else (False, "The update was interrupted.")
        if ok:
            restart()
        elif failed:
            failed(message)
        else:
            show_message(parent, Gtk.MessageType.ERROR, "Update failed", message)

    run_with_progress(parent, "Updating Falco", "Starting download…", work, finish)


def auto_update(tray, delay_seconds: int = 45) -> bool:
    """Schedule the once-a-day startup check; it installs a newer release."""
    from gi.repository import GLib
    from .config import load_config
    from . import update_checker

    config = load_config()
    if not config.auto_check_updates:
        logger.debug("Startup update check is off")
        return False
    if not update_checker.should_check_today(config.last_update_check):
        logger.debug("Already checked for updates today")
        return False
    if not is_managed_install():
        logger.debug("This install is not managed by install.sh")
        return False

    def start():
        from . import recording_state
        if getattr(recording_state.state, "is_recording", False):
            GLib.timeout_add_seconds(60, start)
            return False
        threading.Thread(target=_auto_update_worker, args=(tray,),
                         daemon=True, name="Falco update").start()
        return False

    GLib.timeout_add_seconds(delay_seconds, start)
    return False


def _auto_update_worker(tray) -> None:
    from gi.repository import GLib
    from .config import record_update_check
    from . import update_checker

    result = check()
    if not result.get("success"):
        logger.info(f"Startup update check failed: {result.get('error')}")
        return
    GLib.idle_add(record_update_check, update_checker.get_current_timestamp())
    if not result.get("update_available"):
        logger.info("Falco is up to date")
        return
    release = result["release"]
    logger.info(f"Installing Falco {release['version']} at startup")
    ok, message = install(release["tag_name"])
    if not ok:
        logger.warning(f"Startup update failed: {message}")
        return
    GLib.idle_add(tray.restart_app)
