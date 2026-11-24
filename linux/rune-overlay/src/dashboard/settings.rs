use super::*;
use rune_kit::{Kit, Select, SelectAppearance, Switch};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Default, Deserialize)]
pub struct Choice {
    pub value: String,
    pub label: String,
}
#[derive(Clone, Default, Deserialize)]
pub struct Field {
    pub section: String,
    pub key: String,
    pub label: String,
    pub hint: String,
    pub kind: String,
    pub value: String,
    pub datatype: String,
    pub choices: Vec<Choice>,
}
#[derive(Clone, Default, Deserialize)]
#[serde(default)]
pub struct Job {
    pub id: String,
    pub busy: bool,
    pub failed: bool,
    pub cancelled: bool,
    pub cancellable: bool,
    pub message: String,
    pub progress: u32,
    pub result: Value,
}
#[derive(Clone, Default, Deserialize)]
pub struct StatRow {
    pub label: String,
    pub value: String,
}

pub struct Preferences {
    pub section: String,
    pub search: TextEdit,
    pub edits: BTreeMap<String, TextEdit>,
    pub dirty: BTreeSet<String>,
    pub open: Option<String>,
    pub saving: bool,
    pub job_id: String,
}
impl Default for Preferences {
    fn default() -> Self {
        Self {
            section: "general".into(),
            search: TextEdit::new(""),
            edits: BTreeMap::new(),
            dirty: BTreeSet::new(),
            open: None,
            saving: false,
            job_id: String::new(),
        }
    }
}

pub fn sync(s: &mut State, snapshot: &Snapshot) {
    if s.preferences.saving
        && !s.preferences.job_id.is_empty()
        && snapshot.job.id == s.preferences.job_id
        && !snapshot.job.busy
    {
        s.preferences.saving = false;
        if !snapshot.job.failed && !snapshot.job.cancelled {
            s.preferences.dirty.clear();
        }
    }
    for field in &snapshot.settings {
        if !s.preferences.dirty.contains(&field.key) {
            let edit = s.preferences.edits.entry(field.key.clone()).or_default();
            if edit.text != field.value {
                *edit = TextEdit::new(field.value.clone());
            }
        }
    }
}

pub fn kit() -> Kit {
    let mut kit = Kit::neutral(true);
    kit.c.text_base = ink();
    kit.c.text_muted = muted();
    kit.c.text_faint = muted();
    kit.c.text_accent = accent();
    kit.c.bg_accent = accent();
    kit.c.border_focus = accent();
    kit.c.surface_base = panel();
    kit.c.surface_raised = rail();
    kit.c.bg_base = panel();
    kit.c.layer_01 = rail();
    kit.c.hover = muted_accent();
    kit
}

fn apply(s: &mut State) {
    let mut changes = serde_json::Map::new();
    for field in &s.snapshot.settings {
        if !s.preferences.dirty.contains(&field.key) {
            continue;
        }
        let value = &s.preferences.edits[&field.key].text;
        let parsed = match field.datatype.as_str() {
            "bool" => Some(Value::Bool(value == "true")),
            "int" => value.parse::<i64>().ok().map(Value::from),
            "float" => value
                .parse::<f64>()
                .ok()
                .filter(|v| v.is_finite())
                .map(Value::from),
            _ => Some(Value::String(value.clone())),
        };
        let Some(parsed) = parsed else {
            s.notice = format!(
                "{} needs a valid number. Your changes are still here.",
                field.label
            );
            s.notice_error = true;
            return;
        };
        changes.insert(field.key.clone(), parsed);
    }
    if changes.is_empty() {
        return;
    }
    send_request(json!({"action":"save_settings", "changes":changes}));
    s.notice = "Preparing your changes…".into();
    s.notice_error = false;
    s.preferences.job_id.clear();
    s.preferences.saving = true;
}

