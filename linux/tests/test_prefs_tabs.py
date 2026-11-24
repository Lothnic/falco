"""The Preferences window's tabs: every tab is registered with the notebook,
and the ones the tray opens by name can be found.

An Updates & Backup tab was built but never appended to the notebook, so the
update check, settings backup and uninstall were unreachable. These tests fail
if a tab is built and then dropped again.

The tabs read the installed models while they build, which reaches for
huggingface_hub: a dependency of the speech engine, not of this app, and absent
from a bare test environment. The model lookup is stubbed so the tab structure
can be checked without it."""
import sys
from dataclasses import asdict
from unittest.mock import MagicMock

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import pytest  # noqa: E402

from localdictation import config, prefs  # noqa: E402


@pytest.fixture(autouse=True)
def _no_model_lookup(monkeypatch):
    """Answer "which models are on disk" without the download stack."""
    if "huggingface_hub" not in sys.modules:
        monkeypatch.setitem(sys.modules, "huggingface_hub", MagicMock())
    from localdictation import ai_download, parakeet_engine
    monkeypatch.setattr(ai_download, "is_installed", lambda *a: False)
    monkeypatch.setattr(parakeet_engine, "cached_model_dir", lambda *a, **k: None,
                        raising=False)


@pytest.fixture
def window(monkeypatch):
    """A PreferencesWindow with only what _build_tabs needs: the saved
    settings as a dict, and the scroll controllers it keeps alive."""
    window = prefs.PreferencesWindow.__new__(prefs.PreferencesWindow)
    window.config = asdict(config.load_config())
    window._scroll_controllers = []
    window._tabs = []
    return window


def _labels(notebook):
    return [notebook.get_tab_label_text(notebook.get_nth_page(i))
            for i in range(notebook.get_n_pages())]


def test_every_built_tab_reaches_the_notebook(window):
    notebook = prefs.PreferencesWindow._build_tabs(window)
    labels = _labels(notebook)
    # Every tab the window keeps is one the notebook shows.
    assert len(labels) == len(window._tabs)
    assert labels == [label for label in labels if label]


def test_updates_and_backup_is_shown(window):
    """The tab the tray opens with --tab updates, and whose uninstall and
    backup live nowhere else."""
    assert "Updates & Backup" in _labels(prefs.PreferencesWindow._build_tabs(window))


@pytest.mark.parametrize("name", ["stats", "updates", "backup", "words", "general"])
def test_the_tray_can_open_each_tab_by_name(window, name):
    prefs.PreferencesWindow._build_tabs(window)
    assert window.select_tab(name) is True
