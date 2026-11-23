import os
import shutil
import tarfile
from types import SimpleNamespace

from localdictation import self_update


def test_a_newer_release_is_detected():
    assert self_update.is_newer("2.0.1", "2.0.0")
    assert self_update.is_newer("10.0", "9.9")
    assert not self_update.is_newer("2.0.0", "2.0.0")
    assert not self_update.is_newer("1.9.9", "2.0.0")


def test_check_reports_the_latest_release(monkeypatch):
    monkeypatch.setattr(self_update, "current_version", lambda: "2.0.0")
    monkeypatch.setattr(self_update, "latest_release", lambda: {
        "tag_name": "v2.0.1", "version": "2.0.1", "html_url": "u", "body": "notes"})
    result = self_update.check()
    assert result["success"] and result["update_available"]
    assert result["latest_version"] == "2.0.1"
    assert result["release"]["html_url"] == "u"


def test_check_reports_a_failed_lookup(monkeypatch):
    def fail():
        raise OSError("offline")
    monkeypatch.setattr(self_update, "latest_release", fail)
    result = self_update.check()
    assert not result["success"] and "offline" in result["error"]


def test_install_runs_the_release_installer(monkeypatch, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    archive = work / "falco.tar.gz"
    source = tmp_path / "falco-2.0.1"
    (source / "linux").mkdir(parents=True)
    (source / "linux/install.sh").write_text("#!/bin/sh\n")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(source, arcname="falco-2.0.1")

    monkeypatch.setattr(self_update, "_download", lambda tag, dest, progress=None:
                        shutil.copyfile(archive, dest))
    monkeypatch.setattr(self_update, "install_base", lambda: str(tmp_path / "base"))
    monkeypatch.setattr(self_update, "bin_dir", lambda: str(tmp_path / "bin"))
    marked = []
    monkeypatch.setattr(self_update, "_mark_updated", marked.append)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(self_update.subprocess, "run", fake_run)
    ok, message = self_update.install("v2.0.1")
    assert ok, message
    assert calls[0][0][-1].endswith("linux/install.sh")
    env = calls[0][1]["env"]
    assert env["PHONON_INSTALL_BASE"] == str(tmp_path / "base")
    assert env["PHONON_BIN_DIR"] == str(tmp_path / "bin")
    assert marked == ["2.0.1"]


def test_install_rejects_an_unexpected_tag():
    ok, message = self_update.install("main")
    assert not ok and "unexpected release tag" in message


def test_install_reports_the_installer_failure(monkeypatch, tmp_path):
    archive = tmp_path / "falco.tar.gz"
    source = tmp_path / "falco-2.0.1"
    (source / "linux").mkdir(parents=True)
    (source / "linux/install.sh").write_text("#!/bin/sh\n")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(source, arcname="falco-2.0.1")
    monkeypatch.setattr(self_update, "_download", lambda tag, dest, progress=None:
                        shutil.copyfile(archive, dest))
    monkeypatch.setattr(self_update, "install_base", lambda: str(tmp_path / "base"))
    monkeypatch.setattr(self_update, "bin_dir", lambda: str(tmp_path / "bin"))
    monkeypatch.setattr(self_update.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=1, stdout="", stderr="no room\n"))
    ok, message = self_update.install("v2.0.1")
    assert not ok and message == "no room"


def test_the_update_marker_is_read_once(monkeypatch, tmp_path):
    monkeypatch.setattr(self_update, "_marker_path",
                        lambda: str(tmp_path / "data/.just_updated"))
    self_update._mark_updated("2.0.1")
    assert self_update.check_just_updated() == "2.0.1"
    assert self_update.check_just_updated() is None


def test_managed_install_requires_the_launcher(monkeypatch, tmp_path):
    monkeypatch.setattr(self_update, "install_base", lambda: str(tmp_path))
    monkeypatch.setattr(self_update, "package_path",
                        lambda: str(tmp_path / "releases/2.0.0/.venv/x.py"))
    monkeypatch.setattr(self_update, "launcher", lambda: str(tmp_path / "bin/falco"))
    assert not self_update.is_managed_install()
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin/falco").write_text("")
    assert self_update.is_managed_install()


def test_restart_starts_the_launcher_after_this_process(monkeypatch, tmp_path):
    launcher = tmp_path / "falco"
    launcher.write_text("#!/bin/sh\n")
    launcher.chmod(0o755)
    monkeypatch.setattr(self_update, "launcher", lambda: str(launcher))
    started = []
    monkeypatch.setattr(self_update.subprocess, "Popen",
                        lambda command, **kwargs: started.append((command, kwargs)))
    ok, message = self_update.restart_via_launcher()
    assert ok, message
    script = started[0][0][-1]
    assert str(os.getpid()) in script and str(launcher) in script
    assert started[0][1]["start_new_session"] is True
