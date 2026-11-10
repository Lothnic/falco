//! Falco's dashboard. The Python bridge owns all service operations.
use rune::tok::type_;
use rune::{App, AppSpec, Color, Cx, El, ScrollSpec, TextEdit, col, el, row, text, text_input};
use serde::Deserialize;
use serde_json::{Value, json};
use std::io::Write;
use std::process::{Command, Stdio};
use std::sync::{OnceLock, mpsc};
use std::time::Duration;

static COMMANDS: OnceLock<mpsc::Sender<Value>> = OnceLock::new();

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
enum Page {
    #[default]
    Home,
    Recent,
    Words,
    Settings,
}

#[derive(Clone, Default, Deserialize)]
#[serde(default)]
struct Snapshot {
    connected: bool,
    running: bool,
    recording: bool,
    engine: String,
    error: String,
    hotkey: String,
    toggle_hotkey: String,
    microphone: String,
    model: String,
    refiner: bool,
    refiner_installed: bool,
    auto_space: bool,
    auto_period: bool,
    words: Vec<String>,
    recent: Vec<String>,
}

#[derive(Default)]
struct State {
    page: Page,
    snapshot: Snapshot,
    loaded: bool,
    notice: String,
    word_input: TextEdit,
    edit_input: TextEdit,
    editing: bool,
}

fn color(r: f32, g: f32, b: f32) -> Color {
    Color { r, g, b, a: 1.0 }
}
fn bg() -> Color {
    color(0.055, 0.075, 0.09)
}
fn rail() -> Color {
    color(0.075, 0.10, 0.12)
}
fn panel() -> Color {
    color(0.105, 0.14, 0.16)
}
fn edge() -> Color {
    color(0.19, 0.24, 0.26)
}
fn ink() -> Color {
    color(0.91, 0.95, 0.94)
}
fn muted() -> Color {
    color(0.59, 0.69, 0.69)
}
fn accent() -> Color {
    color(0.43, 0.83, 0.71)
}
fn muted_accent() -> Color {
    color(0.14, 0.24, 0.23)
}

fn send(action: &str) {
    if let Some(tx) = COMMANDS.get() {
        let _ = tx.send(json!({"action": action}));
    }
}
fn send_copy(value: String) {
    if let Some(tx) = COMMANDS.get() {
        let _ = tx.send(json!({"action":"copy", "text":value}));
    }
}
fn send_request(value: Value) {
    if let Some(tx) = COMMANDS.get() {
        let _ = tx.send(value);
    }
}
fn add_word(s: &mut State) {
    let word = s.word_input.text.trim().to_string();
    if word.is_empty() {
        s.notice = "Enter a word or short name.".into();
        return;
    }
    send_request(json!({"action":"add_word", "word":word}));
    s.notice = "Saving word…".into();
}

