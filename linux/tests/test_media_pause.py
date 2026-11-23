from localdictation import media_pause


class FakeBus:
    def __init__(self, statuses, play_works=True):
        self.statuses = dict(statuses)
        self.play_works = play_works
        self.calls = []

    def players(self):
        return list(self.statuses)

    def playback_status(self, name):
        return self.statuses[name]

    def call(self, name, method):
        self.calls.append((name, method))
        if method == "Pause":
            self.statuses[name] = "Paused"
        elif method == "Play" and self.play_works:
            self.statuses[name] = "Playing"
        elif method == "PlayPause":
            self.statuses[name] = (
                "Paused" if self.statuses[name] == "Playing" else "Playing")


def test_pause_and_resume_touch_only_playing_players():
    bus = FakeBus({"a": "Playing", "b": "Paused", "c": "Stopped"})
    pauser = media_pause.MediaPauser(bus)

    pauser.pause()
    assert pauser.wait_idle(2)
    assert bus.statuses == {"a": "Paused", "b": "Paused", "c": "Stopped"}
    assert bus.calls == [("a", "Pause")]

    pauser.resume()
    assert pauser.wait_idle(2)
    assert bus.statuses["a"] == "Playing"
    assert ("a", "Play") in bus.calls


def test_a_player_that_stays_paused_after_play_is_toggled():
    bus = FakeBus({"a": "Playing"})
    pauser = media_pause.MediaPauser(bus)
    pauser.pause()
    assert pauser.wait_idle(2)

    bus.play_works = False       # accepts Play, but never leaves Paused
    pauser.resume()
    assert pauser.wait_idle(3)
    assert bus.statuses["a"] == "Playing"
    assert ("a", "PlayPause") in bus.calls


def test_resume_can_be_turned_off(monkeypatch):
    monkeypatch.setattr(media_pause.live, "resume_media", False)
    bus = FakeBus({"a": "Playing"})
    pauser = media_pause.MediaPauser(bus)
    pauser.pause()
    assert pauser.wait_idle(2)

    pauser.resume()
    assert pauser.wait_idle(2)
    assert bus.statuses["a"] == "Paused"
    assert ("a", "Play") not in bus.calls


def test_a_player_restarted_meanwhile_is_left_alone():
    bus = FakeBus({"a": "Playing"})
    pauser = media_pause.MediaPauser(bus)
    pauser.pause()
    assert pauser.wait_idle(2)

    bus.statuses["a"] = "Playing"
    pauser.resume()
    assert pauser.wait_idle(2)
    assert ("a", "Play") not in bus.calls
