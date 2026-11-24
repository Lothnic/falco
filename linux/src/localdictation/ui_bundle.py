"""Install the exact release's Rune binaries, never an older cached dashboard.

Kept standard-library-only so the source installer can run it before starting
the app. Official Linux x86_64 bundles are built and tested on Ubuntu in CI.
"""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request

FILES = ("phonon-window", "phonon-overlay", "VERSION")
BASE = "https://github.com/Lothnic/falco/releases/download"


def matches(folder, version):
    try:
        return ((folder / "VERSION").read_text().strip() == version
                and all((folder / name).is_file() for name in FILES))
    except OSError:
        return False


def fetch(url, destination):
    request = urllib.request.Request(url, headers={"User-Agent": "Falco-installer"})
    with urllib.request.urlopen(request, timeout=60) as response, open(destination, "wb") as output:
        shutil.copyfileobj(response, output)


def unpack(archive, target, version):
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        if {m.name for m in members} != set(FILES) or len(members) != len(FILES) or any(not m.isfile() for m in members):
            raise ValueError("Unexpected files in the Rune bundle.")
        for member in members:
            if member.size > 200 * 1024 * 1024:
                raise ValueError("Unexpected size in the Rune bundle.")
            with source.extractfile(member) as stream, open(target / member.name, "wb") as output:
                shutil.copyfileobj(stream, output)
            (target / member.name).chmod(0o644 if member.name == "VERSION" else 0o755)
    if not matches(target, version):
        raise ValueError("The Rune bundle has the wrong version.")


def install(version, cache, built=None):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid UI release version.")
    cache = Path(cache)
    if matches(cache, version):
        return True
    cache.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".rune-download-", dir=cache.parent) as work:
        stage = Path(work) / "bundle"
        stage.mkdir()
        if built and matches(Path(built), version):
            for name in FILES:
                shutil.copy2(Path(built) / name, stage / name)
        else:
            if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
                return False
            name = f"falco-rune-v{version}-linux-x86_64.tar.gz"
            archive, checksums = Path(work) / name, Path(work) / "SHA256SUMS.txt"
            fetch(f"{BASE}/v{version}/{name}", archive)
            fetch(f"{BASE}/v{version}/SHA256SUMS.txt", checksums)
            expected = next((line.split()[0] for line in checksums.read_text().splitlines()
                             if len(line.split()) == 2 and line.split()[1].lstrip("*") == name), None)
            actual = hashlib.sha256(archive.read_bytes()).hexdigest()
            if expected != actual:
                raise ValueError("Rune bundle checksum did not match. The download was not installed.")
            unpack(archive, stage, version)
        result = subprocess.run([str(stage / "phonon-window"), "--version"], capture_output=True,
                                text=True, timeout=5)
        if result.returncode or result.stdout.strip() != version:
            raise ValueError("The Rune dashboard cannot run on this computer.")
        if cache.exists():
            # An incomplete cache cannot replace a working release: the caller
            # links to this version only after installation succeeds.
            shutil.rmtree(cache)
        os.replace(stage, cache)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--built")
    args = parser.parse_args()
    try:
        ok = install(args.version, args.cache, args.built)
    except (OSError, ValueError, tarfile.TarError, subprocess.SubprocessError, urllib.error.URLError) as error:
        print(f"Rune UI unavailable: {error}. The GTK fallback remains available.")
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