fn title(value: impl Into<String>) -> El {
    text(value.into()).font(type_::TITLE).color(ink())
}
fn body(value: impl Into<String>) -> El {
    text(value.into()).font(type_::BODY).color(ink()).wrap()
}
fn secondary(value: impl Into<String>) -> El {
    text(value.into()).font(type_::LABEL).color(muted()).wrap()
}
fn heading(value: impl Into<String>) -> El {
    text(value.into())
        .font(rune::TextStyle::new(25.0, 650.0))
        .color(ink())
}
fn button(label: &'static str, action: &'static str, primary: bool) -> El {
    row()
        .key(format!("action-{action}"))
        .role("button")
        .label(label)
        .focusable(true)
        .h(38.0)
        .px(14.0)
        .center()
        .radius(8.0)
        .fill(if primary { accent() } else { rail() })
        .hover(if primary {
            color(0.56, 0.90, 0.79)
        } else {
            edge()
        })
        .on_press(move |s: &mut State| {
            s.notice.clear();
            send(action);
        })
        .child(
            text(label)
                .font(type_::LABEL)
                .color(if primary { bg() } else { ink() }),
        )
}
fn nav(label: &'static str, page: Page, current: Page) -> El {
    row()
        .key(format!("nav-{page:?}"))
        .role("button")
        .label(label)
        .focusable(true)
        .w_full()
        .h(40.0)
        .px(13.0)
        .center_y()
        .radius(8.0)
        .fill(if page == current {
            muted_accent()
        } else {
            rail()
        })
        .hover(color(0.15, 0.22, 0.23))
        .on_press(move |s: &mut State| {
            s.page = page;
            s.notice.clear();
        })
        .child(
            text(label)
                .font(type_::BODY)
                .color(if page == current { accent() } else { ink() }),
        )
}
fn rule() -> El {
    el().w_full().h(1.0).fill(edge())
}
fn info_row(label: &str, value: &str) -> El {
    row()
        .w_full()
        .min_h(40.0)
        .center_y()
        .gap(20.0)
        .child(secondary(label.to_owned()).w(160.0))
        .child(body(value.to_owned()).grow(1.0))
}
fn recent_row(value: &str, index: usize, preview: bool) -> El {
    let copy = value.to_owned();
    let edit = copy.clone();
    let value = if preview && value.chars().count() > 200 {
        format!("{}…", value.chars().take(200).collect::<String>())
    } else {
        value.to_owned()
    };
    row()
        .key(format!("recent-{index}"))
        .w_full()
        .py(13.0)
        .gap(16.0)
        .center_y()
        .child(body(value).grow(1.0).min_w(0.0))
        .child(
            row()
                .key(format!("edit-{index}"))
                .role("button")
                .label("Edit dictation")
                .focusable(true)
                .h(32.0)
                .px(12.0)
                .center()
                .radius(7.0)
                .fill(rail())
                .hover(edge())
                .on_press(move |s: &mut State| {
                    s.edit_input = TextEdit::new(edit.clone());
                    s.editing = true;
                    s.page = Page::Recent;
                })
                .child(text("Edit").font(type_::LABEL).color(ink())),
        )
        .child(
            row()
                .key(format!("copy-{index}"))
                .role("button")
                .label("Copy dictation")
                .focusable(true)
                .h(32.0)
                .px(12.0)
                .center()
                .radius(7.0)
                .fill(rail())
                .hover(edge())
                .on_press(move |s: &mut State| {
                    send_copy(copy.clone());
                    s.notice = "Copying…".into();
                })
                .child(text("Copy").font(type_::LABEL).color(ink())),
        )
}
fn status(snapshot: &Snapshot, loaded: bool) -> (&'static str, &'static str, Color) {
    if !loaded {
        ("Connecting", "Checking the local service", muted())
    } else if !snapshot.connected {
        (
            "Unavailable",
            "Open Falco to start the service",
            color(0.95, 0.66, 0.46),
        )
    } else if snapshot.recording {
        ("Listening", "Your microphone is active", accent())
    } else if snapshot.running {
        ("Running", "Use your shortcut to dictate", accent())
    } else {
        ("Stopped", "Start the service to use dictation", muted())
    }
}
fn card() -> El {
    col()
        .w_full()
        .padding(20.0)
        .gap(12.0)
        .radius(12.0)
        .fill(panel())
}
fn page_header(title_text: &str, detail: &str) -> El {
    col()
        .gap(6.0)
        .child(heading(title_text.to_owned()))
        .child(secondary(detail.to_owned()))
}
fn recent_list(snapshot: &Snapshot, limit: usize) -> El {
    let mut list = col().w_full();
    if snapshot.recent.is_empty() {
        return list.child(secondary("Dictations from this session will appear here."));
    }
    for (i, value) in snapshot.recent.iter().take(limit).enumerate() {
        if i > 0 {
            list = list.child(rule());
        }
        list = list.child(recent_row(value, i, limit == 3));
    }
    list
}
fn home(s: &State) -> El {
    let (state, hint, tone) = status(&s.snapshot, s.loaded);
    let mut status_card = card().gap(16.0).child(
        row()
            .w_full()
            .center_y()
            .gap(11.0)
            .child(el().size(9.0, 9.0).radius(4.5).fill(tone))
            .child(
                col()
                    .grow(1.0)
                    .gap(4.0)
                    .child(title(state))
                    .child(secondary(hint)),
            ),
    );
    status_card = status_card.child(rule()).child(
        row()
            .w_full()
            .gap(20.0)
            .child(
                col()
                    .grow(1.0)
                    .gap(5.0)
                    .child(secondary("HOLD TO TALK"))
                    .child(body(s.snapshot.hotkey.clone())),
            )
            .child(
                col()
                    .grow(1.0)
                    .gap(5.0)
                    .child(secondary("TOGGLE RECORDING"))
                    .child(body(s.snapshot.toggle_hotkey.clone())),
            )
            .child(
                col()
                    .grow(1.0)
                    .gap(5.0)
                    .child(secondary("MICROPHONE"))
                    .child(body(s.snapshot.microphone.clone())),
            ),
    );
    if s.snapshot.connected {
        status_card = status_card.child(row().child(if s.snapshot.running {
            button("Stop service", "stop_service", false)
        } else {
            button("Start service", "start_service", true)
        }));
    }
    col()
        .gap(22.0)
        .w_full()
        .child(page_header(
            "Your voice, ready when you are",
            "Dictation runs locally on this device.",
        ))
        .child(status_card)
        .child(
            row()
                .w_full()
                .center_y()
                .child(title("Recent dictations").grow(1.0))
                .child(
                    row()
                        .role("button")
                        .label("View recent dictations")
                        .focusable(true)
                        .on_press(|s: &mut State| s.page = Page::Recent)
                        .child(text("View all").font(type_::LABEL).color(accent())),
                ),
        )
        .child(card().child(recent_list(&s.snapshot, 3)))
        .child(secondary(
            "Recent dictations stay in this session and are cleared at logout.",
        ))
}
fn recent(s: &State) -> El {
    let mut contents = col().gap(22.0).w_full().child(page_header(
        "Recent dictations",
        "Copy text from this session if you need it again.",
    ));
    if s.editing {
        let editor = text_input(&s.edit_input, type_::BODY)
            .key("dictation-editor")
            .label("Edit dictation")
            .w_full()
            .min_h(110.0)
            .padding(12.0)
            .radius(8.0)
            .fill(rail())
            .color(ink())
            .on_edit(|s: &mut State| &mut s.edit_input);
        let copy = row()
            .key("copy-edited")
            .role("button")
            .label("Copy edited text")
            .focusable(true)
            .h(38.0)
            .px(14.0)
            .center()
            .radius(8.0)
            .fill(accent())
            .hover(color(0.56, 0.90, 0.79))
            .on_press(|s: &mut State| {
                send_copy(s.edit_input.text.clone());
                s.notice = "Copying…".into();
            })
            .child(text("Copy edited text").font(type_::LABEL).color(bg()));
        let close = row()
            .key("close-editor")
            .role("button")
            .label("Close editor")
            .focusable(true)
            .h(38.0)
            .px(14.0)
            .center()
            .radius(8.0)
            .fill(rail())
            .hover(edge())
            .on_press(|s: &mut State| {
                s.editing = false;
            })
            .child(text("Close").font(type_::LABEL).color(ink()));
        contents = contents.child(
            card()
                .child(title("Edit a copy"))
                .child(secondary(
                    "Changes here do not change the original dictation.",
                ))
                .child(editor)
                .child(row().gap(10.0).child(copy).child(close)),
        );
    }
    contents
        .child(card().child(recent_list(&s.snapshot, 20)))
        .child(secondary(
            "Saved in the session's temporary storage and cleared at logout.",
        ))
}

