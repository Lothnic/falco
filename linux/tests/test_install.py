import os
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LOCAL_INSTALLER = ROOT / "linux/install.sh"
WEB_INSTALLER = ROOT / "website/public/install.sh"


def executable(path, script):
    path.write_text(script)
    path.chmod(0o755)


@pytest.fixture
def install_env(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    executable(stubs / "uv", "#!/bin/sh\nexit \"${FALCO_TEST_INSTALL_EXIT:-0}\"\n")
    env = os.environ.copy()
    env.pop("FALCO_REF", None)
    env.update(HOME=str(tmp_path), TMPDIR=str(tmp_path), PATH=f"{stubs}:{env['PATH']}",
               PHONON_INSTALL_BASE=str(tmp_path / "app releases"),
               PHONON_BIN_DIR=str(tmp_path / "my bin"),
               PHONON_DESKTOP_DIR=str(tmp_path / "desktop"))
    import tomllib
    version = tomllib.loads((ROOT / "linux/pyproject.toml").read_text())["tool"]["poetry"]["version"]
    cache = Path(env["PHONON_INSTALL_BASE"]) / "rune" / version
    cache.mkdir(parents=True)
    (cache / "VERSION").write_text(version)
    for name in ("phonon-window", "phonon-overlay"):
        executable(cache / name, "#!/bin/sh\nexit 0\n")
    return env


def run_installer(path, env, *args, **overrides):
    return subprocess.run(["bash", path, *args], env=env | overrides,
                          capture_output=True, text=True, timeout=30, check=False)


def test_failed_install_can_be_retried(install_env):
    releases = Path(install_env["PHONON_INSTALL_BASE"]) / "releases"
    launcher = Path(install_env["PHONON_BIN_DIR"]) / "falco"
    result = run_installer(LOCAL_INSTALLER, install_env, FALCO_TEST_INSTALL_EXIT="42")
    assert result.returncode == 42, result.stderr
    assert list(releases.iterdir()) == []
    assert not launcher.is_symlink()

    result = run_installer(LOCAL_INSTALLER, install_env)
    assert result.returncode == 0, result.stderr
    assert os.access(launcher, os.X_OK)
    assert launcher.resolve().parent.parent == releases
    assert "670 MB" in result.stdout and "1 GB" in result.stdout


def test_upgrade_keeps_the_legacy_release_until_the_new_one_succeeds(install_env):
    legacy = Path(install_env["PHONON_INSTALL_BASE"]) / "releases/0.1.0/run.sh"
    legacy.parent.mkdir(parents=True)
    executable(legacy, "#!/bin/sh\n")
    launcher = Path(install_env["PHONON_BIN_DIR"]) / "falco"
    launcher.parent.mkdir()
    launcher.symlink_to(legacy)
    desktop = Path(install_env["PHONON_DESKTOP_DIR"]) / "falco.desktop"
    desktop.parent.mkdir()
    old_desktop = f'[Desktop Entry]\nExec="{legacy}"\n'
    desktop.write_text(old_desktop)

    result = run_installer(LOCAL_INSTALLER, install_env, FALCO_TEST_INSTALL_EXIT="42")
    assert result.returncode == 42, result.stderr
    assert launcher.resolve() == legacy
    assert desktop.read_text() == old_desktop
    assert list(legacy.parent.parent.iterdir()) == [legacy.parent]

    result = run_installer(LOCAL_INSTALLER, install_env)
    assert result.returncode == 0, result.stderr
    assert launcher.resolve() != legacy
    assert os.access(launcher, os.X_OK) and os.access(legacy, os.X_OK)
    assert f'Exec="{launcher}"' in desktop.read_text()


@pytest.mark.skipif(os.geteuid() == 0, reason="The public installer requires a normal user")
@pytest.mark.parametrize(("status", "ref", "archive_path"), [
    ("200", None, "/archive/refs/tags/v2.0.0.tar.gz"),
    ("404", None, "/archive/main.tar.gz"),
    ("403", None, None),
    ("403", "preview/next", "/archive/preview/next.tar.gz"),
])
def test_public_installer_selects_the_release(install_env, tmp_path, status, ref, archive_path):
    source = tmp_path / "source/linux"
    source.mkdir(parents=True)
    executable(source / "install.sh", "#!/bin/sh\necho 'Selected archive installed'\n")
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(source.parent, arcname="falco-source")
    calls = tmp_path / "requests"
    executable(tmp_path / "stubs/curl", r"""#!/bin/bash
set -eu
while (($#)); do
    case "$1" in
        -o) output="$2"; shift ;;
        https://*) url="$1" ;;
    esac
    shift
done
printf '%s\n' "$url" >> "$FALCO_TEST_CALLS"
case "$url" in
    */releases/latest)
        printf '{"tag_name":"v2.0.0"}' > "$output"
        printf '%s' "$FALCO_TEST_STATUS"
        ;;
    */archive/*) cp "$FALCO_TEST_ARCHIVE" "$output" ;;
    *) exit 1 ;;
esac
""")
    args = ("--no-deps", "--ref", ref) if ref else ("--no-deps",)
    result = run_installer(WEB_INSTALLER, install_env, *args,
                           FALCO_TEST_STATUS=status, FALCO_TEST_CALLS=str(calls),
                           FALCO_TEST_ARCHIVE=str(archive))
    requests = calls.read_text().splitlines()
    if ref is None:
        assert requests[0].endswith("/releases/latest")
    else:
        assert len(requests) == 1
    if archive_path:
        assert result.returncode == 0, result.stderr
        assert requests[-1].endswith(archive_path)
        assert "Selected archive installed" in result.stdout
        if status == "404":
            assert "no published release" in result.stdout
    else:
        assert result.returncode != 0
        assert len(requests) == 1


def test_rune_launcher_preserves_cli_and_explicit_legacy_mode(install_env):
    result = run_installer(LOCAL_INSTALLER, install_env)
    assert result.returncode == 0, result.stderr
    launcher = (Path(install_env["PHONON_BIN_DIR"]) / "falco").resolve()
    python = launcher.parent / ".venv/bin/python"
    python.parent.mkdir(parents=True, exist_ok=True)
    python.unlink(missing_ok=True)
    executable(python, '#!/bin/sh\nprintf "%s\\n" "$@"\n')
    command = subprocess.run([str(launcher), "transcribe", "--help"], env=install_env,
                             capture_output=True, text=True, check=True)
    assert command.stdout.splitlines() == ["-m", "localdictation.cli", "transcribe", "--help"]
    legacy = subprocess.run([str(launcher)], env=install_env | {"FALCO_LEGACY_UI": "1"},
                            capture_output=True, text=True, check=True)
    assert legacy.stdout.splitlines() == ["-m", "localdictation.cli"]
