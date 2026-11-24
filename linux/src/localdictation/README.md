# Falco 2.5: where things are

One line per group, its main file first. Each module's docstring says what it
is for.

- **Tray and menus:** `tray.py`, with `tray_menu.py` (the menu), `tray_service.py`
  (starting and stopping the service), `tray_dbus_app.py` and `dbus_service.py`
  (what the GNOME extension calls), and `menu_window.py` (the menu as a window
  where there is no tray).
- **Dictation service:** `app.py`, with `pipeline.py` (audio to text in the
  window), `recording.py`, `dictation_worker.py`, `service_tick.py` and
  `service_launcher.py` (the one place that starts and stops it),
  `code_dictation.py` (developer mode's spoken file names, casing and symbols)
  and `learned_words.py` (names learned from the refiner's spelling fixes).
- **Preferences:** `prefs.py`, with one `prefs_*.py` file per tab or part
  (`prefs_general.py`, `prefs_speech.py`, `prefs_audio.py`, `prefs_advanced.py`,
  `prefs_words.py`, `prefs_updates.py` and the rest); `prefs_tab.py` holds what
  the tabs share.
- **Hotkeys and the hotkey helper:** `hotkeys.py`, with `hotkey_helper.py` (the
  helper that reads the keyboards), `hotkey_helper_client.py`,
  `modifier_hotkeys.py` (Right Ctrl, Right Alt, Left Ctrl+Space),
  `secure_input.py`, the desktop hold-backs (`kwin_hotkeys.py`,
  `cosmic_hotkeys.py`, `x11_hotkeys.py`) and the first-run test
  (`hotkey_test_dialog.py`).
- **Typing and the virtual keyboard:** `virtual_keyboard.py`, with
  `keyboard_layout.py` (which keys to press for the layout), `keyboard_output.py`
  (typing and pasting), `delivery.py` (a finished dictation into the window) and
  `clipboard.py`.
- **Speech engines:** `engine.py`, with `parakeet_engine.py`, `parakeet_gpu.py`,
  `parakeet_ultra.py` (the Parakeet download), `whisper_vulkan.py` (the Vulkan
  engine) and `model_helper.py` (downloading and loading the models).
- **Refinement:** `ai_cleanup.py` and `ai_server.py` (the local model and optional
  DFlash2 launch), `ai_download.py` and `hub_pins.py` (pinned, checked weights),
  `ai_stream.py` (SSE and complete-answer validation), `refiner_prefetch.py`
  (reuse during pauses), `refiner_preview.py` (provisional Rune text) and
  `prefs_refiner.py` (the optional acceleration download).
- **Voice commands:** `voice_actions.py`, with `command_phrases.py` (the one
  parser), `voice_commands.py` (undo, "fix that word", select and move),
  `commands_reference.py` (the table Help shows), and one file per kind of
  command (`open_app.py`, `window_actions.py`, `desktop_actions.py`,
  `web_commands.py`, `mouse_grid.py`, `voice_edit.py` and others).
- **Help:** `help_dialog.py`, with `help_text.py` (what it says),
  `help_pages.py` and `cards.py` (the card look), and
  `problem_report_window.py` (Report a Problem).
