use rune::tok::type_;
use rune::{
    Align, App, AppSpec, Color, Cx, El, OverlayOptions, OverlaySpec, ScreenEdge, col, el, row, text,
};
use std::io::{self, BufRead, Write};

const HUD_SIZE: (f32, f32) = (408.0, 118.0);

#[derive(Clone)]
struct Hud {
    level: f32,
    processing: bool,
    draft: String,
}
impl Default for Hud {
    fn default() -> Self {
        Self {
            level: 0.25,
            processing: false,
            draft: String::new(),
        }
    }
}
fn c(r: f32, g: f32, b: f32) -> Color {
    Color { r, g, b, a: 1.0 }
}
fn view(s: &Hud, _: &mut Cx<Hud>) -> El {
    let accent = if s.processing {
        c(0.57, 0.69, 0.83)
    } else {
        c(0.39, 0.84, 0.72)
    };
    let bars = [0.35_f32, 0.65, 0.9, 0.65, 0.35];
    let mut meter = row().key("meter").gap(3.0).center().h(24.0);
    for (i, shape) in bars.iter().enumerate() {
        let h = if s.processing {
            5.0
        } else {
            (4.0 + shape * s.level.clamp(0.0, 1.0) * 18.0).max(4.0)
        };
        meter = meter.child(
            el().key(format!("bar-{i}"))
                .size(3.0, h)
                .radius(1.5)
                .fill(accent),
        );
    }
    let label = if s.processing {
        "Finishing…"
    } else {
        "Listening"
    };
    let mut overlay = col()
        .key("overlay")
        .w_full()
        .h_full()
        .items_center()
        .justify_end()
        .pb(10.0)
        .gap(8.0);
    if !s.draft.is_empty() {
        overlay = overlay.child(
            row()
                .max_w(390.0)
                .px(16.0)
                .py(8.0)
                .center_y()
                .radius(12.0)
                .fill(c(0.10, 0.14, 0.17))
                .child(
                    text(s.draft.clone())
                        .key("draft")
                        .font(type_::BODY)
                        .color(c(0.96, 0.98, 0.97))
                        .wrap()
                        .max_lines(2),
                ),
        );
    }
    overlay.child(
        row()
            .key("pill")
            .h(44.0)
            .px(17.0)
            .gap(12.0)
            .center()
            .radius(22.0)
            .fill(c(0.10, 0.14, 0.17))
            .shadow(
                4.0,
                18.0,
                Color {
                    r: 0.0,
                    g: 0.0,
                    b: 0.0,
                    a: 0.27,
                },
            )
            .child(meter)
            .child(
                text(label)
                    .key("status")
                    .font(type_::LABEL)
                    .color(c(0.96, 0.98, 0.97)),
            ),
    )
}
fn spec() -> AppSpec<Hud> {
    AppSpec {
        scenes: &[
            ("listening", |s| {
                s.level = 0.8;
            }),
            ("processing", |s| {
                s.processing = true;
            }),
            ("draft", |s| {
                s.draft = "Let's move the design review to Friday morning.".into();
            }),
        ],
        ..AppSpec::new("Falco overlay", HUD_SIZE, Hud::default, view)
    }
}
fn main() {
    if std::env::args().any(|a| a == "--version") {
        println!("{}", env!("CARGO_PKG_VERSION"));
        return;
    }
    if std::env::args().any(|a| matches!(a.as_str(), "--snap" | "--tree" | "--list-scenes")) {
        rune::run(spec());
        return;
    }
    let mut app = App::new(spec()).windowless().accessory();
    let overlay = app.overlay(
        OverlaySpec {
            name: "phonon-dictation",
            size: HUD_SIZE,
            edge: ScreenEdge::Bottom,
            margin: 32.0,
            align: Align::Center,
            inset: 0.0,
            interactive: false,
            view,
        }
        .options(OverlayOptions {
            prewarm: true,
            ..Default::default()
        }),
        Hud::default(),
    );
    let control = app.handle();
    std::thread::spawn(move || {
        for line in io::stdin().lock().lines() {
            let Ok(line) = line else { break };
            if let Some(json) = line.strip_prefix("preview ") {
                if let Ok(draft) = serde_json::from_str::<String>(json) {
                    overlay.update(move |s, _| s.draft = draft);
                }
                continue;
            }
            let mut words = line.split_whitespace();
            match words.next() {
                Some("show") => {
                    overlay.update(|s, _| {
                        s.processing = false;
                        s.level = 0.0;
                        s.draft.clear();
                    });
                    overlay.show();
                }
                Some("hide") => {
                    overlay.hide();
                    overlay.update(|s, _| s.draft.clear());
                }
                Some("processing") => overlay.update(|s, _| {
                    s.processing = true;
                    s.draft.clear();
                }),
                Some("level") => {
                    if let Some(Ok(level)) = words.next().map(str::parse::<f32>) {
                        if level.is_finite() {
                            overlay.update(move |s, _| s.level = level.clamp(0.0, 1.0));
                        }
                    }
                }
                Some("status") => {
                    let request = words.next().unwrap_or("0");
                    let _ = writeln!(io::stdout(), "{:?} {}", overlay.availability(), request);
                    let _ = io::stdout().flush();
                }
                Some("quit") => break,
                _ => {}
            }
        }
        control.quit();
    });
    app.run();
}
