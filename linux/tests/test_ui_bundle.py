"""Release bundles must be matched and checked before the launcher changes."""
import hashlib
import io
import tarfile

import pytest

from localdictation import ui_bundle


def bundle(path, version="2.5.1", extra=None):
    with tarfile.open(path, "w:gz") as archive:
        files = {"VERSION": version.encode(), "phonon-window": b"binary", "phonon-overlay": b"binary"}
        if extra:
            files.update(extra)
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))


def test_bundle_rejects_wrong_version_and_paths(tmp_path):
    archive = tmp_path / "bundle.tar.gz"
    target = tmp_path / "target"
    target.mkdir()
    bundle(archive, "2.5.0")
    with pytest.raises(ValueError, match="wrong version"):
        ui_bundle.unpack(archive, target, "2.5.1")
    bundle(archive, extra={"../escape": b"bad"})
    with pytest.raises(ValueError, match="Unexpected files"):
        ui_bundle.unpack(archive, target, "2.5.1")
    assert not (tmp_path / "escape").exists()


def test_stale_cache_is_never_accepted_and_bad_download_keeps_it(monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "VERSION").write_text("2.5.0")
    for name in ("phonon-window", "phonon-overlay"):
        (cache / name).write_text("old binary")
    monkeypatch.setattr(ui_bundle.platform, "system", lambda: "Linux")
    monkeypatch.setattr(ui_bundle.platform, "machine", lambda: "x86_64")
    def fetch(url, destination):
        if url.endswith(".tar.gz"):
            bundle(destination)
        else:
            destination.write_text("0" * 64 + "  falco-rune-v2.5.1-linux-x86_64.tar.gz")
    monkeypatch.setattr(ui_bundle, "fetch", fetch)
    with pytest.raises(ValueError, match="checksum"):
        ui_bundle.install("2.5.1", cache)
    assert (cache / "VERSION").read_text() == "2.5.0"


def test_verified_download_installs_matching_binaries(monkeypatch, tmp_path):
    monkeypatch.setattr(ui_bundle.platform, "system", lambda: "Linux")
    monkeypatch.setattr(ui_bundle.platform, "machine", lambda: "x86_64")
    digest = []
    def fetch(url, destination):
        if url.endswith(".tar.gz"):
            bundle(destination)
            digest.append(hashlib.sha256(destination.read_bytes()).hexdigest())
        else:
            destination.write_text(digest[0] + "  falco-rune-v2.5.1-linux-x86_64.tar.gz")
    monkeypatch.setattr(ui_bundle, "fetch", fetch)
    from types import SimpleNamespace
    monkeypatch.setattr(ui_bundle.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout="2.5.1\n"))
    cache = tmp_path / "cache"
    assert ui_bundle.install("2.5.1", cache)
    assert ui_bundle.matches(cache, "2.5.1")
    assert (cache / "phonon-window").stat().st_mode & 0o111
