"""Optional acceleration, offered only after the Phonon setup is ready."""
from . import ai_download, config


def eligible(cfg):
    return (not cfg.refiner_acceleration_offered and not cfg.refiner_acceleration
            and (cfg.ai_corrections or cfg.voice_editing or cfg.command_mode)
            and ai_download.selected_model(cfg) == "phonon"
            and ai_download.is_installed("phonon"))


def dismiss():
    cfg = config.load_config()
    cfg.refiner_acceleration_offered = True
    config.save_config(cfg)
    return {"ok": True, "message": "You can enable acceleration later in Settings → Refiner."}


def enable(report, cancel):
    from .ui_operations import _check, _download
    if not eligible(config.load_config()):
        raise ValueError("Your refiner setup changed. Use Settings → Refiner to enable acceleration.")
    report("Downloading the optional Phonon drafter (215 MB)…", 1)
    _download(ai_download.make_drafter_download_func(), report, cancel)
    _check(cancel)
    # Downloads can take minutes: retain unrelated settings, and never enable
    # a drafter after the user changed models or declined in another window.
    cfg = config.load_config()
    if not eligible(cfg):
        raise ValueError("Your refiner setup changed. The drafter is cached; acceleration was not enabled.")
    cfg.refiner_acceleration = True
    cfg.refiner_acceleration_offered = True
    config.save_config(cfg)
    # A recording may have started during the download. Let the user restart
    # when ready rather than interrupting dictation to reload its models.
    return {"message": "Drafter ready. Restart dictation to use acceleration. Turn it off in Settings → Refiner if slower."}
