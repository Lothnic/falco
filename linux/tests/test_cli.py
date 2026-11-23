"""`falco` from a terminal: which arguments the CLI answers itself, which go
to the tray, and where a transcript is written.

Nothing here loads a speech model or opens GTK: the engine is stubbed, so the
argument handling and the output routing are what is checked."""
import sys

import pytest

from localdictation import cli, file_transcribe


class _Piece(file_transcribe.Piece):
    pass


def _pieces(*texts):
    return [file_transcribe.Piece(i * 20.0, (i + 1) * 20.0, t)
            for i, t in enumerate(texts)]


@pytest.fixture
def engine(monkeypatch):
    """An engine that answers from a script, so no model is needed."""
    class Engine:
        def __init__(self, answer):
            self.answer = answer
            self.closed = False

        def text(self, audio):
            return self.answer

        def close(self):
            self.closed = True

    made = {}

    def load(_cfg):
        made["engine"] = Engine("the words that were said")
        return made["engine"]

    monkeypatch.setattr(file_transcribe, "load_engine", load)
    monkeypatch.setattr(file_transcribe, "decode", lambda path: [0.0] * 16000)
    monkeypatch.setattr(file_transcribe, "transcribe",
                        lambda audio, eng, progress=None, cancelled=None: _pieces(
                            "the words that were said"))
    return made


def test_transcribe_writes_plain_text_to_stdout(tmp_path, engine, capfd):
    source = tmp_path / "talk.mp3"
    source.write_bytes(b"x")
    assert cli.main(["transcribe", str(source), "--quiet"]) == 0
    out, _err = capfd.readouterr()
    assert out.strip() == "the words that were said"
    assert engine["engine"].closed


def test_transcribe_writes_to_the_named_file(tmp_path, engine, capfd):
    source = tmp_path / "talk.mp3"
    source.write_bytes(b"x")
    target = tmp_path / "out.txt"
    assert cli.main(["transcribe", str(source), "-o", str(target), "--quiet"]) == 0
    assert target.read_text(encoding="utf-8").strip() == "the words that were said"
    # Nothing went to standard output: it is reserved for the transcript.
    out, _err = capfd.readouterr()
    assert out == ""


def test_several_files_with_one_output_are_all_numbered(tmp_path, engine):
    """Numbering every one keeps the naming symmetric: no file is special, and
    none can overwrite another."""
    first = tmp_path / "a.mp3"
    second = tmp_path / "b.mp3"
    first.write_bytes(b"x")
    second.write_bytes(b"x")
    target = tmp_path / "all.txt"
    assert cli.main(["transcribe", str(first), str(second),
                     "-o", str(target), "--quiet"]) == 0
    assert not target.exists()
    assert (tmp_path / "all.1.txt").exists()
    assert (tmp_path / "all.2.txt").exists()


def test_a_missing_file_fails_without_stopping_the_others(tmp_path, engine, capfd):
    good = tmp_path / "good.mp3"
    good.write_bytes(b"x")
    code = cli.main(["transcribe", str(tmp_path / "missing.mp3"), str(good), "--quiet"])
    _out, err = capfd.readouterr()
    assert code == 1                     # one file failed
    assert "no such file" in err
    assert "the words that were said" in _out    # the good one still printed


def test_a_missing_file_is_reported_before_the_model_is_loaded(tmp_path, capfd, monkeypatch):
    """A mistyped name must not cost a speech-model load: reading a model
    takes seconds, and saying the name is wrong does not need it."""
    def must_not_load(_cfg):
        raise AssertionError("the model was loaded for a file that isn't there")

    monkeypatch.setattr(file_transcribe, "load_engine", must_not_load)
    assert cli.main(["transcribe", str(tmp_path / "nope.mp3"), "--quiet"]) == 1
    _out, err = capfd.readouterr()
    assert "no such file" in err


def test_a_file_with_no_sound_is_reported_not_crashed(tmp_path, engine, capfd, monkeypatch):
    source = tmp_path / "silent.mp3"
    source.write_bytes(b"x")

    def no_sound(path):
        raise file_transcribe.NoSound("This file has no sound in it.")

    monkeypatch.setattr(file_transcribe, "decode", no_sound)
    assert cli.main(["transcribe", str(source), "--quiet"]) == 1
    _out, err = capfd.readouterr()
    assert "no sound" in err


def test_an_undownloaded_model_explains_itself(tmp_path, engine, capfd, monkeypatch):
    source = tmp_path / "talk.mp3"
    source.write_bytes(b"x")

    def missing(_cfg):
        raise file_transcribe.NotDownloaded("Parakeet isn't downloaded yet.")

    monkeypatch.setattr(file_transcribe, "load_engine", missing)
    assert cli.main(["transcribe", str(source), "--quiet"]) == 1
    _out, err = capfd.readouterr()
    assert "isn't downloaded" in err
    assert "download a speech model" in err


def test_srt_is_what_asks_for_subtitles(tmp_path, engine, monkeypatch):
    source = tmp_path / "talk.mp3"
    source.write_bytes(b"x")
    asked = {}
    monkeypatch.setattr(file_transcribe, "to_srt",
                        lambda pieces: asked.setdefault("srt", True) and "1\n00:00:00,000 --> ")
    monkeypatch.setattr(file_transcribe, "to_text",
                        lambda pieces, times=False: asked.setdefault("text", True) and "text")
    cli.main(["transcribe", str(source), "--srt", "--quiet"])
    assert asked.get("srt")
    assert "text" not in asked


def test_clean_removes_fillers_before_writing(tmp_path, engine, monkeypatch):
    source = tmp_path / "talk.mp3"
    source.write_bytes(b"x")
    monkeypatch.setattr(file_transcribe, "transcribe",
                        lambda audio, eng, progress=None, cancelled=None: _pieces(
                            "um, the words that were said"))
    assert cli.main(["transcribe", str(source), "--clean", "--quiet"]) == 0
    out = file_transcribe.to_text(file_transcribe.cleaned(_pieces("um, the words that were said")))
    assert "um" not in out.lower()


def test_the_cli_answers_help_without_the_tray(capfd, monkeypatch):
    """`falco help` must not pull in GTK: it is what a broken install reaches
    for to see whether anything works."""
    imported = []
    monkeypatch.setattr(sys, "modules", dict(sys.modules))
    monkeypatch.setitem(sys.modules, "gi", None)   # any GTK import would fail
    monkeypatch.setattr(cli, "_tray_main", lambda argv: imported.append(argv) or 0)
    assert cli.main(["help"]) == 0
    out, _err = capfd.readouterr()
    assert "falco transcribe FILE" in out
    assert imported == []


def test_tray_options_are_handed_to_the_tray(monkeypatch):
    """--toggle and the rest are the running app's; the CLI must not swallow
    them."""
    seen = []
    monkeypatch.setattr(cli, "_tray_main", lambda argv: seen.append(argv) or 0)
    for argv in (["--toggle"], ["--start"], ["--open", "preferences"], ["--quit"]):
        assert cli.main(argv) == 0
    assert seen == [["--toggle"], ["--start"], ["--open", "preferences"], ["--quit"]]


def test_no_arguments_starts_the_app(monkeypatch):
    seen = []
    monkeypatch.setattr(cli, "_tray_main", lambda argv: seen.append(argv) or 0)
    assert cli.main([]) == 0
    assert seen == [[]]
