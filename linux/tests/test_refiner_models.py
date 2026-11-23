from types import SimpleNamespace

from localdictation import ai_download


def cfg(language="en", choice="auto"):
    return SimpleNamespace(refiner_model=choice, language_mode="manual",
                           language=language, dictation_language="")


def test_auto_uses_phonon_for_english():
    assert ai_download.selected_model(cfg("en")) == "phonon"


def test_auto_uses_the_1b_model_for_hindi():
    assert ai_download.selected_model(cfg("hi")) == "gemma-3-1b"


def test_an_explicit_model_wins():
    assert ai_download.selected_model(cfg("hi", "llama-3.2-1b")) == "llama-3.2-1b"


def test_sizes_are_the_hindi_model_s_own():
    assert ai_download.model_size_text("gemma-3-1b") == "810 MB"
    assert ai_download.download_size_text("gemma-3-1b") == "840 MB"
    assert ai_download.model_size_text("phonon") == "989 MB"


def test_model_path_uses_the_chosen_repository(monkeypatch):
    calls = []
    monkeypatch.setattr("localdictation.download_utils.cached_hub_file",
                        lambda repo, file: calls.append((repo, file)) or "/model.gguf")
    assert ai_download.model_path("gemma-3-1b") == "/model.gguf"
    assert calls == [("unsloth/gemma-3-1b-it-GGUF", "gemma-3-1b-it-Q4_K_M.gguf")]


def test_download_uses_the_chosen_repository(monkeypatch):
    calls = []

    def fake(name, repo_id=None, only_files=()):
        calls.append((name, repo_id, only_files))
        return lambda progress, cancel: True

    monkeypatch.setattr("localdictation.model_helper.make_model_download_func", fake)
    ai_download.make_model_download_func("llama-3.2-1b")
    assert calls == [("ai-cleanup", "unsloth/Llama-3.2-1B-Instruct-GGUF",
                      ("Llama-3.2-1B-Instruct-Q4_K_M.gguf",))]
