"""Carry the old Phonon Linux prototype's folders into Falco's.

The prototype (``tuxtalk`` 0.22.0) kept settings in ``~/.config/phonon-linux``
and data in ``~/.local/share/PhononLinux``; Falco uses
``~/.config/phonon-linux-app`` and ``~/.local/share/PhononLinuxApp``. An
install over the prototype would otherwise start first-run setup again, with
the user's settings and 600 MB of models left behind.

Runs first in every entry point, before the first-run check. Never deletes:
an unfinished new settings file is kept beside the old one, and the models
are linked rather than copied.
"""
import os
import shutil

from .logger import setup_logger

logger = setup_logger(__name__)

OLD_CONFIG = os.path.join(".config", "phonon-linux")
OLD_DATA = os.path.join(".local", "share", "PhononLinux")
NEW_CONFIG = os.path.join(".config", "phonon-linux-app")
NEW_DATA = os.path.join(".local", "share", "PhononLinuxApp")
DONE = ".first_run_done"
SHARED = ("parakeet-ultra", "ai-engine", "rune", "stats.json")
SMALL = ("custom_words.txt", "custom_commands.toml")


def _share_or_copy(source, destination):
    """Link *source* at *destination*, falling back to a copy."""
    try:
        os.symlink(source, destination)
    except OSError:
        if os.path.isdir(source):
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)


def migrate(home=None):
    """Do the move; return one line per thing done, for the log. Never raises."""
    home = home or os.path.expanduser("~")
    old_config = os.path.join(home, OLD_CONFIG)
    old_data = os.path.join(home, OLD_DATA)
    new_config = os.path.join(home, NEW_CONFIG)
    new_data = os.path.join(home, NEW_DATA)
    done = []

    try:
        if not os.path.isdir(old_data):
            return done
        if os.path.exists(os.path.join(new_data, DONE)):
            return done                 # already migrated or a real new install
        os.makedirs(new_data, exist_ok=True)

        old_toml = os.path.join(old_config, "config.toml")
        new_toml = os.path.join(new_config, "config.toml")
        if os.path.isfile(old_toml):
            os.makedirs(new_config, exist_ok=True)
            if os.path.exists(new_toml):
                # First-run on the new name wrote defaults seconds ago; the
                # old file is the settings the user actually chose.
                shutil.copy2(new_toml, new_toml + ".before-migration")
            shutil.copy2(old_toml, new_toml)
            done.append(f"settings from {old_toml}")

        for name in SMALL:
            source = os.path.join(old_config, name)
            destination = os.path.join(new_config, name)
            if os.path.isfile(source) and not os.path.exists(destination):
                shutil.copy2(source, destination)
                done.append(name)

        backups = os.path.join(old_config, "backups")
        new_backups = os.path.join(new_config, "backups")
        if os.path.isdir(backups) and not os.path.isdir(new_backups):
            shutil.copytree(backups, new_backups)
            done.append("backups")

        for name in SHARED:
            source = os.path.join(old_data, name)
            destination = os.path.join(new_data, name)
            if os.path.exists(source) and not os.path.lexists(destination):
                _share_or_copy(source, destination)
                done.append(name)

        old_done = os.path.join(old_data, DONE)
        if os.path.exists(old_done):
            shutil.copy2(old_done, os.path.join(new_data, DONE))
            done.append("first-run state")
    except Exception as e:      # a migration problem never stops the app
        logger.warning(f"Carrying over the old Phonon Linux install failed: {e}")
        return done

    if done:
        logger.info("Carried over the old Phonon Linux install: " + ", ".join(done))
    return done
