//! Falco's dashboard. The Python bridge owns all service operations.
use rune::tok::type_;
use rune::{App, AppSpec, Color, Cx, El, ScrollSpec, TextEdit, col, el, row, text, text_input};
use serde::Deserialize;
use serde_json::{Value, json};
use std::io::Write;
#[path = "../dashboard/ipc.rs"]
mod dashboard_ipc;
#[path = "../dashboard/pages.rs"]
mod pages_ui;
#[path = "../dashboard/settings.rs"]
mod settings_ui;
#[path = "../dashboard/words.rs"]
mod words_ui;
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
    Stats,
    Updates,
    Help,
    Commands,
}

#[derive(Clone, Default, Deserialize)]
#[serde(default)]
struct Snapshot {
    version: String,
    settings: Vec<settings_ui::Field>,
    job: settings_ui::Job,
    word_rows: Vec<words_ui::Word>,
    snippets: Vec<words_ui::Snippet>,
    learned_words: Vec<String>,
    stats_rows: Vec<settings_ui::StatRow>,
    restore_points: Vec<pages_ui::RestorePoint>,
    commands: Vec<pages_ui::VoiceCommand>,
    system_rows: Vec<settings_ui::StatRow>,
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
    notice_error: bool,
    dismissed_job: String,
    confirmation: Option<(String, Value)>,
    preferences: settings_ui::Preferences,
    vocabulary: words_ui::Vocabulary,
    word_input: TextEdit,
    recent_query: TextEdit,
    commands_query: TextEdit,
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
fn initial_state() -> State {
    let mut state = State::default();
    dashboard_ipc::route(&mut state, &dashboard_ipc::requested_route());
    state
}
fn request_button(
    s: &State,
    label: &str,
    key: &str,
    request: Value,
    primary: bool,
    confirmation: Option<String>,
) -> El {
    let busy = s.snapshot.job.busy || s.preferences.saving;
    let mut button = row()
        .key(key.to_owned())
        .role("button")
        .label(label.to_owned())
        .min_h(38.0)
        .px(14.0)
        .center()
        .radius(8.0)
        .fill(if primary && !busy { accent() } else { rail() })
        .child(text(label.to_owned()).font(type_::LABEL).color(if busy {
            muted()
        } else if primary {
            bg()
        } else {
            ink()
        }));
    if !busy {
        button = button
            .focusable(true)
            .hover(edge())
            .on_press(move |s: &mut State| {
                s.notice.clear();
                s.notice_error = false;
                if let Some(message) = &confirmation {
                    s.confirmation = Some((message.clone(), request.clone()));
                } else {
                    send_request(request.clone());
                }
            });
    }
    button
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
            match action {
                "settings" => s.page = Page::Settings,
                "words" => s.page = Page::Words,
                _ => send(action),
            }
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
fn recent_list(snapshot: &Snapshot, limit: usize, query: &str) -> El {
    let mut list = col().w_full();
    let query = query.trim().to_lowercase();
    let matches = snapshot
        .recent
        .iter()
        .enumerate()
        .filter(|(_, value)| query.is_empty() || value.to_lowercase().contains(&query))
        .take(limit);
    let mut empty = true;
    for (index, value) in matches {
        if !empty {
            list = list.child(rule());
        }
        empty = false;
        list = list.child(recent_row(value, index, limit == 3));
    }
    if empty {
        list = list.child(secondary(if snapshot.recent.is_empty() {
            "Dictations from this session will appear here."
        } else {
            "No dictations match your search."
        }));
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
        .child(card().child(recent_list(&s.snapshot, 3, "")))
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
        .child(
            text_input(&s.recent_query, type_::BODY)
                .key("recent-search")
                .label("Search recent dictations")
                .placeholder("Search recent dictations", muted())
                .single_line()
                .w_full()
                .h(40.0)
                .px(12.0)
                .py(9.0)
                .radius(8.0)
                .fill(panel())
                .color(ink())
                .on_edit(|s: &mut State| &mut s.recent_query),
        )
        .child(card().child(recent_list(&s.snapshot, 20, &s.recent_query.text)))
        .child(secondary(
            "Saved in the session's temporary storage and cleared at logout.",
        ))
}

fn view(s: &State, _: &mut Cx<State>) -> El {
    let mut layer = Vec::new();
    let contents = match s.page {
        Page::Home => home(s),
        Page::Recent => recent(s),
        Page::Words => words_ui::view(s),
        Page::Settings => settings_ui::view(s, &mut layer),
        Page::Stats => pages_ui::stats(s, &mut layer),
        Page::Updates => pages_ui::updates(s, &mut layer),
        Page::Help => pages_ui::help(s),
        Page::Commands => pages_ui::commands(s),
    };
    let mut content = col().w_full().gap(18.0);
    if !s.notice.is_empty() {
        content = content.child(text(s.notice.clone()).font(type_::BODY).wrap().color(
            if s.notice_error {
                color(1.0, 0.66, 0.61)
            } else {
                accent()
            },
        ));
    }
    if s.loaded && !s.snapshot.error.is_empty() {
        content = content.child(secondary(s.snapshot.error.clone()));
    }
    if let Some((message, request)) = &s.confirmation {
        let request = request.clone();
        content = content.child(
            col()
                .key("confirmation")
                .w_full()
                .gap(12.0)
                .padding(18.0)
                .fill(panel())
                .radius(12.0)
                .child(body(message.clone()))
                .child(
                    row()
                        .gap(12.0)
                        .child(
                            row()
                                .key("confirm-action")
                                .role("button")
                                .label("Confirm action")
                                .focusable(true)
                                .h(36.0)
                                .px(14.0)
                                .center()
                                .radius(8.0)
                                .fill(accent())
                                .on_press(move |s: &mut State| {
                                    send_request(request.clone());
                                    s.confirmation = None;
                                })
                                .child(text("Confirm").font(type_::LABEL).color(bg())),
                        )
                        .child(
                            row()
                                .key("cancel-action")
                                .role("button")
                                .label("Cancel action")
                                .focusable(true)
                                .h(36.0)
                                .px(14.0)
                                .center()
                                .radius(8.0)
                                .fill(rail())
                                .on_press(|s: &mut State| s.confirmation = None)
                                .child(body("Cancel")),
                        ),
                ),
        );
    }
    if !s.snapshot.job.message.is_empty() && s.dismissed_job != s.snapshot.job.id {
        let job = &s.snapshot.job;
        let message = job
            .result
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or(&job.message);
        let mut progress = col()
            .key("operation-status")
            .w_full()
            .gap(10.0)
            .padding(16.0)
            .radius(12.0)
            .fill(panel())
            .child(
                text(message.to_owned())
                    .font(type_::BODY)
                    .wrap()
                    .color(if job.failed {
                        color(1.0, 0.66, 0.61)
                    } else {
                        ink()
                    }),
            );
        if job.busy {
            progress = progress.child(
                row()
                    .w_full()
                    .gap(16.0)
                    .center_y()
                    .child(secondary(format!("{}%", job.progress)).grow(1.0))
                    .child(if job.cancellable {
                        row()
                            .role("button")
                            .label("Cancel operation")
                            .focusable(true)
                            .h(30.0)
                            .px(10.0)
                            .radius(6.0)
                            .fill(rail())
                            .on_press(|_: &mut State| send("cancel_job"))
                            .child(secondary("Cancel"))
                    } else {
                        el()
                    }),
            );
        }
        if !job.busy {
            let id = job.id.clone();
            progress = progress.child(
                row()
                    .key("dismiss-operation")
                    .role("button")
                    .label("Dismiss status")
                    .focusable(true)
                    .min_h(30.0)
                    .px(10.0)
                    .radius(6.0)
                    .fill(rail())
                    .on_press(move |s: &mut State| {
                        s.dismissed_job = id.clone();
                        s.notice.clear();
                    })
                    .child(secondary("Dismiss")),
            );
        }
        content = content.child(progress);
    }
    let has_banner = !s.notice.is_empty()
        || (s.loaded && !s.snapshot.error.is_empty())
        || s.confirmation.is_some()
        || (!s.snapshot.job.message.is_empty() && s.dismissed_job != s.snapshot.job.id);
    let base =
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
                            .child(col().gap(3.0).child(title("Falco")).child(secondary(
                                &format!(
                                    "v{} · Command Mode",
                                    if s.snapshot.version.is_empty() {
                                        env!("CARGO_PKG_VERSION")
                                    } else {
                                        &s.snapshot.version
                                    }
                                ),
                            ))),
                    )
                    .child(nav("Overview", Page::Home, s.page))
                    .child(nav("Recent", Page::Recent, s.page))
                    .child(nav("Your words", Page::Words, s.page))
                    .child(nav("Settings", Page::Settings, s.page))
                    .child(nav("Usage", Page::Stats, s.page))
                    .child(nav("Updates & backup", Page::Updates, s.page))
                    .child(nav("Voice commands", Page::Commands, s.page))
                    .child(nav("Help", Page::Help, s.page))
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
                    .child(if has_banner { content.pb(18.0) } else { el() })
                    .child(
                        contents
                            .scroll(ScrollSpec {
                                stick_bottom: false,
                            })
                            .grow(1.0)
                            .min_h(0.0),
                    )
                    .child(
                        if matches!(s.page, Page::Settings | Page::Stats | Page::Updates)
                            || !s.preferences.dirty.is_empty()
                        {
                            settings_ui::save_bar(s)
                        } else {
                            el()
                        },
                    ),
            );
    rune_kit::root(base, layer)
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
    s.snapshot.settings =
        serde_json::from_str(include_str!("../../fixtures/settings.json")).unwrap();
    s.snapshot.word_rows = vec![
        words_ui::Word {
            word: "Parakeet".into(),
            phrases: vec!["para keet".into()],
        },
        words_ui::Word {
            word: "Phonon".into(),
            phrases: vec![],
        },
    ];
    let snapshot = s.snapshot.clone();
    settings_ui::sync(s, &snapshot);
    s.snapshot.words = vec!["Parakeet".into(), "Phonon".into()];
    s.snapshot.recent = vec!["A sample dictation for preview.".into()];
}
fn main() {
    if std::env::args().any(|a| a == "--version") {
        println!("{}", env!("CARGO_PKG_VERSION"));
        return;
    }
    let spec = AppSpec {
        min_size: Some((860.0, 600.0)),
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
            ("command", |s: &mut State| {
                preview(s);
                s.page = Page::Settings;
                s.preferences.search = TextEdit::new("Command Mode");
            }),
            ("refiner", |s: &mut State| {
                preview(s);
                s.page = Page::Settings;
                s.preferences.section = "refiner".into();
            }),
            ("select", |s: &mut State| {
                preview(s);
                s.page = Page::Settings;
                s.preferences.open = Some("hotkey".into());
            }),
            ("editor", |s: &mut State| {
                preview(s);
                s.page = Page::Words;
                s.vocabulary.editing = true;
                s.vocabulary.name = TextEdit::new("DeepSeek");
            }),
            ("updates", |s: &mut State| {
                preview(s);
                s.page = Page::Updates;
            }),
            ("usage", |s: &mut State| {
                preview(s);
                s.page = Page::Stats;
            }),
            ("help", |s: &mut State| {
                preview(s);
                s.page = Page::Help;
            }),
            ("busy", |s: &mut State| {
                preview(s);
                s.page = Page::Settings;
                s.snapshot.job.busy = true;
                s.snapshot.job.message = "Downloading the selected model…".into();
                s.snapshot.job.progress = 42;
            }),
            ("error", |s: &mut State| {
                preview(s);
                s.page = Page::Words;
                s.vocabulary.editing = true;
                s.notice_error = true;
                s.notice="A pronunciation is already assigned. Edit its existing word first. Your changes are still here.".into();
            }),
        ],
        ..AppSpec::new("Falco", (1100.0, 780.0), initial_state, view)
    };
    if std::env::args().any(|a| matches!(a.as_str(), "--snap" | "--tree" | "--list-scenes")) {
        rune::run(spec);
        return;
    }
    let Some(instance) = dashboard_ipc::claim() else {
        return;
    };
    let app = App::new(spec)
        .tab_visits_controls(true)
        .keep_running()
        .on_close(|s, tx| {
            if s.preferences.dirty.is_empty() && !s.vocabulary.editing {
                tx.quit();
            } else {
                s.notice = "Your unsaved changes were kept while the window was closed.".into();
                s.notice_error = false;
            }
        });
    let handle = app.handle();
    dashboard_ipc::listen(&instance, handle.clone());
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
                            s.notice_error = false;
                            if action == "save_word" || action == "save_snippet" {
                                s.vocabulary.editing = false;
                            }
                            if action == "save_settings" {
                                s.preferences.job_id = value
                                    .get("job_id")
                                    .and_then(Value::as_str)
                                    .unwrap_or("")
                                    .into();
                            }
                            if let Some(message) = value.get("message").and_then(Value::as_str) {
                                message.into()
                            } else if action == "copy" {
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
                        Ok(value) => {
                            s.notice_error = true;
                            s.preferences.saving = false;
                            value
                                .get("error")
                                .and_then(Value::as_str)
                                .unwrap_or("The action failed.")
                                .to_string()
                        }
                        Err(error) => {
                            s.notice_error = true;
                            s.preferences.saving = false;
                            error
                        }
                    };
                });
            }
            match bridge(&json!({"action":"snapshot"})) {
                Ok(value) => match serde_json::from_value::<Snapshot>(value) {
                    Ok(snapshot) => handle.update(move |s: &mut State, _| {
                        settings_ui::sync(s, &snapshot);
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
        click(&mut rt, "new-word");
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

    #[test]
    fn recent_search_matches_case_insensitively_and_edits_the_original_row() {
        let mut state = State {
            page: Page::Recent,
            recent_query: TextEdit::new("  CAFÉ  "),
            ..State::default()
        };
        preview(&mut state);
        state
            .snapshot
            .recent
            .push("Meet at the café on Monday.".into());
        let mut rt = Runtime::new(state, view, (1000.0, 700.0), Env::new(true, 1.0));
        rt.frame(0.0);
        assert!(rt.find("recent-search").is_some());
        assert!(rt.find("edit-0").is_none());
        click(&mut rt, "edit-1");
        assert_eq!(rt.state.edit_input.text, "Meet at the café on Monday.");
    }
    #[test]
    fn settings_drafts_survive_polling_failure_and_cancellation() {
        let mut s = State::default();
        preview(&mut s);
        s.preferences
            .edits
            .insert("hotkey".into(), TextEdit::new("F10"));
        s.preferences.dirty.insert("hotkey".into());
        s.preferences.saving = true;
        s.preferences.job_id = "new".into();
        let mut snapshot = s.snapshot.clone();
        snapshot.job.id = "old".into();
        settings_ui::sync(&mut s, &snapshot);
        assert!(s.preferences.saving);
        assert_eq!(s.preferences.edits["hotkey"].text, "F10");
        snapshot.job.id = "new".into();
        snapshot.job.cancelled = true;
        settings_ui::sync(&mut s, &snapshot);
        assert!(!s.preferences.saving);
        assert!(s.preferences.dirty.contains("hotkey"));
        s.preferences.saving = true;
        snapshot.job.cancelled = false;
        snapshot.job.failed = true;
        settings_ui::sync(&mut s, &snapshot);
        assert!(s.preferences.dirty.contains("hotkey"));
        s.preferences.saving = true;
        snapshot.job.failed = false;
        settings_ui::sync(&mut s, &snapshot);
        assert!(s.preferences.dirty.is_empty());
    }
    #[test]
    fn default_route_keeps_general_settings_and_external_routes_keep_drafts() {
        let mut s = State::default();
        dashboard_ipc::route(&mut s, &json!({"page":"settings","section":""}));
        assert_eq!(s.preferences.section, "general");
        s.preferences.dirty.insert("hotkey".into());
        dashboard_ipc::route(&mut s, &json!({"page":"words"}));
        assert_eq!(s.page, Page::Words);
        assert!(s.preferences.dirty.contains("hotkey"));
    }
    #[test]
    fn settings_search_and_word_editor_use_real_controls() {
        let mut s = State::default();
        preview(&mut s);
        s.page = Page::Settings;
        let mut rt = Runtime::new(s, view, (860.0, 600.0), Env::new(true, 1.0));
        rt.frame(0.0);
        assert!(rt.find("setting-hotkey-trigger").is_some());
        rt.update(|s, _| s.preferences.search = TextEdit::new("clipboard"));
        for _ in 0..30 {
            rt.frame(1.0 / 60.0);
        }
        assert!(rt.find("setting-hotkey-trigger").is_none());
        assert!(rt.find("setting-restore_clipboard").is_some());
        click(&mut rt, "nav-Words");
        click(&mut rt, "new-snippet");
        assert!(rt.state.vocabulary.snippet);
        assert!(rt.find("snippet-text").is_some());
    }
}