fn words(s: &State) -> El {
    let mut entries = col().w_full().gap(0.0);
    if s.snapshot.words.is_empty() {
        entries = entries.child(secondary(
            "No custom words yet. Add names or technical terms you use often.",
        ));
    } else {
        for (i, word) in s.snapshot.words.iter().take(100).enumerate() {
            if i > 0 {
                entries = entries.child(rule());
            }
            entries = entries.child(row().w_full().py(11.0).child(body(word.clone())));
        }
    }
    col()
        .gap(22.0)
        .w_full()
        .child(page_header(
            "Your words",
            "Give dictation the names and terms you use.",
        ))
        .child(
            row()
                .gap(10.0)
                .center_y()
                .child(
                    text_input(&s.word_input, type_::BODY)
                        .key("word-input")
                        .label("New word")
                        .placeholder("Add a name or term", muted())
                        .single_line()
                        .grow(1.0)
                        .h(40.0)
                        .px(12.0)
                        .radius(8.0)
                        .fill(panel())
                        .color(ink())
                        .on_edit(|s: &mut State| &mut s.word_input)
                        .on_submit(|s: &mut State, _| add_word(s)),
                )
                .child(
                    row()
                        .key("add-word")
                        .role("button")
                        .label("Add word")
                        .focusable(true)
                        .h(40.0)
                        .px(16.0)
                        .center()
                        .radius(8.0)
                        .fill(accent())
                        .hover(color(0.56, 0.90, 0.79))
                        .on_press(add_word)
                        .child(text("Add word").font(type_::LABEL).color(bg())),
                ),
        )
        .child(row().child(button("Manage pronunciations", "words", false)))
        .child(card().child(entries))
}
fn setting_toggle(label: &'static str, name: &'static str, enabled: bool) -> El {
    row()
        .w_full()
        .min_h(42.0)
        .center_y()
        .gap(12.0)
        .child(body(label).grow(1.0))
        .child(
            row()
                .key(format!("option-{name}"))
                .role("switch")
                .label(label)
                .checked(enabled)
                .focusable(true)
                .h(32.0)
                .px(12.0)
                .center()
                .radius(8.0)
                .fill(if enabled { muted_accent() } else { rail() })
                .hover(edge())
                .on_press(move |s: &mut State| {
                    send_request(json!({"action":"set_option", "name":name, "value":!enabled}));
                    s.notice = "Saving…".into();
                })
                .child(
                    text(if enabled { "On" } else { "Off" })
                        .font(type_::LABEL)
                        .color(if enabled { accent() } else { ink() }),
                ),
        )
}

