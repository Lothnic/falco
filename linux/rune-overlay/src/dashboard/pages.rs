use super::*;
use rune::FileDialogOptions;
#[derive(Clone, Default, Deserialize)]
pub struct RestorePoint {
    pub label: String,
    pub path: String,
}

fn backup_button(restore: bool) -> El {
    let label = if restore {
        "Restore from backup…"
    } else {
        "Save a backup…"
    };
    row().key(if restore { "restore-backup" } else { "save-backup" }).role("button").label(label).focusable(true)
        .min_h(38.0).px(14.0).radius(8.0).center().fill(rail()).hover(edge())
        .on_press_tx(move |_: &mut State, tx| {
            let options = FileDialogOptions { title: label.into(), file_name: if restore { None } else { Some("Falco-settings.zip".into()) }, ..Default::default() }.filter("Settings backup", &["zip"]);
            let answer = move |s: &mut State, result: rune::FileDialogResult, _: &mut rune::Tx| {
                match result {
                    Ok(Some(path)) => {
                        let request = json!({"action":if restore {"restore"} else {"backup"},"path":path,"confirmed":true});
                        if restore { s.confirmation = Some((format!("Replace current settings, words and snippets with {}? An automatic restore point is kept.",path.display()),request)); }
                        else { send_request(request); }
                    }
                    Ok(None) => (),
                    Err(error) => {s.notice = format!("The desktop file picker could not open: {error}");s.notice_error=true;}
                }
            };
            if restore { tx.open_file(options, answer); } else { tx.save_file(options, answer); }
        }).child(text(label).font(type_::LABEL).color(ink()))
}

pub fn stats(s: &State, layer: &mut Vec<El>) -> El {
    let mut content = col().w_full().gap(18.0).child(page_header(
        "Usage",
        "Your dictation counts stay on this computer. Text is never stored in usage statistics.",
    ));
    for row in &s.snapshot.stats_rows {
        content = content
            .child(info_row(&row.label, &row.value))
            .child(rule());
    }
    content
        .child(secondary("Time saved estimates typing the same words at your typing speed, minus time spent speaking."))
        .child(settings_ui::extra_fields(s, "stats", layer))
        .child(request_button(
            s,
            "Reset usage statistics",
            "reset-stats",
            json!({"action":"reset_stats","confirmed":true}),
            false,
            Some(
                "Permanently reset all usage counts? Your settings and vocabulary will stay."
                    .into(),
            ),
        ))
}
pub fn updates(s: &State, layer: &mut Vec<El>) -> El {
    let mut points = col()
        .w_full()
        .gap(10.0)
        .child(title("Earlier restore points"));
    if s.snapshot.restore_points.is_empty() {
        points = points.child(secondary(
            "Automatic copies appear here after settings change.",
        ));
    }
    for (index, point) in s.snapshot.restore_points.iter().enumerate() {
        points = points.child(
            row()
                .w_full()
                .gap(12.0)
                .center_y()
                .child(body(point.label.clone()).grow(1.0))
                .child(request_button(
                    s,
                    "Restore",
                    &format!("restore-point-{index}"),
                    json!({"action":"restore","path":point.path,"confirmed":true}),
                    false,
                    Some(format!(
                        "Restore the setup from {}? A copy of your current setup is kept first.",
                        point.label
                    )),
                )),
        );
    }
    col().w_full().gap(20.0).child(page_header("Updates & backup", "Keep Falco current and keep a copy of your setup."))
        .child(info_row("Installed version",&format!("Falco {}",s.snapshot.version)))
        .child(secondary("The unified interface is included with this version. Model downloads remain separate."))
        .child(settings_ui::extra_fields(s,"updates",layer))
        .child(row().gap(12.0)
            .child(request_button(s, "Check for updates","check-updates",json!({"action":"check_updates"}),false,None))
            .child(request_button(s, "Install latest update","install-update",json!({"action":"install_update"}),true,
                Some("Download and install the latest release? You will reopen Falco afterwards. Settings and models are retained.".into()))))
        .child(rule()).child(title("Settings backup"))
        .child(secondary("Includes settings, your custom words, snippets and usage counts. Model weights are not included."))
        .child(row().gap(12.0).child(backup_button(false)).child(backup_button(true)))
        .child(points)
        .child(rule()).child(title("About Falco"))
        .child(secondary("Local dictation for Linux. Built on TuxTalk and Phonon. MIT for the Linux app; models retain their own licenses."))
        .child(secondary("Your audio and dictation stay on your machine. No account is required."))
}

