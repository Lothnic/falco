import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_pairs import build

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
FILLER = re.compile(r"\b(?:um|uh|matlab|yaani|arre)\b", re.IGNORECASE)
CUE = re.compile(r"\b(?:no wait|arre nahi|i mean|sorry|actually)\b", re.IGNORECASE)


def test_build_makes_raw_and_clean_pairs():
    rows = build(300, seed=7)
    assert len(rows) == 300
    assert {row["language"] for row in rows} == {"hi", "en"}
    for row in rows:
        assert row["raw"] and row["clean"]
        assert row["raw"] != row["clean"]
        assert [message["role"] for message in row["messages"]] == [
            "system", "user", "assistant"]
        assert row["messages"][1]["content"] == row["raw"]
        assert row["messages"][2]["content"] == row["clean"]
        assert not FILLER.search(row["clean"])


def test_corruption_covers_scripts_corrections_and_noise():
    rows = build(400, seed=11)
    assert any(DEVANAGARI.search(row["raw"]) for row in rows if row["language"] == "hi")
    assert any(CUE.search(row["raw"]) for row in rows)
    assert any(row["language"] == "en" for row in rows)
    assert not any(DEVANAGARI.search(row["clean"])
                   for row in rows if row["language"] == "en")


def test_same_seed_same_rows():
    first = build(20, seed=3)
    second = build(20, seed=3)
    assert [row["raw"] for row in first] == [row["raw"] for row in second]
