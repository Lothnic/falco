"""The text side of streaming dictation: splicing a release's tail onto the
phrases already committed, and when to distrust a seam."""
from localdictation import streaming


def test_splice_drops_the_words_heard_twice():
    joined, lined_up = streaming.splice(
        "I went to the store", "the store and bought milk")
    assert joined == "I went to the store and bought milk"
    assert lined_up


def test_splice_keeps_a_single_misheard_word_at_the_seam():
    # The same speech with and without its right context: one word differs.
    joined, lined_up = streaming.splice(
        "run the test in the container", "the test and the container now passes")
    assert lined_up
    assert joined == "run the test in the container now passes"


def test_splice_without_a_shared_run_says_it_is_untrusted():
    joined, lined_up = streaming.splice("first phrase", "something else entirely")
    assert not lined_up
    assert joined == "first phrase something else entirely"


def test_splice_puts_no_space_before_punctuation():
    joined, lined_up = streaming.splice("he said hello", "hello, then left")
    assert joined == "he said hello, then left"
    assert lined_up


def test_splice_of_an_empty_side_is_the_other():
    assert streaming.splice("", "only tail") == ("only tail", True)
    assert streaming.splice("only head", "") == ("only head", True)


def test_commit_waits_for_enough_speech():
    s = streaming.Streamer()
    assert s.commit_span(0.4) is None
    span = s.commit_span(2.0)
    assert span == (0.0, 2.0)


def test_commit_waits_for_new_speech_not_the_reheard_lead_in():
    """The span re-hears LEAD_KEEP_S before the seam. Counting that toward the
    minimum would commit again the moment the last one finished."""
    s = streaming.Streamer()
    s.accept("the first phrase", 4.0)
    assert s.commit_span(4.0 + streaming.MIN_COMMIT_S / 2) is None
    assert s.commit_span(4.0 + streaming.MIN_COMMIT_S) is not None


def test_commit_span_rehears_a_little_before_the_seam():
    s = streaming.Streamer()
    s.accept("the first phrase", 2.0)
    start, end = s.commit_span(4.0)
    assert end == 4.0
    assert start == 2.0 - streaming.LEAD_KEEP_S


def test_an_empty_commit_leaves_the_seam_alone():
    s = streaming.Streamer()
    s.accept("", 3.0)
    assert s.cut_s == 3.0
    assert s.committed == ""
    assert s.rounds == 0


def test_a_second_phrase_that_does_not_line_up_stops_streaming():
    s = streaming.Streamer()
    s.accept("the first phrase", 2.0)
    assert s.trusted
    s.accept("nothing in common here", 4.0)
    assert not s.trusted
    assert s.commit_span(6.0) is None


def test_the_first_phrase_is_taken_as_it_comes():
    s = streaming.Streamer()
    s.accept("anything at all", 2.0)
    assert s.committed == "anything at all"
    assert s.rounds == 1


def test_release_span_starts_an_overlap_before_the_seam():
    s = streaming.Streamer()
    s.accept("I went to the store", 5.0)
    assert s.release_span(8.0) == (5.0 - streaming.OVERLAP_S, 8.0)


def test_a_short_recording_is_not_streamed_at_release():
    s = streaming.Streamer()
    s.accept("a few words", 2.0)
    assert s.release_span(streaming.MIN_STREAM_S - 1) is None


def test_nothing_left_to_hear_is_not_a_span():
    s = streaming.Streamer()
    s.accept("all of it", 9.0)
    assert s.release_span(9.0) is None


def test_result_splices_the_tail_onto_the_committed_text():
    s = streaming.Streamer()
    s.accept("I went to the store", 5.0)
    result = s.result("the store and bought milk")
    assert result == "I went to the store and bought milk"


def test_result_of_a_silent_tail_is_the_committed_text():
    s = streaming.Streamer()
    s.accept("I went to the store", 5.0)
    assert s.result("") == "I went to the store"


def test_result_refuses_a_tail_that_does_not_line_up():
    s = streaming.Streamer()
    s.accept("I went to the store", 5.0)
    assert s.result("a totally different sentence") is None