fn settings(s: &State) -> El {
    let refiner = if !s.snapshot.refiner {
        "Off"
    } else if s.snapshot.refiner_installed {
        "Enabled · downloaded"
    } else {
        "Enabled · download required"
    };
    col()
        .gap(22.0)
        .w_full()
        .child(page_header("Settings", "Your current dictation setup."))
        .child(
            card()
                .child(title("Input & shortcuts"))
                .child(info_row("Microphone", &s.snapshot.microphone))
                .child(rule())
                .child(info_row("Hold to talk", &s.snapshot.hotkey))
                .child(rule())
                .child(info_row("Toggle recording", &s.snapshot.toggle_hotkey)),
        )
        .child(
            card()
                .child(title("Local models"))
                .child(info_row(
                    "Speech recognition",
                    if s.snapshot.engine.is_empty() {
                        &s.snapshot.model
                    } else {
                        &s.snapshot.engine
                    },
                ))
                .child(rule())
                .child(info_row("Phonon refiner", refiner)),
        )
        .child(
            card()
                .child(title("Text formatting"))
                .child(setting_toggle(
                    "Add space after dictation",
                    "auto_space",
                    s.snapshot.auto_space,
                ))
                .child(rule())
                .child(setting_toggle(
                    "Add punctuation",
                    "auto_period",
                    s.snapshot.auto_period,
                )),
        )
        .child(row().child(button("Open all settings", "settings", false)))
        .child(secondary("Changes open in the existing settings window."))
}
fn view(s: &State, _: &mut Cx<State>) -> El {
    let contents = match s.page {
        Page::Home => home(s),
        Page::Recent => recent(s),
        Page::Words => words(s),
        Page::Settings => settings(s),
    };
    let mut content = col().w_full().gap(18.0);
    if !s.notice.is_empty() {
        content = content.child(secondary(s.notice.clone()));
    }
    if s.loaded && !s.snapshot.error.is_empty() {
        content = content.child(secondary(s.snapshot.error.clone()));
    }
    content = content.child(contents);
    row()
        .key("window")
        .role("window")
        .w_full()
        .h_full()
        .fill(bg())
        .child(
            col()
                .key("sidebar")
                .w(206.0)
                .h_full()
                .padding(18.0)
                .gap(6.0)
                .fill(rail())
                .child(
                    row()
                        .h(64.0)
                        .center_y()
                        .gap(10.0)
                        .child(el().size(11.0, 11.0).radius(5.5).fill(accent()))
                        .child(
                            col()
                                .gap(3.0)
                                .child(title("Falco"))
                                .child(secondary("Voice typing")),
                        ),
                )
                .child(nav("Overview", Page::Home, s.page))
                .child(nav("Recent", Page::Recent, s.page))
                .child(nav("Your words", Page::Words, s.page))
                .child(nav("Settings", Page::Settings, s.page))
                .child(el().grow(1.0))
                .child(secondary("LOCAL BY DESIGN")),
        )
        .child(
            col()
                .key("content-area")
                .grow(1.0)
                .h_full()
                .min_w(0.0)
                .padding(30.0)
                .child(
                    content
                        .scroll(ScrollSpec {
                            stick_bottom: false,
                        })
                        .grow(1.0)
                        .min_h(0.0),
                ),
        )
}
fn bridge(request: &Value) -> Result<Value, String> {
    let python = std::env::var("PHONON_PYTHON").unwrap_or_else(|_| "python3".into());
    let module =
        std::env::var("PHONON_BRIDGE_MODULE").unwrap_or_else(|_| "localdictation.ui_bridge".into());
    let mut child = Command::new(python)
        .args(["-m", &module])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "Couldn't start the local service bridge.".to_string())?;
    let mut stdin = child
        .stdin
        .take()
        .ok_or("Couldn't open the local service bridge.")?;
    serde_json::to_writer(&mut stdin, request).map_err(|_| "Couldn't send the request.")?;
    stdin.flush().map_err(|_| "Couldn't send the request.")?;
    drop(stdin);
    let output = child
        .wait_with_output()
        .map_err(|_| "The local service bridge stopped.")?;
    if !output.status.success() {
        return Err("The local service bridge stopped.".into());
    }
    serde_json::from_slice(&output.stdout)
        .map_err(|_| "The local service returned an invalid response.".into())
}
fn preview(s: &mut State) {
    s.loaded = true;
    s.snapshot.connected = true;
    s.snapshot.running = true;
    s.snapshot.hotkey = "F8".into();
    s.snapshot.toggle_hotkey = "F9".into();
    s.snapshot.microphone = "System default".into();
    s.snapshot.model = "Parakeet".into();
    s.snapshot.refiner = true;
    s.snapshot.refiner_installed = true;
    s.snapshot.auto_space = true;
    s.snapshot.auto_period = true;
    s.snapshot.words = vec!["Parakeet".into(), "Phonon".into()];
    s.snapshot.recent = vec!["A sample dictation for preview.".into()];
}
fn main() {
    let spec = AppSpec {
        scenes: &[
            ("preview", preview),
            ("recent", |s: &mut State| {
                preview(s);
                s.page = Page::Recent;
            }),
            ("words", |s: &mut State| {
                preview(s);
                s.page = Page::Words;
            }),
            ("settings", |s: &mut State| {
                preview(s);
                s.page = Page::Settings;
            }),
        ],
        ..AppSpec::new("Falco", (1000.0, 700.0), State::default, view)
    };
    if std::env::args().any(|a| matches!(a.as_str(), "--snap" | "--tree" | "--list-scenes")) {
        rune::run(spec);
        return;
    }
    let app = App::new(spec);
    let handle = app.handle();
    let (tx, rx) = mpsc::channel();
    let _ = COMMANDS.set(tx);
    std::thread::spawn(move || {
        let mut first = true;
        loop {
            let next = if first {
                first = false;
                None
            } else {
                rx.recv_timeout(Duration::from_secs(2)).ok()
            };
            if let Some(command) = next {
                let submitted_word = command
                    .get("word")
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .to_string();
                let action = command
                    .get("action")
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .to_string();
                let result = bridge(&command);
                handle.update(move |s: &mut State, _| {
                    s.notice = match result {
                        Ok(ref value) if value.get("ok").and_then(Value::as_bool) == Some(true) => {
                            if action == "copy" {
                                "Copied to clipboard.".into()
                            } else if action == "add_word" {
                                if s.word_input.text.trim() == submitted_word {
                                    s.word_input.clear();
                                }
                                "Word added.".into()
                            } else if action == "set_option" {
                                "Setting saved.".into()
                            } else {
                                String::new()
                            }
                        }
                        Ok(value) => value
                            .get("error")
                            .and_then(Value::as_str)
                            .unwrap_or("The action failed.")
                            .to_string(),
                        Err(error) => error,
                    };
                });
            }
            match bridge(&json!({"action":"snapshot"})) {
                Ok(value) => match serde_json::from_value::<Snapshot>(value) {
                    Ok(snapshot) => handle.update(move |s: &mut State, _| {
                        s.snapshot = snapshot;
                        s.loaded = true;
                    }),
                    Err(_) => handle.update(|s: &mut State, _| {
                        s.loaded = true;
                        s.snapshot.connected = false;
                        s.snapshot.error = "Couldn't read local service status.".into();
                    }),
                },
                Err(error) => handle.update(move |s: &mut State, _| {
                    s.loaded = true;
                    s.snapshot.connected = false;
                    s.snapshot.error = error;
                }),
            }
        }
    });
    app.run();
}

