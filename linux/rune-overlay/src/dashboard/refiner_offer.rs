//! A quiet, explicit opt-in. Rune owns modal focus and background inertness.
use super::*;

pub fn visible(s: &State) -> bool {
    s.loaded
        && s.snapshot.refiner_offer
        && !s.offer_closed
        && !s.snapshot.recording
        && !s.snapshot.job.busy
        && !s.preferences.saving
        && s.preferences.dirty.is_empty()
        && s.preferences.open.is_none()
        && s.confirmation.is_none()
        && !s.vocabulary.editing
        && !s.editing
        && matches!(s.page, Page::Home | Page::Settings)
}

fn answer(s: &mut State, accept: bool) {
    s.offer_closed = true;
    s.notice.clear();
    s.notice_error = false;
    if accept {
        s.page = Page::Settings;
        s.preferences.section = "refiner".into();
        s.preferences.search.clear();
    }
    send_request(json!({"action":"refiner_offer", "accept":accept}));
}

fn choice(label: &str, key: &str, accept: bool) -> El {
    let control = row()
        .key(key.to_owned())
        .role("button")
        .label(label.to_owned())
        .focusable(true)
        .min_h(42.0)
        .px(16.0)
        .center()
        .radius(8.0)
        .fill(if accept { accent() } else { panel() })
        .hover(if accept {
            color(0.56, 0.90, 0.79)
        } else {
            edge()
        })
        .on_press(move |s: &mut State| answer(s, accept))
        .child(
            text(label.to_owned())
                .font(type_::LABEL)
                .color(if accept { bg() } else { ink() }),
        );
    if accept {
        control
    } else {
        control.default_button()
    }
}

pub fn view(s: &State, layer: &mut Vec<El>) {
    rune_kit::Dialog::new("refiner-offer", "Try faster refinement?")
        .open(visible(s)).width(510.0).fit().click_outside(false)
        .on_close(|s: &mut State| answer(s, false))
        .child(col().padding(20.0).pt(4.0).gap(16.0)
            .child(body("Add Phonon’s optional DFlash2 drafter to speed up text cleanup."))
            .child(col().w_full().padding(14.0).gap(7.0).radius(8.0).fill(panel())
                .child(body("215 MB · one-time download · runs locally"))
                .child(secondary("32% less total refinement time in our RTX 4060 test. Gains vary; it can be slower on other hardware.")))
            .child(secondary("Restart dictation after the download to use it. You can turn it off in Settings → Refiner. Speech recognition is unchanged."))
            .child(row().w_full().gap(12.0).child(el().grow(1.0))
                .child(choice("Not now", "refiner-offer-decline", false))
                .child(choice("Download & enable", "refiner-offer-accept", true))))
        .build(&settings_ui::kit(), layer);
}
