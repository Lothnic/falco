"""Recent Dictations: the list the dashboard, the tray menu and "Fix a Word"
all read. A damaged file must leave them working, and a dictation must never
be lost from the list by accident."""
import json
import os

import pytest

from localdictation import history


@pytest.fixture(autouse=True)
def runtime_dir(tmp_path, monkeypatch):
    """A private session folder, which is where the list lives: without one
    history keeps nothing at all."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize("payload", ["null", "5", '"text"', '{"a": 1}', "[[1, 2]]",
                                     "not json at all", ""])
def test_a_damaged_list_is_read_as_empty_rather_than_raising(payload):
    """These are all valid files; what they hold is not a list of strings. The
    dashboard and the tray menu call this and would go down with it."""
    path = history.history_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(payload)
    assert history.get_entries() == []


def test_a_list_of_strings_is_read_newest_first():
    path = history.history_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(["newest", "older", 3, None], f)
    # Things that aren't strings are dropped, not fatal.
    assert history.get_entries() == ["newest", "older"]


def test_a_dictation_is_kept_and_read_back():
    history.add_entry("meet me at noon")
    assert history.get_entries() == ["meet me at noon"]


def test_the_list_is_cut_to_its_limit():
    for number in range(history.MAX_ENTRIES + 5):
        history.add_entry(f"dictation {number}")
    entries = history.get_entries()
    assert len(entries) == history.MAX_ENTRIES
    assert entries[0] == f"dictation {history.MAX_ENTRIES + 4}"


def test_a_grown_entry_replaces_the_one_it_grew_from():
    """Type at pause adds to one entry per recording; the shorter version must
    not be left behind beside it."""
    history.add_entry("meet me at")
    history.add_entry("meet me at noon", replaces="meet me at")
    assert history.get_entries() == ["meet me at noon"]


def test_forget_takes_it_back_out():
    history.add_entry("a secret")
    history.add_entry("something else")
    history.forget("a secret")
    assert history.get_entries() == ["something else"]


def test_an_empty_dictation_is_not_kept():
    history.add_entry("   ")
    assert history.get_entries() == []


def test_without_a_private_session_folder_nothing_is_written(tmp_path, monkeypatch):
    """No XDG_RUNTIME_DIR means no trustworthy place on disk for dictated
    text, so the list keeps nothing rather than using /tmp."""
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(history, "history_path", lambda: None)
    history.add_entry("should not be written anywhere")
    assert history.get_entries() == []