#[cfg(test)]
mod tests {
    use super::*;
    use rune::{Env, Runtime};

    fn click(rt: &mut Runtime<State>, key: &str) {
        let (x, y) = rt.find(key).expect("control should exist");
        rt.pointer_down(x, y);
        rt.pointer_up(x, y);
        for _ in 0..30 {
            rt.frame(1.0 / 60.0);
        }
    }

    #[test]
    fn navigation_and_editing_use_the_selected_dictation() {
        let mut state = State::default();
        preview(&mut state);
        let mut rt = Runtime::new(state, view, (1000.0, 700.0), Env::new(true, 1.0));
        rt.frame(0.0);
        click(&mut rt, "nav-Recent");
        assert_eq!(rt.state.page, Page::Recent);
        click(&mut rt, "edit-0");
        assert!(rt.state.editing);
        assert_eq!(rt.state.edit_input.text, "A sample dictation for preview.");
        assert!(rt.find("dictation-editor").is_some());
        click(&mut rt, "nav-Words");
        assert_eq!(rt.state.page, Page::Words);
        assert!(rt.find("word-input").is_some());
    }

    #[test]
    fn unavailable_service_is_never_claimed_as_running() {
        let snapshot = Snapshot {
            connected: false,
            running: true,
            ..Snapshot::default()
        };
        assert_eq!(status(&snapshot, true).0, "Unavailable");
        assert_eq!(status(&snapshot, false).0, "Connecting");
    }
}