pub fn help(s: &State) -> El {
    let mut page = col().w_full().gap(22.0).child(page_header(
        "Help",
        "A few things to make dictation feel natural.",
    ));
    for (title, detail) in [
        ("Start a dictation", format!("Hold {} while speaking, then release to insert the text. The toggle shortcut is {}. Configure both in Settings → General.",s.snapshot.hotkey,s.snapshot.toggle_hotkey)),
        ("Use Command Mode", "On Wayland, enable Command Mode in Settings → General. Its default shortcut is Ctrl+Alt+C: press once, say what to change or write, then press again. Selected text is rewritten; an empty selection creates a draft at the cursor. Missing AI files download when you enable it. Esc cancels; drafts are not automatically submitted.".into()),
        ("Choose a speech model", "Settings → Speech lets you choose the model, device and language. CPU works on every computer. Parakeet supports English and 24 European languages; choose Whisper for Hindi and other languages.".into()),
        ("Refine your text", "Settings → Refiner controls cleanup, writing style and optional Phonon acceleration. Models run locally. Applying changes downloads missing files first; you can cancel without changing the saved setup.".into()),
        ("See a live transcript", "Enable Show live transcript in Settings → Appearance. With CPU Parakeet, Start typing sooner in Audio also works during speech pauses. Preview text can change; only completed, checked text is inserted.".into()),
        ("Teach Falco a name", "Your words keeps spelling, alternate pronunciations and snippets together. Add a word as it should be spelled and, optionally, the phrases Falco hears instead. Snippets turn a distinctive spoken phrase into longer text.".into()),
        ("When a shortcut doesn’t work", "Apply your saved shortcuts, start dictation, then use Test saved shortcuts in Settings → General. If nothing is heard, check typing access in Advanced. Administrator approval opens through your desktop’s standard authentication dialog.".into()),
        ("Keep your setup", "Updates & backup can save or restore settings, vocabulary and snippets. A backup does not include model weights. Usage counts contain numbers only; recent dictation text is temporary session data.".into()),
    ] {
        page = page.child(col().w_full().gap(8.0).child(super::title(title)).child(body(detail))).child(rule());
    }
    page
}

#[derive(Clone, Default, Deserialize)]
pub struct VoiceCommand {
    pub group: String,
    pub section: String,
    pub phrase: String,
    pub detail: String,
    pub note: String,
}
pub fn commands(s: &State) -> El {
    let mut page=col().w_full().gap(18.0).child(page_header("Voice commands","Hold your dictation key, say the command, then release. Commands use English words in every dictation language."))
        .child(text_input(&s.commands_query,type_::BODY).key("commands-search").label("Search voice commands").placeholder("Find a command…",muted()).single_line().w_full().h(40.0).px(12.0).py(10.0).radius(8.0).fill(panel()).color(ink()).on_edit(|s:&mut State| &mut s.commands_query));
    let query = s.commands_query.text.to_lowercase();
    let mut section = String::new();
    let mut count = 0;
    for command in &s.snapshot.commands {
        if !format!(
            "{} {} {} {} {}",
            command.group, command.section, command.phrase, command.detail, command.note
        )
        .to_lowercase()
        .contains(&query)
        {
            continue;
        }
        count += 1;
        if section != command.section {
            section = command.section.clone();
            page = page.child(title(format!("{} · {}", command.group, command.section)));
        }
        let mut entry = col()
            .w_full()
            .gap(5.0)
            .child(body(command.phrase.clone()))
            .child(secondary(command.detail.clone()));
        if !command.note.is_empty() {
            entry = entry.child(secondary(command.note.clone()));
        }
        page = page.child(entry).child(rule());
    }
    if count == 0 {
        page = page.child(secondary("No matching commands. Try a shorter search."));
    }
    page
}