fn field(s: &State, field: &Field, layer: &mut Vec<El>) -> El {
    let prefs = &s.preferences;
    let value = prefs
        .edits
        .get(&field.key)
        .map(|e| e.text.as_str())
        .unwrap_or(&field.value);
    let key = field.key.clone();
    let busy = s.snapshot.job.busy || prefs.saving;
    let control = if field.kind == "bool" {
        let enabled = value == "true";
        Switch::new(enabled)
            .label(field.label.clone())
            .hide_label()
            .disabled(busy)
            .on_toggle(move |s: &mut State| {
                s.preferences.edits.insert(
                    key.clone(),
                    TextEdit::new(if enabled { "false" } else { "true" }),
                );
                s.preferences.dirty.insert(key.clone());
            })
            .build(&kit())
            .key(format!("setting-{}", field.key))
    } else if field.kind == "choice" {
        let label = field
            .choices
            .iter()
            .find(|c| c.value == value)
            .map(|c| c.label.as_str())
            .unwrap_or(value);
        let labels: Vec<_> = field.choices.iter().map(|c| c.label.clone()).collect();
        let toggle_key = key.clone();
        let choices = field.choices.clone();
        let choose_key = key.clone();
        Select::new(format!("setting-{key}"), &labels)
            .current(Some(label))
            .label(field.label.clone())
            .appearance(SelectAppearance::Field)
            .width(220.0)
            .disabled(busy)
            .open(prefs.open.as_deref() == Some(&key))
            .on_toggle(move |s: &mut State| {
                s.preferences.open = if s.preferences.open.as_deref() == Some(&toggle_key) {
                    None
                } else {
                    Some(toggle_key.clone())
                };
            })
            .on_close(|s: &mut State| s.preferences.open = None)
            .on_choose(move |s: &mut State, label, _| {
                if let Some(choice) = choices.iter().find(|c| c.label == label) {
                    s.preferences
                        .edits
                        .insert(choose_key.clone(), TextEdit::new(choice.value.clone()));
                    s.preferences.dirty.insert(choose_key.clone());
                }
                s.preferences.open = None;
            })
            .build(&kit(), layer)
    } else {
        let edit = prefs
            .edits
            .get(&key)
            .expect("setting drafts initialized with snapshot");
        let mut input = text_input(edit, type_::BODY)
            .key(format!("setting-{key}"))
            .label(field.label.clone())
            .single_line()
            .w(220.0)
            .min_h(38.0)
            .px(12.0)
            .py(10.0)
            .radius(8.0)
            .fill(panel())
            .color(ink());
        if !busy {
            input = input.on_edit(move |s: &mut State| {
                s.preferences.dirty.insert(key.clone());
                s.preferences.edits.get_mut(&key).unwrap()
            });
        }
        input
    };
    row()
        .key(format!("field-{}", field.key))
        .w_full()
        .min_h(70.0)
        .py(10.0)
        .gap(24.0)
        .center_y()
        .child(
            col()
                .gap(6.0)
                .grow(1.0)
                .min_w(0.0)
                .child(body(field.label.clone()))
                .child(secondary(field.hint.clone())),
        )
        .child(control)
}

