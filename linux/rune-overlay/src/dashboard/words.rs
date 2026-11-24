use super::*;

#[derive(Clone, Default, Deserialize)]
pub struct Word {
    pub word: String,
    pub phrases: Vec<String>,
}
#[derive(Clone, Default, Deserialize)]
pub struct Snippet {
    pub phrase: String,
    pub text: String,
}
#[derive(Default)]
pub struct Vocabulary {
    pub search: TextEdit,
    pub editing: bool,
    pub snippet: bool,
    pub name: TextEdit,
    pub phrases: TextEdit,
    pub replacement: TextEdit,
    pub old: Option<String>,
}

fn open_word(s: &mut State, word: Option<&Word>) {
    s.vocabulary.editing = true;
    s.vocabulary.snippet = false;
    s.vocabulary.old = word.map(|w| w.word.clone());
    s.vocabulary.name = TextEdit::new(word.map(|w| w.word.clone()).unwrap_or_default());
    s.vocabulary.phrases = TextEdit::new(word.map(|w| w.phrases.join("\n")).unwrap_or_default());
    s.notice.clear();
}
fn open_snippet(s: &mut State, snippet: Option<&Snippet>) {
    s.vocabulary.editing = true;
    s.vocabulary.snippet = true;
    s.vocabulary.old = snippet.map(|w| w.phrase.clone());
    s.vocabulary.name = TextEdit::new(snippet.map(|w| w.phrase.clone()).unwrap_or_default());
    s.vocabulary.replacement = TextEdit::new(snippet.map(|w| w.text.clone()).unwrap_or_default());
    s.notice.clear();
}
fn local_button(
    label: &str,
    key: &str,
    primary: bool,
    handler: impl Fn(&mut State) + 'static,
) -> El {
    row()
        .key(key.to_owned())
        .role("button")
        .label(label.to_owned())
        .focusable(true)
        .min_h(36.0)
        .px(12.0)
        .center()
        .radius(8.0)
        .fill(if primary { accent() } else { rail() })
        .hover(edge())
        .on_press(handler)
        .child(
            text(label.to_owned())
                .font(type_::LABEL)
                .color(if primary { bg() } else { ink() }),
        )
}
fn editor(s: &State) -> El {
    let v = &s.vocabulary;
    let snippet = v.snippet;
    let name = if snippet {
        "Trigger phrase"
    } else {
        "Correct spelling"
    };
    let mut form = col()
        .key("word-editor")
        .w_full()
        .gap(12.0)
        .padding(20.0)
        .radius(12.0)
        .fill(panel())
        .child(title(if v.old.is_some() {
            if snippet { "Edit snippet" } else { "Edit word" }
        } else if snippet {
            "New snippet"
        } else {
            "New word"
        }))
        .child(secondary(name))
        .child(
            text_input(&v.name, type_::BODY)
                .key("word-input")
                .label(name)
                .single_line()
                .w_full()
                .h(40.0)
                .px(12.0)
                .py(10.0)
                .radius(8.0)
                .fill(rail())
                .color(ink())
                .on_edit(|s: &mut State| &mut s.vocabulary.name),
        );
    if snippet {
        form = form.child(secondary("Text to type")).child(
            text_input(&v.replacement, type_::BODY)
                .key("snippet-text")
                .label("Snippet text")
                .w_full()
                .h(110.0)
                .padding(12.0)
                .radius(8.0)
                .fill(rail())
                .color(ink())
                .on_edit(|s: &mut State| &mut s.vocabulary.replacement),
        );
    } else {
        form = form
            .child(secondary(
                "What Falco hears instead (optional, one phrase per line)",
            ))
            .child(
                text_input(&v.phrases, type_::BODY)
                    .key("word-pronunciations")
                    .label("Alternate pronunciations")
                    .w_full()
                    .h(90.0)
                    .padding(12.0)
                    .radius(8.0)
                    .fill(rail())
                    .color(ink())
                    .on_edit(|s: &mut State| &mut s.vocabulary.phrases),
            );
    }
    form.child(row().gap(10.0)
        .child(local_button("Save", "save-word-editor", true, |s| {
            let v = &s.vocabulary;
            let request = if v.snippet {
                json!({"action":"save_snippet", "phrase":v.name.text, "text":v.replacement.text, "old":v.old})
            } else {
                let phrases: Vec<_> = v.phrases.text.lines().map(str::trim).filter(|x| !x.is_empty()).collect();
                json!({"action":"save_word", "word":v.name.text, "phrases":phrases, "old":v.old})
            };
            send_request(request); s.notice = "Saving…".into(); s.notice_error = false;
        }))
        .child(local_button("Cancel", "cancel-word-editor", false, |s| s.vocabulary.editing = false)))
}

