import os

from localdictation import legacy_migration


def make_old_install(home):
    old_config = home / ".config/phonon-linux"
    old_data = home / ".local/share/PhononLinux"
    old_config.mkdir(parents=True)
    old_data.mkdir(parents=True)
    (old_config / "config.toml").write_text('model = "parakeet-v3"\ndevice = "cpu"\n')
    (old_config / "custom_words.txt").write_text("Falco\n")
    (old_config / "custom_commands.toml").write_text('["x"]\n')
    (old_config / "backups").mkdir()
    (old_config / "backups/one.zip").write_text("zip")
    (old_data / ".first_run_done").write_text("done")
    (old_data / "parakeet-ultra").mkdir()
    (old_data / "parakeet-ultra/model.onnx").write_text("model")
    (old_data / "stats.json").write_text("{}")
    return old_config, old_data


def test_settings_marker_and_models_come_across(tmp_path):
    home = tmp_path
    old_config, old_data = make_old_install(home)
    new_config = home / ".config/phonon-linux-app"
    new_data = home / ".local/share/PhononLinuxApp"
    new_config.mkdir(parents=True)
    new_data.mkdir(parents=True)
    (new_config / "config.toml").write_text('device = "vulkan"\n')

    done = legacy_migration.migrate(str(home))

    assert "settings" in " ".join(done)
    assert (new_config / "config.toml").read_text() == (old_config / "config.toml").read_text()
    assert (new_config / "config.toml.before-migration").read_text() == 'device = "vulkan"\n'
    assert (new_config / "custom_words.txt").read_text() == "Falco\n"
    assert (new_config / "backups/one.zip").exists()
    assert (new_data / ".first_run_done").exists()
    assert (new_data / "parakeet-ultra").exists()
    assert os.path.realpath(new_data / "parakeet-ultra") == \
        os.path.realpath(old_data / "parakeet-ultra")
    assert (new_data / "stats.json").exists()


def test_a_finished_install_is_left_alone(tmp_path):
    home = tmp_path
    make_old_install(home)
    new_data = home / ".local/share/PhononLinuxApp"
    new_data.mkdir(parents=True)
    (new_data / ".first_run_done").write_text("done")

    assert legacy_migration.migrate(str(home)) == []
    assert not (home / ".config/phonon-linux-app").exists()


def test_no_old_install_is_harmless(tmp_path):
    assert legacy_migration.migrate(str(tmp_path)) == []
