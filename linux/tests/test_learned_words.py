from localdictation import learned_words
from localdictation import live_settings as live


def setup_store(monkeypatch, tmp_path, enabled=True):
    monkeypatch.setattr(learned_words, "path",
                        lambda: str(tmp_path / "learned_words.json"))
    monkeypatch.setattr(live, "learn_words", enabled)


def test_a_name_joins_after_two_fixes(monkeypatch, tmp_path):
    setup_store(monkeypatch, tmp_path)
    assert learned_words.observe("we use github", "we use GitHub") == []
    assert learned_words.words() == []
    assert learned_words.observe("push it to github", "push it to GitHub") == ["GitHub"]
    assert learned_words.words() == ["GitHub"]
    assert learned_words.all_entries() == [("GitHub", 2)]


def test_a_compound_name_joins(monkeypatch, tmp_path):
    setup_store(monkeypatch, tmp_path)
    learned_words.observe("the tux talk app", "the TuxTalk app")
    assert learned_words.observe("open tux talk", "open TuxTalk") == ["TuxTalk"]


def test_rewrites_are_not_learned(monkeypatch, tmp_path):
    setup_store(monkeypatch, tmp_path)
    for _ in range(2):
        learned_words.observe("im gonna go", "I'm going to go")
    assert learned_words.words() == []


def test_sentence_starts_and_word_splits_are_not_learned(monkeypatch, tmp_path):
    setup_store(monkeypatch, tmp_path)
    for _ in range(2):
        learned_words.observe("the app is maybe ready", "The app may be ready")
    assert learned_words.words() == []


def test_acronyms_are_learned(monkeypatch, tmp_path):
    setup_store(monkeypatch, tmp_path)
    learned_words.observe("the api is ready", "the API is ready")
    assert learned_words.observe("call the api", "call the API") == ["API"]


def test_turning_it_off_learns_nothing(monkeypatch, tmp_path):
    setup_store(monkeypatch, tmp_path, enabled=False)
    for _ in range(2):
        learned_words.observe("we use github", "we use GitHub")
    assert learned_words.words() == []


def test_user_words_win_and_clear_forgets(monkeypatch, tmp_path):
    setup_store(monkeypatch, tmp_path)
    for _ in range(2):
        learned_words.observe("we use github", "we use GitHub")
    assert learned_words.merge(["github"]) == ["github"]
    assert learned_words.merge([]) == ["GitHub"]

    learned_words.clear()
    assert learned_words.words() == []