pub fn view(s: &State) -> El {
    let mut content = col()
        .w_full()
        .gap(20.0)
        .child(page_header(
            "Your words",
            "Names, pronunciations and shortcuts, all in one place.",
        ))
        .child(
            row()
                .gap(10.0)
                .w_full()
                .center_y()
                .child(
                    text_input(&s.vocabulary.search, type_::BODY)
                        .key("words-search")
                        .label("Search words and snippets")
                        .placeholder("Search your vocabulary…", muted())
                        .single_line()
                        .grow(1.0)
                        .min_w(0.0)
                        .h(40.0)
                        .px(12.0)
                        .py(10.0)
                        .radius(8.0)
                        .fill(panel())
                        .color(ink())
                        .on_edit(|s: &mut State| &mut s.vocabulary.search),
                )
                .child(local_button("Add word", "new-word", true, |s| {
                    open_word(s, None)
                }))
                .child(local_button("New snippet", "new-snippet", false, |s| {
                    open_snippet(s, None)
                })),
        );
    if s.vocabulary.editing {
        content = content.child(editor(s));
    }
    let query = s.vocabulary.search.text.to_lowercase();
    let words: Vec<_> = s
        .snapshot
        .word_rows
        .iter()
        .filter(|w| {
            format!("{} {}", w.word, w.phrases.join(" "))
                .to_lowercase()
                .contains(&query)
        })
        .collect();
    content = content.child(title(format!("Custom words · {}", words.len())));
    if words.is_empty() {
        content = content.child(secondary(if query.is_empty() { "Add a name or technical term. You can teach Falco alternate pronunciations in its editor." } else { "No matching words." }));
    }
    for (index, word) in words.into_iter().enumerate() {
        let edit = word.clone();
        content = content
            .child(
                row()
                    .key(format!("word-row-{index}"))
                    .w_full()
                    .min_h(64.0)
                    .gap(12.0)
                    .center_y()
                    .child(
                        col()
                            .gap(5.0)
                            .grow(1.0)
                            .min_w(0.0)
                            .child(body(word.word.clone()))
                            .child(secondary(if word.phrases.is_empty() {
                                "No alternate pronunciations".into()
                            } else {
                                word.phrases.join(" · ")
                            })),
                    )
                    .child(local_button(
                        "Edit",
                        &format!("edit-word-{index}"),
                        false,
                        move |s| open_word(s, Some(&edit)),
                    ))
                    .child(request_button(
                        s,
                        "Remove",
                        &format!("remove-word-{index}"),
                        json!({"action":"remove_word","word":word.word}),
                        false,
                        Some(format!(
                            "Remove {} and its alternate pronunciations?",
                            word.word
                        )),
                    )),
            )
            .child(rule());
    }
    content = content.child(title("Snippets"));
    let snippets: Vec<_> = s
        .snapshot
        .snippets
        .iter()
        .filter(|w| {
            format!("{} {}", w.phrase, w.text)
                .to_lowercase()
                .contains(&query)
        })
        .collect();
    if snippets.is_empty() {
        content = content.child(secondary(
            "Create a short spoken phrase that types a longer piece of text.",
        ));
    }
    for (index, snippet) in snippets.into_iter().enumerate() {
        let edit = snippet.clone();
        content = content
            .child(
                row()
                    .w_full()
                    .min_h(76.0)
                    .gap(12.0)
                    .center_y()
                    .child(
                        col()
                            .grow(1.0)
                            .min_w(0.0)
                            .gap(5.0)
                            .child(body(snippet.phrase.clone()))
                            .child(secondary(snippet.text.clone())),
                    )
                    .child(local_button(
                        "Edit",
                        &format!("edit-snippet-{index}"),
                        false,
                        move |s| open_snippet(s, Some(&edit)),
                    ))
                    .child(request_button(
                        s,
                        "Remove",
                        &format!("remove-snippet-{index}"),
                        json!({"action":"remove_snippet","phrase":snippet.phrase}),
                        false,
                        Some(format!("Remove the snippet {}?", snippet.phrase)),
                    )),
            )
            .child(rule());
    }
    content = content.child(title("Learned names"));
    content = content.child(secondary(if s.snapshot.learned_words.is_empty() {
        "Names repeatedly corrected by the refiner will appear here when learning is enabled."
            .into()
    } else {
        s.snapshot.learned_words.join(" · ")
    }));
    if !s.snapshot.learned_words.is_empty() {
        content = content.child(request_button(
            s,
            "Clear learned names",
            "clear-learned",
            json!({"action":"clear_learned", "confirmed":true}),
            false,
            Some("Forget learned names? Your custom words and snippets will stay.".into()),
        ));
    }
    content
}