pub fn view(s: &State, layer: &mut Vec<El>) -> El {
    let mut content = col()
        .w_full()
        .gap(18.0)
        .child(page_header(
            "Settings",
            "Make Falco work the way you speak.",
        ))
        .child(
            text_input(&s.preferences.search, type_::BODY)
                .key("settings-search")
                .label("Search settings")
                .placeholder("Find a setting…", muted())
                .single_line()
                .w_full()
                .h(40.0)
                .px(12.0)
                .py(10.0)
                .radius(8.0)
                .fill(panel())
                .color(ink())
                .on_edit(|s: &mut State| &mut s.preferences.search),
        );
    let sections = [
        ("general", "General"),
        ("speech", "Speech"),
        ("audio", "Audio"),
        ("refiner", "Refiner"),
        ("text", "Text"),
        ("appearance", "Appearance"),
        ("advanced", "Advanced"),
    ];
    for chunk in sections.chunks(4) {
        let mut tabs = row().w_full().gap(6.0);
        for &(id, label) in chunk {
            tabs =
                tabs.child(
                    row()
                        .key(format!("settings-{id}"))
                        .role("button")
                        .label(label)
                        .focusable(true)
                        .min_h(34.0)
                        .px(12.0)
                        .radius(7.0)
                        .center()
                        .fill(if s.preferences.section == id {
                            muted_accent()
                        } else {
                            rail()
                        })
                        .hover(edge())
                        .on_press(move |s: &mut State| {
                            s.preferences.section = id.into();
                            s.preferences.open = None;
                            s.preferences.search.clear();
                        })
                        .child(text(label).font(type_::LABEL).color(
                            if s.preferences.section == id {
                                accent()
                            } else {
                                ink()
                            },
                        )),
                );
        }
        content = content.child(tabs);
    }
    let query = s.preferences.search.text.to_lowercase();
    let matches: Vec<_> = s
        .snapshot
        .settings
        .iter()
        .filter(|f| {
            if query.is_empty() {
                f.section == s.preferences.section
            } else {
                format!("{} {}", f.label, f.hint)
                    .to_lowercase()
                    .contains(&query)
            }
        })
        .collect();
    if matches.is_empty() {
        content = content.child(secondary(if s.loaded {
            "No matching settings. Try a shorter search."
        } else {
            "Loading your settings…"
        }));
    }
    for f in matches {
        content = content.child(field(s, f, layer)).child(rule());
    }
    if s.preferences.section == "audio" {
        content = content.child(request_button(
            s,
            "Test microphone",
            "test-microphone",
            json!({"action":"microphone_test"}),
            false,
            None,
        ));
    }
    if s.preferences.section == "general" {
        content = content.child(secondary("Apply shortcut changes before testing. The test briefly pauses dictation and resumes it automatically."))
            .child(request_button(s, "Test saved shortcuts", "test-shortcuts", json!({"action":"hotkey_test"}), false, None));
    }
    if s.preferences.section == "speech" || s.preferences.section == "refiner" {
        content = content.child(secondary("Downloads stay on this computer. Apply can download missing files before saving; cancellation keeps the current setup."))
            .child(request_button(s, "Download selected models", "download-models", json!({"action":"download_models"}), false, None));
    }
    if s.preferences.section == "advanced" {
        for row in &s.snapshot.system_rows {
            content = content
                .child(info_row(&row.label, &row.value))
                .child(rule());
        }
        content = content.child(request_button(
            s,
            "Clear local log…",
            "clear-log",
            json!({"action":"clear_log","confirmed":true}),
            false,
            Some("Erase the local log and its rotated copy? This cannot be undone.".into()),
        ));
        content = content.child(request_button(s,"Set up typing access…","setup-keyboard",json!({"action":"setup_keyboard"}),false,
            Some("Install or update Falco’s keyboard helper and typing rule? Your desktop will ask for administrator approval.".into())));
        content = content.child(secondary("System permissions and hotkey access are managed by your Linux desktop. You can restart dictation after changing access."))
            .child(request_button(s, "Restart dictation", "restart-service", json!({"action":"restart_service"}), false, None));
    }
    content
}

pub fn save_bar(s: &State) -> El {
    let busy = s.snapshot.job.busy || s.preferences.saving;
    let dirty = !s.preferences.dirty.is_empty();
    let mut save = row()
        .key("apply-settings")
        .role("button")
        .label("Apply changes")
        .h(38.0)
        .px(16.0)
        .center()
        .radius(8.0)
        .fill(if dirty && !busy { accent() } else { rail() })
        .child(
            text(if busy { "Working…" } else { "Apply changes" })
                .font(type_::LABEL)
                .color(if dirty && !busy { bg() } else { muted() }),
        );
    if dirty && !busy {
        save = save
            .focusable(true)
            .hover(color(0.56, 0.90, 0.79))
            .on_press(apply);
    }
    let mut revert = row()
        .key("revert-settings")
        .role("button")
        .label("Discard changes")
        .h(38.0)
        .px(12.0)
        .center()
        .radius(8.0)
        .fill(rail())
        .child(text("Discard").font(type_::LABEL).color(if dirty && !busy {
            ink()
        } else {
            muted()
        }));
    if dirty && !busy {
        revert = revert
            .focusable(true)
            .hover(edge())
            .on_press(|s: &mut State| {
                s.preferences.dirty.clear();
                let snapshot = s.snapshot.clone();
                sync(s, &snapshot);
            });
    }
    row()
        .w_full()
        .py(12.0)
        .px(24.0)
        .gap(12.0)
        .center_y()
        .fill(rail())
        .child(
            secondary(if dirty {
                "Unsaved changes"
            } else {
                "All changes saved"
            })
            .grow(1.0),
        )
        .child(revert)
        .child(save)
}
pub fn extra_fields(s: &State, section: &str, layer: &mut Vec<El>) -> El {
    let mut result = col().w_full();
    for f in s.snapshot.settings.iter().filter(|f| f.section == section) {
        result = result.child(field(s, f, layer)).child(rule());
    }
    result
}
