# Product

<!-- impeccable:product-schema 1 -->

## Platform

Linux desktop (GNOME Wayland and X11 among the intended environments).

## People and purpose

Phonon Linux helps a person dictate text into the application they are using. It listens through a shortcut, transcribes locally and refines the transcript with a model trained for dictation cleanup. The user wants the app to make dictation status, recent dictations, custom words and settings accessible together.

## Capabilities and constraints

- Dictation, microphone handling, text insertion and configuration are provided by the existing Python service.
- Parakeet speech recognition and the Phonon LFM refiner run locally after the models are downloaded.
- Recent dictations are session data; do not claim durable history unless it is actually implemented and enabled.
- Preserve the current shortcuts, the Rune recording overlay, the service's privacy settings and existing functionality.
- Onboarding is out of scope for this work.
- The Linux app code is MIT-licensed; the separately distributed models have their own licenses.

## Open decisions

- Longer-term history retention and editing capabilities.
- Distribution strategy for the new Rune interface.
