//! One dashboard per login session; tray routes bring that same window forward.
use super::*;
use std::fs::{self, File, OpenOptions};
use std::io::{BufRead, BufReader, Read};
use std::os::fd::AsRawFd;
use std::os::unix::{
    fs::{MetadataExt, PermissionsExt},
    net::{UnixListener, UnixStream},
};
use std::path::PathBuf;

pub struct Instance {
    _lock: File,
    pub listener: UnixListener,
    path: PathBuf,
}
impl Drop for Instance {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path);
    }
}

pub fn route(s: &mut State, request: &Value) {
    s.page = match request
        .get("page")
        .and_then(Value::as_str)
        .unwrap_or("overview")
    {
        "settings" => Page::Settings,
        "words" => Page::Words,
        "recent" => Page::Recent,
        "stats" => Page::Stats,
        "help" => Page::Help,
        "commands" => Page::Commands,
        "updates" | "about" => Page::Updates,
        _ => Page::Home,
    };
    if let Some(section) = request.get("section").and_then(Value::as_str) {
        if !section.is_empty() {
            s.preferences.section = section.into();
        }
    }
    s.preferences.open = None;
}
pub fn requested_route() -> Value {
    let args: Vec<_> = std::env::args().collect();
    let get = |key| {
        args.windows(2)
            .find(|w| w[0] == key)
            .map(|w| w[1].clone())
            .unwrap_or_default()
    };
    json!({"page":get("--page"), "section":get("--section")})
}

pub fn claim() -> Option<Instance> {
    // The fallback directory is private to the kernel's actual uid, not an environment value.
    let uid = unsafe { libc::geteuid() };
    let directory = PathBuf::from(
        std::env::var_os("XDG_RUNTIME_DIR").unwrap_or_else(|| format!("/tmp/falco-{uid}").into()),
    )
    .join(format!("falco-dashboard-{}", env!("CARGO_PKG_VERSION")));
    fs::create_dir_all(&directory).expect("private dashboard directory");
    let metadata = fs::symlink_metadata(&directory).expect("dashboard directory metadata");
    assert!(
        metadata.is_dir() && metadata.uid() == uid,
        "dashboard directory must belong to this user"
    );
    fs::set_permissions(&directory, fs::Permissions::from_mode(0o700))
        .expect("private dashboard permissions");
    let path = directory.join("window.sock");
    let lock = OpenOptions::new()
        .create(true)
        .truncate(false)
        .read(true)
        .write(true)
        .open(directory.join("window.lock"))
        .expect("dashboard lock");
    if unsafe { libc::flock(lock.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } != 0 {
        for _ in 0..100 {
            if let Ok(mut stream) = UnixStream::connect(&path) {
                let _ = writeln!(stream, "{}", requested_route());
                return None;
            }
            std::thread::sleep(Duration::from_millis(20));
        }
        eprintln!("The Falco window is still starting. Try again shortly.");
        return None;
    }
    let _ = fs::remove_file(&path);
    let listener = UnixListener::bind(&path).expect("dashboard socket");
    Some(Instance {
        _lock: lock,
        listener,
        path,
    })
}

pub fn listen(instance: &Instance, handle: rune::AppHandle<State>) {
    let listener = instance.listener.try_clone().expect("dashboard listener");
    std::thread::spawn(move || {
        for stream in listener.incoming().flatten() {
            let mut line = String::new();
            let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
            if BufReader::new(stream)
                .take(4096)
                .read_line(&mut line)
                .is_ok()
            {
                if let Ok(request) = serde_json::from_str::<Value>(&line) {
                    handle.update(move |s: &mut State, _| route(s, &request));
                    handle.open();
                }
            }
        }
    });
}
