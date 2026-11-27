import os
import subprocess
import sys

import pytest

from localdictation import legacy_install


def release(base, folder="0.1.0", version="0.1.0", name="falco-dictation"):
    root = base / "releases" / folder
    (root / "src/localdictation").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        f'[tool.poetry]\nname = "{name}"\nversion = "{version}"\n')
    (root / "src/localdictation/__init__.py").write_text(f'__version__ = "{version}"\n')
    return root


@pytest.mark.parametrize("folder,version,name", [
    ("0.1.1", "0.1.1", "falco-dictation"),
    ("2.5.1", "2.5.1", "falco-dictation"),
    ("0.1.0", "2.5.1", "falco-dictation"),
    ("0.1.0", "0.1.0", "another-application"),
])
def test_only_identifiable_exact_010_is_eligible(tmp_path, folder, version, name):
    assert not legacy_install.is_010(release(tmp_path, folder, version, name))


def test_disagreeing_or_symlinked_release_is_not_removed(tmp_path):
    root = release(tmp_path)
    (root / "src/localdictation/__init__.py").write_text('__version__ = "2.5.1"\n')
    assert not legacy_install.is_010(root)
    link = tmp_path / "0.1.0"
    link.symlink_to(root, target_is_directory=True)
    assert not legacy_install.is_010(link)


def test_autostart_is_recreated_for_current_launcher_and_other_entries_survive(tmp_path):
    base, bin_dir, desktop, autostart = [tmp_path / x for x in ("app", "bin", "desktop", "autostart")]
    root = release(base)
    autostart.mkdir()
    old = autostart / "falco.desktop"
    old.write_text(f'[Desktop Entry]\nName=Falco\nExec="{root}/run.sh"\nHidden=false\n')
    other = autostart / "other.desktop"
    other.write_text('[Desktop Entry]\nExec=/another/app\n')
    legacy_install.begin(base, bin_dir, desktop, autostart, tmp_path / "prototype")
    assert not root.exists() and not old.exists()
    assert other.exists()
    legacy_install.finish(base / ".legacy-0.1.0.json", commit=True)
    assert 'Hidden=false' in old.read_text()
    assert f'Exec="{bin_dir}/falco"' in old.read_text()
    assert not root.exists()
    assert not list(autostart.glob('.falco-0.1.0-*'))


def test_interrupted_install_can_be_rolled_back(tmp_path):
    base = tmp_path / "app"
    root = release(base)
    args = (base, tmp_path / "bin", tmp_path / "desktop", tmp_path / "autostart", tmp_path / "prototype")
    legacy_install.begin(*args)
    assert not root.exists()
    legacy_install.finish(base / ".legacy-0.1.0.json")
    assert legacy_install.is_010(root)
    assert not (base / ".legacy-0.1.0.json").exists()


def test_only_old_app_processes_are_stopped(tmp_path):
    root = release(tmp_path)
    python = root / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    (root / "src/localdictation/prefs.py").write_text('import time\ntime.sleep(60)\n')
    old = subprocess.Popen([str(python), "-m", "localdictation.prefs"],
                           env={**os.environ, "PYTHONPATH": str(root / "src")})
    unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"])
    try:
        legacy_install.stop_old_processes([root])
        assert old.wait(timeout=3) != 0
        assert unrelated.poll() is None
    finally:
        for process in (old, unrelated):
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=3)


def test_activation_interrupted_before_cleanup_finishes_the_migration(tmp_path):
    base, bin_dir = tmp_path / "app", tmp_path / "bin"
    old = release(base)
    bin_dir.mkdir()
    launcher = bin_dir / "falco"
    launcher.symlink_to(old / "run.sh")
    legacy_install.begin(base, bin_dir, tmp_path / "desktop", tmp_path / "autostart", tmp_path / "prototype")
    replacement = release(base, "2.6.0.new", "2.6.0")
    (replacement / ".venv/bin").mkdir(parents=True)
    (replacement / ".venv/bin/python").write_text("interpreter")
    (replacement / "run.sh").write_text("launcher")
    launcher.symlink_to(replacement / "run.sh")
    legacy_install.finish(base / ".legacy-0.1.0.json")
    assert launcher.resolve() == replacement / "run.sh"
    assert not old.exists()
    assert not list(old.parent.glob('.falco-0.1.0-*'))


def test_legacy_root_alias_is_not_removed_twice(tmp_path):
    base = tmp_path / "app"
    old = release(base)
    alias = tmp_path / "prototype"
    alias.symlink_to(base, target_is_directory=True)
    legacy_install.begin(base, tmp_path / "bin", tmp_path / "desktop", tmp_path / "autostart", alias)
    assert not old.exists()
    legacy_install.finish(base / ".legacy-0.1.0.json", commit=True)
    assert not old.exists()
