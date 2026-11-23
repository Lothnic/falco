from localdictation import code_dictation


def test_spoken_filenames_become_paths():
    assert code_dictation.apply("open main dot py") == "open main.py"
    assert code_dictation.apply("edit test underscore utils dot py") == "edit test_utils.py"
    assert code_dictation.apply("open src slash components slash button dot tsx") == \
        "open src/components/button.tsx"


def test_an_unknown_extension_is_left_alone():
    assert code_dictation.apply("the dot product") == "the dot product"
    assert code_dictation.apply("main dot pie") == "main dot pie"


def test_spoken_casing():
    assert code_dictation.apply("camel case get user id") == "getUserId"
    assert code_dictation.apply("snake case get user id") == "get_user_id"
    assert code_dictation.apply("kebab case my component") == "my-component"
    assert code_dictation.apply("pascal case http server") == "HttpServer"
    assert code_dictation.apply("constant case api key") == "API_KEY"


def test_casing_stops_before_the_next_phrase():
    assert code_dictation.apply("camel case get user id and send it") == \
        "getUserId and send it"


def test_symbols_and_backticks():
    assert code_dictation.apply("wrap it in open paren x close paren") == "wrap it in (x)"
    assert code_dictation.apply("use backtick npm run build backtick") == \
        "use `npm run build`"
    assert code_dictation.apply("a fat arrow b") == "a => b"


def test_developer_names_keep_their_spelling():
    assert code_dictation.apply("push it to github") == "push it to GitHub"
    assert code_dictation.apply("we use typescript and node js") == \
        "we use TypeScript and Node.js"
    assert code_dictation.apply("the postgres database") == "the Postgres database"


def test_ordinary_prose_is_not_rewritten():
    text = "I react to that and then go home"
    assert code_dictation.apply(text) == text


def test_prepare_text_applies_code_mode(monkeypatch):
    from localdictation import dictation_text
    from localdictation import live_settings as live
    monkeypatch.setattr(live, "developer_mode", "on")
    monkeypatch.setattr(live, "ai_corrections", False)
    out = dictation_text.prepare_text("open main dot py", True, True, True)
    assert "main.py" in out
    assert not out.endswith(".")


def test_prepare_text_leaves_it_alone_when_off(monkeypatch):
    from localdictation import dictation_text
    from localdictation import live_settings as live
    monkeypatch.setattr(live, "developer_mode", "off")
    monkeypatch.setattr(live, "ai_corrections", False)
    out = dictation_text.prepare_text("open main dot py", True, True, True)
    assert "main dot py" in out
